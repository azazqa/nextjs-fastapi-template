import asyncio

from sqlalchemy import select

from app.database import async_session_maker
from app.models import User
from app.rbac.seed import seed_rbac
from app.rbac.service import assign_role


async def grant_role(*, email: str, role_code: str) -> None:
    async with async_session_maker() as session:
        await seed_rbac(session)

        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            raise SystemExit(f"User not found: {email}")

        try:
            granted = await assign_role(
                session, user_id=user.id, role_code=role_code
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

        if granted:
            print(f"Granted role '{role_code}' to {email}")
        else:
            print(f"User {email} already has role '{role_code}'")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True)
    args = parser.parse_args()
    asyncio.run(grant_role(email=args.email, role_code=args.role))
