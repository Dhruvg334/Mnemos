import { NextResponse } from "next/server";

// The dashboard is intentionally public for the hackathon demo. Mutation
// endpoints remain protected by backend authentication and role checks.
export function middleware() {
  return NextResponse.next();
}

export const config = { matcher: ["/dashboard/:path*"] };
