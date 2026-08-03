# Refresh Token Flow

## 목표

- **Access token**: 1시간 (`accessToken` 쿠키)
- **Refresh token**: 3시간 (`refreshToken` 쿠키)
- 둘 다 **HTTP-only 쿠키**로 저장해서 클라이언트 JS에서 읽을 수 없게 함.

## 로그인 시

1. 프론트 `login-action`이 `/auth/jwt/login`으로 access token 발급
2. `accessToken` 쿠키 저장 (maxAge 3600)
3. 이어서 `/auth/jwt/refresh-token` 호출로 refresh token 발급
4. `refreshToken` 쿠키 저장 (maxAge 10800)

## 만료 처리 (서버 사이드)

서버에서 API 호출이 401을 받으면:

1. `refreshToken` 쿠키가 있으면 `/auth/jwt/refresh`로 access token 재발급 시도
2. 성공 시 `accessToken` 쿠키 갱신 후 **원래 요청 1회 재시도**
3. 실패(또는 refreshToken 없음) 시 `accessToken`/`refreshToken` 삭제 후 `/login` 리다이렉트

## 트러블슈팅

- **로그인 직후 refreshToken이 없어요**: `API_BASE_URL` 설정 확인, `/auth/jwt/refresh-token` 응답 확인
- **401 후 바로 로그인으로 튕겨요**: refreshToken 쿠키 존재 여부 확인(서버에서만 동작), `/auth/jwt/refresh`가 200인지 확인
- **Refresh가 401(Expired)**: refresh 만료(3시간) → 재로그인 필요

