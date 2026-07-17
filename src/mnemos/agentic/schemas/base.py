from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class AgentMessage(BaseModel):
    role: MessageRole
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    PROVENANCE_VALIDATED = "provenance_validated"
    HUMAN_REVIEWED = "human_reviewed"
    CONFLICTED = "conflicted"
    STALE = "stale"


class BoundingBox(BaseModel):
    page: int
    x1: float
    y1: float
    x2: float
    y2: float


class ProvenanceChain(BaseModel):
    """
    Detailed traceability from a result back to the original physical source.
    Maps: Graph Node/Edge -> Evidence Region -> Chunk -> Page -> Revision -> Original Document
    """
    node_id: str | None = None
    relationship_id: str | None = None
    evidence_region_id: str
    chunk_id: str | None = None
    document_id: str
    document_version: int
    page_number: str | None = None
    locator: str | None = None
    bounding_box: BoundingBox | None = None
    sha256: str
    source_filename: str
    storage_key: str


class EvidenceSource(BaseModel):
    text_excerpt: str
    provenance: ProvenanceChain
    relevance_score: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimSupportStatus(StrEnum):
    SUPPORTED = "supported"
    REFUTED = "refuted"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNCERTAIN = "uncertain"
    NO_EVIDENCE = "no_evidence"


class GroundedClaim(BaseModel):
    claim_id: str
    text: str
    status: ClaimSupportStatus
    sources: list[EvidenceSource] = Field(default_factory=list)
    reasoning: str | None = None


class GroundedRelationship(BaseModel):
    """
    A graph relationship that has been verified against physical evidence.
    """
    source_id: str
    target_id: str
    relationship_type: str
    evidence: EvidenceSource
    confidence: float


class RecommendedAction(BaseModel):
    action_id: str
    type: str  # TEST, INSPECTION, REPAIR, MONITOR, PROCEDURE_UPDATE, TRAINING
    description: str
    priority: str = "medium"  # low, medium, high, critical
    reasoning: str
    linked_claim_ids: list[str] = Field(default_factory=list)


class Contradiction(BaseModel):
    contradiction_id: str
    summary: str
    description: str
    involved_evidence_ids: list[str]
    severity: str = "high"


class QueryIntent(StrEnum):
    ASSET_INFO = "asset_info"
    RCA = "rca"
    COMPLIANCE = "compliance"
    LESSONS_LEARNED = "lessons_learned"
    GENERAL = "general"


class RetrievalStrategy(StrEnum):
    GRAPH_TRAVERSAL = "graph_traversal"
    VECTOR_SEARCH = "vector_search"
    METADATA_FILTER = "metadata_filter"
    SQL_QUERY = "sql_query"
    LEXICAL_SEARCH = "lexical_search"
    RERANKING = "reranking"
    MULTI_HOP = "multi_hop"
    QUERY_DECOMPOSITION = "query_decomposition"


class GraphType(StrEnum):
    """Knowledge graph types supported by GraphRAG."""
    ASSET_HIERARCHY = "asset_hierarchy"
    COMPONENT_GRAPH = "component_graph"
    INCIDENT_GRAPH = "incident_graph"
    PROCEDURE_GRAPH = "procedure_graph"
    FAILURE_GRAPH = "failure_graph"
    REQUIREMENT_GRAPH = "requirement_graph"


class ReflectionDecision(StrEnum):
    """Exit paths for the retrieval reflection agent."""
    RETRIEVE_AGAIN = "retrieve_again"
    EXPAND_GRAPH = "expand_graph"
    CHANGE_STRATEGY = "change_strategy"
    ASK_CLARIFICATION = "ask_clarification"
    ABSTAIN = "abstain"
    SUFFICIENT = "sufficient"


class RetrievalPlan(BaseModel):
    intent: QueryIntent
    strategies: list[RetrievalStrategy]
    target_entities: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    reasoning: str

    # --- Asset scope --------------------------------------------------
    asset_ids: list[str] = Field(
        default_factory=list,
        description="Resolved asset IDs to scope retrieval to.",
    )
    document_ids: list[str] = Field(
        default_factory=list,
        description="Specific document IDs to restrict search.",
    )

    # --- Sub-queries for decomposition --------------------------------
    sub_queries: list[str] = Field(
        default_factory=list,
        description="Decomposed sub-queries when multi-hop or decomposition is used.",
    )
    max_hops: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of graph hops for multi-hop retrieval.",
    )
    decomposition_enabled: bool = Field(
        default=False,
        description="Whether to decompose the query into sub-queries.",
    )

    # --- Temporal filters ---------------------------------------------
    date_from: str | None = Field(
        default=None,
        description="ISO-8601 lower bound for evidence recency (e.g. '2024-01-01').",
    )
    date_to: str | None = Field(
        default=None,
        description="ISO-8601 upper bound for evidence recency.",
    )

    # --- Revision filters ---------------------------------------------
    latest_version_only: bool = Field(
        default=True,
        description="When True only the current document revision is searched.",
    )
    document_versions: list[int] | None = Field(
        default=None,
        description="Explicit document version numbers to include (overrides latest_version_only).",
    )

    # --- Permission / tenancy filters ---------------------------------
    organisation_id: str | None = Field(default=None)
    site_id: str | None = Field(default=None)

    # --- Retrieval tuning ---------------------------------------------
    top_k_per_strategy: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum candidates each strategy should return.",
    )
    min_relevance_score: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Minimum relevance after reranking to keep evidence.",
    )
    enable_reranking: bool = Field(
        default=True,
        description="Whether to run cross-encoder reranking after fusion.",
    )

    # --- Sufficiency --------------------------------------------------
    min_evidence_count: int = Field(
        default=3,
        ge=0,
        description="Minimum number of verified evidence items required.",
    )
    min_average_confidence: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum average confidence across evidence to consider sufficient.",
    )

    # --- Budget -------------------------------------------------------
    max_total_candidates: int = Field(
        default=100,
        ge=1,
        description="Maximum total candidates across all strategies before dedup.",
    )
    budget_tokens: int | None = Field(
        default=None,
        description="Optional token budget for LLM calls during retrieval.",
    )

    # --- Graph types to query -----------------------------------------
    graph_types: list[GraphType] = Field(
        default_factory=list,
        description="Knowledge graph types to traverse (empty = default traversal).",
    )


class ResolvedEntity(BaseModel):
    original_text: str
    entity_id: str
    entity_type: str
    confidence: float
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ------------------------------------------------------------------
# Citation
# ------------------------------------------------------------------


class Citation(BaseModel):
    """A structured citation linking evidence to its source document."""
    citation_id: str
    evidence_region_id: str
    document_id: str
    document_title: str | None = None
    document_version: int = 1
    chunk_id: str | None = None
    page_number: str | None = None
    locator: str | None = None
    text_excerpt: str
    retrieval_sources: list[str] = Field(default_factory=list)
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_latest_version: bool = True


# ------------------------------------------------------------------
# Source reliability
# ------------------------------------------------------------------


class SourceReliability(BaseModel):
    """Trust score for a source type."""
    source_type: str
    reliability_score: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


# ------------------------------------------------------------------
# Missing evidence
# ------------------------------------------------------------------


class MissingEvidence(BaseModel):
    """Describes evidence that was expected but not found."""
    evidence_type: str
    description: str
    suggested_action: str = ""
    priority: str = "medium"


# ------------------------------------------------------------------
# Confidence signal
# ------------------------------------------------------------------


class ConfidenceSignal(BaseModel):
    """A single signal contributing to overall confidence."""
    signal_name: str
    signal_value: float = Field(ge=0.0, le=1.0)
    weight: float = Field(default=1.0, ge=0.0)
    reasoning: str = ""


# ------------------------------------------------------------------
# Sub-query (decomposition)
# ------------------------------------------------------------------


class SubQuery(BaseModel):
    """A decomposed sub-query from the original query."""
    original_query: str
    sub_query_text: str
    decomposition_reasoning: str = ""
    priority: int = Field(default=0, ge=0)
    depends_on: list[int] = Field(default_factory=list)


class EvidenceBundle(BaseModel):
    query_id: str
    intent: QueryIntent
    resolved_entities: list[ResolvedEntity] = Field(default_factory=list)
    verified_evidence: list[EvidenceSource] = Field(default_factory=list)
    grounded_relationships: list[GroundedRelationship] = Field(default_factory=list)
    raw_graph_data: dict[str, Any] = Field(default_factory=dict)
    raw_vector_data: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    missing_evidence: list[MissingEvidence] = Field(default_factory=list)
    confidence_signals: list[ConfidenceSignal] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)


class AgentResponse(BaseModel):
    """
    The final grounded report generated by Mnemos.
    """
    answer: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    claims: list[GroundedClaim] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    graph_paths: list[list[str]] = Field(default_factory=list, description="KG paths supporting the answer")
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------
# Reasoning output (shared by all reasoning agents)
# ------------------------------------------------------------------


class ReasoningDecision(StrEnum):
    """Exit paths for reasoning agents."""
    SUFFICIENT = "sufficient"
    REQUEST_EVIDENCE = "request_evidence"
    DELEGATE = "delegate"
    ABSTAIN = "abstain"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


class TimelineEvent(BaseModel):
    """A chronological event in an RCA timeline."""
    event_id: str
    timestamp: str
    description: str
    source_evidence_ids: list[str] = Field(default_factory=list)
    category: str = "observation"  # observation, action, symptom, condition
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Hypothesis(BaseModel):
    """A causal hypothesis for root cause analysis."""
    hypothesis_id: str
    text: str
    support_status: str = "not_evaluated"  # not_evaluated, supported, refuted, partially_supported, uncertain
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    reasoning: str = ""
    causal_chain: list[str] = Field(default_factory=list, description="Ordered chain of cause→effect links")


class EvidenceRanking(BaseModel):
    """Ranked evidence item with relevance to a specific reasoning task."""
    evidence_index: int
    relevance_score: float = Field(ge=0.0, le=1.0)
    role: str = ""  # e.g. "root_cause", "contributing_factor", "symptom", "context"
    reasoning: str = ""


class TestRecommendation(BaseModel):
    """A recommended diagnostic test to validate or refute a hypothesis."""
    test_id: str
    description: str
    target_hypothesis_ids: list[str] = Field(default_factory=list)
    priority: str = "medium"
    expected_outcome: str = ""
    reasoning: str = ""


class ComplianceCheckResult(BaseModel):
    """Result of a single deterministic compliance check."""
    check_id: str
    check_type: str  # revision, date, requirement, expiry, workflow
    requirement_id: str | None = None
    requirement_code: str | None = None
    status: str = "pass"  # pass, fail, warning, not_applicable
    details: str = ""
    evidence_source_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSubmission(BaseModel):
    """A structured knowledge card submission (never published directly)."""
    submission_id: str
    title: str
    content: str
    asset_ids: list[str] = Field(default_factory=list)
    source_evidence_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    conflicts_with: list[str] = Field(default_factory=list, description="IDs of conflicting submissions")
    status: str = "draft"  # draft, submitted_for_review, approved, rejected
    reasoning: str = ""


class HistoricalComparison(BaseModel):
    """Comparison between current situation and a historical incident."""
    comparison_id: str
    historical_case_id: str
    historical_title: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    matching_factors: list[str] = Field(default_factory=list)
    differing_factors: list[str] = Field(default_factory=list)
    applicable_actions: list[str] = Field(default_factory=list, description="Actions from history worth applying")
    reasoning: str = ""


class ProactiveRecommendation(BaseModel):
    """A forward-looking recommendation derived from historical patterns."""
    recommendation_id: str
    title: str
    description: str
    category: str  # preventive, predictive, corrective, procedural
    priority: str = "medium"
    linked_pattern_ids: list[str] = Field(default_factory=list)
    reasoning: str = ""
    evidence_source_ids: list[str] = Field(default_factory=list)


class ReasoningOutput(BaseModel):
    """Common output schema for all reasoning agents."""
    agent_name: str
    reasoning_decision: ReasoningDecision
    claims: list[GroundedClaim] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_evidence: list[MissingEvidence] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    next_actions: list[RecommendedAction] = Field(default_factory=list)
    next_recommended_agents: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# =====================================================================
# MCP Tool Layer
# =====================================================================


class MCPToolName(StrEnum):
    """Names of all MCP tools exposed to agents."""
    RESOLVE_ASSET_TAG = "resolve_asset_tag"
    GRAPH_TRAVERSAL = "graph_traversal"
    DOCUMENT_RETRIEVAL = "document_retrieval"
    TIMELINE = "timeline"
    SIMILAR_FAILURES = "similar_failures"
    REVISION_CHECK = "revision_check"
    EVIDENCE_RULES = "evidence_rules"
    APPROVAL_RECORDING = "approval_recording"
    ACTION_CREATION = "action_creation"
    REPORT_GENERATION = "report_generation"


class MCPToolResult(BaseModel):
    """Typed result wrapper for every MCP tool call."""
    tool_name: str
    success: bool
    data: Any = None
    error: str | None = None
    guardrail_passed: bool = True
    guardrail_violations: list[str] = Field(default_factory=list)
    audit_id: str | None = None
    duration_ms: float = 0.0


# =====================================================================
# Guardrails
# =====================================================================


class GuardrailCheckType(StrEnum):
    """Types of guardrail checks."""
    PERMISSION = "permission"
    HALLUCINATED_CITATION = "hallucinated_citation"
    UNAPPROVED_PROCEDURE = "unapproved_procedure"
    FAKE_SENSOR_DATA = "fake_sensor_data"
    COMPLIANCE_WITHOUT_EVIDENCE = "compliance_without_evidence"
    UNSAFE_RECOMMENDATION = "unsafe_recommendation"
    GROUNDING = "grounding"
    SOP_VERSION = "sop_version"
    PROMPT_INJECTION = "prompt_injection"


class GuardrailVerdict(BaseModel):
    """Result of a single guardrail check."""
    check_type: GuardrailCheckType
    passed: bool
    reason: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class GuardrailCheckResult(BaseModel):
    """Aggregate result of all guardrail checks for a tool call or agent action."""
    all_passed: bool
    verdicts: list[GuardrailVerdict] = Field(default_factory=list)
    blocking_violations: list[str] = Field(default_factory=list)


# =====================================================================
# Audit Logging
# =====================================================================


class AuditAction(StrEnum):
    """Actions recorded in the audit log."""
    TOOL_CALLED = "tool_called"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    AGENT_INVOKED = "agent_invoked"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    DECISION_MADE = "decision_made"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    APPROVAL_CHANGES = "approval_changes"
    GUARDRAIL_CHECK = "guardrail_check"
    GUARDRAIL_VIOLATION = "guardrail_violation"
    STATE_TRANSITION = "state_transition"
    EVIDENCE_COLLECTED = "evidence_collected"
    CLAIM_ADDED = "claim_added"
    REPORT_GENERATED = "report_generated"
    ACTION_CREATED = "action_created"
    CHECKPOINT_SAVED = "checkpoint_saved"


class AuditEntry(BaseModel):
    """Immutable audit log entry. Every significant action is recorded."""
    audit_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    investigation_id: str
    trace_id: str | None = None
    agent_name: str | None = None
    action: AuditAction
    tool_name: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    guardrail_checks: list[GuardrailCheckType] = Field(default_factory=list)
    guardrail_verdicts: list[GuardrailVerdict] = Field(default_factory=list)
    approval_gate: str | None = None
    approval_decision: str | None = None
    success: bool = True
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# =====================================================================
# Human Approval Gates
# =====================================================================


class ApprovalGateType(StrEnum):
    """Mandatory approval gate types."""
    RCA_CLOSURE = "rca_closure"
    COMPLIANCE_CLOSURE = "compliance_closure"
    KNOWLEDGE_PUBLICATION = "knowledge_publication"
    MAINTENANCE_STRATEGY = "maintenance_strategy"
    AUDIT_EXPORT = "audit_export"
    HIGH_PRIORITY_ACTION = "high_priority_action"


class ApprovalGateRequest(BaseModel):
    """Request for human approval at a mandatory gate."""
    gate_type: ApprovalGateType
    investigation_id: str
    agent_name: str
    summary: str
    findings: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    impact_level: str = "medium"  # low, medium, high, critical
    requires_signature: bool = False
    timeout_seconds: float = 600.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalGateDecision(BaseModel):
    """Human decision on an approval gate."""
    gate_type: ApprovalGateType
    investigation_id: str
    decision: str  # approve, reject, request_changes
    reviewer: str
    comments: str = ""
    conditions: list[str] = Field(default_factory=list, description="Conditions for approval")
    signature: str | None = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
