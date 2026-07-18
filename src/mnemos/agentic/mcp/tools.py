"""Typed MCP tool definitions for all 10 Mnemos tools.

Each tool has a strict Pydantic input schema and output schema.
No agent may access databases directly -- every external action
goes through these typed MCP tools.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# =====================================================================
# Tool 1: resolve_asset_tag
# =====================================================================


class ResolveAssetTagInput(BaseModel):
    """Input for resolving an asset tag or name to a canonical entity."""

    mention: str = Field(..., description="Asset tag, name, or alias (e.g. 'P-101', 'Boiler A').")
    site_id: str | None = Field(None, description="Optional site scope filter.")
    organisation_id: str | None = Field(None, description="Optional org scope filter.")


class ResolveAssetTagOutput(BaseModel):
    """Output from asset tag resolution."""

    resolved: bool
    entities: list[dict[str, Any]] = Field(default_factory=list)
    ambiguity_reason: str | None = None


# =====================================================================
# Tool 2: graph_traversal
# =====================================================================


class GraphTraversalInput(BaseModel):
    """Input for knowledge graph traversal."""

    start_node_id: str = Field(
        ..., description="Starting node ID (asset, component, incident, etc.)."
    )
    graph_type: str = Field(
        default="asset_hierarchy",
        description="Graph type: asset_hierarchy, component_graph, incident_graph, "
        "procedure_graph, failure_graph, requirement_graph.",
    )
    depth: int = Field(default=2, ge=1, le=5, description="Traversal depth.")
    direction: str = Field(default="both", description="Traversal direction: out, in, both.")
    relationship_types: list[str] = Field(
        default_factory=list, description="Filter by relationship types."
    )
    limit: int = Field(default=50, ge=1, le=200, description="Maximum nodes to return.")


class GraphTraversalOutput(BaseModel):
    """Output from graph traversal."""

    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    paths: list[list[str]] = Field(default_factory=list)
    total_nodes: int = 0
    truncated: bool = False


# =====================================================================
# Tool 3: document_retrieval
# =====================================================================


class DocumentRetrievalInput(BaseModel):
    """Input for document retrieval with provenance."""

    document_id: str = Field(..., description="Document identifier.")
    version: int | None = Field(None, description="Specific version (None = latest).")
    page_range: tuple[int, int] | None = Field(
        None, description="Optional page range (start, end)."
    )
    include_provenance: bool = Field(default=True, description="Include full provenance chain.")


class DocumentRetrievalOutput(BaseModel):
    """Output from document retrieval."""

    document_id: str
    version: int
    title: str | None = None
    status: str = "unknown"
    content: str = ""
    provenance: dict[str, Any] | None = None
    sha256: str | None = None
    is_latest: bool = True


# =====================================================================
# Tool 4: timeline
# =====================================================================


class TimelineInput(BaseModel):
    """Input for chronological event history."""

    asset_id: str = Field(..., description="Asset to retrieve timeline for.")
    date_from: str | None = Field(None, description="ISO-8601 start date filter.")
    date_to: str | None = Field(None, description="ISO-8601 end date filter.")
    event_types: list[str] = Field(
        default_factory=list,
        description="Filter by event types: failure, maintenance, inspection, modification.",
    )
    limit: int = Field(default=100, ge=1, le=500, description="Maximum events to return.")


class TimelineOutput(BaseModel):
    """Output from timeline retrieval."""

    asset_id: str
    events: list[dict[str, Any]] = Field(default_factory=list)
    total_events: int = 0
    date_range: dict[str, str | None] = Field(default_factory=dict)


# =====================================================================
# Tool 5: similar_failures
# =====================================================================


class SimilarFailuresInput(BaseModel):
    """Input for finding similar failure patterns."""

    asset_id: str = Field(..., description="Asset to find similar failures for.")
    failure_description: str = Field(default="", description="Text description of the failure.")
    similarity_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum similarity score."
    )
    max_results: int = Field(
        default=10, ge=1, le=50, description="Maximum similar failures to return."
    )


class SimilarFailuresOutput(BaseModel):
    """Output from similar failure search."""

    asset_id: str
    similar_failures: list[dict[str, Any]] = Field(default_factory=list)
    total_found: int = 0
    pattern_summary: str | None = None


# =====================================================================
# Tool 6: revision_check
# =====================================================================


class RevisionCheckInput(BaseModel):
    """Input for document revision currency check."""

    document_id: str = Field(..., description="Document to check revision for.")
    expected_version: int | None = Field(
        None, description="Expected version (None = check latest)."
    )
    asset_id: str | None = Field(None, description="Associated asset for context.")


class RevisionCheckOutput(BaseModel):
    """Output from revision check."""

    document_id: str
    current_version: int
    is_current: bool
    status: str  # current, outdated, not_found
    details: str = ""


# =====================================================================
# Tool 7: evidence_rules
# =====================================================================


class EvidenceRulesInput(BaseModel):
    """Input for compliance/requirement rules lookup."""

    query: str = Field(..., description="Requirement or regulation to look up.")
    asset_id: str | None = Field(None, description="Asset scope.")
    site_id: str | None = Field(None, description="Site scope.")
    rule_type: str = Field(
        default="all",
        description="Rule type filter: iso, regulation, standard, sop, all.",
    )


class EvidenceRulesOutput(BaseModel):
    """Output from evidence rules lookup."""

    rules: list[dict[str, Any]] = Field(default_factory=list)
    total_found: int = 0
    coverage_gaps: list[str] = Field(default_factory=list)


# =====================================================================
# Tool 8: approval_recording
# =====================================================================


class ApprovalRecordingInput(BaseModel):
    """Input for recording a human approval decision."""

    gate_type: str = Field(..., description="Approval gate type.")
    investigation_id: str = Field(..., description="Investigation being approved.")
    decision: str = Field(..., description="Decision: approve, reject, request_changes.")
    reviewer: str = Field(..., description="Reviewer identifier.")
    comments: str = Field(default="", description="Reviewer comments.")
    conditions: list[str] = Field(default_factory=list, description="Approval conditions.")
    signature: str | None = Field(None, description="Digital signature if required.")


class ApprovalRecordingOutput(BaseModel):
    """Output from approval recording."""

    recorded: bool
    gate_type: str
    decision: str
    reviewer: str
    audit_id: str | None = None


# =====================================================================
# Tool 9: action_creation
# =====================================================================


class ActionCreationInput(BaseModel):
    """Input for creating a maintenance/inspection action."""

    action_type: str = Field(
        ...,
        description="Action type: TEST, INSPECTION, REPAIR, MONITOR, PROCEDURE_UPDATE, TRAINING.",
    )
    description: str = Field(..., description="Action description.")
    asset_id: str | None = Field(None, description="Target asset.")
    priority: str = Field(default="medium", description="Priority: low, medium, high, critical.")
    reasoning: str = Field(default="", description="Why this action is recommended.")
    evidence_ids: list[str] = Field(default_factory=list, description="Supporting evidence IDs.")
    linked_claim_ids: list[str] = Field(default_factory=list, description="Linked claim IDs.")


class ActionCreationOutput(BaseModel):
    """Output from action creation."""

    created: bool
    action_id: str | None = None
    action_type: str
    priority: str
    requires_approval: bool = False
    approval_gate_type: str | None = None


# =====================================================================
# Tool 10: report_generation
# =====================================================================


class ReportGenerationInput(BaseModel):
    """Input for generating a structured report."""

    report_type: str = Field(
        ...,
        description="Report type: rca_report, compliance_report, audit_export, "
        "maintenance_strategy, knowledge_card, investigation_summary.",
    )
    investigation_id: str = Field(..., description="Investigation to report on.")
    sections: list[str] = Field(
        default_factory=list,
        description="Specific sections to include (empty = all).",
    )
    format: str = Field(default="json", description="Output format: json, markdown, pdf_ref.")
    include_evidence: bool = Field(default=True, description="Include evidence citations.")
    include_recommendations: bool = Field(default=True, description="Include recommended actions.")


class ReportGenerationOutput(BaseModel):
    """Output from report generation."""

    generated: bool
    report_type: str
    report_data: dict[str, Any] = Field(default_factory=dict)
    section_count: int = 0
    requires_approval: bool = False
    approval_gate_type: str | None = None


# =====================================================================
# Tool 11: get_current_procedure
# =====================================================================


class GetCurrentProcedureInput(BaseModel):
    """Input for retrieving the current approved procedure for an asset."""

    asset_id: str = Field(..., description="Asset to get procedure for.")
    procedure_type: str = Field(
        default="all",
        description="Procedure type filter: maintenance, safety, operations, all.",
    )
    site_id: str | None = Field(None, description="Optional site scope filter.")


class GetCurrentProcedureOutput(BaseModel):
    """Output from current procedure lookup."""

    asset_id: str
    procedures: list[dict[str, Any]] = Field(default_factory=list)
    total_found: int = 0
    all_approved: bool = True
    outdated_procedures: list[dict[str, Any]] = Field(default_factory=list)


# =====================================================================
# Tool 12: generate_source_preview
# =====================================================================


class GenerateSourcePreviewInput(BaseModel):
    """Input for generating a preview link for an evidence source."""

    source_type: str = Field(
        ...,
        description="Source type: document, evidence_region, graph_node, knowledge_card.",
    )
    source_id: str = Field(..., description="Identifier of the source to preview.")
    document_id: str | None = Field(None, description="Document ID if applicable.")
    page_number: int | None = Field(None, description="Page number if applicable.")
    highlight_text: str | None = Field(None, description="Text to highlight in preview.")


class GenerateSourcePreviewOutput(BaseModel):
    """Output from source preview generation."""

    preview_url: str
    source_type: str
    source_id: str
    expires_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
