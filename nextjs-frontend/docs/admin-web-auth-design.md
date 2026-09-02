# 관리자 웹 인증 · 권한 설계

> 작성일: 2026-09-01
> 대상: 검색 + AI 플랫폼 — 관리자 웹 (Next.js 16 SSR + FastAPI + PostgreSQL 18)
> 범위: 토큰 · 쿠키 인증과 RBAC 권한 설계 (확정본)
> 이 문서는 `token-cookie-design.md`를 대체한다

> **구현 채택 차이 (2026-09-02):** Part 1의 `admin_session`/`admin_refresh`, access 15분·refresh 3일, FastAPI Set-Cookie, BFF 제거는 **채택하지 않음**. 실제 구현은 `accessToken`/`refreshToken` HttpOnly 쿠키(Next 설정), access 1시간·refresh 1일, BFF+Bearer, `refresh_tokens` DB 저장·회전을 사용한다. Part 2 RBAC·감사 설계는 본 문서를 따른다.

---

## 목차

**전제**

1. [전제 조건](#1-전제-조건)
2. [확정 사항 요약](#2-확정-사항-요약)

**Part 1 — 인증 · 토큰**

3. [저장 위치 — 왜 쿠키인가](#3-저장-위치--왜-쿠키인가)
4. [쿠키 속성](#4-쿠키-속성)
5. [토큰 2종 구성](#5-토큰-2종-구성)
6. [Refresh 토큰 DB 저장](#6-refresh-토큰-db-저장)
7. [SSR에서의 함정](#7-ssr에서의-함정)
8. [CSRF 대응](#8-csrf-대응)

**Part 2 — 권한 (RBAC)**

9. [설계 원칙](#9-설계-원칙)
10. [권한 목록](#10-권한-목록)
11. [역할 구성](#11-역할-구성)
12. [superuser 운영 정책](#12-superuser-운영-정책)
13. [부트스트랩](#13-부트스트랩)
14. [FastAPI 구현](#14-fastapi-구현)
15. [감사 로그](#15-감사-로그)

**Part 3 — 실행**

16. [전체 스키마](#16-전체-스키마)
17. [Phase 계획](#17-phase-계획)
18. [향후 확장](#18-향후-확장)
19. [체크리스트](#19-체크리스트)
20. [부록 — 흔한 실수](#20-부록--흔한-실수)

---

## 1. 전제 조건

### 개발 범위

**관리자 웹을 먼저 개발**하고, 사용자 웹과 모바일 앱은 이후에 추가한다. 이 설계는 나중에 추가될 클라이언트를 **구조 변경 없이 수용**하는 것을 목표로 한다.

### 인프라

```
                    ┌─────────────────────────────────┐
   브라우저 ──443──▶ │  HAProxy                        │
                    │  · 서브도메인 라우팅              │
                    │  · TLS 종료                     │
                    │  · 관리자 IP 제한                │
                    └─────────────────────────────────┘
                              │
              admin.example.com/*     → admin-frontend  (Next SSR)
              admin.example.com/api/* → api             (FastAPI)
```

**같은 오리진**이므로 브라우저가 Next와 FastAPI 양쪽에 쿠키를 자동 전송한다. 이것이 설계의 전제다. 별도 API 서브도메인(`api.example.com`)을 두면 쿠키를 `Domain=.example.com`으로 넓혀야 하고, 그 순간 서브도메인 격리가 무너진다.

> 실제 도메인은 확정 후 반영한다. 쿠키 설정 · `ALLOWED_ORIGINS` · HAProxy ACL 세 곳에 들어간다.

### 기존 구현

| 항목 | 상태 |
|---|---|
| 인증 | fastapi-users 계열 (`/auth/jwt/login`, `is_superuser`) |
| `users.id` | **UUID v7** |
| `users.role` 컬럼 | **없음** → 데이터 이관 절차 불필요 |
| 프론트엔드 | `nextjs-frontend` → `nextjs-admin-frontend` 로 rename 예정 |

---

## 2. 확정 사항 요약

### 인증

| 항목 | 확정값 |
|---|---|
| 저장 위치 | **HttpOnly 쿠키** (localStorage 사용 안 함) |
| 쿠키 설정 주체 | FastAPI (같은 오리진, BFF 불필요) |
| **`Domain` 속성** | **설정하지 않음 (host-only)** |
| access 토큰 | `admin_session`, **15분**, `path=/` |
| refresh 토큰 | `admin_refresh`, **3일**, `path=/api/auth` |
| access 페이로드 | `user_id`만. **권한 미포함** |
| refresh 저장 | DB (해시), 회전 + 폐기 가능 |
| refresh 갱신 위치 | **Proxy(쿠키 게이트) + DAL** (`lib/permissions-server.ts`, BFF Route Handlers) |
| CSRF | `SameSite=Lax` + Origin 헤더 검증 |

### 권한

| 항목 | 확정값 |
|---|---|
| 모델 | RBAC (역할 ↔ 권한 다대다) |
| `permissions.domain` | **`admin`만 정의** (`user`는 추후) |
| 권한 수 | 8개 (scheduler · task · user · audit) |
| 역할 | **`admin` + `operator`** |
| `is_superuser` | 개발용 root, **DB 직접 수정만**, 1~2개 |
| 감사 로그 | **기한 없이 보관**, 파티셔닝은 추후 |

---

# Part 1 — 인증 · 토큰

## 3. 저장 위치 — 왜 쿠키인가

### localStorage를 쓰지 않는다

관리자 앱은 **권한이 가장 큰 클라이언트**다. XSS가 한 번 발생하면 관리자 토큰이 통째로 유출된다.

`localStorage`와 `sessionStorage`는 JavaScript가 읽을 수 있다. 서드파티 스크립트 하나, npm 의존성 하나가 오염되면 방어 수단이 없다.

**HttpOnly 쿠키는 JavaScript가 읽을 수 없다.** XSS가 발생해도 토큰 자체는 탈취되지 않는다. 공격자는 피해자의 브라우저에서 요청을 보낼 수는 있어도, 토큰을 외부로 빼내 재사용할 수는 없다.

### BFF 프록시가 불필요한 이유

HAProxy가 `admin.example.com` 하나로 Next와 FastAPI를 묶으므로 **같은 오리진**이다. FastAPI가 설정한 쿠키를 브라우저가 Next에도, FastAPI에도 자동으로 보낸다.

Next.js Route Handler로 토큰을 감싸는 BFF 계층은 오리진이 다를 때 필요한 우회책이다. 여기서는 홉만 늘리므로 두지 않는다.

---

## 4. 쿠키 속성

```python
response.set_cookie(
    key="admin_session",
    value=access_token,
    httponly=True,          # JS 접근 차단
    secure=True,            # HTTPS 전용
    samesite="lax",         # CSRF 완화
    path="/",
    max_age=900,            # 15분
    # domain=  ← 절대 설정하지 않는다
)
```

### `domain`을 설정하지 않는 것이 핵심이다

`domain`을 생략하면 **host-only 쿠키**가 되어 `admin.example.com`에만 적용된다.

```python
domain=".example.com"   # ✗ 나중에 추가할 사용자 웹과 쿠키가 공유됨
# (생략)                # ✓ admin.example.com 전용
```

지금 편의상 `.example.com`을 넣어두면, 사용자 웹(`app.example.com`)을 추가할 때 **두 웹의 세션이 서로 덮어쓴다.** 관리자로 로그인한 상태에서 사용자 웹에 다른 계정으로 로그인하면 관리자 세션이 사라진다.

그때 되돌리려면 코드 수정뿐 아니라 **이미 발급된 쿠키 정리**까지 필요하다. 지금 생략해두면 사용자 웹 추가 시 아무 작업 없이 격리된다.

> 나중에 SSO처럼 한 번의 로그인으로 양쪽을 쓰고 싶어지면 그때 `Domain`을 붙이면 된다. 되돌리기 쉬운 방향으로 시작한다.

### `secure=True`와 개발 환경

`secure=True`인 쿠키는 HTTPS에서만 전송된다. 개발 환경이 HTTP라면 쿠키가 실리지 않아 로그인이 되지 않는다.

**개발 환경도 HTTPS로 맞춘다.** HAProxy에 자체 서명 인증서를 물리면 된다. 환경변수로 `secure`를 껐다 켰다 하면 개발에서만 재현되지 않는 버그가 생긴다.

### `samesite` 선택

| 값 | 동작 | 판단 |
|---|---|---|
| **`lax`** | 크로스사이트 POST 차단, GET 탐색은 허용 | **채택** |
| `strict` | 외부 링크로 진입 시 쿠키 미전송 | 재로그인 유발 |

`strict`가 더 안전하지만, 이메일이나 메신저 링크로 관리 페이지에 들어올 때마다 로그인 화면이 뜬다. CSRF는 8장의 Origin 검증으로 보완한다.

---

## 5. 토큰 2종 구성

| | 쿠키 이름 | 수명 | `path` |
|---|---|---|---|
| Access | `admin_session` | **15분** | `/` |
| Refresh | `admin_refresh` | **3일** | `/api/auth` |

### Refresh 쿠키의 `path`를 제한한다

refresh 토큰은 갱신 엔드포인트에만 필요하다. `path`를 좁히면 **일반 API 요청에 refresh 토큰이 실려 나가지 않는다.** 노출 표면이 줄어든다.

### 3일을 선택한 이유

관리자 세션은 권한이 크므로 짧게 가져간다. 운영자는 주 2~3회 재로그인하게 되지만, 계정 탈취 시 유효 기간이 그만큼 짧아진다. IP 제한이 상시 적용되지 않을 수 있는 상황에서는 이쪽이 안전하다.

### Refresh 토큰 회전(rotation)

refresh를 사용할 때마다 새 refresh 토큰을 발급하고 이전 것을 무효화한다.

이미 사용된 refresh 토큰이 다시 들어오면 **탈취를 의심**할 수 있고, 해당 사용자의 전체 세션을 폐기하는 대응이 가능해진다. 회전 없이는 탈취를 탐지할 방법이 없다.

### Access 토큰에 권한을 담지 않는다

access 토큰에 권한 목록을 넣으면 **권한을 회수해도 만료까지 유효**하다. 관리자가 권한을 뺐는데 그 사용자가 계속 삭제를 할 수 있다면 사고다.

access 토큰은 `user_id`만 담고, **권한은 요청마다 DB에서 조회**한다. 인덱스가 걸린 뷰 조회 한 번이므로 이 규모에서 부담이 되지 않는다.

---

## 6. Refresh 토큰 DB 저장

JWT만으로는 **로그아웃이 불가능하다.** 발급된 토큰은 만료 전까지 유효하기 때문이다.

### 이 테이블로 가능해지는 것

| 기능 | 방법 |
|---|---|
| 로그아웃 | `revoked_at` 설정 |
| 전체 세션 종료 | 계정 탈취 의심 시 해당 사용자 전부 폐기 |
| 활성 세션 목록 | 관리 화면에서 조회 · 개별 폐기 |
| 클라이언트 구분 | `client` 컬럼 — 모바일 추가 시 그대로 활용 |

### 반영 시점

| 대상 | 반영 시점 |
|---|---|
| 권한 변경 | **즉시** (요청마다 조회) |
| 세션 폐기 | **최대 15분** (access 만료 후 refresh 실패) |

즉시 차단이 필요한 경우(계정 탈취)에는 access 검증 시 폐기 여부를 함께 확인하는 옵션을 둘 수 있으나, 매 요청 DB 조회가 추가되므로 기본은 15분 지연을 수용한다.

### `ip` 컬럼 주의

HAProxy 뒤에 있으므로 그대로 두면 **HAProxy 컨테이너 IP가 기록된다.**

```bash
uvicorn app.main:app \
  --proxy-headers \
  --forwarded-allow-ips="10.0.0.0/8"    # HAProxy 대역만
```

`--forwarded-allow-ips="*"`로 두면 아무나 `X-Forwarded-For`를 위조할 수 있다. **반드시 실제 프록시 대역만 지정한다.**

---

## 7. SSR에서의 함정

Next.js SSR에서 반드시 걸리는 두 가지다.

### (1) Server Component에서 쿠키가 자동 전달되지 않는다

브라우저에서 Next 서버까지는 쿠키가 오지만, **Next 서버가 FastAPI를 호출할 때는 실리지 않는다.**

```ts
import { cookies } from 'next/headers'

export async function apiFetch(path: string, init?: RequestInit) {
  const cookieStore = await cookies()
  return fetch(`${process.env.API_INTERNAL_URL}${path}`, {
    ...init,
    headers: {
      ...init?.headers,
      cookie: cookieStore.toString(),   // ★ 명시적 전달
    },
    cache: 'no-store',
  })
}
```

빠뜨리면 **로컬에서는 동작하는데 배포하면 인증이 풀리는** 형태로 나타나 원인 추적이 까다롭다. 헬퍼로 감싸고 직접 `fetch`를 호출하지 않는 규칙을 세운다.

### (2) Server Component는 쿠키를 설정할 수 없다

access 토큰이 만료되어 Server Component에서 refresh를 시도해도, **일부 컨텍스트에서 `cookies().set()`이 제한될 수 있다.** Next.js 16에서는 refresh를 **Proxy가 아니라 DAL·Route Handler·Server Action**에서 처리한다.

**실제 구현 (Next.js 16 `proxy.ts`)**

```ts
// proxy.ts — 쿠키 존재 여부만 확인 (refreshToken 있으면 통과)
export async function proxy(request: NextRequest) {
  const token = request.cookies.get("accessToken")
  const refreshToken = request.cookies.get("refreshToken")

  if (!token && !refreshToken && !isPublicPath(pathname)) {
    return NextResponse.redirect(new URL("/login", request.url))
  }
  return NextResponse.next()
}
```

```ts
// lib/permissions-server.ts — 세션 검증 + refresh (layout, BFF)
async function fetchServerUserMe() {
  let token = store.get("accessToken")?.value
  if (!token) token = await refreshServerAccessToken(store)

  let res = await fetch(`${baseURL}/users/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (res.status === 401) {
    token = await refreshServerAccessToken(store)
    // ... retry once
  }
}
```

- **Proxy**: public 경로 게이트 + 쿠키 없으면 `/login` (1차)
- **DAL** (`requireServerUserMe`, `getAuthenticatedSession`): refresh 후 `/users/me` 재시도 (2차)
- **BFF** (`assertServerPermission`): 권한 검사 (3차)

> Next.js 16부터 `middleware.ts`는 [`proxy.ts`](https://nextjs.org/docs/messages/middleware-to-proxy)로 이름이 변경되었다. `export function middleware` → `export function proxy`.

### Proxy에서 권한을 판정하지 않는다

Proxy는 **매 요청 실행**된다. 여기서 DB를 조회하면 전체 응답이 느려진다.

Proxy는 **인증 여부(쿠키 존재)만** 확인하고, 권한 판정은 FastAPI가 담당한다.

---

## 8. CSRF 대응

`SameSite=Lax`가 크로스사이트 POST를 차단하므로 대부분 방어된다. 관리자 앱은 파괴적 작업이 많으므로 한 겹 더 얹는다.

### Origin 헤더 검증

```python
ALLOWED_ORIGINS = {"https://admin.example.com"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

@app.middleware("http")
async def verify_origin(request: Request, call_next):
    if request.method not in SAFE_METHODS:
        if request.headers.get("origin") not in ALLOWED_ORIGINS:
            return JSONResponse({"detail": "Origin 검증 실패"}, status_code=403)
    return await call_next(request)
```

### 함께 지킬 규칙

- **상태 변경은 반드시 POST / PATCH / PUT / DELETE로.** GET으로 상태를 바꾸면 `SameSite=Lax`의 방어가 무력화된다
- 모바일 추가 시 **Bearer 인증 요청은 이 검사에서 제외**한다 (쿠키 기반 요청에만 CSRF가 성립한다)

CSRF 토큰(double-submit)까지는 현 단계에서 과하다.

---

# Part 2 — 권한 (RBAC)

## 9. 설계 원칙

### 원칙 1 — 코드는 권한을 검사하고, 역할은 권한 묶음일 뿐이다

```python
# 나쁨 — 역할이 늘어날 때마다 코드를 고쳐야 한다
if user.role in ("admin", "operator"):
    ...

# 좋음 — 역할 정의만 DB에서 바꾸면 된다
if "scheduler:manage" in user.permissions:
    ...
```

"operator도 태스크를 취소할 수 있게 해달라"는 요청 하나에 코드 수정과 배포가 필요해서는 안 된다. 관리 화면에서 역할에 권한을 추가하면 끝나야 한다.

### 원칙 2 — 권한 판정의 정본은 백엔드다

Next.js Proxy와 화면 요소 숨김은 **사용자 경험**을 위한 것이지 보안 장치가 아니다. 모든 권한 판정은 FastAPI가 수행한다.

### 원칙 3 — 거부를 기본값으로

새 엔드포인트에서 권한 선언을 빠뜨리면 **아무도 접근하지 못하는** 상태가 되어야 하고, **누구나 접근 가능한** 상태가 되어서는 안 된다.

---

## 10. 권한 목록

**`<resource>:<action>` 형식**으로 통일한다. 현재 전부 `domain = 'admin'` 이다.

| 권한 코드 | category | domain | 설명 |
|---|---|---|---|
| `scheduler:read` | scheduler | admin | 수집 스케줄 조회 |
| `scheduler:manage` | scheduler | admin | 스케줄 생성 · 수정 · 활성화 |
| `task:read` | task | admin | 태스크 상태 조회 |
| `task:cancel` | task | admin | 태스크 취소 · 재시도 |
| `user:read` | user | admin | 사용자 목록 조회 |
| `user:manage` | user | admin | 사용자 생성 · 비활성화 |
| `role:manage` | user | admin | 역할 부여 · 권한 변경 |
| `audit:read` | audit | admin | 감사 로그 조회 |

### 명명 규칙

- **소문자 + 콜론 구분자**로 고정한다
- 리소스는 **단수형**을 쓴다
- 액션은 CRUD에 억지로 맞추지 않는다. `cancel`, `reindex` 처럼 도메인 동사가 명확하면 그대로 쓴다
- **`*` 와일드카드를 도입하지 않는다.** `scheduler:*` 같은 표현은 나중에 추가된 액션이 자동으로 부여되어 의도치 않은 권한 확대를 만든다

### `category`와 `domain`은 다른 개념이다

| 컬럼 | 용도 | 값 |
|---|---|---|
| `category` | 관리 화면 그룹핑 | `scheduler`, `task`, `user`, `audit` |
| `domain` | 클라이언트 노출 구분 | `admin` (현재), `user` (추후) |

두 개념을 한 컬럼에 담으면 관리 화면을 만들 때 반드시 다시 쪼개게 된다.

### 권한 목록은 코드가 정본이다

관리자가 화면에서 새 권한을 만들지 않는다. **코드에 없는 권한은 아무 의미가 없기 때문이다.** 애플리케이션 기동 시 시드로 동기화한다.

```python
ALL_PERMISSIONS = [
    # (code, name, category, domain)
    ("scheduler:read",   "스케줄 조회",   "scheduler", "admin"),
    ("scheduler:manage", "스케줄 관리",   "scheduler", "admin"),
    ("task:read",        "태스크 조회",   "task",      "admin"),
    ("task:cancel",      "태스크 취소",   "task",      "admin"),
    ("user:read",        "사용자 조회",   "user",      "admin"),
    ("user:manage",      "사용자 관리",   "user",      "admin"),
    ("role:manage",      "역할 관리",     "user",      "admin"),
    ("audit:read",       "감사 로그 조회", "audit",     "admin"),
]
```

**코드에서 사라진 권한을 자동 삭제하지 않는다.** 배포 실수나 브랜치 차이로 권한이 날아가면 역할 매핑까지 CASCADE로 삭제된다. 정리는 수동으로 한다.

---

## 11. 역할 구성

구분선은 명확하다.

> **`operator` = 시스템 운영 / `admin` = 계정 · 감사 관리**

| 권한 코드 | `admin` | `operator` |
|---|:---:|:---:|
| `scheduler:read` | O | O |
| `scheduler:manage` | O | O |
| `task:read` | O | O |
| `task:cancel` | O | O |
| `user:read` | O | - |
| `user:manage` | O | - |
| `role:manage` | O | - |
| `audit:read` | O | - |

두 역할 모두 `is_system = true`로 두어 관리 화면에서 삭제되지 않게 한다.

### `task:cancel`이 operator에 있는 이유

**되돌릴 수 있는 작업**이기 때문이다. 취소한 태스크는 다시 등록하면 된다. 반면 역할 부여와 계정 비활성화는 영향 범위가 넓어 `admin`에 둔다.

### 권한 추가 시의 판단 기준

기능이 늘어날 때마다 **"되돌릴 수 있는가"**를 기준으로 operator 포함 여부를 판단하면 일관성이 유지된다.

| 성격 | 배정 |
|---|---|
| 조회 계열 | 양쪽 |
| 되돌릴 수 있는 운영 작업 | 양쪽 |
| 되돌릴 수 없는 작업 (삭제 등) | `admin`만 |
| 계정 · 권한 · 감사 | `admin`만 |

---

## 12. superuser 운영 정책

### 성격

`is_superuser`는 **개발자 전용 root 계정**이다. 운영에는 사용하지 않는다.

| 항목 | 정책 |
|---|---|
| 용도 | 개발자의 시스템 디버깅 |
| 계정 수 | **1~2개** |
| 설정 방법 | **DB 직접 쿼리** |
| API 수정 | **불가** |
| 운영 사용 | **없음** |

### 구현 — 권한 검사를 먼저, superuser는 폴백으로

```python
def has(self, *codes: str) -> bool:
    if set(codes).issubset(self.permissions):
        return True
    if self.is_superuser:
        audit.log_superuser_bypass(self.id, codes)   # ★ 폴백일 때만 기록
        return True
    return False
```

순서가 중요하다. superuser를 먼저 검사하면 **"정당한 권한으로 통과"와 "우회로 통과"가 구분되지 않아** 감사 로그가 무의미해진다.

### ⚠ fastapi-users는 기본적으로 API 수정을 허용한다

"API를 통해 수정 불가"로 정했으나, **fastapi-users의 기본 `UserUpdate` 스키마에는 `is_superuser` 필드가 포함되어 있다.** superuser 권한으로 `PATCH /users/{id}`를 호출하면 다른 계정에 superuser를 부여할 수 있다.

개발용 root 계정이 유출되면 그 계정으로 다른 계정에 superuser를 심어놓을 수 있다는 뜻이다.

```python
# schemas.py — 필드를 제거하고 미정의 필드를 거부한다
class UserUpdate(schemas.BaseUserUpdate):
    model_config = ConfigDict(extra="forbid")   # ★ 필수
    email: EmailStr | None = None
    password: str | None = None
    # is_superuser 없음
```

`extra="forbid"`를 함께 걸어야 한다. 필드만 빼고 기본값(`extra="ignore"`)으로 두면 요청이 조용히 통과하면서 무시되어, **"막았다고 생각했는데 안 막힌" 상황과 구분되지 않는다.** 거부하고 422를 반환하는 편이 명확하다.

### 개수 감시

DB 직접 수정만 허용하므로, **개수가 늘어났다는 것 자체가 이상 신호**다.

```python
# 애플리케이션 기동 시
count = await session.scalar(
    select(func.count()).select_from(User).where(User.is_superuser.is_(True))
)
if count > 2:
    logger.critical("superuser 계정이 %d개입니다. 즉시 확인이 필요합니다.", count)
```

### 테스트 계정 규칙

**통합 테스트 픽스처를 superuser로 만들지 않는다.** superuser로 테스트를 돌리면 모든 권한 검사가 통과하므로, 권한 선언 누락을 영원히 발견하지 못한다.

---

## 13. 부트스트랩

`users.role` 컬럼이 없고 `user_roles`가 비어 있으므로, **배포 직후에는 아무도 `admin` 역할이 없다.** `role:manage` 권한이 있어야 역할을 부여할 수 있는데 그 권한을 가진 사람이 없는 교착 상태다.

### 권장 — CLI 시드 명령

```bash
python -m app.cli grant-role --email ops@example.com --role admin
```

superuser 로그인 없이 초기 설정이 가능하고, 재해 복구 시에도 쓸 수 있다. **superuser는 정말 디버깅 용도로만 남는다.**

### 대안 — superuser 경유

```
1. 개발자가 DB 직접 쿼리로 is_superuser = true 설정
2. 그 계정으로 로그인 → superuser 우회로 role:manage 통과
3. 운영 담당자 계정에 admin 역할 부여
4. 이후 운영은 admin 역할 계정으로 수행
```

두 경로 중 하나는 반드시 준비해두어야 한다. 없으면 배포 후 아무도 관리 기능을 쓸 수 없다.

---

## 14. FastAPI 구현

### 현재 사용자 모델

```python
@dataclass
class CurrentUser:
    id: UUID
    email: str
    is_active: bool
    is_superuser: bool
    permissions: frozenset[str] = field(default_factory=frozenset)

    def has(self, *codes: str) -> bool:
        if set(codes).issubset(self.permissions):
            return True
        if self.is_superuser:
            audit.log_superuser_bypass(self.id, codes)
            return True
        return False
```

### 인증 의존성

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
        is_superuser=user.is_superuser,
        permissions=frozenset(perms),
    )
```

### 권한 의존성

```python
def require(*codes: str):
    async def dependency(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if not user.has(*codes):
            raise HTTPException(403, f"권한이 없습니다: {', '.join(sorted(codes))}")
        return user
    return dependency
```

### 사용

```python
@router.get("/api/admin/scheduler")
async def list_schedules(user: CurrentUser = Depends(require("scheduler:read"))):
    ...

@router.post("/api/admin/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: UUID,
    user: CurrentUser = Depends(require("task:cancel")),
):
    ...

# 라우터 단위 기본 권한
admin_router = APIRouter(
    prefix="/api/admin",
    dependencies=[Depends(get_current_user)],
)
```

### 401과 403을 구분한다

| 코드 | 의미 | 프론트 동작 |
|---|---|---|
| **401** | 인증되지 않음 | 로그인 페이지로 이동 |
| **403** | 인증됐으나 권한 없음 | 권한 없음 안내 표시 |

뭉뚱그리면 권한 없는 사용자가 **로그인 → 다시 거부 → 무한 반복**에 빠진다.

### 권한 선언 누락 방지

```python
def test_all_routes_declare_permission():
    """인증·권한 의존성이 없는 라우트가 있으면 실패한다."""
    PUBLIC = {"/health", "/api/auth/jwt/login", "/docs", "/openapi.json"}
    # app.routes 를 순회하며 dependencies 검사
```

기능이 늘어날수록 권한 선언을 빠뜨리는 사고가 생긴다. **이 테스트 하나가 그 사고를 전부 막는다.** 단, 테스트 계정이 superuser가 아니어야 의미가 있다.

### `/api/users/me` 응답

```json
{
  "id": "...",
  "email": "...",
  "is_superuser": false,
  "roles": ["operator"],
  "permissions": ["scheduler:read", "scheduler:manage", "task:read", "task:cancel"]
}
```

프론트엔드는 **역할이 아니라 권한 배열을 기준으로** UI를 구성한다. 그래야 백엔드와 동일한 규칙이 적용된다.

> 사용자 웹 추가 시 `?scope=user` 파라미터로 도메인 필터를 붙인다. 지금은 불필요하다.

---

## 15. 감사 로그

### 보관 정책

**기한 없이 보관한다.** 데이터 누적량을 보고 파티셔닝을 판단한다.

감사 대상이 역할 부여 · 계정 변경 · 파괴적 작업 · superuser 우회로 한정되므로 연간 수천 건 수준이다. 수백만 건이 되기 전까지 일반 테이블로 충분하다.

> **참고:** PostgreSQL은 일반 테이블을 나중에 파티션 테이블로 변경할 수 없다. 새 파티션 테이블을 만들고 데이터를 옮긴 뒤 이름을 교체해야 하며, 그 사이 쓰기를 멈춰야 한다. 지금은 인덱스만 제대로 잡아두면 된다.

### 기록 대상

- **superuser 우회 발생** ★
- 역할 부여 · 회수
- 역할의 권한 변경
- 사용자 활성화 · 비활성화
- API 키 발급 · 폐기
- 권한 거부(403) — 공격 탐지에 유용
- 파괴적 작업

### 기록하지 않을 것

일반 조회는 남기지 않는다. 볼륨만 커지고 가치가 낮다.

### superuser 우회는 알림으로 연결한다

운영에서 사용되지 않기로 한 기능이므로, **우회가 발생했다는 것 자체가 이상 신호**다. 로그만 남기지 말고 알림 채널에 연결한다.

---

# Part 3 — 실행

## 16. 전체 스키마

`users.id`가 UUID이므로 참조 컬럼이 전부 UUID로 통일된다.

> Alembic 마이그레이션 파일은 CLI로 직접 생성한다.

```sql
-- ============ 권한 ============

CREATE TABLE roles (
    id          UUID PRIMARY KEY DEFAULT uuidv7(),
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    description TEXT,
    is_system   BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE permissions (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,          -- 화면 그룹핑
    domain      TEXT NOT NULL,          -- 'admin' (현재) | 'user' (추후)
    description TEXT
);

CREATE TABLE role_permissions (
    role_id         UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_code TEXT NOT NULL REFERENCES permissions(code) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_code)
);
CREATE INDEX idx_role_permissions_permission ON role_permissions (permission_code);

CREATE TABLE user_roles (
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id     UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    granted_by  UUID REFERENCES users(id),
    PRIMARY KEY (user_id, role_id)
);
CREATE INDEX idx_user_roles_role ON user_roles (role_id);

CREATE VIEW user_permissions AS
SELECT DISTINCT ur.user_id, rp.permission_code
FROM user_roles ur
JOIN role_permissions rp ON rp.role_id = ur.role_id;

-- ============ 인증 ============

CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,       -- 원문 저장 금지
    client      TEXT NOT NULL,              -- 'admin_web' | 'user_web' | 'mobile'
    user_agent  TEXT,
    ip          INET,
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_refresh_tokens_user
    ON refresh_tokens (user_id) WHERE revoked_at IS NULL;

-- ============ 감사 ============

CREATE TABLE audit_logs (
    id          UUID PRIMARY KEY DEFAULT uuidv7(),
    actor_id    UUID REFERENCES users(id),
    action      TEXT NOT NULL,              -- 'role.grant', 'superuser.bypass'
    target_type TEXT,
    target_id   TEXT,
    detail      JSONB NOT NULL DEFAULT '{}',
    ip          INET,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_logs_actor   ON audit_logs (actor_id, created_at DESC);
CREATE INDEX idx_audit_logs_created ON audit_logs (created_at DESC);
CREATE INDEX idx_audit_logs_action  ON audit_logs (action, created_at DESC);

-- ============ MCP (테이블만 미리 생성) ============

CREATE TABLE api_keys (
    id           UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    key_hash     TEXT NOT NULL UNIQUE,
    scopes       TEXT[] NOT NULL DEFAULT '{}',   -- 사용자 권한의 부분집합
    last_used_at TIMESTAMPTZ,
    expires_at   TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `api_keys.scopes`의 의미

MCP 구현 시 사용한다. 키의 유효 권한은 **사용자 권한과의 교집합**으로 제한된다.

```
유효 권한 = 사용자 권한 ∩ API 키 scopes
```

사용자가 admin이어도, 키에 `scheduler:read`만 담겨 있으면 그 키로는 조회만 가능하다. **키가 유출되어도 피해 범위가 scope로 제한된다.**

---

## 17. Phase 계획

| Phase | 작업 | 비고 |
|---|---|---|
| **1** | 스키마 생성 + 권한 · 역할 시드 + CLI 부트스트랩 명령 | `users.role` 이관 불필요 |
| **2** | 백엔드 — `require()`, superuser 가드, `UserUpdate` 필드 제거, `/users/me`, 쿠키 인증, refresh 회전, 감사 로그 | dual-mode refresh 제외 |
| **3** | `nextjs-frontend` → `nextjs-admin-frontend` **rename** + 사용자 코드 정리 | 분리 아님 |
| **4** | 관리자 웹 권한 UX — `proxy.ts`, Forbidden 화면, 권한 기반 nav | |
| **5** | (나중) 사용자 웹 · 모바일 · MCP 권한 | |

### Phase 3이 축소된 이유

당초 계획은 `nextjs-frontend`(사용자)와 `nextjs-admin-frontend`(관리자)를 나누는 작업이었으나, **관리자만 개발한다면 나눌 대상이 없다.**

기존 admin 코드가 이미 그 앱에 있으므로 `git mv`로 rename하고 사용자 라우트만 정리하면 된다. **이동 비용이 0**이다. 포트도 3000을 유지한다. HAProxy가 서브도메인으로 구분하므로 포트 번호는 외부에서 보이지 않는다.

---

## 18. 향후 확장

### 사용자 웹 추가 시

```
admin.example.com  →  admin_session  / admin_refresh   (host-only)
app.example.com    →  session        / refresh         (host-only)
```

**`domain`을 생략해뒀으므로 별도 작업 없이 격리된다.** HAProxy에 백엔드를 추가하고 `ALLOWED_ORIGINS`에 한 줄 더하면 된다.

권한은 `domain = 'user'` 행을 추가하고, `/api/users/me`에 `?scope=` 필터를 붙인다.

#### ⚠ HAProxy 규칙을 반드시 함께 활성화한다

**잊으면 관리자 IP 제한이 통째로 우회된다.** 지금 설정 파일에 주석으로 남겨둔다.

```haproxy
# 현재: 관리자 서브도메인만 운영
acl host_admin   hdr(host) -i admin.example.com
acl admin_ip_ok  src -f /etc/haproxy/admin_allowlist.acl
http-request deny deny_status 403 if host_admin !admin_ip_ok

# TODO: 사용자 서브도메인(app.example.com) 추가 시 아래를 반드시 활성화한다.
#   없으면 사용자 서브도메인을 통해 관리자 API에 IP 제한 없이 도달할 수 있다.
# acl host_app       hdr(host) -i app.example.com
# acl path_api_admin path_beg /api/admin/
# http-request deny deny_status 404 if host_app path_api_admin
```

### 모바일 추가 시

| 클라이언트 | 토큰 전달 | 저장 위치 |
|---|---|---|
| 웹 (관리자 · 사용자) | 쿠키 자동 전송 | HttpOnly 쿠키 |
| 모바일 | `Authorization: Bearer` | **iOS Keychain / Android Keystore** |

`AsyncStorage`나 `SharedPreferences`에 저장하면 안 된다. 루팅 · 탈옥 기기에서 평문으로 읽힌다.

`/api/auth/jwt/refresh`를 dual-mode(쿠키 + Bearer/body)로 확장한다. `refresh_tokens.client` 컬럼이 이미 있으므로 스키마 변경은 없다.

권한 갱신 시점(앱 포그라운드 복귀, 토큰 갱신 시)을 정해둔다.

### MCP 추가 시

`api_keys` 테이블이 이미 있다. 노출 도구는 **읽기 전용을 기본**으로 한다. 수집한 외부 데이터가 LLM 컨텍스트에 들어가므로 프롬프트 인젝션 표면이 넓다.

---

## 19. 체크리스트

### 인증 — 쿠키

- [ ] `httponly=True`, `secure=True`, `samesite="lax"`
- [ ] **`domain` 인자를 넘기지 않음** (host-only)
- [ ] access `path="/"`, refresh `path="/api/auth"`
- [ ] 쿠키 이름 `admin_session` / `admin_refresh`
- [ ] 개발 환경도 HTTPS (HAProxy 자체 서명 인증서)

### 인증 — 토큰

- [ ] access 15분 / refresh 3일
- [ ] access 페이로드에 권한 미포함 (`user_id`만)
- [ ] refresh 회전 구현
- [ ] 재사용 감지 시 해당 사용자 전체 세션 폐기
- [ ] 로그아웃 시 `revoked_at` 설정
- [ ] uvicorn `--proxy-headers --forwarded-allow-ips` (프록시 대역만)

### 권한 — 스키마

- [ ] 테이블 4종 + `user_permissions` 뷰
- [ ] `permissions.category` / `permissions.domain` **분리**
- [ ] `roles.is_system = true` (admin, operator)
- [ ] `refresh_tokens` / `audit_logs` / `api_keys`

### 권한 — 백엔드

- [ ] 권한 8종 시드, 기동 시 동기화 (자동 삭제 안 함)
- [ ] `require()` 의존성, 401 / 403 구분
- [ ] **`UserUpdate` 스키마에서 `is_superuser` 제거 + `extra="forbid"`**
- [ ] superuser 우회 시 감사 로그 (권한 검사 후 폴백)
- [ ] superuser 계정 수 감시 (기동 시)
- [ ] **라우트 권한 선언 테스트** (픽스처는 superuser 아님)
- [ ] CLI 부트스트랩 명령 (`grant-role`)

### CSRF

- [ ] 상태 변경 요청의 Origin 헤더 검증
- [ ] 상태 변경은 POST / PATCH / PUT / DELETE로만

### Next.js

- [ ] Server Component fetch 헬퍼 — 쿠키 명시 전달
- [ ] 직접 `fetch` 호출 금지 규칙
- [ ] `proxy.ts` — 쿠키 존재 여부 게이트 (refreshToken 있으면 통과)
- [ ] DAL(`permissions-server`)에서 refresh + `/users/me` 재시도
- [ ] Proxy는 인증 여부만, 권한 판정은 FastAPI
- [ ] 권한 배열 기반 UI 분기 (역할 아님)
- [ ] 403 전용 화면 (로그인 리다이렉트 금지)

### 운영

- [ ] superuser 우회 알림 채널 연결
- [ ] HAProxy에 사용자 서브도메인 TODO 주석
- [ ] 실제 도메인 확정 후 3곳 반영 (쿠키 · `ALLOWED_ORIGINS` · HAProxy)

---

## 20. 부록 — 흔한 실수

| 실수 | 결과 |
|---|---|
| `domain=".example.com"` 설정 | 사용자 웹 추가 시 세션 충돌 |
| localStorage에 토큰 저장 | XSS 한 번에 관리자 권한 탈취 |
| access 토큰에 권한 담기 | 권한 회수가 만료까지 미반영 |
| Server Component에서 쿠키 미전달 | 배포 후에만 인증 실패 |
| Server Component에서 refresh 시도 | 쿠키 설정 불가로 무한 리다이렉트 |
| Proxy에서 권한 판정 | 매 요청 DB 조회로 전체 지연 |
| `--forwarded-allow-ips="*"` | IP 위조로 감사 로그 오염 |
| 개발만 HTTP | 운영에서만 발생하는 쿠키 버그 |
| GET으로 상태 변경 | `SameSite=Lax` 방어 무력화 |
| refresh 토큰 DB 미저장 | 로그아웃 불가 |
| **`UserUpdate`에 `is_superuser` 방치** | **API로 superuser 부여 가능** |
| superuser를 먼저 검사 | 감사 로그에서 우회 구분 불가 |
| 테스트 픽스처가 superuser | 권한 누락을 영원히 발견 못 함 |
| 코드에서 역할을 직접 검사 | 역할 추가 시 코드 수정 |
| 부트스트랩 경로 미준비 | 배포 후 아무도 관리 기능 사용 불가 |
| `scheduler:*` 와일드카드 | 신규 액션이 자동 부여됨 |

---

## 관련 문서

- `authorization-guide.md` — RBAC 일반 설계 원칙
- `collector-storage-service-architecture.md` — 수집 + 저장 서비스
