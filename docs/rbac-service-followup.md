# 후속 조치 — N4 · N5 (`app/rbac/service.py`)

> 작성일: 2026-09-03
> 대상: `azazqa/nextjs-fastapi-template` commit `0ebda5d`
> 배경: N1~N3 조치 검증 중 발견한 사소한 항목 2건

---

## 개요

N1~N3은 모두 적용 확인되었다. 이 문서는 그 과정에서 발견한 **동작에 즉시 영향은 없으나 정리해두면 좋은 항목 2건**을 다룬다.

| # | 항목 | 위치 | 등급 |
|---|---|---|---|
| **N4** | `rowcount`를 `commit()` 이후에 읽음 | `revoke_role()` | 낮 |
| **N5** | 반환값 분기가 테스트되지 않음 | `assign_role()` · `revoke_role()` | 낮 |

두 건 모두 `app/rbac/service.py` 한 파일이며, **함께 처리하면 20줄 남짓**이다.

### 공통 배경

두 항목은 같은 지점을 가리킨다. **`assign_role` / `revoke_role`의 반환값(`bool`)이 현재는 CLI 출력 문구를 고르는 데만 쓰이고, 검증되지 않은 채로 남아 있다.**

지금은 영향이 없지만, `role:manage` API를 만들면 이 반환값이 **HTTP 응답 코드를 가르는 근거**가 된다. 그때 처음 문제가 드러나면 원인 추적이 번거로워진다.

```python
# 향후 API에서 예상되는 사용
removed = await revoke_role(session, user_id=..., role_code=...)
if not removed:
    raise NotFoundError("해당 역할을 보유하고 있지 않습니다")   # 404
return {"detail": "revoked"}                                   # 200
```

---

# N4. `rowcount`를 `commit()` 이후에 읽는다

## 현황

`app/rbac/service.py` — `revoke_role()`

```python
result = await session.execute(
    delete(UserRole).where(
        UserRole.user_id == user_id, UserRole.role_id == role.id
    )
)
await session.commit()
await invalidate_user_rbac(user_id)
return result.rowcount > 0      # ← commit 이후 접근
```

## 판단 — 아마 동작하지만, 보장에 기대고 있다

**SQLAlchemy 2.0은 DML 실행 시점에 `rowcount`를 `CursorResult`에 캐시**하므로, 커서가 닫힌 뒤에도 값을 읽을 수 있을 가능성이 높다. 현재 테스트가 통과한다는 것도 이를 뒷받침한다.

다만 두 가지가 걸린다.

**첫째, 그 동작을 이 코드가 검증하지 않는다.** `test_revoke_role_invalidates_cache`는 캐시 무효화만 확인하고 **반환값을 보지 않는다.** 즉 `rowcount` 접근이 예외를 던지지 않는다는 것만 우연히 확인될 뿐, 값이 올바른지는 아무도 보지 않는다 (N5와 연결된다).

**둘째, 드라이버·버전에 따라 달라질 수 있는 영역이다.** `CursorResult.rowcount`의 커서 종료 후 동작은 SQLAlchemy가 명시적으로 계약한 지점이 아니다. asyncpg 드라이버나 SQLAlchemy 마이너 버전이 올라가며 바뀌어도 이상하지 않다.

**버그로 단정하지 않는다.** 다만 커밋 전에 값을 확보하면 이 논의 자체가 사라지고, 비용은 한 줄이다.

## 조치

```diff
     result = await session.execute(
         delete(UserRole).where(
             UserRole.user_id == user_id, UserRole.role_id == role.id
         )
     )
+    removed = result.rowcount > 0
     await session.commit()
     await invalidate_user_rbac(user_id)
-    return result.rowcount > 0
+    return removed
```

### 왜 이 형태가 나은가

- **커서가 살아 있는 시점에 값을 읽는다** — 드라이버 구현에 의존하지 않는다
- **의도가 드러난다** — `removed`라는 이름이 "무엇을 반환하는가"를 설명한다
- **부수효과와 반환값이 분리된다** — `commit`·`invalidate` 사이에 반환 로직이 끼어들지 않는다

---

# N5. 반환값 분기가 테스트되지 않는다

## 현황

두 함수 모두 **분기를 반환값으로 표현**하는데, 그 분기를 검증하는 테스트가 없다.

| 함수 | 반환 | 의미 | 테스트 |
|---|---|---|---|
| `assign_role()` | `True` | 새로 부여함 | 없음 |
| | `False` | **이미 보유 중** | **없음** |
| `revoke_role()` | `True` | 회수함 | 없음 |
| | `False` | **보유하지 않았음** | **없음** |

기존 테스트 2개(`test_assign_role_invalidates_cache`, `test_revoke_role_invalidates_cache`)는 **캐시 무효화만** 확인한다.

```python
await assign_role(db_session, user_id=user.id, role_code="operator")
assert await get_cached_rbac(user.id) is None      # 반환값을 받지도 않는다
```

## 영향

**현재:** CLI의 출력 문구가 잘못 나올 수 있다.

```python
# app/cli/grant_role.py
if granted:
    print(f"Granted role '{role_code}' to {email}")
else:
    print(f"User {email} already has role '{role_code}'")
```

부여에 성공했는데 "already has role"이 출력되어도 아무도 모른다. 반대도 마찬가지다.

**향후:** `role:manage` API에서 이 값이 HTTP 상태 코드를 결정하게 되면, 잘못된 반환이 **잘못된 응답 코드**가 된다. 멱등성 판단(이미 부여된 역할을 다시 부여했을 때 200인가 409인가)도 여기에 걸린다.

## 조치 — 회귀 테스트 2건 추가

기존 테스트와 같은 파일(`tests/rbac/test_permission_cache.py`)에 두거나, 서비스 계층 테스트가 늘어날 것을 예상해 `tests/rbac/test_rbac_service.py`로 분리해도 된다. **분리를 권한다** — 캐시 테스트와 서비스 동작 테스트는 관심사가 다르다.

```python
# tests/rbac/test_rbac_service.py
import uuid

import pytest
from fastapi_users.password import PasswordHelper

from app.models import User
from app.rbac.service import assign_role, revoke_role


async def _create_user(db_session, email: str) -> User:
    user = User(
        id=uuid.uuid7(),
        email=email,
        hashed_password=PasswordHelper().hash("TestPassword123#"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_assign_role_returns_false_when_already_granted(db_session, fake_redis):
    """같은 역할을 두 번 부여하면 False 를 반환해야 한다 (N5)."""
    user = await _create_user(db_session, "assign-twice@example.com")

    first = await assign_role(db_session, user_id=user.id, role_code="operator")
    second = await assign_role(db_session, user_id=user.id, role_code="operator")

    assert first is True, "최초 부여는 True 여야 한다"
    assert second is False, "이미 보유한 역할은 False 여야 한다"


@pytest.mark.asyncio
async def test_revoke_role_returns_expected_flag(db_session, fake_redis):
    """보유한 역할은 True, 보유하지 않은 역할은 False 를 반환해야 한다 (N4·N5)."""
    user = await _create_user(db_session, "revoke-flag@example.com")
    await assign_role(db_session, user_id=user.id, role_code="operator")

    removed = await revoke_role(db_session, user_id=user.id, role_code="operator")
    again = await revoke_role(db_session, user_id=user.id, role_code="operator")

    assert removed is True, "보유한 역할 회수는 True 여야 한다"
    assert again is False, "보유하지 않은 역할 회수는 False 여야 한다"


@pytest.mark.asyncio
async def test_unknown_role_raises(db_session, fake_redis):
    """존재하지 않는 역할 코드는 ValueError 를 던져야 한다."""
    user = await _create_user(db_session, "unknown-role@example.com")

    with pytest.raises(ValueError):
        await assign_role(db_session, user_id=user.id, role_code="no_such_role")

    with pytest.raises(ValueError):
        await revoke_role(db_session, user_id=user.id, role_code="no_such_role")
```

두 번째 테스트가 **N4까지 함께 검증한다.** `removed is True`를 단언하므로, `rowcount` 접근이 잘못되면 예외가 아니라 값 불일치로 드러난다.

세 번째 테스트(`ValueError`)는 요청 범위 밖이지만, CLI가 이 예외를 `SystemExit`로 변환하는 경로가 있으므로 함께 두면 계약이 완성된다.

> `fake_redis` 픽스처를 넣은 이유는 `invalidate_user_rbac()`이 Redis를 건드리기 때문이다. 없으면 `get_redis()`가 `None`을 반환해 무효화가 no-op이 되고, 테스트가 실제 경로를 타지 않는다.

---

# 적용 후 `revoke_role()` 전문

```python
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
    removed = result.rowcount > 0        # ★ commit 전에 확보
    await session.commit()
    await invalidate_user_rbac(user_id)
    return removed
```

`assign_role()`은 코드 변경이 없다. 테스트만 추가된다.

---

# 검증

```bash
cd fastapi_backend

# 새 테스트만
uv run pytest tests/rbac/test_rbac_service.py -v

# 전체
make test-backend
```

기존 48개 + 신규 3개 = **51개**가 되어야 한다.

# 체크리스트

> 상태: **적용 완료** (2026-09-03)

- [x] `revoke_role()` — `removed`를 `commit()` 전에 확보 (N4)
- [x] `tests/rbac/test_rbac_service.py` 신설
- [x] `assign_role` 중복 부여 → `False` 테스트 (N5)
- [x] `revoke_role` 반환값 True/False 테스트 (N4·N5 동시 검증)
- [x] 알 수 없는 역할 코드 → `ValueError` 테스트
- [x] `make test-backend` 전체 통과

---

## 이후 `role:manage` API를 만들 때

이 두 건을 정리해두면 API 구현 시 계약이 이미 확정된 상태가 된다. 그때 결정할 것은 하나 남는다.

**멱등성 정책** — 이미 보유한 역할을 다시 부여하면 무엇을 반환할 것인가.

| 정책 | 응답 | 특징 |
|---|---|---|
| 멱등 | `200` (또는 `204`) | 재시도에 안전. 클라이언트 구현이 단순 |
| 충돌 명시 | `409 Conflict` | 상태 변화 여부가 명확 |

**멱등 쪽을 권한다.** 관리 화면에서 더블클릭이나 네트워크 재시도로 같은 요청이 두 번 갈 수 있고, 그때 에러를 띄우면 사용자는 실패로 오인한다. `assign_role()`이 이미 `False`로 "변화 없음"을 알려주므로, 응답 본문에 `{"changed": false}`를 실어 구분하면 충분하다.

---

## 관련 문서

- `docs/cache-layer-followup.md` — N1·N2·N3 (적용 완료)
- `docs/critical-fixes.md` — C1·C3·H1·H3 (적용 완료)
- `docs/project-structure-review.md` — 전체 검토 결과
