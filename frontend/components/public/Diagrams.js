function DiagramFrame({ src, alt, label }) {
  return (
    <figure className="overflow-hidden rounded-xl border border-line bg-paper">
      {label && (
        <figcaption className="border-b border-line px-5 py-3">
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-ink-faint">{label}</span>
        </figcaption>
      )}
      <div className="px-4 py-5 sm:px-6">
        <img src={src} alt={alt} className="block h-auto w-full" />
      </div>
    </figure>
  );
}

export function InfrastructureDiagram() {
  return <DiagramFrame src="/diagrams/topology.svg" alt="Multi-cloud deployment topology" label="Production Topology" />;
}

export function ArchitectureStackDiagram() {
  return <DiagramFrame src="/diagrams/architecture-stack.svg" alt="Six-layer system architecture" label="System Architecture Stack" />;
}

export function AgentWorkflowDiagram() {
  return <DiagramFrame src="/diagrams/agent-workflow.svg" alt="Agentic pipeline workflow" label="Agentic Pipeline Workflow" />;
}

export function PipelineArchitectureDiagram() {
  return <DiagramFrame src="/diagrams/pipeline-architecture.svg" alt="Eleven-stage investigation pipeline" label="Investigation Pipeline" />;
}

export function RetrievalArchitectureDiagram() {
  return <DiagramFrame src="/diagrams/retrieval-architecture.svg" alt="Five-strategy hybrid retrieval engine" label="Hybrid Retrieval Engine" />;
}

export function IngestionWorkflowDiagram() {
  return <DiagramFrame src="/diagrams/ingestion-workflow.svg" alt="Document ingestion workflow" label="Document Ingestion Workflow" />;
}

export function GovernanceWorkflowDiagram() {
  return <DiagramFrame src="/diagrams/governance-workflow.svg" alt="Governed knowledge lifecycle" label="Knowledge Lifecycle" />;
}

export function DeploymentTopologyDiagram() {
  return <DiagramFrame src="/diagrams/topology.svg" alt="Multi-cloud deployment topology" label="Deployment Topology" />;
}
