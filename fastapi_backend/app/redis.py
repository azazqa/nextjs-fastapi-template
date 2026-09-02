from __future__ import annotations

from redis.asyncio import Redis

from app.config import settings

_redis: Redis | None = None


def get_redis() -> Redis | None:
    if not settings.REDIS_URL:
        return None
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
