import { NextResponse } from "next/server";
import { backendRequest, getAccessToken, refreshSession } from "@/lib/server/auth";

async function readUser(token) {
  return backendRequest("/me", { headers: { Authorization: `Bearer ${token}` } });
}

export async function GET() {
  let token = getAccessToken();
  if (!token) token = await refreshSession();
  if (!token) return NextResponse.json({ error: { code: "UNAUTHENTICATED", message: "No active session." } }, { status: 401 });

  let result = await readUser(token);
  if (result.response.status === 401) {
    token = await refreshSession();
    if (!token) return NextResponse.json({ error: { code: "UNAUTHENTICATED", message: "Session expired." } }, { status: 401 });
    result = await readUser(token);
  }
  return NextResponse.json(result.payload, { status: result.response.status });
}
