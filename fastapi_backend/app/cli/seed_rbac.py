import asyncio

from app.database import async_session_maker
from app.rbac.seed import seed_rbac


async def seed_rbac_cmd() -> None:
    async with async_session_maker() as session:
        await seed_rbac(session)
    print("RBAC seed completed.")


if __name__ == "__main__":
    asyncio.run(seed_rbac_cmd())
