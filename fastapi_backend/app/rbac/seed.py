from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Permission, Role, RolePermission
from app.rbac.constants import ADMIN_PERMISSIONS, ROLE_PERMISSIONS


async def seed_rbac(session: AsyncSession) -> None:
    """Idempotently seed admin permissions and system roles."""
    for code, name, category, domain in ADMIN_PERMISSIONS:
        existing = await session.get(Permission, code)
        if existing is None:
            session.add(
                Permission(
                    code=code,
                    name=name,
                    category=category,
                    domain=domain,
                )
            )

    await session.flush()

    for role_code, perm_codes in ROLE_PERMISSIONS.items():
        role = await session.scalar(select(Role).where(Role.code == role_code))
        if role is None:
            role = Role(
                code=role_code,
                name="Administrator" if role_code == "admin" else "Operator",
                description=f"System role: {role_code}",
                is_system=True,
            )
            session.add(role)
            await session.flush()

        existing_perms = {
            row
            for row in (
                await session.execute(
                    select(RolePermission.permission_code).where(
                        RolePermission.role_id == role.id
                    )
                )
            ).scalars()
        }
        for perm_code in perm_codes:
            if perm_code not in existing_perms:
                session.add(
                    RolePermission(role_id=role.id, permission_code=perm_code)
                )

    await session.commit()
