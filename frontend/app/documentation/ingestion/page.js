import DocLayout from "@/components/public/DocLayout";
import { SequenceDiagram } from "@/components/public/Diagrams";

export const metadata = { title: "Ingestion and evidence" };

export default function IngestionPage() {
  return (
    <DocLayout
      eyebrow="Ingestion"
      title="How raw plant material becomes retrieval-ready evidence."
      summary="The ingestion layer converts documents and field records into durable evidence objects with chunking, metadata, embeddings, graph entities, and provenance strong enough to support downstream reasoning."
    >
      <div className="grid gap-6">
        <SequenceDiagram />
        <section className="rounded-[28px] border border-line bg-paper p-6">
          <h2 className="text-[22px] font-semibold tracking-[-0.03em] text-ink">Evidence pipeline</h2>
          <div className="mt-4 grid gap-3">
            {[
              "Upload and source binding: every file is attached to a tenant, site, asset scope, source type, and revision context.",
              "Parsing and OCR: PDFs, images, and semi-structured records are normalized so the system retains both content and positional evidence.",
              "Chunking and metadata: chunks are section-aware and carry document, revision, source, and evidence-region metadata.",
              "Embedding and indexing: chunks are embedded once the model contract is fixed, then indexed in pgvector with the correct dimensional configuration.",
              "Entity and relation extraction: assets, procedures, failures, events, requirements, and work-order references are extracted into graph entities.",
              "Provenance retention: every graph assertion and evidence citation points back to a document, chunk, and locator.",
            ].map((item) => (
              <div key={item} className="rounded-2xl border border-line bg-paper-alt px-4 py-4 text-[13px] leading-6 text-ink-soft">{item}</div>
            ))}
          </div>
        </section>
      </div>
    </DocLayout>
  );
}
