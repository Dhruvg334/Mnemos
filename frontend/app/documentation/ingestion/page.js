import DocLayout from "@/components/public/DocLayout";
import { IngestionWorkflowDiagram } from "@/components/public/Diagrams";

export const metadata = { title: "Ingestion and evidence" };

export default function Page() {
  return (
    <DocLayout
      eyebrow="Ingestion"
      title="Every answer starts with a traceable evidence object."
      summary="The ingestion pipeline converts heterogeneous plant material into structured chunks, embeddings, entities, relationships, and locators without discarding source provenance."
    >
      <div className="grid gap-8">
        <IngestionWorkflowDiagram />
        <section className="rounded-[28px] border border-line bg-paper p-6">
          <h2 className="text-[22px] font-semibold text-ink">Document-aware processing</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {[
              "PDF and scanned documents: OCR, page structure, headings, and bounding regions.",
              "Tables and spreadsheets: sheet, row, column, and header context.",
              "Work orders and logs: asset tags, event dates, failure codes, and action history.",
              "Procedures and requirements: revision, supersession, applicability, and authority.",
              "Images and diagrams: extracted text, page locator, and source-region linkage.",
              "Expert notes: author, review state, scope, support, and temporal validity.",
            ].map((x) => (
              <div key={x} className="rounded-2xl bg-paper-alt px-4 py-4 text-[13px] leading-6 text-ink-soft">{x}</div>
            ))}
          </div>
        </section>
      </div>
    </DocLayout>
  );
}
