"use server";

import { cookies } from "next/headers";
import { authJwtLogout } from "@/app/clientService";
import { redirect } from "next/navigation";

export async function logout() {
  const cookieStore = await cookies();
  const token = cookieStore.get("accessToken")?.value;

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
