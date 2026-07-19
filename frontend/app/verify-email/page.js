"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import Brand from "@/components/public/Brand";

function VerifyEmailContent() {
  const params = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState({ status: "loading", message: "Verifying your email…" });

  useEffect(() => {
    if (!token) {
      setState({ status: "error", message: "The verification link is missing its token." });
      return;
    }
    let active = true;
    fetch("/api/auth/verify-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    })
      .then(async (response) => ({ response, payload: await response.json().catch(() => null) }))
      .then(({ response, payload }) => {
        if (!active) return;
        if (response.ok) setState({ status: "success", message: "Email verified. Your Mnemos workspace is ready for sign in." });
        else setState({ status: "error", message: payload?.error?.message || "Verification could not be completed." });
      })
      .catch(() => active && setState({ status: "error", message: "The verification service is unavailable." }));
    return () => { active = false; };
  }, [token]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-paper-alt px-5">
      <section className="w-full max-w-lg rounded-[28px] border border-line bg-paper p-7 shadow-pop">
        <Link href="/"><Brand /></Link>
        <div className="mt-7 text-[11px] font-semibold uppercase tracking-[0.2em] text-signal-blue">Email verification</div>
        <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.04em] text-ink">Confirm workspace access</h1>
        <div className={`mt-5 rounded-2xl border px-4 py-4 text-[13px] leading-6 ${state.status === "error" ? "border-signal-red-line bg-signal-red-pale text-signal-red" : "border-signal-blue-line bg-signal-blue-pale text-signal-blue-deep"}`}>
          {state.message}
        </div>
        <Link href="/signin" className="mt-5 inline-flex rounded-full bg-rail px-5 py-2.5 text-[12.5px] font-medium text-white">Continue to sign in</Link>
      </section>
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<main className="flex min-h-screen items-center justify-center bg-paper-alt">Verifying…</main>}>
      <VerifyEmailContent />
    </Suspense>
  );
}
