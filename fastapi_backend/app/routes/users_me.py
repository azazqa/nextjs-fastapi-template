from fastapi import APIRouter, Depends

from app.auth.current_user import CurrentUser, get_current_user
from app.schemas import UserMeRead


router = APIRouter()


@router.get("/me", response_model=UserMeRead)
async def read_users_me(
    user: CurrentUser = Depends(get_current_user),
):
    return UserMeRead(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        is_verified=user.is_verified,
        roles=list(user.roles),
        permissions=sorted(user.permissions),
    )
