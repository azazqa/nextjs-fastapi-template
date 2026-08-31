from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import SchedulerJobQueue
from scheduler.db import build_scheduler_engine
from scheduler.jobs.sample_heartbeat import run_sample_heartbeat

logger = logging.getLogger(__name__)

KNOWN_JOB_KEYS = frozenset({"sample_heartbeat"})

_PROCESSING_JOB_KEYS = (
    select(SchedulerJobQueue.job_key)
    .where(
        SchedulerJobQueue.status == "PROCESSING",
        SchedulerJobQueue.is_delete == False,  # noqa: E712
    )
    .distinct()
    .scalar_subquery()
)


def _run_job(job_key: str, *, engine, payload: dict | None = None) -> tuple[str, str | None]:
    """
    Returns (outcome, error_message).

    outcome: succeeded | failed | lock_skipped
    """
    _ = payload
    if job_key == "sample_heartbeat":
        result = run_sample_heartbeat(engine=engine)
        if result is None:
            return "lock_skipped", None
        if result.status == "SUCCESS":
            return "succeeded", None
        return "failed", result.error_message or "job failed"
    return "failed", f"unknown job_key: {job_key}"


def process_pending_queue(*, engine=None) -> None:
    """
    Pick one PENDING queue row, run the job, then mark SUCCEEDED / FAILED,
    or reset to PENDING when advisory lock was not acquired.
    """
    engine = engine or build_scheduler_engine()

    with Session(engine) as session:
        qid = session.scalar(
            select(SchedulerJobQueue.id)
            .where(
                SchedulerJobQueue.status == "PENDING",
                SchedulerJobQueue.is_delete == False,  # noqa: E712
                SchedulerJobQueue.job_key.not_in(_PROCESSING_JOB_KEYS),
            )
            .order_by(SchedulerJobQueue.id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if qid is None:
            return

        row = session.get(SchedulerJobQueue, qid)
        if row is None:
            return

        job_key = row.job_key
        if job_key not in KNOWN_JOB_KEYS:
            session.execute(
                update(SchedulerJobQueue)
                .where(SchedulerJobQueue.id == qid)
                .values(
                    status="FAILED",
                    finished_at=datetime.now(tz=timezone.utc),
                    error_message=f"unknown job_key: {job_key}",
                    updated_at=func.now(),
                )
            )
            session.commit()
            return

        session.execute(
            update(SchedulerJobQueue)
            .where(SchedulerJobQueue.id == qid)
            .values(
                status="PROCESSING",
                started_at=datetime.now(tz=timezone.utc),
                updated_at=func.now(),
            )
        )
        session.commit()

    with Session(engine) as session:
        if (
            session.scalar(select(SchedulerJobQueue.status).where(SchedulerJobQueue.id == qid))
            == "CANCELLED"
        ):
            logger.info("[QUEUE] skip cancelled before run id=%s", qid)
            return

        row = session.get(SchedulerJobQueue, qid)
        payload = row.payload if row else None

    outcome, err = _run_job(job_key, engine=engine, payload=payload)

    with Session(engine) as session:
        if (
            session.scalar(select(SchedulerJobQueue.status).where(SchedulerJobQueue.id == qid))
            == "CANCELLED"
        ):
            logger.info("[QUEUE] skip finalize cancelled id=%s", qid)
            return
        if outcome == "lock_skipped":
            session.execute(
                update(SchedulerJobQueue)
                .where(SchedulerJobQueue.id == qid)
                .values(
                    status="PENDING",
                    started_at=None,
                    error_message="Lock not acquired; retry later",
                    updated_at=func.now(),
                )
            )
        elif outcome == "succeeded":
            session.execute(
                update(SchedulerJobQueue)
                .where(SchedulerJobQueue.id == qid)
                .values(
                    status="SUCCEEDED",
                    finished_at=datetime.now(tz=timezone.utc),
                    error_message=None,
                    updated_at=func.now(),
                )
            )
        else:
            session.execute(
                update(SchedulerJobQueue)
                .where(SchedulerJobQueue.id == qid)
                .values(
                    status="FAILED",
                    finished_at=datetime.now(tz=timezone.utc),
                    error_message=(err or "failed")[:10000],
                    updated_at=func.now(),
                )
            )
        session.commit()

    logger.info("[QUEUE] processed queue id=%s job_key=%s outcome=%s", qid, job_key, outcome)
