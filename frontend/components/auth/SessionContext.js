"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "../icons";

const SessionContext = createContext(null);

export function SessionProvider({ children }) {
  const router = useRouter();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lockedAction, setLockedAction] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/auth/session", { cache: "no-store" });
      const payload = response.ok ? await response.json() : null;
      setUser(payload?.data || null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const requireAuthentication = useCallback((action, callback) => {
    if (!user) {
      setLockedAction(action);
      return false;
    }
    callback?.();
    return true;
  }, [user]);

  const logout = useCallback(async () => {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => null);
    setUser(null);
    router.refresh();
  }, [router]);

  const value = useMemo(() => ({
    user,
    loading,
    isAuthenticated: Boolean(user),
    refresh,
    logout,
    requireAuthentication,
  }), [user, loading, refresh, logout, requireAuthentication]);

  return (
    <SessionContext.Provider value={value}>
      {children}
      {lockedAction ? (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/45 px-4" onClick={() => setLockedAction(null)}>
          <div className="w-full max-w-sm rounded-xl border border-line bg-paper p-6 shadow-xl animate-scale-in" onClick={(event) => event.stopPropagation()}>
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-signal-amber-pale">
              <Icon name="lock" className="h-6 w-6 text-signal-amber" />
            </div>
            <h3 className="text-center text-[15px] font-semibold text-ink">Sign in to {lockedAction.toLowerCase()}</h3>
            <p className="mt-2 text-center text-[12.5px] leading-relaxed text-ink-faint">
              The public demo is read-only. Create an account or sign in to perform actions that modify organisation data.
            </p>
            <div className="mt-5 flex justify-center gap-3">
              <button onClick={() => setLockedAction(null)} className="rounded-md border border-line px-4 py-2 text-[12.5px] font-medium text-ink hover:bg-paper-alt">Continue demo</button>
              <button onClick={() => router.push("/signin")} className="rounded-md bg-signal-blue px-4 py-2 text-[12.5px] font-medium text-white hover:bg-signal-blue-deep">Sign in</button>
            </div>
          </div>
        </div>
      ) : null}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
