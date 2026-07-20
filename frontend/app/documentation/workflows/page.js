import DocLayout from "@/components/public/DocLayout";
import { IngestionWorkflowDiagram, GovernanceWorkflowDiagram } from "@/components/public/Diagrams";

export const metadata = { title: "End-to-end workflows" };

export default function Page() {
  return (
    <DocLayout
      eyebrow="Workflows"
      title="From document arrival to governed operational action."
      summary="Mnemos links ingestion, retrieval, investigation, review, and audit into one traceable lifecycle."
    >
      <div className="grid gap-8">
        <section>
          <h2 className="mb-4 text-[18px] font-semibold text-ink">Document Ingestion</h2>
          <IngestionWorkflowDiagram />
        </section>
        <section>
          <h2 className="mb-4 text-[18px] font-semibold text-ink">Knowledge Governance</h2>
          <GovernanceWorkflowDiagram />
        </section>
      </div>
    </DocLayout>
  );
}
