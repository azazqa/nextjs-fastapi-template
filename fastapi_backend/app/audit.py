import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog

logger = logging.getLogger(__name__)


async def log_audit(
    session: AsyncSession,
    *,
    action: str,
    actor_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail or {},
            ip=ip,
        )
    )
    await session.commit()


def log_superuser_bypass(actor_id: uuid.UUID, codes: tuple[str, ...]) -> None:
    logger.warning(
        "superuser bypass: actor=%s permissions=%s",
        actor_id,
        ",".join(sorted(codes)),
    )
