import PublicShell from "@/components/public/PublicShell";

const stages = [
  ["01", "Ingest", "Documents, logs, inspections and procedures enter a governed ingestion lifecycle with versioning, checksum validation and source metadata."],
  ["02", "Structure", "Content is parsed into evidence regions and chunks. Assets, events, procedures, failures and requirements are resolved into canonical entities."],
  ["03", "Retrieve", "Query classification selects a bounded strategy across metadata, vector similarity, graph traversal and structured records."],
  ["04", "Reason", "Candidates are deduplicated, reranked and converted into supported claims, conflicts, hypotheses and missing-evidence statements."],
  ["05", "Govern", "The backend validates scope, persists citations and audit history, and routes RCA, compliance and expert knowledge through human review."],
];

export const metadata = { title: "How Mnemos works" };

export default function HowItWorksPage() {
  return (
    <PublicShell>
      <section className="border-b border-line">
        <div className="mx-auto max-w-7xl px-5 py-20 sm:px-7 lg:px-8">
          <div className="max-w-3xl">
            <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-signal-blue-deep">How it works</div>
            <h1 className="mt-4 text-[40px] font-semibold leading-[1.1] tracking-[-0.035em] text-ink sm:text-[48px]">From industrial records to evidence-backed operational intelligence.</h1>
            <p className="mt-5 max-w-2xl text-[15px] leading-7 text-ink-soft">Mnemos combines document intelligence, asset identity, graph relationships and retrieval evaluation while keeping application security and persistence under backend control.</p>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-16 sm:px-7 lg:px-8">
        <div className="grid gap-0 border-l border-t border-line">
          {stages.map(([n, title, text]) => (
            <div key={n} className="grid border-b border-r border-line md:grid-cols-[120px_220px_1fr]">
              <div className="border-b border-line p-5 font-mono text-[12px] text-signal-blue-deep md:border-b-0 md:border-r">{n}</div>
              <div className="border-b border-line p-5 text-[16px] font-semibold text-ink md:border-b-0 md:border-r">{title}</div>
              <div className="p-5 text-[13px] leading-6 text-ink-soft">{text}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="border-y border-line bg-paper-alt">
        <div className="mx-auto max-w-7xl px-5 py-16 sm:px-7 lg:px-8">
          <div className="grid gap-10 lg:grid-cols-[.8fr_1.2fr]">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-ink-faint">System boundary</div>
              <h2 className="mt-3 text-[28px] font-semibold tracking-[-0.02em] text-ink">Clear ownership across product layers.</h2>
              <p className="mt-3 text-[13px] leading-6 text-ink-soft">The frontend never talks directly to the agent layer. The backend remains the authority for authentication, tenancy, validation, audit and application state.</p>
            </div>
            <Architecture />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-16 sm:px-7 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-3">
          <Principle title="Bounded retrieval" text="Graph depth, candidate count, tenant scope and evidence authority are constrained before generation." />
          <Principle title="Explicit uncertainty" text="Supported facts, inferences, contradictions and missing records are represented separately." />
          <Principle title="Human authority" text="Operational closure and approval remain deliberate user actions with immutable review history." />
        </div>
      </section>
    </PublicShell>
  );
}

function Architecture() {
  const boxes = ["Web application", "Versioned backend API", "Agent execution service", "Vector + graph stores"];
  return <div className="rounded-lg border border-line bg-paper p-4 sm:p-6"><div className="space-y-3">{boxes.map((box, index) => <div key={box}><div className="rounded-md border border-line bg-paper px-4 py-3"><div className="text-[12px] font-semibold text-ink">{box}</div><div className="mt-1 text-[11px] text-ink-faint">{["Product workflows and evidence presentation", "Auth, tenancy, validation, persistence and audit", "Retrieval, reasoning and structured result generation", "Source chunks, embeddings, entities and relationships"][index]}</div></div>{index < boxes.length - 1 && <div className="mx-auto h-3 w-px bg-line-strong" />}</div>)}</div></div>;
}

function Principle({ title, text }) {
  return <div className="border-t-2 border-ink pt-5"><h3 className="text-[15px] font-semibold text-ink">{title}</h3><p className="mt-2 text-[13px] leading-6 text-ink-soft">{text}</p></div>;
}
