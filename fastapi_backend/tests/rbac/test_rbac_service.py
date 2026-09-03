import uuid

import pytest
from fastapi_users.password import PasswordHelper

from app.models import User
from app.rbac.service import assign_role, revoke_role


async def _create_user(db_session, email: str) -> User:
    user = User(
        id=uuid.uuid7(),
        email=email,
        hashed_password=PasswordHelper().hash("TestPassword123#"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_assign_role_returns_false_when_already_granted(db_session, fake_redis):
    """같은 역할을 두 번 부여하면 False 를 반환해야 한다 (N5)."""
    user = await _create_user(db_session, "assign-twice@example.com")

    first = await assign_role(db_session, user_id=user.id, role_code="operator")
    second = await assign_role(db_session, user_id=user.id, role_code="operator")

    assert first is True, "최초 부여는 True 여야 한다"
    assert second is False, "이미 보유한 역할은 False 여야 한다"


@pytest.mark.asyncio
async def test_revoke_role_returns_expected_flag(db_session, fake_redis):
    """보유한 역할은 True, 보유하지 않은 역할은 False 를 반환해야 한다 (N4·N5)."""
    user = await _create_user(db_session, "revoke-flag@example.com")
    await assign_role(db_session, user_id=user.id, role_code="operator")

    removed = await revoke_role(db_session, user_id=user.id, role_code="operator")
    again = await revoke_role(db_session, user_id=user.id, role_code="operator")

    assert removed is True, "보유한 역할 회수는 True 여야 한다"
    assert again is False, "보유하지 않은 역할 회수는 False 여야 한다"


@pytest.mark.asyncio
async def test_unknown_role_raises(db_session, fake_redis):
    """존재하지 않는 역할 코드는 ValueError 를 던져야 한다."""
    user = await _create_user(db_session, "unknown-role@example.com")

    with pytest.raises(ValueError):
        await assign_role(db_session, user_id=user.id, role_code="no_such_role")

    with pytest.raises(ValueError):
        await revoke_role(db_session, user_id=user.id, role_code="no_such_role")
