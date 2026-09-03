from __future__ import annotations

import logging

from app.config import settings
from app.redis import get_redis

logger = logging.getLogger(__name__)

_KEY_PREFIX = "access_deny:"


def _deny_key(jti: str) -> str:
    return f"{_KEY_PREFIX}{jti}"


async def deny_access_jti(jti: str, ttl: int | None = None) -> None:
    redis = get_redis()
    if redis is None or not jti:
        return
    expire = ttl if ttl is not None else settings.ACCESS_TOKEN_EXPIRE_SECONDS + 60
    try:
        await redis.set(_deny_key(jti), "1", ex=expire)
    except Exception:
        logger.warning("access denylist write failed for jti=%s", jti, exc_info=True)


async def is_access_jti_denied(jti: str) -> bool:
    if not jti:
        return False
    redis = get_redis()
    if redis is None:
        return False
    try:
        return bool(await redis.exists(_deny_key(jti)))
    except Exception:
        logger.warning("access denylist read failed for jti=%s", jti, exc_info=True)
        return False
