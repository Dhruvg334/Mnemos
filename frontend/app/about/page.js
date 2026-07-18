import PublicShell from "@/components/public/PublicShell";

const team = [
  {
    name: "Dhruv Gupta",
    role: "Backend, integration, infrastructure, and deployment",
    detail: "Owns the application control plane, API contracts, persistence, authentication, security controls, cloud deployment, and the integration boundary across all product layers.",
  },
  {
    name: "Pavit Aggarwal",
    role: "Agentic intelligence and retrieval",
    detail: "Owns the AI reasoning layer, including ingestion intelligence, query classification, hybrid retrieval, graph reasoning, reranking, evidence composition, and retrieval evaluation.",
  },
  {
    name: "Akshhaya",
    role: "Frontend, UI, and product experience",
    detail: "Owns the operational product surface, dashboard interaction model, visual hierarchy, and the user experience through which plant teams access Mnemos workflows.",
  },
];

export const metadata = { title: "About" };

export default function AboutPage() {
  return (
    <PublicShell>
      <main className="mx-auto max-w-6xl px-5 py-12 sm:px-6 lg:px-8">
        <section className="border-b border-line pb-12">
          <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-signal-blue">About Mnemos</div>
          <h1 className="mt-4 max-w-4xl text-[42px] font-semibold leading-[1.02] tracking-[-0.055em] text-ink">
            Mnemos is being built as an industrial operating memory, not a generic AI assistant.
          </h1>
          <p className="mt-6 max-w-3xl text-[15px] leading-8 text-ink-soft">
            Industrial teams already have information. The deeper problem is fragmentation: procedures live in one system, work orders in another, inspection evidence in files, failure context in shift logs, and important judgement in the memory of experienced people. Mnemos brings those sources together around the asset and keeps every conclusion tied to evidence and review.
          </p>
        </section>

        <section className="grid gap-10 border-b border-line py-12 lg:grid-cols-[0.8fr,1.2fr]">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-signal-blue">Project direction</div>
            <h2 className="mt-3 text-[30px] font-semibold tracking-[-0.045em] text-ink">From document search to governed operational intelligence.</h2>
          </div>
          <div className="grid gap-5 text-[14px] leading-7 text-ink-soft">
            <p>
              The product direction is intentionally broader than retrieval. Mnemos connects document intelligence, asset history, knowledge graphs, RCA, compliance, expert knowledge, and operational governance into one coherent workflow.
            </p>
            <p>
              The current build prioritizes technical credibility: strict backend ownership, hybrid retrieval, evidence mapping, provenance, role-scoped access, review workflows, audit logging, and production-oriented infrastructure. The frontend is designed to keep this depth accessible rather than expose raw architecture to plant users.
            </p>
          </div>
        </section>

        <section className="border-b border-line py-12">
          <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-signal-blue">Why it was designed this way</div>
          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            {[
              ["Assets are the organizing unit", "Plant teams make decisions around equipment, not embeddings or chat threads. Every workflow therefore resolves back to an asset, site, event, and evidence trail."],
              ["Evidence is part of the answer", "A response without provenance is insufficient for RCA or compliance. Mnemos returns supported claims, contradictions, citations, and missing evidence."],
              ["Governance is part of usability", "Approvals, review states, supersession, and audit logs are built into the product because trust depends on controlled operational memory."],
            ].map(([title, text]) => (
              <div key={title}>
                <h3 className="text-[18px] font-semibold tracking-[-0.03em] text-ink">{title}</h3>
                <p className="mt-3 text-[13.5px] leading-7 text-ink-soft">{text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="border-b border-line py-12">
          <div className="grid gap-10 lg:grid-cols-[0.8fr,1.2fr]">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-signal-blue">How it helps</div>
              <h2 className="mt-3 text-[30px] font-semibold tracking-[-0.045em] text-ink">Turn scattered operational evidence into decisions teams can defend.</h2>
            </div>
            <div className="divide-y divide-line border-y border-line">
              {[
                ["Reliability", "Reconstruct recurring failure patterns across work orders, inspection evidence, procedures, and similar incidents."],
                ["Operations", "Recover asset context without manually searching across disconnected records and teams."],
                ["Compliance", "Map requirements to current, missing, expired, or conflicting evidence and retain review history."],
                ["Knowledge continuity", "Capture expert judgement in a governed form that survives handovers and workforce changes."],
              ].map(([title, text]) => (
                <div key={title} className="grid gap-2 py-4 md:grid-cols-[140px,1fr]">
                  <div className="text-[13px] font-semibold text-ink">{title}</div>
                  <div className="text-[13px] leading-6 text-ink-soft">{text}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="py-12">
          <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-signal-blue">Team</div>
          <h2 className="mt-3 text-[30px] font-semibold tracking-[-0.045em] text-ink">Three parallel engineering streams, one shared product contract.</h2>
          <div className="mt-8 divide-y divide-line border-y border-line">
            {team.map((member, index) => (
              <div key={member.name} className="grid gap-3 py-5 md:grid-cols-[44px,190px,250px,1fr]">
                <div className="font-mono text-[10.5px] text-signal-blue">0{index + 1}</div>
                <div className="text-[14px] font-semibold text-ink">{member.name}</div>
                <div className="text-[13px] font-medium text-ink-soft">{member.role}</div>
                <div className="text-[13px] leading-6 text-ink-soft">{member.detail}</div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </PublicShell>
  );
}
