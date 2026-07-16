import Link from "next/link";
import Brand from "./Brand";

export default function PublicFooter() {
  return (
    <footer className="border-t border-line bg-paper">
      <div className="mx-auto max-w-7xl px-5 py-10 sm:px-7 lg:px-8">
        <div className="grid gap-8 md:grid-cols-[1.5fr_1fr_1fr]">
          <div>
            <Brand />
            <p className="mt-4 max-w-md text-[13px] leading-6 text-ink-faint">
              Evidence-grounded operational intelligence for industrial reliability, maintenance, safety and compliance teams.
            </p>
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Product</div>
            <div className="mt-3 space-y-2.5 text-[13px] text-ink-soft">
              <Link className="block hover:text-ink" href="/#product">Capabilities</Link>
              <Link className="block hover:text-ink" href="/how-it-works">How it works</Link>
              <Link className="block hover:text-ink" href="/dashboard">Workspace</Link>
            </div>
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Company</div>
            <div className="mt-3 space-y-2.5 text-[13px] text-ink-soft">
              <Link className="block hover:text-ink" href="/about">About</Link>
              <Link className="block hover:text-ink" href="/login">Sign in</Link>
            </div>
          </div>
        </div>
        <div className="mt-9 flex flex-col gap-2 border-t border-line pt-5 text-[11.5px] text-ink-faint sm:flex-row sm:items-center sm:justify-between">
          <span>© 2026 Mnemos. Industrial knowledge, grounded in evidence.</span>
          <span>Built for governed human decision-making.</span>
        </div>
      </div>
    </footer>
  );
}
