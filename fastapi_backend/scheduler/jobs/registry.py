from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from scheduler.jobs._job_base import JobResult, run_job
from scheduler.jobs._registry import JobSpec, discover, get_registry


@dataclass(frozen=True)
class JobOutcome:
    outcome: str  # succeeded | failed | lock_skipped
    log_id: uuid.UUID | None
    error_message: str | None


def _ensure_discovered() -> dict[str, JobSpec]:
    return discover()


def get_registered_job_keys() -> frozenset[str]:
    return frozenset(_ensure_discovered())


# Eager discover so REGISTERED_JOB_KEYS is available at import (API / runner).
REGISTERED_JOB_KEYS: frozenset[str] = get_registered_job_keys()


def refresh_registered_job_keys() -> frozenset[str]:
    """Recompute the frozenset after test rediscovery."""
    global REGISTERED_JOB_KEYS
    REGISTERED_JOB_KEYS = get_registered_job_keys()
    return REGISTERED_JOB_KEYS


def run_registered_job(
    job_key: str,
    *,
    engine: Any,
    lock_key: str | None = None,
    payload: dict | None = None,
    queue_id: uuid.UUID | None = None,
    schedule_id: uuid.UUID | None = None,
) -> JobOutcome:
    """
    Run a registered job by key.

    Returns JobOutcome where outcome is succeeded | failed | lock_skipped.
    """
    registry = get_registry()
    spec = registry.get(job_key)
    if spec is None:
        return JobOutcome("failed", None, f"unknown job_key: {job_key}")

    effective_lock = lock_key or spec.concurrency_key or spec.key

    def work_fn() -> dict[str, Any]:
        return spec.runner(engine=engine, payload=payload, ctx=None)

    result = run_job(
        job_key=job_key,
        lock_key=effective_lock,
        work_fn=work_fn,
        engine=engine,
        queue_id=queue_id,
        schedule_id=schedule_id,
    )
    if result is None:
        return JobOutcome("lock_skipped", None, None)
    if result.status == "SUCCESS":
        return JobOutcome("succeeded", result.log_id, None)
    return JobOutcome(
        "failed",
        result.log_id,
        result.error_message or "job failed",
    )
