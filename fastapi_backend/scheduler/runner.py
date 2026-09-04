from __future__ import annotations

import hashlib
import logging
import signal
import sys
from typing import Any
from uuid import UUID

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import SchedulerJobQueue
from scheduler.db import build_scheduler_engine
from scheduler.jobs.registry import get_registered_job_keys
from scheduler.queue_processor import process_pending_queue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler.runner")

scheduler = BlockingScheduler(timezone=settings.TZ)
_current_fingerprint: str | None = None
_engine = None


def _on_job_executed(event) -> None:
    logger.info("[RUNNER] job executed: %s", getattr(event, "job_id", "-"))


def _on_job_error(event) -> None:
    logger.error(
        "[RUNNER] job error: %s - %s",
        getattr(event, "job_id", "-"),
        getattr(event, "exception", None),
    )


def _shutdown(signum, frame) -> None:
    _ = (signum, frame)
    logger.info("[RUNNER] shutdown signal received; stopping scheduler...")
    scheduler.shutdown(wait=False)
    sys.exit(0)


def _load_enabled_schedules(engine) -> list[dict[str, Any]]:
    """
    scheduler_schedules에 등록·활성화된 행만 cron 대상으로 반환한다.
    """
    try:
        with engine.connect() as c:
            rows = (
                c.execute(
                    text(
                        """
                    SELECT id, job_key, name, cron_expression, timezone, enabled, payload
                      FROM scheduler_schedules
                     WHERE is_delete = false AND enabled = true
                     ORDER BY name, id
                    """
                    )
                )
                .mappings()
                .all()
            )
    except Exception:
        logger.warning(
            "[RUNNER] could not read scheduler_schedules; no cron jobs scheduled",
            exc_info=True,
        )
        return []

    schedules: list[dict[str, Any]] = []
    for row in rows:
        job_key = str(row["job_key"])
        if job_key not in get_registered_job_keys():
            logger.warning(
                "[RUNNER] unknown job_key in scheduler_schedules: %s; skipping cron",
                job_key,
            )
            continue
        schedules.append(dict(row))
    return schedules


def _fingerprint(rows: list[dict[str, Any]]) -> str:
    payload = [
        (
            str(r["id"]),
            r["job_key"],
            r["cron_expression"],
            r.get("timezone") or settings.TZ,
            bool(r.get("enabled", True)),
        )
        for r in rows
    ]
    return hashlib.sha256(repr(sorted(payload)).encode()).hexdigest()


def _enqueue_scheduled_job(
    *,
    schedule_id: UUID,
    job_key: str,
    engine,
    payload: dict | None = None,
) -> None:
    with Session(engine) as session:
        row = SchedulerJobQueue(
            job_key=job_key,
            schedule_id=schedule_id,
            action="SCHEDULED",
            status="PENDING",
            payload=payload,
            requested_by_user_id=None,
            error_message=None,
            started_at=None,
            finished_at=None,
        )
        session.add(row)
        session.flush()
        queue_id = row.id
        session.commit()
    logger.info(
        "[RUNNER] scheduled enqueue: schedule_id=%s job_key=%s queue_id=%s",
        schedule_id,
        job_key,
        queue_id,
    )


def _reload_schedules(engine=None) -> None:
    global _current_fingerprint
    engine = engine or _engine
    if engine is None:
        return

    rows = _load_enabled_schedules(engine)
    fp = _fingerprint(rows)
    if fp == _current_fingerprint:
        return

    known = {f"sched:{r['id']}" for r in rows}
    for j in scheduler.get_jobs():
        jid = str(j.id)
        if jid.startswith("sched:") and jid not in known:
            scheduler.remove_job(jid)

    for r in rows:
        tz = r.get("timezone") or settings.TZ
        try:
            trigger = CronTrigger.from_crontab(r["cron_expression"], timezone=tz)
        except ValueError:
            logger.warning(
                "[RUNNER] invalid cron_expression for schedule %s: %r; skipping",
                r["id"],
                r["cron_expression"],
                exc_info=True,
            )
            continue
        scheduler.add_job(
            _enqueue_scheduled_job,
            trigger,
            kwargs={
                "schedule_id": r["id"],
                "job_key": r["job_key"],
                "engine": engine,
                "payload": r.get("payload"),
            },
            id=f"sched:{r['id']}",
            name=f"{r['name']} ({r['job_key']})",
            max_instances=1,
            misfire_grace_time=600,
            replace_existing=True,
        )
    _current_fingerprint = fp
    logger.info("[RUNNER] schedules reloaded: %d active", len(rows))


def _tick_queue() -> None:
    try:
        process_pending_queue()
    except Exception:
        logger.exception("[RUNNER] job queue poll failed")


def _tick_reload() -> None:
    try:
        _reload_schedules()
    except Exception:
        logger.exception("[RUNNER] schedule reload failed")


def main() -> None:
    global _engine
    scheduler.add_listener(_on_job_executed, EVENT_JOB_EXECUTED)
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

    _engine = build_scheduler_engine()
    _reload_schedules(_engine)

    scheduler.add_job(
        _tick_queue,
        IntervalTrigger(seconds=15),
        id="scheduler_job_queue_poll",
        name="DB job queue poll",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        _tick_reload,
        IntervalTrigger(seconds=60),
        id="scheduler_schedules_reload",
        name="DB schedules hot reload",
        max_instances=1,
        replace_existing=True,
    )

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("[RUNNER] scheduler started (cron + queue poll + schedule reload)")
    scheduler.start()


if __name__ == "__main__":
    main()
