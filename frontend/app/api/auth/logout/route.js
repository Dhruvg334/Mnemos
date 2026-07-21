import { NextResponse } from "next/server";
import { backendRequest, clearSessionCookies, getRefreshToken } from "@/lib/server/auth";

export async function POST() {
  const refreshToken = await getRefreshToken();
  if (refreshToken) {
    await backendRequest("/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).catch(() => null);
  }
  await clearSessionCookies();
  return NextResponse.json({ data: { logged_out: true } });
}
