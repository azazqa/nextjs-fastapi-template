from fastapi import Response

from app.config import settings

REFRESH_COOKIE_NAME = "refreshToken"


def set_refresh_token_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=int(settings.REFRESH_TOKEN_EXPIRE_SECONDS),
        path="/",
    )
