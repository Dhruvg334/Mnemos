import { NextResponse } from "next/server";
import { backendRequest, getAccessToken, refreshSession } from "@/lib/server/auth";

async function requestWithSession(path, options = {}) {
  let token = await getAccessToken();
  if (!token) token = await refreshSession();
  if (!token) return { response: new Response(null, { status: 401 }), payload: { error: { code: "UNAUTHENTICATED", message: "Sign in to run an analysis against your workspace." } } };

  let result = await backendRequest(path, {
    ...options,
    timeoutMs: options.timeoutMs ?? 30_000,
    headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` },
  });
  if (result.response.status === 401) {
    token = await refreshSession();
    if (!token) return result;
    result = await backendRequest(path, {
      ...options,
      timeoutMs: options.timeoutMs ?? 30_000,
      headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` },
    });
  }
  return result;
}

export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  const question = typeof body.question === "string" ? body.question.trim() : "";
  if (question.length < 3) {
    return NextResponse.json({ error: { code: "VALIDATION_ERROR", message: "Enter a longer operational question." } }, { status: 422 });
  }

  const sitesResult = await requestWithSession("/sites", { method: "GET" });
  if (!sitesResult.response.ok) {
    return NextResponse.json(sitesResult.payload, { status: sitesResult.response.status });
  }
  const siteId = body.site_id || sitesResult.payload?.data?.[0]?.id;
  if (!siteId) {
    return NextResponse.json({ error: { code: "SITE_REQUIRED", message: "No accessible site is available for this workspace." } }, { status: 409 });
  }

  const result = await requestWithSession("/queries", {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({
      site_id: siteId,
      question,
      mode: body.mode || "general",
      context: {
        asset_ids: Array.isArray(body.asset_ids) ? body.asset_ids : [],
        document_ids: Array.isArray(body.document_ids) ? body.document_ids : [],
      },
    }),
  });
  return NextResponse.json(result.payload, { status: result.response.status });
}
