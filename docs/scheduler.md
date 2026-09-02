# Scheduler

APScheduler + PostgreSQL 큐 패턴으로 백그라운드 작업을 실행합니다.

## 아키텍처

- **FastAPI (`backend`)**: 큐에 작업을 적재하고 Admin API로 관리합니다. APScheduler는 포함하지 않습니다.
- **scheduler 컨테이너**: `scheduler_jobs`의 cron 설정을 읽고, 15초마다 `scheduler_job_queue`를 폴링해 job을 실행합니다.
- **PostgreSQL**: `scheduler_jobs`, `scheduler_job_queue`, `scheduler_job_log` 3테이블을 사용합니다.

```
Admin UI / API  →  scheduler_job_queue  ←  cron (scheduler runner)
                         ↓
                   job 실행 + scheduler_job_log
```

## 로컬 개발

### 마이그레이션

로컬에서 revision 생성 후 Docker에서 적용:

```bash
# 로컬 (Alembic revision 생성 시)
cd fastapi_backend && uv run alembic revision --autogenerate -m "description"

# Docker DB에 적용
make docker-migrate-db
```

### 서비스 기동

```bash
docker compose up -d db backend scheduler frontend
# 또는
make docker-start-scheduler
```

cron 변경은 **scheduler 컨테이너 재기동** 후 반영됩니다.

## Admin UI

superuser로 로그인하면 사이드바 **관리자 → 스케줄 관리** (`/admin/scheduler`)에서 Job 정의와 실행 이력을 확인할 수 있습니다.

## 새 job 추가

1. `fastapi_backend/scheduler/jobs/my_job.py` — `JOB_KEY` 상수와 `run_*()` 함수 구현
2. `scheduler/jobs/registry.py` — `_JOB_RUNNERS`에 job 등록 (단일 소스)
3. `scheduler/lock.py` — `LOCK_IDS`에 advisory lock ID 추가
4. (선택) Alembic migration으로 `scheduler_jobs` 시드

Admin UI는 `GET /admin/scheduler/job-keys`로 등록 가능한 job_key 목록을 조회합니다.

## 샘플 job

`sample_heartbeat`가 기본 시드로 포함되어 있습니다. 로그만 남기는 placeholder job입니다.
