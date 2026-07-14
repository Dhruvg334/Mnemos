from typing import Any, Dict, List, Optional
from mnemos.agentic.schemas.base import EvidenceSource, GroundedClaim, ClaimSupportStatus, VerificationStatus
from mnemos.agentic.utils.exceptions import AgenticError

class GuardrailViolation(AgenticError):
    """Raised when a safety or grounding guardrail is violated."""
    pass

class MnemosGuardrails:
    """
    Industrial-grade guardrails for the Mnemos AI layer.
    """

    @staticmethod
    def verify_grounding(claims: List[GroundedClaim]) -> None:
        """
        Prevents unsupported claims.
        Every 'SUPPORTED' claim must have at least one verified evidence source.
        """
        for claim in claims:
            if claim.status == ClaimSupportStatus.SUPPORTED:
                if not claim.sources:
                    raise GuardrailViolation(f"Claim '{claim.text}' marked as SUPPORTED but has no evidence sources.")

                # Ensure all sources are at least provenance validated
                for source in claim.sources:
                    if source.verification_status == VerificationStatus.UNVERIFIED:
                        raise GuardrailViolation(f"Claim '{claim.text}' relies on unverified evidence.")

    @staticmethod
    def check_sop_version(procedure: Dict[str, Any], latest_version: int) -> None:
        """
        Prevents outdated SOP usage.
        """
        if procedure.get("version", 0) < latest_version:
            raise GuardrailViolation(
                f"Attempting to use outdated SOP version {procedure.get('version')}. "
                f"Latest approved version is {latest_version}."
            )

    @staticmethod
    def validate_compliance_evidence(requirement_id: str, evidence: List[EvidenceSource]) -> None:
        """
        Prevents compliance claims without evidence.
        """
        if not evidence:
            raise GuardrailViolation(f"Compliance verification for {requirement_id} failed: No evidence found.")

    @staticmethod
    def check_permissions(user_context: Dict[str, Any], evidence: List[EvidenceSource]) -> None:
        """
        Prevents site/org permission violations.
        """
        user_site_id = user_context.get("site_id")
        user_org_id = user_context.get("org_id")

        for source in evidence:
            source_site_id = source.metadata.get("site_id")
            source_org_id = source.metadata.get("org_id")

            if source_org_id and source_org_id != user_org_id:
                raise GuardrailViolation("Security violation: Evidence belongs to a different organisation.")

            if source_site_id and source_site_id != user_site_id:
                raise GuardrailViolation("Security violation: Evidence belongs to a different site.")

    @staticmethod
    def detect_injection(query: str) -> None:
        """
        Prevents prompt injection attacks.
        """
        injection_keywords = [
            "ignore all previous", "system prompt", "developer mode",
            "dan mode", "output as json only", "you are now a"
        ]
        if any(k in query.lower() for k in injection_keywords):
            raise GuardrailViolation("Potential prompt injection detected in user query.")
