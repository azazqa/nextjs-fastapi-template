import asyncio

from sqlalchemy import select

from app.database import async_session_maker
from app.models import Role, User, UserRole
from app.rbac.permission_cache import invalidate_user_rbac
from app.rbac.seed import seed_rbac


async def grant_role(*, email: str, role_code: str) -> None:
    async with async_session_maker() as session:
        await seed_rbac(session)

        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            raise SystemExit(f"User not found: {email}")

        role = await session.scalar(select(Role).where(Role.code == role_code))
        if role is None:
            raise SystemExit(f"Role not found: {role_code}")

        existing = await session.scalar(
            select(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role_id == role.id,
            )
        )
        if existing is None:
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await session.commit()
            print(f"Granted role '{role_code}' to {email}")
        else:
            print(f"User {email} already has role '{role_code}'")

    await invalidate_user_rbac(user.id)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True)
    args = parser.parse_args()
    asyncio.run(grant_role(email=args.email, role_code=args.role))
