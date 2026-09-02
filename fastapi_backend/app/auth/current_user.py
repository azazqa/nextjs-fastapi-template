import uuid
from dataclasses import dataclass, field

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import log_superuser_bypass
from app.database import get_async_session
from app.models import User
from app.rbac.queries import fetch_user_permissions, fetch_user_roles
from app.users import current_active_user


@dataclass
class CurrentUser:
    id: uuid.UUID
    email: str
    is_active: bool
    is_superuser: bool
    is_verified: bool
    permissions: frozenset[str] = field(default_factory=frozenset)
    roles: tuple[str, ...] = ()

    def has(self, *codes: str) -> bool:
        if set(codes).issubset(self.permissions):
            return True
        if self.is_superuser:
            log_superuser_bypass(self.id, codes)
            return True
        return False


async def get_current_user(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> CurrentUser:
    permissions = await fetch_user_permissions(session, user.id)
    roles = await fetch_user_roles(session, user.id)
    return CurrentUser(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        is_verified=user.is_verified,
        permissions=frozenset(permissions),
        roles=tuple(roles),
    )


def require(*codes: str):
    async def dependency(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if not user.has(*codes):
            raise HTTPException(
                status_code=403,
                detail=f"권한이 없습니다: {', '.join(sorted(codes))}",
            )
        return user

    return dependency
