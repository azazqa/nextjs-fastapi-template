"use server";

import { cookies } from "next/headers";
import { authJwtLogout } from "@/app/clientService";
import { redirect } from "next/navigation";

export async function logout() {
  const cookieStore = await cookies();
  const token = cookieStore.get("accessToken")?.value;
  const refresh = cookieStore.get("refreshToken")?.value;

  const baseURL = process.env.API_BASE_URL;
  if (baseURL && refresh) {
    await fetch(`${baseURL}/auth/jwt/logout`, {
      method: "POST",
      headers: refresh ? { Cookie: `refreshToken=${encodeURIComponent(refresh)}` } : {},
      cache: "no-store",
    });
  }

  if (token) {
    await authJwtLogout({
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  }

  cookieStore.delete("accessToken");
  cookieStore.delete("refreshToken");
  redirect(`/login`);
}
