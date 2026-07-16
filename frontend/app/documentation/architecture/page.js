import DocLayout from "@/components/public/DocLayout";
import { ArchitectureDiagram, FlowTable } from "@/components/public/Diagrams";

const rows = [
  { layer: "Public experience", responsibility: "Home, About, Documentation, Sign in, Sign up, and footer-level product framing.", output: "First-touch product understanding and access entry points." },
  { layer: "Operational experience", responsibility: "Asset overview, passports, documents, investigations, compliance, graph, and expert knowledge screens.", output: "Operational interaction surfaces grounded in business entities." },
  { layer: "Backend application", responsibility: "FastAPI endpoints, authorization, persistence, audit logging, rate limiting, and workflow orchestration.", output: "Trusted application records and API contracts." },
  { layer: "Agentic subsystem", responsibility: "Classification, retrieval planning, vector search, graph traversal, reranking, evidence mapping, and answer composition.", output: "Evidence-grounded results returned to the backend contract." },
  { layer: "Storage and indexing", responsibility: "PostgreSQL, pgvector, Neo4j, object storage, and ingestion artifacts.", output: "Durable operational memory and search infrastructure." },
];

export const metadata = { title: "System architecture" };

export default function ArchitecturePage() {
  return (
    <DocLayout
      eyebrow="Architecture"
      title="A layered architecture with controlled ownership boundaries."
      summary="Mnemos is designed so that the AI layer enriches the application without replacing application truth. Business workflows, approvals, and audit state remain backend-owned; retrieval and reasoning remain agent-owned."
    >
      <div className="grid gap-6">
        <ArchitectureDiagram />
        <FlowTable rows={rows} />
        <section className="rounded-[28px] border border-line bg-paper p-6">
          <h2 className="text-[22px] font-semibold tracking-[-0.03em] text-ink">Design decisions</h2>
          <div className="mt-4 grid gap-3">
            {[
              "The frontend is intentionally kept product-oriented and low-noise; implementation depth is documented separately rather than cluttering user workflows.",
              "The backend owns workflow truth so that an agent failure cannot directly corrupt compliance, RCA, or audit records.",
              "The agentic layer is integrated through a structured result contract, not uncontrolled direct writes into application tables.",
              "The knowledge substrate is split between vector retrieval, graph relationships, and durable source evidence because no single store is sufficient for this problem.",
            ].map((item) => (
              <div key={item} className="rounded-2xl border border-line bg-paper-alt px-4 py-4 text-[13px] leading-6 text-ink-soft">{item}</div>
            ))}
          </div>
        </section>
      </div>
    </DocLayout>
  );
}
