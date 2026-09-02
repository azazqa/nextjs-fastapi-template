import { client } from "@/app/openapi-client/client.gen";

import {
  applyRefreshCookies,
  clearAuthCookies,
} from "@/lib/auth-cookies";
import { readSetCookie } from "@/lib/parse-set-cookie";

const configureClient = () => {
  const baseURL = process.env.API_BASE_URL;

  client.setConfig({
    baseURL: baseURL,
  });

  // 401 시 서버에서만 쿠키 삭제 후 로그인으로 리다이렉트 (Server Action 컨텍스트)
  if (typeof window === "undefined") {
    client.instance.interceptors.response.use(
      (res) => res,
      async (error) => {
        if (error?.response?.status === 401) {
          const { cookies } = await import("next/headers");
          const { redirect } = await import("next/navigation");
          const cookieStore = await cookies();

          const originalRequest = error?.config as
            | (typeof error)["config"] & { _retry?: boolean }
            | undefined;

          if (!originalRequest || originalRequest._retry) {
            await clearAuthCookies(cookieStore);
            redirect("/login");
            return Promise.reject(error);
          }

          const refreshToken = cookieStore.get("refreshToken")?.value;
          if (!refreshToken || !baseURL) {
            await clearAuthCookies(cookieStore);
            redirect("/login");
            return Promise.reject(error);
          }

          const refreshRes = await fetch(`${baseURL}/auth/jwt/refresh`, {
            method: "POST",
            headers: {
              Cookie: `refreshToken=${encodeURIComponent(refreshToken)}`,
            },
            cache: "no-store",
          });

          if (!refreshRes.ok) {
            await clearAuthCookies(cookieStore);
            redirect("/login");
            return Promise.reject(error);
          }

          const json = (await refreshRes.json()) as { access_token?: string };
          const rotatedRefresh = readSetCookie(refreshRes.headers, "refreshToken");
          const accessToken = await applyRefreshCookies(cookieStore, {
            access_token: json.access_token,
            refresh_token: rotatedRefresh,
          });
          if (!accessToken) {
            await clearAuthCookies(cookieStore);
            redirect("/login");
            return Promise.reject(error);
          }

          originalRequest._retry = true;
          originalRequest.headers = {
            ...(originalRequest.headers ?? {}),
            Authorization: `Bearer ${accessToken}`,
          };
          return client.instance.request(originalRequest);
        }
        return Promise.reject(error);
      },
    );
  }
};

configureClient();
