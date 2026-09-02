import inspect

from fastapi import Depends
from fastapi.routing import APIRoute

from app.auth.current_user import get_current_user, require
from app.main import app
from app.users import current_active_user, current_superuser


PUBLIC_PATHS = {
    "/auth/jwt/login",
    "/auth/jwt/logout",
    "/auth/jwt/refresh",
    "/auth/jwt/refresh-token",
    "/auth/forgot-password",
    "/auth/reset-password",
    "/auth/request-verify-token",
    "/auth/verify",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}


def _uses_require(route: APIRoute) -> bool:
    if route.endpoint is None:
        return False
    sig = inspect.signature(route.endpoint)
    for param in sig.parameters.values():
        if isinstance(param.default, Depends):
            dep = param.default.dependency
            qualname = getattr(dep, "__qualname__", "")
            if "require" in qualname:
                return True
    return False


def _uses_auth_dependency(route: APIRoute) -> bool:
    if route.endpoint is None:
        return False
    allowed = {get_current_user, current_active_user, current_superuser}
    sig = inspect.signature(route.endpoint)
    for param in sig.parameters.values():
        if isinstance(param.default, Depends):
            dep = param.default.dependency
            if dep in allowed:
                return True
            qualname = getattr(dep, "__qualname__", "")
            if "current_user" in qualname or "get_current_user" in qualname:
                return True
    return False


def test_admin_routes_declare_require():
    missing: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/admin/"):
            continue
        if not _uses_require(route):
            missing.append(f"{','.join(route.methods)} {route.path}")
    assert not missing, f"Admin routes missing require(): {missing}"


def test_non_public_routes_have_auth():
    missing: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path in PUBLIC_PATHS:
            continue
        if route.path.startswith("/admin/"):
            continue
        if _uses_require(route) or _uses_auth_dependency(route):
            continue
        missing.append(f"{','.join(route.methods)} {route.path}")
    assert not missing, f"Routes missing auth dependency: {missing}"
