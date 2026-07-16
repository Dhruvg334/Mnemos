import Link from "next/link";
import DocLayout from "@/components/public/DocLayout";
import { ArchitectureDiagram, FlowTable, SequenceDiagram } from "@/components/public/Diagrams";

const rows = [
  {
    layer: "Product layer",
    responsibility: "Public site, documentation, authenticated dashboard, and role-aware operational experiences.",
    output: "Navigation, workflows, and action surfaces that expose evidence without exposing raw implementation internals.",
  },
  {
    layer: "Control plane",
    responsibility: "API orchestration, authentication, tenancy, audit, RCA, compliance, and expert-knowledge lifecycle management.",
    output: "Structured application records and governed workflow state.",
  },
  {
    layer: "Reasoning plane",
    responsibility: "Query classification, retrieval planning, evidence gathering, reranking, contradiction handling, and answer composition.",
    output: "Claims, citations, missing evidence, and confidence-backed answers.",
  },
  {
    layer: "Knowledge substrate",
    responsibility: "Persistent evidence, embeddings, graph structure, and object storage for raw source material.",
    output: "A durable operational memory with provenance.",
  },
];

export const metadata = {
  title: "Documentation",
};

export default function DocumentationPage() {
  return (
    <DocLayout
      eyebrow="Documentation"
      title="The complete product design behind Mnemos."
      summary="This section documents the product architecture, ingestion pipeline, hybrid retrieval engine, governance model, and operational deployment design. It is written to explain how Mnemos works as a system, not just how the UI looks."
    >
      <div className="grid gap-6">
        <section className="rounded-[28px] border border-line bg-paper p-6">
          <h2 className="text-[24px] font-semibold tracking-[-0.03em] text-ink">System overview</h2>
          <p className="mt-3 text-[14px] leading-7 text-ink-soft">
            Mnemos is organized as a product stack with clear ownership boundaries. The frontend presents a restrained, operational interface. The backend owns authorization, workflow state, and auditability. The agentic layer performs retrieval and reasoning but does not become the source of truth for business records.
          </p>
        </section>

        <ArchitectureDiagram />
        <SequenceDiagram />
        <FlowTable rows={rows} />

        <section className="rounded-[28px] border border-line bg-paper p-6">
          <h2 className="text-[22px] font-semibold tracking-[-0.03em] text-ink">Documentation map</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {[
              ["/documentation/architecture", "System architecture", "Core system boundaries, major services, and component relationships."],
              ["/documentation/ingestion", "Ingestion and evidence", "How source material becomes structured evidence with provenance."],
              ["/documentation/retrieval", "Query and retrieval engine", "How Mnemos chooses retrieval strategies and grounds answers."],
              ["/documentation/governance", "Governance and review", "Approval flows, auditability, and role-aware workflow control."],
              ["/documentation/deployment", "Deployment and operations", "Infrastructure, CI, runtime contracts, and production concerns."],
            ].map(([href, title, body]) => (
              <Link key={href} href={href} className="rounded-2xl border border-line bg-paper-alt p-4 transition hover:bg-paper">
                <div className="text-[15px] font-semibold text-ink">{title}</div>
                <div className="mt-2 text-[13px] leading-6 text-ink-soft">{body}</div>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </DocLayout>
  );
}
