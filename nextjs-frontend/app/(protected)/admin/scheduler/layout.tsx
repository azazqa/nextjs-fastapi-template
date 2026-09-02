import { Forbidden } from "@/components/forbidden";
import { hasPermission } from "@/lib/permissions";
import { getServerUserMe } from "@/lib/permissions-server";

export default async function AdminSchedulerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const me = await getServerUserMe();
  if (!hasPermission(me, "scheduler:read")) {
    return <Forbidden />;
  }
  return children;
}
