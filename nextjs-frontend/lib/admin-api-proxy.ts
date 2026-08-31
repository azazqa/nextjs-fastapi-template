import { assertServerSuperuser } from "@/lib/permissions-server";

export async function proxyAdminRequest(
  request: Request,
  backendPath: string,
): Promise<Response> {
  const auth = await assertServerSuperuser();
  if (!auth.ok) {
    return new Response(auth.message, { status: auth.status });
  }

  const token = auth.token;

  const baseURL = process.env.API_BASE_URL;
  if (!baseURL) return new Response("API_BASE_URL is not configured", { status: 500 });

  const incoming = new URL(request.url);
  const backendUrl = new URL(`${baseURL}${backendPath}`);
  for (const [key, value] of incoming.searchParams.entries()) {
    backendUrl.searchParams.set(key, value);
  }

  const headers: HeadersInit = { Authorization: `Bearer ${token}` };
  const init: RequestInit = { method: request.method, headers, cache: "no-store" };

  if (request.method !== "GET" && request.method !== "HEAD") {
    const body = await request.text();
    if (body) {
      headers["Content-Type"] = request.headers.get("content-type") ?? "application/json";
      init.body = body;
    }
  }

  const res = await fetch(backendUrl.toString(), init);
  return new Response(res.body, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
  });
}
