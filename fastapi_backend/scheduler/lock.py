from __future__ import annotations

import logging
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from scheduler.db import build_scheduler_engine, scheduler_session

logger = logging.getLogger(__name__)

LOCK_IDS: dict[str, int] = {
    "sample_heartbeat": 20260831,
}


@contextmanager
def advisory_lock(job_id: str, *, engine: Engine | None = None) -> Session | None:
    """
    PostgreSQL advisory lock을 획득한다.

    - 락 획득 실패(이미 다른 인스턴스 실행 중) 시: None을 yield하고 즉시 종료한다.
    - 획득 성공 시: 락을 보유한 세션(Session)을 yield한다.
    """
    if job_id not in LOCK_IDS:
        raise ValueError(f"Unknown job_id for lock: {job_id}")

    engine = engine or build_scheduler_engine()

    with scheduler_session(engine) as db:
        lock_id = LOCK_IDS[job_id]
        acquired = False
        try:
            acquired = bool(
                db.execute(
                    text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": lock_id}
                ).scalar()
            )
            if not acquired:
                logger.warning(
                    "[LOCK] %s lock not acquired; another instance running. skip.", job_id
                )
                yield None
                return

            logger.info("[LOCK] %s lock acquired", job_id)
            yield db
        finally:
            if acquired:
                try:
                    db.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})
                    db.commit()
                except Exception:
                    db.rollback()
                    logger.exception("[LOCK] %s unlock failed", job_id)
                else:
                    logger.info("[LOCK] %s lock released", job_id)
