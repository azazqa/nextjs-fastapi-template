/** Parse Set-Cookie header values from a fetch Response (Node/Next server). */
export function readSetCookieMap(headers: Headers): Record<string, string> {
  const cookies: Record<string, string> = {};
  const rawCookies =
    typeof headers.getSetCookie === "function"
      ? headers.getSetCookie()
      : [];

  for (const raw of rawCookies) {
    const [pair] = raw.split(";");
    const eq = pair.indexOf("=");
    if (eq <= 0) continue;
    const name = pair.slice(0, eq).trim();
    const value = pair.slice(eq + 1).trim();
    cookies[name] = decodeURIComponent(value);
  }

  return cookies;
}

export function readSetCookie(headers: Headers, name: string): string | undefined {
  return readSetCookieMap(headers)[name];
}
