import { NextResponse } from "next/server";
import { requestWithSession, resolveSiteId } from "../_session";

export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  const siteId = await resolveSiteId(body.site_id);
  if (!siteId) return NextResponse.json({ error: { code: "SITE_REQUIRED", message: "No accessible site is available." } }, { status: 409 });
  const result = await requestWithSession("/documents/upload-session", { method: "POST", body: JSON.stringify({ ...body, site_id: siteId }) });
  return NextResponse.json(result.payload, { status: result.response.status });
}
