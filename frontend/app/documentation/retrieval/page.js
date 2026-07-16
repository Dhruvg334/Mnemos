import DocLayout from "@/components/public/DocLayout";

export const metadata = { title: "Query and retrieval engine" };

export default function RetrievalPage() {
  return (
    <DocLayout
      eyebrow="Retrieval"
      title="Hybrid retrieval built around evidence quality, not just recall."
      summary="Mnemos does not treat all questions as identical. Query classification, scope constraints, graph context, vector search, and reranking combine to produce a context bundle that is useful enough for a reasoning layer and explicit enough for citation."
    >
      <div className="grid gap-6">
        <section className="rounded-[28px] border border-line bg-paper p-6">
          <h2 className="text-[22px] font-semibold tracking-[-0.03em] text-ink">Retrieval sequence</h2>
          <div className="mt-4 grid gap-3">
            {[
              "Intent classification chooses a retrieval strategy instead of forcing one universal pipeline.",
              "Scope resolution applies user, site, asset, and document-type constraints before retrieval expands candidate space.",
              "Vector retrieval surfaces semantically similar chunks from the evidence store.",
              "Graph traversal introduces structurally related entities and evidence candidates rather than naïvely mixing graph and cosine scores.",
              "Reranking promotes the strongest evidence bundle and preserves candidate order even in degraded mode.",
              "Answer composition yields supported claims, contradictions, missing evidence, and citations instead of a single unsupported paragraph.",
            ].map((item) => (
              <div key={item} className="rounded-2xl border border-line bg-paper-alt px-4 py-4 text-[13px] leading-6 text-ink-soft">{item}</div>
            ))}
          </div>
        </section>
        <section className="rounded-[28px] border border-line bg-paper p-6">
          <h2 className="text-[22px] font-semibold tracking-[-0.03em] text-ink">Important safeguards</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {[
              "No silent empty-result fallbacks when the vector store is unavailable.",
              "Embedding dimension must remain locked to the chosen model contract.",
              "Graph expansion requires constraints on depth, edges, and candidate volume.",
              "Duplicate entity aliases must normalize to a canonical identity before being trusted.",
            ].map((item) => (
              <div key={item} className="rounded-2xl border border-line bg-paper-alt px-4 py-4 text-[13px] leading-6 text-ink-soft">{item}</div>
            ))}
          </div>
        </section>
      </div>
    </DocLayout>
  );
}
