import pytest


def _refresh_cookie(response) -> str:
    token = response.cookies.get("refreshToken")
    assert token, "refreshToken Set-Cookie missing"
    return token


@pytest.mark.asyncio
async def test_users_me_requires_auth(test_client):
    res = await test_client.get("/users/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_users_me_without_role_has_empty_permissions(
    test_client, authenticated_user
):
    res = await test_client.get("/users/me", headers=authenticated_user["headers"])
    assert res.status_code == 200
    body = res.json()
    assert body["roles"] == []
    assert body["permissions"] == []
    assert body["is_superuser"] is False


@pytest.mark.asyncio
async def test_users_me_returns_operator_roles_and_permissions(
    test_client, operator_user
):
    res = await test_client.get("/users/me", headers=operator_user["headers"])
    assert res.status_code == 200
    body = res.json()
    assert "operator" in body["roles"]
    assert "scheduler:read" in body["permissions"]
    assert "scheduler:manage" in body["permissions"]
    assert "user:manage" not in body["permissions"]


@pytest.mark.asyncio
async def test_issue_refresh_token_sets_cookie_only(test_client, authenticated_user):
    res = await test_client.post(
        "/auth/jwt/refresh-token",
        headers=authenticated_user["headers"],
    )
    assert res.status_code == 200
    body = res.json()
    assert body == {"token_type": "bearer"}
    assert "refresh_token" not in body
    _refresh_cookie(res)


@pytest.mark.asyncio
async def test_refresh_access_token_rotates_cookie(test_client, authenticated_user):
    issue = await test_client.post(
        "/auth/jwt/refresh-token",
        headers=authenticated_user["headers"],
    )
    refresh_token = _refresh_cookie(issue)

    res = await test_client.post(
        "/auth/jwt/refresh",
        cookies={"refreshToken": refresh_token},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["access_token"]
    assert "refresh_token" not in body
    assert _refresh_cookie(res) != refresh_token


@pytest.mark.asyncio
async def test_refresh_missing_cookie_returns_401(test_client):
    res = await test_client.post("/auth/jwt/refresh")
    assert res.status_code == 401
    assert res.json()["detail"] == "Missing refresh token"


@pytest.mark.asyncio
async def test_refresh_token_reuse_revokes_sessions(test_client, authenticated_user):
    issue = await test_client.post(
        "/auth/jwt/refresh-token",
        headers=authenticated_user["headers"],
    )
    refresh_token = _refresh_cookie(issue)

    first = await test_client.post(
        "/auth/jwt/refresh",
        cookies={"refreshToken": refresh_token},
    )
    assert first.status_code == 200
    rotated_refresh = _refresh_cookie(first)

    reuse = await test_client.post(
        "/auth/jwt/refresh",
        cookies={"refreshToken": refresh_token},
    )
    assert reuse.status_code == 401

    after_reuse = await test_client.post(
        "/auth/jwt/refresh",
        cookies={"refreshToken": rotated_refresh},
    )
    assert after_reuse.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(test_client, authenticated_user):
    issue = await test_client.post(
        "/auth/jwt/refresh-token",
        headers=authenticated_user["headers"],
    )
    refresh_token = _refresh_cookie(issue)

    logout = await test_client.post(
        "/auth/jwt/logout",
        cookies={"refreshToken": refresh_token},
    )
    assert logout.status_code == 200

    refresh = await test_client.post(
        "/auth/jwt/refresh",
        cookies={"refreshToken": refresh_token},
    )
    assert refresh.status_code == 401


@pytest.mark.asyncio
async def test_refreshed_access_token_works_for_users_me(
    test_client, authenticated_user
):
    issue = await test_client.post(
        "/auth/jwt/refresh-token",
        headers=authenticated_user["headers"],
    )
    refresh_token = _refresh_cookie(issue)

    refresh = await test_client.post(
        "/auth/jwt/refresh",
        cookies={"refreshToken": refresh_token},
    )
    assert refresh.status_code == 200
    access_token = refresh.json()["access_token"]

    me = await test_client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == authenticated_user["user"].email


@pytest.mark.asyncio
async def test_user_update_rejects_privileged_fields(test_client, authenticated_user):
    headers = {
        **authenticated_user["headers"],
        "Content-Type": "application/json",
    }
    for payload in (
        {"is_superuser": True},
        {"is_active": False},
    ):
        res = await test_client.patch("/users/me", headers=headers, json=payload)
        assert res.status_code == 422
