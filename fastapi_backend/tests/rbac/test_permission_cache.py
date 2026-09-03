import uuid

import pytest
from sqlalchemy import select

from app.models import Role, User, UserRole
from app.rbac.permission_cache import (
    get_cached_rbac,
    invalidate_all_rbac,
    invalidate_user_rbac,
    set_cached_rbac,
)
from app.rbac.service import assign_role, revoke_role
from fastapi_users.password import PasswordHelper


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
async def test_empty_rbac_is_cached(fake_redis):
    """역할이 없는 사용자도 캐시되어야 한다 (N2 회귀 방지)."""
    user_id = uuid.uuid7()

    await set_cached_rbac(user_id, frozenset(), ())

    cached = await get_cached_rbac(user_id)
    assert cached is not None, "빈 권한이 캐시 미스로 처리되면 안 된다"

    permissions, roles = cached
    assert permissions == frozenset()
    assert roles == ()


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


@pytest.mark.asyncio
async def test_assign_role_invalidates_cache(db_session, fake_redis):
    """역할 부여 시 캐시가 무효화되어야 한다 (N3 회귀 방지)."""
    user = User(
        id=uuid.uuid7(),
        email="cache-assign@example.com",
        hashed_password=PasswordHelper().hash("TestPassword123#"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    await set_cached_rbac(user.id, frozenset({"stale:permission"}), ("stale",))
    assert await get_cached_rbac(user.id) is not None

    await assign_role(db_session, user_id=user.id, role_code="operator")

    assert await get_cached_rbac(user.id) is None


@pytest.mark.asyncio
async def test_revoke_role_invalidates_cache(db_session, fake_redis):
    """역할 회수 시 캐시가 무효화되어야 한다 (N3 회귀 방지)."""
    user = User(
        id=uuid.uuid7(),
        email="cache-revoke@example.com",
        hashed_password=PasswordHelper().hash("TestPassword123#"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    role = await db_session.scalar(select(Role).where(Role.code == "operator"))
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    await db_session.commit()

    await set_cached_rbac(
        user.id, frozenset({"scheduler:read"}), ("operator",)
    )
    assert await get_cached_rbac(user.id) is not None

    await revoke_role(db_session, user_id=user.id, role_code="operator")

    assert await get_cached_rbac(user.id) is None
