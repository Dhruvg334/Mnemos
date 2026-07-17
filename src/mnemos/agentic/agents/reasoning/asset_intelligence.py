"""Asset Intelligence Agent.

Analyses verified evidence to produce structured intelligence about
industrial assets: health status, operating parameters, maintenance
history, relationships, and risk indicators.

All conclusions trace to verified evidence only.
No hallucinated facts.
"""

from __future__ import annotations

import uuid

from mnemos.agentic.agents.reasoning._base import _BaseReasoningAgent
from mnemos.agentic.runtime.types import AgentCapability, AgentRole
from mnemos.agentic.schemas.base import (
    Citation,
    ClaimSupportStatus,
    ConfidenceSignal,
    EvidenceSource,
    GroundedClaim,
    MissingEvidence,
    ReasoningDecision,
    ReasoningOutput,
    RecommendedAction,
)
from mnemos.agentic.schemas.state import AgentState


class AssetIntelligenceAgent(_BaseReasoningAgent):
    """Produces structured intelligence about industrial assets.

    Reads verified evidence from the retrieval layer and extracts:
    - Asset identity and specifications
    - Operating parameters and thresholds
    - Maintenance history and status
    - Component relationships
    - Risk indicators and anomalies

    Every claim is grounded in verified evidence.
    """

    name = "asset_intelligence"
    role = AgentRole.ANALYSIS
    description = (
        "Analyses verified evidence to produce structured intelligence "
        "about industrial assets: health, parameters, maintenance, "
        "relationships, and risk indicators."
    )
    timeout_seconds = 60.0

    def _capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="asset_intelligence",
                description=(
                    "Extracts structured asset intelligence from verified evidence: "
                    "specifications, parameters, maintenance status, relationships, "
                    "and risk indicators."
                ),
                input_types=["evidence_bundle"],
                output_types=["reasoning_output", "asset_claims"],
                dependencies=["evidence_verification"],
            ),
        ]

    @property
    def required_dependencies(self) -> list[str]:
        return ["evidence_verification"]

    async def execute(self, state: AgentState) -> AgentState:
        bundle = self._validate_evidence_exists(state)
        if bundle is None:
            return state

        verified = bundle.verified_evidence
        if not verified:
            output = ReasoningOutput(
                agent_name=self.name,
                reasoning_decision=ReasoningDecision.ABSTAIN,
                confidence_score=0.0,
                reasoning_summary="No verified evidence available for asset analysis",
                missing_evidence=[
                    MissingEvidence(
                        evidence_type="asset_evidence",
                        description="No verified evidence sources found for asset analysis",
                        suggested_action="Retrieve additional evidence about the target asset",
                        priority="high",
                    )
                ],
            )
            self._store_reasoning_output(state, output)
            return state

        claims = self._extract_claims(verified)
        citations = self._build_citations(verified)
        confidence = self._calculate_confidence(verified, claims)
        missing = self._identify_missing_evidence(verified, state)
        next_actions = self._recommend_actions(claims, verified)

        # Cross-asset comparison
        similar_assets = self._compare_similar_assets(verified, state)
        if similar_assets:
            claims.extend(similar_assets["claims"])
            missing.extend(similar_assets["missing_evidence"])
            next_actions.extend(similar_assets["actions"])

        output = ReasoningOutput(
            agent_name=self.name,
            reasoning_decision=(
                ReasoningDecision.SUFFICIENT
                if confidence >= 0.5
                else ReasoningDecision.REQUEST_EVIDENCE
            ),
            claims=claims,
            citations=citations,
            confidence_score=confidence,
            missing_evidence=missing,
            confidence_signals=[
                ConfidenceSignal(
                    signal_name="evidence_count",
                    signal_value=min(len(verified) / 5.0, 1.0),
                    weight=1.0,
                    reasoning=f"{len(verified)} verified evidence sources available",
                ),
                ConfidenceSignal(
                    signal_name="avg_source_confidence",
                    signal_value=sum(s.confidence_score for s in verified) / len(verified),
                    weight=1.5,
                    reasoning="Average confidence across all evidence sources",
                ),
            ],
            next_actions=next_actions,
            next_recommended_agents=(
                ["rca_agent"] if any(c.status == ClaimSupportStatus.UNCERTAIN for c in claims) else []
            ),
            reasoning_summary=(
                f"Extracted {len(claims)} grounded claims from "
                f"{len(verified)} verified evidence sources. "
                f"Overall confidence: {confidence:.2f}"
            ),
        )

        self._store_reasoning_output(state, output)

        for claim in claims:
            state.setdefault("claims", [])
            state["claims"].append(claim)

        self.logger.info(
            f"Asset intelligence: {len(claims)} claims, "
            f"confidence={confidence:.2f}, "
            f"missing={len(missing)}"
        )
        return state

    # ------------------------------------------------------------------
    # Claim extraction
    # ------------------------------------------------------------------

    def _extract_claims(
        self, evidence: list[EvidenceSource]
    ) -> list[GroundedClaim]:
        """Extract grounded claims from verified evidence.

        Each claim traces to specific evidence sources.
        """
        claims: list[GroundedClaim] = []
        seen_signatures: set[str] = set()

        for _idx, source in enumerate(evidence):
            text = source.text_excerpt.strip()
            if not text:
                continue

            signature = text.lower()[:100]
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)

            claim_id = f"asset_claim_{uuid.uuid4().hex[:8]}"
            status = self._assess_claim_status(source)

            claims.append(
                GroundedClaim(
                    claim_id=claim_id,
                    text=text,
                    status=status,
                    sources=[source],
                    reasoning=self._explain_grounding(source, status),
                )
            )

        return claims

    def _assess_claim_status(self, source: EvidenceSource) -> ClaimSupportStatus:
        """Determine support status based on evidence quality."""
        if source.verification_status == "provenance_validated":
            if source.confidence_score >= 0.8 and source.relevance_score >= 0.7:
                return ClaimSupportStatus.SUPPORTED
            if source.confidence_score >= 0.5:
                return ClaimSupportStatus.PARTIALLY_SUPPORTED
        if source.verification_status == "human_reviewed":
            return ClaimSupportStatus.SUPPORTED
        if source.verification_status == "conflicted":
            return ClaimSupportStatus.UNCERTAIN
        if source.confidence_score < 0.3:
            return ClaimSupportStatus.NO_EVIDENCE
        return ClaimSupportStatus.PARTIALLY_SUPPORTED

    def _explain_grounding(
        self, source: EvidenceSource, status: ClaimSupportStatus
    ) -> str:
        return (
            f"Claim grounded in evidence from {source.provenance.source_filename} "
            f"(v{source.provenance.document_version}), "
            f"confidence={source.confidence_score:.2f}, "
            f"relevance={source.relevance_score:.2f}, "
            f"verification={source.verification_status}"
        )

    # ------------------------------------------------------------------
    # Citations
    # ------------------------------------------------------------------

    def _build_citations(
        self, evidence: list[EvidenceSource]
    ) -> list[Citation]:
        citations: list[Citation] = []
        for source in evidence:
            p = source.provenance
            citations.append(
                Citation(
                    citation_id=f"cit_{uuid.uuid4().hex[:8]}",
                    evidence_region_id=p.evidence_region_id,
                    document_id=p.document_id,
                    document_version=p.document_version,
                    chunk_id=p.chunk_id,
                    page_number=p.page_number,
                    locator=p.locator,
                    text_excerpt=source.text_excerpt,
                    relevance_score=source.relevance_score,
                    confidence_score=source.confidence_score,
                )
            )
        return citations

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def _calculate_confidence(
        self,
        evidence: list[EvidenceSource],
        claims: list[GroundedClaim],
    ) -> float:
        if not evidence:
            return 0.0

        source_conf = sum(s.confidence_score for s in evidence) / len(evidence)
        source_rel = sum(s.relevance_score for s in evidence) / len(evidence)

        supported = sum(
            1 for c in claims
            if c.status in (ClaimSupportStatus.SUPPORTED, ClaimSupportStatus.PARTIALLY_SUPPORTED)
        )
        claim_ratio = supported / len(claims) if claims else 0.0

        provenance_count = sum(
            1 for s in evidence
            if s.verification_status in ("provenance_validated", "human_reviewed")
        )
        provenance_ratio = provenance_count / len(evidence)

        confidence = (
            0.35 * source_conf
            + 0.25 * source_rel
            + 0.25 * claim_ratio
            + 0.15 * provenance_ratio
        )
        return round(min(confidence, 1.0), 3)

    # ------------------------------------------------------------------
    # Missing evidence
    # ------------------------------------------------------------------

    def _identify_missing_evidence(
        self,
        evidence: list[EvidenceSource],
        state: AgentState,
    ) -> list[MissingEvidence]:
        missing: list[MissingEvidence] = []

        source_types = {s.metadata.get("type", "unknown") for s in evidence}
        if "graph" not in source_types:
            missing.append(
                MissingEvidence(
                    evidence_type="graph_relationships",
                    description="No graph-based evidence for asset relationships",
                    suggested_action="Query asset hierarchy and component graphs",
                    priority="medium",
                )
            )

        if len(evidence) < 3:
            missing.append(
                MissingEvidence(
                    evidence_type="additional_sources",
                    description=f"Only {len(evidence)} evidence sources found; "
                    "multiple independent sources improve reliability",
                    suggested_action="Retrieve evidence from additional document sources",
                    priority="medium",
                )
            )

        return missing

    # ------------------------------------------------------------------
    # Recommended actions
    # ------------------------------------------------------------------

    def _recommend_actions(
        self,
        claims: list[GroundedClaim],
        evidence: list[EvidenceSource],
    ) -> list[RecommendedAction]:
        actions: list[RecommendedAction] = []

        uncertain = [
            c for c in claims if c.status == ClaimSupportStatus.UNCERTAIN
        ]
        if uncertain:
            actions.append(
                RecommendedAction(
                    action_id=f"act_{uuid.uuid4().hex[:8]}",
                    type="INSPECTION",
                    description=(
                        f"{len(uncertain)} claims have uncertain support. "
                        "Physical inspection recommended to verify."
                    ),
                    priority="medium",
                    reasoning="Claims with uncertain support status require direct verification",
                    linked_claim_ids=[c.claim_id for c in uncertain],
                )
            )

        partially = [
            c for c in claims if c.status == ClaimSupportStatus.PARTIALLY_SUPPORTED
        ]
        if partially:
            actions.append(
                RecommendedAction(
                    action_id=f"act_{uuid.uuid4().hex[:8]}",
                    type="TEST",
                    description=(
                        f"{len(partially)} claims are only partially supported. "
                        "Additional testing recommended."
                    ),
                    priority="low",
                    reasoning="Partially supported claims benefit from corroborating evidence",
                    linked_claim_ids=[c.claim_id for c in partially],
                )
            )

        return actions

    # ------------------------------------------------------------------
    # Cross-asset comparison
    # ------------------------------------------------------------------

    def _compare_similar_assets(
        self,
        evidence: list[EvidenceSource],
        state: AgentState,
    ) -> dict[str, Any]:
        """Compare the target asset with similar assets using graph and evidence data.

        Looks for evidence sourced from graph traversals that reference
        related assets (same component type, same failure mode, same site).
        Produces comparison claims and identifies unresolved actions.
        """
        ctx = state.get("context", {})
        bundle = ctx.get("evidence_bundle")

        # Collect similar asset evidence from graph traversals
        similar_asset_evidence: list[dict[str, Any]] = []
        if bundle is not None:
            raw_graph = getattr(bundle, "raw_graph_data", {})
            for entity_id, data in raw_graph.items():
                if not isinstance(data, dict):
                    continue
                nodes = data.get("nodes", [])
                for node in nodes:
                    if not isinstance(node, dict):
                        continue
                    node_type = str(node.get("type", "")).lower()
                    node_id = str(node.get("id", ""))
                    # Skip the primary asset itself
                    primary_entities = {
                        e.entity_id for e in getattr(bundle, "resolved_entities", [])
                    }
                    if node_id in primary_entities:
                        continue
                    if node_type in ("asset", "component", "failure_mode"):
                        similar_asset_evidence.append(node)

        if not similar_asset_evidence:
            return {}

        # Build comparison claims
        claims: list[GroundedClaim] = []
        missing_evidence: list[MissingEvidence] = []
        actions: list[RecommendedAction] = []

        # Group similar assets by type
        asset_type_groups: dict[str, list[dict]] = {}
        for node in similar_asset_evidence:
            ntype = str(node.get("type", "unknown")).lower()
            asset_type_groups.setdefault(ntype, []).append(node)

        for asset_type, nodes in asset_type_groups.items():
            claim_id = f"asset_comparison_{uuid.uuid4().hex[:8]}"
            node_names = [str(n.get("name", n.get("id", "?"))) for n in nodes[:5]]
            claim_text = (
                f"{len(nodes)} similar {asset_type}(s) identified in the knowledge graph: "
                f"{', '.join(node_names)}"
                f"{'...' if len(nodes) > 5 else ''}"
            )
            claims.append(
                GroundedClaim(
                    claim_id=claim_id,
                    text=claim_text,
                    status=ClaimSupportStatus.PARTIALLY_SUPPORTED,
                    sources=[],
                    reasoning=(
                        f"Cross-asset comparison found {len(nodes)} related "
                        f"{asset_type} entities via graph traversal"
                    ),
                )
            )

        # Check for unresolved actions on similar assets
        unresolved_assets = [
            n for n in similar_asset_evidence
            if str(n.get("status", "")).lower() in ("active", "open", "pending", "in_progress")
        ]
        if unresolved_assets:
            actions.append(
                RecommendedAction(
                    action_id=f"act_{uuid.uuid4().hex[:8]}",
                    type="MONITOR",
                    description=(
                        f"{len(unresolved_assets)} similar assets have unresolved "
                        "actions or active issues that may be relevant"
                    ),
                    priority="medium",
                    reasoning="Similar assets with unresolved issues may share root causes",
                )
            )

        # Identify gaps: no cross-asset evidence means comparison is incomplete
        if len(similar_asset_evidence) < 2:
            missing_evidence.append(
                MissingEvidence(
                    evidence_type="cross_asset_comparison",
                    description=(
                        "Limited similar asset data available for comprehensive "
                        "cross-asset comparison"
                    ),
                    suggested_action=(
                        "Query failure_graph and component_graph for related assets "
                        "with similar failure modes"
                    ),
                    priority="medium",
                )
            )

        return {
            "claims": claims,
            "missing_evidence": missing_evidence,
            "actions": actions,
            "similar_asset_count": len(similar_asset_evidence),
        }
