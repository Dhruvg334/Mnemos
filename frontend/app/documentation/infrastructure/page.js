import DocLayout from "@/components/public/DocLayout";
import { InfrastructureDiagram } from "@/components/public/Diagrams";

export const metadata = { title: "Infrastructure topology" };

export default function Page() {
  return (
    <DocLayout
      eyebrow="Infrastructure"
      title="Services are separated by responsibility, failure domain, and data ownership."
      summary="The topology supports independent frontend, API, agent, ingestion, graph, vector, cache, and object-storage concerns while keeping the backend as the operational control plane."
    >
      <div className="grid gap-8">
        <InfrastructureDiagram />
        <section className="rounded-[28px] border border-line bg-paper p-6">
          <h2 className="text-[22px] font-semibold text-ink">Runtime responsibilities</h2>
          <p className="mt-3 text-[14px] leading-7 text-ink-soft">
            The frontend runs on Vercel with global CDN delivery. The backend API, PostgreSQL with pgvector, and Redis are deployed on Render Cloud as Docker containers. Neo4j runs in development via Docker Compose and is disabled on the free Render tier. Document storage uses S3-compatible object storage (MinIO in development, configurable in production). A standalone cross-encoder reranker can be deployed on Hugging Face Spaces for production use. Migration execution is isolated from API startup.
          </p>
        </section>
      </div>
    </DocLayout>
  );
}
