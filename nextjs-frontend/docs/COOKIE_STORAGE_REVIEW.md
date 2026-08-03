# 토큰 저장 방식 검토 (쿠키 vs 로컬/세션 스토리지)

## 현재 구현

- **저장소**: HTTP 쿠키 `accessToken`
- **옵션**: `httpOnly: true`, `secure`(프로덕션), `sameSite: "lax"`, `maxAge: 3600`, `path: "/"`
- **특성**: **지속 쿠키(Persistent Cookie)** — 1시간(3600초) 동안 유효, 브라우저를 닫아도 유지됨
- **사용처**: Server Actions·API 라우트에서만 `cookies().get("accessToken")`으로 읽고, `Authorization: Bearer` 헤더에 설정 (클라이언트 JS에서 토큰 접근 불가)

---

## 방식별 비교

| 저장 방식 | XSS 노출 | 탭/창 종료 후 | 서버 요청 시 자동 전송 | Next.js Server에서 접근 | 비고 |
|-----------|----------|----------------|------------------------|-------------------------|------|
| **쿠키 (httpOnly)** | 없음 | maxAge 있으면 유지, 없으면 세션 쿠키 | 예 (같은 도메인 요청 시) | 예 (`cookies()`) | **추천** |
| **쿠키 (일반)** | 있음 | 위와 동일 | 예 | 예 | JS로 읽을 수 있어 위험 |
| **sessionStorage** | 있음 | 탭/창 닫으면 삭제 | 아니오 (직접 헤더에 넣어야 함) | 클라이언트만 | 토큰 탈취에 취약 |
| **localStorage** | 있음 | 삭제할 때까지 유지 | 아니오 | 클라이언트만 | 토큰 탈취에 취약 |

---

## 1. 로컬 쿠키 (Persistent Cookie) — 현재 방식

- **정의**: `maxAge` 또는 `expires`를 주어, 그 시간까지 디스크에 보관되는 쿠키.
- **현재**: `maxAge: 3600` → 로그인 후 1시간 동안 유효, 브라우저를 닫았다 열어도 같은 기기에서는 로그인 유지.
- **장점**: 백엔드 JWT 만료(예: 3600초)와 맞춰 “로그인 유지 시간”을 통일하기 좋고, `httpOnly`로 XSS에 강함.
- **단점**: 공용 PC 등에서는 “로그아웃 안 하고 나가도” 설정 시간 동안 쿠키가 남음. 필요하면 `maxAge`를 줄이거나 세션 쿠키로 바꾸면 됨.

---

## 2. 세션 쿠키 (Session Cookie)

- **정의**: `maxAge`/`expires`를 **설정하지 않은** 쿠키. 브라우저는 “세션”이 끝날 때(보통 **탭/창을 모두 닫을 때**) 삭제한다.
- **적용 예**:
  ```ts
  (await cookies()).set("accessToken", data.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    // maxAge 없음 → 세션 쿠키
  });
  ```
- **장점**: 탭을 다 닫으면 토큰이 사라져, 공용 PC에서 상대적으로 안전.
- **단점**: 탭만 닫아도 로그아웃되므로, “로그인 유지”를 원하는 사용자에게는 불편할 수 있음.

---

## 3. 로컬 스토리지 (localStorage)

- **특성**: 클라이언트 JS만 접근 가능, 도메인 기준으로 영구 보관(명시적 삭제 전까지 유지). 요청 시 자동으로 헤더에 붙지 않음.
- **문제**: **XSS가 나면** `localStorage`를 읽는 스크립트로 토큰이 그대로 탈취될 수 있음. JWT는 서명만 되어 있고 암호화가 아니므로, 토큰이 유출되면 만료 전까지 동일 권한으로 사용 가능.
- **결론**: access token 같은 민감한 값 저장에는 **권장하지 않음**. (참고: [OWASP – Token Storage](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html#token-storage-on-client))

---

## 4. 세션 스토리지 (sessionStorage)

- **특성**: 클라이언트 JS만 접근, **탭/창 단위**로 유지되며 탭을 닫으면 삭제됨.
- **문제**: XSS 취약점이 있으면 localStorage와 동일하게 토큰 탈취 가능. “탭 닫으면 사라짐”은 쿠키의 세션 쿠키로도 구현 가능한데, 쿠키는 `httpOnly`로 XSS를 막을 수 있음.
- **결론**: access token 저장에는 **쿠키(httpOnly)보다 불리**. 세션처럼 “탭 닫으면 로그아웃”이 필요하면 **세션 쿠키**가 더 적합.

---

## 정리 및 권장

- **현재 선택(로컬 쿠키 + httpOnly)** 은 보안·구현 측면에서 적절합니다.  
  - XSS로 토큰을 읽기 어렵고  
  - Server Actions / API에서만 토큰을 사용하는 구조와 잘 맞습니다.

- **선택 가이드**:
  - **“로그인 유지”(예: 1시간)** → 지금처럼 **maxAge 있는 httpOnly 쿠키** 유지.  
    - `maxAge`는 백엔드 `ACCESS_TOKEN_EXPIRE_SECONDS`와 맞추는 것을 권장.
  - **“브라우저 탭을 다 닫으면 로그아웃”**을 원하면 → **세션 쿠키**로 전환(maxAge 제거).
  - **localStorage / sessionStorage**에는 access token을 두지 않는 것을 권장.

- **추가 권장** (이미 적용된 경우 무시):
  - `secure: true`는 프로덕션에서 반드시 사용(HTTPS만 전송).
  - `sameSite: "lax"` 또는 `"strict"` 유지로 CSRF 완화.

요약하면, **지금처럼 “로컬 쿠키(httpOnly, maxAge 3600)”를 쓰는 방식이 적절**하고, “탭 닫으면 로그아웃”이 필요할 때만 세션 쿠키로 바꾸면 됩니다.
