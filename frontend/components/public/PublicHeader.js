"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Brand from "./Brand";

const LINKS = [
  { href: "/documentation", label: "Documentation" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/about", label: "About" },
];

export default function PublicHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const [session, setSession] = useState({ loading: true, user: null });

  useEffect(() => {
    let active = true;
    fetch("/api/auth/session", { cache: "no-store" })
      .then(async (response) => (response.ok ? response.json() : null))
      .then((payload) => {
        if (active) setSession({ loading: false, user: payload?.data || null });
      })
      .catch(() => {
        if (active) setSession({ loading: false, user: null });
      });
    return () => { active = false; };
  }, [pathname]);

  async function signOut() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => null);
    setSession({ loading: false, user: null });
    router.refresh();
  }

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-[#111216]/95 text-white backdrop-blur-xl">
      <div className="mx-auto grid max-w-7xl grid-cols-[1fr_auto_1fr] items-center gap-3 px-5 py-3.5 sm:px-6 lg:px-8">
        <Link href="/" className="min-w-0 justify-self-start" aria-label="Go to Mnemos home">
          <Brand compact inverse />
        </Link>

        <nav className="hidden justify-self-center items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] p-1 md:flex" aria-label="Primary navigation">
          {LINKS.map((link) => {
            const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-full px-4 py-2 text-[12.5px] font-medium transition ${
                  active ? "bg-white text-[#111216]" : "text-[#cdd0d7] hover:bg-white/[0.06] hover:text-white"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex min-h-10 min-w-0 justify-self-end items-center justify-end gap-1 sm:min-w-[250px] sm:gap-2">
          {session.loading ? (
            <div className="h-9 w-full max-w-[220px] animate-pulse rounded-full bg-white/10" aria-label="Loading session" />
          ) : session.user ? (
            <>
              <button onClick={signOut} className="rounded-full px-4 py-2.5 text-[12.5px] font-medium text-[#cdd0d7] transition hover:bg-white/[0.06] hover:text-white">Sign out</button>
              <Link href="/dashboard" className="rounded-full bg-white px-4 py-2.5 text-[12.5px] font-semibold text-[#111216] transition hover:bg-[#e2e4e9]">
                Open workspace
              </Link>
            </>
          ) : (
            <>
              <Link href="/signin" className="rounded-full px-4 py-2 text-[12.5px] font-medium text-[#cdd0d7] transition hover:text-white">
                Sign in
              </Link>
              <Link href="/signup" className="rounded-full bg-white px-4 py-2.5 text-[12.5px] font-semibold text-[#111216] transition hover:bg-[#e2e4e9]">
                Create workspace
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
