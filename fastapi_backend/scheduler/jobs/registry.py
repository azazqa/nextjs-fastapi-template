from __future__ import annotations

from collections.abc import Callable
from typing import Any

from scheduler.jobs import sample_heartbeat
from scheduler.jobs._job_base import JobResult

JobRunner = Callable[..., JobResult | None]

_JOB_RUNNERS: dict[str, JobRunner] = {
    sample_heartbeat.JOB_KEY: sample_heartbeat.run_sample_heartbeat,
}

REGISTERED_JOB_KEYS: frozenset[str] = frozenset(_JOB_RUNNERS)


def run_registered_job(
    job_key: str,
    *,
    engine: Any,
    payload: dict | None = None,
) -> tuple[str, str | None]:
    """
    Run a registered job by key.

    Returns (outcome, error_message) where outcome is
    succeeded | failed | lock_skipped.
    """
    _ = payload
    runner = _JOB_RUNNERS.get(job_key)
    if runner is None:
        return "failed", f"unknown job_key: {job_key}"

    result = runner(engine=engine)
    if result is None:
        return "lock_skipped", None
    if result.status == "SUCCESS":
        return "succeeded", None
    return "failed", result.error_message or "job failed"
