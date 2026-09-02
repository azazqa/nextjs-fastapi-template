import { cookies } from "next/headers";

import { readSetCookie } from "@/lib/parse-set-cookie";

export const REFRESH_MAX_AGE = 24 * 3600;
export const ACCESS_MAX_AGE = 3600;

type CookieStore = Awaited<ReturnType<typeof cookies>>;

const cookieOptions = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
};

export async function clearAuthCookies(store?: CookieStore): Promise<void> {
  const cookieStore = store ?? (await cookies());
  try {
    cookieStore.delete("accessToken");
  } catch {}
  try {
    cookieStore.delete("refreshToken");
  } catch {}
}

export async function applyRefreshCookies(
  store: CookieStore,
  data: { access_token?: string; refresh_token?: string },
): Promise<string | null> {
  if (!data.access_token) return null;

  try {
    store.set("accessToken", data.access_token, {
      ...cookieOptions,
      maxAge: ACCESS_MAX_AGE,
    });
    if (data.refresh_token) {
      store.set("refreshToken", data.refresh_token, {
        ...cookieOptions,
        maxAge: REFRESH_MAX_AGE,
      });
    }
  } catch {
    // Route handler context may forbid set; token is still valid for this request.
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
