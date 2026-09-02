import { cookies } from "next/headers";

import { hasPermission, type UserPermissions } from "@/lib/permissions";

export type ServerUserMe = UserPermissions;
export { hasPermission };

type CookieStore = Awaited<ReturnType<typeof cookies>>;

const REFRESH_MAX_AGE = 24 * 3600;
const ACCESS_MAX_AGE = 3600;

async function applyRefreshCookies(
  store: CookieStore,
  data: { access_token?: string; refresh_token?: string },
): Promise<string | null> {
  if (!data.access_token) return null;

  try {
    store.set("accessToken", data.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: ACCESS_MAX_AGE,
      path: "/",
    });
    if (data.refresh_token) {
      store.set("refreshToken", data.refresh_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: REFRESH_MAX_AGE,
        path: "/",
      });
    }
  } catch {
    // Route handler context may forbid set; token is still valid for this request.
  }

  return data.access_token;
}

async function refreshServerAccessToken(store: CookieStore): Promise<string | null> {
  const refresh = store.get("refreshToken")?.value;
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

    const data = (await res.json()) as { access_token?: string; refresh_token?: string };
    return applyRefreshCookies(store, data);
  } catch {
    return null;
  }
}

async function fetchServerUserMe(): Promise<{ me: ServerUserMe; token: string } | null> {
  const store = await cookies();
  let token = store.get("accessToken")?.value ?? null;
  if (!token) {
    token = await refreshServerAccessToken(store);
    if (!token) return null;
  }

  const baseURL = process.env.API_BASE_URL;
  if (!baseURL) return null;

  try {
    let res = await fetch(`${baseURL}/users/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (res.status === 401) {
      const refreshed = await refreshServerAccessToken(store);
      if (!refreshed) return null;
      token = refreshed;
      res = await fetch(`${baseURL}/users/me`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
    }
    if (!res.ok) return null;
    const me = (await res.json()) as ServerUserMe;
    return { me, token };
  } catch {
    return null;
  }
}

export async function getServerIsSuperuser(): Promise<boolean> {
  const result = await fetchServerUserMe();
  return Boolean(result?.me.is_superuser);
}

export async function getServerPermissions(): Promise<string[]> {
  const result = await fetchServerUserMe();
  return result?.me.permissions ?? [];
}

export async function getServerUserMe(): Promise<ServerUserMe | null> {
  const result = await fetchServerUserMe();
  return result?.me ?? null;
}

/** Permission-aware API routes: reject missing session (401) or missing permission (403). */
export async function assertServerPermission(
  ...codes: string[]
): Promise<
  { ok: true; token: string; me: ServerUserMe } | { ok: false; status: 401 | 403; message: string }
> {
  const result = await fetchServerUserMe();
  if (!result) {
    return { ok: false, status: 401, message: "Unauthorized" };
  }
  if (!hasPermission(result.me, ...codes)) {
    return { ok: false, status: 403, message: "Forbidden" };
  }
  return { ok: true, token: result.token, me: result.me };
}

/** Superuser-only API routes: reject missing session (401) or non-superuser (403). */
export async function assertServerSuperuser(): Promise<
  { ok: true; token: string } | { ok: false; status: 401 | 403; message: string }
> {
  const result = await fetchServerUserMe();
  if (!result) {
    return { ok: false, status: 401, message: "Unauthorized" };
  }
  if (!result.me.is_superuser) {
    return { ok: false, status: 403, message: "Superuser access required" };
  }
  return { ok: true, token: result.token };
}
