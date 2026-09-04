from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, Depends, Query
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.current_user import CurrentUser, require
from app.config import settings
from app.database import get_async_session
from app.exceptions import AppError, ConflictError, NotFoundError
from app.models import SchedulerJobLog, SchedulerJobQueue, SchedulerSchedule
from app.pagination import Page, Params
from scheduler.jobs._registry import get_registry
from scheduler.jobs.registry import get_registered_job_keys

router = APIRouter()

QUEUE_ACTION_RUN_NOW = "RUN_NOW"
QUEUE_ACTION_RESTART = "RESTART"
QUEUE_ACTION_SCHEDULED = "SCHEDULED"
QUEUE_STATUS_PENDING = "PENDING"
QUEUE_STATUS_PROCESSING = "PROCESSING"
QUEUE_STATUS_CANCELLED = "CANCELLED"


def _validate_cron_expression(value: str) -> str:
    try:
        CronTrigger.from_crontab(value)
    except ValueError as e:
        raise ValueError(f"잘못된 Cron 표현식: {e}") from e
    return value


class SchedulerScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_key: str
    name: str
    cron_expression: str
    timezone: str
    enabled: bool
    payload: dict | list | None = None
    concurrency_key: str | None = None
    description: str | None
    registered: bool = True


class SchedulerScheduleCreate(BaseModel):
    job_key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=255)
    cron_expression: str = Field(min_length=1, max_length=120)
    enabled: bool = True
    payload: dict | None = None
    concurrency_key: str | None = Field(default=None, max_length=100)
    description: str | None = None

    @field_validator("cron_expression")
    @classmethod
    def _cron(cls, v: str) -> str:
        return _validate_cron_expression(v.strip())


class SchedulerScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    cron_expression: str | None = Field(default=None, max_length=120)
    enabled: bool | None = None
    payload: dict | None = None
    concurrency_key: str | None = Field(default=None, max_length=100)
    description: str | None = None

    @field_validator("cron_expression")
    @classmethod
    def _cron(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_cron_expression(v.strip())


class RegistryEntry(BaseModel):
    job_key: str
    title: str | None
    registered: bool
    schedule_count: int
    description: str | None = None


class CronPreviewResponse(BaseModel):
    next_runs: list[datetime]


class SchedulerJobQueueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_key: str
    schedule_id: UUID | None = None
    action: str
    status: str
    payload: dict | list | None = None
    requested_by_user_id: UUID | None
    related_log_id: UUID | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class SchedulerJobLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_key: str
    queue_id: UUID | None = None
    schedule_id: UUID | None = None
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
                job_key=r.job_key,
                queue_id=r.queue_id,
                schedule_id=r.schedule_id,
                started_at=r.started_at,
                finished_at=r.finished_at,
                status=r.status,
                elapsed_sec=float(r.elapsed_sec) if r.elapsed_sec is not None else None,
                error_message=r.error_message,
                detail=r.detail,
            )
        )
    return out


def _schedule_read(row: SchedulerSchedule) -> SchedulerScheduleRead:
    return SchedulerScheduleRead(
        id=row.id,
        job_key=row.job_key,
        name=row.name,
        cron_expression=row.cron_expression,
        timezone=row.timezone,
        enabled=row.enabled,
        payload=row.payload,
        concurrency_key=row.concurrency_key,
        description=row.description,
        registered=row.job_key in get_registered_job_keys(),
    )


@router.get("/registry", response_model=list[RegistryEntry])
async def list_registry(
    session: AsyncSession = Depends(get_async_session),
    _: CurrentUser = Depends(require("scheduler:read")),
):
    registry = get_registry()
    counts_result = await session.execute(
        select(SchedulerSchedule.job_key, func.count())
        .where(SchedulerSchedule.is_delete == False)  # noqa: E712
        .group_by(SchedulerSchedule.job_key)
    )
    counts = {job_key: int(n) for job_key, n in counts_result.all()}

    entries: list[RegistryEntry] = []
    for key, spec in sorted(registry.items()):
        entries.append(
            RegistryEntry(
                job_key=key,
                title=spec.title,
                registered=True,
                schedule_count=counts.get(key, 0),
                description=spec.description,
            )
        )
    for job_key, n in sorted(counts.items()):
        if job_key not in registry:
            entries.append(
                RegistryEntry(
                    job_key=job_key,
                    title=None,
                    registered=False,
                    schedule_count=n,
                )
            )
    return entries


@router.get("/cron-preview", response_model=CronPreviewResponse)
async def cron_preview(
    cron_expression: str = Query(..., min_length=1),
    count: int = Query(default=5, ge=1, le=20),
    _: CurrentUser = Depends(require("scheduler:read")),
):
    try:
        expr = _validate_cron_expression(cron_expression.strip())
        tz = ZoneInfo(settings.TZ)
        trigger = CronTrigger.from_crontab(expr, timezone=tz)
    except Exception as e:
        raise AppError(f"잘못된 Cron 표현식: {e}") from e

    now = datetime.now(tz=tz)
    runs: list[datetime] = []
    previous: datetime | None = None
    cursor = now
    for _ in range(count):
        nxt = trigger.get_next_fire_time(previous, cursor)
        if nxt is None:
            break
        runs.append(nxt)
        previous = nxt
        cursor = nxt
    return CronPreviewResponse(next_runs=runs)


@router.get("/schedules", response_model=list[SchedulerScheduleRead])
async def list_scheduler_schedules(
    q: str | None = Query(default=None, description="name 또는 job_key 검색"),
    session: AsyncSession = Depends(get_async_session),
    _: CurrentUser = Depends(require("scheduler:read")),
):
    stmt = select(SchedulerSchedule).where(
        SchedulerSchedule.is_delete == False  # noqa: E712
    )
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            SchedulerSchedule.name.ilike(term) | SchedulerSchedule.job_key.ilike(term)
        )
    stmt = stmt.order_by(SchedulerSchedule.name.asc(), SchedulerSchedule.id.asc())
    result = await session.execute(stmt)
    return [_schedule_read(row) for row in result.scalars().all()]


@router.post("/schedules", response_model=SchedulerScheduleRead, status_code=201)
async def create_scheduler_schedule(
    body: SchedulerScheduleCreate,
    session: AsyncSession = Depends(get_async_session),
    _: CurrentUser = Depends(require("scheduler:manage")),
):
    keys = get_registered_job_keys()
    if body.job_key not in keys:
        raise AppError(f"job_key must be one of: {', '.join(sorted(keys))}")
    row = SchedulerSchedule(**body.model_dump(), timezone=settings.TZ)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _schedule_read(row)


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_scheduler_schedule(
    schedule_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    _: CurrentUser = Depends(require("scheduler:manage")),
):
    row = await session.get(SchedulerSchedule, schedule_id)
    if row is None or row.is_delete:
        raise NotFoundError("Schedule not found")
    row.is_delete = True
    await session.commit()


@router.patch("/schedules/{schedule_id}", response_model=SchedulerScheduleRead)
async def update_scheduler_schedule(
    schedule_id: UUID,
    body: SchedulerScheduleUpdate,
    session: AsyncSession = Depends(get_async_session),
    _: CurrentUser = Depends(require("scheduler:manage")),
):
    row = await session.get(SchedulerSchedule, schedule_id)
    if row is None or row.is_delete:
        raise NotFoundError("Schedule not found")

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise AppError("No fields to update")

    for k, v in data.items():
        setattr(row, k, v)
    await session.commit()
    await session.refresh(row)
    return _schedule_read(row)


@router.post(
    "/schedules/{schedule_id}/enqueue-run",
    response_model=SchedulerJobQueueRead,
)
async def enqueue_run_now(
    schedule_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: CurrentUser = Depends(require("scheduler:manage")),
):
    schedule = await session.get(SchedulerSchedule, schedule_id)
    if schedule is None or schedule.is_delete:
        raise NotFoundError("Schedule not found")

    dup = await session.scalar(
        select(SchedulerJobQueue.id)
        .where(
            SchedulerJobQueue.schedule_id == schedule_id,
            SchedulerJobQueue.status.in_(
                (QUEUE_STATUS_PENDING, QUEUE_STATUS_PROCESSING)
            ),
            SchedulerJobQueue.is_delete == False,  # noqa: E712
        )
        .limit(1)
    )
    if dup is not None:
        raise ConflictError("이미 대기 중이거나 실행 중인 요청이 있습니다")

    q = SchedulerJobQueue(
        job_key=schedule.job_key,
        schedule_id=schedule.id,
        action=QUEUE_ACTION_RUN_NOW,
        status=QUEUE_STATUS_PENDING,
        payload=schedule.payload,
        requested_by_user_id=user.id,
    )
    session.add(q)
    await session.commit()
    await session.refresh(q)
    return q


@router.get("/queue", response_model=Page[SchedulerJobQueueRead])
async def list_job_queue(
    params: Params = Depends(),
    status: str | None = Query(default=None),
    job_key: str | None = Query(default=None),
    q: str | None = Query(default=None, description="job_key 검색"),
    session: AsyncSession = Depends(get_async_session),
    _: CurrentUser = Depends(require("scheduler:read")),
):
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
    queue_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    _: CurrentUser = Depends(require("scheduler:manage")),
):
    row = await session.get(SchedulerJobQueue, queue_id)
    if row is None or row.is_delete:
        raise NotFoundError("Queue item not found")
    if row.status not in (QUEUE_STATUS_PENDING, QUEUE_STATUS_PROCESSING):
        raise AppError("Only PENDING or PROCESSING items can be cancelled")
    row.status = QUEUE_STATUS_CANCELLED
    row.finished_at = datetime.now(tz=timezone.utc)
    row.error_message = "Cancelled by operator"
    await session.commit()
    await session.refresh(row)
    return row


@router.get("/job-logs", response_model=Page[SchedulerJobLogRead])
async def list_job_logs(
    params: Params = Depends(),
    job_key: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    _: CurrentUser = Depends(require("scheduler:read")),
):
    q = select(SchedulerJobLog).where(SchedulerJobLog.is_delete == False)  # noqa: E712
    if job_key and job_key.strip():
        q = q.where(SchedulerJobLog.job_key == job_key.strip())
    if status and status.strip():
        q = q.where(SchedulerJobLog.status == status.strip().upper())
    q = q.order_by(SchedulerJobLog.started_at.desc(), SchedulerJobLog.id.desc())
    return await apaginate(session, q, params, transformer=_transform_logs)


@router.post(
    "/job-logs/{log_id}/clear-stuck-and-enqueue",
    response_model=SchedulerJobQueueRead,
)
async def clear_stuck_running_log_and_enqueue(
    log_id: UUID,
    min_age_seconds: int = Query(default=90, ge=5, le=86400),
    session: AsyncSession = Depends(get_async_session),
    user: CurrentUser = Depends(require("scheduler:manage")),
):
    log = await session.get(SchedulerJobLog, log_id)
    if log is None or log.is_delete:
        raise NotFoundError("Log not found")
    if log.status != "RUNNING" or log.finished_at is not None:
        raise AppError("Only unfinished RUNNING logs can be cleared this way")

    now = datetime.now(tz=timezone.utc)
    started = log.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if (now - started).total_seconds() < float(min_age_seconds):
        raise AppError(
            f"log is newer than min_age_seconds={min_age_seconds}; "
            "wait or increase the threshold to avoid aborting a live run"
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
        job_key=log.job_key,
        schedule_id=log.schedule_id,
        action=QUEUE_ACTION_RESTART,
        status=QUEUE_STATUS_PENDING,
        requested_by_user_id=user.id,
        related_log_id=log_id,
    )
    session.add(q)
    await session.commit()
    await session.refresh(q)
    return q
