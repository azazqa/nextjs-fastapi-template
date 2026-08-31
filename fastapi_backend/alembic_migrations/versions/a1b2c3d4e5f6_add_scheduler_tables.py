"""add scheduler tables

Revision ID: a1b2c3d4e5f6
Revises: f532d17c937f
Create Date: 2026-08-31 17:50:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f532d17c937f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduler_job_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=100), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="RUNNING", nullable=False),
        sa.Column("elapsed_sec", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "is_delete",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scheduler_job_log_job_id"), "scheduler_job_log", ["job_id"])
    op.create_index(
        op.f("ix_scheduler_job_log_started_at"), "scheduler_job_log", ["started_at"]
    )
    op.create_index(
        "ix_scheduler_job_log_job_id_started_at",
        "scheduler_job_log",
        ["job_id", "started_at"],
    )

    op.create_table(
        "scheduler_jobs",
        sa.Column("job_key", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("cron_hour", sa.Integer(), server_default="3", nullable=False),
        sa.Column("cron_minute", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "timezone", sa.String(length=64), server_default="Asia/Seoul", nullable=False
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "is_delete",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("job_key"),
    )

    op.create_table(
        "scheduler_job_queue",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_key", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("related_log_id", sa.BigInteger(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "is_delete",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_scheduler_job_queue_job_key"), "scheduler_job_queue", ["job_key"]
    )
    op.create_index(
        op.f("ix_scheduler_job_queue_requested_by_user_id"),
        "scheduler_job_queue",
        ["requested_by_user_id"],
    )
    op.create_index(
        "ix_scheduler_job_queue_status_created",
        "scheduler_job_queue",
        ["status", "created_at"],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO scheduler_jobs (
                job_key, title, enabled, cron_hour, cron_minute, timezone, description
            ) VALUES (
                'sample_heartbeat',
                'Sample Heartbeat',
                true,
                3,
                0,
                'Asia/Seoul',
                'Template sample job — logs a heartbeat placeholder'
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_scheduler_job_queue_status_created", table_name="scheduler_job_queue")
    op.drop_index(
        op.f("ix_scheduler_job_queue_requested_by_user_id"), table_name="scheduler_job_queue"
    )
    op.drop_index(op.f("ix_scheduler_job_queue_job_key"), table_name="scheduler_job_queue")
    op.drop_table("scheduler_job_queue")
    op.drop_table("scheduler_jobs")
    op.drop_index("ix_scheduler_job_log_job_id_started_at", table_name="scheduler_job_log")
    op.drop_index(op.f("ix_scheduler_job_log_started_at"), table_name="scheduler_job_log")
    op.drop_index(op.f("ix_scheduler_job_log_job_id"), table_name="scheduler_job_log")
    op.drop_table("scheduler_job_log")
