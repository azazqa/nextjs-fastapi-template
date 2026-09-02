from datetime import datetime, timezone
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_async_session
from app.models import User
from app.services.refresh_tokens import (
    persist_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_refresh_token_row,
)
from app.users import current_active_user, get_jwt_strategy


router = APIRouter(tags=["auth"])


def _encode_refresh_token(*, user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + int(settings.REFRESH_TOKEN_EXPIRE_SECONDS),
    }
    return jwt.encode(payload, settings.REFRESH_SECRET_KEY, algorithm=settings.ALGORITHM)


def _decode_refresh_token(token: str) -> UUID:
    try:
        payload = jwt.decode(
            token,
            settings.REFRESH_SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token type")

    try:
        return UUID(str(payload["sub"]))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token subject")


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


@router.post("/jwt/refresh-token")
async def issue_refresh_token(
    request: Request,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Issue refresh token while access token is valid.
    Frontend stores it in HTTP-only cookie.
    """
    raw_token = _encode_refresh_token(user_id=user.id)
    await persist_refresh_token(
        db,
        user_id=user.id,
        raw_token=raw_token,
        user_agent=request.headers.get("user-agent"),
        ip=_client_ip(request),
    )
    return {"refresh_token": raw_token, "token_type": "bearer"}


@router.post("/jwt/refresh")
async def refresh_access_token(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Re-issue access token using refresh token from httpOnly cookie.
    Rotates refresh token in DB and returns a new refresh token when valid.
    """
    refresh_token = request.cookies.get("refreshToken")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    _decode_refresh_token(refresh_token)
    row = await verify_refresh_token_row(db, refresh_token)

    user = await db.get(User, row.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    new_refresh_token = _encode_refresh_token(user_id=user.id)
    await rotate_refresh_token(
        db,
        row,
        new_raw_token=new_refresh_token,
        user_agent=request.headers.get("user-agent"),
        ip=_client_ip(request),
    )

    strategy = get_jwt_strategy()
    access = await strategy.write_token(user)
    return {
        "access_token": access,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@router.post("/jwt/logout")
async def logout_refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """Revoke refresh token stored in the refreshToken cookie."""
    refresh_token = request.cookies.get("refreshToken")
    if refresh_token:
        await revoke_refresh_token(db, refresh_token)
    return {"detail": "Logged out"}
