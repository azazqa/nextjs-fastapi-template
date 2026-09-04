import { proxyAdminRequest } from "@/lib/admin-api-proxy";

type Params = { params: Promise<{ scheduleId: string }> };

export async function POST(request: Request, { params }: Params) {
  const { scheduleId } = await params;
  return proxyAdminRequest(
    request,
    `/admin/scheduler/schedules/${encodeURIComponent(scheduleId)}/enqueue-run`,
    "scheduler:manage",
  );
}
