from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.redis import get_redis

logger = logging.getLogger(__name__)

_OK_PREFIX = "refresh_ok:"
_USER_PREFIX = "refresh_user:"


def _ok_key(token_hash: str) -> str:
    return f"{_OK_PREFIX}{token_hash}"


def _user_key(user_id: uuid.UUID) -> str:
    return f"{_USER_PREFIX}{user_id}"


def _ttl_seconds(expires_at: datetime) -> int:
    now = datetime.now(timezone.utc)
    exp = expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return max(1, min(int((exp - now).total_seconds()) + 1, settings.REFRESH_TOKEN_EXPIRE_SECONDS))


async def cache_valid_refresh(
    token_hash: str,
    *,
    user_id: uuid.UUID,
    row_id: uuid.UUID,
    expires_at: datetime,
) -> None:
    redis = get_redis()
    if redis is None:
        return
    ok_key = _ok_key(token_hash)
    payload = json.dumps({"user_id": str(user_id), "row_id": str(row_id)})
    ttl = _ttl_seconds(expires_at)
    try:
        pipe = redis.pipeline()
        pipe.set(ok_key, payload, ex=ttl)
        pipe.sadd(_user_key(user_id), token_hash)
        pipe.expire(_user_key(user_id), settings.REFRESH_TOKEN_EXPIRE_SECONDS)
        await pipe.execute()
    except Exception:
        logger.warning("refresh cache write failed hash=%s", token_hash[:8], exc_info=True)


async def invalidate_refresh_hash(token_hash: str, *, user_id: uuid.UUID | None = None) -> None:
    redis = get_redis()
    if redis is None:
        return
    try:
        await redis.delete(_ok_key(token_hash))
        if user_id is not None:
            await redis.srem(_user_key(user_id), token_hash)
    except Exception:
        logger.warning("refresh cache invalidate failed hash=%s", token_hash[:8], exc_info=True)


async def invalidate_user_refresh_cache(user_id: uuid.UUID) -> None:
    redis = get_redis()
    if redis is None:
        return
    uk = _user_key(user_id)
    try:
        hashes = await redis.smembers(uk)
        if hashes:
            await redis.delete(*[_ok_key(h) for h in hashes], uk)
        else:
            await redis.delete(uk)
    except Exception:
        logger.warning("refresh cache user invalidate failed user=%s", user_id, exc_info=True)
