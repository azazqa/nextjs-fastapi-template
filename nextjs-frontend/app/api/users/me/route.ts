import { cookies } from "next/headers";

type BackendUserMe = {
  id: string;
  email?: string;
  is_superuser?: boolean;
};

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get("accessToken")?.value;
  if (!token) return new Response("No access token found", { status: 401 });

  const baseURL = process.env.API_BASE_URL;
  if (!baseURL) return new Response("API_BASE_URL is not configured", { status: 500 });

  const meRes = await fetch(`${baseURL}/users/me`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!meRes.ok) {
    const contentType = meRes.headers.get("content-type") ?? "application/json";
    const headers = new Headers({ "content-type": contentType });
    return new Response(meRes.body, { status: meRes.status, headers });
  }

  const me = (await meRes.json()) as BackendUserMe;

  return Response.json({
    id: me.id,
    email: me.email ?? null,
    is_superuser: Boolean(me.is_superuser),
  });
}
