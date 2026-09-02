import pytest
from fastapi_users.router.common import ErrorCode


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
