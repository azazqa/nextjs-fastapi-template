# 후속 조치 — N6 · N7 · N8 (프론트엔드 쿠키 처리 중복)

> 작성일: 2026-09-03
> 대상: `azazqa/nextjs-fastapi-template` commit `79b1a86`
> 범위: `nextjs-frontend` 쿠키 설정·삭제 경로의 중복 정리

---

## 개요

`COOKIE_SECURE` 조사 과정에서 프론트엔드의 쿠키 처리가 여러 곳에 흩어져 있음을 확인했다.

| # | 항목 | 위치 | 등급 |
|---|---|---|---|
| **N6** | 쿠키 옵션이 3벌로 중복 | `lib/auth-cookies.ts` · `login-action.ts` ×2 | 중 |
| **N7** | 토큰 수명(TTL)이 3벌로 중복 | 백엔드 설정 · `lib/auth-cookies.ts` · `login-action.ts` | 낮 |
| **N8** | 로그아웃이 같은 엔드포인트를 2회 호출 | `logout-action.ts` | 낮 |

세 건 모두 **파일 3개 수정으로 함께 해결**된다.

### 전제 — 범위에서 제외한 것

**`NODE_ENV` 기반 Secure 판정은 현재 정상 동작한다.** 개발은 `pnpm run dev`(`NODE_ENV=development` → `secure: false`), 배포는 compose(`NODE_ENV=production` → `secure: true`)로 분리되어 있어 워크플로상 문제가 없다. 보류 사유는 뒤에 정리한다.

**`__Host-` 접두사 전환은 이번 범위에서 제외한다.**

---

## 중복 현황

| 중복 대상 | 벌 수 | 위치 |
|---|---|---|
| 쿠키 옵션 (`httpOnly`·`secure`·`sameSite`·`path`) | **3** | `auth-cookies.ts` (비공개) · `login-action.ts` accessToken · `login-action.ts` refreshToken |
| access TTL | **3** | 백엔드 `ACCESS_TOKEN_EXPIRE_SECONDS` · `ACCESS_MAX_AGE` · `login-action.ts` 인라인 `3600` |
| refresh TTL | **3** | 백엔드 `REFRESH_TOKEN_EXPIRE_SECONDS` · `REFRESH_MAX_AGE` · `login-action.ts` 인라인 `24 * 3600` |
| 쿠키 삭제 | **2** | `clearAuthCookies()` · `logout-action.ts` 인라인 |
| 로그아웃 호출 | **2** | `logout-action.ts` 안에서 같은 엔드포인트 2회 |

### 근본 원인 — `cookieOptions`가 export되지 않았다

```ts
// lib/auth-cookies.ts
const cookieOptions = {          // ← export 없음
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
};
```

`login-action.ts`가 **import할 수 없어서 복사한 것**이다. 원인이 명확하고, 수정은 한 단어에서 시작한다.

> `lib/clientConfig.ts`의 401 인터셉터는 이미 `applyRefreshCookies()`를 재사용하고 있어 중복이 없다. 문제는 로그인·로그아웃 경로에 한정된다.

---

# N6. 쿠키 옵션이 3벌로 중복된다

## 현황

```ts
// login-action.ts — accessToken
cookieStore.set("accessToken", data.access_token, {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax",
  maxAge: 3600,
  path: "/",
});

// login-action.ts — refreshToken (같은 파일에서 한 번 더)
cookieStore.set("refreshToken", refreshToken, {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax",
  maxAge: 24 * 3600,
  path: "/",
});
```

`lib/auth-cookies.ts`의 `cookieOptions`와 **글자 단위로 동일**하다.

## 영향

**쿠키 속성을 바꿀 때 조용히 어긋난다.**

`sameSite`를 `strict`로 조이거나 `path`를 좁히는 변경을 `lib/auth-cookies.ts`에서만 하면, **로그인 경로에는 반영되지 않는다.** 그 결과 다음이 발생한다.

| 시점 | 쿠키 속성 |
|---|---|
| 로그인 직후 | 옛 속성 (`login-action.ts`) |
| 토큰 갱신 후 | 새 속성 (`applyRefreshCookies`) |

브라우저는 **이름·도메인·경로 조합이 다르면 별개의 쿠키로 취급**한다. 속성이 갈리면 같은 이름의 쿠키가 둘 저장되거나, `clearAuthCookies()`의 삭제가 한쪽만 지우는 상황이 생긴다. 로그아웃했는데 세션이 남는 형태로 드러나며, 재현 조건이 "로그인 후 갱신을 한 번 거친 경우"라 추적이 어렵다.

**이번 정리의 주된 목적이 이것이다.** 나머지 둘은 부수적이다.

---

# N7. 토큰 수명이 3벌로 중복된다

## 현황

```python
# 백엔드 — app/config.py
ACCESS_TOKEN_EXPIRE_SECONDS: int = 3600
REFRESH_TOKEN_EXPIRE_SECONDS: int = 24 * 3600
```

```ts
// lib/auth-cookies.ts
export const ACCESS_MAX_AGE = 3600;
export const REFRESH_MAX_AGE = 24 * 3600;
```

```ts
// login-action.ts — 인라인
maxAge: 3600,        // 1h; align with backend ACCESS_TOKEN_EXPIRE_SECONDS
maxAge: 24 * 3600,   // 1d; align with backend REFRESH_TOKEN_EXPIRE_SECONDS
```

주석이 "백엔드와 맞추라"고 안내하고 있다는 것 자체가 **자동화되지 않은 동기화**임을 보여준다.

## 영향

백엔드에서 `ACCESS_TOKEN_EXPIRE_SECONDS`를 900(15분)으로 줄이면 프론트 두 곳은 여전히 3600을 쓴다.

| 방향 | 결과 |
|---|---|
| 쿠키 수명 > 토큰 수명 | 쿠키는 남아 있는데 토큰이 만료 → 매 요청이 401 후 refresh를 탄다 |
| 쿠키 수명 < 토큰 수명 | 쿠키가 먼저 사라져 조기 재인증 |

둘 다 refresh 경로가 흡수하므로 **장애로는 이어지지 않는다.** 다만 불필요한 왕복이 생기고, 원인이 로그에 드러나지 않는다.

## 해결 방향 — 설정을 맞추지 말고 토큰에서 도출한다

액세스·리프레시 토큰 모두 JWT이고 `exp` 클레임을 담고 있다.

```python
# 백엔드 — 리프레시 토큰 페이로드
payload = {"sub": ..., "type": "refresh", "jti": ..., "iat": ..., "exp": ...}
```

**토큰에서 `exp`를 읽어 쿠키 수명을 정하면 설정 동기화 자체가 필요 없어진다.** 백엔드 값을 바꿔도 프론트가 자동으로 따라간다.

서명 검증은 하지 않는다. **쿠키 만료 시각을 정하는 힌트로만 쓰므로 보안 판단이 아니며**, 값이 조작되어도 쿠키가 일찍/늦게 사라질 뿐 인증 자체는 백엔드가 검증한다. 파싱 실패 시 상수로 폴백한다.

---

# N8. 로그아웃이 같은 엔드포인트를 2회 호출한다

## 현황

```ts
// logout-action.ts
if (baseURL && refresh) {
  await fetch(`${baseURL}/auth/jwt/logout`, {
    method: "POST",
    headers: refresh ? { Cookie: `refreshToken=${encodeURIComponent(refresh)}` } : {},
    cache: "no-store",
  });                                   // ① 쿠키만 전달
}

if (token) {
  await authJwtLogout({
    headers: { Authorization: `Bearer ${token}` },
  });                                   // ② Bearer 만 전달
}
```

H1 수정으로 `/auth/jwt/logout`이 하나가 되면서 **두 호출이 같은 핸들러로 간다.**

```python
# 백엔드 — routes/auth_refresh.py
auth = request.headers.get("Authorization")
if auth and auth.lower().startswith("bearer "):
    ...
    await strategy.destroy_token(token, user)      # denylist 등록

refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
if refresh_token:
    await revoke_refresh_token(db, refresh_token)  # 리프레시 폐기
```

| 호출 | Authorization | Cookie | 실제로 수행되는 일 |
|---|---|---|---|
| ① | 없음 | 있음 | 리프레시 폐기만 |
| ② | 있음 | 없음 | denylist 등록만 |

**각각 절반씩 수행한다.** 헤더를 함께 보내면 한 번에 끝난다.

## 두 번째 문제 — 실패 시 로그아웃되지 않는다

```ts
await fetch(...)          // 예외를 잡지 않는다
...
cookieStore.delete("accessToken");
cookieStore.delete("refreshToken");
redirect(`/login`);
```

백엔드가 응답하지 않거나 네트워크 오류가 나면 **`fetch`가 던지고 쿠키 삭제·리다이렉트에 도달하지 못한다.** 사용자는 로그아웃 버튼을 눌렀는데 아무 일도 일어나지 않은 것처럼 보이고, 세션 쿠키는 그대로 남는다.

**서버 폐기에 실패해도 로컬 세션은 반드시 정리되어야 한다.**

## 세 번째 — 쿠키 삭제가 중복이다

`clearAuthCookies()`가 정확히 같은 일을 하는데 재사용하지 않고 `delete`를 두 번 직접 호출한다.

---

# 통합 수정안

## 1. `lib/auth-cookies.ts` — 전체 교체

```ts
import { cookies } from "next/headers";

import { readSetCookie } from "@/lib/parse-set-cookie";

type CookieStore = Awaited<ReturnType<typeof cookies>>;

/** JWT 파싱 실패 시에만 사용하는 폴백 값. 정상 경로에서는 토큰의 exp 를 따른다. */
export const ACCESS_MAX_AGE_FALLBACK = 3600;
export const REFRESH_MAX_AGE_FALLBACK = 24 * 3600;

/** 모든 인증 쿠키의 단일 속성 정의. 쿠키 속성 변경은 이 객체만 수정한다. */
export const cookieOptions = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
};

/**
 * JWT 의 exp 로 쿠키 수명을 계산한다.
 * 서명은 검증하지 않는다 — 만료 시각 힌트로만 쓰이며 인증 판단은 백엔드가 한다.
 */
function maxAgeFromJwt(token: string, fallback: number): number {
  try {
    const segment = token.split(".")[1];
    if (!segment) return fallback;
    const payload = JSON.parse(
      Buffer.from(segment, "base64url").toString("utf8"),
    );
    const ttl = Number(payload.exp) - Math.floor(Date.now() / 1000);
    return Number.isFinite(ttl) && ttl > 0 ? Math.floor(ttl) : fallback;
  } catch {
    return fallback;
  }
}

export function setAccessCookie(store: CookieStore, token: string): void {
  store.set("accessToken", token, {
    ...cookieOptions,
    maxAge: maxAgeFromJwt(token, ACCESS_MAX_AGE_FALLBACK),
  });
}

export function setRefreshCookie(store: CookieStore, token: string): void {
  store.set("refreshToken", token, {
    ...cookieOptions,
    maxAge: maxAgeFromJwt(token, REFRESH_MAX_AGE_FALLBACK),
  });
}

export async function clearAuthCookies(store?: CookieStore): Promise<void> {
  const cookieStore = store ?? (await cookies());
  for (const name of ["accessToken", "refreshToken"]) {
    try {
      cookieStore.delete(name);
    } catch {
      // Route handler 컨텍스트에서 삭제가 금지될 수 있다
    }
  }
}

export async function applyRefreshCookies(
  store: CookieStore,
  data: { access_token?: string; refresh_token?: string },
): Promise<string | null> {
  if (!data.access_token) return null;

  try {
    setAccessCookie(store, data.access_token);
    if (data.refresh_token) {
      setRefreshCookie(store, data.refresh_token);
    }
  } catch {
    // Route handler 컨텍스트에서는 set 이 금지될 수 있다.
    // 이번 요청에 한해 토큰은 여전히 유효하므로 값은 반환한다.
  }

  return data.access_token;
}

export async function refreshServerAccessToken(
  store?: CookieStore,
): Promise<string | null> {
  const cookieStore = store ?? (await cookies());
  const refresh = cookieStore.get("refreshToken")?.value;
  if (!refresh) return null;

  const baseURL = process.env.API_BASE_URL;
  if (!baseURL) return null;

  try {
    const res = await fetch(`${baseURL}/auth/jwt/refresh`, {
      method: "POST",
      headers: { Cookie: `refreshToken=${encodeURIComponent(refresh)}` },
      cache: "no-store",
    });
    if (!res.ok) return null;

    const data = (await res.json()) as { access_token?: string };
    const rotatedRefresh = readSetCookie(res.headers, "refreshToken");
    return applyRefreshCookies(cookieStore, {
      access_token: data.access_token,
      refresh_token: rotatedRefresh,
    });
  } catch {
    return null;
  }
}
```

### 기존 export와의 호환

| 심볼 | 처리 |
|---|---|
| `clearAuthCookies` | 유지 (`permissions-server.ts` · `clientConfig.ts` 사용) |
| `applyRefreshCookies` | 유지 (`clientConfig.ts` 사용), 내부만 헬퍼로 교체 |
| `refreshServerAccessToken` | 유지 (`permissions-server.ts` 사용) |
| `ACCESS_MAX_AGE` · `REFRESH_MAX_AGE` | **외부 사용처 없음** — `*_FALLBACK`으로 개명 |
| `cookieOptions` · `setAccessCookie` · `setRefreshCookie` | **신규 export** |

개명한 두 상수는 저장소 전체에서 참조가 없음을 확인했다. 깨지는 import는 없다.

## 2. `components/actions/login-action.ts`

```diff
 import { readSetCookie } from "@/lib/parse-set-cookie";
+import { setAccessCookie, setRefreshCookie } from "@/lib/auth-cookies";
```

```diff
     const cookieStore = await cookies();
-    cookieStore.set("accessToken", data.access_token, {
-      httpOnly: true,
-      secure: process.env.NODE_ENV === "production",
-      sameSite: "lax",
-      maxAge: 3600, // 1h; align with backend ACCESS_TOKEN_EXPIRE_SECONDS
-      path: "/",
-    });
+    setAccessCookie(cookieStore, data.access_token);
```

```diff
-    cookieStore.set("refreshToken", refreshToken, {
-      httpOnly: true,
-      secure: process.env.NODE_ENV === "production",
-      sameSite: "lax",
-      maxAge: 24 * 3600, // 1d; align with backend REFRESH_TOKEN_EXPIRE_SECONDS
-      path: "/",
-    });
+    setRefreshCookie(cookieStore, refreshToken);
```

## 3. `components/actions/logout-action.ts` — 전체 교체

```ts
"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { clearAuthCookies } from "@/lib/auth-cookies";

export async function logout() {
  const cookieStore = await cookies();
  const token = cookieStore.get("accessToken")?.value;
  const refresh = cookieStore.get("refreshToken")?.value;
  const baseURL = process.env.API_BASE_URL;

  if (baseURL && (token || refresh)) {
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    if (refresh) headers.Cookie = `refreshToken=${encodeURIComponent(refresh)}`;

    try {
      // Authorization 과 Cookie 를 함께 보내 한 번의 호출로
      // 액세스 토큰 denylist 등록과 리프레시 토큰 폐기를 모두 수행한다.
      await fetch(`${baseURL}/auth/jwt/logout`, {
        method: "POST",
        headers,
        cache: "no-store",
      });
    } catch {
      // 서버 폐기에 실패해도 로컬 세션은 반드시 정리한다
    }
  }

  await clearAuthCookies(cookieStore);
  redirect("/login");
}
```

`authJwtLogout`(생성된 OpenAPI 클라이언트) import가 불필요해지므로 제거한다.

> **주의:** `redirect()`는 Next.js 내부적으로 예외를 던져 동작한다. 반드시 `try` 블록 **바깥**에 두어야 한다. 위 코드는 `fetch`만 감싸고 있어 문제없다.

---

# 관련 관찰 (이번 범위 외)

**리프레시 호출 로직이 2벌 존재한다.**

| 위치 | 용도 |
|---|---|
| `lib/auth-cookies.ts` → `refreshServerAccessToken()` | 레이아웃·BFF에서 세션 복구 |
| `lib/clientConfig.ts` → 401 인터셉터 | 생성된 클라이언트의 자동 재시도 |

둘 다 `POST /auth/jwt/refresh` → 응답 파싱 → `applyRefreshCookies()`를 독립적으로 구현하고 있다. 쿠키 옵션 중복은 아니지만 **같은 계열의 문제**다.

인터셉터가 `refreshServerAccessToken()`을 호출하도록 통합할 수 있으나, 재시도 로직(`_retry` 플래그)과 얽혀 있어 별도 작업으로 다루는 편이 안전하다. **N6~N8 적용 후 판단한다.**

---

# 보류 — `NODE_ENV` 기반 Secure 판정

## 현재는 정상 동작한다

| 환경 | `NODE_ENV` | `secure` | 접속 | 결과 |
|---|---|---|---|---|
| `pnpm run dev` | development | `false` | `http://192.168.50.220:3000` | 정상 |
| compose 배포 | production | `true` | HTTPS | 정상 |

개발과 배포가 분리되어 있어 문제가 없다.

## 그럼에도 나중에 분리하면 좋은 이유

`NODE_ENV`는 Next.js의 **빌드 최적화 스위치**이지 전송 보안 스위치가 아니다. 지금은 두 조건이 우연히 일치할 뿐이다.

| 상황 | `NODE_ENV=production` | HTTPS |
|---|---|---|
| 현재 배포 | ✅ | ✅ 일치 |
| 사내망 HTTP 배포 | ✅ | ❌ **불일치 → 쿠키 유실** |
| compose 로컬 기동 + LAN IP 접속 | ✅ | ❌ 불일치 |

두 번째 줄이 실제 위험이다. 내부망에 HTTP로 올리는 순간 **로그인이 성공했는데 세션이 남지 않는** 증상이 나타나고, 서버 로그에는 아무 오류도 남지 않는다.

## 분리가 필요해지면

N6 적용으로 `cookieOptions`가 한 곳에 모이므로, **그때 한 줄만 바꾸면 된다.**

```ts
secure: process.env.COOKIE_SECURE !== "false",   // 기본 true, 명시적으로만 끔
```

지금 하지 않아도 **중복만 제거해두면 나중 비용이 한 줄로 줄어든다.** 그것이 이번 정리의 실질적 이득이다.

---

# 적용 순서

| 순서 | 파일 | 작업 |
|---|---|---|
| 1 | `lib/auth-cookies.ts` | `cookieOptions` export + 헬퍼 2종 + `maxAgeFromJwt` |
| 2 | `components/actions/login-action.ts` | 인라인 `set` 2곳 → 헬퍼 호출 |
| 3 | `components/actions/logout-action.ts` | 호출 1회 통합 + `clearAuthCookies` + `try/catch` |

1번이 나머지의 전제이므로 순서를 지킨다.

# 검증

```bash
cd nextjs-frontend

pnpm run tsc          # 타입 검사 — 개명한 상수의 잔여 참조 확인
pnpm run lint
pnpm run test
```

## 수동 확인

브라우저 개발자도구 → Application → Cookies

| 확인 항목 | 기대 |
|---|---|
| 로그인 직후 `accessToken`·`refreshToken` 속성 | HttpOnly ✓, SameSite=Lax, Path=/ |
| **토큰 갱신 후 같은 쿠키의 속성** | **로그인 직후와 동일** |
| `accessToken`의 Expires | 백엔드 `ACCESS_TOKEN_EXPIRE_SECONDS`와 일치 |
| 로그아웃 후 | 두 쿠키 모두 사라짐 |
| 백엔드를 내린 상태에서 로그아웃 | **쿠키가 지워지고 `/login`으로 이동** |

마지막 항목이 N8의 핵심이다. `docker compose stop backend` 후 로그아웃을 눌러 확인한다.

## 네트워크 확인

로그아웃 시 개발자도구 Network 탭에서 **`/auth/jwt/logout` 요청이 1건**이어야 한다. 현재는 2건이다.

# 체크리스트

> 상태: **적용 완료** (2026-09-03)

- [x] `cookieOptions` export (N6)
- [x] `setAccessCookie` · `setRefreshCookie` 헬퍼 추가
- [x] `maxAgeFromJwt` 도입 — TTL 상수 동기화 제거 (N7)
- [x] `ACCESS_MAX_AGE` → `ACCESS_MAX_AGE_FALLBACK` 개명 (외부 참조 없음 확인 완료)
- [x] `login-action.ts` 인라인 `set` 2곳 제거
- [x] `applyRefreshCookies`가 헬퍼를 재사용
- [x] `logout-action.ts` 호출 1회로 통합
- [x] `logout-action.ts` `clearAuthCookies` 재사용
- [x] `logout-action.ts` `try/catch` — 서버 실패 시에도 로컬 세션 정리
- [x] `authJwtLogout` import 제거
- [x] `pnpm run tsc` 통과 · `login.test.tsx` 통과 (`lint`는 typescript-eslint/TS7 사전 이슈로 미통과; password-reset 테스트 실패는 본 변경 범위 밖)
- [ ] 수동 확인 5항목

---

## 관련 문서

- `docs/rbac-service-followup.md` — N4·N5 (적용 완료)
- `docs/cache-layer-followup.md` — N1·N2·N3 (적용 완료)
- `docs/critical-fixes.md` — C1·C3·H1·H3 (적용 완료)
