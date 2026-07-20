import DocLayout from "@/components/public/DocLayout";
import { PipelineArchitectureDiagram, AgentWorkflowDiagram } from "@/components/public/Diagrams";

export const metadata = { title: "Agentic orchestration" };

export default function Page() {
  return (
    <DocLayout
      eyebrow="Agentic system"
      title="A bounded reasoning workflow with explicit evidence outputs."
      summary="The agentic layer classifies intent, resolves entities, plans retrieval, combines graph and vector evidence, reranks candidates, and returns a structured result. It does not own application persistence."
    >
      <div className="grid gap-8">
        <section>
          <h2 className="mb-4 text-[18px] font-semibold text-ink">Pipeline Architecture</h2>
          <PipelineArchitectureDiagram />
        </section>

        <section>
          <h2 className="mb-4 text-[18px] font-semibold text-ink">Stage Overview</h2>
          <AgentWorkflowDiagram />
        </section>

        <section className="rounded-[28px] border border-line bg-paper p-6">
          <h2 className="text-[22px] font-semibold text-ink">Orchestration contract</h2>
          <div className="mt-4 grid gap-3">
            {[
              "Input includes tenant, site, user, asset, document, and access scope.",
              "The classifier selects an asset, RCA, compliance, lessons-learned, or general retrieval strategy.",
              "Entity resolution combines request scope, aliases, classifier entities, and canonical asset IDs.",
              "The final result contains claims, citations, confidence, contradictions, missing evidence, and run metadata.",
              "Backend validation remains the final boundary before any result becomes an application record.",
            ].map((x) => (
              <div key={x} className="rounded-2xl bg-paper-alt px-4 py-4 text-[13px] leading-6 text-ink-soft">{x}</div>
            ))}
          </div>
        </section>
      </div>
    </DocLayout>
  );
}
