"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

type RefreshResponse = { access_token: string; token_type: string };

async function logoutAndRedirect(): Promise<never> {
  const store = await cookies();
  // 쿠키가 없더라도 예외 없이 진행
  try {
    store.delete("accessToken");
  } catch {}
  try {
    store.delete("refreshToken");
  } catch {}
  redirect("/login");
}

export async function requireAccessToken(): Promise<string> {
  const store = await cookies();
  const access = store.get("accessToken")?.value;
  if (access) return access;

  const refresh = store.get("refreshToken")?.value;
  if (!refresh) {
    await logoutAndRedirect();
  }

  const baseURL = process.env.API_BASE_URL;
  if (!baseURL) {
    // 구성 문제는 로그인으로 보내기보다 에러가 더 낫지만,
    // 요구사항(갱신 실패 시 로그아웃)에 맞춰 동일 처리
    await logoutAndRedirect();
  }

  const res = await fetch(`${baseURL}/auth/jwt/refresh`, {
    method: "POST",
    headers: {
      // 백엔드는 refreshToken을 httpOnly cookie에서 읽는다.
      Cookie: `refreshToken=${encodeURIComponent(refresh!)}`,
    },
    cache: "no-store",
  });

  if (!res.ok) {
    await logoutAndRedirect();
  }

  const data = (await res.json()) as Partial<RefreshResponse>;
  const accessToken = data.access_token;
  if (!accessToken) {
    return await logoutAndRedirect();
  }

  // 서버 액션/라우트 핸들러가 아닌 렌더링 컨텍스트에서는 set이 금지될 수 있다.
  // 이 경우 쿠키 저장은 건너뛰고, 현재 요청에서만 accessToken을 사용한다.
  try {
    store.set("accessToken", accessToken, {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      secure: process.env.NODE_ENV === "production",
    });
  } catch {}

  return accessToken;
}

