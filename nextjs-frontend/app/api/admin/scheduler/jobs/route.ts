import { proxyAdminRequest } from "@/lib/admin-api-proxy";

export async function GET(request: Request) {
  return proxyAdminRequest(request, "/admin/scheduler/jobs");
}

export async function POST(request: Request) {
  return proxyAdminRequest(request, "/admin/scheduler/jobs");
}
