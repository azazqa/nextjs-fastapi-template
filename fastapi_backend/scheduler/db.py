from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool


@dataclass(frozen=True)
class SchedulerDbSettings:
    database_url: str


def _get_env_database_url() -> str:
    v = os.getenv("DATABASE_URL")
    if not v:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return v


def to_sync_database_url(async_database_url: str) -> str:
    """Convert an asyncpg SQLAlchemy URL to psycopg2 for sync SQLAlchemy usage."""
    parsed = urlparse(async_database_url)
    scheme = parsed.scheme

    if scheme in ("postgres", "postgresql"):
        return async_database_url
    if scheme in ("postgres+asyncpg", "postgresql+asyncpg"):
        return async_database_url.replace("+asyncpg", "+psycopg2", 1)
    if scheme.endswith("+asyncpg"):
        return async_database_url.replace("+asyncpg", "+psycopg2", 1)
    return async_database_url


def build_scheduler_engine(settings: SchedulerDbSettings | None = None) -> Engine:
    settings = settings or SchedulerDbSettings(database_url=_get_env_database_url())
    sync_url = to_sync_database_url(settings.database_url)
    return create_engine(sync_url, poolclass=NullPool, future=True)


_SessionMaker = sessionmaker(class_=Session, autocommit=False, autoflush=False, expire_on_commit=False)


@contextmanager
def scheduler_session(engine: Engine | None = None) -> Session:
    engine = engine or build_scheduler_engine()
    maker = _SessionMaker
    maker.configure(bind=engine)
    db = maker()
    try:
        yield db
    finally:
        db.close()
