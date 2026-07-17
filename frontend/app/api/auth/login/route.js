import { NextResponse } from "next/server";
import { backendRequest, setSessionCookies } from "@/lib/server/auth";

export async function POST(request) {
  const body = await request.json().catch(() => null);
  if (!body) {
    return NextResponse.json({ error: { code: "INVALID_REQUEST", message: "Invalid request body." } }, { status: 400 });
  }
  const { response, payload } = await backendRequest("/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!response.ok) return NextResponse.json(payload, { status: response.status });
  setSessionCookies(payload.data);
  return NextResponse.json({ data: { authenticated: true }, meta: payload.meta });
}
