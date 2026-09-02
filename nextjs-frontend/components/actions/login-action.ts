"use server";

import { cookies } from "next/headers";

import { authJwtLogin } from "@/app/clientService";
import { redirect } from "next/navigation";
import { loginSchema } from "@/lib/definitions";
import { readSetCookie } from "@/lib/parse-set-cookie";
import { getErrorMessage } from "@/lib/utils";

export async function login(prevState: unknown, formData: FormData) {
  const validatedFields = loginSchema.safeParse({
    username: formData.get("username") as string,
    password: formData.get("password") as string,
  });

  if (!validatedFields.success) {
    return {
      errors: validatedFields.error.flatten().fieldErrors,
    };
  }

  const { username, password } = validatedFields.data;

  const input = {
    body: {
      username,
      password,
    },
  };

  try {
    const { data, error } = await authJwtLogin(input);
    if (error) {
      return { server_validation_error: getErrorMessage(error) };
    }
    const cookieStore = await cookies();
    cookieStore.set("accessToken", data.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 3600, // 1h; align with backend ACCESS_TOKEN_EXPIRE_SECONDS
      path: "/",
    });

    const baseURL = process.env.API_BASE_URL;
    if (!baseURL) {
      return { server_error: "API_BASE_URL is not configured." };
    }

    const refreshRes = await fetch(`${baseURL}/auth/jwt/refresh-token`, {
      method: "POST",
      headers: { Authorization: `Bearer ${data.access_token}` },
      cache: "no-store",
    });
    if (!refreshRes.ok) {
      const text = await refreshRes.text();
      return { server_error: text || "Failed to issue refresh token." };
    }
    const refreshToken = readSetCookie(refreshRes.headers, "refreshToken");
    if (!refreshToken) {
      return { server_error: "Refresh token cookie was not returned." };
    }
    cookieStore.set("refreshToken", refreshToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 24 * 3600, // 1d; align with backend REFRESH_TOKEN_EXPIRE_SECONDS
      path: "/",
    });
  } catch (err) {
    console.error("Login error:", err);
    return {
      server_error: "An unexpected error occurred. Please try again later.",
    };
  }
  redirect("/");
}
