import { cookies } from "next/headers";

const ACCESS_COOKIE = "mnemos_access";
const REFRESH_COOKIE = "mnemos_refresh";

function apiBaseUrl() {
  const value = process.env.MNEMOS_API_URL?.replace(/\/$/, "");
  if (!value) throw new Error("MNEMOS_API_URL is required for server-side API requests.");
  return value;
}

export async function backendRequest(path, options = {}) {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...options,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => ({ error: { code: "UPSTREAM_INVALID_RESPONSE", message: "Backend returned an invalid response." } }));
  return { response, payload };
}

const cookieOptions = () => ({ httpOnly:true, secure:process.env.NODE_ENV === "production", sameSite:"lax", path:"/" });
export function getAccessToken() { return cookies().get(ACCESS_COOKIE)?.value || null; }
export function getRefreshToken() { return cookies().get(REFRESH_COOKIE)?.value || null; }
export function setSessionCookies(data) {
  const jar = cookies();
  jar.set(ACCESS_COOKIE, data.access_token, { ...cookieOptions(), maxAge:Number(data.expires_in || 1800) });
  if (data.refresh_token) jar.set(REFRESH_COOKIE, data.refresh_token, { ...cookieOptions(), maxAge:Number(process.env.AUTH_REFRESH_COOKIE_SECONDS || 604800) });
}
export function clearSessionCookies() { const jar=cookies(); jar.delete(ACCESS_COOKIE); jar.delete(REFRESH_COOKIE); }
export async function refreshSession() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;
  const { response, payload } = await backendRequest("/auth/refresh", { method:"POST", body:JSON.stringify({refresh_token:refreshToken}) });
  if (!response.ok || !payload?.data?.access_token) { clearSessionCookies(); return null; }
  setSessionCookies(payload.data);
  return payload.data.access_token;
}
