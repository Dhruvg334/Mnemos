import Link from "next/link";
import PublicShell from "@/components/public/PublicShell";
import { FadeIn } from "@/components/public/Motion";

export default function HomePage() {
  return (
    <PublicShell>
      <main>
        <section className="flex min-h-[calc(100vh-74px)] items-center justify-center px-5 py-16 text-center sm:px-6 lg:px-8">
          <FadeIn className="mx-auto max-w-4xl">
            <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-signal-blue">Industrial operating memory</div>
            <h1 className="mt-5 text-[46px] font-semibold leading-[0.98] tracking-[-0.065em] text-ink sm:text-[68px]">
              Find the evidence behind an asset decision before the plant forgets it.
            </h1>
            <p className="mx-auto mt-7 max-w-2xl text-[16px] leading-8 text-ink-soft">
              Mnemos connects maintenance history, procedures, inspections, failures, compliance evidence, and expert knowledge around the assets your teams operate.
            </p>
            <div className="mt-9 flex flex-wrap justify-center gap-3">
              <Link href="/dashboard" className="rounded-full bg-rail px-5 py-3 text-[13px] font-medium text-white transition hover:bg-rail-raised">Explore live demo</Link>
              <Link href="/documentation" className="rounded-full border border-line bg-paper px-5 py-3 text-[13px] font-medium text-ink transition hover:bg-paper-alt">See how it works</Link>
            </div>
            <div className="mt-8 flex flex-wrap justify-center gap-x-7 gap-y-3 text-[12px] text-ink-faint">
              <span>Asset-centred</span><span>Evidence-linked</span><span>Review-governed</span><span>Site-scoped</span>
            </div>
          </FadeIn>
        </section>

        <section className="border-y border-line bg-paper">
          <div className="mx-auto grid max-w-6xl gap-0 px-5 sm:px-6 lg:grid-cols-3 lg:px-8">
            {[
              ["Recover context", "Trace failures across events, work orders, procedures, and source evidence."],
              ["Reason with limits", "Separate supported claims, contradictions, hypotheses, and evidence gaps."],
              ["Keep decisions governed", "Move findings into RCA, compliance, and expert review without losing provenance."],
            ].map(([title, text], index) => (
              <div key={title} className="border-b border-line py-9 lg:border-b-0 lg:border-r lg:px-8 lg:first:pl-0 lg:last:border-r-0">
                <div className="font-mono text-[10.5px] text-signal-blue">0{index + 1}</div>
                <h2 className="mt-3 text-[19px] font-semibold tracking-[-0.03em] text-ink">{title}</h2>
                <p className="mt-3 text-[13.5px] leading-7 text-ink-soft">{text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-5 py-20 sm:px-6 lg:px-8">
          <div className="grid gap-10 lg:grid-cols-[0.8fr,1.2fr]">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-signal-blue">One product surface</div>
              <h2 className="mt-3 text-[34px] font-semibold tracking-[-0.05em] text-ink">Technical depth without pushing implementation details onto operators.</h2>
              <p className="mt-5 text-[14px] leading-7 text-ink-soft">
                The dashboard remains operational. The documentation explains the architecture, agentic workflow, retrieval system, infrastructure, governance, and deployment decisions for judges and technical evaluators.
              </p>
            </div>
            <div className="divide-y divide-line border-y border-line">
              {[
                ["Asset intelligence", "Passports, timelines, evidence health, aliases, and graph relationships."],
                ["Investigations", "Claims, hypotheses, corrective actions, missing evidence, and approval."],
                ["Document intelligence", "Parsing, OCR, chunking, provenance, and ingestion status."],
                ["Governed knowledge", "Compliance and expert knowledge with review and supersession."],
              ].map(([title, text], index) => (
                <div key={title} className="grid gap-3 py-5 md:grid-cols-[44px,180px,1fr]">
                  <span className="font-mono text-[10.5px] text-ink-faint">0{index + 1}</span>
                  <span className="text-[14px] font-semibold text-ink">{title}</span>
                  <span className="text-[13px] leading-6 text-ink-soft">{text}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>
    </PublicShell>
  );
}
