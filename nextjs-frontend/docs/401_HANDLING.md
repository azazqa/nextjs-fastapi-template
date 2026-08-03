# 401 처리: Refresh 후 재시도

## 동작

- API 클라이언트(`lib/clientConfig.ts`)에 **response interceptor**가 등록되어 있음.
- **서버**(Server Action 등)에서 요청 시 **401 Unauthorized**가 오면:
  1. 쿠키 `refreshToken`이 있으면 `/auth/jwt/refresh`로 **access token 재발급**을 시도
  2. 성공 시 `accessToken` 쿠키를 갱신하고 **원래 요청을 1회 재시도**
  3. refresh 실패(또는 refreshToken 없음) 시 `accessToken`/`refreshToken` 삭제 후 `/login`으로 리다이렉트

이렇게 하면 access token 만료로 인한 401이 발생해도, refresh token이 유효한 동안은 자동으로 복구된다.

## 적용 범위

- **서버에서만** 동작: `typeof window === "undefined"`일 때만 interceptor를 등록함.
- 인증이 필요한 API(listProducts, listChannels 등)를 **Server Action**에서 호출할 때 401이 나면 위 순서대로 처리됨.
- 로그인/회원가입/비밀번호 재설정 등 인증이 없는 요청에서 401이 나는 경우는 일반적이지 않으며, 해당 액션에 try/catch가 있어도 리다이렉트는 인증 필요한 API 호출 경로에서만 사용됨.

## try/catch 사용 시

- Server Action에서 `try { await listProducts(...) } catch (e) { ... }`처럼 **인증 필요한 API**를 try/catch로 감쌌다면, 401 시 interceptor가 던지는 **리다이렉트**를 그대로 넘겨줘야 로그인으로 이동한다.
- Next.js에서는 `next/navigation`의 `isRedirectError(e)`로 리다이렉트인지 확인한 뒤, 리다이렉트면 `throw e`로 다시 던지면 된다.

## 요약

| 상황              | 동작                          |
|-------------------|-------------------------------|
| 401 응답 (서버)   | refresh 시도 → 성공 시 재시도 / 실패 시 쿠키 삭제 → `/login` |
| 401 응답 (클라이언트) | interceptor 미등록, 기존 에러 처리 유지 |
| 로그아웃 버튼     | `logout-action`: 쿠키 삭제 후 `/login` 리다이렉트 |
