import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role, RolePermission, UserRole


async def fetch_user_permissions(
    session: AsyncSession, user_id: uuid.UUID
) -> list[str]:
    stmt = (
        select(RolePermission.permission_code)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id)
        .distinct()
    )
    return list((await session.execute(stmt)).scalars().all())


async def fetch_user_roles(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    stmt = (
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
        .order_by(Role.code.asc())
    )
    return list((await session.execute(stmt)).scalars().all())
