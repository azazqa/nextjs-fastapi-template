from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models import SchedulerJob, SchedulerJobLog, SchedulerJobQueue, User
from app.pagination import MAX_PAGE_SIZE, Page, Params
from app.users import current_superuser

router = APIRouter()

QUEUE_ACTION_RUN_NOW = "RUN_NOW"
QUEUE_ACTION_RESTART = "RESTART"
QUEUE_ACTION_SCHEDULED = "SCHEDULED"
QUEUE_STATUS_PENDING = "PENDING"
QUEUE_STATUS_PROCESSING = "PROCESSING"
QUEUE_STATUS_CANCELLED = "CANCELLED"

REGISTERED_JOB_KEYS = frozenset({"sample_heartbeat"})


class SchedulerJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_key: str
    title: str
    enabled: bool
    cron_hour: int
    cron_minute: int
    timezone: str
    description: str | None


class SchedulerJobCreate(BaseModel):
    job_key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    title: str = Field(min_length=1, max_length=255)
    enabled: bool = True
    cron_hour: int = Field(default=3, ge=0, le=23)
    cron_minute: int = Field(default=0, ge=0, le=59)
    timezone: str = Field(default="Asia/Seoul", max_length=64)
    description: str | None = None


class SchedulerJobUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    enabled: bool | None = None
    cron_hour: int | None = Field(default=None, ge=0, le=23)
    cron_minute: int | None = Field(default=None, ge=0, le=59)
    timezone: str | None = Field(default=None, max_length=64)
    description: str | None = None


class SchedulerJobQueueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_key: str
    action: str
    status: str
    payload: dict | list | None = None
    requested_by_user_id: UUID | None
    related_log_id: int | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class SchedulerJobLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    elapsed_sec: float | None
    error_message: str | None
    detail: dict | list | None


def _transform_logs(rows: list[SchedulerJobLog]) -> list[SchedulerJobLogRead]:
    out: list[SchedulerJobLogRead] = []
    for r in rows:
        out.append(
            SchedulerJobLogRead(
                id=r.id,
                job_id=r.job_id,
                started_at=r.started_at,
                finished_at=r.finished_at,
                status=r.status,
                elapsed_sec=float(r.elapsed_sec) if r.elapsed_sec is not None else None,
                error_message=r.error_message,
                detail=r.detail,
            )
        )
    return out


@router.get("/jobs", response_model=list[SchedulerJobRead])
async def list_scheduler_jobs(
    q: str | None = Query(default=None, description="job_key 또는 title 검색"),
    session: AsyncSession = Depends(get_async_session),
    _: User = Depends(current_superuser),
):
    stmt = select(SchedulerJob).where(SchedulerJob.is_delete == False)  # noqa: E712
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            SchedulerJob.job_key.ilike(term) | SchedulerJob.title.ilike(term)
        )
    stmt = stmt.order_by(SchedulerJob.job_key.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("/jobs", response_model=SchedulerJobRead, status_code=201)
async def create_scheduler_job(
    body: SchedulerJobCreate,
    session: AsyncSession = Depends(get_async_session),
    _: User = Depends(current_superuser),
):
    if body.job_key not in REGISTERED_JOB_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"job_key must be one of: {', '.join(sorted(REGISTERED_JOB_KEYS))}",
        )
    existing = await session.get(SchedulerJob, body.job_key)
    if existing is not None:
        if existing.is_delete:
            for k, v in body.model_dump().items():
                setattr(existing, k, v)
            existing.is_delete = False
            await session.commit()
            await session.refresh(existing)
            return existing
        raise HTTPException(status_code=409, detail="Job already exists")

    row = SchedulerJob(**body.model_dump())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@router.delete("/jobs/{job_key}", status_code=204)
async def delete_scheduler_job(
    job_key: str,
    session: AsyncSession = Depends(get_async_session),
    _: User = Depends(current_superuser),
):
    row = await session.get(SchedulerJob, job_key)
    if row is None or row.is_delete:
        raise HTTPException(status_code=404, detail="Job not found")
    row.is_delete = True
    await session.commit()


@router.patch("/jobs/{job_key}", response_model=SchedulerJobRead)
async def update_scheduler_job(
    job_key: str,
    body: SchedulerJobUpdate,
    session: AsyncSession = Depends(get_async_session),
    _: User = Depends(current_superuser),
):
    row = await session.get(SchedulerJob, job_key)
    if row is None or row.is_delete:
        raise HTTPException(status_code=404, detail="Job not found")

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    for k, v in data.items():
        setattr(row, k, v)
    await session.commit()
    await session.refresh(row)
    return row


@router.post("/jobs/{job_key}/enqueue-run", response_model=SchedulerJobQueueRead)
async def enqueue_run_now(
    job_key: str,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_superuser),
):
    job = await session.get(SchedulerJob, job_key)
    if job is None or job.is_delete:
        raise HTTPException(status_code=404, detail="Job definition not found")

    q = SchedulerJobQueue(
        job_key=job_key,
        action=QUEUE_ACTION_RUN_NOW,
        status=QUEUE_STATUS_PENDING,
        requested_by_user_id=user.id,
    )
    session.add(q)
    await session.commit()
    await session.refresh(q)
    return q


@router.get("/queue", response_model=Page[SchedulerJobQueueRead])
async def list_job_queue(
    page: int = 1,
    size: int = 20,
    status: str | None = Query(default=None),
    job_key: str | None = Query(default=None),
    q: str | None = Query(default=None, description="job_key 검색"),
    session: AsyncSession = Depends(get_async_session),
    _: User = Depends(current_superuser),
):
    if size < 1:
        raise HTTPException(status_code=400, detail="size must be >= 1")
    if size > MAX_PAGE_SIZE:
        raise HTTPException(status_code=400, detail=f"size must be <= {MAX_PAGE_SIZE}")
    params = Params(page=page, size=size)
    stmt = select(SchedulerJobQueue).where(SchedulerJobQueue.is_delete == False)  # noqa: E712
    if status:
        stmt = stmt.where(SchedulerJobQueue.status == status.strip().upper())
    if job_key:
        stmt = stmt.where(SchedulerJobQueue.job_key == job_key.strip())
    if q and q.strip():
        stmt = stmt.where(SchedulerJobQueue.job_key.ilike(f"%{q.strip()}%"))
    stmt = stmt.order_by(SchedulerJobQueue.id.desc())
    return await apaginate(session, stmt, params)


@router.post("/queue/{queue_id}/cancel", response_model=SchedulerJobQueueRead)
async def cancel_queue_item(
    queue_id: int,
    session: AsyncSession = Depends(get_async_session),
    _: User = Depends(current_superuser),
):
    row = await session.get(SchedulerJobQueue, queue_id)
    if row is None or row.is_delete:
        raise HTTPException(status_code=404, detail="Queue item not found")
    if row.status not in (QUEUE_STATUS_PENDING, QUEUE_STATUS_PROCESSING):
        raise HTTPException(
            status_code=400,
            detail="Only PENDING or PROCESSING items can be cancelled",
        )
    row.status = QUEUE_STATUS_CANCELLED
    row.finished_at = datetime.now(tz=timezone.utc)
    row.error_message = "Cancelled by operator"
    await session.commit()
    await session.refresh(row)
    return row


@router.get("/job-logs", response_model=Page[SchedulerJobLogRead])
async def list_job_logs(
    page: int = 1,
    size: int = 20,
    job_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    _: User = Depends(current_superuser),
):
    if size < 1:
        raise HTTPException(status_code=400, detail="size must be >= 1")
    if size > MAX_PAGE_SIZE:
        raise HTTPException(status_code=400, detail=f"size must be <= {MAX_PAGE_SIZE}")
    params = Params(page=page, size=size)
    q = select(SchedulerJobLog).where(SchedulerJobLog.is_delete == False)  # noqa: E712
    if job_id and job_id.strip():
        q = q.where(SchedulerJobLog.job_id == job_id.strip())
    if status and status.strip():
        q = q.where(SchedulerJobLog.status == status.strip().upper())
    q = q.order_by(SchedulerJobLog.started_at.desc(), SchedulerJobLog.id.desc())
    return await apaginate(session, q, params, transformer=_transform_logs)


@router.post("/job-logs/{log_id}/clear-stuck-and-enqueue", response_model=SchedulerJobQueueRead)
async def clear_stuck_running_log_and_enqueue(
    log_id: int,
    min_age_seconds: int = Query(default=90, ge=5, le=86400),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_superuser),
):
    log = await session.get(SchedulerJobLog, log_id)
    if log is None or log.is_delete:
        raise HTTPException(status_code=404, detail="Log not found")
    if log.status != "RUNNING" or log.finished_at is not None:
        raise HTTPException(
            status_code=400,
            detail="Only unfinished RUNNING logs can be cleared this way",
        )

    now = datetime.now(tz=timezone.utc)
    started = log.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if (now - started).total_seconds() < float(min_age_seconds):
        raise HTTPException(
            status_code=400,
            detail=(
                f"log is newer than min_age_seconds={min_age_seconds}; "
                "wait or increase the threshold to avoid aborting a live run"
            ),
        )

    await session.execute(
        update(SchedulerJobLog)
        .where(SchedulerJobLog.id == log_id)
        .values(
            status="FAILED",
            finished_at=now,
            error_message="Marked stuck / operator restart; re-enqueued",
            updated_at=func.now(),
        )
    )

    q = SchedulerJobQueue(
        job_key=log.job_id,
        action=QUEUE_ACTION_RESTART,
        status=QUEUE_STATUS_PENDING,
        requested_by_user_id=user.id,
        related_log_id=log_id,
    )
    session.add(q)
    await session.commit()
    await session.refresh(q)
    return q
