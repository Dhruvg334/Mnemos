import DocLayout from "@/components/public/DocLayout";
import { DeploymentTopologyDiagram } from "@/components/public/Diagrams";

export const metadata = { title: "Deployment and operations" };

export default function Page() {
  return (
    <DocLayout
      eyebrow="Operations"
      title="Deployment is treated as part of system correctness."
      summary="The system is deployed across Vercel (frontend), Render Cloud (backend API + managed PostgreSQL + Redis), and optional Hugging Face Spaces (reranker). A Docker Compose production configuration is available for self-hosted deployments."
    >
      <div className="grid gap-8">
        <DeploymentTopologyDiagram />

        <section className="rounded-[28px] border border-line bg-paper p-6">
          <h2 className="text-[22px] font-semibold text-ink">Deployment options</h2>
          <div className="mt-4 grid gap-4">
            {[
              ["Vercel", "Next.js frontend deployed via Vercel with framework preset. Static generation and SSR for documentation pages. API calls proxied to Render backend via environment-configured URL. Auth cookie domain must match between frontend and API."],
              ["Render Cloud", "Single Docker web service running FastAPI on the free tier. Includes managed PostgreSQL 16 and Redis 7. Neo4j is disabled for free-tier optimisation. Background tasks run in-process via QUERY_DISPATCH_MODE=background."],
              ["Docker Compose (Self-hosted)", "Production compose file (docker-compose.production.yml) deploys API, PostgreSQL+pgvector, Redis, MinIO (S3), and optional Neo4j. Separate migrate service handles Alembic migrations. Uses non-root user and read-only rootfs for security."],
              ["Hugging Face Spaces", "Standalone cross-encoder reranker microservice deployed as a Docker Space. Exposes POST / endpoint for reranking. Configurable model via MODEL_NAME env var. Not bundled with the main API — runs as an independent service."],
            ].map(([title, text]) => (
              <div key={title} className="rounded-2xl bg-paper-alt px-4 py-4">
                <div className="text-[13px] font-semibold text-ink">{title}</div>
                <div className="mt-1 text-[13px] leading-6 text-ink-soft">{text}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-[28px] border border-line bg-paper p-6">
          <h2 className="text-[22px] font-semibold text-ink">Operational checks</h2>
          <div className="mt-4 grid gap-3">
            {[
              "Run Alembic migrations in a separate job before API deployment.",
              "Use pgvector-enabled PostgreSQL in local, CI, and deployed environments.",
              "Verify database, Redis, and object storage readiness independently from liveness.",
              "Keep agent and ingestion services behind authenticated service contracts.",
              "Store secrets outside Git and validate required production configuration at startup.",
              "Retain structured logs with request, query, run, and trace identifiers.",
            ].map((x) => (
              <div key={x} className="rounded-2xl bg-paper-alt px-4 py-4 text-[13px] leading-6 text-ink-soft">{x}</div>
            ))}
          </div>
        </section>
      </div>
    </DocLayout>
  );
}
