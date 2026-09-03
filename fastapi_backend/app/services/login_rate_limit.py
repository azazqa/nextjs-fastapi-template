"""로그인 레이트리밋.

Redis가 설정되면 원자적 INCR 기반으로 동작한다.
미설정 시 상한이 있는 인메모리 폴백을 쓰지만, 이는 테스트·단일 워커 개발용이며
운영에서는 REDIS_URL 설정을 전제한다.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass

from redis.asyncio import Redis

from app.config import settings
from app.exceptions import RateLimitError
from app.redis import get_redis

_KEY_PREFIX = "login_rate:"

# 인메모리 폴백 상한 — 무제한 증가 방지 (H3)
_MAX_TRACKED_IDS = 10_000


def _normalize_login_id(login_id: str) -> str:
    return login_id.strip().lower()


def _locked_error(retry_after: int) -> RateLimitError:
    return RateLimitError(
        f"Too many failed login attempts. Try again in {retry_after} seconds.",
        retry_after=retry_after,
    )


# ---------------------------------------------------------------------------
# Redis — 원자적 구현 (C3)
# ---------------------------------------------------------------------------


def _fail_key(key: str) -> str:
    return f"{_KEY_PREFIX}fail:{key}"


def _lock_key(key: str) -> str:
    return f"{_KEY_PREFIX}lock:{key}"


async def _assert_login_allowed_redis(redis: Redis, key: str) -> None:
    ttl = await redis.ttl(_lock_key(key))
    if ttl > 0:
        raise _locked_error(ttl)


async def _record_login_failure_redis(redis: Redis, key: str) -> None:
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(_fail_key(key))
        # nx=True: TTL이 없을 때만 설정 → 실패마다 윈도우가 연장되지 않는다
        pipe.expire(_fail_key(key), settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS, nx=True)
        failures, _ = await pipe.execute()

    if failures >= settings.LOGIN_RATE_LIMIT_MAX_FAILURES:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.set(_lock_key(key), "1", ex=settings.LOGIN_RATE_LIMIT_LOCKOUT_SECONDS)
            pipe.delete(_fail_key(key))
            await pipe.execute()


async def _clear_login_failures_redis(redis: Redis, key: str) -> None:
    await redis.delete(_fail_key(key), _lock_key(key))


# ---------------------------------------------------------------------------
# 인메모리 폴백 — 상한 있음 (H3)
# ---------------------------------------------------------------------------


@dataclass
class _AttemptState:
    failures: int = 0
    window_expires_at: float = 0.0
    locked_until: float = 0.0


_store: OrderedDict[str, _AttemptState] = OrderedDict()


def _get_state(key: str, now: float) -> _AttemptState:
    state = _store.get(key)
    if state is None:
        state = _AttemptState()
        _store[key] = state
    else:
        _store.move_to_end(key)  # LRU 갱신

    # 지연 만료: 윈도우가 지났으면 실패 횟수를 초기화한다
    if state.window_expires_at and state.window_expires_at <= now:
        state.failures = 0
        state.window_expires_at = 0.0
    return state


def _enforce_capacity() -> None:
    """가장 오래 접근되지 않은 항목부터 제거해 상한을 지킨다."""
    while len(_store) > _MAX_TRACKED_IDS:
        _store.popitem(last=False)


def _assert_login_allowed_memory(key: str) -> None:
    now = time.monotonic()
    state = _get_state(key, now)
    if state.locked_until > now:
        raise _locked_error(max(1, int(state.locked_until - now)))


def _record_login_failure_memory(key: str) -> None:
    now = time.monotonic()
    state = _get_state(key, now)

    if state.failures == 0:
        state.window_expires_at = now + settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    state.failures += 1

    if state.failures >= settings.LOGIN_RATE_LIMIT_MAX_FAILURES:
        state.locked_until = now + settings.LOGIN_RATE_LIMIT_LOCKOUT_SECONDS
        state.failures = 0
        state.window_expires_at = 0.0

    _enforce_capacity()


def _clear_login_failures_memory(key: str) -> None:
    _store.pop(key, None)


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


async def assert_login_allowed(login_id: str) -> None:
    key = _normalize_login_id(login_id)
    if not key:
        return
    redis = get_redis()
    if redis is None:
        _assert_login_allowed_memory(key)
        return
    await _assert_login_allowed_redis(redis, key)


async def record_login_failure(login_id: str) -> None:
    key = _normalize_login_id(login_id)
    if not key:
        return
    redis = get_redis()
    if redis is None:
        _record_login_failure_memory(key)
        return
    await _record_login_failure_redis(redis, key)


async def clear_login_failures(login_id: str) -> None:
    key = _normalize_login_id(login_id)
    if not key:
        return
    redis = get_redis()
    if redis is None:
        _clear_login_failures_memory(key)
        return
    await _clear_login_failures_redis(redis, key)
