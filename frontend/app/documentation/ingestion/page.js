import DocLayout from "@/components/public/DocLayout";
import { IngestionWorkflowDiagram } from "@/components/public/Diagrams";

export const metadata = { title: "Ingestion and evidence" };

const behaviours = [
  ["PDF", "Page-aware text extraction with retained page locators. Image-only files fail visibly because OCR is not currently available."],
  ["TXT and Markdown", "Safe decoding, normalized line endings, and retained source context."],
  ["CSV", "Bounded rows, columns, and cells with headers rendered into readable evidence excerpts."],
  ["DOCX", "Paragraph extraction with heading context where the document exposes it."],
  ["XLSX", "Bounded sheet and cell extraction with sheet names and row context."],
  ["Provider degradation", "Lexical evidence remains available when embeddings, Neo4j, the reranker, or Groq are unavailable."],
];

export default function Page() {
  return (
    <DocLayout eyebrow="Ingestion" title="Every answer starts with a traceable evidence object." summary="Authenticated uploads move through checksum, role, size, MIME, storage, extraction, chunking, and provenance controls before becoming retrievable evidence.">
      <div className="grid gap-8">
        <IngestionWorkflowDiagram />
        <section className="rounded-[28px] border border-line bg-paper p-6">
          <h2 className="text-[22px] font-semibold text-ink">Guarded upload sequence</h2>
          <p className="mt-3 text-[13px] leading-6 text-ink-soft">The browser calculates SHA-256, requests a site-scoped upload session through the Next.js server proxy, uploads to an expiring presigned URL, and confirms the object. The backend rechecks size and content type, records audit context, extracts readable content, and persists evidence regions and overlapping chunks.</p>
          <div className="mt-5 grid gap-3 md:grid-cols-2">{behaviours.map(([title, text]) => <div key={title} className="rounded-2xl bg-paper-alt px-4 py-4"><div className="text-[13px] font-semibold text-ink">{title}</div><div className="mt-1 text-[12.5px] leading-6 text-ink-soft">{text}</div></div>)}</div>
        </section>
        <section className="rounded-[28px] border border-line bg-paper p-6">
          <h2 className="text-[22px] font-semibold text-ink">Truth boundaries</h2>
          <div className="mt-3 grid gap-2 text-[13px] leading-6 text-ink-soft"><p>Public demo documents are synthetic and read-only. Authenticated workspace documents are listed from the backend and processed from the uploaded object.</p><p>Embeddings and graph enrichment are best-effort. A document is not described as vector-indexed or graph-enriched unless those stages complete.</p><p>Source locators, tenant, site, document revision, checksum, MIME type, and timestamps remain attached to persisted evidence.</p></div>
        </section>
      </div>
    </DocLayout>
  );
}
