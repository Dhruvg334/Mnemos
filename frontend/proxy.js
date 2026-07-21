import { NextResponse } from "next/server";

// The dashboard is intentionally public for the public demonstration. Mutation
// endpoints remain protected by backend authentication and role checks.
export function proxy() {
  return NextResponse.next();
}

export const config = { matcher: ["/dashboard/:path*"] };
