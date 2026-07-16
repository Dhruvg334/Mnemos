import DocLayout from "@/components/public/DocLayout";

export const metadata = { title: "Governance and review" };

export default function GovernancePage() {
  return (
    <DocLayout
      eyebrow="Governance"
      title="Governance is embedded in product workflows, not attached later as paperwork."
      summary="Mnemos treats review, approval, provenance, and auditability as first-class product features. This is necessary for industrial trust and for workflows such as RCA, compliance, and expert-knowledge acceptance."
    >
      <div className="grid gap-6">
        <section className="rounded-[28px] border border-line bg-paper p-6">
          <h2 className="text-[22px] font-semibold tracking-[-0.03em] text-ink">Governed flows</h2>
          <div className="mt-4 grid gap-3">
            {[
              "RCA investigations move through structured stages rather than ad hoc note-taking.",
              "Compliance evidence is evaluated against requirements with explicit status and review state.",
              "Expert knowledge enters the system through submission, review, approval, and supersession.",
              "Audit logs capture changes, actor identity, resource, and action trace for operational review.",
              "Access is role- and site-scoped so knowledge does not leak across unrelated operational contexts.",
            ].map((item) => (
              <div key={item} className="rounded-2xl border border-line bg-paper-alt px-4 py-4 text-[13px] leading-6 text-ink-soft">{item}</div>
            ))}
          </div>
        </section>
      </div>
    </DocLayout>
  );
}
