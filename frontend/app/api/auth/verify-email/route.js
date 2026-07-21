import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json(
    { error: { code: "FEATURE_DEFERRED", message: "Email verification is not enabled in this release." } },
    { status: 410 },
  );
}
