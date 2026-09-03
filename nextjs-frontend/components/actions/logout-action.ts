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
