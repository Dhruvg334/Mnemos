from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from mnemos.agentic.schemas.base import GroundedClaim, EvidenceSource, RecommendedAction, Contradiction

class AssetTimelineEvent(BaseModel):
    timestamp: datetime
    event_type: str
    description: str
    source_id: Optional[str] = None
    severity: Optional[str] = None
    provenance: Optional[EvidenceSource] = None

class AssetPassport(BaseModel):
    asset_id: str
    tag: str
    name: str
    type: str
    status: str
    site_context: Dict[str, Any]
    specifications: Dict[str, Any]
    timeline: List[AssetTimelineEvent] = Field(default_factory=list)
    failure_history: List[Dict[str, Any]] = Field(default_factory=list)
    maintenance_summary: Dict[str, Any] = Field(default_factory=dict)
    evidence_health_score: float = Field(ge=0.0, le=1.0)
    recommended_actions: List[RecommendedAction] = Field(default_factory=list)
    contradictions: List[Contradiction] = Field(default_factory=list)

class RCACaseReport(BaseModel):
    problem_statement: str
    chronology: List[Dict[str, Any]]
    hypotheses: List[GroundedClaim]
    supporting_evidence: List[EvidenceSource]
    opposing_evidence: List[EvidenceSource]
    missing_diagnostics: List[str]
    suggested_tests: List[str]
    root_cause_candidates: List[str]
    recommended_actions: List[RecommendedAction] = Field(default_factory=list)
    contradictions: List[Contradiction] = Field(default_factory=list)

class ComplianceAuditPackage(BaseModel):
    requirement_mappings: List[Dict[str, Any]]
    verified_evidence: List[EvidenceSource]
    expiry_alerts: List[Dict[str, Any]]
    contradictions: List[Contradiction] = Field(default_factory=list)
    gap_analysis: List[str]
    overall_compliance_status: str
    recommended_actions: List[RecommendedAction] = Field(default_factory=list)

class LessonsLearnedSummary(BaseModel):
    recurring_failure_modes: List[str]
    similar_incident_ids: List[str]
    preventive_recommendations: List[GroundedClaim]
    effectiveness_score: Optional[float]
    recommended_actions: List[RecommendedAction] = Field(default_factory=list)

class FinalReport(BaseModel):
    title: str
    summary: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sections: Dict[str, Any] # Contains AssetPassport, RCACaseReport, etc.
    grounded_claims: List[GroundedClaim] = Field(default_factory=list)
    recommended_actions: List[RecommendedAction] = Field(default_factory=list)
    contradictions: List[Contradiction] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    graph_paths: List[List[str]] = Field(default_factory=list)
    confidence_statement: str
    disclaimer: str = "This report is generated based on available evidence and requires human validation."
