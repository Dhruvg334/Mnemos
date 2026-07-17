"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

function initials(name) {
  return (name || "User")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export default function SessionControls() {
  const router = useRouter();
  const [user, setUser] = useState(null);

  useEffect(() => {
    let active = true;
    fetch("/api/auth/session", { cache: "no-store" })
      .then(async (response) => (response.ok ? response.json() : null))
      .then((payload) => active && setUser(payload?.data || null))
      .catch(() => null);
    return () => { active = false; };
  }, []);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => null);
    router.push("/signin");
    router.refresh();
  }

  if (!user) {
    return (
      <a href="/signin" className="rounded-md border border-line px-3 py-1.5 text-[12px] font-medium text-ink-soft hover:bg-paper-alt">
        Sign in
      </a>
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
