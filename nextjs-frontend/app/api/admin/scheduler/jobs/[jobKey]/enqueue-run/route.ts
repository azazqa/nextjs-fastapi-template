import { proxyAdminRequest } from "@/lib/admin-api-proxy";

type Params = { params: Promise<{ jobKey: string }> };

export async function POST(request: Request, { params }: Params) {
  const { jobKey } = await params;
  return proxyAdminRequest(
    request,
    `/admin/scheduler/jobs/${encodeURIComponent(jobKey)}/enqueue-run`,
  );
}
