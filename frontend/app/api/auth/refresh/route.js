import { NextResponse } from "next/server";
import { refreshSession } from "@/lib/server/auth";

export async function POST() {
  const token = await refreshSession();
  if (!token) return NextResponse.json({ error: { code: "UNAUTHENTICATED", message: "Session expired." } }, { status: 401 });
  return NextResponse.json({ data: { refreshed: true } });
}
