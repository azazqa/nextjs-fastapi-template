import { proxyAdminRequest } from "@/lib/admin-api-proxy";

export async function GET(request: Request) {
  return proxyAdminRequest(request, "/admin/scheduler/schedules", "scheduler:read");
}

export async function POST(request: Request) {
  return proxyAdminRequest(request, "/admin/scheduler/schedules", "scheduler:manage");
}
