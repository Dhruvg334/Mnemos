import Link from "next/link";
import PublicShell from "@/components/public/PublicShell";
import HeroMemoryField from "@/components/public/HeroMemoryField";
import { FadeIn } from "@/components/public/Motion";

export default function HomePage() {
  return (
    <PublicShell>
      <main>
        <section className="mx-auto grid min-h-[calc(100vh-74px)] max-w-7xl items-center gap-10 px-5 py-14 sm:px-6 lg:grid-cols-[1.04fr,.96fr] lg:px-8">
          <FadeIn>
            <div className="max-w-[720px]">
              <div className="text-[11px] font-semibold uppercase tracking-[0.23em] text-signal-blue">Industrial operating memory</div>
              <h1 className="mt-5 text-[44px] font-semibold leading-[.98] tracking-[-0.065em] text-ink sm:text-[64px]">
                Find the evidence behind an asset decision, before the plant forgets it.
              </h1>
              <p className="mt-7 max-w-[640px] text-[16px] leading-8 text-ink-soft">
                Mnemos connects maintenance history, procedures, inspection records, failures, expert knowledge, and compliance evidence around the assets your teams operate.
              </p>
              <div className="mt-9 flex flex-wrap items-center gap-3">
                <Link href="/dashboard" className="rounded-full bg-rail px-5 py-3 text-[13px] font-medium text-white transition hover:bg-rail-raised">Enter workspace</Link>
                <Link href="/documentation" className="rounded-full border border-line bg-paper px-5 py-3 text-[13px] font-medium text-ink transition hover:bg-paper-alt">Explore how it works</Link>
              </div>
              <div className="mt-10 flex flex-wrap gap-x-7 gap-y-3 text-[12px] text-ink-faint">
                <span>Asset-centred</span><span>Evidence-linked</span><span>Review-governed</span><span>Site-scoped</span>
              </div>
            </div>
          </FadeIn>
          <FadeIn delay={0.1}><HeroMemoryField /></FadeIn>
        </section>

        <section className="border-y border-line bg-paper">
          <div className="mx-auto grid max-w-7xl gap-0 px-5 sm:px-6 lg:grid-cols-3 lg:px-8">
            {[
              ["01", "Recover context", "Trace a failure from an asset to events, work orders, procedures, and source evidence."],
              ["02", "Reason with limits", "Separate supported claims, contradictions, hypotheses, and evidence gaps."],
              ["03", "Keep decisions governed", "Move findings into RCA, compliance, and expert-review workflows without losing provenance."],
            ].map(([n,title,text])=>(
              <div key={n} className="interactive-row border-b border-line py-8 lg:border-b-0 lg:border-r lg:px-8 lg:first:pl-0 lg:last:border-r-0">
                <div className="font-mono text-[11px] text-signal-blue">{n}</div>
                <h2 className="mt-4 text-[20px] font-semibold tracking-[-0.03em] text-ink">{title}</h2>
                <p className="mt-3 max-w-sm text-[13.5px] leading-7 text-ink-soft">{text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-20 sm:px-6 lg:px-8">
          <div className="grid gap-10 lg:grid-cols-[.8fr,1.2fr]">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-signal-blue">One operational surface</div>
              <h2 className="mt-3 text-[34px] font-semibold tracking-[-0.05em] text-ink">Not another chat window beside the real work.</h2>
              <p className="mt-5 text-[14px] leading-7 text-ink-soft">Mnemos embeds intelligence into asset passports, investigations, documents, compliance checks, graph views, and expert knowledge review.</p>
            </div>
            <div className="divide-y divide-line border-y border-line">
              {[
                ["Asset Passport", "Operational history, evidence health, aliases, relationships, and related knowledge."],
                ["Investigations", "Claims, hypotheses, corrective actions, missing evidence, and governed approval."],
                ["Document Intelligence", "Parsing, OCR, section-aware chunks, provenance, and ingestion status."],
                ["Knowledge Graph", "Bounded relationships that map entities back to source evidence."],
              ].map(([title,text],i)=>(
                <div key={title} className="interactive-row grid gap-3 py-5 md:grid-cols-[44px,180px,1fr]">
                  <span className="font-mono text-[11px] text-ink-faint">0{i+1}</span>
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
