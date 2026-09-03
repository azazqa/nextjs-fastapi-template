# 우선 조치 항목 — C1 · C3 · H1 · H3

> 작성일: 2026-09-03
> 대상: `azazqa/nextjs-fastapi-template` (commit `56fd00f`)
> 범위: 코드 검토에서 도출된 4개 항목의 상세 분석과 수정안

---

## 개요

| # | 항목 | 위치 | 성격 |
|---|---|---|---|
| **C1** | DB 비밀번호 공개 저장소 노출 | `docker-compose.yml` | 시크릿 관리 |
| **C3** | 레이트리밋 경쟁 상태 | `app/services/login_rate_limit.py` | 동시성 결함 |
| **H1** | `/auth/jwt/logout` 경로 중복 등록 | `app/main.py`, `routes/auth_jwt.py`, `routes/auth_refresh.py` | 라우팅 결함 |
| **H3** | 인메모리 저장소 무한 증가 | `app/services/login_rate_limit.py` | 자원 고갈 |

C3과 H3은 같은 파일이므로 **한 번의 교체로 함께 해결**한다.

### 공통 성격

네 건 모두 **평상시에는 드러나지 않는다.**

- C1 — 저장소를 열어보기 전까지 모른다
- C3 — 순차 요청(테스트 포함)에서는 정상 동작한다
- H1 — JWT 전략에서 두 핸들러의 겉보기 결과가 비슷해 묻힌다
- H3 — 정상 사용자만 있으면 증가가 느리다

**전부 공격 상황이나 운영 사고 시점에 처음 드러난다.** 그래서 우선순위를 높게 잡았다.

---

# C1. DB 비밀번호가 공개 저장소 히스토리에 기록됨

## 현황

`docker-compose.yml` **4곳**에 동일한 값이 평문으로 있다.

| 서비스 | 노출 형태 |
|---|---|
| `backend` | `DATABASE_URL=postgresql+asyncpg://postgres:439e19e7...@db:5432/app` |
| `db` | `POSTGRES_PASSWORD: 439e19e7...` |
| `db_test` | `POSTGRES_PASSWORD: 439e19e7...` |
| `scheduler` | `DATABASE_URL=postgresql+asyncpg://postgres:439e19e7...@db:5432/app` |

`.gitignore`에 `.env`가 등록되어 있어 실제 시크릿 파일은 보호되지만, **compose 파일에 직접 쓴 값이 그 보호를 우회했다.**

## 영향

저장소가 공개이므로 이 값은 **이미 유출된 것으로 간주해야 한다.** 파일을 수정해도 git 히스토리에는 남고, GitHub는 push된 커밋을 캐시하므로 force-push 이후에도 일정 기간 dangling commit으로 접근할 수 있다.

템플릿이라는 성격 때문에 영향이 증폭된다. **이 저장소에서 파생된 모든 프로젝트가 같은 비밀번호를 공유**하게 되고, 개발자가 바꿀 이유를 느끼지 못한다.

## 조치

### 1단계 — 비밀번호 교체 (최우선)

히스토리 정리보다 먼저 한다. 이미 노출된 값이므로 **교체하지 않으면 다른 조치가 의미 없다.**

```sql
ALTER USER postgres WITH PASSWORD '<새 비밀번호>';
```

사용 중인 모든 환경(로컬·개발·스테이징)에 적용한다.

### 2단계 — compose를 변수 참조로 변경

```yaml
services:
  backend:
    env_file:
      - ./fastapi_backend/.env
    environment:
      - TZ=${TZ:-Asia/Seoul}
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
      - OPENAPI_OUTPUT_FILE=./shared-data/openapi.json

  db:
    image: postgres:18.6-trixie
    environment:
      TZ: ${TZ:-Asia/Seoul}
      POSTGRES_USER: ${POSTGRES_USER:?POSTGRES_USER is required}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}
      POSTGRES_DB: ${POSTGRES_DB:?POSTGRES_DB is required}

  db_test:
    image: postgres:18.6-trixie
    environment:
      TZ: ${TZ:-Asia/Seoul}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_TEST_PASSWORD:-test}
      POSTGRES_DB: ${POSTGRES_DB}_test          # 운영 DB와 이름 분리

  scheduler:
    env_file:
      - ./fastapi_backend/.env                  # backend와 환경 일치
    environment:
      - TZ=${TZ:-Asia/Seoul}
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
```

**`:?` 구문이 핵심이다.** 값이 없으면 `docker compose up`이 실패한다. 기본값을 주면 아무도 바꾸지 않는다.

> **주의 — `env_file`과 `${...}`는 다른 파일을 본다.**
> compose 파일 안의 `${VAR}` 치환은 **compose 파일과 같은 디렉터리의 `.env`**(프로젝트 루트)에서 읽는다. `env_file:`로 지정한 `./fastapi_backend/.env`는 컨테이너 안으로 주입될 뿐 치환에는 쓰이지 않는다.
> 따라서 **루트에 `.env`를 새로 만들어야 한다.** 루트 `.gitignore`의 `.env` 패턴이 모든 디렉터리의 `.env`를 이미 제외하므로 추가 설정은 필요 없다.

### 3단계 — 루트 `.env.example` 추가

```bash
# .env.example  (프로젝트 루트 — docker compose 변수 치환용)
COMPOSE_PROJECT_NAME=__PROJECT_NAME__
TZ=Asia/Seoul

POSTGRES_USER=postgres
POSTGRES_PASSWORD=__POSTGRES_PASSWORD__
POSTGRES_DB=app
POSTGRES_TEST_PASSWORD=test
```

`COMPOSE_PROJECT_NAME`을 함께 두면 같은 머신에서 여러 파생 프로젝트를 돌릴 때 볼륨·네트워크 이름 충돌을 막을 수 있다.

### 4단계 — `make init`으로 시크릿 자동 생성

템플릿이라면 **초기화 명령이 비밀번호를 만들어야 한다.** 사람이 손으로 채우게 하면 예제 값이 그대로 운영에 간다.

```makefile
.PHONY: init
init: ## .env 생성 및 시크릿 자동 발급
	@test -f .env && { echo ".env가 이미 있습니다. 건너뜁니다."; exit 0; } || true
	@sed -e "s|__POSTGRES_PASSWORD__|$$(openssl rand -hex 32)|" \
	     -e "s|__PROJECT_NAME__|$$(basename $$(pwd))|" \
	     .env.example > .env
	@sed -e "s|your_access_secret_key|$$(openssl rand -hex 32)|" \
	     -e "s|your_refresh_secret_key|$$(openssl rand -hex 32)|" \
	     -e "s|your_reset_password_secret_key|$$(openssl rand -hex 32)|" \
	     -e "s|your_verification_secret_key|$$(openssl rand -hex 32)|" \
	     $(BACKEND_DIR)/.env.example > $(BACKEND_DIR)/.env
	@echo "생성 완료: .env, $(BACKEND_DIR)/.env"
```

`.env.example`의 시크릿 자리표시자(`your_access_secret_key` 등)도 함께 치환된다. **현재는 이 값들이 예제 그대로 남을 위험이 있다.**

### 5단계 — 재발 방지 훅

`.pre-commit-config.yaml`에 이미 `detect-private-key`가 있으나 **개인키만 잡고 비밀번호는 잡지 못한다.**

```yaml
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.28.0
    hooks:
      - id: gitleaks
```

### 히스토리 정리에 대해

`git filter-repo`나 BFG로 과거 커밋에서 값을 지울 수 있으나 **이미 노출된 값이므로 실익이 적다.** 협업자 전원이 새로 clone해야 하는 비용도 크다.

**교체가 완료되었다면 히스토리는 그대로 두어도 무방하다.** 다만 저장소를 비공개로 전환할 계획이 있다면 그때 함께 정리하는 편이 낫다.

## 검증

```bash
# 하드코딩된 비밀번호가 남아 있지 않은지
grep -rn "439e19e7" . --exclude-dir=.git

# 변수 치환이 정상 동작하는지 (실제 실행 없이 최종 설정 출력)
docker compose config

# .env 없이 실행 시 실패하는지
mv .env .env.bak && docker compose config ; mv .env.bak .env
```

마지막 명령은 **오류가 나야 정상**이다.

---

# C3 + H3. 로그인 레이트리밋 — 경쟁 상태와 무한 증가

두 결함이 같은 파일에 있으므로 **파일 전체를 교체**하는 방식으로 함께 해결한다.

## C3. Redis 경로가 원자적이지 않다

### 현황

`app/services/login_rate_limit.py:127-133`

```python
async def _record_login_failure_redis(redis: Redis, login_id: str) -> None:
    state = await _load_redis_state(redis, key)       # ① GET
    _record_failure(state, now)                       # ② 파이썬에서 수정
    await _save_redis_state(redis, key, state, now)   # ③ SET
```

### 영향

**GET → 수정 → SET 사이에 다른 요청이 끼어들 수 있다.**

동시 요청 5개가 들어오면 다섯 모두 `failures=[]`를 읽고, 각자 실패 1건씩 추가한 뒤 서로를 덮어쓴다. 최종 저장값은 `failures=[t]` **1건**이다. 임계값 5에 도달하지 못한다.

```
요청 A: GET → [] ──── 수정 → [a] ──── SET [a]
요청 B: GET → []    ── 수정 → [b] ──── SET [b]   ← A의 기록 소실
요청 C: GET → []      ─ 수정 → [c] ── SET [c]   ← B의 기록 소실
```

브루트포스는 **정의상 병렬 요청**이다. 이 레이트리밋은 순차 요청(현재 테스트 포함)에서는 정상 동작하고, **정확히 방어해야 할 병렬 공격에서만 무력화된다.** Gunicorn 워커가 2개 이상이면 더 심해진다.

Redis를 도입한 목적이 "멀티 워커 간 상태 공유"였는데, 공유는 되지만 **갱신이 안전하지 않다.**

## H3. 인메모리 폴백이 무한히 증가한다

### 현황

`app/services/login_rate_limit.py:32`

```python
_store: dict[str, _AttemptState] = {}
```

`_prune_old_failures()`는 `state.failures` **리스트 내부만** 정리하고 dict 키는 남긴다. 키가 삭제되는 유일한 경로는 로그인 성공 시의 `_clear_login_failures_memory()`뿐이다.

### 영향

**존재하지 않는 계정으로 시도해도 항목이 생성되고, 그 항목은 영원히 남는다.**

```
POST /auth/jwt/login  username=a1@x.com  → _store["a1@x.com"] 생성 (영구)
POST /auth/jwt/login  username=a2@x.com  → _store["a2@x.com"] 생성 (영구)
...
```

무작위 이메일 수백만 건을 던지면 프로세스 메모리가 고갈된다. 인증조차 필요 없는 공격이다.

`REDIS_URL`은 **선택값**이므로 미설정 시 이 경로가 기본 동작이다. `.env.example`과 문서 모두 "unset → in-memory fallback"으로 안내하고 있어 운영에서 이 상태로 갈 여지가 있다.

## 통합 수정안

### 설계 방침

| 항목 | 방침 |
|---|---|
| Redis | `INCR` 기반 **원자 연산**으로 전환 |
| 잠금 | 별도 키 + TTL — 만료를 Redis에 위임 |
| 인메모리 | **상한이 있는 LRU**로 교체, 지연 만료 |
| 위치 | 인메모리는 **테스트·단일 워커 개발용**으로 명시 |

핵심은 **Redis에 계산을 맡기는 것**이다. 파이썬에서 상태를 읽어와 수정하는 구조 자체가 경쟁 상태의 원인이므로, `INCR`과 TTL로 Redis가 직접 처리하게 한다.

### 교체 코드

`app/services/login_rate_limit.py` 전체를 아래로 대체한다.

```python
"""로그인 레이트리밋.

Redis가 설정되면 원자적 INCR 기반으로 동작한다.
미설정 시 상한이 있는 인메모리 폴백을 쓰지만, 이는 테스트·단일 워커 개발용이며
운영에서는 REDIS_URL 설정을 전제한다.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass

from redis.asyncio import Redis

from app.config import settings
from app.exceptions import RateLimitError
from app.redis import get_redis

_KEY_PREFIX = "login_rate:"

# 인메모리 폴백 상한 — 무제한 증가 방지 (H3)
_MAX_TRACKED_IDS = 10_000


def _normalize_login_id(login_id: str) -> str:
    return login_id.strip().lower()


def _locked_error(retry_after: int) -> RateLimitError:
    return RateLimitError(
        f"Too many failed login attempts. Try again in {retry_after} seconds.",
        retry_after=retry_after,
    )


# ---------------------------------------------------------------------------
# Redis — 원자적 구현 (C3)
# ---------------------------------------------------------------------------


def _fail_key(key: str) -> str:
    return f"{_KEY_PREFIX}fail:{key}"


def _lock_key(key: str) -> str:
    return f"{_KEY_PREFIX}lock:{key}"


async def _assert_login_allowed_redis(redis: Redis, key: str) -> None:
    ttl = await redis.ttl(_lock_key(key))
    if ttl > 0:
        raise _locked_error(ttl)


async def _record_login_failure_redis(redis: Redis, key: str) -> None:
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(_fail_key(key))
        # nx=True: TTL이 없을 때만 설정 → 실패마다 윈도우가 연장되지 않는다
        pipe.expire(_fail_key(key), settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS, nx=True)
        failures, _ = await pipe.execute()

    if failures >= settings.LOGIN_RATE_LIMIT_MAX_FAILURES:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.set(_lock_key(key), "1", ex=settings.LOGIN_RATE_LIMIT_LOCKOUT_SECONDS)
            pipe.delete(_fail_key(key))
            await pipe.execute()


async def _clear_login_failures_redis(redis: Redis, key: str) -> None:
    await redis.delete(_fail_key(key), _lock_key(key))


# ---------------------------------------------------------------------------
# 인메모리 폴백 — 상한 있음 (H3)
# ---------------------------------------------------------------------------


@dataclass
class _AttemptState:
    failures: int = 0
    window_expires_at: float = 0.0
    locked_until: float = 0.0


_store: "OrderedDict[str, _AttemptState]" = OrderedDict()


def _get_state(key: str, now: float) -> _AttemptState:
    state = _store.get(key)
    if state is None:
        state = _AttemptState()
        _store[key] = state
    else:
        _store.move_to_end(key)  # LRU 갱신

    # 지연 만료: 윈도우가 지났으면 실패 횟수를 초기화한다
    if state.window_expires_at and state.window_expires_at <= now:
        state.failures = 0
        state.window_expires_at = 0.0
    return state


def _enforce_capacity() -> None:
    """가장 오래 접근되지 않은 항목부터 제거해 상한을 지킨다."""
    while len(_store) > _MAX_TRACKED_IDS:
        _store.popitem(last=False)


def _assert_login_allowed_memory(key: str) -> None:
    now = time.monotonic()
    state = _get_state(key, now)
    if state.locked_until > now:
        raise _locked_error(max(1, int(state.locked_until - now)))


def _record_login_failure_memory(key: str) -> None:
    now = time.monotonic()
    state = _get_state(key, now)

    if state.failures == 0:
        state.window_expires_at = now + settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    state.failures += 1

    if state.failures >= settings.LOGIN_RATE_LIMIT_MAX_FAILURES:
        state.locked_until = now + settings.LOGIN_RATE_LIMIT_LOCKOUT_SECONDS
        state.failures = 0
        state.window_expires_at = 0.0

    _enforce_capacity()


def _clear_login_failures_memory(key: str) -> None:
    _store.pop(key, None)


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


async def assert_login_allowed(login_id: str) -> None:
    key = _normalize_login_id(login_id)
    if not key:
        return
    redis = get_redis()
    if redis is None:
        _assert_login_allowed_memory(key)
        return
    await _assert_login_allowed_redis(redis, key)


async def record_login_failure(login_id: str) -> None:
    key = _normalize_login_id(login_id)
    if not key:
        return
    redis = get_redis()
    if redis is None:
        _record_login_failure_memory(key)
        return
    await _record_login_failure_redis(redis, key)


async def clear_login_failures(login_id: str) -> None:
    key = _normalize_login_id(login_id)
    if not key:
        return
    redis = get_redis()
    if redis is None:
        _clear_login_failures_memory(key)
        return
    await _clear_login_failures_redis(redis, key)
```

### 호환성

- **공개 API 시그니처가 동일**하다. `auth_jwt.py` 호출부는 수정할 필요가 없다
- 오류 메시지와 `retry_after`가 그대로라 기존 테스트 2개가 통과한다
- `expire(..., nx=True)`는 **Redis 7.0+ / redis-py 4.4+** 필요. 현재 `redis:8.2-alpine`, `redis>=5.2.0`이므로 충족한다

### 남는 제약을 명시할 것

인메모리 폴백은 상한이 생겼지만 **여전히 보안 통제로는 부족하다.** LRU 특성상 공격자가 1만 개 넘는 아이디를 순환시키면 잠긴 정상 계정의 항목이 밀려날 수 있다.

**운영에서는 Redis를 필수로 만드는 것이 옳다.**

```python
# app/config.py
    REQUIRE_REDIS: bool = False
```

```python
# app/main.py — lifespan
if settings.REQUIRE_REDIS and not settings.REDIS_URL:
    raise RuntimeError("REQUIRE_REDIS=true인데 REDIS_URL이 설정되지 않았습니다")
```

운영 `.env`에 `REQUIRE_REDIS=true`를 두면, 폴백으로 **조용히 열화되는 대신 명시적으로 실패**한다.

## 회귀 방지 테스트

병렬 실패를 재현하는 테스트를 추가한다. **현재 코드에서는 실패하고, 수정 후에는 통과한다.**

```python
import asyncio
import pytest


@pytest.mark.asyncio
async def test_login_rate_limit_holds_under_concurrent_failures(test_client):
    """동시 실패 요청에서도 잠금이 발동해야 한다 (C3 회귀 방지)."""
    email = "concurrent@example.com"

    await asyncio.gather(*[
        test_client.post(
            "/auth/jwt/login",
            data={"username": email, "password": "WrongPassword1!"},
        )
        for _ in range(5)
    ])

    locked = await test_client.post(
        "/auth/jwt/login",
        data={"username": email, "password": "WrongPassword1!"},
    )
    assert locked.status_code == 429


def test_memory_store_is_bounded():
    """인메모리 저장소가 상한을 넘지 않아야 한다 (H3 회귀 방지)."""
    from app.services import login_rate_limit as rl

    rl._store.clear()
    for i in range(rl._MAX_TRACKED_IDS + 500):
        rl._record_login_failure_memory(f"user{i}@example.com")

    assert len(rl._store) <= rl._MAX_TRACKED_IDS
```

> 동시성 테스트는 Redis 경로에서 의미가 크다. `REDIS_URL`을 설정한 통합 테스트 환경에서도 돌려볼 것을 권한다.

---

# H1. `/auth/jwt/logout` 경로 중복 등록

## 현황

두 파일이 **같은 경로 + 같은 메서드**를 등록한다.

| 파일 | 라우터 prefix | 데코레이터 | 최종 경로 |
|---|---|---|---|
| `routes/auth_refresh.py:128` | `/auth` | `@router.post("/jwt/logout")` | `POST /auth/jwt/logout` |
| `routes/auth_jwt.py:43` | `/auth/jwt` | `@router.post("/logout")` | `POST /auth/jwt/logout` |

`app/main.py`의 등록 순서다.

```python
app.include_router(auth_refresh_router, prefix=f"/{AUTH_URL_PATH}", ...)      # 먼저
app.include_router(auth_jwt_router,     prefix=f"/{AUTH_URL_PATH}/jwt", ...)  # 나중
```

## 영향

**라우팅과 문서가 서로 다른 핸들러를 가리킨다.**

| 관점 | 실제 |
|---|---|
| **요청 처리** | 먼저 등록된 `auth_refresh.logout_refresh_token()` — 리프레시 토큰 폐기, `200 {"detail": "Logged out"}` |
| **OpenAPI 스펙** | 나중 것이 dict를 덮어써 `auth_jwt`의 `auth-logout` — Bearer 필요, `204 No Content` |

프론트엔드 클라이언트는 OpenAPI에서 생성되므로, **클라이언트가 기대하는 계약과 서버 동작이 어긋난다.**

`auth_jwt.py`의 `logout`은 **도달 불가능한 죽은 코드**다. 지금 당장 기능 사고로 이어지진 않지만 다음 조건에서 즉시 문제가 된다.

- 누군가 `main.py`의 `include_router` 순서를 바꾸면 → **로그아웃이 리프레시 토큰을 폐기하지 않는 no-op이 된다**
- 인증 전략을 교체하면 → 어느 쪽이 실행되는지 추적이 어려워진다

> **참고 — `auth_backend.logout()`은 예외를 내지 않는다.**
> fastapi-users 15.0.5의 `AuthenticationBackend.logout()`은 `StrategyDestroyNotSupportedError`와 `TransportLogoutNotSupportedError`를 모두 잡아 `204`를 반환한다(`authentication/backend.py:48-61`). JWT + Bearer 조합에서는 **아무 일도 하지 않고 204만 돌려준다.**
> 즉 `auth_jwt.logout`이 이겼다면 리프레시 토큰이 폐기되지 않은 채 로그아웃 성공으로 보였을 것이다.

## H1 관련 추가 발견 — 로그아웃이 쿠키를 지우지 않는다

```python
@router.post("/jwt/logout")
async def logout_refresh_token(request, db):
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        await revoke_refresh_token(db, refresh_token)
    return {"detail": "Logged out"}   # ← Set-Cookie 없음
```

DB에서는 폐기하지만 **브라우저의 쿠키는 그대로 남는다.** 이후 흐름이 문제다.

```
1. 로그아웃 → DB row.revoked_at 설정, 쿠키는 유지
2. 재방문 → proxy.ts가 refreshToken 쿠키 존재를 확인하고 통과시킴
3. refreshServerAccessToken() → POST /auth/jwt/refresh (폐기된 토큰)
4. verify_refresh_token_row() → revoked_at is not None
        → revoke_all_user_refresh_tokens(user_id)   ← 재사용 공격으로 판정
5. 해당 사용자의 모든 기기 세션이 폐기됨
```

**한 기기에서 로그아웃하면 다른 모든 기기의 세션이 끊긴다.** 재사용 탐지 로직 자체는 올바르지만, 로그아웃이 쿠키를 남겨 정상 흐름을 공격으로 오인하게 만든다.

## 수정안

### 1. `auth_refresh.py` — 단일 핸들러로 통합

```python
from app.config import settings
from app.services.auth_cookies import REFRESH_COOKIE_NAME


@router.post("/jwt/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """리프레시 토큰을 폐기하고 쿠키를 제거한다.

    액세스 토큰(JWT)은 서버에서 무효화할 수 없으므로 만료까지 유효하다.
    즉시 차단이 필요하면 ACCESS_TOKEN_EXPIRE_SECONDS를 줄이거나
    액세스 토큰 denylist 도입을 검토한다.
    """
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        await revoke_refresh_token(db, refresh_token)

    response = JSONResponse(content={"detail": "Logged out"})
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
    )
    return response
```

**액세스 토큰 유효성을 요구하지 않는 것이 의도적이다.** 액세스 토큰이 만료된 상태에서도 로그아웃은 성공해야 한다. 그렇지 않으면 리프레시 토큰이 영영 폐기되지 않는다.

> `delete_cookie`의 `path`·`secure`·`samesite`는 **설정 시와 동일해야** 브라우저가 삭제를 인식한다.

### 2. `auth_jwt.py` — 죽은 코드 제거

```python
# 아래를 삭제한다
_get_current_user_token = fastapi_users.authenticator.current_user_token(active=True)


@router.post("/logout")
async def logout(...):
    ...
```

`Strategy`, `fastapi_users` import 중 미사용이 되는 것도 함께 정리한다.

### 3. 재발 방지 테스트

```python
def test_no_duplicate_route_paths():
    """같은 (method, path)가 두 번 등록되지 않아야 한다 (H1 회귀 방지)."""
    from fastapi.routing import APIRoute
    from app.main import app

    seen: set[tuple[str, str]] = set()
    duplicates: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            entry = (method, route.path)
            if entry in seen:
                duplicates.append(f"{method} {route.path}")
            seen.add(entry)

    assert not duplicates, f"중복 등록된 라우트: {duplicates}"
```

이 테스트는 `tests/routes/test_route_permissions.py`에 함께 두면 자연스럽다. 라우트 구성을 검증하는 같은 성격이다.

### 4. OpenAPI 재생성

경로 정의가 바뀌므로 스펙과 프론트 클라이언트를 다시 만든다.

```bash
cd fastapi_backend && uv run python -m commands.generate_openapi_schema
cd ../nextjs-frontend && pnpm run generate-client
```

pre-commit 훅이 `main.py` 변경을 감지해 자동 실행하지만, 수동으로 한 번 확인하는 편이 안전하다.

## 검증

```bash
# 중복 라우트가 사라졌는지
cd fastapi_backend && uv run python -c "
from fastapi.routing import APIRoute
from app.main import app
paths = [(m, r.path) for r in app.routes if isinstance(r, APIRoute) for m in r.methods]
print('중복:', [p for p in set(paths) if paths.count(p) > 1] or '없음')
"

# 로그아웃 후 쿠키가 삭제되는지
curl -i -X POST http://localhost:8000/auth/jwt/logout -b "refreshToken=<토큰>"
# 응답 헤더에 Set-Cookie: refreshToken=""; Max-Age=0 이 있어야 한다
```

---

# 적용 순서

| 순서 | 작업 | 배포 필요 | 비고 |
|---|---|---|---|
| 1 | **DB 비밀번호 교체** | DB 재기동 | 코드 변경 없이 선행 가능 |
| 2 | compose 변수화 + 루트 `.env` / `.env.example` | 재기동 | C1 |
| 3 | `make init` + gitleaks 훅 | — | C1 재발 방지 |
| 4 | `login_rate_limit.py` 교체 | 백엔드 배포 | C3 + H3 |
| 5 | `REQUIRE_REDIS` 설정 추가 | 백엔드 배포 | C3 보완 |
| 6 | 로그아웃 통합 + `auth_jwt.logout` 제거 | 백엔드 배포 | H1 |
| 7 | OpenAPI · 프론트 클라이언트 재생성 | 프론트 배포 | H1 후속 |
| 8 | 회귀 테스트 3종 추가 | — | 전 항목 |

**1번은 코드 변경 없이 지금 바로 할 수 있고, 가장 급하다.**

4~7번은 한 번의 백엔드 배포로 묶을 수 있다. 다만 7번은 프론트엔드 재빌드가 필요하므로, **백엔드를 먼저 배포하면 잠시 스펙과 서버가 어긋나는 구간**이 생긴다. 로그아웃 응답 형태만 달라지는 수준이라 실사용에 영향은 없지만, 가능하면 함께 배포하는 편이 깔끔하다.

# 검증 체크리스트

> 상태: **코드 적용 완료** (2026-09-03). 운영 DB 비밀번호 교체·히스토리 정리는 별도.

- [x] compose / Makefile에 DB 비밀번호 평문 없음 (`${POSTGRES_*}` 치환)
- [x] 루트 `.env.example` + `make init` (기존 파일은 덮어쓰기 확인)
- [x] 루트 `.env`가 `.gitignore`로 제외 (`git check-ignore -v .env`)
- [x] gitleaks pre-commit 훅
- [x] `login_rate_limit` Redis INCR + 인메모리 LRU 상한
- [x] `REQUIRE_REDIS` 설정 (lifespan 가드)
- [x] 동시 실패 → 잠금 회귀 테스트 (서비스 계층 + fakeredis)
- [x] 인메모리 `_MAX_TRACKED_IDS` 상한 테스트
- [x] 중복 라우트 0건 테스트
- [x] 로그아웃 `Set-Cookie` 삭제 (Max-Age=0)
- [x] C2: `.env.example` CORS `http://localhost:3000`
- [x] `make test-backend` 통과 (49 passed, 8 skipped)
- [ ] **운영:** 노출된 DB 비밀번호 `ALTER USER`로 교체 후 루트 `.env`와 일치
- [ ] **운영:** `REQUIRE_REDIS=true` (멀티 워커)
- [ ] 로그아웃 후 다른 기기 세션 유지 (수동 E2E)

---

## 참고

- 전체 검토 결과는 `template-review.md` 참조 (치명 3 · 높음 4 · 중간 11 · 낮음 5)
- **C2(CORS 와일드카드)** 는 `.env.example`에서 `["http://localhost:3000"]`으로 변경됨
