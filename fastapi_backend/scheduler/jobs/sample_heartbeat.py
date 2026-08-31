from __future__ import annotations

import logging

from sqlalchemy.engine import Engine

from scheduler.jobs._job_base import JobResult, run_job

logger = logging.getLogger(__name__)

JOB_KEY = "sample_heartbeat"
LOCK_KEY = "sample_heartbeat"


def _work_fn() -> dict:
    """Template sample job — logs a heartbeat placeholder."""
    logger.info("[SAMPLE_HEARTBEAT] placeholder run — no external side effects")
    return {"status": "placeholder", "heartbeat": True}


def run_sample_heartbeat(*, engine: Engine | None = None) -> JobResult | None:
    return run_job(
        job_key=JOB_KEY,
        lock_key=LOCK_KEY,
        work_fn=_work_fn,
        engine=engine,
    )


def _main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    run_sample_heartbeat()


if __name__ == "__main__":
    _main()
