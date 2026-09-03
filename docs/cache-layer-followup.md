# 후속 조치 — N1 · N2 · N3 (캐시 계층)

> 작성일: 2026-09-03
> 대상: `azazqa/nextjs-fastapi-template` commit `8040113`
> 배경: C1·C3·H1·H3 수정 과정에서 함께 추가된 Redis 캐시 계층 검토 결과

---

## 개요

`8040113`에서 세 개의 Redis 캐시 모듈이 새로 도입되었다.

| 모듈 | 목적 | 상태 |
|---|---|---|
| `app/services/access_denylist.py` | 액세스 JWT 무효화 | **정상 동작** — `DenyListJWTStrategy.read_token`이 읽는다 |
| `app/rbac/permission_cache.py` | RBAC 권한·역할 캐시 | 동작하나 **빈 권한을 캐시하지 못함** (N2) · **무효화 규약 미확립** (N3) |
| `app/services/refresh_token_cache.py` | 리프레시 토큰 캐시 | **읽는 코드가 없음** (N1) |

액세스 denylist는 설계·구현 모두 문제가 없다. 나머지 두 개에 대한 조치를 정리한다.

| # | 항목 | 등급 | 조치 방향 |
|---|---|---|---|
| **N1** | `refresh_token_cache`가 write-only | 중 | **제거** |
| **N2** | 권한 없는 사용자는 캐시되지 않음 | 낮 | sentinel 값으로 빈 결과 캐시 |
| **N3** | 캐시 무효화가 CLI에만 연결 | 낮 | 역할 변경을 단일 서비스 함수로 통합 |

---

# N1. `refresh_token_cache`가 write-only다

## 현황

모듈에 **읽기 함수가 정의되어 있지 않다.**

```
$ grep -n "^async def\|^def" app/services/refresh_token_cache.py
17:def _ok_key(token_hash)
21:def _user_key(user_id)
25:def _ttl_seconds(expires_at)
33:async def cache_valid_refresh(...)
56:async def invalidate_refresh_hash(...)
68:async def invalidate_user_refresh_cache(...)
```

저장소 전체에서 호출되는 것도 쓰기·무효화뿐이다.

| 호출 지점 | 동작 |
|---|---|
| `verify_refresh_token_row()` | DB 검증 후 **캐시에 쓰기** |
| `rotate_refresh_token()` | 이전 해시 무효화 + 새 해시 **쓰기** |
| `revoke_refresh_token()` | 무효화 |
| `revoke_all_user_refresh_tokens()` | 사용자 전체 무효화 |
| **읽기** | **없음** |

## 영향

기능·보안 문제는 아니다. **순수한 비용만 남는다.**

- refresh 요청마다 Redis 파이프라인 1회 추가 (`SET` + `SADD` + `EXPIRE` = 3 커맨드)
- 회전 시 추가로 `DEL` + `SREM`
- 발급된 리프레시 토큰 수만큼 Redis 키가 쌓인다 (TTL로 정리되나 그때까지 상주)

테스트 2건(`test_refresh_token_cache.py`)도 **캐시가 자기 자신에게 쓰고 읽는 것만** 검증하므로 이 공백을 잡지 못한다. 소비자가 없다는 사실이 테스트로 드러나지 않는다.

## 왜 읽기 경로를 넣어도 이득이 없는가

"읽기를 추가하면 되지 않나"가 자연스러운 다음 생각이지만, **현재 흐름에서는 캐시가 DB 왕복을 줄이지 못한다.**

### 근거 1 — 리프레시는 어차피 DB에 써야 한다

```python
# routes/auth_refresh.py — refresh_access_token()
row = await verify_refresh_token_row(db, refresh_token)   # SELECT
user = await db.get(User, row.user_id)                    # SELECT
await rotate_refresh_token(db, row, new_raw_token=...)    # UPDATE + INSERT
```

회전은 **기존 행을 UPDATE하고 새 행을 INSERT한다.** 이 트랜잭션은 캐시 여부와 무관하게 반드시 발생한다. 캐시가 아낄 수 있는 것은 앞의 SELECT 하나뿐이다.

### 근거 2 — 회전은 ORM 인스턴스를 필요로 한다

`rotate_refresh_token(db, row, ...)`은 `row.revoked_at`을 직접 수정한다. 캐시가 담고 있는 것은 `{user_id, row_id}` JSON이므로 **ORM 객체를 대체할 수 없다.** 캐시를 읽어도 결국 행을 다시 가져와야 한다.

### 근거 3 — 조회 자체가 이미 인덱스 스캔이다

```python
token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
```

`unique=True`이므로 PostgreSQL이 유니크 인덱스를 만든다. `WHERE token_hash = ?`는 단일 인덱스 조회이며, Redis 왕복과 비교해 유의미한 차이가 없다.

### 근거 4 — 캐시 미스가 "무효"를 뜻하지 않는다

캐시에는 **유효했던 해시만** 들어간다. 따라서 미스는 "무효한 토큰"과 "아직 캐시되지 않은 토큰"을 구분하지 못한다. 잘못된 토큰을 DB 접근 전에 걸러내는 용도로도 쓸 수 없다.

## 조치 — 제거

```bash
git rm fastapi_backend/app/services/refresh_token_cache.py
git rm fastapi_backend/tests/services/test_refresh_token_cache.py
```

`app/services/refresh_tokens.py`에서 관련 호출을 제거한다.

```diff
-from app.services.refresh_token_cache import (
-    cache_valid_refresh,
-    invalidate_refresh_hash,
-    invalidate_user_refresh_cache,
-)

 async def revoke_refresh_token(session, raw_token):
     ...
     row.revoked_at = datetime.now(timezone.utc)
     await session.commit()
-    await invalidate_refresh_hash(token_hash, user_id=row.user_id)

 async def revoke_all_user_refresh_tokens(session, user_id):
     ...
     await session.commit()
-    await invalidate_user_refresh_cache(user_id)

 async def verify_refresh_token_row(session, raw_token):
     ...
     if expires_at < now:
         raise RefreshTokenError("Refresh token expired")
-
-    await cache_valid_refresh(
-        token_hash, user_id=row.user_id, row_id=row.id, expires_at=expires_at
-    )
     return row
```

`rotate_refresh_token()`에서도 `invalidate_refresh_hash` · `cache_valid_refresh` 호출을 제거한다. 다만 `8040113`에서 함께 들어간 **`await session.flush()`는 유지한다.** 캐시와 무관하게 `new_row.id`를 확보하는 데 쓰이며, 제거하면 향후 새 행 ID가 필요할 때 다시 넣어야 한다.

```diff
     session.add(new_row)
     await session.flush()
     await session.commit()
-    await invalidate_refresh_hash(old_hash, user_id=user_id)
-    await cache_valid_refresh(
-        new_hash, user_id=user_id, row_id=new_row.id, expires_at=expires_at
-    )
```

`old_hash` · `user_id` 지역 변수도 미사용이 되면 함께 정리한다.

## 제거하지 말아야 할 경우

다음 기능을 곧 만들 계획이라면 **모듈을 남기되 소비자를 함께 구현**하는 편이 낫다.

| 기능 | 캐시 활용 |
|---|---|
| 활성 세션 목록 화면 | `refresh_user:{user_id}` 집합을 목록 소스로 사용 |
| 리프레시 검증을 DB 밖으로 이동 | 읽기 경로 + 미스 시 DB 폴백 |

**둘 다 계획에 없다면 제거가 맞다.** 소비자 없는 캐시는 시간이 지날수록 "왜 있는지 모르는 코드"가 되고, 나중에 무효화 누락 사고의 원인이 된다.

> 읽기 경로를 넣기로 한다면 **미스 시 반드시 DB로 폴백**해야 한다. `rotate_refresh_token`이 이전 해시를 무효화하므로 재사용된 토큰은 자연히 캐시 미스가 되고, DB의 `revoked_at` 검사를 거쳐 재사용 탐지가 유지된다.

---

# N2. 권한이 없는 사용자는 캐시되지 않는다

## 현황

`app/rbac/permission_cache.py`

```python
async def get_cached_rbac(user_id):
    ...
    if not perms_raw and not roles_raw:
        return None          # ← 빈 결과를 "캐시 미스"로 취급
    return frozenset(perms_raw), tuple(sorted(roles_raw))
```

쓰기 쪽도 대칭적으로 빈 값을 저장하지 않는다.

```python
async def set_cached_rbac(user_id, permissions, roles):
    ...
    pipe.delete(pk, rk)
    if permissions:                    # 비어 있으면 SADD 없음
        pipe.sadd(pk, *sorted(permissions))
    if roles:                          # 비어 있으면 SADD 없음
        pipe.sadd(rk, *sorted(roles))
    if permissions or roles:           # 비어 있으면 EXPIRE도 없음
        ...
```

Redis에는 빈 집합이라는 개념이 없어(마지막 원소를 지우면 키가 사라진다) 자연스럽게 이런 구조가 되었다.

## 영향

**역할이 없는 사용자는 영원히 캐시 미스가 된다.** 요청마다 DB 쿼리 2회가 발생한다.

```python
permissions = frozenset(await fetch_user_permissions(session, user.id))  # JOIN 1회
roles = tuple(await fetch_user_roles(session, user.id))                  # JOIN 1회
await set_cached_rbac(...)   # 아무것도 저장되지 않음 → 다음 요청도 미스
```

해당하는 경우가 적지 않다.

- **부트스트랩 직후** — `grant_role` 실행 전에는 모든 사용자가 여기 해당
- **일반 사용자** — 관리 권한이 필요 없는 계정
- **역할이 회수된 계정** — 비활성화 대신 역할만 뺀 경우

캐시를 도입한 목적이 DB 부하 감소인데, **정작 권한이 없는 사용자에게는 캐시가 전혀 동작하지 않는다.**

## 조치 — sentinel 값으로 빈 결과를 캐시한다

```python
# 권한 코드는 "<resource>:<action>" 형식이므로 이 값과 충돌하지 않는다
_EMPTY_MARKER = "__none__"


async def get_cached_rbac(
    user_id: uuid.UUID,
) -> tuple[frozenset[str], tuple[str, ...]] | None:
    redis = get_redis()
    if redis is None:
        return None
    try:
        pipe = redis.pipeline()
        pipe.smembers(_perms_key(user_id))
        pipe.smembers(_roles_key(user_id))
        perms_raw, roles_raw = await pipe.execute()      # 왕복 1회로 축소
    except Exception:
        logger.warning("RBAC cache read failed for user %s", user_id, exc_info=True)
        return None

    if not perms_raw and not roles_raw:
        return None                                      # 진짜 캐시 미스

    permissions = frozenset(p for p in perms_raw if p != _EMPTY_MARKER)
    roles = tuple(sorted(r for r in roles_raw if r != _EMPTY_MARKER))
    return permissions, roles


async def set_cached_rbac(
    user_id: uuid.UUID,
    permissions: frozenset[str] | set[str],
    roles: tuple[str, ...] | list[str],
) -> None:
    redis = get_redis()
    if redis is None:
        return
    ttl = settings.PERMISSION_CACHE_TTL_SECONDS
    pk, rk = _perms_key(user_id), _roles_key(user_id)
    try:
        pipe = redis.pipeline()
        pipe.delete(pk, rk)
        # 빈 결과도 sentinel 로 캐시한다 — 그래야 다음 요청이 DB 를 치지 않는다
        pipe.sadd(pk, *(sorted(permissions) or [_EMPTY_MARKER]))
        pipe.sadd(rk, *(sorted(roles) or [_EMPTY_MARKER]))
        pipe.expire(pk, ttl)
        pipe.expire(rk, ttl)
        await pipe.execute()
    except Exception:
        logger.warning("RBAC cache write failed for user %s", user_id, exc_info=True)
```

읽기 쪽 왕복도 함께 줄였다. 기존 코드는 두 번의 `await`를 순차 실행해 Redis 왕복이 2회였다.

```python
# 기존 — 튜플 표현식이지만 순차 실행된다
perms_raw, roles_raw = await redis.smembers(...), await redis.smembers(...)
```

## 회귀 방지 테스트

```python
@pytest.mark.asyncio
async def test_empty_rbac_is_cached(fake_redis):
    """역할이 없는 사용자도 캐시되어야 한다 (N2 회귀 방지)."""
    user_id = uuid.uuid7()

    await set_cached_rbac(user_id, frozenset(), ())

    cached = await get_cached_rbac(user_id)
    assert cached is not None, "빈 권한이 캐시 미스로 처리되면 안 된다"

    permissions, roles = cached
    assert permissions == frozenset()
    assert roles == ()
```

---

# N3. 캐시 무효화가 CLI에만 연결되어 있다

## 현황

무효화 호출은 두 곳뿐이다.

| 위치 | 호출 |
|---|---|
| `app/cli/grant_role.py` | `invalidate_user_rbac(user.id)` |
| `app/cli/seed_rbac.py` | `invalidate_all_rbac()` |

현재는 역할 변경 경로가 CLI밖에 없으므로 **누락은 없다.** 문제는 앞으로다.

## 영향

### 보장이 바뀌었다

캐시 도입 전후로 권한 반영 시점이 달라졌다.

| | 도입 전 | 도입 후 |
|---|---|---|
| 권한 변경 반영 | **요청 즉시** | **명시적 무효화 시 즉시, 누락 시 최대 300초** |
| 계정 비활성화 반영 | 즉시 | **즉시** (변동 없음) |
| 슈퍼유저 플래그 | 즉시 | **즉시** (변동 없음) |

`is_active` · `is_superuser`는 `current_active_user`가 매 요청 User 행을 읽으므로 캐시의 영향을 받지 않는다. **캐시의 영향 범위는 역할·권한으로 한정된다.** 계정 차단은 여전히 즉시 반영되므로 사고 시 대응 경로는 살아 있다.

### 향후 누락 위험

`role:manage` 권한은 이미 정의되어 있으나(`rbac/constants.py`) 이를 사용하는 API는 아직 없다. **관리 화면에서 역할을 부여하는 엔드포인트를 만드는 시점**에 무효화 호출을 빠뜨리면, 권한을 회수해도 최대 5분간 유효한 상태가 된다.

이런 종류의 누락은 코드 리뷰로 잡기 어렵다. DB 쓰기와 캐시 무효화가 서로 다른 모듈에 있어 연결이 보이지 않기 때문이다.

## 조치 — 역할 변경을 단일 서비스 함수로 통합한다

**규칙으로 강제하는 대신 구조로 강제한다.** 역할을 바꾸는 방법이 하나뿐이면 무효화를 빠뜨릴 수 없다.

### 1. 서비스 함수 신설

```python
# app/rbac/service.py
"""역할 부여·회수 — DB 변경과 캐시 무효화를 함께 수행한다.

역할을 변경하는 코드는 반드시 이 모듈을 거쳐야 한다.
UserRole 을 직접 조작하면 캐시가 어긋난다.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role, UserRole
from app.rbac.permission_cache import invalidate_user_rbac


async def assign_role(
    session: AsyncSession, *, user_id: uuid.UUID, role_code: str
) -> bool:
    """역할을 부여한다. 이미 보유 중이면 False 를 반환한다."""
    role = await session.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        raise ValueError(f"Unknown role: {role_code}")

    exists = await session.scalar(
        select(UserRole).where(
            UserRole.user_id == user_id, UserRole.role_id == role.id
        )
    )
    if exists is not None:
        return False

    session.add(UserRole(user_id=user_id, role_id=role.id))
    await session.commit()
    await invalidate_user_rbac(user_id)      # ★ DB 변경과 항상 한 쌍
    return True


async def revoke_role(
    session: AsyncSession, *, user_id: uuid.UUID, role_code: str
) -> bool:
    """역할을 회수한다. 보유하지 않았다면 False 를 반환한다."""
    role = await session.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        raise ValueError(f"Unknown role: {role_code}")

    result = await session.execute(
        delete(UserRole).where(
            UserRole.user_id == user_id, UserRole.role_id == role.id
        )
    )
    await session.commit()
    await invalidate_user_rbac(user_id)      # ★
    return result.rowcount > 0
```

### 2. CLI를 서비스 함수 위로 옮긴다

`app/cli/grant_role.py`가 `UserRole`을 직접 만들고 별도로 무효화하는 대신 `assign_role()`을 호출하게 한다. 호출 지점이 하나로 모이면 이후 API도 같은 함수를 쓰게 된다.

### 3. 규약을 코드에 남긴다

`app/models.py`의 `UserRole` 클래스에 주석을 단다.

```python
class UserRole(Base):
    """사용자-역할 매핑.

    직접 조작하지 말 것. 반드시 app.rbac.service 의
    assign_role() / revoke_role() 을 사용한다.
    (캐시 무효화가 함께 수행되어야 한다)
    """
```

### 4. 회귀 방지 테스트

```python
@pytest.mark.asyncio
async def test_assign_role_invalidates_cache(session, fake_redis, existing_user):
    """역할 부여 시 캐시가 무효화되어야 한다 (N3 회귀 방지)."""
    from app.rbac.permission_cache import get_cached_rbac, set_cached_rbac
    from app.rbac.service import assign_role

    user_id = existing_user.id

    # 낡은 캐시를 심어둔다
    await set_cached_rbac(user_id, frozenset({"stale:permission"}), ("stale",))
    assert await get_cached_rbac(user_id) is not None

    await assign_role(session, user_id=user_id, role_code="operator")

    assert await get_cached_rbac(user_id) is None, "역할 변경 후 캐시가 남아 있다"
```

`revoke_role`에 대해서도 같은 형태로 하나 더 둔다.

## TTL 설정에 대해

`PERMISSION_CACHE_TTL_SECONDS`의 기본값 300초는 **무효화가 항상 동작한다는 전제에서 안전망**이다. 무효화가 확실히 보장되는 구조가 되면 TTL을 늘려 DB 부하를 더 줄일 수 있다.

반대로 규제나 보안 요구로 권한 회수 지연을 허용할 수 없다면 TTL을 60초 이하로 낮추거나, 해당 환경에서만 `REDIS_URL`을 비워 캐시를 끄는 선택도 가능하다. **설정으로 조절 가능하도록 되어 있으므로 코드 변경은 필요 없다.**

---

# 적용 순서

| 순서 | 작업 | 파일 | 규모 |
|---|---|---|---|
| 1 | **N1 — `refresh_token_cache` 제거** | 3개 파일 삭제·수정 | 작음 |
| 2 | **N2 — sentinel 캐시 + 파이프라인 읽기** | `permission_cache.py` | 작음 |
| 3 | **N3 — `rbac/service.py` 신설 + CLI 이관** | 신규 1 + 수정 2 | 중간 |
| 4 | 회귀 테스트 3종 추가 | `tests/rbac/` | 작음 |

1번과 2번은 독립적이라 순서를 바꿔도 무방하다. 3번은 향후 역할 관리 API를 만들기 **전에** 끝내는 것이 핵심이다. API를 먼저 만들면 그 코드가 규약 없이 자리 잡는다.

# 검증

```bash
# N1 — 참조가 남아 있지 않은지
grep -rn "refresh_token_cache" fastapi_backend/ && echo "잔여 참조 있음" || echo "제거 완료"

# N2 — 빈 권한 사용자의 두 번째 요청이 DB를 치지 않는지
#   (로그 레벨을 올리고 SQL 쿼리 수를 확인하거나 회귀 테스트로 대체)

# N3 — UserRole 직접 조작이 서비스 밖에 없는지
grep -rn "UserRole(" fastapi_backend/app/ | grep -v "app/rbac/service.py"

# 전체
cd fastapi_backend && make test-backend
```

세 번째 명령은 **`app/models.py`의 정의부 외에 출력이 없어야** 정상이다.

# 체크리스트

> 상태: **적용 완료** (2026-09-03)

- [x] `refresh_token_cache.py` · 해당 테스트 삭제
- [x] `refresh_tokens.py`에서 캐시 호출 제거 (`session.flush()`는 유지)
- [x] `_EMPTY_MARKER` 도입, 빈 권한 캐시 동작
- [x] `get_cached_rbac` 파이프라인으로 왕복 1회
- [x] `app/rbac/service.py` 신설 (`assign_role` / `revoke_role`)
- [x] `cli/grant_role.py`가 서비스 함수 사용
- [x] `UserRole` 모델에 직접 조작 금지 주석
- [x] 회귀 테스트 3종 통과
- [x] `make test-backend` 전체 통과

---

## 부록 — 캐시를 추가할 때의 원칙

이번 세 건은 모두 같은 뿌리에서 나왔다. 앞으로 캐시를 늘릴 때 확인할 것들이다.

**1. 소비자를 먼저 만든다.**
읽는 코드 없이 쓰기만 추가하면 비용만 남는다 (N1). 캐시 PR에는 읽기 경로가 반드시 포함되어야 한다.

**2. 캐시가 실제로 왕복을 줄이는지 확인한다.**
같은 트랜잭션이 어차피 DB에 쓴다면 읽기 캐시의 이득은 거의 없다 (N1). 인덱스 조회 한 번을 Redis 왕복 한 번으로 바꾸는 것은 이득이 아니다.

**3. "값 없음"도 값이다.**
빈 결과를 캐시하지 않으면 그 대상은 영원히 미스가 된다 (N2). 캐시 미스와 빈 결과를 구분할 수단을 함께 설계한다.

**4. 무효화는 규약이 아니라 구조로 보장한다.**
"잊지 말고 호출하자"는 반드시 잊힌다. 데이터 변경과 무효화를 같은 함수 안에 두고, 그 함수를 유일한 경로로 만든다 (N3).

**5. 캐시가 바꾼 보장을 문서에 적는다.**
"권한 회수 즉시 반영"이 "최대 N초 지연"으로 바뀌었다면 그것은 설계 변경이다. 영향 범위(무엇이 캐시되고 무엇이 안 되는지)를 함께 남긴다.

---

## 관련 문서

- `docs/critical-fixes.md` — C1·C3·H1·H3 조치 (적용 완료)
- `docs/project-structure-review.md` — 전체 검토 결과
