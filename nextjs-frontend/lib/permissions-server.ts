import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { clearAuthCookies, refreshServerAccessToken } from "@/lib/auth-cookies";
import { hasPermission, type UserPermissions } from "@/lib/permissions";

export type ServerUserMe = UserPermissions;
export { hasPermission };

export type AuthenticatedSession = { me: ServerUserMe; token: string };

async function fetchServerUserMe(): Promise<AuthenticatedSession | null> {
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

/** Route handlers and BFF: returns session with refresh retry, or null (401). */
export async function getAuthenticatedSession(): Promise<AuthenticatedSession | null> {
  return fetchServerUserMe();
}

/** Protected layouts: redirect to login when session cannot be established. */
export async function requireServerUserMe(): Promise<ServerUserMe> {
  const result = await fetchServerUserMe();
  if (!result) {
    await clearAuthCookies();
    redirect("/login");
  }
  return result.me;
}

/** Server Actions: access token with refresh, or redirect to login. */
export async function requireAccessToken(): Promise<string> {
  const result = await fetchServerUserMe();
  if (!result) {
    await clearAuthCookies();
    redirect("/login");
  }
  return result.token;
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
  | { ok: true; token: string; me: ServerUserMe }
  | { ok: false; status: 401 | 403; message: string }
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
