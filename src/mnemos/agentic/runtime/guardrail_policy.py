"""Explicit guardrail policy model (P0 #16).

Every policy check produces one of five outcomes:
- ALLOW           : proceed without any restriction
- ALLOW_WITH_WARNING : proceed but record an operator-facing warning in the audit log
- REQUIRE_HUMAN_APPROVAL : pause execution and route to the human approval gate
- ABSTAIN         : the agent should not produce an answer for this query
- BLOCK           : reject the request immediately

Policy decisions are auditable: every decision is written to the
runtime audit log with the policy name, outcome, and reason.

Policies implemented:
1.  prompt_injection          — detect injection in user queries and tool args
2.  indirect_injection        — detect injection embedded in retrieved documents
3.  tenant_site_leakage       — cross-tenant or cross-site evidence reference
4.  obsolete_evidence         — evidence from superseded/archived documents
5.  restricted_document       — document classified above the user's clearance
6.  unsupported_claim         — SUPPORTED claim with no verified evidence sources
7.  missing_citation          — answer references facts with no citation
8.  unsafe_operational_recommendation — critical action without approval
9.  autonomous_control        — instruction that would give the agent direct control
10. compliance_overclaim      — compliance assertion without regulatory evidence
11. sensitive_data_exposure   — PII or secret detected in output
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Outcome enum
# ---------------------------------------------------------------------------


class PolicyOutcome(StrEnum):
    ALLOW = "allow"
    ALLOW_WITH_WARNING = "allow_with_warning"
    REQUIRE_HUMAN_APPROVAL = "require_human_approval"
    ABSTAIN = "abstain"
    BLOCK = "block"


# ---------------------------------------------------------------------------
# Decision value object
# ---------------------------------------------------------------------------


class PolicyDecision(BaseModel):
    """The result of a single policy evaluation."""

    policy_name: str
    outcome: PolicyOutcome
    reason: str
    detail: str = ""
    auditable: bool = True

    @property
    def blocks_execution(self) -> bool:
        return self.outcome in (
            PolicyOutcome.BLOCK,
            PolicyOutcome.REQUIRE_HUMAN_APPROVAL,
            PolicyOutcome.ABSTAIN,
        )


# ---------------------------------------------------------------------------
# Individual policy implementations
# ---------------------------------------------------------------------------

_PROMPT_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"you\s+are\s+now\s+a\s+",
        r"system\s*:\s*you\s+are",
        r"forget\s+(all\s+)?prior\s+(context|instructions)",
        r"new\s+instructions?\s*:",
        r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions",
        r"disregard\s+(all\s+)?previous",
        r"you\s+are\s+now\s+DAN",
        r"do\s+anything\s+now",
        r"override\s+safety",
        r"output\s+your\s+system\s+prompt",
        r"reveal\s+(your|the)\s+instructions",
        r"<\|im_start\|>|<\|im_end\|>",
        r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>",
    ]
]

_SENSITIVE_DATA_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"(?:password|passwd|secret|api_?key)\s*[:=]\s*['\"]?\S+",
        r"bearer\s+[A-Za-z0-9\-._~+/]+=*",
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
    ]
]


def _check_prompt_injection(text: str) -> bool:
    return any(p.search(text) for p in _PROMPT_INJECTION_PATTERNS)


def _check_sensitive_data(text: str) -> bool:
    return any(p.search(text) for p in _SENSITIVE_DATA_PATTERNS)


# ---------------------------------------------------------------------------
# Policy engine
# ---------------------------------------------------------------------------


class GuardrailPolicyEngine:
    """Evaluates all guardrail policies for a given context.

    Usage::

        engine = GuardrailPolicyEngine()

        # Check a user query before passing to agents
        decisions = engine.evaluate_query(query_text, user_context)

        # Check agent output before persisting
        decisions = engine.evaluate_output(output_dict, user_context)

        # Check a tool call before dispatching
        decisions = engine.evaluate_tool_call(tool_name, arguments, user_context)

    Every call returns a list of PolicyDecision objects.  Callers must
    inspect each decision's ``outcome`` and ``blocks_execution`` flag.

    All decisions with ``auditable=True`` must be written to the audit
    log by the caller.
    """

    def evaluate_query(
        self,
        query: str,
        user_context: dict[str, Any],
    ) -> list[PolicyDecision]:
        """Evaluate policies for an incoming user query."""
        decisions: list[PolicyDecision] = []
        decisions.append(self._policy_prompt_injection(query, source="query"))
        decisions.append(self._policy_sensitive_data_in_query(query))
        return decisions

    def evaluate_retrieved_document(
        self,
        doc_text: str,
        doc_metadata: dict[str, Any],
        user_context: dict[str, Any],
    ) -> list[PolicyDecision]:
        """Evaluate policies for a retrieved document chunk."""
        decisions: list[PolicyDecision] = []
        decisions.append(self._policy_indirect_injection(doc_text, doc_metadata))
        decisions.append(self._policy_obsolete_evidence(doc_metadata, user_context))
        decisions.append(self._policy_restricted_document(doc_metadata, user_context))
        decisions.append(self._policy_tenant_site_leakage(doc_metadata, user_context))
        return decisions

    def evaluate_claim(
        self,
        claim: dict[str, Any],
        user_context: dict[str, Any],
    ) -> list[PolicyDecision]:
        """Evaluate policies for a grounded claim before persistence."""
        decisions: list[PolicyDecision] = []
        decisions.append(self._policy_unsupported_claim(claim))
        decisions.append(self._policy_missing_citation(claim))
        decisions.append(self._policy_compliance_overclaim(claim))
        return decisions

    def evaluate_recommended_action(
        self,
        action: dict[str, Any],
        user_context: dict[str, Any],
    ) -> list[PolicyDecision]:
        """Evaluate policies for a recommended operational action."""
        decisions: list[PolicyDecision] = []
        decisions.append(self._policy_unsafe_operational(action))
        decisions.append(self._policy_autonomous_control(action))
        return decisions

    def evaluate_output(
        self,
        output: dict[str, Any],
        user_context: dict[str, Any],
    ) -> list[PolicyDecision]:
        """Evaluate policies for a final agent output."""
        decisions: list[PolicyDecision] = []
        output_str = str(output)
        decisions.append(self._policy_sensitive_data_in_output(output_str))
        return decisions

    def evaluate_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        user_context: dict[str, Any],
    ) -> list[PolicyDecision]:
        """Evaluate policies for a tool call before dispatch."""
        decisions: list[PolicyDecision] = []
        args_str = str(arguments)
        decisions.append(self._policy_prompt_injection(args_str, source=f"tool:{tool_name}"))
        decisions.append(self._policy_tenant_site_leakage(arguments, user_context))
        return decisions

    # ------------------------------------------------------------------
    # Individual policy methods
    # ------------------------------------------------------------------

    @staticmethod
    def _policy_prompt_injection(text: str, source: str = "input") -> PolicyDecision:
        if _check_prompt_injection(text):
            return PolicyDecision(
                policy_name="prompt_injection",
                outcome=PolicyOutcome.BLOCK,
                reason="Prompt injection pattern detected",
                detail=f"Source: {source}",
            )
        return PolicyDecision(
            policy_name="prompt_injection",
            outcome=PolicyOutcome.ALLOW,
            reason="No injection patterns detected",
            auditable=False,
        )

    @staticmethod
    def _policy_indirect_injection(doc_text: str, doc_metadata: dict[str, Any]) -> PolicyDecision:
        if _check_prompt_injection(doc_text):
            doc_id = doc_metadata.get("document_id", "unknown")
            return PolicyDecision(
                policy_name="indirect_injection",
                outcome=PolicyOutcome.BLOCK,
                reason="Prompt injection pattern found in retrieved document",
                detail=f"Document: {doc_id}",
            )
        return PolicyDecision(
            policy_name="indirect_injection",
            outcome=PolicyOutcome.ALLOW,
            reason="Document clean",
            auditable=False,
        )

    @staticmethod
    def _policy_tenant_site_leakage(
        data: dict[str, Any], user_context: dict[str, Any]
    ) -> PolicyDecision:
        user_org = user_context.get("org_id") or user_context.get("organisation_id")
        user_site = user_context.get("site_id")
        data_org = data.get("organisation_id") or data.get("org_id")
        data_site = data.get("site_id")

        if user_org and data_org and data_org != user_org:
            return PolicyDecision(
                policy_name="tenant_site_leakage",
                outcome=PolicyOutcome.BLOCK,
                reason="Cross-tenant data access attempt",
                detail=(f"User org={user_org}, data org={data_org}"),
            )
        if user_site and data_site and data_site != user_site:
            return PolicyDecision(
                policy_name="tenant_site_leakage",
                outcome=PolicyOutcome.BLOCK,
                reason="Cross-site data access attempt",
                detail=f"User site={user_site}, data site={data_site}",
            )
        return PolicyDecision(
            policy_name="tenant_site_leakage",
            outcome=PolicyOutcome.ALLOW,
            reason="Scope within tenant boundary",
            auditable=False,
        )

    @staticmethod
    def _policy_obsolete_evidence(
        doc_metadata: dict[str, Any], user_context: dict[str, Any]
    ) -> PolicyDecision:
        status = doc_metadata.get("status", "")
        if status in ("superseded", "archived", "rejected"):
            return PolicyDecision(
                policy_name="obsolete_evidence",
                outcome=PolicyOutcome.ALLOW_WITH_WARNING,
                reason=f"Document has status '{status}' — evidence may be outdated",
                detail=f"Document: {doc_metadata.get('document_id', 'unknown')}",
            )
        return PolicyDecision(
            policy_name="obsolete_evidence",
            outcome=PolicyOutcome.ALLOW,
            reason="Document is current",
            auditable=False,
        )

    @staticmethod
    def _policy_restricted_document(
        doc_metadata: dict[str, Any], user_context: dict[str, Any]
    ) -> PolicyDecision:
        doc_classification = doc_metadata.get("classification", "internal")
        user_classifications = user_context.get("access_classifications", ["internal"])

        _classification_levels = {
            "public": 0,
            "internal": 1,
            "confidential": 2,
            "restricted": 3,
            "secret": 4,
        }
        doc_level = _classification_levels.get(str(doc_classification).lower(), 1)
        user_level = (
            max(_classification_levels.get(str(c).lower(), 0) for c in user_classifications)
            if user_classifications
            else 0
        )

        if doc_level > user_level:
            return PolicyDecision(
                policy_name="restricted_document",
                outcome=PolicyOutcome.BLOCK,
                reason=(f"Document classification '{doc_classification}' exceeds user clearance"),
                detail=f"Document: {doc_metadata.get('document_id', 'unknown')}",
            )
        return PolicyDecision(
            policy_name="restricted_document",
            outcome=PolicyOutcome.ALLOW,
            reason="User has sufficient clearance",
            auditable=False,
        )

    @staticmethod
    def _policy_unsupported_claim(claim: dict[str, Any]) -> PolicyDecision:
        status = claim.get("support_status") or claim.get("status", "")
        sources = claim.get("sources", []) or claim.get("citation_ids", [])

        if status == "supported" and not sources:
            return PolicyDecision(
                policy_name="unsupported_claim",
                outcome=PolicyOutcome.ABSTAIN,
                reason="Claim marked SUPPORTED but has no evidence sources",
                detail=f"Claim: {str(claim.get('text', ''))[:100]}",
            )
        return PolicyDecision(
            policy_name="unsupported_claim",
            outcome=PolicyOutcome.ALLOW,
            reason="Claim has adequate support",
            auditable=False,
        )

    @staticmethod
    def _policy_missing_citation(claim: dict[str, Any]) -> PolicyDecision:
        citation_ids = claim.get("citation_ids", [])
        status = claim.get("support_status") or claim.get("status", "")

        if status in ("supported", "partially_supported") and not citation_ids:
            return PolicyDecision(
                policy_name="missing_citation",
                outcome=PolicyOutcome.ALLOW_WITH_WARNING,
                reason="Claim asserts support but has no citation IDs",
                detail=f"Claim: {str(claim.get('text', ''))[:100]}",
            )
        return PolicyDecision(
            policy_name="missing_citation",
            outcome=PolicyOutcome.ALLOW,
            reason="Citations present",
            auditable=False,
        )

    @staticmethod
    def _policy_unsafe_operational(action: dict[str, Any]) -> PolicyDecision:
        action_type = action.get("action_type", "")
        priority = action.get("priority", "medium")

        if priority in ("high", "critical") and action_type in (
            "REPAIR",
            "PROCEDURE_UPDATE",
            "SHUTDOWN",
            "BYPASS",
        ):
            return PolicyDecision(
                policy_name="unsafe_operational_recommendation",
                outcome=PolicyOutcome.REQUIRE_HUMAN_APPROVAL,
                reason=(f"High-priority {action_type} action requires human approval"),
                detail=f"Priority={priority}, Type={action_type}",
            )
        return PolicyDecision(
            policy_name="unsafe_operational_recommendation",
            outcome=PolicyOutcome.ALLOW,
            reason="Action within safe bounds",
            auditable=False,
        )

    @staticmethod
    def _policy_autonomous_control(action: dict[str, Any]) -> PolicyDecision:
        autonomous_keywords = [
            "execute automatically",
            "no human needed",
            "bypass approval",
            "self-execute",
            "autonomous action",
            "override safety",
        ]
        description = str(action.get("description", "")).lower()
        reasoning = str(action.get("reasoning", "")).lower()
        combined = description + " " + reasoning

        if any(kw in combined for kw in autonomous_keywords):
            return PolicyDecision(
                policy_name="autonomous_control",
                outcome=PolicyOutcome.BLOCK,
                reason="Autonomous control instruction detected — blocked",
                detail="Agent may not instruct autonomous execution of physical actions",
            )
        return PolicyDecision(
            policy_name="autonomous_control",
            outcome=PolicyOutcome.ALLOW,
            reason="No autonomous control instruction",
            auditable=False,
        )

    @staticmethod
    def _policy_compliance_overclaim(claim: dict[str, Any]) -> PolicyDecision:
        text = str(claim.get("text", "")).lower()
        overclaim_phrases = [
            "fully compliant",
            "completely meets all",
            "satisfies all requirements",
            "zero compliance gaps",
            "100% compliant",
        ]
        if any(phrase in text for phrase in overclaim_phrases):
            sources = claim.get("sources", []) or claim.get("citation_ids", [])
            if not sources:
                return PolicyDecision(
                    policy_name="compliance_overclaim",
                    outcome=PolicyOutcome.ABSTAIN,
                    reason="Absolute compliance assertion without regulatory evidence",
                    detail=f"Claim: {text[:100]}",
                )
        return PolicyDecision(
            policy_name="compliance_overclaim",
            outcome=PolicyOutcome.ALLOW,
            reason="Compliance claim is appropriately qualified",
            auditable=False,
        )

    @staticmethod
    def _policy_sensitive_data_in_query(query: str) -> PolicyDecision:
        if _check_sensitive_data(query):
            return PolicyDecision(
                policy_name="sensitive_data_exposure",
                outcome=PolicyOutcome.ALLOW_WITH_WARNING,
                reason="Query contains potentially sensitive data (PII/credentials)",
                detail="Query was not blocked but sensitive content was detected",
            )
        return PolicyDecision(
            policy_name="sensitive_data_exposure",
            outcome=PolicyOutcome.ALLOW,
            reason="No sensitive data detected in query",
            auditable=False,
        )

    @staticmethod
    def _policy_sensitive_data_in_output(output_str: str) -> PolicyDecision:
        if _check_sensitive_data(output_str):
            return PolicyDecision(
                policy_name="sensitive_data_exposure",
                outcome=PolicyOutcome.BLOCK,
                reason="Sensitive data (PII/credentials) detected in agent output",
                detail="Output blocked to prevent data leakage",
            )
        return PolicyDecision(
            policy_name="sensitive_data_exposure",
            outcome=PolicyOutcome.ALLOW,
            reason="Output clean",
            auditable=False,
        )
