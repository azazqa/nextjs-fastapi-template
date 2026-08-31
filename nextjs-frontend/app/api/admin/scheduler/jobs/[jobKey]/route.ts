import { proxyAdminRequest } from "@/lib/admin-api-proxy";

type Params = { params: Promise<{ jobKey: string }> };

export async function PATCH(request: Request, { params }: Params) {
  const { jobKey } = await params;
  return proxyAdminRequest(request, `/admin/scheduler/jobs/${encodeURIComponent(jobKey)}`);
}

export async function DELETE(_request: Request, { params }: Params) {
  const { jobKey } = await params;
  return proxyAdminRequest(
    new Request(_request.url, { method: "DELETE" }),
    `/admin/scheduler/jobs/${encodeURIComponent(jobKey)}`,
  );
}
