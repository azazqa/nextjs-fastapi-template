from __future__ import annotations

import logging
import uuid

from redis.asyncio import Redis

from app.config import settings
from app.redis import get_redis

logger = logging.getLogger(__name__)

_PERMS_PREFIX = "user_perms:"
_ROLES_PREFIX = "user_roles:"


def _perms_key(user_id: uuid.UUID) -> str:
    return f"{_PERMS_PREFIX}{user_id}"


def _roles_key(user_id: uuid.UUID) -> str:
    return f"{_ROLES_PREFIX}{user_id}"


async def get_cached_rbac(
    user_id: uuid.UUID,
) -> tuple[frozenset[str], tuple[str, ...]] | None:
    redis = get_redis()
    if redis is None:
        return None
    try:
        perms_raw, roles_raw = await redis.smembers(_perms_key(user_id)), await redis.smembers(
            _roles_key(user_id)
        )
        if not perms_raw and not roles_raw:
            return None
        return frozenset(perms_raw), tuple(sorted(roles_raw))
    except Exception:
        logger.warning("RBAC cache read failed for user %s", user_id, exc_info=True)
        return None


async def set_cached_rbac(
    user_id: uuid.UUID,
    permissions: frozenset[str] | set[str],
    roles: tuple[str, ...] | list[str],
) -> None:
    redis = get_redis()
    if redis is None:
        return
    ttl = settings.PERMISSION_CACHE_TTL_SECONDS
    pk, rk = _perms_key(user_id), _roles_key(user_id)
    try:
        pipe = redis.pipeline()
        pipe.delete(pk, rk)
        if permissions:
            pipe.sadd(pk, *sorted(permissions))
        if roles:
            pipe.sadd(rk, *sorted(roles))
        if permissions or roles:
            pipe.expire(pk, ttl)
            pipe.expire(rk, ttl)
        await pipe.execute()
    except Exception:
        logger.warning("RBAC cache write failed for user %s", user_id, exc_info=True)


async def invalidate_user_rbac(user_id: uuid.UUID) -> None:
    redis = get_redis()
    if redis is None:
        return
    try:
        await redis.delete(_perms_key(user_id), _roles_key(user_id))
    except Exception:
        logger.warning("RBAC cache invalidate failed for user %s", user_id, exc_info=True)


async def _scan_delete(redis: Redis, pattern: str) -> None:
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
        if keys:
            await redis.delete(*keys)
        if cursor == 0:
            break


async def invalidate_all_rbac() -> None:
    redis = get_redis()
    if redis is None:
        return
    try:
        await _scan_delete(redis, f"{_PERMS_PREFIX}*")
        await _scan_delete(redis, f"{_ROLES_PREFIX}*")
    except Exception:
        logger.warning("RBAC cache invalidate_all failed", exc_info=True)
