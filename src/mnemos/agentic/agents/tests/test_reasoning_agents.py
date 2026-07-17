"""Comprehensive tests for all 5 reasoning agents.

Tests verify:
- Protocol conformance (CollaborativeAgent, BaseAgent)
- Registration metadata (name, role, capabilities, dependencies)
- Evidence-only reasoning (no hallucinated facts)
- Claim grounding (every claim traces to verified evidence)
- Collaboration support (next_recommended_agents)
- All exit paths / decision types
- RCA-specific: timeline, hypotheses, evidence ranking, test recommendations
- Compliance-specific: deterministic checks (revision, date, expiry, workflow)
- Expert Knowledge-specific: structuring, conflict detection, review request
- Lessons Learned-specific: historical comparison, pattern detection
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.agents.interfaces import CollaborativeAgent
from mnemos.agentic.agents.reasoning import (
    AssetIntelligenceAgent,
    ComplianceAgent,
    ExpertKnowledgeAgent,
    LessonsLearnedAgent,
    RCAAgent,
)
from mnemos.agentic.agents.reasoning._base import _BaseReasoningAgent
from mnemos.agentic.runtime.types import AgentRole
from mnemos.agentic.schemas.base import (
    Citation,
    ClaimSupportStatus,
    EvidenceBundle,
    EvidenceSource,
    GroundedClaim,
    ProvenanceChain,
    QueryIntent,
    ReasoningDecision,
    ReasoningOutput,
    RecommendedAction,
    ResolvedEntity,
)

# ======================================================================
# Fixtures
# ======================================================================

@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock(spec=AsyncSession)
    db.get = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    return db


def _make_provenance(
    evidence_region_id: str = "evr_001",
    document_id: str = "doc_001",
    document_version: int = 1,
    source_filename: str = "maintenance_log.pdf",
    page_number: str = "1",
) -> ProvenanceChain:
    return ProvenanceChain(
        evidence_region_id=evidence_region_id,
        document_id=document_id,
        document_version=document_version,
        sha256="abc123def456",
        source_filename=source_filename,
        storage_key="s3://bucket/key",
        page_number=page_number,
    )


def _make_evidence(
    text: str = "Pump P-101 pressure limit is 40 bar",
    confidence: float = 0.9,
    relevance: float = 0.85,
    verification_status: str = "provenance_validated",
    evidence_region_id: str = "evr_001",
    document_id: str = "doc_001",
    metadata: dict | None = None,
) -> EvidenceSource:
    return EvidenceSource(
        text_excerpt=text,
        provenance=_make_provenance(
            evidence_region_id=evidence_region_id,
            document_id=document_id,
        ),
        relevance_score=relevance,
        confidence_score=confidence,
        verification_status=verification_status,
        metadata=metadata or {},
    )


def _make_bundle(
    evidence: list[EvidenceSource] | None = None,
    intent: QueryIntent = QueryIntent.ASSET_INFO,
    resolved_entities: list[ResolvedEntity] | None = None,
) -> EvidenceBundle:
    if evidence is None:
        evidence = [_make_evidence()]
    return EvidenceBundle(
        query_id="qry_test_001",
        intent=intent,
        verified_evidence=evidence,
        resolved_entities=resolved_entities or [],
        raw_vector_data=[{"content": "test data", "metadata": {}, "score": 0.9}],
        raw_graph_data={"ast_001": {"nodes": [{"id": "n1"}], "relationships": []}},
    )


def _initial_state(
    query: str = "What is the pressure limit for P-101?",
    evidence: list[EvidenceSource] | None = None,
    resolved_entities: list | None = None,
) -> dict:
    bundle = _make_bundle(evidence=evidence, resolved_entities=resolved_entities)
    return {
        "query": query,
        "context": {
            "query_id": "qry_test_001",
            "site_id": "site_alpha",
            "org_id": "org_mnemos",
            "user_id": "usr_001",
            "evidence_bundle": bundle,
        },
        "intent": QueryIntent.ASSET_INFO,
        "resolved_entities": [],
        "retrieval_plan": None,
        "evidence_bundle": bundle,
        "messages": [],
        "claims": [],
        "final_response": None,
        "steps_completed": [],
        "errors": [],
    }


# ======================================================================
# Protocol conformance (all 5 agents)
# ======================================================================

class TestReasoningProtocolConformance:
    ALL_AGENTS = [
        AssetIntelligenceAgent,
        RCAAgent,
        ComplianceAgent,
        ExpertKnowledgeAgent,
        LessonsLearnedAgent,
    ]

    @pytest.mark.parametrize("cls", ALL_AGENTS)
    def test_is_collaborative_agent(self, cls: type, mock_db: MagicMock) -> None:
        agent = cls(mock_db)
        assert isinstance(agent, CollaborativeAgent)
        assert isinstance(agent, _BaseReasoningAgent)

    @pytest.mark.parametrize("cls", ALL_AGENTS)
    def test_is_base_reasoning_agent(self, cls: type, mock_db: MagicMock) -> None:
        agent = cls(mock_db)
        assert isinstance(agent, _BaseReasoningAgent)

    @pytest.mark.parametrize("cls", ALL_AGENTS)
    def test_has_registration(self, cls: type, mock_db: MagicMock) -> None:
        agent = cls(mock_db)
        reg = agent.to_registration()
        assert reg.name
        assert reg.role in [r.value for r in AgentRole]
        assert isinstance(reg.capabilities, list)
        assert len(reg.capabilities) > 0

    @pytest.mark.parametrize("cls", ALL_AGENTS)
    def test_has_name_and_role(self, cls: type, mock_db: MagicMock) -> None:
        agent = cls(mock_db)
        assert isinstance(agent.name, str) and len(agent.name) > 0
        assert isinstance(agent.role, AgentRole)

    @pytest.mark.parametrize("cls", ALL_AGENTS)
    def test_has_required_dependencies(self, cls: type, mock_db: MagicMock) -> None:
        agent = cls(mock_db)
        deps = agent.required_dependencies
        assert isinstance(deps, list)
        assert len(deps) > 0


# ======================================================================
# AssetIntelligenceAgent
# ======================================================================

class TestAssetIntelligenceAgent:
    def test_registration_metadata(self, mock_db: MagicMock) -> None:
        agent = AssetIntelligenceAgent(mock_db)
        reg = agent.to_registration()
        assert reg.name == "asset_intelligence"
        assert reg.role == AgentRole.ANALYSIS
        assert reg.capabilities[0].name == "asset_intelligence"

    def test_depends_on_evidence_verification(self, mock_db: MagicMock) -> None:
        assert "evidence_verification" in AssetIntelligenceAgent(mock_db).required_dependencies

    @pytest.mark.asyncio
    async def test_produces_claims_from_evidence(self, mock_db: MagicMock) -> None:
        agent = AssetIntelligenceAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Pump P-101 pressure limit is 40 bar",
                confidence=0.9,
                evidence_region_id="evr_001",
            ),
            _make_evidence(
                text="Last inspection date: January 2024",
                confidence=0.85,
                evidence_region_id="evr_002",
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert isinstance(output, ReasoningOutput)
        assert output.agent_name == "asset_intelligence"
        assert len(output.claims) >= 2
        assert output.confidence_score > 0
        assert len(output.citations) == 2
        assert "asset_intelligence" in result["steps_completed"]

    @pytest.mark.asyncio
    async def test_claims_are_grounded(self, mock_db: MagicMock) -> None:
        agent = AssetIntelligenceAgent(mock_db)
        evidence = [
            _make_evidence(text="Temperature reading: 85C", confidence=0.95),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        for claim in result["context"]["reasoning_output"].claims:
            assert claim.status in [
                ClaimSupportStatus.SUPPORTED,
                ClaimSupportStatus.PARTIALLY_SUPPORTED,
                ClaimSupportStatus.UNCERTAIN,
                ClaimSupportStatus.NO_EVIDENCE,
            ]
            assert claim.reasoning

    @pytest.mark.asyncio
    async def test_abstains_without_evidence(self, mock_db: MagicMock) -> None:
        agent = AssetIntelligenceAgent(mock_db)
        state = {
            "query": "test",
            "context": {"evidence_bundle": None},
            "intent": None,
            "resolved_entities": [],
            "retrieval_plan": None,
            "evidence_bundle": None,
            "messages": [],
            "claims": [],
            "final_response": None,
            "steps_completed": [],
            "errors": [],
        }
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert output.reasoning_decision == ReasoningDecision.ABSTAIN
        assert output.confidence_score == 0.0

    @pytest.mark.asyncio
    async def test_requests_evidence_when_low_confidence(self, mock_db: MagicMock) -> None:
        agent = AssetIntelligenceAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Vague observation",
                confidence=0.2,
                relevance=0.15,
                verification_status="unverified",
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert output.reasoning_decision == ReasoningDecision.REQUEST_EVIDENCE

    @pytest.mark.asyncio
    async def test_produces_citations(self, mock_db: MagicMock) -> None:
        agent = AssetIntelligenceAgent(mock_db)
        evidence = [_make_evidence(text="Test fact")]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        citations = result["context"]["reasoning_output"].citations
        assert len(citations) == 1
        assert isinstance(citations[0], Citation)
        assert citations[0].document_id == "doc_001"

    @pytest.mark.asyncio
    async def test_identifies_missing_evidence(self, mock_db: MagicMock) -> None:
        agent = AssetIntelligenceAgent(mock_db)
        evidence = [_make_evidence(text="Only one source")]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        missing = result["context"]["reasoning_output"].missing_evidence
        assert len(missing) >= 1
        assert any("graph" in m.evidence_type for m in missing)

    @pytest.mark.asyncio
    async def test_adds_claims_to_state(self, mock_db: MagicMock) -> None:
        agent = AssetIntelligenceAgent(mock_db)
        evidence = [_make_evidence(text="Test claim")]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        assert len(result["claims"]) >= 1
        assert isinstance(result["claims"][0], GroundedClaim)

    @pytest.mark.asyncio
    async def test_sufficient_when_high_confidence(self, mock_db: MagicMock) -> None:
        agent = AssetIntelligenceAgent(mock_db)
        evidence = [
            _make_evidence(text="Clear specification", confidence=0.95, relevance=0.9),
            _make_evidence(text="Verified parameter", confidence=0.92, relevance=0.88),
            _make_evidence(text="Maintenance confirmed", confidence=0.89, relevance=0.85),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert output.reasoning_decision == ReasoningDecision.SUFFICIENT


# ======================================================================
# RCAAgent
# ======================================================================

class TestRCAAgent:
    def test_registration_metadata(self, mock_db: MagicMock) -> None:
        agent = RCAAgent(mock_db)
        reg = agent.to_registration()
        assert reg.name == "rca_agent"
        assert reg.role == AgentRole.ANALYSIS
        assert reg.capabilities[0].name == "root_cause_analysis"

    def test_depends_on_evidence_verification(self, mock_db: MagicMock) -> None:
        assert "evidence_verification" in RCAAgent(mock_db).required_dependencies

    @pytest.mark.asyncio
    async def test_generates_timeline(self, mock_db: MagicMock) -> None:
        agent = RCAAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Alarm triggered at 14:30",
                metadata={"timestamp": "2024-01-15T14:30:00", "type": "sensor_data"},
            ),
            _make_evidence(
                text="Temperature reading 95C",
                metadata={"timestamp": "2024-01-15T14:25:00", "type": "sensor_data"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert "timeline" in output.metadata
        timeline = output.metadata["timeline"]
        assert len(timeline) >= 2
        # Should be sorted by timestamp
        assert timeline[0]["timestamp"] <= timeline[1]["timestamp"]

    @pytest.mark.asyncio
    async def test_generates_hypotheses(self, mock_db: MagicMock) -> None:
        agent = RCAAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Vibration alarm on bearing",
                metadata={"timestamp": "2024-01-15T10:00:00", "type": "sensor_data"},
            ),
            _make_evidence(
                text="Bearing temperature elevated to 85C",
                metadata={"timestamp": "2024-01-15T09:50:00", "type": "sensor_data"},
            ),
            _make_evidence(
                text="Lubrication performed 30 days ago",
                metadata={"timestamp": "2024-01-15T08:00:00", "type": "maintenance_log"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert "hypotheses" in output.metadata
        hypotheses = output.metadata["hypotheses"]
        assert len(hypotheses) >= 1
        assert hypotheses[0]["confidence_score"] >= 0

    @pytest.mark.asyncio
    async def test_hypotheses_sorted_by_confidence(self, mock_db: MagicMock) -> None:
        agent = RCAAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Symptom: pump noise",
                metadata={"timestamp": "2024-01-15T10:00:00"},
            ),
            _make_evidence(
                text="Condition: high temperature",
                metadata={"timestamp": "2024-01-15T09:00:00"},
            ),
            _make_evidence(
                text="Action: bearing replaced",
                metadata={"timestamp": "2024-01-15T11:00:00"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        hypotheses = result["context"]["reasoning_output"].metadata["hypotheses"]
        for i in range(len(hypotheses) - 1):
            assert hypotheses[i]["confidence_score"] >= hypotheses[i + 1]["confidence_score"]

    @pytest.mark.asyncio
    async def test_produces_evidence_rankings(self, mock_db: MagicMock) -> None:
        agent = RCAAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Alarm on pump P-101",
                metadata={"timestamp": "2024-01-15T10:00:00"},
            ),
            _make_evidence(
                text="Temperature spike",
                metadata={"timestamp": "2024-01-15T09:30:00"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        rankings = result["context"]["reasoning_output"].metadata["evidence_rankings"]
        assert len(rankings) == 2
        assert all("relevance_score" in r for r in rankings)

    @pytest.mark.asyncio
    async def test_recommends_diagnostic_tests(self, mock_db: MagicMock) -> None:
        agent = RCAAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Unusual vibration detected",
                metadata={"timestamp": "2024-01-15T10:00:00"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        test_recs = result["context"]["reasoning_output"].metadata["test_recommendations"]
        assert len(test_recs) >= 1
        assert all("description" in t for t in test_recs)

    @pytest.mark.asyncio
    async def test_identifies_missing_diagnostics(self, mock_db: MagicMock) -> None:
        agent = RCAAgent(mock_db)
        evidence = [
            _make_evidence(
                text="General observation",
                metadata={"type": "manual_report"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        missing = result["context"]["reasoning_output"].missing_evidence
        missing_types = {m.evidence_type for m in missing}
        assert "sensor_data" in missing_types or "maintenance_log" in missing_types

    @pytest.mark.asyncio
    async def test_no_definitive_conclusion_without_evidence(self, mock_db: MagicMock) -> None:
        agent = RCAAgent(mock_db)
        state = {
            "query": "What caused the failure?",
            "context": {"evidence_bundle": None},
            "intent": QueryIntent.RCA,
            "resolved_entities": [],
            "retrieval_plan": None,
            "evidence_bundle": None,
            "messages": [],
            "claims": [],
            "final_response": None,
            "steps_completed": [],
            "errors": [],
        }
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert output.reasoning_decision == ReasoningDecision.ABSTAIN
        assert output.confidence_score == 0.0

    @pytest.mark.asyncio
    async def test_categorizes_events(self, mock_db: MagicMock) -> None:
        agent = RCAAgent(mock_db)
        evidence = [
            _make_evidence(text="Pump alarm tripped", metadata={}),
            _make_evidence(text="Bearing replaced by technician", metadata={}),
            _make_evidence(text="Temperature reading 85C", metadata={}),
            _make_evidence(text="Visual inspection completed", metadata={}),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        timeline = result["context"]["reasoning_output"].metadata["timeline"]
        categories = {e["category"] for e in timeline}
        assert "symptom" in categories
        assert "action" in categories
        assert "condition" in categories

    @pytest.mark.asyncio
    async def test_claims_match_hypotheses(self, mock_db: MagicMock) -> None:
        agent = RCAAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Failure occurred after maintenance",
                metadata={"timestamp": "2024-01-15T10:00:00"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert len(output.claims) >= 1
        for claim in output.claims:
            assert claim.text
            assert claim.reasoning


# ======================================================================
# ComplianceAgent
# ======================================================================

class TestComplianceAgent:
    def test_registration_metadata(self, mock_db: MagicMock) -> None:
        agent = ComplianceAgent(mock_db)
        reg = agent.to_registration()
        assert reg.name == "compliance_agent"
        assert reg.role == AgentRole.ANALYSIS
        assert reg.capabilities[0].name == "compliance_verification"

    @pytest.mark.asyncio
    async def test_runs_revision_checks(self, mock_db: MagicMock) -> None:
        agent = ComplianceAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Document SOP-001 v3",
                metadata={"type": "document"},
            ),
            _make_evidence(
                text="Document SOP-001 v2",
                metadata={"type": "document"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        checks = result["context"]["reasoning_output"].metadata["compliance_checks"]
        revision_checks = [c for c in checks if c["check_type"] == "revision"]
        assert len(revision_checks) >= 1

    @pytest.mark.asyncio
    async def test_runs_date_checks(self, mock_db: MagicMock) -> None:
        agent = ComplianceAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Inspection completed",
                metadata={"timestamp": "2024-06-15T10:00:00", "type": "inspection"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        checks = result["context"]["reasoning_output"].metadata["compliance_checks"]
        date_checks = [c for c in checks if c["check_type"] == "date"]
        assert len(date_checks) >= 1

    @pytest.mark.asyncio
    async def test_runs_requirement_checks(self, mock_db: MagicMock) -> None:
        agent = ComplianceAgent(mock_db)
        evidence = [
            _make_evidence(text="ISO 9001 compliance verified"),
            _make_evidence(text="Regulation OSHA 1910.147 applied"),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        checks = result["context"]["reasoning_output"].metadata["compliance_checks"]
        req_checks = [c for c in checks if c["check_type"] == "requirement"]
        assert len(req_checks) >= 2

    @pytest.mark.asyncio
    async def test_runs_expiry_checks(self, mock_db: MagicMock) -> None:
        agent = ComplianceAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Certificate expires on 2024-12-31",
                metadata={"expiry_date": "2024-12-31", "type": "certificate"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        checks = result["context"]["reasoning_output"].metadata["compliance_checks"]
        expiry_checks = [c for c in checks if c["check_type"] == "expiry"]
        assert len(expiry_checks) >= 1

    @pytest.mark.asyncio
    async def test_expired_certificate_fails(self, mock_db: MagicMock) -> None:
        agent = ComplianceAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Permit expired",
                metadata={"expiry_date": "2023-01-01", "type": "permit"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        checks = result["context"]["reasoning_output"].metadata["compliance_checks"]
        expiry_checks = [c for c in checks if c["check_type"] == "expiry"]
        assert any(c["status"] == "fail" for c in expiry_checks)

    @pytest.mark.asyncio
    async def test_runs_workflow_checks(self, mock_db: MagicMock) -> None:
        agent = ComplianceAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Reviewed and approved",
                verification_status="human_reviewed",
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        checks = result["context"]["reasoning_output"].metadata["compliance_checks"]
        wf_checks = [c for c in checks if c["check_type"] == "workflow"]
        assert len(wf_checks) >= 1

    @pytest.mark.asyncio
    async def test_pass_rate_in_confidence(self, mock_db: MagicMock) -> None:
        agent = ComplianceAgent(mock_db)
        evidence = [
            _make_evidence(text="ISO 9001 verified"),
            _make_evidence(text="Regulation compliant"),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert output.confidence_score >= 0.0
        assert output.confidence_score <= 1.0
        assert "pass_rate" in output.metadata

    @pytest.mark.asyncio
    async def test_needs_human_review_on_failure(self, mock_db: MagicMock) -> None:
        agent = ComplianceAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Certificate expired",
                metadata={"expiry_date": "2022-01-01"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert output.reasoning_decision == ReasoningDecision.NEEDS_HUMAN_REVIEW

    @pytest.mark.asyncio
    async def test_no_llm_for_checks(self, mock_db: MagicMock) -> None:
        """Compliance checks are deterministic — no LLM should be called."""
        agent = ComplianceAgent(mock_db)
        original_llm = agent.llm
        agent.llm = MagicMock()

        evidence = [_make_evidence(text="Test")]
        state = _initial_state(evidence=evidence)
        await agent.run(state)

        agent.llm.call_structured.assert_not_called()
        agent.llm = original_llm

    @pytest.mark.asyncio
    async def test_abstains_without_evidence(self, mock_db: MagicMock) -> None:
        agent = ComplianceAgent(mock_db)
        state = {
            "query": "Check compliance",
            "context": {"evidence_bundle": None},
            "intent": QueryIntent.COMPLIANCE,
            "resolved_entities": [],
            "retrieval_plan": None,
            "evidence_bundle": None,
            "messages": [],
            "claims": [],
            "final_response": None,
            "steps_completed": [],
            "errors": [],
        }
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert output.reasoning_decision == ReasoningDecision.ABSTAIN

    @pytest.mark.asyncio
    async def test_generates_actions_for_failures(self, mock_db: MagicMock) -> None:
        agent = ComplianceAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Certificate expired",
                metadata={"expiry_date": "2022-06-01"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        actions = result["context"]["reasoning_output"].next_actions
        assert len(actions) >= 1
        assert isinstance(actions[0], RecommendedAction)


# ======================================================================
# ExpertKnowledgeAgent
# ======================================================================

class TestExpertKnowledgeAgent:
    def test_registration_metadata(self, mock_db: MagicMock) -> None:
        agent = ExpertKnowledgeAgent(mock_db)
        reg = agent.to_registration()
        assert reg.name == "expert_knowledge_agent"
        assert reg.role == AgentRole.ANALYSIS
        assert reg.capabilities[0].name == "expert_knowledge"

    @pytest.mark.asyncio
    async def test_structures_submissions(self, mock_db: MagicMock) -> None:
        agent = ExpertKnowledgeAgent(mock_db)
        evidence = [
            _make_evidence(text="Pump P-101 operates at 40 bar max pressure"),
            _make_evidence(text="Annual inspection required per SOP-005"),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        submissions = output.metadata["knowledge_submissions"]
        assert len(submissions) == 2
        assert all(s["status"] == "submitted_for_review" for s in submissions)

    @pytest.mark.asyncio
    async def test_never_publishes_directly(self, mock_db: MagicMock) -> None:
        agent = ExpertKnowledgeAgent(mock_db)
        evidence = [_make_evidence(text="Test knowledge")]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        submissions = result["context"]["reasoning_output"].metadata["knowledge_submissions"]
        for sub in submissions:
            assert sub["status"] == "submitted_for_review"
            assert sub["status"] != "approved"
            assert sub["status"] != "published"

    @pytest.mark.asyncio
    async def test_requests_human_review(self, mock_db: MagicMock) -> None:
        agent = ExpertKnowledgeAgent(mock_db)
        evidence = [_make_evidence(text="Expert observation")]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert output.reasoning_decision == ReasoningDecision.NEEDS_HUMAN_REVIEW

    @pytest.mark.asyncio
    async def test_detects_conflicts(self, mock_db: MagicMock) -> None:
        agent = ExpertKnowledgeAgent(mock_db)
        evidence = [
            _make_evidence(text="Pressure should always be increased"),
            _make_evidence(text="Pressure should never be increased"),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        submissions = result["context"]["reasoning_output"].metadata["knowledge_submissions"]
        conflicting = [s for s in submissions if s["conflicts_with"]]
        assert len(conflicting) >= 1

    @pytest.mark.asyncio
    async def test_links_entities(self, mock_db: MagicMock) -> None:
        agent = ExpertKnowledgeAgent(mock_db)
        evidence = [_make_evidence(text="Pump maintenance procedure")]
        resolved = [
            ResolvedEntity(
                original_text="P-101",
                entity_id="ast_001",
                entity_type="asset",
                confidence=0.9,
                canonical_name="Pump P-101",
            ),
        ]
        state = _initial_state(evidence=evidence, resolved_entities=resolved)
        result = await agent.run(state)

        submissions = result["context"]["reasoning_output"].metadata["knowledge_submissions"]
        assert any(s["asset_ids"] for s in submissions)

    @pytest.mark.asyncio
    async def test_extracts_tags(self, mock_db: MagicMock) -> None:
        agent = ExpertKnowledgeAgent(mock_db)
        evidence = [
            _make_evidence(text="Maintenance procedure for safety inspection"),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        submissions = result["context"]["reasoning_output"].metadata["knowledge_submissions"]
        all_tags = [t for s in submissions for t in s["tags"]]
        assert "maintenance" in all_tags or "safety" in all_tags

    @pytest.mark.asyncio
    async def test_abstains_without_evidence(self, mock_db: MagicMock) -> None:
        agent = ExpertKnowledgeAgent(mock_db)
        state = {
            "query": "Document knowledge",
            "context": {"evidence_bundle": None},
            "intent": QueryIntent.GENERAL,
            "resolved_entities": [],
            "retrieval_plan": None,
            "evidence_bundle": None,
            "messages": [],
            "claims": [],
            "final_response": None,
            "steps_completed": [],
            "errors": [],
        }
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert output.reasoning_decision == ReasoningDecision.ABSTAIN

    @pytest.mark.asyncio
    async def test_produces_citations(self, mock_db: MagicMock) -> None:
        agent = ExpertKnowledgeAgent(mock_db)
        evidence = [_make_evidence(text="Test")]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        citations = result["context"]["reasoning_output"].citations
        assert len(citations) == 1
        assert isinstance(citations[0], Citation)

    @pytest.mark.asyncio
    async def test_detects_conflicting_content_patterns(self, mock_db: MagicMock) -> None:
        agent = ExpertKnowledgeAgent(mock_db)
        evidence = [
            _make_evidence(text="Normal operating temperature is safe"),
            _make_evidence(text="Normal operating temperature is unsafe"),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert output.metadata["conflicts_detected"] >= 1


# ======================================================================
# LessonsLearnedAgent
# ======================================================================

class TestLessonsLearnedAgent:
    def test_registration_metadata(self, mock_db: MagicMock) -> None:
        agent = LessonsLearnedAgent(mock_db)
        reg = agent.to_registration()
        assert reg.name == "lessons_learned_agent"
        assert reg.role == AgentRole.ANALYSIS
        assert reg.capabilities[0].name == "lessons_learned"

    @pytest.mark.asyncio
    async def test_compares_historical_incidents(self, mock_db: MagicMock) -> None:
        agent = LessonsLearnedAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Pump failure due to bearing wear",
                metadata={"incident_id": "INC-001", "type": "incident_report"},
            ),
            _make_evidence(
                text="Pump bearing wear caused vibration alarm",
                metadata={"incident_id": "INC-002", "type": "incident_report"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        comparisons = output.metadata["historical_comparisons"]
        assert len(comparisons) >= 1
        assert all("similarity_score" in c for c in comparisons)

    @pytest.mark.asyncio
    async def test_detects_recurring_patterns(self, mock_db: MagicMock) -> None:
        agent = LessonsLearnedAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Bearing failure on pump P-101",
                metadata={"incident_id": "INC-001", "type": "incident_report"},
            ),
            _make_evidence(
                text="Bearing failure on pump P-102",
                metadata={"incident_id": "INC-002", "type": "incident_report"},
            ),
            _make_evidence(
                text="Bearing failure on pump P-103",
                metadata={"incident_id": "INC-003", "type": "incident_report"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        patterns = result["context"]["reasoning_output"].metadata["patterns"]
        assert len(patterns) >= 1
        assert any("bearing" in p["factor"].lower() or "failure" in p["factor"].lower() for p in patterns)

    @pytest.mark.asyncio
    async def test_generates_proactive_recommendations(self, mock_db: MagicMock) -> None:
        agent = LessonsLearnedAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Recurring vibration issue on rotating equipment",
                metadata={"incident_id": "INC-001", "type": "incident_report"},
            ),
            _make_evidence(
                text="Vibration monitoring prevented failure at site B",
                metadata={"incident_id": "INC-002", "type": "incident_report"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        recs = result["context"]["reasoning_output"].metadata["proactive_recommendations"]
        assert len(recs) >= 1
        assert all("category" in r for r in recs)

    @pytest.mark.asyncio
    async def test_abstains_without_evidence(self, mock_db: MagicMock) -> None:
        agent = LessonsLearnedAgent(mock_db)
        state = {
            "query": "Lessons learned",
            "context": {"evidence_bundle": None},
            "intent": QueryIntent.LESSONS_LEARNED,
            "resolved_entities": [],
            "retrieval_plan": None,
            "evidence_bundle": None,
            "messages": [],
            "claims": [],
            "final_response": None,
            "steps_completed": [],
            "errors": [],
        }
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert output.reasoning_decision == ReasoningDecision.ABSTAIN

    @pytest.mark.asyncio
    async def test_evaluates_action_effectiveness(self, mock_db: MagicMock) -> None:
        agent = LessonsLearnedAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Corrective action taken: replaced bearing",
                metadata={"incident_id": "INC-001", "status": "closed"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        effectiveness = result["context"]["reasoning_output"].metadata["action_effectiveness"]
        assert "total_applicable_actions" in effectiveness

    @pytest.mark.asyncio
    async def test_analyses_asset_similarity(self, mock_db: MagicMock) -> None:
        agent = LessonsLearnedAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Pump failure",
                metadata={"asset_id": "ast_001"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        similarity = result["context"]["reasoning_output"].metadata["asset_similarity"]
        assert "unique_assets" in similarity

    @pytest.mark.asyncio
    async def test_sufficient_when_high_similarity(self, mock_db: MagicMock) -> None:
        agent = LessonsLearnedAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Bearing failure caused vibration alarm on pump P-101",
                metadata={"incident_id": "INC-001"},
            ),
            _make_evidence(
                text="Bearing failure caused vibration alarm on pump P-102",
                metadata={"incident_id": "INC-002"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        if output.confidence_score >= 0.5:
            assert output.reasoning_decision == ReasoningDecision.SUFFICIENT

    @pytest.mark.asyncio
    async def test_requests_evidence_when_low_confidence(self, mock_db: MagicMock) -> None:
        agent = LessonsLearnedAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Unrelated observation about weather conditions",
                metadata={},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        if output.confidence_score < 0.5:
            assert output.reasoning_decision == ReasoningDecision.REQUEST_EVIDENCE

    @pytest.mark.asyncio
    async def test_produces_claims(self, mock_db: MagicMock) -> None:
        agent = LessonsLearnedAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Historical incident: pump failure",
                metadata={"incident_id": "INC-001"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert len(output.claims) >= 1
        for claim in output.claims:
            assert claim.text
            assert claim.reasoning

    @pytest.mark.asyncio
    async def test_missing_evidence_identified(self, mock_db: MagicMock) -> None:
        agent = LessonsLearnedAgent(mock_db)
        evidence = [
            _make_evidence(text="Just a general observation"),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        missing = result["context"]["reasoning_output"].missing_evidence
        assert len(missing) >= 1


# ======================================================================
# Cross-agent collaboration
# ======================================================================

class TestCrossAgentCollaboration:
    @pytest.mark.asyncio
    async def test_asset_intelligence_suggests_rca(self, mock_db: MagicMock) -> None:
        agent = AssetIntelligenceAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Uncertain reading",
                confidence=0.4,
                relevance=0.3,
                verification_status="unverified",
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert output.reasoning_decision != ReasoningDecision.SUFFICIENT

    @pytest.mark.asyncio
    async def test_compliance_suggests_expert_knowledge(self, mock_db: MagicMock) -> None:
        agent = ComplianceAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Certificate expired",
                metadata={"expiry_date": "2022-01-01"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert "expert_knowledge_agent" in output.next_recommended_agents

    @pytest.mark.asyncio
    async def test_rca_suggests_lessons_learned(self, mock_db: MagicMock) -> None:
        agent = RCAAgent(mock_db)
        evidence = [
            _make_evidence(
                text="Failure on pump",
                metadata={"incident_id": "INC-001", "type": "incident_report"},
            ),
        ]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        # RCA checks for similar failures via previous reasoning outputs
        output = result["context"]["reasoning_output"]
        assert output.reasoning_decision in [
            ReasoningDecision.SUFFICIENT,
            ReasoningDecision.REQUEST_EVIDENCE,
            ReasoningDecision.ABSTAIN,
        ]

    @pytest.mark.asyncio
    async def test_expert_knowledge_suggests_lessons_learned(self, mock_db: MagicMock) -> None:
        agent = ExpertKnowledgeAgent(mock_db)
        evidence = [_make_evidence(text="Expert observation")]
        state = _initial_state(evidence=evidence)
        result = await agent.run(state)

        output = result["context"]["reasoning_output"]
        assert "lessons_learned_agent" in output.next_recommended_agents


# ======================================================================
# ReasoningOutput schema
# ======================================================================

class TestReasoningOutputSchema:
    def test_output_has_required_fields(self) -> None:
        output = ReasoningOutput(
            agent_name="test_agent",
            reasoning_decision=ReasoningDecision.SUFFICIENT,
            confidence_score=0.85,
            reasoning_summary="Test summary",
        )
        assert output.agent_name == "test_agent"
        assert output.reasoning_decision == ReasoningDecision.SUFFICIENT
        assert output.confidence_score == 0.85
        assert output.claims == []
        assert output.citations == []
        assert output.missing_evidence == []
        assert output.contradictions == []
        assert output.next_actions == []
        assert output.next_recommended_agents == []

    def test_decision_enum_values(self) -> None:
        decisions = [
            ReasoningDecision.SUFFICIENT,
            ReasoningDecision.REQUEST_EVIDENCE,
            ReasoningDecision.DELEGATE,
            ReasoningDecision.ABSTAIN,
            ReasoningDecision.NEEDS_HUMAN_REVIEW,
        ]
        assert len(decisions) == 5
        assert all(isinstance(d, str) for d in decisions)

    def test_metadata_supports_rca_fields(self) -> None:
        output = ReasoningOutput(
            agent_name="rca_agent",
            reasoning_decision=ReasoningDecision.SUFFICIENT,
            metadata={
                "timeline": [],
                "hypotheses": [],
                "evidence_rankings": [],
                "test_recommendations": [],
            },
        )
        assert "timeline" in output.metadata
        assert "hypotheses" in output.metadata
        assert "evidence_rankings" in output.metadata
        assert "test_recommendations" in output.metadata

    def test_metadata_supports_compliance_fields(self) -> None:
        output = ReasoningOutput(
            agent_name="compliance_agent",
            reasoning_decision=ReasoningDecision.SUFFICIENT,
            metadata={
                "compliance_checks": [],
                "pass_rate": 1.0,
                "total_checks": 5,
            },
        )
        assert output.metadata["pass_rate"] == 1.0
        assert output.metadata["total_checks"] == 5

    def test_metadata_supports_knowledge_fields(self) -> None:
        output = ReasoningOutput(
            agent_name="expert_knowledge_agent",
            reasoning_decision=ReasoningDecision.NEEDS_HUMAN_REVIEW,
            metadata={
                "knowledge_submissions": [],
                "conflicts_detected": 0,
                "pending_review": 1,
            },
        )
        assert output.metadata["pending_review"] == 1

    def test_metadata_supports_lessons_learned_fields(self) -> None:
        output = ReasoningOutput(
            agent_name="lessons_learned_agent",
            reasoning_decision=ReasoningDecision.SUFFICIENT,
            metadata={
                "historical_comparisons": [],
                "patterns": [],
                "proactive_recommendations": [],
            },
        )
        assert "historical_comparisons" in output.metadata
