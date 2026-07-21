import { cookies } from "next/headers";

const ACCESS_COOKIE = "mnemos_access";
const REFRESH_COOKIE = "mnemos_refresh";
const DEFAULT_TIMEOUT_MS = 20_000;

function apiBaseUrl() {
  const value = process.env.MNEMOS_API_URL?.replace(/\/$/, "");
  if (!value) throw new Error("MNEMOS_API_URL is required for server-side API requests.");
  return value;
}

export async function backendRequest(path, options = {}) {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...requestOptions } = options;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), Number(timeoutMs));
  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      ...requestOptions,
      cache: "no-store",
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(requestOptions.headers || {}) },
    });
    const payload = await response.json().catch(() => ({
      error: { code: "UPSTREAM_INVALID_RESPONSE", message: "Backend returned an invalid response." },
    }));
    return { response, payload };
  } catch (error) {
    if (error?.name === "AbortError") {
      return {
        response: new Response(null, { status: 504 }),
        payload: { error: { code: "UPSTREAM_TIMEOUT", message: "The authentication service took too long to respond. Please try again." } },
      };
    }
    return {
      response: new Response(null, { status: 503 }),
      payload: { error: { code: "UPSTREAM_UNAVAILABLE", message: "The authentication service is temporarily unavailable." } },
    };
  } finally {
    clearTimeout(timeout);
  }
}

const cookieOptions = () => ({
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax",
  path: "/",
});

export async function getAccessToken() {
  const jar = await cookies();
  return jar.get(ACCESS_COOKIE)?.value || null;
}

export async function getRefreshToken() {
  const jar = await cookies();
  return jar.get(REFRESH_COOKIE)?.value || null;
}

export async function setSessionCookies(data) {
  const jar = await cookies();
  jar.set(ACCESS_COOKIE, data.access_token, {
    ...cookieOptions(),
    maxAge: Number(data.expires_in || 1800),
  });
  if (data.refresh_token) {
    jar.set(REFRESH_COOKIE, data.refresh_token, {
      ...cookieOptions(),
      maxAge: Number(process.env.AUTH_REFRESH_COOKIE_SECONDS || 604800),
    });
  }
}

export async function clearSessionCookies() {
  const jar = await cookies();
  jar.delete(ACCESS_COOKIE);
  jar.delete(REFRESH_COOKIE);
}

export async function refreshSession() {
  const refreshToken = await getRefreshToken();
  if (!refreshToken) return null;
  const { response, payload } = await backendRequest("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok || !payload?.data?.access_token) {
    await clearSessionCookies();
    return null;
  }
  await setSessionCookies(payload.data);
  return payload.data.access_token;
}
