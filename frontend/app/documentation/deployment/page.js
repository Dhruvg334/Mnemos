import DocLayout from "@/components/public/DocLayout";

export const metadata = { title: "Deployment and operations" };

export default function DeploymentPage() {
  return (
    <DocLayout
      eyebrow="Operations"
      title="Built for a deployment path that can mature beyond a hackathon demo."
      summary="The current architecture already separates concerns in a way that supports testing, CI, staging, and eventual production hardening. The remaining work is mainly integration and environment validation rather than a redesign."
    >
      <div className="grid gap-6">
        <section className="rounded-[28px] border border-line bg-paper p-6">
          <h2 className="text-[22px] font-semibold tracking-[-0.03em] text-ink">Operational checklist</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {[
              "Frontend build validation and route-level QA.",
              "Backend CI for lint, compile, test, and migration execution.",
              "pgvector-capable PostgreSQL for both local and CI environments.",
              "Neo4j connectivity and non-default credential enforcement.",
              "Agent service configuration for embeddings, reranking, and LLM access.",
              "Secure secret handling, rate limiting, and structured error responses.",
            ].map((item) => (
              <div key={item} className="rounded-2xl border border-line bg-paper-alt px-4 py-4 text-[13px] leading-6 text-ink-soft">{item}</div>
            ))}
          </div>
        </section>
      </div>
    </DocLayout>
  );
}
