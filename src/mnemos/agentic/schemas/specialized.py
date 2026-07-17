from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from mnemos.agentic.schemas.base import (
    Contradiction,
    EvidenceSource,
    GroundedClaim,
    RecommendedAction,
)


class AssetTimelineEvent(BaseModel):
    timestamp: datetime
    event_type: str
    description: str
    source_id: str | None = None
    severity: str | None = None
    provenance: EvidenceSource | None = None

class AssetPassport(BaseModel):
    asset_id: str
    tag: str
    name: str
    type: str
    status: str
    site_context: dict[str, Any]
    specifications: dict[str, Any]
    timeline: list[AssetTimelineEvent] = Field(default_factory=list)
    failure_history: list[dict[str, Any]] = Field(default_factory=list)
    maintenance_summary: dict[str, Any] = Field(default_factory=dict)
    evidence_health_score: float = Field(ge=0.0, le=1.0)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)

class RCACaseReport(BaseModel):
    problem_statement: str
    chronology: list[dict[str, Any]]
    hypotheses: list[GroundedClaim]
    supporting_evidence: list[EvidenceSource]
    opposing_evidence: list[EvidenceSource]
    missing_diagnostics: list[str]
    suggested_tests: list[str]
    root_cause_candidates: list[str]
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)

class ComplianceAuditPackage(BaseModel):
    requirement_mappings: list[dict[str, Any]]
    verified_evidence: list[EvidenceSource]
    expiry_alerts: list[dict[str, Any]]
    contradictions: list[Contradiction] = Field(default_factory=list)
    gap_analysis: list[str]
    overall_compliance_status: str
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)

class LessonsLearnedSummary(BaseModel):
    recurring_failure_modes: list[str]
    similar_incident_ids: list[str]
    preventive_recommendations: list[GroundedClaim]
    effectiveness_score: float | None
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)

class FinalReport(BaseModel):
    title: str
    summary: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sections: dict[str, Any] # Contains AssetPassport, RCACaseReport, etc.
    grounded_claims: list[GroundedClaim] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    graph_paths: list[list[str]] = Field(default_factory=list)
    confidence_statement: str
    disclaimer: str = "This report is generated based on available evidence and requires human validation."
    approval_decisions: list[dict[str, Any]] = Field(default_factory=list, description="Human approval decisions recorded during investigation")
    document_versions: list[dict[str, Any]] = Field(default_factory=list, description="Document versions referenced in evidence with currency status")
