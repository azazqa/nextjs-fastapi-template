from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users.router.common import ErrorCode

from app.services.login_rate_limit import (
    assert_login_allowed,
    clear_login_failures,
    record_login_failure,
)
from app.users import User, auth_backend, get_user_manager
from fastapi_users import BaseUserManager


router = APIRouter()


@router.post("/login")
async def login(
    request: Request,
    credentials: OAuth2PasswordRequestForm = Depends(),
    user_manager: BaseUserManager[User, ...] = Depends(get_user_manager),
    strategy=Depends(auth_backend.get_strategy),
):
    await assert_login_allowed(credentials.username)

    user = await user_manager.authenticate(credentials)
    if user is None or not user.is_active:
        await record_login_failure(credentials.username)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.LOGIN_BAD_CREDENTIALS,
        )

    await clear_login_failures(credentials.username)
    response = await auth_backend.login(strategy, user)
    await user_manager.on_after_login(user, request, response)
    return response
