"""Expert Knowledge Agent.

Structures expert knowledge submissions from verified evidence:
- Structures raw knowledge into formatted cards
- Links knowledge to graph entities (assets, documents, procedures)
- Detects conflicts with existing knowledge
- Requests human review before publishing
- Never publishes directly
"""

from __future__ import annotations

import uuid
from typing import Any

from mnemos.agentic.agents.reasoning._base import _BaseReasoningAgent
from mnemos.agentic.runtime.types import AgentCapability, AgentRole
from mnemos.agentic.schemas.base import (
    Citation,
    ClaimSupportStatus,
    ConfidenceSignal,
    EvidenceSource,
    GroundedClaim,
    KnowledgeSubmission,
    MissingEvidence,
    ReasoningDecision,
    ReasoningOutput,
    RecommendedAction,
)
from mnemos.agentic.schemas.state import AgentState


class ExpertKnowledgeAgent(_BaseReasoningAgent):
    """Structures expert knowledge from verified evidence.

    Pipeline:
    1. Structure raw evidence into knowledge submissions
    2. Link to graph entities (assets, documents, procedures)
    3. Detect conflicts with existing knowledge
    4. Request review (never publishes directly)

    Every submission is grounded in verified evidence.
    """

    name = "expert_knowledge_agent"
    role = AgentRole.ANALYSIS
    description = (
        "Structures expert knowledge submissions, links to graph entities, "
        "detects conflicts, and requests human review. Never publishes directly."
    )
    timeout_seconds = 60.0

    def _capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="expert_knowledge",
                description=(
                    "Structures knowledge submissions, links graph entities, "
                    "detects conflicts, and requests review."
                ),
                input_types=["evidence_bundle", "reasoning_outputs"],
                output_types=["reasoning_output", "knowledge_submissions"],
                dependencies=["evidence_verification"],
            ),
        ]

    @property
    def required_dependencies(self) -> list[str]:
        return ["evidence_verification"]

    async def execute(self, state: AgentState) -> AgentState:
        bundle = self._validate_evidence_exists(state)
        ctx = state.get("context", {})

        # Check for voice transcription input
        voice_transcription = ctx.get("voice_transcription")
        if voice_transcription and isinstance(voice_transcription, str):
            # Process voice transcription as additional expert evidence
            voice_evidence = self._process_voice_transcription(
                voice_transcription, state
            )
            if bundle is None:
                # Create a minimal bundle from voice transcription alone
                from mnemos.agentic.schemas.base import EvidenceBundle
                bundle = EvidenceBundle(
                    query_id=ctx.get("query_id", "voice"),
                    intent=ctx.get("intent", "general"),
                    verified_evidence=voice_evidence,
                )
                ctx["evidence_bundle"] = bundle
                state["context"] = ctx
            else:
                bundle.verified_evidence.extend(voice_evidence)

        if bundle is None:
            return state

        verified = bundle.verified_evidence
        if not verified:
            output = ReasoningOutput(
                agent_name=self.name,
                reasoning_decision=ReasoningDecision.ABSTAIN,
                confidence_score=0.0,
                reasoning_summary="No verified evidence for knowledge structuring",
                missing_evidence=[
                    MissingEvidence(
                        evidence_type="expert_evidence",
                        description="No verified evidence for knowledge structuring",
                        suggested_action="Retrieve expert testimony or documented procedures",
                        priority="high",
                    )
                ],
            )
            self._store_reasoning_output(state, output)
            return state

        submissions = self._structure_submissions(verified, state)
        submissions = self._link_entities(submissions, bundle)
        submissions = self._detect_conflicts(submissions, state)
        submissions = self._request_review(submissions)
        claims = self._build_claims(submissions, verified)
        citations = self._build_citations(verified)
        confidence = self._calculate_confidence(submissions, verified)
        missing = self._identify_missing(submissions, verified)
        next_actions = self._build_actions(submissions)

        output = ReasoningOutput(
            agent_name=self.name,
            reasoning_decision=ReasoningDecision.NEEDS_HUMAN_REVIEW,
            claims=claims,
            citations=citations,
            confidence_score=confidence,
            missing_evidence=missing,
            confidence_signals=[
                ConfidenceSignal(
                    signal_name="submission_count",
                    signal_value=min(len(submissions) / 3.0, 1.0),
                    weight=1.0,
                    reasoning=f"{len(submissions)} knowledge submissions structured",
                ),
                ConfidenceSignal(
                    signal_name="conflict_rate",
                    signal_value=1.0 - (
                        sum(1 for s in submissions if s.conflicts_with) / max(len(submissions), 1)
                    ),
                    weight=1.5,
                    reasoning="Ratio of conflict-free submissions",
                ),
            ],
            next_actions=next_actions,
            next_recommended_agents=["lessons_learned_agent"],
            reasoning_summary=self._build_summary(submissions, confidence),
            metadata={
                "knowledge_submissions": [s.model_dump() for s in submissions],
                "total_submissions": len(submissions),
                "conflicts_detected": sum(1 for s in submissions if s.conflicts_with),
                "pending_review": sum(
                    1 for s in submissions if s.status == "submitted_for_review"
                ),
            },
        )

        self._store_reasoning_output(state, output)

        for claim in claims:
            state.setdefault("claims", [])
            state["claims"].append(claim)

        self.logger.info(
            f"Expert knowledge: {len(submissions)} submissions, "
            f"conflicts={sum(1 for s in submissions if s.conflicts_with)}, "
            f"confidence={confidence:.2f}"
        )
        return state

    # ------------------------------------------------------------------
    # Structure submissions
    # ------------------------------------------------------------------

    def _structure_submissions(
        self,
        evidence: list[EvidenceSource],
        state: AgentState,
    ) -> list[KnowledgeSubmission]:
        """Structure verified evidence into knowledge submissions."""
        submissions: list[KnowledgeSubmission] = []
        ctx = state.get("context", {})

        asset_ids: list[str] = ctx.get("resolved_entities", [])
        if isinstance(asset_ids, list) and asset_ids:
            if isinstance(asset_ids[0], dict):
                asset_ids = [e.get("entity_id", "") for e in asset_ids if isinstance(e, dict)]

        for _idx, source in enumerate(evidence):
            text = source.text_excerpt.strip()
            if not text:
                continue

            tags = self._extract_tags(text)

            submissions.append(
                KnowledgeSubmission(
                    submission_id=f"sub_{uuid.uuid4().hex[:8]}",
                    title=f"Knowledge from {source.provenance.source_filename}: {text[:60]}",
                    content=text,
                    asset_ids=asset_ids[:5] if asset_ids else [],
                    source_evidence_ids=[source.provenance.evidence_region_id],
                    tags=tags,
                    status="draft",
                    reasoning=f"Structured from verified evidence (confidence={source.confidence_score:.2f})",
                )
            )

        return submissions

    def _extract_tags(self, text: str) -> list[str]:
        """Extract relevant tags from text content."""
        tags: list[str] = []
        tag_keywords = {
            "maintenance": "maintenance",
            "repair": "repair",
            "inspection": "inspection",
            "safety": "safety",
            "procedure": "procedure",
            "calibration": "calibration",
            "failure": "failure",
            "operating": "operations",
            "specification": "specification",
        }
        text_lower = text.lower()
        for keyword, tag in tag_keywords.items():
            if keyword in text_lower:
                tags.append(tag)
        return tags

    # ------------------------------------------------------------------
    # Link entities
    # ------------------------------------------------------------------

    def _link_entities(
        self,
        submissions: list[KnowledgeSubmission],
        bundle: Any,
    ) -> list[KnowledgeSubmission]:
        """Link knowledge submissions to graph entities."""
        entity_ids = {
            e.entity_id for e in getattr(bundle, "resolved_entities", [])
        }

        for sub in submissions:
            linked = set(sub.asset_ids)
            for eid in entity_ids:
                if eid and eid not in linked:
                    linked.add(eid)
            sub.asset_ids = list(linked)[:10]

        return submissions

    # ------------------------------------------------------------------
    # Detect conflicts
    # ------------------------------------------------------------------

    def _detect_conflicts(
        self,
        submissions: list[KnowledgeSubmission],
        state: AgentState,
    ) -> list[KnowledgeSubmission]:
        """Detect conflicts with existing knowledge or between submissions."""
        previous = self._get_previous_reasoning(state)
        existing_claims: list[str] = []
        for output in previous:
            for claim in output.claims:
                existing_claims.append(claim.text.lower())

        for idx, sub in enumerate(submissions):
            content_lower = sub.content.lower()

            for prev_claim in existing_claims:
                if self._is_conflicting(content_lower, prev_claim):
                    sub.conflicts_with.append(f"existing_claim_{hash(prev_claim) % 10000}")

            for jdx, other in enumerate(submissions):
                if idx != jdx and self._is_conflicting(
                    content_lower, other.content.lower()
                ):
                    if other.submission_id not in sub.conflicts_with:
                        sub.conflicts_with.append(other.submission_id)

        return submissions

    def _is_conflicting(self, text_a: str, text_b: str) -> bool:
        """Simple conflict detection based on negation patterns."""
        negation_pairs = [
            ("increase", "decrease"),
            ("always", "never"),
            ("required", "not required"),
            ("pass", "fail"),
            ("safe", "unsafe"),
            ("normal", "abnormal"),
            ("open", "closed"),
            ("on", "off"),
        ]
        for pos, neg in negation_pairs:
            if (pos in text_a and neg in text_b) or (neg in text_a and pos in text_b):
                return True
        return False

    # ------------------------------------------------------------------
    # Request review (never publish directly)
    # ------------------------------------------------------------------

    def _request_review(
        self, submissions: list[KnowledgeSubmission]
    ) -> list[KnowledgeSubmission]:
        """Mark all submissions for human review. Never publishes directly."""
        for sub in submissions:
            if sub.status == "draft":
                sub.status = "submitted_for_review"
        return submissions

    # ------------------------------------------------------------------
    # Voice transcription processing
    # ------------------------------------------------------------------

    def _process_voice_transcription(
        self,
        transcription: str,
        state: AgentState,
    ) -> list[EvidenceSource]:
        """Process a voice transcription into structured evidence.

        Takes raw transcribed text from an expert's voice submission,
        segments it into meaningful knowledge fragments, and wraps each
        as an EvidenceSource for downstream structuring.
        """
        from mnemos.agentic.schemas.base import (
            EvidenceSource,
            ProvenanceChain,
            VerificationStatus,
        )

        evidence_sources: list[EvidenceSource] = []

        # Split transcription into sentences/segments
        segments = self._segment_transcription(transcription)

        for idx, segment in enumerate(segments):
            if not segment.strip() or len(segment.strip()) < 10:
                continue

            provenance = ProvenanceChain(
                document_id=f"voice_transcription_{uuid.uuid4().hex[:8]}",
                document_version=1,
                evidence_region_id=f"voice_region_{idx}",
                source_filename="voice_submission",
                source_type="voice_transcription",
                verification_status=VerificationStatus.UNVERIFIED,
            )

            evidence_sources.append(
                EvidenceSource(
                    text_excerpt=segment.strip(),
                    confidence_score=0.7,
                    relevance_score=0.8,
                    verification_status=VerificationStatus.UNVERIFIED,
                    provenance=provenance,
                    metadata={
                        "type": "voice_transcription",
                        "source": "expert_voice",
                        "segment_index": idx,
                        "total_segments": len(segments),
                    },
                )
            )

        self.logger.info(
            f"Processed voice transcription: {len(segments)} segments, "
            f"{len(evidence_sources)} evidence sources created"
        )
        return evidence_sources

    def _segment_transcription(self, text: str) -> list[str]:
        """Segment a voice transcription into meaningful knowledge fragments.

        Splits on sentence boundaries (periods, newlines) and merges
        very short segments. Returns non-empty segments.
        """
        import re

        # Split on sentence-ending punctuation followed by whitespace or newline
        raw_segments = re.split(r'(?<=[.!?])\s+|\n+', text)

        # Merge very short segments with their successor
        merged: list[str] = []
        buffer = ""
        for seg in raw_segments:
            if not seg.strip():
                continue
            if buffer:
                buffer = f"{buffer} {seg.strip()}"
                if len(buffer) >= 30:
                    merged.append(buffer)
                    buffer = ""
            elif len(seg.strip()) < 20:
                buffer = seg.strip()
            else:
                merged.append(seg.strip())

        if buffer:
            merged.append(buffer)

        return merged

    # ------------------------------------------------------------------
    # Claims
    # ------------------------------------------------------------------

    def _build_claims(
        self,
        submissions: list[KnowledgeSubmission],
        evidence: list[EvidenceSource],
    ) -> list[GroundedClaim]:
        claims: list[GroundedClaim] = []

        for sub in submissions:
            conflict_status = ClaimSupportStatus.PARTIALLY_SUPPORTED if sub.conflicts_with else ClaimSupportStatus.SUPPORTED
            claims.append(
                GroundedClaim(
                    claim_id=sub.submission_id,
                    text=sub.content[:200],
                    status=conflict_status,
                    sources=[
                        s for s in evidence
                        if s.provenance.evidence_region_id in sub.source_evidence_ids
                    ][:3],
                    reasoning=sub.reasoning,
                )
            )

        return claims

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
        submissions: list[KnowledgeSubmission],
        evidence: list[EvidenceSource],
    ) -> float:
        if not submissions:
            return 0.0

        conflict_free = sum(1 for s in submissions if not s.conflicts_with)
        conflict_ratio = conflict_free / len(submissions)

        evidence_quality = (
            sum(s.confidence_score for s in evidence) / len(evidence)
            if evidence
            else 0.0
        )

        has_entities = any(s.asset_ids for s in submissions)
        entity_bonus = 0.15 if has_entities else 0.0

        confidence = (
            0.4 * conflict_ratio
            + 0.4 * evidence_quality
            + entity_bonus
            + 0.05
        )
        return round(min(confidence, 1.0), 3)

    # ------------------------------------------------------------------
    # Missing evidence
    # ------------------------------------------------------------------

    def _identify_missing(
        self,
        submissions: list[KnowledgeSubmission],
        evidence: list[EvidenceSource],
    ) -> list[MissingEvidence]:
        missing: list[MissingEvidence] = []

        conflicting = [s for s in submissions if s.conflicts_with]
        if conflicting:
            missing.append(
                MissingEvidence(
                    evidence_type="conflict_resolution",
                    description=(
                        f"{len(conflicting)} submissions conflict with existing knowledge. "
                        "Resolution evidence needed."
                    ),
                    suggested_action="Provide evidence to resolve conflicts",
                    priority="high",
                )
            )

        unlinked = [s for s in submissions if not s.asset_ids]
        if unlinked:
            missing.append(
                MissingEvidence(
                    evidence_type="entity_linking",
                    description=f"{len(unlinked)} submissions lack entity links",
                    suggested_action="Link knowledge to specific assets or documents",
                    priority="medium",
                )
            )

        return missing

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _build_actions(
        self, submissions: list[KnowledgeSubmission]
    ) -> list[RecommendedAction]:
        actions: list[RecommendedAction] = []

        for sub in submissions:
            if sub.conflicts_with:
                actions.append(
                    RecommendedAction(
                        action_id=f"act_{uuid.uuid4().hex[:8]}",
                        type="TRAINING",
                        description=f"Resolve conflict in knowledge: {sub.title[:80]}",
                        priority="high",
                        reasoning=f"Submission conflicts with {len(sub.conflicts_with)} existing items",
                        linked_claim_ids=[sub.submission_id],
                    )
                )

        pending = [s for s in submissions if s.status == "submitted_for_review"]
        if pending:
            actions.append(
                RecommendedAction(
                    action_id=f"act_{uuid.uuid4().hex[:8]}",
                    type="PROCEDURE_UPDATE",
                    description=(
                        f"{len(pending)} knowledge submissions awaiting human review"
                    ),
                    priority="medium",
                    reasoning="All submissions require human review before publishing",
                )
            )

        return actions

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        submissions: list[KnowledgeSubmission],
        confidence: float,
    ) -> str:
        conflicts = sum(1 for s in submissions if s.conflicts_with)
        pending = sum(1 for s in submissions if s.status == "submitted_for_review")
        parts = [
            f"Structured {len(submissions)} knowledge submissions.",
            f"Conflicts detected: {conflicts}.",
            f"Pending review: {pending}.",
            f"Confidence: {confidence:.2f}.",
            "All submissions routed for human review.",
        ]
        return " ".join(parts)
