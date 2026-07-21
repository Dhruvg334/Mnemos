import { NextResponse } from "next/server";
import { backendRequest, getAccessToken, refreshSession } from "@/lib/server/auth";

async function readQuery(queryId) {
  let token = await getAccessToken();
  if (!token) token = await refreshSession();
  if (!token) return { response: new Response(null, { status: 401 }), payload: { error: { code: "UNAUTHENTICATED", message: "Session expired." } } };

  let result = await backendRequest(`/queries/${encodeURIComponent(queryId)}`, {
    method: "GET",
    timeoutMs: 30_000,
    headers: { Authorization: `Bearer ${token}` },
  });
  if (result.response.status === 401) {
    token = await refreshSession();
    if (token) {
      result = await backendRequest(`/queries/${encodeURIComponent(queryId)}`, {
        method: "GET",
        timeoutMs: 30_000,
        headers: { Authorization: `Bearer ${token}` },
      });
    }
  }
  return result;
}

export async function GET(_request, { params }) {
  const { queryId } = await params;
  const result = await readQuery(queryId);
  return NextResponse.json(result.payload, { status: result.response.status });
}
