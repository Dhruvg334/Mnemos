import { NextResponse } from "next/server";
import { requestWithSession } from "../../_session";

export async function POST(request, { params }) {
  const { documentId } = await params;
  const body = await request.json().catch(() => ({}));
  const result = await requestWithSession(`/documents/${encodeURIComponent(documentId)}/confirm`, { method: "POST", body: JSON.stringify(body), timeoutMs: 120_000 });
  return NextResponse.json(result.payload, { status: result.response.status });
}
