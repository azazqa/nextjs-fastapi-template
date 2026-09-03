import uuid

import pytest

from app.rbac.permission_cache import (
    get_cached_rbac,
    invalidate_all_rbac,
    invalidate_user_rbac,
    set_cached_rbac,
)


@pytest.mark.asyncio
async def test_permission_cache_miss(fake_redis):
    user_id = uuid.uuid7()
    assert await get_cached_rbac(user_id) is None


@pytest.mark.asyncio
async def test_permission_cache_hit(fake_redis):
    user_id = uuid.uuid7()
    await set_cached_rbac(user_id, {"scheduler:read", "scheduler:manage"}, ("operator",))

    perms, roles = await get_cached_rbac(user_id)
    assert perms == frozenset({"scheduler:read", "scheduler:manage"})
    assert roles == ("operator",)


@pytest.mark.asyncio
async def test_invalidate_user_rbac(fake_redis):
    user_id = uuid.uuid7()
    await set_cached_rbac(user_id, {"user:manage"}, ("admin",))
    await invalidate_user_rbac(user_id)
    assert await get_cached_rbac(user_id) is None


@pytest.mark.asyncio
async def test_invalidate_all_rbac(fake_redis):
    u1, u2 = uuid.uuid7(), uuid.uuid7()
    await set_cached_rbac(u1, {"a"}, ("r1",))
    await set_cached_rbac(u2, {"b"}, ("r2",))
    await invalidate_all_rbac()
    assert await get_cached_rbac(u1) is None
    assert await get_cached_rbac(u2) is None
