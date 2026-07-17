import { NextResponse } from "next/server";
import { backendRequest } from "@/lib/server/auth";

export async function POST(request) {
  const body = await request.json().catch(() => null);
  if (!body) return NextResponse.json({ error: { code: "INVALID_REQUEST", message: "Invalid request body." } }, { status: 400 });
  const { response, payload } = await backendRequest("/auth/register", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return NextResponse.json(payload, { status: response.status });
}
