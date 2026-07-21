import Link from "next/link";
import Brand from "./Brand";

export default function PublicFooter() {
  return (
    <footer className="border-t border-white/10 bg-[#061421] text-white">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 py-12 sm:px-6 lg:grid-cols-[1.5fr,1fr,1fr] lg:px-8">
        <div>
          <Brand inverse />
          <p className="mt-5 max-w-md text-[13px] leading-6 text-slate-400">
            Mnemos connects plant records, field evidence, maintenance history, and expert knowledge into a governed operating memory.
          </p>
        </div>
        <div>
          <h3 className="text-[10.5px] font-semibold uppercase tracking-[0.18em] text-slate-500">Product</h3>
          <div className="mt-4 grid gap-3 text-[13px] text-[#cdd0d7]">
            <Link href="/dashboard" className="hover:text-white">Live workspace</Link>
            <Link href="/documentation" className="hover:text-white">Documentation</Link>
            <Link href="/about" className="hover:text-white">About</Link>
          </div>
        </div>
        <div>
          <h3 className="text-[10.5px] font-semibold uppercase tracking-[0.18em] text-slate-500">Engineering</h3>
          <div className="mt-4 grid gap-3 text-[13px] text-[#cdd0d7]">
            <Link href="/documentation/architecture" className="hover:text-white">Architecture</Link>
            <Link href="/documentation/retrieval" className="hover:text-white">Retrieval</Link>
            <Link href="/documentation/governance" className="hover:text-white">Governance</Link>
          </div>
        </div>
      </div>
      <div className="border-t border-white/10 px-5 py-5 text-center text-[11px] text-slate-500">
        Mnemos · Operating memory for evidence-grounded industrial decisions
      </div>
    </footer>
  );
}
