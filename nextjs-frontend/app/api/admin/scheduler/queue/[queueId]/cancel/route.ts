import { proxyAdminRequest } from "@/lib/admin-api-proxy";

type Params = { params: Promise<{ queueId: string }> };

export async function POST(request: Request, { params }: Params) {
  const { queueId } = await params;
  return proxyAdminRequest(request, `/admin/scheduler/queue/${encodeURIComponent(queueId)}/cancel`);
}
