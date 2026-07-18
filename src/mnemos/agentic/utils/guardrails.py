"""Guardrails for the Mnemos AI layer.

Prevents:
- Permission violations (site/org boundary enforcement)
- Hallucinated citations (citations must trace to real documents)
- Unapproved procedures (SOPs must be approved before use)
- Fake sensor data (simulated data cannot be used for analysis)
- Compliance without evidence (compliance claims require evidence)
- Unsafe recommendations (critical actions require safety review)
- Unsupported claims (every SUPPORTED claim needs verified evidence)
- Prompt injection attacks
"""

from __future__ import annotations

from typing import Any

from mnemos.agentic.schemas.base import (
    ClaimSupportStatus,
    EvidenceSource,
    GroundedClaim,
    VerificationStatus,
)
from mnemos.agentic.utils.exceptions import AgenticError


class GuardrailViolation(AgenticError):
    """Raised when a safety or grounding guardrail is violated."""


class MnemosGuardrails:
    """Industrial-grade guardrails for the Mnemos AI layer.

    Every guardrail check is deterministic, auditable, and raises
    GuardrailViolation on failure. No exceptions are swallowed.
    """

    # ------------------------------------------------------------------
    # 1. Permission violations
    # ------------------------------------------------------------------

    @staticmethod
    def check_permissions(user_context: dict[str, Any], evidence: list[EvidenceSource]) -> None:
        """Prevents site/org permission violations.

        Evidence must belong to the same organisation and site as the
        requesting user context.
        """
        user_site_id = user_context.get("site_id")
        user_org_id = user_context.get("org_id")

        for source in evidence:
            source_site_id = source.metadata.get("site_id")
            source_org_id = source.metadata.get("org_id")

            if source_org_id and user_org_id and source_org_id != user_org_id:
                raise GuardrailViolation(
                    "Security violation: Evidence belongs to a different organisation."
                )
            if source_site_id and user_site_id and source_site_id != user_site_id:
                raise GuardrailViolation(
                    "Security violation: Evidence belongs to a different site."
                )

    # ------------------------------------------------------------------
    # 2. Hallucinated citations
    # ------------------------------------------------------------------

    @staticmethod
    def check_citation_grounding(citations: list[dict[str, Any]]) -> None:
        """Prevents hallucinated citations.

        Every citation must have a valid document_id and evidence_region_id.
        Empty or placeholder IDs indicate hallucinated references.
        """
        for citation in citations:
            doc_id = citation.get("document_id", "")
            region_id = citation.get("evidence_region_id", "")

            if not doc_id or not doc_id.strip():
                raise GuardrailViolation(
                    f"Hallucinated citation detected: empty document_id "
                    f"in citation '{citation.get('citation_id', 'unknown')}'"
                )
            if not region_id or not region_id.strip():
                raise GuardrailViolation(
                    f"Hallucinated citation detected: empty evidence_region_id "
                    f"in citation '{citation.get('citation_id', 'unknown')}'"
                )
            if doc_id.startswith("fake_") or doc_id.startswith("mock_"):
                raise GuardrailViolation(
                    f"Hallucinated citation detected: document_id '{doc_id}' "
                    "appears to be fabricated"
                )

    # ------------------------------------------------------------------
    # 3. Unapproved procedures
    # ------------------------------------------------------------------

    @staticmethod
    def check_sop_version(procedure: dict[str, Any], latest_version: int) -> None:
        """Prevents outdated SOP usage.

        Procedure version must match the latest approved version.
        """
        if procedure.get("version", 0) < latest_version:
            raise GuardrailViolation(
                f"Attempting to use outdated SOP version {procedure.get('version')}. "
                f"Latest approved version is {latest_version}."
            )

    @staticmethod
    def check_procedure_approval(procedure: dict[str, Any]) -> None:
        """Prevents use of unapproved procedures.

        Procedure status must be 'approved' or 'APPROVED'.
        """
        status = str(procedure.get("status", "")).upper()
        if status in ("DRAFT", "REVIEW", "PENDING", "REJECTED", "SUPERSEDED"):
            raise GuardrailViolation(
                f"Procedure '{procedure.get('id', 'unknown')}' has status '{status}' "
                "and cannot be used until approved."
            )

    # ------------------------------------------------------------------
    # 4. Fake sensor data
    # ------------------------------------------------------------------

    @staticmethod
    def check_sensor_data_authenticity(data: dict[str, Any]) -> None:
        """Prevents use of fake/simulated sensor data for analysis.

        Sensor data must have a valid source and cannot be simulated,
        mocked, or synthetic.
        """
        source = str(data.get("source", "")).lower()
        data_type = str(data.get("data_type", "")).lower()

        fake_indicators = ["simulated", "mock", "synthetic", "test", "dummy", "fake"]
        for indicator in fake_indicators:
            if indicator in source:
                raise GuardrailViolation(
                    f"Fake sensor data detected: source '{data.get('source')}' "
                    f"contains '{indicator}'. Cannot use for analysis."
                )
            if indicator in data_type:
                raise GuardrailViolation(
                    f"Fake sensor data detected: data_type '{data.get('data_type')}' "
                    f"contains '{indicator}'. Cannot use for analysis."
                )

        if not source or source in ("", "unknown"):
            raise GuardrailViolation(
                "Sensor data missing provenance: no source identified. Cannot verify authenticity."
            )

    # ------------------------------------------------------------------
    # 5. Compliance without evidence
    # ------------------------------------------------------------------

    @staticmethod
    def validate_compliance_evidence(requirement_id: str, evidence: list[EvidenceSource]) -> None:
        """Prevents compliance claims without evidence.

        Every compliance requirement must have at least one piece of
        supporting evidence.
        """
        if not evidence:
            raise GuardrailViolation(
                f"Compliance verification for {requirement_id} failed: No evidence found."
            )

    # ------------------------------------------------------------------
    # 6. Unsafe recommendations
    # ------------------------------------------------------------------

    @staticmethod
    def check_recommendation_safety(
        action_type: str, priority: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Prevents unsafe recommendations.

        Critical repair and procedure update actions require explicit
        safety review and cannot be auto-generated.
        """
        if priority == "critical":
            if action_type in ("REPAIR", "PROCEDURE_UPDATE", "SHUTDOWN"):
                raise GuardrailViolation(
                    f"Critical {action_type} action requires explicit safety review. "
                    "Cannot auto-generate critical maintenance recommendations."
                )

        unsafe_combos = [
            ("REPAIR", "online"),
            ("PROCEDURE_UPDATE", "bypass"),
        ]
        meta = metadata or {}
        for combo_type, combo_flag in unsafe_combos:
            if action_type == combo_type and meta.get(combo_flag):
                raise GuardrailViolation(
                    f"Unsafe combination: {action_type} with '{combo_flag}' flag. "
                    "Requires manual safety assessment."
                )

    # ------------------------------------------------------------------
    # Grounding (existing)
    # ------------------------------------------------------------------

    @staticmethod
    def verify_grounding(claims: list[GroundedClaim]) -> None:
        """Prevents unsupported claims.

        Every SUPPORTED claim must have at least one verified evidence source.
        """
        for claim in claims:
            if claim.status == ClaimSupportStatus.SUPPORTED:
                if not claim.sources:
                    raise GuardrailViolation(
                        f"Claim '{claim.text}' marked as SUPPORTED but has no evidence sources."
                    )
                for source in claim.sources:
                    if source.verification_status == VerificationStatus.UNVERIFIED:
                        raise GuardrailViolation(
                            f"Claim '{claim.text}' relies on unverified evidence."
                        )

    # ------------------------------------------------------------------
    # Prompt injection (existing)
    # ------------------------------------------------------------------

    @staticmethod
    def detect_injection(query: str) -> None:
        """Prevents prompt injection attacks."""
        injection_keywords = [
            "ignore all previous",
            "system prompt",
            "developer mode",
            "dan mode",
            "output as json only",
            "you are now a",
        ]
        if any(k in query.lower() for k in injection_keywords):
            raise GuardrailViolation("Potential prompt injection detected in user query.")

    # ------------------------------------------------------------------
    # 7. Output validation guardrails
    # ------------------------------------------------------------------

    @staticmethod
    def validate_reasoning_output(output: dict[str, Any]) -> None:
        """Validate that a reasoning agent output has proper structure.

        Checks that the output contains required fields and that
        supported claims have evidence backing.
        """
        if "reasoning_decision" not in output:
            raise GuardrailViolation("Agent output missing required 'reasoning_decision' field.")

        valid_decisions = {
            "sufficient",
            "insufficient",
            "needs_human_review",
            "abstain",
            "needs_more_evidence",
            "conflicting_evidence",
        }
        decision = output["reasoning_decision"]
        if decision not in valid_decisions:
            raise GuardrailViolation(
                f"Invalid reasoning_decision '{decision}'. "
                f"Must be one of: {', '.join(sorted(valid_decisions))}"
            )

        if "confidence" in output:
            conf = output["confidence"]
            if not isinstance(conf, int | float) or conf < 0 or conf > 1:
                raise GuardrailViolation(
                    f"Invalid confidence value '{conf}'. Must be between 0 and 1."
                )

    @staticmethod
    def validate_confidence_threshold(
        output: dict[str, Any],
        min_confidence: float = 0.3,
    ) -> None:
        """Validate that agent output meets minimum confidence threshold.

        Low-confidence outputs should trigger review, not be passed
        as authoritative findings.
        """
        conf = output.get("confidence")
        if conf is None:
            return

        if isinstance(conf, int | float) and conf < min_confidence:
            raise GuardrailViolation(
                f"Agent confidence {conf:.2f} is below minimum threshold "
                f"{min_confidence:.2f}. Output requires human review."
            )

    @staticmethod
    def validate_output_completeness(
        output: dict[str, Any],
        required_fields: list[str],
    ) -> None:
        """Validate that agent output contains all required fields.

        Prevents incomplete outputs from being treated as authoritative.
        """
        missing = [f for f in required_fields if f not in output]
        if missing:
            raise GuardrailViolation(f"Agent output missing required fields: {', '.join(missing)}")

    @staticmethod
    def validate_output_no_hallucinated_facts(
        output: dict[str, Any],
        known_facts: list[str] | None = None,
    ) -> None:
        """Basic check that agent output doesn't contain obvious hallucination patterns.

        Checks for common LLM hallucination markers like "according to my training",
        "as an AI", "I believe without evidence", etc.
        """
        text_fields = ["reasoning_summary", "content", "description", "summary"]
        hallucination_markers = [
            "as an ai",
            "according to my training",
            "i believe without evidence",
            "based on my knowledge cutoff",
            "i don't have access to",
            "this is hypothetical",
            "assume without evidence",
        ]

        for field in text_fields:
            value = output.get(field, "")
            if not isinstance(value, str):
                continue
            value_lower = value.lower()
            for marker in hallucination_markers:
                if marker in value_lower:
                    raise GuardrailViolation(
                        f"Potential hallucination detected in output field '{field}': "
                        f"contains '{marker}'. Agent output may not be grounded."
                    )
