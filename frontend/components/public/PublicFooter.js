import Link from "next/link";
import Brand from "./Brand";

export default function PublicFooter() {
  return (
    <footer className="border-t border-line bg-paper">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 py-10 sm:px-6 lg:grid-cols-[1.4fr,1fr,1fr] lg:px-8">
        <div>
          <Brand />
          <p className="mt-4 max-w-md text-[13px] leading-6 text-ink-soft">
            Mnemos turns plant documents, field evidence, maintenance history, and expert knowledge into a governed operational memory for reliability teams.
          </p>
        </div>
        <div>
          <h3 className="text-[12px] font-semibold uppercase tracking-[0.18em] text-ink-faint">Product</h3>
          <div className="mt-4 grid gap-3 text-[13px] text-ink-soft">
            <Link href="/documentation" className="hover:text-ink">Documentation</Link>
            <Link href="/dashboard" className="hover:text-ink">Dashboard</Link>
            <Link href="/about" className="hover:text-ink">About</Link>
          </div>
        </div>
        <div>
          <h3 className="text-[12px] font-semibold uppercase tracking-[0.18em] text-ink-faint">Entry points</h3>
          <div className="mt-4 grid gap-3 text-[13px] text-ink-soft">
            <Link href="/signin" className="hover:text-ink">Sign in</Link>
            <Link href="/signup" className="hover:text-ink">Create account</Link>
            <Link href="/documentation/architecture" className="hover:text-ink">Architecture</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
