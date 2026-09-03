import uuid
from datetime import datetime, timezone
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_async_session
from app.exceptions import RefreshTokenError, UnauthorizedError
from app.models import User
from app.services.auth_cookies import REFRESH_COOKIE_NAME, set_refresh_token_cookie
from app.services.refresh_tokens import (
    persist_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_refresh_token_row,
)
from app.users import current_active_user, get_jwt_strategy, get_user_manager
from fastapi_users import BaseUserManager


router = APIRouter(tags=["auth"])


def _encode_refresh_token(*, user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": str(uuid.uuid7()),
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
    except jwt.ExpiredSignatureError as exc:
        raise RefreshTokenError("Refresh token expired") from exc
    except jwt.PyJWTError as exc:
        raise RefreshTokenError("Invalid refresh token") from exc

    if payload.get("type") != "refresh":
        raise RefreshTokenError("Invalid refresh token type")

    try:
        return UUID(str(payload["sub"]))
    except (ValueError, TypeError) as exc:
        raise RefreshTokenError("Invalid refresh token subject") from exc


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
    Token is returned only via HttpOnly Set-Cookie (not JSON body).
    """
    raw_token = _encode_refresh_token(user_id=user.id)
    await persist_refresh_token(
        db,
        user_id=user.id,
        raw_token=raw_token,
        user_agent=request.headers.get("user-agent"),
        ip=_client_ip(request),
    )
    response = JSONResponse(content={"token_type": "bearer"})
    set_refresh_token_cookie(response, raw_token)
    return response


@router.post("/jwt/refresh")
async def refresh_access_token(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Re-issue access token using refresh token from httpOnly cookie.
    Rotates refresh token in DB; new refresh token is Set-Cookie only.
    """
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise UnauthorizedError("Missing refresh token")

    _decode_refresh_token(refresh_token)
    row = await verify_refresh_token_row(db, refresh_token)

    user = await db.get(User, row.user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

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
    response = JSONResponse(
        content={"access_token": access, "token_type": "bearer"},
    )
    set_refresh_token_cookie(response, new_refresh_token)
    return response


@router.post("/jwt/logout")
async def logout_refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    user_manager: BaseUserManager[User, uuid.UUID] = Depends(get_user_manager),
):
    """Revoke refresh cookie, clear cookie, and deny access JWT when Bearer is sent."""
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1]
        strategy = get_jwt_strategy()
        user = await strategy.read_token(token, user_manager)
        if user is not None:
            await strategy.destroy_token(token, user)

    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        await revoke_refresh_token(db, refresh_token)

    response = JSONResponse(content={"detail": "Logged out"})
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
    )
    return response
