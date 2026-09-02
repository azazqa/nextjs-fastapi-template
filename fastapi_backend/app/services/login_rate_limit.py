"""Login rate limit — Redis when REDIS_URL is set, in-memory otherwise (tests/single worker)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from redis.asyncio import Redis

from app.config import settings
from app.exceptions import RateLimitError
from app.redis import get_redis

_KEY_PREFIX = "login_rate:"


@dataclass
class _AttemptState:
    failures: list[float] = field(default_factory=list)
    locked_until: float | None = None


_store: dict[str, _AttemptState] = {}


def _normalize_login_id(login_id: str) -> str:
    return login_id.strip().lower()


def _prune_old_failures(state: _AttemptState, now: float) -> None:
    cutoff = now - settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    state.failures = [ts for ts in state.failures if ts >= cutoff]


def _state_ttl(state: _AttemptState, now: float) -> int:
    ttl = settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    if state.locked_until is not None and state.locked_until > now:
        ttl = max(ttl, int(state.locked_until - now) + 1)
    return ttl


def _raise_if_locked(state: _AttemptState, now: float) -> None:
    if state.locked_until is not None:
        if now < state.locked_until:
            retry_after = max(1, int(state.locked_until - now))
            raise RateLimitError(
                f"Too many failed login attempts. Try again in {retry_after} seconds.",
                retry_after=retry_after,
            )
        state.locked_until = None
        state.failures.clear()


def _record_failure(state: _AttemptState, now: float) -> None:
    _prune_old_failures(state, now)
    state.failures.append(now)
    if len(state.failures) >= settings.LOGIN_RATE_LIMIT_MAX_FAILURES:
        state.locked_until = now + settings.LOGIN_RATE_LIMIT_LOCKOUT_SECONDS


def _assert_login_allowed_memory(login_id: str) -> None:
    key = _normalize_login_id(login_id)
    if not key:
        return

    now = time.monotonic()
    state = _store.setdefault(key, _AttemptState())
    _raise_if_locked(state, now)


def _record_login_failure_memory(login_id: str) -> None:
    key = _normalize_login_id(login_id)
    if not key:
        return

    now = time.monotonic()
    state = _store.setdefault(key, _AttemptState())
    _record_failure(state, now)


def _clear_login_failures_memory(login_id: str) -> None:
    key = _normalize_login_id(login_id)
    _store.pop(key, None)


async def _load_redis_state(redis: Redis, key: str) -> _AttemptState:
    raw = await redis.get(f"{_KEY_PREFIX}{key}")
    if not raw:
        return _AttemptState()
    data = json.loads(raw)
    return _AttemptState(
        failures=list(data.get("failures", [])),
        locked_until=data.get("locked_until"),
    )


async def _save_redis_state(redis: Redis, key: str, state: _AttemptState, now: float) -> None:
    _prune_old_failures(state, now)
    await redis.set(
        f"{_KEY_PREFIX}{key}",
        json.dumps({"failures": state.failures, "locked_until": state.locked_until}),
        ex=_state_ttl(state, now),
    )


async def _assert_login_allowed_redis(redis: Redis, login_id: str) -> None:
    key = _normalize_login_id(login_id)
    if not key:
        return

    now = time.time()
    state = await _load_redis_state(redis, key)
    _raise_if_locked(state, now)
    await _save_redis_state(redis, key, state, now)


async def _record_login_failure_redis(redis: Redis, login_id: str) -> None:
    key = _normalize_login_id(login_id)
    if not key:
        return

    now = time.time()
    state = await _load_redis_state(redis, key)
    _record_failure(state, now)
    await _save_redis_state(redis, key, state, now)


async def _clear_login_failures_redis(redis: Redis, login_id: str) -> None:
    key = _normalize_login_id(login_id)
    if not key:
        return
    await redis.delete(f"{_KEY_PREFIX}{key}")


async def assert_login_allowed(login_id: str) -> None:
    redis = get_redis()
    if redis is None:
        _assert_login_allowed_memory(login_id)
        return
    await _assert_login_allowed_redis(redis, login_id)


async def record_login_failure(login_id: str) -> None:
    redis = get_redis()
    if redis is None:
        _record_login_failure_memory(login_id)
        return
    await _record_login_failure_redis(redis, login_id)


async def clear_login_failures(login_id: str) -> None:
    redis = get_redis()
    if redis is None:
        _clear_login_failures_memory(login_id)
        return
    await _clear_login_failures_redis(redis, login_id)
