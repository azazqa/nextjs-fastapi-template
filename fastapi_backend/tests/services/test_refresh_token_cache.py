import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services.refresh_token_cache import (
    cache_valid_refresh,
    invalidate_refresh_hash,
    invalidate_user_refresh_cache,
)
from app.services.refresh_tokens import hash_refresh_token


@pytest.mark.asyncio
async def test_refresh_cache_set_and_invalidate_hash(fake_redis):
    user_id = uuid.uuid7()
    row_id = uuid.uuid7()
    token_hash = hash_refresh_token("raw-refresh-token")
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    await cache_valid_refresh(
        token_hash, user_id=user_id, row_id=row_id, expires_at=expires_at
    )

    ok_key = f"refresh_ok:{token_hash}"
    payload = json.loads(await fake_redis.get(ok_key))
    assert payload["user_id"] == str(user_id)
    assert payload["row_id"] == str(row_id)

    await invalidate_refresh_hash(token_hash, user_id=user_id)
    assert await fake_redis.get(ok_key) is None


@pytest.mark.asyncio
async def test_invalidate_user_refresh_cache(fake_redis):
    user_id = uuid.uuid7()
    h1 = hash_refresh_token("token-a")
    h2 = hash_refresh_token("token-b")
    exp = datetime.now(timezone.utc) + timedelta(hours=1)

    await cache_valid_refresh(h1, user_id=user_id, row_id=uuid.uuid7(), expires_at=exp)
    await cache_valid_refresh(h2, user_id=user_id, row_id=uuid.uuid7(), expires_at=exp)

    await invalidate_user_refresh_cache(user_id)
    assert await fake_redis.get(f"refresh_ok:{h1}") is None
    assert await fake_redis.get(f"refresh_ok:{h2}") is None
