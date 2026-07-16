import PublicShell from "@/components/public/PublicShell";

const principles = [
  {
    title: "Evidence before elegance",
    text: "The product is intentionally designed around source evidence, revision context, and role-scoped actions. Good visual design should not hide operational uncertainty.",
  },
  {
    title: "Assets as the organizing unit",
    text: "Operators do not think in embeddings or agents. They think in pumps, exchangers, compressors, work orders, and investigation history.",
  },
  {
    title: "Governance is part of usability",
    text: "Review workflows, approvals, and provenance are not administrative extras. They are what make the system trustworthy during real plant operations.",
  },
];

export const metadata = {
  title: "About",
};

export default function AboutPage() {
  return (
    <PublicShell>
      <main className="mx-auto max-w-6xl px-5 py-12 sm:px-6 lg:px-8">
        <div className="rounded-[36px] border border-line bg-paper p-8 surface-glow sm:p-10">
          <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-signal-blue">About Mnemos</div>
          <h1 className="mt-4 max-w-4xl text-[40px] font-semibold tracking-[-0.05em] text-ink">Mnemos is designed as an operating memory, not just an AI layer.</h1>
          <p className="mt-5 max-w-3xl text-[15px] leading-8 text-ink-soft">
            Industrial teams already have data. The real problem is that evidence is fragmented across procedures, work orders, inspection notes, spreadsheets, expert memory, and inconsistent document trails. Mnemos is built to recover that knowledge, structure it, and keep it reviewable.
          </p>
        </div>

        <div className="mt-8 grid gap-4 lg:grid-cols-3">
          {principles.map((item) => (
            <div key={item.title} className="rounded-[28px] border border-line bg-paper p-6">
              <h2 className="text-[18px] font-semibold tracking-[-0.03em] text-ink">{item.title}</h2>
              <p className="mt-3 text-[14px] leading-7 text-ink-soft">{item.text}</p>
            </div>
          ))}
        </div>

        <div className="mt-8 rounded-[32px] border border-line bg-paper p-8">
          <h2 className="text-[22px] font-semibold tracking-[-0.03em] text-ink">What the product covers</h2>
          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            {[
              "Asset passports with history, citations, compliance state, and related knowledge.",
              "Document ingestion with evidence extraction, provenance, and retrieval readiness.",
              "Investigation and RCA workflows with claims, contradictions, and missing evidence handling.",
              "Expert-knowledge capture governed by review and supersession instead of hidden chat history.",
            ].map((item) => (
              <div key={item} className="rounded-2xl border border-line bg-paper-alt px-4 py-4 text-[13px] leading-6 text-ink-soft">
                {item}
              </div>
            ))}
          </div>
        </div>
      </main>
    </PublicShell>
  );
}
