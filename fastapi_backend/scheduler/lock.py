from __future__ import annotations

import logging
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from scheduler.db import build_scheduler_engine, scheduler_session

logger = logging.getLogger(__name__)

# Application-wide advisory-lock namespace (int4). Do not change after deploy.
APP_LOCK_NAMESPACE = 4207


@contextmanager
def advisory_lock(lock_key: str, *, engine: Engine | None = None) -> Session | None:
    """
    PostgreSQL advisory lock을 획득한다.

    - 락 획득 실패(이미 다른 인스턴스 실행 중) 시: None을 yield하고 즉시 종료한다.
    - 획득 성공 시: 락을 보유한 세션(Session)을 yield한다.

    Uses ``pg_try_advisory_lock(namespace, hashtext(key))`` so lock IDs are
    derived from keys instead of a manual integer map.
    """
    engine = engine or build_scheduler_engine()

    with scheduler_session(engine) as db:
        acquired = False
        try:
            acquired = bool(
                db.execute(
                    text(
                        "SELECT pg_try_advisory_lock(:ns, hashtext(:key))"
                    ),
                    {"ns": APP_LOCK_NAMESPACE, "key": lock_key},
                ).scalar()
            )
            if not acquired:
                logger.warning(
                    "[LOCK] %s lock not acquired; another instance running. skip.",
                    lock_key,
                )
                yield None
                return

            logger.info("[LOCK] %s lock acquired", lock_key)
            yield db
        finally:
            if acquired:
                try:
                    db.execute(
                        text(
                            "SELECT pg_advisory_unlock(:ns, hashtext(:key))"
                        ),
                        {"ns": APP_LOCK_NAMESPACE, "key": lock_key},
                    )
                    db.commit()
                except Exception:
                    db.rollback()
                    logger.exception("[LOCK] %s unlock failed", lock_key)
                else:
                    logger.info("[LOCK] %s lock released", lock_key)
