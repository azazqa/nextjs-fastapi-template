from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import SchedulerJobQueue, SchedulerSchedule
from scheduler.db import build_scheduler_engine
from scheduler.jobs._registry import get_registry
from scheduler.jobs.registry import get_registered_job_keys, run_registered_job

logger = logging.getLogger(__name__)

_PROCESSING_JOB_KEYS = (
    select(SchedulerJobQueue.job_key)
    .where(
        SchedulerJobQueue.status == "PROCESSING",
        SchedulerJobQueue.is_delete == False,  # noqa: E712
    )
    .distinct()
    .scalar_subquery()
)


def _resolve_lock_key(
    *,
    job_key: str,
    schedule: SchedulerSchedule | None,
) -> str:
    registry = get_registry()
    spec = registry.get(job_key)
    if schedule is not None and schedule.concurrency_key:
        return schedule.concurrency_key
    if spec is not None and spec.concurrency_key:
        return spec.concurrency_key
    return job_key


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
        schedule_id: UUID | None = row.schedule_id
        payload = row.payload

        if schedule_id is not None:
            schedule = session.get(SchedulerSchedule, schedule_id)
            if (
                schedule is None
                or schedule.is_delete
                or not schedule.enabled
            ):
                session.execute(
                    update(SchedulerJobQueue)
                    .where(SchedulerJobQueue.id == qid)
                    .values(
                        status="CANCELLED",
                        finished_at=datetime.now(tz=timezone.utc),
                        error_message="Schedule deleted or disabled",
                        updated_at=func.now(),
                    )
                )
                session.commit()
                return
            if payload is None:
                payload = schedule.payload
            lock_key = _resolve_lock_key(job_key=job_key, schedule=schedule)
        else:
            lock_key = _resolve_lock_key(job_key=job_key, schedule=None)

        if job_key not in get_registered_job_keys():
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

    outcome = run_registered_job(
        job_key,
        engine=engine,
        lock_key=lock_key,
        payload=payload,
        queue_id=qid,
        schedule_id=schedule_id,
    )

    with Session(engine) as session:
        if (
            session.scalar(select(SchedulerJobQueue.status).where(SchedulerJobQueue.id == qid))
            == "CANCELLED"
        ):
            logger.info("[QUEUE] skip finalize cancelled id=%s", qid)
            return
        if outcome.outcome == "lock_skipped":
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
        elif outcome.outcome == "succeeded":
            session.execute(
                update(SchedulerJobQueue)
                .where(SchedulerJobQueue.id == qid)
                .values(
                    status="SUCCEEDED",
                    finished_at=datetime.now(tz=timezone.utc),
                    error_message=None,
                    related_log_id=outcome.log_id,
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
                    error_message=(outcome.error_message or "failed")[:10000],
                    related_log_id=outcome.log_id,
                    updated_at=func.now(),
                )
            )
        session.commit()

    logger.info(
        "[QUEUE] processed queue id=%s job_key=%s outcome=%s",
        qid,
        job_key,
        outcome.outcome,
    )
