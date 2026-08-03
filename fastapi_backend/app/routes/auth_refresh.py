from datetime import datetime, timezone
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_async_session
from app.models import User
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


@router.post("/jwt/refresh-token")
async def issue_refresh_token(
    user: User = Depends(current_active_user),
):
    """
    Issue refresh token while access token is valid.
    Frontend stores it in HTTP-only cookie.
    """
    return {"refresh_token": _encode_refresh_token(user_id=user.id), "token_type": "bearer"}


@router.post("/jwt/refresh")
async def refresh_access_token(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Re-issue access token using refresh token from httpOnly cookie.
    """
    refresh_token = request.cookies.get("refreshToken")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    user_id = _decode_refresh_token(refresh_token)

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    strategy = get_jwt_strategy()
    access = await strategy.write_token(user)
    return {"access_token": access, "token_type": "bearer"}

