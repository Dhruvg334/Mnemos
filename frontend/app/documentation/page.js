import Link from "next/link";
import DocLayout from "@/components/public/DocLayout";
import { ArchitectureStackDiagram } from "@/components/public/Diagrams";

export const metadata = { title: "Documentation" };

const tour = [
  ["01", "Start with the ownership boundary", "The frontend presents workflows, the backend owns application truth, and the agentic layer returns structured evidence rather than writing business records.", "/documentation/architecture"],
  ["02", "Follow one document into the system", "See how a source becomes parsed content, evidence regions, chunks, embeddings, graph entities, and provenance-linked records.", "/documentation/ingestion"],
  ["03", "Follow one question through retrieval", "Understand query classification, entity resolution, retrieval planning, vector search, graph expansion, reranking, and evidence composition.", "/documentation/agentic"],
  ["04", "See how operational knowledge is governed", "RCA, compliance, and expert knowledge move through reviewable lifecycles with role checks, approvals, and audit history.", "/documentation/governance"],
  ["05", "Review the production path", "Inspect infrastructure, health checks, migrations, secrets, rate limits, deployment, and service-level failure handling.", "/documentation/infrastructure"],
];

export default function DocumentationPage() {
  return (
    <DocLayout
      eyebrow="Technical documentation"
      title="Understand Mnemos in five minutes, then inspect any layer in depth."
      summary="The documentation is structured for judges and technical evaluators: first the system model, then one end-to-end path, followed by focused engineering deep dives."
    >
      <div className="grid gap-10">
        <section className="grid gap-8 border-b border-line pb-10 lg:grid-cols-[0.75fr,1.25fr]">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.19em] text-ink">Thirty-second model</div>
            <h2 className="mt-3 text-[28px] font-semibold tracking-[-0.04em] text-ink">Mnemos connects evidence, reasoning, and governed action.</h2>
          </div>
          <div className="grid gap-4 text-[14px] leading-7 text-ink-soft">
            <p><strong className="font-semibold text-ink">Evidence:</strong> industrial documents, asset history, work orders, inspections, procedures, and expert notes are converted into provenance-linked records.</p>
            <p><strong className="font-semibold text-ink">Reasoning:</strong> a bounded agentic workflow classifies the question, selects a retrieval strategy, gathers vector and graph evidence, reranks candidates, and returns supported claims.</p>
            <p><strong className="font-semibold text-ink">Action:</strong> the backend validates results and moves them into controlled workflows for RCA, compliance, expert knowledge, and audit.</p>
          </div>
        </section>

        <ArchitectureStackDiagram />

        <section>
          <div className="text-[11px] font-semibold uppercase tracking-[0.19em] text-ink">Five-minute technical tour</div>
          <div className="mt-5 divide-y divide-line border-y border-line">
            {tour.map(([number, title, text, href]) => (
              <Link key={href} href={href} className="grid gap-3 py-5 transition hover:bg-paper-alt md:grid-cols-[44px,220px,1fr,92px] md:px-3">
                <span className="font-mono text-[10.5px] text-ink">{number}</span>
                <span className="text-[14px] font-semibold text-ink">{title}</span>
                <span className="text-[13px] leading-6 text-ink-soft">{text}</span>
                <span className="text-[12px] font-medium text-ink-faint md:text-right">Open →</span>
              </Link>
            ))}
          </div>
        </section>

        <section className="grid gap-8 border-t border-line pt-10 lg:grid-cols-[0.8fr,1.2fr]">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.19em] text-ink">What makes it technically distinctive</div>
            <h2 className="mt-3 text-[28px] font-semibold tracking-[-0.04em] text-ink">Depth is concentrated in the system, not dumped onto the operator.</h2>
          </div>
          <div className="divide-y divide-line border-y border-line">
            {[
              ["Hybrid retrieval", "Vector evidence, graph relationships, metadata constraints, and reranking are combined through a common evidence representation."],
              ["Evidence mapping", "Every claim and graph assertion can resolve back to source document, revision, chunk, page or locator, extraction version, and review state."],
              ["Controlled ownership", "The agent returns a result; the backend validates, persists, audits, and exposes it. This avoids duplicate writes and state races."],
              ["Production-oriented controls", "Authentication, tenancy, rate limits, idempotency, retries, audit logs, health checks, migrations, and cloud deployment are already part of the design."],
            ].map(([title, text]) => (
              <div key={title} className="grid gap-2 py-4 md:grid-cols-[180px,1fr]">
                <span className="text-[13px] font-semibold text-ink">{title}</span>
                <span className="text-[13px] leading-6 text-ink-soft">{text}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </DocLayout>
  );
}
