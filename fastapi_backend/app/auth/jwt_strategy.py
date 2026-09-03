from __future__ import annotations

import uuid

import jwt
from fastapi_users import exceptions, models
from fastapi_users.authentication.strategy.jwt import JWTStrategy
from fastapi_users.jwt import decode_jwt, generate_jwt
from fastapi_users.manager import BaseUserManager

from app.services.access_denylist import deny_access_jti, is_access_jti_denied


class DenyListJWTStrategy(JWTStrategy[models.UP, models.ID]):
    async def read_token(
        self, token: str | None, user_manager: BaseUserManager[models.UP, models.ID]
    ) -> models.UP | None:
        if token is None:
            return None

        try:
            data = decode_jwt(
                token, self.decode_key, self.token_audience, algorithms=[self.algorithm]
            )
        except jwt.PyJWTError:
            return None

        jti = data.get("jti")
        if jti and await is_access_jti_denied(str(jti)):
            return None

        user_id = data.get("sub")
        if user_id is None:
            return None

        try:
            parsed_id = user_manager.parse_id(user_id)
            return await user_manager.get(parsed_id)
        except (exceptions.UserNotExists, exceptions.InvalidID):
            return None

    async def write_token(self, user: models.UP) -> str:
        data = {
            "sub": str(user.id),
            "aud": self.token_audience,
            "jti": str(uuid.uuid7()),
        }
        return generate_jwt(
            data, self.encode_key, self.lifetime_seconds, algorithm=self.algorithm
        )

    async def destroy_token(self, token: str, user: models.UP) -> None:
        try:
            data = decode_jwt(
                token, self.decode_key, self.token_audience, algorithms=[self.algorithm]
            )
        except jwt.PyJWTError:
            return
        jti = data.get("jti")
        if jti:
            await deny_access_jti(str(jti))
