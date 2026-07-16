import Link from "next/link";
import DocLayout from "@/components/public/DocLayout";
import { InfrastructureDiagram, AgentWorkflowDiagram, IngestionWorkflowDiagram } from "@/components/public/Diagrams";

export const metadata={title:"Documentation"};
export default function Page(){
 const sections=[
  ["/documentation/architecture","System architecture","Boundaries, ownership, contracts, and service responsibilities."],
  ["/documentation/agentic","Agentic orchestration","Intent classification, retrieval planning, evidence composition, and safe outputs."],
  ["/documentation/ingestion","Ingestion and evidence","OCR, chunking, embeddings, graph extraction, and provenance."],
  ["/documentation/retrieval","Retrieval engine","Vector search, graph traversal, reranking, evidence mapping, and abstention."],
  ["/documentation/infrastructure","Infrastructure topology","Backend, agent service, pgvector, Neo4j, Redis, and object storage."],
  ["/documentation/governance","Governance","RCA, compliance, expert knowledge, review, approval, and audit."],
  ["/documentation/workflows","End-to-end workflows","Document-to-answer and draft-to-approval lifecycles."],
  ["/documentation/deployment","Deployment and operations","CI, migrations, health, secrets, rate limits, and production validation."],
 ];
 return <DocLayout eyebrow="Technical documentation" title="How Mnemos turns fragmented plant knowledge into governed operational memory." summary="This documentation is the technical centre of the product. It explains system boundaries, agent orchestration, retrieval mechanics, infrastructure, evidence provenance, security, governance, and operational workflows.">
  <div className="grid gap-7">
   <InfrastructureDiagram/>
   <AgentWorkflowDiagram/>
   <IngestionWorkflowDiagram/>
   <section className="border-y border-line py-6">
    <div className="grid gap-0 md:grid-cols-2">
     {sections.map(([href,title,body],i)=><Link key={href} href={href} className={`interactive-row p-5 ${i%2===0?"md:border-r":""} ${i<sections.length-2?"border-b":""}`}><div className="font-mono text-[10px] text-signal-blue">0{i+1}</div><div className="mt-2 text-[15px] font-semibold text-ink">{title}</div><div className="mt-2 text-[13px] leading-6 text-ink-soft">{body}</div></Link>)}
    </div>
   </section>
  </div>
 </DocLayout>
}
