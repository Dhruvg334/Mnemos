import DocLayout from "@/components/public/DocLayout";
import { GovernanceWorkflowDiagram } from "@/components/public/Diagrams";

export const metadata = { title: "Governance and review" };

export default function Page() {
  return (
    <DocLayout
      eyebrow="Governance"
      title="Knowledge becomes operational only after its authority is clear."
      summary="RCA conclusions, compliance findings, and expert knowledge move through explicit review states with role checks, evidence checks, versioning, supersession, and audit history."
    >
      <div className="grid gap-8">
        <GovernanceWorkflowDiagram />
        <section className="rounded-[28px] border border-line bg-paper p-6">
          <h2 className="text-[22px] font-semibold text-ink">Controls</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {[
              "Authors cannot approve their own RCA conclusions.",
              "Approved snapshots remain immutable.",
              "Expert knowledge can be superseded without deleting prior versions.",
              "Compliance findings retain requirement and evidence references.",
              "Every mutation records actor, action, resource, request ID, and time.",
              "Tenant and site boundaries apply before retrieval and before persistence.",
            ].map((x) => (
              <div key={x} className="rounded-2xl bg-paper-alt px-4 py-4 text-[13px] leading-6 text-ink-soft">{x}</div>
            ))}
          </div>
        </section>
      </div>
    </DocLayout>
  );
}
