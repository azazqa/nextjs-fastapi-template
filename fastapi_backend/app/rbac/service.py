"""역할 부여·회수 — DB 변경과 캐시 무효화를 함께 수행한다.

역할을 변경하는 코드는 반드시 이 모듈을 거쳐야 한다.
UserRole 을 직접 조작하면 캐시가 어긋난다.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role, UserRole
from app.rbac.permission_cache import invalidate_user_rbac


async def assign_role(
    session: AsyncSession, *, user_id: uuid.UUID, role_code: str
) -> bool:
    """역할을 부여한다. 이미 보유 중이면 False 를 반환한다."""
    role = await session.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        raise ValueError(f"Unknown role: {role_code}")

    exists = await session.scalar(
        select(UserRole).where(
            UserRole.user_id == user_id, UserRole.role_id == role.id
        )
    )
    if exists is not None:
        return False

    session.add(UserRole(user_id=user_id, role_id=role.id))
    await session.commit()
    await invalidate_user_rbac(user_id)
    return True


async def revoke_role(
    session: AsyncSession, *, user_id: uuid.UUID, role_code: str
) -> bool:
    """역할을 회수한다. 보유하지 않았다면 False 를 반환한다."""
    role = await session.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        raise ValueError(f"Unknown role: {role_code}")

    result = await session.execute(
        delete(UserRole).where(
            UserRole.user_id == user_id, UserRole.role_id == role.id
        )
    )
    removed = result.rowcount > 0
    await session.commit()
    await invalidate_user_rbac(user_id)
    return removed
