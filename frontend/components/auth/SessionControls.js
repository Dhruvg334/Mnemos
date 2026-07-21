"use client";

import Link from "next/link";
import { useSession } from "./SessionContext";

function initials(name) {
  return (name || "User").split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("");
}

export default function SessionControls() {
  const { user, loading, logout } = useSession();

  if (loading) return <div className="h-8 w-20 animate-pulse rounded-md bg-paper-sunk" />;

  if (!user) {
    return (
      <div className="ml-1.5 flex items-center gap-2 border-l border-line pl-3">
        <span className="hidden rounded-full bg-signal-amber-pale px-2.5 py-1 text-[10.5px] font-medium text-signal-amber sm:inline-flex">Read-only demo</span>
        <Link href="/signin" className="rounded-md border border-line px-3 py-1.5 text-[12px] font-medium text-ink-soft hover:bg-paper-alt">Sign in</Link>
      </div>
    );
  }

  return (
    <div className="ml-1.5 flex items-center gap-2 border-l border-line pl-3">
      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-rail font-mono text-[11px] text-rail-ink">{initials(user.full_name)}</div>
      <div className="hidden leading-tight md:block">
        <div className="text-[12.5px] font-medium text-ink">{user.full_name}</div>
        <button onClick={logout} className="text-[10.5px] text-ink-faint hover:text-signal-red">Sign out</button>
      </div>
    </div>
  );
}
