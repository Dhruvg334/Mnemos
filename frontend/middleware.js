import { NextResponse } from "next/server";

export function middleware(request) {
  if (process.env.AUTH_REQUIRED !== "true") return NextResponse.next();
  const refreshToken = request.cookies.get("mnemos_refresh")?.value;
  if (refreshToken) return NextResponse.next();
  const signInUrl = new URL("/signin", request.url);
  signInUrl.searchParams.set("next", request.nextUrl.pathname);
  return NextResponse.redirect(signInUrl);
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
