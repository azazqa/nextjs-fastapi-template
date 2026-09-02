import { getAuthenticatedSession } from "@/lib/permissions-server";

export async function GET() {
  const session = await getAuthenticatedSession();
  if (!session) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { me } = session;
  return Response.json({
    id: me.id,
    email: me.email ?? null,
    is_superuser: Boolean(me.is_superuser),
    roles: me.roles ?? [],
    permissions: me.permissions ?? [],
  });
}
