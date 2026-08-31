from unittest.mock import MagicMock, patch

from scheduler.jobs.sample_heartbeat import run_sample_heartbeat


@patch("scheduler.jobs._job_base.advisory_lock")
@patch("scheduler.jobs._job_base.scheduler_session")
def test_run_sample_heartbeat_success(mock_scheduler_session, mock_advisory_lock):
    mock_db = MagicMock()
    mock_db.execute.return_value.scalar.side_effect = [42, None]
    mock_scheduler_session.return_value.__enter__.return_value = mock_db
    mock_advisory_lock.return_value.__enter__.return_value = mock_db

    result = run_sample_heartbeat(engine=MagicMock())

    assert result is not None
    assert result.status == "SUCCESS"
    assert result.detail.get("heartbeat") is True


@patch("scheduler.jobs._job_base.advisory_lock")
def test_run_sample_heartbeat_lock_skipped(mock_advisory_lock):
    mock_advisory_lock.return_value.__enter__.return_value = None

    result = run_sample_heartbeat(engine=MagicMock())

    assert result is None
