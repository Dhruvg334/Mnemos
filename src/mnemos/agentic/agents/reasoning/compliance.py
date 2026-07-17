"""Compliance Agent.

Performs deterministic compliance verification using structured checks:
- Document revision validation
- Date compliance (expiry, validity windows)
- Requirement mapping to evidence
- Workflow status verification
- Certification expiry tracking

Uses NO LLM for checks — all checks are deterministic and rule-based.
Every check result traces to specific evidence.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from mnemos.agentic.agents.reasoning._base import _BaseReasoningAgent
from mnemos.agentic.runtime.types import AgentCapability, AgentRole
from mnemos.agentic.schemas.base import (
    Citation,
    ClaimSupportStatus,
    ComplianceCheckResult,
    ConfidenceSignal,
    EvidenceSource,
    GroundedClaim,
    MissingEvidence,
    ReasoningDecision,
    ReasoningOutput,
    RecommendedAction,
)
from mnemos.agentic.schemas.state import AgentState


class ComplianceAgent(_BaseReasoningAgent):
    """Performs deterministic compliance verification.

    All checks are rule-based with zero LLM involvement:
    - Revision checks: Document version currency
    - Date validation: Expiry, validity windows, review deadlines
    - Requirement mapping: Evidence-to-requirement coverage
    - Expiry validation: Certifications, permits, training
    - Workflow status: Approval chains, review completion

    Every result traces to specific evidence sources.
    """

    name = "compliance_agent"
    role = AgentRole.ANALYSIS
    description = (
        "Deterministic compliance verification: revision checks, date "
        "validation, requirement mapping, expiry validation, and "
        "workflow status. No LLM — rule-based checks only."
    )
    timeout_seconds = 60.0

    def _capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="compliance_verification",
                description=(
                    "Runs deterministic compliance checks: revision currency, "
                    "date validation, requirement mapping, expiry, workflow status."
                ),
                input_types=["evidence_bundle"],
                output_types=["reasoning_output", "compliance_checks"],
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
                reasoning_summary="No verified evidence for compliance checks",
                missing_evidence=[
                    MissingEvidence(
                        evidence_type="compliance_evidence",
                        description="No evidence available for compliance verification",
                        suggested_action="Retrieve compliance-related documents and evidence",
                        priority="high",
                    )
                ],
            )
            self._store_reasoning_output(state, output)
            return state

        checks = self._run_all_checks(verified, state)
        claims = self._build_claims(checks)
        citations = self._build_citations(verified)
        confidence = self._calculate_confidence(checks)
        missing = self._identify_missing(checks, verified)
        next_actions = self._build_actions(checks)

        output = ReasoningOutput(
            agent_name=self.name,
            reasoning_decision=self._decide(checks, confidence),
            claims=claims,
            citations=citations,
            confidence_score=confidence,
            missing_evidence=missing,
            confidence_signals=[
                ConfidenceSignal(
                    signal_name="check_pass_rate",
                    signal_value=self._pass_rate(checks),
                    weight=2.0,
                    reasoning="Ratio of passing compliance checks",
                ),
                ConfidenceSignal(
                    signal_name="evidence_coverage",
                    signal_value=min(len(verified) / max(len(checks), 1), 1.0),
                    weight=1.0,
                    reasoning="Evidence items per compliance check",
                ),
            ],
            next_actions=next_actions,
            next_recommended_agents=(
                ["expert_knowledge_agent"]
                if any(c.status == "fail" for c in checks)
                else []
            ),
            reasoning_summary=self._build_summary(checks, confidence),
            metadata={
                "compliance_checks": [c.model_dump() for c in checks],
                "pass_rate": self._pass_rate(checks),
                "total_checks": len(checks),
                "passed": sum(1 for c in checks if c.status == "pass"),
                "failed": sum(1 for c in checks if c.status == "fail"),
                "warnings": sum(1 for c in checks if c.status == "warning"),
            },
        )

        self._store_reasoning_output(state, output)

        for claim in claims:
            state.setdefault("claims", [])
            state["claims"].append(claim)

        self.logger.info(
            f"Compliance: {len(checks)} checks, "
            f"pass_rate={self._pass_rate(checks):.2f}, "
            f"confidence={confidence:.2f}"
        )
        return state

    # ------------------------------------------------------------------
    # Deterministic checks
    # ------------------------------------------------------------------

    def _run_all_checks(
        self, evidence: list[EvidenceSource], state: AgentState
    ) -> list[ComplianceCheckResult]:
        """Run all deterministic compliance checks."""
        checks: list[ComplianceCheckResult] = []
        checks.extend(self._check_revisions(evidence))
        checks.extend(self._check_dates(evidence))
        checks.extend(self._check_requirements(evidence))
        checks.extend(self._check_expiry(evidence))
        checks.extend(self._check_workflow(state))
        return checks

    def _check_revisions(
        self, evidence: list[EvidenceSource]
    ) -> list[ComplianceCheckResult]:
        """Check document revision currency."""
        checks: list[ComplianceCheckResult] = []
        seen_docs: dict[str, list[EvidenceSource]] = {}

        for source in evidence:
            doc_id = source.provenance.document_id
            seen_docs.setdefault(doc_id, []).append(source)

        for doc_id, sources in seen_docs.items():
            versions = [s.provenance.document_version for s in sources]
            latest = max(versions)
            is_latest = all(
                s.metadata.get("is_latest_version", True) for s in sources
            )

            status = "pass" if is_latest else "warning"
            if any(v < latest for v in versions):
                status = "fail"

            checks.append(
                ComplianceCheckResult(
                    check_id=f"chk_rev_{uuid.uuid4().hex[:8]}",
                    check_type="revision",
                    status=status,
                    details=(
                        f"Document {doc_id}: latest version is {latest}. "
                        f"Found versions {sorted(set(versions))}. "
                        + ("All sources reference latest version." if is_latest
                           else "Some sources reference older versions.")
                    ),
                    evidence_source_ids=[
                        s.provenance.evidence_region_id for s in sources
                    ],
                    metadata={"document_id": doc_id, "versions": sorted(set(versions))},
                )
            )

        return checks

    def _check_dates(
        self, evidence: list[EvidenceSource]
    ) -> list[ComplianceCheckResult]:
        """Check date-related compliance: recency, validity windows."""
        checks: list[ComplianceCheckResult] = []
        now = datetime.now(UTC)

        for source in evidence:
            ts = source.metadata.get("timestamp") or source.metadata.get("document_date")
            if not ts:
                continue

            try:
                if isinstance(ts, str):
                    doc_date = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if doc_date.tzinfo is None:
                        doc_date = doc_date.replace(tzinfo=UTC)
                elif isinstance(ts, datetime):
                    doc_date = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
                else:
                    continue
            except (ValueError, TypeError):
                continue

            age_days = (now - doc_date).days
            status = "pass"
            if age_days > 365:
                status = "warning"
            if age_days > 730:
                status = "fail"

            checks.append(
                ComplianceCheckResult(
                    check_id=f"chk_date_{uuid.uuid4().hex[:8]}",
                    check_type="date",
                    status=status,
                    details=(
                        f"Evidence from {source.provenance.source_filename} "
                        f"is {age_days} days old (dated {doc_date.date()}). "
                        + ("Within acceptable range." if status == "pass"
                           else f"Exceeds {'warning' if status == 'warning' else 'critical'} age threshold.")
                    ),
                    evidence_source_ids=[source.provenance.evidence_region_id],
                    metadata={
                        "document_date": str(doc_date.date()),
                        "age_days": age_days,
                        "filename": source.provenance.source_filename,
                    },
                )
            )

        return checks

    def _check_requirements(
        self, evidence: list[EvidenceSource]
    ) -> list[ComplianceCheckResult]:
        """Check evidence-to-requirement mapping coverage."""
        checks: list[ComplianceCheckResult] = []

        req_keywords = {
            "iso": "ISO standard compliance",
            "regulation": "Regulatory requirement",
            "standard": "Industry standard",
            "requirement": "General requirement",
            "specification": "Technical specification",
            "sop": "Standard Operating Procedure",
        }

        for keyword, req_name in req_keywords.items():
            matching = [
                s for s in evidence
                if keyword in s.text_excerpt.lower()
            ]

            if matching:
                checks.append(
                    ComplianceCheckResult(
                        check_id=f"chk_req_{uuid.uuid4().hex[:8]}",
                        check_type="requirement",
                        requirement_code=keyword.upper(),
                        status="pass",
                        details=(
                            f"Requirement '{req_name}' has {len(matching)} "
                            f"supporting evidence sources."
                        ),
                        evidence_source_ids=[
                            s.provenance.evidence_region_id for s in matching
                        ],
                    )
                )
            else:
                checks.append(
                    ComplianceCheckResult(
                        check_id=f"chk_req_{uuid.uuid4().hex[:8]}",
                        check_type="requirement",
                        requirement_code=keyword.upper(),
                        status="warning",
                        details=f"No evidence found for requirement '{req_name}'.",
                    )
                )

        return checks

    def _check_expiry(
        self, evidence: list[EvidenceSource]
    ) -> list[ComplianceCheckResult]:
        """Check for expiry-related compliance."""
        checks: list[ComplianceCheckResult] = []
        now = datetime.now(UTC)

        expiry_keywords = ["expires", "expiry", "valid until", "certificate", "permit", "license"]

        for source in evidence:
            text_lower = source.text_excerpt.lower()
            if not any(kw in text_lower for kw in expiry_keywords):
                continue

            expiry_date_str = source.metadata.get("expiry_date")
            status = "pass"
            details = f"Expiry-related evidence found in {source.provenance.source_filename}."

            if expiry_date_str:
                try:
                    if isinstance(expiry_date_str, str):
                        expiry_date = datetime.fromisoformat(expiry_date_str.replace("Z", "+00:00"))
                        if expiry_date.tzinfo is None:
                            expiry_date = expiry_date.replace(tzinfo=UTC)
                    elif isinstance(expiry_date_str, datetime):
                        expiry_date = expiry_date_str if expiry_date_str.tzinfo else expiry_date_str.replace(tzinfo=UTC)
                    else:
                        expiry_date = None

                    if expiry_date:
                        days_until = (expiry_date - now).days
                        if days_until < 0:
                            status = "fail"
                            details = f"EXPIRED: {abs(days_until)} days past expiry ({expiry_date.date()})."
                        elif days_until < 30:
                            status = "warning"
                            details = f"Expiring soon: {days_until} days remaining (expires {expiry_date.date()})."
                        else:
                            details = f"Valid: {days_until} days remaining (expires {expiry_date.date()})."
                except (ValueError, TypeError):
                    details += " Could not parse expiry date from metadata."

            checks.append(
                ComplianceCheckResult(
                    check_id=f"chk_exp_{uuid.uuid4().hex[:8]}",
                    check_type="expiry",
                    status=status,
                    details=details,
                    evidence_source_ids=[source.provenance.evidence_region_id],
                )
            )

        return checks

    def _check_workflow(
        self, state: AgentState
    ) -> list[ComplianceCheckResult]:
        """Check workflow/approval status."""
        checks: list[ComplianceCheckResult] = []
        ctx = state.get("context", {})

        evidence_bundle = ctx.get("evidence_bundle")
        if evidence_bundle is None:
            checks.append(
                ComplianceCheckResult(
                    check_id=f"chk_wf_{uuid.uuid4().hex[:8]}",
                    check_type="workflow",
                    status="warning",
                    details="No evidence bundle available for workflow verification.",
                )
            )
            return checks

        verified = evidence_bundle.verified_evidence
        human_reviewed = [
            s for s in verified if s.verification_status == "human_reviewed"
        ]
        provenance_validated = [
            s for s in verified if s.verification_status == "provenance_validated"
        ]

        if human_reviewed:
            checks.append(
                ComplianceCheckResult(
                    check_id=f"chk_wf_{uuid.uuid4().hex[:8]}",
                    check_type="workflow",
                    status="pass",
                    details=(
                        f"{len(human_reviewed)} evidence items have been human-reviewed. "
                        "Workflow approval chain verified."
                    ),
                    evidence_source_ids=[
                        s.provenance.evidence_region_id for s in human_reviewed
                    ],
                )
            )

        if provenance_validated:
            checks.append(
                ComplianceCheckResult(
                    check_id=f"chk_wf_{uuid.uuid4().hex[:8]}",
                    check_type="workflow",
                    status="pass",
                    details=(
                        f"{len(provenance_validated)} evidence items have provenance validated."
                    ),
                    evidence_source_ids=[
                        s.provenance.evidence_region_id for s in provenance_validated
                    ],
                )
            )

        unverified = [
            s for s in verified
            if s.verification_status in ("unverified", "stale")
        ]
        if unverified:
            checks.append(
                ComplianceCheckResult(
                    check_id=f"chk_wf_{uuid.uuid4().hex[:8]}",
                    check_type="workflow",
                    status="warning",
                    details=(
                        f"{len(unverified)} evidence items lack proper workflow verification."
                    ),
                    evidence_source_ids=[
                        s.provenance.evidence_region_id for s in unverified
                    ],
                )
            )

        return checks

    # ------------------------------------------------------------------
    # Claims from checks
    # ------------------------------------------------------------------

    def _build_claims(
        self, checks: list[ComplianceCheckResult]
    ) -> list[GroundedClaim]:
        claims: list[GroundedClaim] = []

        pass_count = sum(1 for c in checks if c.status == "pass")
        fail_count = sum(1 for c in checks if c.status == "fail")
        warn_count = sum(1 for c in checks if c.status == "warning")

        if pass_count > 0:
            claims.append(
                GroundedClaim(
                    claim_id=f"claim_{uuid.uuid4().hex[:8]}",
                    text=f"{pass_count} of {len(checks)} compliance checks passed",
                    status=ClaimSupportStatus.SUPPORTED,
                    reasoning=f"Pass rate: {pass_count}/{len(checks)} ({self._pass_rate(checks):.0%})",
                )
            )

        if fail_count > 0:
            claims.append(
                GroundedClaim(
                    claim_id=f"claim_{uuid.uuid4().hex[:8]}",
                    text=f"{fail_count} compliance checks FAILED",
                    status=ClaimSupportStatus.REFUTED,
                    reasoning="Failed checks require remediation",
                )
            )

        if warn_count > 0:
            claims.append(
                GroundedClaim(
                    claim_id=f"claim_{uuid.uuid4().hex[:8]}",
                    text=f"{warn_count} compliance checks have warnings",
                    status=ClaimSupportStatus.PARTIALLY_SUPPORTED,
                    reasoning="Warnings indicate areas needing attention",
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
        self, checks: list[ComplianceCheckResult]
    ) -> float:
        if not checks:
            return 0.0
        return round(self._pass_rate(checks), 3)

    def _pass_rate(self, checks: list[ComplianceCheckResult]) -> float:
        if not checks:
            return 0.0
        passed = sum(1 for c in checks if c.status == "pass")
        return passed / len(checks)

    # ------------------------------------------------------------------
    # Missing evidence
    # ------------------------------------------------------------------

    def _identify_missing(
        self,
        checks: list[ComplianceCheckResult],
        evidence: list[EvidenceSource],
    ) -> list[MissingEvidence]:
        missing: list[MissingEvidence] = []

        warning_checks = [c for c in checks if c.status == "warning"]
        for check in warning_checks:
            missing.append(
                MissingEvidence(
                    evidence_type=f"compliance_{check.check_type}",
                    description=check.details,
                    suggested_action=f"Provide additional evidence for {check.check_type} check",
                    priority="medium",
                )
            )

        return missing

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _build_actions(
        self, checks: list[ComplianceCheckResult]
    ) -> list[RecommendedAction]:
        actions: list[RecommendedAction] = []

        failed = [c for c in checks if c.status == "fail"]
        for check in failed:
            actions.append(
                RecommendedAction(
                    action_id=f"act_{uuid.uuid4().hex[:8]}",
                    type="PROCEDURE_UPDATE",
                    description=f"Remediate failed {check.check_type} check: {check.details[:120]}",
                    priority="high",
                    reasoning=f"Compliance check {check.check_type} failed",
                )
            )

        warnings = [c for c in checks if c.status == "warning"]
        for check in warnings[:3]:
            actions.append(
                RecommendedAction(
                    action_id=f"act_{uuid.uuid4().hex[:8]}",
                    type="MONITOR",
                    description=f"Review {check.check_type} warning: {check.details[:120]}",
                    priority="medium",
                    reasoning=f"Compliance check {check.check_type} has warnings",
                )
            )

        return actions

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------

    def _decide(
        self, checks: list[ComplianceCheckResult], confidence: float
    ) -> ReasoningDecision:
        failed = sum(1 for c in checks if c.status == "fail")
        if failed > 0:
            return ReasoningDecision.NEEDS_HUMAN_REVIEW
        if confidence < 0.5:
            return ReasoningDecision.REQUEST_EVIDENCE
        return ReasoningDecision.SUFFICIENT

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _build_summary(
        self, checks: list[ComplianceCheckResult], confidence: float
    ) -> str:
        passed = sum(1 for c in checks if c.status == "pass")
        failed = sum(1 for c in checks if c.status == "fail")
        warnings = sum(1 for c in checks if c.status == "warning")
        parts = [
            f"Ran {len(checks)} compliance checks.",
            f"Passed: {passed}, Failed: {failed}, Warnings: {warnings}.",
            f"Pass rate: {confidence:.0%}.",
        ]
        if failed > 0:
            parts.append(f"{failed} checks require remediation.")
        if not checks:
            parts.append("No compliance checks could be performed.")
        return " ".join(parts)
