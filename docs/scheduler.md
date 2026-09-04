# Scheduler

APScheduler + PostgreSQL 큐 패턴으로 백그라운드 작업을 실행합니다.

## 아키텍처

- **FastAPI (`backend`)**: 큐에 작업을 적재하고 Admin API로 관리합니다. APScheduler는 포함하지 않습니다.
- **scheduler 컨테이너**: `scheduler_schedules`의 cron 설정을 읽고(60초마다 핫 리로드), 15초마다 `scheduler_job_queue`를 폴링해 job을 실행합니다.
- **PostgreSQL**: `scheduler_schedules`, `scheduler_job_queue`, `scheduler_job_log` 3테이블을 사용합니다.
- **코드 레지스트리**: `@job` 데코레이터 + `discover()`가 job_key의 단일 소스입니다. Job Key DB 테이블은 없습니다.

```
Admin UI / API  →  scheduler_job_queue  ←  cron (scheduler runner)
                         ↓
                   job 실행 + scheduler_job_log
```

한 job_key(러너) 위에 스케줄(N)을 둘 수 있습니다. 예: 같은 수집 러너로 야간 전체 / 주간 증분.

## 로컬 개발

### 마이그레이션

모델 변경 후 revision은 **직접** 생성합니다 (에이전트가 `alembic/versions`를 작성하지 않습니다).

```bash
# 로컬 (Alembic revision 생성 시)
cd fastapi_backend && uv run alembic revision --autogenerate -m "split schedule from job_key"

# 생성된 revision에서 확인·보완:
# - scheduler_schedules 생성
# - 기존 scheduler_jobs → cron_expression='{m} {h} * * *' 로 시드 후 DROP
# - scheduler_job_log.job_id → job_key 개명
# - queue/log 에 schedule_id · queue_id 컬럼

# Docker DB에 적용
make docker-migrate-db
```

### 서비스 기동

```bash
docker compose up -d db backend scheduler frontend
# 또는
make docker-start-scheduler
```

cron 변경은 Admin UI에서 저장하면 **약 60초 이내** runner에 반영됩니다 (컨테이너 재기동 불필요).

## Admin UI

권한이 있는 계정으로 사이드바 **관리자 → 스케줄 관리** (`/admin/scheduler`)에서 스케줄과 실행 이력을 확인할 수 있습니다.

- `GET /admin/scheduler/registry` — 코드에 등록된 job과 고아 스케줄
- `GET/POST /admin/scheduler/schedules` — 스케줄 CRUD
- cron 예: `0 * * * *` (매시 정각), `*/10 * * * *` (10분마다)

## 새 job 추가

**파일 하나**면 됩니다.

1. `fastapi_backend/scheduler/jobs/my_job.py`에 `@job(...)` 데코레이터와 러너 함수를 작성합니다.
2. (선택) Admin UI에서 해당 `job_key`로 스케줄을 만듭니다.

모듈 최상단에는 표준 라이브러리와 `_registry`만 import 하세요. 무거운 의존성은 함수 안에서 import 합니다.

```python
from scheduler.jobs._registry import job

@job("my_job", title="My Job")
def my_job(*, engine=None, payload=None, ctx=None) -> dict:
    # heavy imports inside
    return {"ok": True}
```

하위 패키지(`jobs/collect/...`)도 `walk_packages`로 자동 인식됩니다. `_`로 시작하는 모듈은 스킵됩니다.

## 샘플 job

`sample_heartbeat`가 기본 예제입니다. 로그만 남기는 placeholder job입니다.
