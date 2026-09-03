import os

# Tests use in-memory login rate limit (no Redis required).
os.environ["REDIS_URL"] = ""

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.password import PasswordHelper
import uuid

import app.redis as redis_module
from app.config import settings
from app.models import Role, User, UserRole, Base

from sqlalchemy import select

from app.database import get_user_db, get_async_session
from app.main import app
from app.rbac.seed import seed_rbac
from app.users import get_jwt_strategy


@pytest_asyncio.fixture
async def fake_redis(monkeypatch):
    """In-memory Redis for auth cache / denylist unit tests."""
    client = FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_module, "_redis", client)
    monkeypatch.setattr(settings, "REDIS_URL", "redis://fake/0")
    yield client
    await client.aclose()
    redis_module._redis = None


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def engine():
    """Create a fresh test database engine for each test function."""
    engine = create_async_engine(settings.TEST_DATABASE_URL, echo=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def db_session(engine):
    """Create a fresh database session for each test."""
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        await seed_rbac(session)
        yield session
        await session.rollback()
        await session.close()


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def test_client(db_session):
    """Fixture to create a test client that uses the test database session."""

    # FastAPI-Users database override (wraps session with user operation helpers)
    async def override_get_user_db():
        session = SQLAlchemyUserDatabase(db_session, User)
        try:
            yield session
        finally:
            await db_session.close()

    # General database override (raw session access)
    async def override_get_async_session():
        try:
            yield db_session
        finally:
            await db_session.close()

    # Set up test database overrides
    app.dependency_overrides[get_user_db] = override_get_user_db
    app.dependency_overrides[get_async_session] = override_get_async_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def authenticated_user(test_client, db_session):
    """Fixture to create and authenticate a test user directly in the database."""

    # Create user data
    user_data = {
        "id": uuid.uuid7(),
        "email": "test@example.com",
        "hashed_password": PasswordHelper().hash("TestPassword123#"),
        "is_active": True,
        "is_superuser": False,
        "is_verified": True,
    }

    # Create user directly in database
    user = User(**user_data)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Generate token using the strategy directly
    strategy = get_jwt_strategy()
    access_token = await strategy.write_token(user)

    # Return both the headers and the user data
    return {
        "headers": {"Authorization": f"Bearer {access_token}"},
        "user": user,
        "user_data": {"email": user_data["email"], "password": "TestPassword123#"},
    }


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def operator_user(test_client, db_session):
    """Authenticated user with operator role (scheduler permissions)."""
    user = User(
        id=uuid.uuid7(),
        email="operator@example.com",
        hashed_password=PasswordHelper().hash("OperatorPassword123#"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    role = await db_session.scalar(select(Role).where(Role.code == "operator"))
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    await db_session.commit()

    strategy = get_jwt_strategy()
    access_token = await strategy.write_token(user)
    return {
        "headers": {"Authorization": f"Bearer {access_token}"},
        "user": user,
    }
