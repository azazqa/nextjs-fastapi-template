import uuid
from datetime import datetime

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    is_delete: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=false()
    )


class User(SQLAlchemyBaseUserTableUUID, Base):
    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid7)


class SchedulerJobLog(Base):
    """스케줄러 잡 실행 이력 테이블."""

    __tablename__ = "scheduler_job_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="RUNNING"
    )
    elapsed_sec: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_scheduler_job_log_job_id_started_at", "job_id", "started_at"),
    )


class SchedulerJob(Base):
    """스케줄러 잡 정의(메타데이터). runner는 기동 시 이 테이블을 읽어 CronTrigger를 구성한다."""

    __tablename__ = "scheduler_jobs"

    job_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    cron_hour: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    cron_minute: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Asia/Seoul", server_default="Asia/Seoul"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class SchedulerJobQueue(Base):
    """관리자가 즉시 실행·중단 복구 등을 요청할 때 적재되는 큐."""

    __tablename__ = "scheduler_job_queue"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", server_default="PENDING"
    )
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user.id"), nullable=True, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_log_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_scheduler_job_queue_status_created", "status", "created_at"),
    )
