import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    pass


class UserMeRead(UserRead):
    roles: list[str] = []
    permissions: list[str] = []


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
