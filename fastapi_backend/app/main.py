import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination
from sqlalchemy import func, select

from app.config import settings
from app.redis import close_redis
from app.database import async_session_maker
from app.exception_handlers import register_exception_handlers
from app.models import User
from app.routes.admin_scheduler import router as admin_scheduler_router
from app.routes.auth_jwt import router as auth_jwt_router
from app.routes.auth_refresh import router as auth_refresh_router
from app.routes.users_me import router as users_me_router
from app.schemas import UserRead, UserUpdate
from app.users import AUTH_URL_PATH, fastapi_users
from app.utils import simple_generate_unique_route_id

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_session_maker() as session:
        count = await session.scalar(
            select(func.count()).select_from(User).where(User.is_superuser.is_(True))
        )
        if count and count > 2:
            logger.critical(
                "superuser 계정이 %d개입니다. 즉시 확인이 필요합니다.", count
            )
    yield
    await close_redis()


app = FastAPI(
    generate_unique_id_function=simple_generate_unique_route_id,
    openapi_url=settings.OPENAPI_URL,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_refresh_router, prefix=f"/{AUTH_URL_PATH}", tags=["auth"])
app.include_router(
    auth_jwt_router,
    prefix=f"/{AUTH_URL_PATH}/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix=f"/{AUTH_URL_PATH}",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix=f"/{AUTH_URL_PATH}",
    tags=["auth"],
)
app.include_router(users_me_router, prefix="/users", tags=["users"])
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)
app.include_router(
    admin_scheduler_router,
    prefix="/admin/scheduler",
    tags=["admin-scheduler"],
)
add_pagination(app)
register_exception_handlers(app)
