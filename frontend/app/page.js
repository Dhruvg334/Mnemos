import Link from "next/link";
import PublicShell from "@/components/public/PublicShell";
import { ArchitectureDiagram, SequenceDiagram } from "@/components/public/Diagrams";
import { FadeIn, FloatCard } from "@/components/public/Motion";

const pillars = [
  {
    title: "Evidence-grounded answers",
    body: "Mnemos does not stop at semantic search. Every operational answer is backed by claims, contradictions, missing evidence, and document-linked citations.",
  },
  {
    title: "Asset-centred intelligence",
    body: "The product organizes knowledge around real plant assets, not abstract chat sessions. That keeps investigation, compliance, and maintenance context aligned.",
  },
  {
    title: "Governed operational memory",
    body: "Expert notes, reviews, RCA conclusions, and requirement checks are versioned and reviewable instead of disappearing into ad hoc conversations.",
  },
];

const stats = [
  { value: "56", label: "Backend endpoints already structured across auth, assets, documents, RCA, compliance, expert knowledge, and audit." },
  { value: "3", label: "Knowledge layers connected in one system: vector evidence, graph relationships, and governed business records." },
  { value: "1", label: "Single product surface for reliability, operations, compliance, and engineering review." },
];

export default function HomePage() {
  return (
    <PublicShell>
      <main>
        <section className="mx-auto max-w-7xl px-5 pb-8 pt-12 sm:px-6 lg:px-8 lg:pt-16">
          <div className="grid gap-8 lg:grid-cols-[1.15fr,0.85fr] lg:items-end">
            <FadeIn>
              <div className="rounded-[36px] border border-line bg-paper p-8 surface-glow sm:p-10">
                <div className="inline-flex rounded-full border border-line bg-paper-alt px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-signal-blue">
                  Industrial knowledge intelligence
                </div>
                <h1 className="mt-5 max-w-4xl text-[40px] font-semibold leading-[1.02] tracking-[-0.06em] text-ink sm:text-[58px]">
                  A governed operating memory for plants that cannot afford shallow answers.
                </h1>
                <p className="mt-6 max-w-2xl text-[15px] leading-8 text-ink-soft">
                  Mnemos unifies plant documents, work orders, inspection evidence, asset history, and expert knowledge into a product designed for reliability, RCA, compliance, and operational decision support.
                </p>
                <div className="mt-8 flex flex-wrap gap-3">
                  <Link href="/dashboard" className="rounded-full bg-rail px-5 py-3 text-[13px] font-medium text-white transition hover:bg-rail-raised">
                    Open dashboard
                  </Link>
                  <Link href="/documentation" className="rounded-full border border-line bg-paper px-5 py-3 text-[13px] font-medium text-ink transition hover:bg-paper-alt">
                    Open documentation
                  </Link>
                </div>
              </div>
            </FadeIn>

            <FloatCard className="rounded-[36px] border border-line bg-paper p-6 surface-glow sm:p-8">
              <div className="grid-noise rounded-[28px] border border-line bg-paper-alt p-5">
                <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-[0.16em] text-ink-faint">
                  <span>Live investigation surface</span>
                  <span className="rounded-full bg-signal-blue-pale px-2 py-1 text-signal-blue-deep">P-117</span>
                </div>
                <div className="mt-5 rounded-3xl border border-line bg-paper p-5">
                  <div className="text-[13px] font-semibold text-ink">Why has P-117 repeatedly failed?</div>
                  <div className="mt-3 text-[13px] leading-7 text-ink-soft">
                    Recurring mechanical-seal failure is strongly associated with documented coupling offset, elevated vibration, and missing post-maintenance evidence. The system retains abstention where proof is incomplete.
                  </div>
                  <div className="mt-5 grid gap-3">
                    {[
                      "Supported: coupling offset was recorded during the second event.",
                      "Supported: overall vibration reached 7.8 mm/s before the third recurrence.",
                      "Missing evidence: no vibration spectrum is attached to the evidence bundle.",
                    ].map((item) => (
                      <div key={item} className="rounded-2xl border border-line bg-paper-alt px-4 py-3 text-[12.5px] text-ink-soft">
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </FloatCard>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-8 sm:px-6 lg:px-8">
          <div className="grid gap-4 lg:grid-cols-3">
            {stats.map((stat, index) => (
              <FadeIn key={stat.value} delay={index * 0.06} className="rounded-[28px] border border-line bg-paper p-6">
                <div className="text-[36px] font-semibold tracking-[-0.05em] text-ink">{stat.value}</div>
                <div className="mt-3 text-[13px] leading-7 text-ink-soft">{stat.label}</div>
              </FadeIn>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-8 sm:px-6 lg:px-8">
          <div className="mb-6 flex items-end justify-between gap-6">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-signal-blue">Product pillars</div>
              <h2 className="mt-2 text-[30px] font-semibold tracking-[-0.04em] text-ink">Built for teams that need evidence, not a prettier chatbot.</h2>
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            {pillars.map((pillar, index) => (
              <FloatCard key={pillar.title} className="rounded-[28px] border border-line bg-paper p-6" delay={index * 0.05}>
                <div className="text-[18px] font-semibold tracking-[-0.03em] text-ink">{pillar.title}</div>
                <p className="mt-3 text-[14px] leading-7 text-ink-soft">{pillar.body}</p>
              </FloatCard>
            ))}
          </div>
        </section>

        <section className="mx-auto grid max-w-7xl gap-8 px-5 py-8 sm:px-6 lg:grid-cols-[1.05fr,0.95fr] lg:px-8">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-signal-blue">Architecture preview</div>
            <h2 className="mt-2 text-[30px] font-semibold tracking-[-0.04em] text-ink">From upload to grounded answer.</h2>
            <p className="mt-4 max-w-xl text-[14px] leading-7 text-ink-soft">
              The product is structured around a strict evidence lifecycle: ingestion, normalization, retrieval, reasoning, citation, governance, and auditability. The documentation section expands every layer in detail.
            </p>
            <div className="mt-6 flex gap-3">
              <Link href="/documentation/architecture" className="rounded-full border border-line bg-paper px-4 py-2.5 text-[12.5px] font-medium text-ink transition hover:bg-paper-alt">
                Explore architecture
              </Link>
              <Link href="/documentation/retrieval" className="rounded-full border border-line bg-paper px-4 py-2.5 text-[12.5px] font-medium text-ink transition hover:bg-paper-alt">
                Query engine
              </Link>
            </div>
          </div>
          <ArchitectureDiagram />
        </section>

        <section className="mx-auto max-w-7xl px-5 py-8 sm:px-6 lg:px-8">
          <SequenceDiagram />
        </section>
      </main>
    </PublicShell>
  );
}
