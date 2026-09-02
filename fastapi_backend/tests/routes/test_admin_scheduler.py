import uuid

import pytest
import pytest_asyncio
from fastapi_users.password import PasswordHelper
from sqlalchemy import select

from app.models import Role, SchedulerJob, User, UserRole


@pytest_asyncio.fixture(loop_scope="function")
async def operator_headers(operator_user):
    return operator_user["headers"]


@pytest.mark.asyncio
async def test_list_scheduler_jobs_requires_auth(test_client):
    res = await test_client.get("/admin/scheduler/jobs")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_scheduler_jobs_forbidden_without_role(
    test_client, authenticated_user
):
    res = await test_client.get(
        "/admin/scheduler/jobs",
        headers=authenticated_user["headers"],
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_list_scheduler_jobs_for_operator(
    test_client, db_session, operator_headers
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

    res = await test_client.get("/admin/scheduler/jobs", headers=operator_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["job_key"] == "sample_heartbeat"


@pytest.mark.asyncio
async def test_list_registered_job_keys(test_client, operator_headers):
    res = await test_client.get("/admin/scheduler/job-keys", headers=operator_headers)
    assert res.status_code == 200
    assert res.json() == ["sample_heartbeat"]


@pytest.mark.asyncio
async def test_create_scheduler_job_rejects_unknown_job_key(
    test_client, operator_headers
):
    res = await test_client.post(
        "/admin/scheduler/jobs",
        headers={**operator_headers, "Content-Type": "application/json"},
        json={
            "job_key": "unknown_job",
            "title": "Bad",
            "enabled": True,
            "cron_hour": 3,
            "cron_minute": 0,
            "timezone": "Asia/Seoul",
        },
    )
    assert res.status_code == 400
    assert "job_key must be one of" in res.json()["detail"]


@pytest.mark.asyncio
async def test_enqueue_run_now(test_client, db_session, operator_headers):
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
        headers=operator_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["job_key"] == "sample_heartbeat"
    assert body["status"] == "PENDING"
    assert body["action"] == "RUN_NOW"
