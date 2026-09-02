import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import RefreshTokenError
from app.models import RefreshToken


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def persist_refresh_token(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    raw_token: str,
    client: str = "admin_web",
    user_agent: str | None = None,
    ip: str | None = None,
) -> RefreshToken:
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=int(settings.REFRESH_TOKEN_EXPIRE_SECONDS)
    )
    row = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(raw_token),
        client=client,
        user_agent=user_agent,
        ip=ip,
        expires_at=expires_at,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def revoke_refresh_token(
    session: AsyncSession, raw_token: str
) -> None:
    token_hash = hash_refresh_token(raw_token)
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    if row is None or row.revoked_at is not None:
        return
    row.revoked_at = datetime.now(timezone.utc)
    await session.commit()


async def revoke_all_user_refresh_tokens(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    now = datetime.now(timezone.utc)
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await session.commit()


async def verify_refresh_token_row(
    session: AsyncSession, raw_token: str
) -> RefreshToken:
    token_hash = hash_refresh_token(raw_token)
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    if row is None:
        raise RefreshTokenError("Invalid refresh token")

    now = datetime.now(timezone.utc)
    if row.revoked_at is not None:
        await revoke_all_user_refresh_tokens(session, row.user_id)
        raise RefreshTokenError("Refresh token revoked")

    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise RefreshTokenError("Refresh token expired")

    return row


async def rotate_refresh_token(
    session: AsyncSession,
    row: RefreshToken,
    *,
    new_raw_token: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    row.revoked_at = now
    expires_at = now + timedelta(seconds=int(settings.REFRESH_TOKEN_EXPIRE_SECONDS))
    session.add(
        RefreshToken(
            user_id=row.user_id,
            token_hash=hash_refresh_token(new_raw_token),
            client=row.client,
            user_agent=user_agent or row.user_agent,
            ip=ip or row.ip,
            expires_at=expires_at,
        )
    )
    await session.commit()
