import { client } from "@/app/openapi-client/client.gen";

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

          // refresh 실패/무한루프 방지
          if (!originalRequest || originalRequest._retry) {
            cookieStore.delete("accessToken");
            cookieStore.delete("refreshToken");
            redirect("/login");
          }

          const refreshToken = cookieStore.get("refreshToken")?.value;
          if (!refreshToken || !baseURL) {
            cookieStore.delete("accessToken");
            cookieStore.delete("refreshToken");
            redirect("/login");
          }

          // Refresh로 access 재발급
          const refreshRes = await fetch(`${baseURL}/auth/jwt/refresh`, {
            method: "POST",
            headers: {
              Cookie: `refreshToken=${refreshToken}`,
            },
            cache: "no-store",
          });

          if (!refreshRes.ok) {
            cookieStore.delete("accessToken");
            cookieStore.delete("refreshToken");
            redirect("/login");
          }

          const json = (await refreshRes.json()) as { access_token: string };
          cookieStore.set("accessToken", json.access_token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === "production",
            sameSite: "lax",
            maxAge: 3600,
            path: "/",
          });

          // Retry original request once with new access token
          originalRequest._retry = true;
          originalRequest.headers = {
            ...(originalRequest.headers ?? {}),
            Authorization: `Bearer ${json.access_token}`,
          };
          return client.instance.request(originalRequest);
        }
        return Promise.reject(error);
      }
    );
  }
};

configureClient();
