import uuid

import pytest
import pytest_asyncio

from app.models import SchedulerSchedule


@pytest_asyncio.fixture(loop_scope="function")
async def operator_headers(operator_user):
    return operator_user["headers"]


@pytest.mark.asyncio
async def test_list_scheduler_schedules_requires_auth(test_client):
    res = await test_client.get("/admin/scheduler/schedules")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_scheduler_schedules_forbidden_without_role(
    test_client, authenticated_user
):
    res = await test_client.get(
        "/admin/scheduler/schedules",
        headers=authenticated_user["headers"],
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_list_scheduler_schedules_for_operator(
    test_client, db_session, operator_headers
):
    schedule = SchedulerSchedule(
        job_key="sample_heartbeat",
        name="Sample Heartbeat Nightly",
        cron_expression="0 3 * * *",
        timezone="Asia/Seoul",
        enabled=True,
        description="test",
    )
    db_session.add(schedule)
    await db_session.commit()

    res = await test_client.get("/admin/scheduler/schedules", headers=operator_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["job_key"] == "sample_heartbeat"
    assert data[0]["cron_expression"] == "0 3 * * *"
    assert data[0]["registered"] is True


@pytest.mark.asyncio
async def test_list_registry(test_client, db_session, operator_headers):
    schedule = SchedulerSchedule(
        job_key="sample_heartbeat",
        name="HB",
        cron_expression="0 * * * *",
        timezone="Asia/Seoul",
        enabled=True,
    )
    db_session.add(schedule)
    await db_session.commit()

    res = await test_client.get("/admin/scheduler/registry", headers=operator_headers)
    assert res.status_code == 200
    data = res.json()
    sample = next(e for e in data if e["job_key"] == "sample_heartbeat")
    assert sample["registered"] is True
    assert sample["schedule_count"] == 1
    assert sample["title"] == "Sample Heartbeat"


@pytest.mark.asyncio
async def test_create_scheduler_schedule_rejects_unknown_job_key(
    test_client, operator_headers
):
    res = await test_client.post(
        "/admin/scheduler/schedules",
        headers={**operator_headers, "Content-Type": "application/json"},
        json={
            "job_key": "unknown_job",
            "name": "Bad",
            "enabled": True,
            "cron_expression": "0 3 * * *",
            "timezone": "Asia/Seoul",
        },
    )
    assert res.status_code == 400
    assert "job_key must be one of" in res.json()["detail"]


@pytest.mark.asyncio
async def test_create_rejects_invalid_cron(test_client, operator_headers):
    res = await test_client.post(
        "/admin/scheduler/schedules",
        headers={**operator_headers, "Content-Type": "application/json"},
        json={
            "job_key": "sample_heartbeat",
            "name": "Bad cron",
            "cron_expression": "not a cron",
            "timezone": "Asia/Seoul",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_enqueue_run_now(test_client, db_session, operator_headers):
    schedule = SchedulerSchedule(
        id=uuid.uuid7(),
        job_key="sample_heartbeat",
        name="Sample Heartbeat",
        cron_expression="0 3 * * *",
        timezone="Asia/Seoul",
        enabled=True,
    )
    db_session.add(schedule)
    await db_session.commit()

    res = await test_client.post(
        f"/admin/scheduler/schedules/{schedule.id}/enqueue-run",
        headers=operator_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["job_key"] == "sample_heartbeat"
    assert body["status"] == "PENDING"
    assert body["action"] == "RUN_NOW"
    assert body["schedule_id"] == str(schedule.id)

    dup = await test_client.post(
        f"/admin/scheduler/schedules/{schedule.id}/enqueue-run",
        headers=operator_headers,
    )
    assert dup.status_code == 409
