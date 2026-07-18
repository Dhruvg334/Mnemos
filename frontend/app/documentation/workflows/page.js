import DocLayout from "@/components/public/DocLayout";
import { IngestionWorkflowDiagram, GovernanceWorkflowDiagram } from "@/components/public/Diagrams";
export const metadata={title:"End-to-end workflows"};
export default function Page(){return <DocLayout eyebrow="Workflows" title="From document arrival to governed operational action." summary="Mnemos links ingestion, retrieval, investigation, review, and audit into one traceable lifecycle."><div className="grid gap-6"><IngestionWorkflowDiagram/><GovernanceWorkflowDiagram/></div></DocLayout>}
