import { backendRequest, getAccessToken, refreshSession } from "@/lib/server/auth";

export async function requestWithSession(path, options = {}) {
  let token = await getAccessToken();
  if (!token) token = await refreshSession();
  if (!token) return { response: new Response(null, { status: 401 }), payload: { error: { code: "UNAUTHENTICATED", message: "Sign in to manage workspace documents." } } };
  let result = await backendRequest(path, { ...options, headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` } });
  if (result.response.status === 401) {
    token = await refreshSession();
    if (token) result = await backendRequest(path, { ...options, headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` } });
  }
  return result;
}

export async function resolveSiteId(explicitSiteId) {
  if (explicitSiteId) return explicitSiteId;
  const sites = await requestWithSession("/sites", { method: "GET" });
  if (!sites.response.ok) return null;
  return sites.payload?.data?.[0]?.id || null;
}
