import uuid

import pytest
import pytest_asyncio
from fastapi_users.password import PasswordHelper

from app.models import SchedulerJob, User


@pytest_asyncio.fixture
async def superuser_headers(test_client, db_session):
    user = User(
        id=uuid.uuid7(),
        email="admin@example.com",
        hashed_password=PasswordHelper().hash("AdminPassword123#"),
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    res = await test_client.post(
        "/auth/jwt/login",
        data={"username": "admin@example.com", "password": "AdminPassword123#"},
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_scheduler_jobs_requires_auth(test_client):
    res = await test_client.get("/admin/scheduler/jobs")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_scheduler_jobs_forbidden_for_non_superuser(
    test_client, authenticated_user
):
    res = await test_client.get(
        "/admin/scheduler/jobs",
        headers=authenticated_user["headers"],
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_list_scheduler_jobs_for_superuser(
    test_client, db_session, superuser_headers
):
    job = SchedulerJob(
        job_key="sample_heartbeat",
        title="Sample Heartbeat",
        enabled=True,
        cron_hour=3,
        cron_minute=0,
        timezone="Asia/Seoul",
        description="test",
    )
    db_session.add(job)
    await db_session.commit()

    res = await test_client.get("/admin/scheduler/jobs", headers=superuser_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["job_key"] == "sample_heartbeat"


@pytest.mark.asyncio
async def test_enqueue_run_now(test_client, db_session, superuser_headers):
    job = SchedulerJob(
        job_key="sample_heartbeat",
        title="Sample Heartbeat",
        enabled=True,
        cron_hour=3,
        cron_minute=0,
        timezone="Asia/Seoul",
    )
    db_session.add(job)
    await db_session.commit()

    res = await test_client.post(
        "/admin/scheduler/jobs/sample_heartbeat/enqueue-run",
        headers=superuser_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["job_key"] == "sample_heartbeat"
    assert body["status"] == "PENDING"
    assert body["action"] == "RUN_NOW"
