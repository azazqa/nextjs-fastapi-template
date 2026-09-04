from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from scheduler.db import build_scheduler_engine, scheduler_session
from scheduler.lock import advisory_lock

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobResult:
    started_at: datetime
    finished_at: datetime
    status: str
    detail: dict[str, Any]
    error_message: str | None = None
    log_id: uuid.UUID | None = None

    @property
    def elapsed_sec(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()


def _insert_job_log(
    db,
    job_key: str,
    *,
    queue_id: uuid.UUID | None = None,
    schedule_id: uuid.UUID | None = None,
) -> uuid.UUID:
    log_id = uuid.uuid7()
    db.execute(
        text(
            """
            INSERT INTO scheduler_job_log(
                id, job_key, started_at, status, queue_id, schedule_id
            )
            VALUES (
                :id, :job_key, NOW(), 'RUNNING', :queue_id, :schedule_id
            )
            """
        ),
        {
            "id": log_id,
            "job_key": job_key,
            "queue_id": queue_id,
            "schedule_id": schedule_id,
        },
    )
    db.commit()
    return log_id


def _finalize_job_log(
    db,
    *,
    log_id: uuid.UUID,
    status: str,
    elapsed_sec: float,
    error_message: str | None,
    detail: dict[str, Any],
) -> None:
    db.execute(
        text(
            """
            UPDATE scheduler_job_log
               SET finished_at   = NOW(),
                   status        = :status,
                   elapsed_sec   = :elapsed_sec,
                   error_message = :error_message,
                   detail        = CAST(:detail AS jsonb)
             WHERE id = :log_id
            """
        ),
        {
            "log_id": log_id,
            "status": status,
            "elapsed_sec": elapsed_sec,
            "error_message": error_message,
            "detail": json.dumps(detail, ensure_ascii=False),
        },
    )
    db.commit()


def run_job(
    *,
    job_key: str,
    lock_key: str,
    work_fn: Callable[[], dict[str, Any]],
    engine: Engine | None = None,
    queue_id: uuid.UUID | None = None,
    schedule_id: uuid.UUID | None = None,
) -> JobResult | None:
    """
    Generic job runner with advisory lock and scheduler_job_log recording.

    Returns None when advisory lock could not be acquired.
    """
    engine = engine or build_scheduler_engine()

    with advisory_lock(lock_key, engine=engine) as lock_db:
        if lock_db is None:
            return None
        return _run_job(
            job_key=job_key,
            work_fn=work_fn,
            engine=engine,
            queue_id=queue_id,
            schedule_id=schedule_id,
        )


def _run_job(
    *,
    job_key: str,
    work_fn: Callable[[], dict[str, Any]],
    engine: Engine,
    queue_id: uuid.UUID | None = None,
    schedule_id: uuid.UUID | None = None,
) -> JobResult:
    started_at = datetime.now(tz=timezone.utc)
    detail: dict[str, Any] = {}
    error_message: str | None = None
    status = "SUCCESS"
    log_id: uuid.UUID | None = None

    with scheduler_session(engine) as db:
        log_id = _insert_job_log(
            db,
            job_key=job_key,
            queue_id=queue_id,
            schedule_id=schedule_id,
        )
        logger.info("[JOB] start job=%s (log_id=%s)", job_key, log_id)

        try:
            detail = work_fn()
        except Exception as e:
            status = "FAILED"
            error_message = str(e)
            detail = {"error": error_message}
            logger.exception("[JOB] failed job=%s", job_key)

        finished_at = datetime.now(tz=timezone.utc)
        elapsed = (finished_at - started_at).total_seconds()

        try:
            _finalize_job_log(
                db,
                log_id=log_id,
                status=status,
                elapsed_sec=elapsed,
                error_message=error_message,
                detail=detail,
            )
        except Exception:
            db.rollback()
            logger.exception(
                "[JOB] failed to finalize scheduler_job_log (log_id=%s)", log_id
            )

    result = JobResult(
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        detail=detail,
        error_message=error_message,
        log_id=log_id,
    )
    logger.info(
        "[JOB] finished job=%s status=%s elapsed=%.1fs",
        job_key,
        result.status,
        result.elapsed_sec,
    )
    return result
