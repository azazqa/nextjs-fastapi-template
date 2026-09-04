from __future__ import annotations

import logging

from sqlalchemy.engine import Engine

from scheduler.jobs._job_base import JobResult, run_job
from scheduler.jobs._registry import job

logger = logging.getLogger(__name__)

JOB_KEY = "sample_heartbeat"


@job(
    JOB_KEY,
    title="Sample Heartbeat",
    description="Template sample job — logs a heartbeat placeholder.",
)
def sample_heartbeat(*, engine=None, payload=None, ctx=None) -> dict:
    """Template sample job — logs a heartbeat placeholder."""
    _ = (engine, payload, ctx)
    logger.info("[SAMPLE_HEARTBEAT] placeholder run — no external side effects")
    return {"status": "placeholder", "heartbeat": True}


def run_sample_heartbeat(*, engine: Engine | None = None) -> JobResult | None:
    """Convenience wrapper used by unit tests and manual CLI runs."""
    return run_job(
        job_key=JOB_KEY,
        lock_key=JOB_KEY,
        work_fn=lambda: sample_heartbeat(engine=engine),
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
