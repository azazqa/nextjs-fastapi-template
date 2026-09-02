# 권한(Authorization) 설계 가이드

> 작성일: 2026-09-01
> 대상: 검색 + AI 플랫폼 (FastAPI + PostgreSQL 18 + Next.js 16 SSR + MCP)
> 전제: 사용자 테이블은 이미 존재

---

## 목차

1. [설계 원칙](#1-설계-원칙)
2. [모델 선택 — RBAC](#2-모델-선택--rbac)
3. [권한 명명 규칙](#3-권한-명명-규칙)
4. [데이터 모델](#4-데이터-모델)
5. [초기 권한 · 역할 정의](#5-초기-권한--역할-정의)
6. [권한 조회와 캐싱](#6-권한-조회와-캐싱)
7. [FastAPI 구현](#7-fastapi-구현)
8. [리소스 단위 권한](#8-리소스-단위-권한)
9. [MCP 서버의 권한 처리](#9-mcp-서버의-권한-처리)
10. [Next.js 측 처리](#10-nextjs-측-처리)
11. [감사 로그](#11-감사-로그)
12. [마이그레이션 전략](#12-마이그레이션-전략)
13. [안티패턴](#13-안티패턴)
14. [구현 체크리스트](#14-구현-체크리스트)

---

## 1. 설계 원칙

### 원칙 1 — 코드는 권한을 검사하고, 역할은 권한 묶음일 뿐이다

가장 중요한 원칙이다.

```python
# 나쁨 — 역할이 늘어날 때마다 코드를 고쳐야 한다
if user.role in ("admin", "manager", "editor"):
    ...

# 좋음 — 역할 정의만 DB에서 바꾸면 된다
if "document:delete" in user.permissions:
    ...
```

역할을 직접 검사하면 "편집자도 삭제할 수 있게 해달라"는 요청 하나에 **코드 수정 + 배포**가 필요하다. 권한을 검사하면 **관리 화면에서 역할에 권한을 추가**하면 끝난다.

기능이 계속 늘어날 전제이므로 이 차이가 누적된다.

### 원칙 2 — 권한 판정의 정본은 백엔드다

Next.js 미들웨어와 화면 요소 숨김은 **사용자 경험**을 위한 것이지 보안 장치가 아니다. 브라우저는 신뢰할 수 없다.

**모든 권한 판정은 FastAPI가 수행한다.** 앞서 세운 SSOT 원칙과 일관된다.

### 원칙 3 — 거부를 기본값으로

권한이 명시적으로 부여되지 않았으면 거부한다. 새 엔드포인트를 추가할 때 권한 선언을 빠뜨리면 **아무도 접근하지 못하는** 상태가 되어야 하고, **누구나 접근 가능한** 상태가 되어서는 안 된다.

---

## 2. 모델 선택 — RBAC

| 모델 | 설명 | 판정 |
|---|---|---|
| 단순 역할 | `users.role` 컬럼 하나 | 초기엔 편하지만 확장 불가 |
| **RBAC (역할-권한 분리)** | 역할 ↔ 권한 다대다 | **권장** |
| ABAC / ReBAC | 속성·관계 기반 동적 판정 | 현 단계에서는 과설계 |

RBAC를 권장하는 이유는 **비용 대비 효과**다. 테이블 4개와 의존성 함수 하나로 구현되며, 이후 기능이 아무리 늘어나도 구조를 바꿀 필요가 없다.

ABAC는 "부서가 같고 문서 등급이 3 이하이면 허용" 같은 동적 규칙이 필요할 때 검토한다. 지금은 필요 없다.

---

## 3. 권한 명명 규칙

**`<resource>:<action>` 형식**으로 통일한다.

```
document:read        문서 조회
document:create      문서 등록
document:update      문서 수정
document:delete      문서 삭제

search:query         검색 실행
search:export        검색 결과 내보내기

source:read          수집 소스 조회
source:manage        수집 소스 생성 · 수정 · 삭제

index:reindex        재색인 실행
index:status         색인 상태 조회

task:read            태스크 조회
task:cancel          태스크 취소

user:read            사용자 조회
user:manage          사용자 생성 · 수정 · 비활성화
role:manage          역할 · 권한 부여
```

### 규칙

- **소문자 + 콜론 구분자**로 고정한다
- 리소스는 **단수형**을 쓴다 (`document`, `documents` 아님)
- 액션은 CRUD에 억지로 맞추지 않는다. `reindex`, `cancel` 처럼 도메인 동사가 명확하면 그대로 쓴다
- **`*` 와일드카드를 도입하지 않는다.** `document:*` 같은 표현은 편해 보이지만, 나중에 추가된 액션이 자동으로 부여되어 의도치 않은 권한 확대를 만든다. 관리자 역할에도 권한을 명시적으로 나열한다

---

## 4. 데이터 모델

> **주의:** 아래는 스키마 설계다. Alembic 마이그레이션 파일은 CLI로 직접 생성한다.

### 4-1. 역할

```sql
CREATE TABLE roles (
    id          UUID PRIMARY KEY DEFAULT uuidv7(),
    code        TEXT NOT NULL UNIQUE,          -- 'admin', 'editor', 'viewer'
    name        TEXT NOT NULL,                 -- 화면 표시용
    description TEXT,
    is_system   BOOLEAN NOT NULL DEFAULT false,-- 시스템 역할: 삭제 금지
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

`is_system`은 `admin` 같은 필수 역할이 관리 화면에서 삭제되는 사고를 막는다. 관리자 역할을 실수로 지우면 복구 경로가 없어진다.

### 4-2. 권한

```sql
CREATE TABLE permissions (
    code        TEXT PRIMARY KEY,              -- 'document:read'
    name        TEXT NOT NULL,                 -- '문서 조회'
    category    TEXT NOT NULL,                 -- 관리 화면 그룹핑
    description TEXT
);
```

**권한 코드를 기본키로 쓴다.** UUID를 쓰지 않는 이유는 두 가지다.

- 권한 코드는 **코드베이스에 문자열로 하드코딩**되므로 자연키가 적합하다
- 조인 결과에 권한 코드가 그대로 보여 디버깅이 쉽다

권한 목록은 애플리케이션 코드가 정의하는 상수에 가깝다. 관리자가 화면에서 새 권한을 만들지 않는다. **코드에 없는 권한은 아무 의미가 없기 때문이다.** 배포 시 시드로 동기화한다.

### 4-3. 역할-권한 매핑

```sql
CREATE TABLE role_permissions (
    role_id         UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_code TEXT NOT NULL REFERENCES permissions(code) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_code)
);

CREATE INDEX idx_role_permissions_permission
    ON role_permissions (permission_code);
```

### 4-4. 사용자-역할 매핑

```sql
CREATE TABLE user_roles (
    user_id     <users.id 타입> NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id     UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    granted_by  <users.id 타입> REFERENCES users(id),
    PRIMARY KEY (user_id, role_id)
);

CREATE INDEX idx_user_roles_role ON user_roles (role_id);
```

> **확인 필요:** `user_id` 컬럼 타입을 기존 `users.id`와 정확히 일치시킨다. BIGINT인지 UUID인지 먼저 확인할 것.

**다대다로 설계한다.** 지금은 사용자당 역할이 하나뿐이더라도, "검토자 + 편집자" 같은 조합 요구는 반드시 생긴다. 나중에 1:N에서 N:M으로 바꾸는 것보다 처음부터 N:M이 싸다.

`granted_by`는 감사 추적의 최소 단위다. 누가 누구에게 권한을 줬는지 남는다.

### 4-5. 권한 조회 뷰

```sql
CREATE VIEW user_permissions AS
SELECT DISTINCT
    ur.user_id,
    rp.permission_code
FROM user_roles ur
JOIN role_permissions rp ON rp.role_id = ur.role_id;
```

애플리케이션은 이 뷰만 조회하면 된다. 역할 구조가 바뀌어도(예: 역할 상속 도입) 뷰만 수정하면 코드는 그대로다.

---

## 5. 초기 권한 · 역할 정의

3개 역할로 시작한다. 더 잘게 나누는 것은 실제 요구가 생긴 뒤에 한다.

| 역할 | 코드 | 설명 |
|---|---|---|
| 관리자 | `admin` | 전체 권한. `is_system = true` |
| 편집자 | `editor` | 콘텐츠 관리, 재색인 |
| 조회자 | `viewer` | 검색과 조회만 |

### 권한 배정

| 권한 | admin | editor | viewer |
|---|:---:|:---:|:---:|
| `search:query` | O | O | O |
| `search:export` | O | O | - |
| `document:read` | O | O | O |
| `document:create` | O | O | - |
| `document:update` | O | O | - |
| `document:delete` | O | - | - |
| `source:read` | O | O | - |
| `source:manage` | O | - | - |
| `index:status` | O | O | - |
| `index:reindex` | O | O | - |
| `task:read` | O | O | - |
| `task:cancel` | O | - | - |
| `user:read` | O | - | - |
| `user:manage` | O | - | - |
| `role:manage` | O | - | - |

### 시드 전략

권한 목록과 시스템 역할은 **애플리케이션 시작 시 동기화**한다.

```python
# 코드가 정의하는 권한 목록이 정본
ALL_PERMISSIONS = [
    ("search:query", "검색 실행", "search"),
    ("document:delete", "문서 삭제", "document"),
    # ...
]

async def sync_permissions(session):
    """앱 기동 시 실행. 신규 권한은 추가하고, 기존 것은 건드리지 않는다."""
    # UPSERT — 코드에 없는 권한을 삭제하지는 않는다 (운영 중 사고 방지)
```

**코드에서 사라진 권한을 자동 삭제하지 않는다.** 배포 실수나 브랜치 차이로 권한이 통째로 날아가면 역할 매핑까지 CASCADE로 삭제된다. 정리는 수동으로 한다.

---

## 6. 권한 조회와 캐싱

### 세션에 권한을 박지 않는다

JWT나 세션 쿠키에 권한 목록을 넣으면 **권한을 회수해도 만료까지 유효**하다. 관리자가 권한을 뺐는데 그 사용자가 계속 삭제를 할 수 있다면 사고다.

**요청마다 권한을 조회한다.** 조회 비용은 인덱스가 걸린 뷰 조회 한 번이므로 이 규모에서 문제가 되지 않는다.

### 요청 단위 캐싱

한 요청 안에서 여러 번 권한을 확인하더라도 DB 조회는 한 번이어야 한다.

```python
# 인증 의존성에서 한 번 조회하여 request.state에 보관
# 이후 권한 검사는 메모리에서 수행
```

### 이후 최적화

트래픽이 늘면 Redis에 사용자별 권한 집합을 캐시한다. 이때 **권한 변경 시 해당 사용자 캐시를 무효화**하는 경로를 반드시 함께 만든다. 무효화 없는 캐시는 위 JWT 문제를 그대로 재현한다.

지금 단계에서는 넣지 않는다.

---

## 7. FastAPI 구현

### 7-1. 현재 사용자 모델

```python
from dataclasses import dataclass, field

@dataclass
class CurrentUser:
    id: UUID
    email: str
    is_active: bool
    permissions: frozenset[str] = field(default_factory=frozenset)

    def has(self, *codes: str) -> bool:
        return set(codes).issubset(self.permissions)
```

### 7-2. 인증 의존성

```python
async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    user = await resolve_session_cookie(request, session)
    if user is None:
        raise HTTPException(401, "인증이 필요합니다")
    if not user.is_active:
        raise HTTPException(403, "비활성화된 계정입니다")

    perms = await fetch_user_permissions(session, user.id)   # user_permissions 뷰
    return CurrentUser(
        id=user.id, email=user.email, is_active=True,
        permissions=frozenset(perms),
    )
```

### 7-3. 권한 의존성

```python
def require(*codes: str):
    """지정한 권한을 모두 가진 사용자만 통과시킨다."""
    async def dependency(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        missing = set(codes) - user.permissions
        if missing:
            raise HTTPException(
                status_code=403,
                detail=f"권한이 없습니다: {', '.join(sorted(missing))}",
            )
        return user
    return dependency


def require_any(*codes: str):
    """지정한 권한 중 하나라도 가지면 통과시킨다."""
    async def dependency(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if not (set(codes) & user.permissions):
            raise HTTPException(403, "권한이 없습니다")
        return user
    return dependency
```

### 7-4. 사용

```python
@router.get("/search")
async def search(
    q: str,
    user: CurrentUser = Depends(require("search:query")),
):
    ...


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: UUID,
    user: CurrentUser = Depends(require("document:delete")),
):
    ...


# 라우터 단위 적용 — 관리 라우터 전체에 기본 권한을 건다
admin_router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(require("user:read"))],
)
```

### 7-5. 401과 403을 구분한다

| 상태 코드 | 의미 | 프론트 동작 |
|---|---|---|
| **401** | 인증되지 않음 (로그인 필요) | 로그인 페이지로 이동 |
| **403** | 인증되었으나 권한 없음 | 권한 없음 안내 표시 |

이 둘을 뭉뜽그리면 프론트엔드가 올바르게 대응할 수 없다. 권한이 없는 사용자를 로그인 페이지로 보내면 로그인 → 다시 거부 → 무한 반복이 된다.

### 7-6. 누락 방지

**권한 선언이 없는 엔드포인트를 찾아내는 테스트를 둔다.**

```python
def test_all_routes_declare_permission():
    """인증·권한 의존성이 없는 라우트가 있으면 실패한다.
    공개 엔드포인트는 명시적 허용 목록에 등록한다."""
    PUBLIC = {"/health", "/api/auth/login", "/docs", "/openapi.json"}
    # app.routes 를 순회하며 dependencies 검사
```

기능이 늘어날수록 권한 선언을 빠뜨리는 사고가 생긴다. 이 테스트 하나가 그 사고를 전부 막는다. **초기에 넣어야 의미가 있다.**

---

## 8. 리소스 단위 권한

RBAC는 **"이 행위를 할 수 있는가"**를 판정한다. **"이 대상에 대해 할 수 있는가"**는 별개다.

```
"문서를 수정할 수 있다"          → RBAC (document:update)
"자기가 등록한 문서만 수정한다"   → 소유권 검사 (서비스 레이어)
```

### 처리 위치

두 검사를 섞지 않는다.

```python
@router.patch("/documents/{doc_id}")
async def update_document(
    doc_id: UUID,
    payload: DocumentUpdate,
    user: CurrentUser = Depends(require("document:update")),  # 1차: 행위 권한
    session: AsyncSession = Depends(get_session),
):
    doc = await get_document(session, doc_id)
    if doc is None:
        raise HTTPException(404)

    # 2차: 대상 한정 — 서비스 레이어의 책임
    if doc.owner_id != user.id and not user.has("document:manage_all"):
        raise HTTPException(403, "본인이 등록한 문서만 수정할 수 있습니다")
    ...
```

`document:manage_all` 같은 **우회 권한**을 별도로 두면, 관리자를 특별 취급하는 하드코딩(`if user.id == 1`)을 피할 수 있다.

### 존재 노출 주의

권한이 없는 리소스에 대해 403을 반환하면 **그 리소스가 존재한다는 사실이 노출**된다. 민감한 경우에는 404를 반환한다. 현 시스템에서는 대부분 공개 데이터이므로 403으로 충분하지만, 사용자 정보 관련 엔드포인트에서는 고려한다.

---

## 9. MCP 서버의 권한 처리

**가장 주의해야 할 영역이다.** MCP 도구는 LLM이 호출하므로, 사람이 화면에서 버튼을 누르는 것과 성격이 다르다.

### 원칙 — 읽기 전용을 기본으로

MCP로 노출하는 도구는 **조회 계열로 한정**하는 것을 기본값으로 삼는다.

| 도구 | 노출 | 필요 권한 |
|---|---|---|
| `search_documents` | O | `search:query` |
| `get_document` | O | `document:read` |
| `list_sources` | O | `source:read` |
| `delete_document` | **X** | — |
| `trigger_reindex` | **X** | — |

LLM이 프롬프트 인젝션에 유도되어 삭제 도구를 호출하는 시나리오는 실재한다. 수집한 외부 데이터(크롤링 결과, API 응답)가 컨텍스트에 들어가는 구조이므로 **인젝션 표면이 넓다.**

쓰기 도구가 꼭 필요해지면, 그때 별도 권한과 확인 절차를 설계한다.

### 신원 확인

MCP 클라이언트는 브라우저 세션 쿠키를 쓰지 않는다. 별도 경로가 필요하다.

```sql
CREATE TABLE api_keys (
    id          UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id     <users.id 타입> NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    key_hash    TEXT NOT NULL UNIQUE,       -- 원문 저장 금지
    scopes      TEXT[] NOT NULL DEFAULT '{}',-- 이 키로 허용할 권한 부분집합
    last_used_at TIMESTAMPTZ,
    expires_at  TIMESTAMPTZ,
    revoked_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### scopes — 권한의 상한선

`scopes`는 **사용자 권한의 부분집합**으로만 동작한다.

```
유효 권한 = 사용자 권한 ∩ API 키 scopes
```

사용자가 관리자여도, 키에 `search:query`만 담겨 있으면 그 키로는 검색만 된다. **키가 유출되어도 피해 범위가 키의 scope로 제한된다.**

### 키 저장

원문을 저장하지 않는다. 해시만 보관하고, 발급 시점에 한 번만 원문을 보여준다. 분실하면 재발급한다.

---

## 10. Next.js 측 처리

### 미들웨어는 인증만 검사한다

```ts
// middleware.ts — 로그인 여부만 확인
export function middleware(request: NextRequest) {
  const session = request.cookies.get('session')
  if (!session && !isPublicPath(request.nextUrl.pathname)) {
    return NextResponse.redirect(new URL('/login', request.url))
  }
  return NextResponse.next()
}
```

**미들웨어에서 권한을 판정하지 않는다.** 미들웨어는 매 요청 실행되므로 여기서 DB를 조회하면 전체 응답이 느려진다. 권한 판정은 FastAPI가 한다.

### 화면 요소 제어

Server Component에서 권한을 조회해 렌더링을 분기한다.

```tsx
// app/(admin)/layout.tsx
const me = await fetchMe()   // FastAPI가 권한 목록을 함께 반환

if (!me.permissions.includes('user:read')) {
  return <Forbidden />
}
```

**이건 UX이지 보안이 아니다.** 버튼을 숨겨도 API를 직접 호출하면 그만이다. 서버 검사가 없으면 아무 의미가 없다.

### `/api/me` 응답 설계

```json
{
  "id": "...",
  "email": "...",
  "roles": ["editor"],
  "permissions": ["search:query", "document:read", "document:update"]
}
```

프론트엔드는 이 배열만 보고 UI를 구성한다. 역할이 아니라 **권한 배열을 기준으로 판단**하게 해야, 백엔드와 동일한 규칙이 적용된다.

---

## 11. 감사 로그

권한 관련 작업은 기록한다. **나중에 넣기 가장 어려운 항목**이다.

```sql
CREATE TABLE audit_logs (
    id          UUID PRIMARY KEY DEFAULT uuidv7(),
    actor_id    <users.id 타입> REFERENCES users(id),
    action      TEXT NOT NULL,          -- 'role.grant', 'user.deactivate'
    target_type TEXT,                   -- 'user', 'role', 'document'
    target_id   TEXT,
    detail      JSONB NOT NULL DEFAULT '{}',
    ip          INET,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_logs_actor   ON audit_logs (actor_id, created_at DESC);
CREATE INDEX idx_audit_logs_target  ON audit_logs (target_type, target_id, created_at DESC);
```

### 기록 대상

- 역할 부여 · 회수
- 역할의 권한 변경
- 사용자 활성화 · 비활성화
- API 키 발급 · 폐기
- 파괴적 작업 (문서 삭제, 전체 재색인)

### 기록하지 않을 것

일반 검색과 조회는 남기지 않는다. 볼륨만 커지고 가치가 낮다. 필요하면 별도의 사용 통계로 다룬다.

---

## 12. 마이그레이션 전략

기존 `users` 테이블에 `role` 컬럼이 있다면 순서대로 진행한다.

| 단계 | 작업 | 비고 |
|---|---|---|
| 1 | 권한 테이블 4종 생성 | 기존 테이블 변경 없음 |
| 2 | 권한 · 역할 시드 투입 | |
| 3 | 기존 `users.role` 값을 `user_roles`로 이관 | 데이터 마이그레이션 |
| 4 | 신규 코드가 `user_roles`를 사용하도록 전환 | |
| 5 | 일정 기간 병행 운영 후 `users.role` 제거 | 롤백 여지 확보 |

**3단계와 5단계 사이에 검증 기간을 둔다.** 권한 체계 전환은 잘못되면 전 사용자가 접근 불가가 되거나 전 사용자가 관리자가 되는 사고로 이어진다. 기존 컬럼을 바로 지우지 않는다.

이관 후 검증 쿼리를 반드시 실행한다.

```sql
-- 역할이 하나도 없는 사용자 확인
SELECT u.id, u.email
FROM users u
LEFT JOIN user_roles ur ON ur.user_id = u.id
WHERE ur.user_id IS NULL;
```

---

## 13. 안티패턴

| 안티패턴 | 문제 | 대안 |
|---|---|---|
| 코드에서 역할을 직접 검사 | 역할 추가 시 코드 수정 | 권한 코드로 검사 |
| 프론트엔드 검사만 신뢰 | API 직접 호출로 우회 | 백엔드가 정본 |
| JWT에 권한을 담고 갱신 안 함 | 권한 회수가 만료까지 미반영 | 요청마다 조회 |
| `if user.id == 1` 관리자 특례 | 추적 불가, 이관 불가 | 우회 권한을 정식으로 정의 |
| `document:*` 와일드카드 | 신규 액션이 자동 부여됨 | 권한 명시 나열 |
| 401과 403 혼용 | 프론트 리다이렉트 루프 | 명확히 구분 |
| 권한 없는 엔드포인트를 기본 허용 | 신규 API에서 사고 | 거부를 기본값으로 + 테스트 |
| MCP에 쓰기 도구 노출 | 프롬프트 인젝션 위험 | 읽기 전용 기본 |
| 캐시만 두고 무효화 없음 | JWT 문제 재현 | 무효화 경로 필수 |

---

## 14. 구현 체크리스트

### 스키마

- [ ] `users.id` 타입 확인 후 참조 컬럼 타입 일치
- [ ] `roles` · `permissions` · `role_permissions` · `user_roles` 생성
- [ ] `user_permissions` 뷰 생성
- [ ] `api_keys` 테이블 생성 (MCP용)
- [ ] `audit_logs` 테이블 생성
- [ ] Alembic 마이그레이션은 CLI로 직접 생성

### 백엔드

- [ ] 권한 상수 목록 정의 및 기동 시 동기화
- [ ] 시스템 역할 3종 시드 (`is_system = true` 지정)
- [ ] `get_current_user` 의존성 — 권한 조회 포함
- [ ] `require()` / `require_any()` 의존성 구현
- [ ] 401 / 403 구분
- [ ] **모든 라우트의 권한 선언을 검사하는 테스트**
- [ ] 소유권 검사를 서비스 레이어에 배치
- [ ] `/api/me` 엔드포인트 (권한 배열 반환)

### MCP

- [ ] 노출 도구를 읽기 전용으로 한정
- [ ] 도구별 필요 권한 선언
- [ ] API 키 인증 (해시 저장, 원문 미보관)
- [ ] `유효 권한 = 사용자 권한 ∩ 키 scopes` 로직

### 프론트엔드

- [ ] 미들웨어는 인증 여부만 검사
- [ ] 권한 배열 기반 UI 분기 (역할 아님)
- [ ] 403 전용 화면 (로그인 리다이렉트 금지)

### 운영

- [ ] 감사 로그 기록 지점 배치
- [ ] 관리자 역할 삭제 방지 (`is_system`)
- [ ] 마이그레이션 후 역할 미보유 사용자 검증
- [ ] 기존 `users.role` 제거는 병행 운영 후

---

## 부록 — 확장 시점 판단

| 요구 | 대응 |
|---|---|
| 역할이 10개를 넘음 | 권한 카테고리 정리, 역할 상속 검토 |
| "부서별로 다른 문서" | 테넌트/그룹 개념 도입 |
| "등급 3 이하만 조회" | ABAC 요소 추가 (권한 + 속성 조건) |
| 권한 조회가 병목 | Redis 캐시 + 무효화 경로 |

**지금은 어느 것도 필요하지 않다.** 위 구조로 시작하면 네 가지 모두 나중에 점진적으로 얹을 수 있다.
