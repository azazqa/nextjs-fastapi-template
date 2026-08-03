# JWT 인증 방식 검토

참고: [FastAPI - OAuth2 with Password (and hashing), Bearer with JWT tokens](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)

## 현재 구현 요약

### 백엔드 (FastAPI)
- **라이브러리**: `fastapi-users` (JWT + Bearer)
- **로그인**: `POST /auth/jwt/login` — OAuth2 Password flow (username + password)
- **토큰**: JWT, `JWTStrategy`로 서명·검증 (secret: `ACCESS_SECRET_KEY`, 만료: `ACCESS_TOKEN_EXPIRE_SECONDS`)
- **전달 방식**: `BearerTransport` → 응답 본문에 `{ "access_token": "..." }` 반환, 클라이언트가 `Authorization: Bearer <token>` 으로 API 호출

### 프론트엔드 (Next.js)
- 로그인 성공 시 응답의 `access_token`을 **쿠키 `accessToken`** 에 저장
- Server Actions에서 `cookies().get("accessToken")`으로 읽어 API 요청 시 `Authorization: Bearer ${token}` 헤더에 설정

---

## 가이드와의 대응 관계

| 항목 | FastAPI 가이드 | 현재 구현 | 비고 |
|------|----------------|-----------|------|
| **토큰 종류** | JWT (서명, 만료 포함) | JWT (fastapi-users `JWTStrategy`) | 동일 개념 |
| **알고리즘** | HS256 | HS256 (config `ALGORITHM`, JWTStrategy 기본값) | 동일 |
| **비밀키** | `SECRET_KEY` (openssl rand -hex 32 권장) | `ACCESS_SECRET_KEY` (env) | 동일 역할 |
| **만료** | `ACCESS_TOKEN_EXPIRE_MINUTES` | `ACCESS_TOKEN_EXPIRE_SECONDS` | 동일 개념 |
| **로그인** | `/token` POST, username+password → JWT 반환 | `/auth/jwt/login` POST, 동일 | OAuth2 Password flow |
| **인증** | `get_current_user`: Bearer 토큰 디코드 → user 반환 | `current_active_user`: fastapi-users가 Bearer 토큰 검증 후 User | 동일 흐름 |
| **비밀번호** | pwdlib 등으로 해시 저장/검증 | fastapi-users 내장 (해시 저장·검증) | 가이드와 동일 목적 |
| **Bearer** | `OAuth2PasswordBearer`, `Authorization: Bearer` | `BearerTransport` + 클라이언트가 Bearer 헤더 전송 | 동일 |

결론: **이미 가이드와 동일한 “JWT + Bearer” 방식**을 쓰고 있으며, 토큰만 쿠키에 넣어 두고 매 요청마다 그 값을 Bearer로 보내는 구조입니다.

---

## 쿠키 vs 가이드

- 가이드: 토큰을 **JSON 응답**으로 주고, 클라이언트가 어디에 보관할지는 설명하지 않음 (메모리/로컬스토리지/쿠키 등).
- 현재: 토큰을 **쿠키 `accessToken`**에 저장한 뒤, Server Actions에서 쿠키를 읽어 `Authorization: Bearer`에 넣어 요청.

즉, **JWT를 쿠키에 넣어 두는 것은 “저장 위치” 선택**일 뿐이고, API 입장에서는 여전히 **Bearer JWT**만 보이므로 가이드와 동일한 방식입니다.

### 쿠키 사용 시 권장 (선택)
- **HttpOnly**: XSS로 토큰 탈취 방지 (설정 시 클라이언트 JS에서 `document.cookie`로는 접근 불가).
- **Secure**: HTTPS에서만 쿠키 전송.
- **SameSite**: CSRF 완화 (예: `Lax` 또는 `Strict`).

Next.js에서 설정 예:

```ts
(await cookies()).set("accessToken", data.access_token, {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax",
  maxAge: 3600, // 초 단위 (백엔드 만료와 맞추기)
  path: "/",
});
```

---

## 요약

- 인증 방식은 **OAuth2 Password + JWT + Bearer** 로, FastAPI 공식 JWT 가이드와 일치합니다.
- 토큰은 **쿠키에 보관**하고, API 호출 시 **Authorization: Bearer** 로 보내고 있어 가이드의 “Bearer with JWT” 사용법과 같습니다.
- 보안을 더 강화하려면 쿠키 옵션(`httpOnly`, `secure`, `sameSite`, `maxAge`)을 위와 같이 설정하는 것을 권장합니다.
