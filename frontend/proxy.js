import { NextResponse } from "next/server";

// Dashboard routes are public. Write operations remain protected by backend
// authentication and role checks.
export function proxy() {
  return NextResponse.next();
}

export const config = { matcher: ["/dashboard/:path*"] };
