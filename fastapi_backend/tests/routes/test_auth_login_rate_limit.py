import asyncio

import pytest
from fastapi_users.router.common import ErrorCode

from app.exceptions import RateLimitError
from app.services import login_rate_limit as rl


@pytest.mark.asyncio
async def test_login_rate_limit_locks_after_five_failures(test_client):
    email = "ratelimit@example.com"

    for _ in range(5):
        res = await test_client.post(
            "/auth/jwt/login",
            data={"username": email, "password": "WrongPassword1!"},
        )
        assert res.status_code == 400
        assert res.json()["detail"] == ErrorCode.LOGIN_BAD_CREDENTIALS

    locked = await test_client.post(
        "/auth/jwt/login",
        data={"username": email, "password": "WrongPassword1!"},
    )
    assert locked.status_code == 429
    assert "Too many failed login attempts" in locked.json()["detail"]
    assert locked.headers.get("retry-after") is not None


@pytest.mark.asyncio
async def test_login_success_clears_rate_limit(test_client, authenticated_user):
    email = authenticated_user["user_data"]["email"]

    for _ in range(3):
        await test_client.post(
            "/auth/jwt/login",
            data={"username": email, "password": "WrongPassword1!"},
        )

    ok = await test_client.post(
        "/auth/jwt/login",
        data={
            "username": email,
            "password": authenticated_user["user_data"]["password"],
        },
    )
    assert ok.status_code == 200
    assert "access_token" in ok.json()

    # After success, failures should not immediately lock again.
    again = await test_client.post(
        "/auth/jwt/login",
        data={"username": email, "password": "WrongPassword1!"},
    )
    assert again.status_code == 400


@pytest.mark.asyncio
async def test_login_rate_limit_holds_under_concurrent_failures(fake_redis):
    """동시 실패에서도 Redis INCR 경로로 잠금이 발동해야 한다 (C3).

    HTTP 동시 요청은 테스트용 단일 DB 세션에서 교착되므로 서비스 API를 직접 호출한다.
    """
    email = "concurrent@example.com"

    await asyncio.gather(*[rl.record_login_failure(email) for _ in range(5)])

    with pytest.raises(RateLimitError):
        await rl.assert_login_allowed(email)


def test_memory_store_is_bounded():
    """인메모리 저장소가 상한을 넘지 않아야 한다 (H3 회귀 방지)."""
    rl._store.clear()
    try:
        for i in range(rl._MAX_TRACKED_IDS + 500):
            rl._record_login_failure_memory(f"user{i}@example.com")
        assert len(rl._store) <= rl._MAX_TRACKED_IDS
    finally:
        rl._store.clear()
