import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const publicPaths = ["/login", "/password-recovery"];

function isPublicPath(pathname: string) {
  return publicPaths.some(
    (path) => pathname === path || pathname.startsWith(path + "/"),
  );
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get("accessToken");
  const refreshToken = request.cookies.get("refreshToken");

  // accessToken이 없더라도 refreshToken이 있으면 서버에서 자동 refresh 후 복구될 수 있으므로 통과시킨다.
  if (!token && !refreshToken && !isPublicPath(pathname)) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Do NOT bounce /login → / when cookies exist.
  // Stale/invalid cookies after 401 would loop: /login → / → clear? → /login.
  // Logged-in users can still open /login; successful login overwrites cookies.
  // Password recovery: send authenticated sessions home.
  if (
    (token || refreshToken) &&
    (pathname === "/password-recovery" ||
      pathname.startsWith("/password-recovery/"))
  ) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|images).*)"],
};
