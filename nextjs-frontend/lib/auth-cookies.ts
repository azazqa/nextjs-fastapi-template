import { cookies } from "next/headers";

import { readSetCookie } from "@/lib/parse-set-cookie";

type CookieStore = Awaited<ReturnType<typeof cookies>>;

/** JWT 파싱 실패 시에만 사용하는 폴백 값. 정상 경로에서는 토큰의 exp 를 따른다. */
export const ACCESS_MAX_AGE_FALLBACK = 3600;
export const REFRESH_MAX_AGE_FALLBACK = 24 * 3600;

/** 모든 인증 쿠키의 단일 속성 정의. 쿠키 속성 변경은 이 객체만 수정한다. */
export const cookieOptions = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
};

/**
 * JWT 의 exp 로 쿠키 수명을 계산한다.
 * 서명은 검증하지 않는다 — 만료 시각 힌트로만 쓰이며 인증 판단은 백엔드가 한다.
 */
function maxAgeFromJwt(token: string, fallback: number): number {
  try {
    const segment = token.split(".")[1];
    if (!segment) return fallback;
    const payload = JSON.parse(
      Buffer.from(segment, "base64url").toString("utf8"),
    );
    const ttl = Number(payload.exp) - Math.floor(Date.now() / 1000);
    return Number.isFinite(ttl) && ttl > 0 ? Math.floor(ttl) : fallback;
  } catch {
    return fallback;
  }
}

export function setAccessCookie(store: CookieStore, token: string): void {
  store.set("accessToken", token, {
    ...cookieOptions,
    maxAge: maxAgeFromJwt(token, ACCESS_MAX_AGE_FALLBACK),
  });
}

export function setRefreshCookie(store: CookieStore, token: string): void {
  store.set("refreshToken", token, {
    ...cookieOptions,
    maxAge: maxAgeFromJwt(token, REFRESH_MAX_AGE_FALLBACK),
  });
}

export async function clearAuthCookies(store?: CookieStore): Promise<void> {
  const cookieStore = store ?? (await cookies());
  for (const name of ["accessToken", "refreshToken"]) {
    try {
      // delete() alone may not clear httpOnly cookies set with path/secure;
      // expire with the same options used by setAccess/setRefreshCookie.
      cookieStore.set(name, "", { ...cookieOptions, maxAge: 0 });
    } catch {
      // Route handler 컨텍스트에서 삭제가 금지될 수 있다
    }
  }
}

export async function applyRefreshCookies(
  store: CookieStore,
  data: { access_token?: string; refresh_token?: string },
): Promise<string | null> {
  if (!data.access_token) return null;

  try {
    setAccessCookie(store, data.access_token);
    if (data.refresh_token) {
      setRefreshCookie(store, data.refresh_token);
    }
  } catch {
    // Route handler 컨텍스트에서는 set 이 금지될 수 있다.
    // 이번 요청에 한해 토큰은 여전히 유효하므로 값은 반환한다.
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
