# 스케줄러 구조 검토 · 재설계

> 작성일: 2026-09-04 (개정 2판 — 자동 등록 검토 통합)
> 대상: `azazqa/nextjs-fastapi-template` — `main` @ `c7948ae`
> 읽은 파일: `scheduler/{runner,queue_processor,lock,db}.py`, `scheduler/jobs/{registry,_job_base,sample_heartbeat}.py`, `app/models.py`, `app/routes/admin_scheduler.py`, `app/rbac/constants.py`, `docker-compose.yml`, `docs/scheduler.md`
> 개발 규모: **Task 10~20개, 활성 스케줄 10개 내외**

---

## 요약

두 가지를 분리하면 나머지가 따라온다.

| 개념 | 소유자 | 정체성 | 지금 |
|---|---|---|---|
| **job_key** | **코드** | 무엇을 실행하는가 | 4곳에 수동 동기화 |
| **Schedule (Task)** | **DB / 운영자** | 언제·어떤 인자로 실행하는가 | job_key와 1:1 강제 결합 |

**목표 구조**

```
scheduler/jobs/*.py          ← @job 데코레이터. Task 개발 = 파일 하나
        ↓ discover()  (기동 시 1회)
   코드 레지스트리 (SSOT — 별도 테이블 없음)
        ↓ GET /admin/scheduler/registry
scheduler_schedules (N개)    ← 운영자가 화면에서 생성. cron_expression · payload
        ↓
scheduler_job_queue  →  scheduler_job_log
```

새 Task 추가 시 손대는 곳이 **4곳 → 1곳**이 된다.

---

## 1. 현재 구조

```
Admin UI / API  →  scheduler_job_queue  ←  cron (scheduler runner)
                          ↓
                    job 실행 + scheduler_job_log
```

- **backend** — 큐 적재와 Admin API. APScheduler 없음
- **scheduler 컨테이너** — 기동 시 `scheduler_jobs`를 읽어 `CronTrigger` 구성, 15초마다 큐 폴링
- **PostgreSQL** — `scheduler_jobs` / `scheduler_job_queue` / `scheduler_job_log`

### 잘 되어 있는 것

먼저 바꾸지 말아야 할 부분을 짚어둔다.

- 큐 순서가 `ORDER BY id ASC`인데 `id`가 UUID v7이라 **시간순 FIFO**가 자연히 성립한다
- `SELECT ... FOR UPDATE SKIP LOCKED`로 워커 경합을 처리한다
- PostgreSQL advisory lock으로 중복 실행을 막는다
- 락 획득 실패를 FAILED가 아니라 **PENDING 되돌림**으로 처리해 재시도된다

APScheduler + PG 큐 + advisory lock 조합은 이 규모에 적정하다. **아키텍처를 갈아엎을 이유가 없다.**

### job_key가 네 곳에 흩어져 있다

| # | 위치 | 내용 | 빠뜨리면 |
|---|---|---|---|
| 1 | `scheduler/jobs/my_job.py` | `JOB_KEY` · `LOCK_KEY` 상수 | — |
| 2 | `scheduler/jobs/registry.py` | `_JOB_RUNNERS` dict 등록 | 실행 시 `unknown job_key` → FAILED |
| 3 | `scheduler/lock.py` | `LOCK_IDS`에 **정수를 직접 골라** 추가 | `ValueError: Unknown job_id for lock` |
| 4 | `scheduler_jobs` 테이블 | Admin UI 또는 마이그레이션 시드 | cron이 아예 안 걸림 |

`docs/scheduler.md`의 "새 job 추가" 절차가 그대로 이 네 단계다. 세 실패 모두 **런타임에, 조용히** 드러난다. Task가 20개가 되면 이 동기화 자체가 결함의 주된 원천이 된다.

### `job_key`가 PK다

```python
class SchedulerJob(Base):
    __tablename__ = "scheduler_jobs"
    job_key: Mapped[str] = mapped_column(String(100), primary_key=True)
```

**하나의 러너를 두 개 이상의 스케줄로 돌릴 수 없다.** "야간 전체 수집 03:00"과 "주간 증분 수집 12:00"을 같은 러너로 돌리려면 `collect_night`, `collect_noon`처럼 코드를 복제해야 하고, 그러면 위 표의 1~3번도 함께 복제된다.

지금 `scheduler_jobs`는 **Task 테이블이 아니라 job_key의 설정 행**이다.

---

## 2. 발견 목록

| # | 항목 | 위치 | 등급 |
|---|---|---|---|
| **S1** | `job_key` PK — 러너당 스케줄 1개 제한 | `models.py` | **높음** |
| **S2** | cron 표현력이 시·분뿐 | `models.py` · `runner.py` | **높음** |
| **S3** | Admin UI에서 cron을 바꿔도 반영 안 됨 | `runner.py` | **높음** |
| **S4** | advisory lock ID 매직 넘버 수동 관리 | `lock.py` | 중 |
| **S5** | 큐 ↔ 로그가 연결되지 않음 | `registry.py` · `_job_base.py` | 중 |
| **S6** | `payload`가 전달되지만 버려짐 | `registry.py` | 중 |
| **S7** | 즉시 실행 중복 방지 없음 | `admin_scheduler.py` | 중 |
| **S8** | 정의를 삭제해도 큐가 살아 있음 | `queue_processor.py` | 중 |
| **S9** | 코드↔DB 불일치를 화면에서 볼 수 없음 | `admin_scheduler.py` | 낮 |
| **S10** | 처리량 15초당 1건 | `queue_processor.py` | 낮 |

### S2. cron 표현력

`cron_hour`(0–23) · `cron_minute`(0–59)만 있다. **"매주 월요일", "10분마다", "평일만", "매월 1일"을 표현할 수 없다.** 수집기는 보통 시간 단위 이하 주기가 필요하다.

### S3. cron 핫 리로드 없음

```python
def main() -> None:
    engine = build_scheduler_engine()
    schedules = _load_enabled_job_schedules(engine)   # ← main() 에서 한 번만
```

`docs/scheduler.md`에도 "cron 변경은 **scheduler 컨테이너 재기동** 후 반영됩니다"라고 적혀 있다. 관리 화면에서 값을 바꿀 수 있는데 반영은 수동이라, 바꿔놓고 재기동을 잊으면 조용히 옛 스케줄로 돈다.

### S4. 락 ID 매직 넘버

```python
LOCK_IDS: dict[str, int] = {
    "sample_heartbeat": 20260831,
}
```

Task가 20개면 정수 20개를 사람이 관리한다. **충돌하면 서로 다른 job이 같은 락을 공유해 조용히 서로를 막는다.** 실패가 아니라 `lock_skipped` → PENDING 되돌림으로 나타나므로 원인 추적이 어렵다.

### S5. 큐 ↔ 로그 단절

```python
def run_registered_job(job_key, *, engine, payload=None) -> tuple[str, str | None]:
    ...
    return "succeeded", None      # log_id 를 버린다
```

`_run_job()` 안에서 만든 `log_id`가 호출자에게 돌아오지 않는다. `related_log_id`는 `clear-stuck-and-enqueue` 경로에서만 채워진다. **정상 실행에서는 "이 실행 요청의 로그"를 화면에서 추적할 수 없다.**

### S6. `payload` 무시

```python
def run_registered_job(job_key, *, engine, payload=None):
    _ = payload          # ← 버린다
```

큐 테이블에 컬럼이 있고 `SchedulerJobQueueRead`에도 노출되는데 쓰이지 않는다. `enqueue_run_now`는 payload를 받지도 않는다.

### S7. 즉시 실행 중복

`enqueue_run_now()`가 기존 PENDING을 확인하지 않는다. 버튼을 연타하면 그만큼 쌓이고, `queue_processor`는 **PROCESSING인 job_key만** 건너뛰므로 남은 PENDING이 전부 순차 실행된다.

### S8. 삭제된 정의의 잔여 큐

`scheduler_jobs`를 `is_delete=true`로 지워도 `queue_processor`는 `REGISTERED_JOB_KEYS`(코드 목록)만 확인한다. **정의가 삭제됐는지는 보지 않으므로** 남은 PENDING을 그대로 실행한다.

### S9. 코드 ↔ DB 불일치 비가시성

`GET /job-keys`는 코드 목록만 준다. 두 불일치 상태가 화면에 드러나지 않는다.

- 코드에 있는데 미등록 → cron이 안 걸림
- DB에 있는데 코드에서 사라짐(고아) → runner 로그에 warning만

---

## 3. 설계 1 — 코드 레지스트리 자동 등록

### 3-1. Job Key 테이블은 만들지 않는다

제안하신 흐름은 "Task 개발 → 자동으로 Job Key **테이블 등록 또는 목록 관리** → 스케줄링"이었다. 자동 등록은 맞고, **저장소는 코드로 두는 쪽을 권한다.**

`docker-compose.yml`을 보면 근거가 분명하다.

```yaml
backend:
  build:
    context: fastapi_backend      # ← 같은 컨텍스트
scheduler:
  build:
    context: fastapi_backend      # ← 같은 컨텍스트
  command: ["/app/.venv/bin/python", "-m", "scheduler.runner"]
```

**두 컨테이너가 동일한 이미지를 실행한다.** API가 아는 job_key 목록과 스케줄러가 아는 목록이 언제나 같다. 실제로 `admin_scheduler.py`가 이미 `scheduler.jobs.registry`를 직접 import하고 있다.

이 상황에서 DB 테이블을 두면 **코드가 원본, 테이블이 복제본**이 된다. 복제본에는 비용과 위험이 따른다.

| 문제 | 내용 |
|---|---|
| 동기화 주체 | 기동 시 sync가 필요하고, backend·scheduler 중 누가 쓸지 정해야 한다 |
| 롤링 배포 | sync가 "코드에 없는 키를 DELETE"하면, 구버전 컨테이너가 신규 키를 지운다 |
| FK 경직 | 스케줄 테이블에서 FK를 걸면 **job_key 이름을 바꾸는 순간 마이그레이션이 막힌다** |
| 이중 진실 | 테이블과 코드가 어긋났을 때 어느 쪽이 맞는지 판단 규칙이 또 필요하다 |

목록이 코드에만 있으면 고아 탐지는 API에서 한 줄이다.

```python
orphans = {s.job_key for s in schedules} - set(REGISTRY)
```

Task 20개 규모에서 이 계산은 즉시 끝난다. **테이블이 벌어주는 것이 없다.**

> **테이블이 필요해지는 조건** — job이 API와 **독립적으로 배포**될 때(플러그인 컨테이너, 외부 패키지)다. 그때는 코드가 여러 곳에 흩어져 어느 프로세스도 전체 목록을 모르므로, DB가 합류 지점이 된다. 현재 계획에는 해당하지 않는다.

### 3-2. 데코레이터 + 패키지 스캔

`registry.py`의 수동 dict와 `lock.py`의 `LOCK_IDS`를 함께 없앤다.

```python
# scheduler/jobs/_registry.py
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class JobSpec:
    key: str
    title: str
    runner: Callable
    concurrency_key: str | None = None
    description: str | None = None


_REGISTRY: dict[str, JobSpec] = {}


def job(key: str, *, title: str, concurrency_key: str | None = None,
        description: str | None = None):
    def deco(fn: Callable) -> Callable:
        if key in _REGISTRY:
            raise RuntimeError(
                f"duplicate job_key {key!r}: "
                f"{_REGISTRY[key].runner.__module__} vs {fn.__module__}"
            )
        _REGISTRY[key] = JobSpec(key, title, fn, concurrency_key, description)
        return fn
    return deco


_discovered = False


def discover(package: str = "scheduler.jobs") -> dict[str, JobSpec]:
    """패키지를 훑어 @job 데코레이터가 붙은 러너를 모두 등록한다."""
    global _discovered
    if _discovered:
        return _REGISTRY
    pkg = importlib.import_module(package)
    for m in pkgutil.walk_packages(pkg.__path__, prefix=f"{package}."):
        if any(p.startswith("_") for p in m.name.split(".")):
            continue
        importlib.import_module(m.name)
    _discovered = True
    return _REGISTRY
```

새 Task 하나 = **파일 하나**가 된다.

```python
# scheduler/jobs/collect_portal.py
from scheduler.jobs._registry import job


@job("collect_portal", title="포털 크롤링 수집", concurrency_key="collect")
def run(*, engine=None, payload=None, ctx=None) -> dict:
    from app.services.crawler import crawl      # 무거운 import 는 함수 안에서
    return crawl(payload or {})
```

### 3-3. 검증한 것

프로토타입으로 확인했다.

| 항목 | 결과 |
|---|---|
| 3개 job 자동 수집 | `registry.py` 수정 없이 전부 인식 |
| 중복 키 감지 | `duplicate job_key 'collect_portal': jobs.collect_portal vs jobs.dup` |
| 하위 패키지 | `walk_packages`로 `jobs/collect/nested.py`까지 인식 |
| payload 전달 | `run(payload={'mode':'full'})` → `{'ok': True, 'payload': {'mode': 'full'}}` |

**하위 패키지 지원이 중요하다.** Task가 20개면 `jobs/collect/`, `jobs/report/`처럼 묶고 싶어진다. `iter_modules`가 아니라 `walk_packages`를 써야 한다.

### 3-4. 대가 — API 컨테이너가 모든 job 모듈을 import한다

자동 탐색은 패키지 전체를 import한다. Task 20개 중 크롤러가 `playwright`를 모듈 최상단에서 import하면 **FastAPI 컨테이너 기동 시에도 그게 로드된다.**

다만 이건 자동 등록이 만드는 문제가 아니다. 지금도 `registry.py`가 `from scheduler.jobs import sample_heartbeat`로 eager import를 하고, API가 그 모듈을 import한다. 자동 탐색은 범위를 넓힐 뿐이다.

**규칙 하나로 해결된다 — job 모듈 최상단에는 표준 라이브러리와 `_registry`만 둔다.** 지키게 하려면 테스트로 막는다.

```python
# tests/scheduler/test_registry.py
import subprocess
import sys


def test_job_modules_stay_light():
    """job 패키지 import 만으로 무거운 의존성이 끌려오면 실패한다."""
    code = (
        "import sys, scheduler.jobs._registry as r; r.discover();"
        "heavy={'playwright','selenium','pandas','bs4','httpx'} & "
        "set(m.split('.')[0] for m in sys.modules);"
        "print(sorted(heavy))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]", (
        f"job 모듈이 최상단에서 무거운 패키지를 import 함: {out.stdout}"
    )


def test_no_duplicate_job_keys():
    from scheduler.jobs._registry import discover
    assert discover()          # 중복이 있으면 RuntimeError 로 실패한다
```

---

## 4. 설계 2 — Task / job_key 분리

### 4-1. 스키마

```python
class SchedulerSchedule(Base):
    """운영자가 만드는 스케줄. 하나의 job_key 위에 N개가 존재할 수 있다."""

    __tablename__ = "scheduler_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    job_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    cron_expression: Mapped[str] = mapped_column(String(120), nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="Asia/Seoul"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # 동시 실행 제어 단위. 비우면 JobSpec.concurrency_key → job_key 순으로 결정
    concurrency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_scheduler_schedules_enabled", "job_key", "enabled"),
    )
```

`job_key`에 **DB FK를 걸지 않는다.** 참조 대상이 코드의 레지스트리이지 테이블이 아니기 때문이다(3-1 참조). 검증은 API 계층에서 한다 — 지금 `create_scheduler_job`이 이미 그렇게 하고 있다.

큐와 로그에 계보를 잇는다.

```python
class SchedulerJobQueue(Base):
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(   # 수동 실행이면 NULL
        PG_UUID(as_uuid=True),
        ForeignKey("scheduler_schedules.id"),
        nullable=True, index=True,
    )
    # job_key 는 유지 — 스케줄이 삭제돼도 무엇을 돌렸는지 남는다

class SchedulerJobLog(Base):
    queue_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("scheduler_job_queue.id"),
        nullable=True, index=True,
    )
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("scheduler_schedules.id"),
        nullable=True, index=True,
    )
```

`scheduler_job_log.job_id`(문자열 job_key)는 유지한다. 스케줄이 지워져도 이력은 남아야 한다.

> `job_id`라는 이름이 UUID처럼 읽혀 혼동을 준다. 같은 마이그레이션에서 `job_key`로 개명하는 것을 권한다. 참조처가 `_job_base.py`, `admin_scheduler.py`, 프론트 3곳뿐이다.

### 4-2. `cron_expression` — S2 해결

APScheduler 3.11.3의 `CronTrigger.from_crontab()`을 쓴다.

```python
trigger = CronTrigger.from_crontab(row["cron_expression"], timezone=row["timezone"])
```

표준 5필드(분 시 일 월 요일)를 지원한다. **초 단위와 `@daily` 류 매크로는 지원하지 않는다.**

생성·수정 API에서 같은 함수로 검증해, 잘못된 표현식이 DB에 들어가 runner를 조용히 망가뜨리는 일을 막는다.

```python
@field_validator("cron_expression")
@classmethod
def _validate_cron(cls, v: str) -> str:
    try:
        CronTrigger.from_crontab(v)
    except ValueError as e:
        raise ValueError(f"invalid cron expression: {e}") from e
    return v
```

### 4-3. advisory lock — S4 해결

`LOCK_IDS`를 없애고 키에서 파생시킨다.

```python
APP_LOCK_NAMESPACE = 4207   # 이 애플리케이션 고유값. 한 번 정하면 바뀌지 않는다

acquired = db.execute(
    text("SELECT pg_try_advisory_lock(:ns, hashtext(:key))"),
    {"ns": APP_LOCK_NAMESPACE, "key": lock_key},
).scalar()
```

`pg_try_advisory_lock(int4, int4)` 2인자 형태를 쓰고 첫 인자를 애플리케이션 네임스페이스로 고정한다. 같은 DB의 다른 애플리케이션과 충돌하지 않고, **관리 대상이 사라진다.**

락 키 결정 순서:

```python
lock_key = schedule.concurrency_key or spec.concurrency_key or spec.key
```

기본값이 `job_key`이므로 **같은 러너의 서로 다른 스케줄은 서로를 배제한다** — 대개 이게 원하는 동작이다. `JobSpec.concurrency_key="collect"`처럼 지정하면 `collect_portal`과 `collect_openapi`가 락을 공유해 DB에 동시에 붙지 않게 할 수도 있다.

### 4-4. cron 핫 리로드 — S3 해결

runner에 리로드 틱을 하나 더 단다.

```python
_current_fingerprint: str | None = None


def _fingerprint(rows) -> str:
    payload = [
        (str(r["id"]), r["job_key"], r["cron_expression"], r["timezone"], r["enabled"])
        for r in rows
    ]
    return hashlib.sha256(repr(sorted(payload)).encode()).hexdigest()


def _reload_schedules(engine) -> None:
    global _current_fingerprint
    rows = _load_enabled_schedules(engine)
    fp = _fingerprint(rows)
    if fp == _current_fingerprint:
        return

    known = {f"sched:{r['id']}" for r in rows}
    for j in scheduler.get_jobs():
        if j.id.startswith("sched:") and j.id not in known:
            scheduler.remove_job(j.id)

    for r in rows:
        scheduler.add_job(
            _enqueue_scheduled_job,
            CronTrigger.from_crontab(r["cron_expression"], timezone=r["timezone"]),
            kwargs={"schedule_id": r["id"], "job_key": r["job_key"], "engine": engine},
            id=f"sched:{r['id']}",
            name=f"{r['name']} ({r['job_key']})",
            max_instances=1,
            misfire_grace_time=600,
            replace_existing=True,
        )
    _current_fingerprint = fp
    logger.info("[RUNNER] schedules reloaded: %d active", len(rows))
```

`IntervalTrigger(seconds=60)`으로 등록한다.

**APScheduler job id를 `job_key`가 아니라 `sched:<uuid>`로 잡는 것이 핵심이다.** 현재 `runner.py`는 `id=job_key`를 쓰는데, 같은 job_key의 스케줄이 여러 개가 되면 서로를 덮어쓴다.

지문 비교로 변경이 없으면 재등록하지 않는다. `docs/scheduler.md`의 "재기동 후 반영" 문구도 함께 지운다.

### 4-5. 큐 ↔ 로그 계보 — S5 · S6 해결

`run_registered_job()`의 반환값에 `log_id`를 넣고 payload를 러너에 전달한다.

```python
@dataclass(frozen=True)
class JobOutcome:
    outcome: str                 # succeeded | failed | lock_skipped
    log_id: uuid.UUID | None
    error_message: str | None


def run_registered_job(
    job_key: str, *, engine, lock_key: str, payload: dict | None = None,
    queue_id: uuid.UUID | None = None, schedule_id: uuid.UUID | None = None,
) -> JobOutcome:
    ...
```

`_job_base.run_job()`은 `queue_id`·`schedule_id`를 받아 `_insert_job_log()`에 함께 넣고, `JobResult`에 `log_id`를 실어 돌려준다. `queue_processor`는 완료 처리 시 `related_log_id`를 채운다.

러너 시그니처는 `(*, engine, payload, ctx)`로 통일한다. payload가 필요 없는 job은 `**_`로 흘려보내면 된다.

### 4-6. 중복 · 고아 처리 — S7 · S8 해결

**S7** — `enqueue_run_now`에서 같은 대상의 미완료 큐를 먼저 확인한다.

```python
dup = await session.scalar(
    select(SchedulerJobQueue.id).where(
        SchedulerJobQueue.schedule_id == schedule_id,
        SchedulerJobQueue.status.in_((QUEUE_STATUS_PENDING, QUEUE_STATUS_PROCESSING)),
        SchedulerJobQueue.is_delete == False,  # noqa: E712
    ).limit(1)
)
if dup is not None:
    raise ConflictError("이미 대기 중이거나 실행 중인 요청이 있습니다")
```

**S8** — `queue_processor`가 실행 직전 스케줄 유효성을 확인한다. `schedule_id`가 있는데 그 스케줄이 삭제·비활성이면 CANCELLED로 종료한다. `schedule_id`가 NULL인 수동 실행은 job_key 등록 여부만 본다.

---

## 5. API · UI

### API

| 변경 | 엔드포인트 |
|---|---|
| 경로 변경 | `/admin/scheduler/jobs` → `/admin/scheduler/schedules` |
| 식별자 변경 | `{job_key}` → `{schedule_id}` (UUID) |
| 본문 변경 | `cron_hour`·`cron_minute` → `cron_expression`, `name`·`payload`·`concurrency_key` 추가 |
| 대체 | `GET /job-keys` → `GET /registry` (**S9**) |
| 유지 | `/queue`, `/queue/{id}/cancel`, `/job-logs`, `/job-logs/{id}/clear-stuck-and-enqueue` |

`GET /admin/scheduler/registry` 응답 예:

```json
[
  { "job_key": "collect_portal",   "title": "포털 크롤링 수집",  "registered": true,  "schedule_count": 2 },
  { "job_key": "collect_openapi",  "title": "공공 Open API 수집", "registered": true,  "schedule_count": 1 },
  { "job_key": "sample_heartbeat", "title": "샘플 하트비트",     "registered": true,  "schedule_count": 0 },
  { "job_key": "legacy_import",    "title": null,               "registered": false, "schedule_count": 1 }
]
```

`registered: false`가 **고아 스케줄**이다. 코드에서 사라졌는데 DB에 스케줄이 남은 상태로, 화면에 경고로 노출한다.

권한은 기존 `scheduler:read` / `scheduler:manage`를 그대로 쓴다. 변경 없음.

### UI

- **스케줄 목록** — job_key가 아니라 `name` 기준. job_key는 보조 표시
- **생성 폼** — job_key는 `GET /registry`의 `registered: true` 목록에서 선택, cron은 텍스트 입력 + 다음 5회 실행 시각 미리보기
- **고아 경고** — `registered: false`인 스케줄에 배지
- **실행 이력** — 큐 행에서 `related_log_id`로 로그 상세 링크 (S5의 결과물)

상태 배지는 이미 `bg-warning-soft` 계열 토큰으로 정리돼 있어 그대로 쓰면 된다.

---

## 6. 마이그레이션 순서

기존 `scheduler_jobs` 행이 `sample_heartbeat` 하나뿐이라 데이터 이관 부담이 없다.

1. **레지스트리 먼저** — `_registry.py` 신설, `sample_heartbeat`에 `@job` 부착, `registry.py`·`lock.py` 정리. 이 단계만으로도 S4가 해결되고 스키마는 그대로다
2. `app/models.py` — `SchedulerSchedule` 추가, 큐·로그에 컬럼 추가
3. revision 생성 — **직접 실행**
   ```bash
   cd fastapi_backend && uv run alembic revision --autogenerate -m "split schedule from job_key"
   ```
4. 생성된 revision을 열어 확인·보완
   - `scheduler_schedules` 생성
   - 기존 `scheduler_jobs` 행을 `cron_expression = '{cron_minute} {cron_hour} * * *'` 형태로 INSERT
   - `scheduler_jobs` DROP (또는 한 릴리스 보존 후 제거)
   - `scheduler_job_log.job_id` → `job_key` 개명
5. 적용
   ```bash
   make docker-migrate-db
   ```
6. 코드 반영 — `_job_base.py`, `runner.py`, `queue_processor.py`, `admin_scheduler.py`
7. 프론트 반영 — `app/(protected)/admin/scheduler/`, `app/api/admin/scheduler/`
8. `make test-backend` · `make typecheck-frontend`
9. `docs/scheduler.md` 갱신

> Alembic revision 파일은 반드시 직접 CLI로 생성하십시오. 여기 적은 것은 그 파일이 담아야 할 내용입니다.

**1단계와 2~9단계를 나눠 커밋하는 것을 권한다.** 1단계는 스키마를 건드리지 않아 되돌리기 쉽고, 그 자체로 가치가 있다.

---

## 7. 검토한 다른 방안

| 방안 | 판단 |
|---|---|
| **Job Key 테이블 + FK** | 코드가 원본, 테이블이 복제본이 된다. 동기화·롤링 배포·FK 경직 문제를 얻고 벌어주는 것이 없다 (3-1) |
| **DB에 import 경로 저장** (`"pkg.mod:func"`) | **하지 말 것.** DB 값으로 임의 모듈을 import하면 **DB 쓰기 권한이 코드 실행 권한이 된다** |
| **`importlib.metadata` entry points** | job을 별도 패키지로 배포할 때의 방식. 단일 저장소 20개 Task에는 과하다 |
| **APScheduler `SQLAlchemyJobStore`** | 스케줄을 APScheduler가 직접 저장한다. 함수 참조를 pickle하므로 리팩터링에 깨지고, 지금의 큐·이력 테이블과 역할이 겹친다 |
| **Celery / Procrastinate로 교체** | 현 구조는 이 규모에 적정하다. 바꿀 이유가 없다 (아래 참고) |

### 태스크 시스템 중복에 대한 메모

`collector-storage-service-architecture.md`에서는 수집+저장 서비스에 **Procrastinate**를 권했다. 그 서비스가 별도 프로세스로 뜨면 한 플랫폼에 태스크 시스템이 둘이 된다.

지금 결정할 일은 아니지만, **수집 서비스를 이 템플릿 위에 올릴지 별도로 세울지**에 따라 정리가 필요하다. 이 템플릿 위에 올린다면 Procrastinate 대신 여기 스케줄러를 쓰는 편이 일관된다.

---

## 8. 규모에 맞춰 하지 말 것

Task 10~20개, 활성 스케줄 10개 규모에서 다음은 과잉이다.

- **job_key 테이블과 FK** — 7장
- **job 플러그인 로딩** (외부 패키지, entry points)
- **워커 다중화** — 현재 15초당 1건이면 시간당 240건이다. 스케줄 10개에 충분하다 (S10을 낮음으로 둔 이유)
- **payload JSON 스키마 프레임워크** — 필요하면 `JobSpec`에 Pydantic 모델 하나를 달면 된다

---

## 9. 결정 필요 사항

| # | 항목 | 선택지 |
|---|---|---|
| 1 | **적용 범위** | 1단계(레지스트리)만 / 전체 |
| 2 | 동시 실행 정책 | 같은 job_key의 서로 다른 스케줄이 동시에 돌아도 되는가 (기본: 불가) |
| 3 | `scheduler_jobs` 처리 | 즉시 DROP / 한 릴리스 보존 |
| 4 | `job_id` → `job_key` 개명 | 같이 할 것인가 |
| 5 | 큐 보관 기간 | 무기한 / N일 후 정리 (감사 로그는 무기한으로 이미 결정) |
| 6 | 수집 서비스 태스크 시스템 | 이 스케줄러 사용 / Procrastinate 별도 |

---

# 체크리스트

### 1단계 — 레지스트리 (스키마 변경 없음)

- [ ] `scheduler/jobs/_registry.py` — `JobSpec` · `@job` · `discover()`
- [ ] `sample_heartbeat.py` — `@job` 데코레이터로 전환
- [ ] `registry.py` — 수동 dict 제거, `discover()` 기반으로 교체
- [ ] `lock.py` — `LOCK_IDS` 제거, `pg_try_advisory_lock(ns, hashtext(key))`로 교체
- [ ] `tests/scheduler/test_registry.py` — 중복 키 · 무거운 import 가드
- [ ] `make test-backend`

### 2단계 — Task 분리

- [ ] `SchedulerSchedule` 모델 추가
- [ ] `SchedulerJobQueue.schedule_id` · `SchedulerJobLog.queue_id`·`schedule_id` 추가
- [ ] Alembic revision 직접 생성 후 시드·개명 보완
- [ ] `_job_base.py` — `queue_id`·`schedule_id` 기록, `log_id` 반환
- [ ] `registry.py` — `JobOutcome` 반환, payload 전달
- [ ] `runner.py` — `cron_expression`, `sched:<uuid>` job id, 60초 핫 리로드
- [ ] `queue_processor.py` — 실행 직전 스케줄 유효성 검증, `related_log_id` 기록
- [ ] `admin_scheduler.py` — 경로·스키마 변경, cron 검증, 중복 enqueue 409, `GET /registry`
- [ ] 프론트 — 스케줄 목록·폼·고아 배지·로그 링크
- [ ] `make test-backend` · `make typecheck-frontend`
- [ ] `docs/scheduler.md` 갱신 — "새 job 추가"가 **4단계 → 1단계**로 줄어든다

---

## 관련 문서

- `docs/scheduler.md` — 현행 스케줄러 문서
- `collector-storage-service-architecture.md` — 수집+저장 서비스 아키텍처
- `admin-web-auth-design.md` — 권한 체계 (`scheduler:read` · `scheduler:manage`)
