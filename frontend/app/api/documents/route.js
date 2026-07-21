import { NextResponse } from "next/server";
import { requestWithSession, resolveSiteId } from "./_session";

export async function GET(request) {
  const siteId = await resolveSiteId(new URL(request.url).searchParams.get("site_id"));
  if (!siteId) return NextResponse.json({ error: { code: "SITE_REQUIRED", message: "No accessible site is available." } }, { status: 409 });
  const result = await requestWithSession(`/documents?site_id=${encodeURIComponent(siteId)}`, { method: "GET" });
  return NextResponse.json(result.payload, { status: result.response.status });
}
