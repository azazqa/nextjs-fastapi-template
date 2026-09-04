import { proxyAdminRequest } from "@/lib/admin-api-proxy";

type Params = { params: Promise<{ scheduleId: string }> };

export async function PATCH(request: Request, { params }: Params) {
  const { scheduleId } = await params;
  return proxyAdminRequest(
    request,
    `/admin/scheduler/schedules/${encodeURIComponent(scheduleId)}`,
    "scheduler:manage",
  );
}

export async function DELETE(_request: Request, { params }: Params) {
  const { scheduleId } = await params;
  return proxyAdminRequest(
    new Request(_request.url, { method: "DELETE" }),
    `/admin/scheduler/schedules/${encodeURIComponent(scheduleId)}`,
    "scheduler:manage",
  );
}
