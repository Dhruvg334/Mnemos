"""Human Approval Gates for the multi-agent runtime.

Implements 6 mandatory approval gates where the supervisor must
pause the investigation and wait for human review:

1. RCA_CLOSURE - RCA findings must be approved before closure
2. COMPLIANCE_CLOSURE - compliance failures must be reviewed
3. KNOWLEDGE_PUBLICATION - knowledge cards must be reviewed
4. MAINTENANCE_STRATEGY - maintenance recommendations need approval
5. AUDIT_EXPORT - audit reports need approval
6. HIGH_PRIORITY_ACTION - high-priority actions need approval

Every approval gate is recorded in the audit log.
"""

from __future__ import annotations

from typing import Any

from mnemos.agentic.runtime.audit import AuditLogger
from mnemos.agentic.runtime.types import (
    ApprovalRequest,
    InvestigationPhase,
)
from mnemos.agentic.schemas.base import (
    ApprovalGateRequest,
    ApprovalGateType,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("runtime.approval")


# Gate configuration: which agent actions trigger which gates
_GATE_TRIGGERS: dict[str, ApprovalGateType] = {
    "rca_closure": ApprovalGateType.RCA_CLOSURE,
    "compliance_closure": ApprovalGateType.COMPLIANCE_CLOSURE,
    "knowledge_publication": ApprovalGateType.KNOWLEDGE_PUBLICATION,
    "maintenance_strategy": ApprovalGateType.MAINTENANCE_STRATEGY,
    "audit_export": ApprovalGateType.AUDIT_EXPORT,
    "high_priority_action": ApprovalGateType.HIGH_PRIORITY_ACTION,
}

# Which reasoning decisions trigger mandatory gates
_DECISION_GATES: dict[str, ApprovalGateType] = {
    "rca_closure": ApprovalGateType.RCA_CLOSURE,
    "compliance_failure": ApprovalGateType.COMPLIANCE_CLOSURE,
    "knowledge_submit": ApprovalGateType.KNOWLEDGE_PUBLICATION,
    "maintenance_critical": ApprovalGateType.MAINTENANCE_STRATEGY,
    "audit_export": ApprovalGateType.AUDIT_EXPORT,
    "high_priority": ApprovalGateType.HIGH_PRIORITY_ACTION,
}


class HumanApprovalNode:
    """Manages human-in-the-loop approval checkpoints.

    When an investigation hits a mandatory approval gate, the node:
    1. Pauses the investigation
    2. Records what needs approval in the audit log
    3. Creates a structured approval request
    4. Processes the human response
    5. Updates the investigation state accordingly
    6. Records the decision in the audit log
    """

    def __init__(
        self,
        auto_approve_timeout_seconds: float = 600.0,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self.auto_approve_timeout_seconds = auto_approve_timeout_seconds
        self.audit_logger = audit_logger

    # ------------------------------------------------------------------
    # Gate request creation
    # ------------------------------------------------------------------

    async def request_approval(
        self,
        state: dict[str, Any],
        *,
        summary: str = "",
        findings: dict[str, Any] | None = None,
        options: list[str] | None = None,
        triggered_by: str = "supervisor",
        gate_type: ApprovalGateType | None = None,
        approval_request: ApprovalGateRequest | None = None,
    ) -> dict[str, Any]:
        """Create an approval request and pause the investigation.

        Returns the updated state with approval metadata populated.
        """
        if approval_request:
            gate_type = approval_request.gate_type
            summary = approval_request.summary
            findings = approval_request.findings

        gate_type_str = gate_type.value if gate_type else "general"

        approval_req = ApprovalRequest(
            summary=f"[{gate_type_str.upper()}] {summary}",
            findings=findings or {},
            options=options or ["approve", "reject", "request_changes"],
            timeout_seconds=self.auto_approve_timeout_seconds,
        )

        state["approval_required"] = True
        state["phase"] = InvestigationPhase.APPROVAL
        state["pending_approval_request"] = approval_req.model_dump(mode="json")
        state["approval_result"] = None

        # Store gate type in context for downstream use
        ctx = dict(state.get("context", {}))
        ctx["approval_gate_type"] = gate_type_str
        state["context"] = ctx

        logger.info(f"Approval gate [{gate_type_str}] requested by {triggered_by}: {summary[:100]}")

        # Audit the request
        if self.audit_logger:
            self.audit_logger.log_approval_requested(
                gate_type=gate_type_str,
                agent_name=triggered_by,
                summary=summary,
                investigation_id=state.get("investigation_id", ""),
                trace_id=state.get("trace_id"),
            )

        return state

    # ------------------------------------------------------------------
    # Gate response processing
    # ------------------------------------------------------------------

    async def process_response(
        self,
        state: dict[str, Any],
        *,
        decision: str,
        reviewer: str = "human",
        comments: str = "",
        conditions: list[str] | None = None,
    ) -> dict[str, Any]:
        """Process a human approval response.

        Args:
            decision: One of "approve", "reject", "request_changes".
            reviewer: Identifier of the human reviewer.
            comments: Optional reviewer comments.
            conditions: Optional approval conditions.
        """
        ctx = dict(state.get("context", {}))
        gate_type_str = ctx.get("approval_gate_type", "general")

        result = {
            "decision": decision,
            "reviewer": reviewer,
            "comments": comments,
            "conditions": conditions or [],
            "gate_type": gate_type_str,
        }

        state["approval_result"] = result
        state["approval_required"] = False
        state["pending_approval_request"] = None

        if decision == "approve":
            state["phase"] = InvestigationPhase.ANALYSIS
            logger.info(f"Approved by {reviewer} [gate={gate_type_str}]")
        elif decision == "reject":
            state["should_abstain"] = True
            state["abstention_reason"] = (
                f"Rejected by {reviewer}: {comments}" if comments else f"Rejected by {reviewer}"
            )
            state["phase"] = InvestigationPhase.ABSTENTION
            logger.info(f"Rejected by {reviewer} [gate={gate_type_str}]")
        elif decision == "request_changes":
            state["phase"] = InvestigationPhase.PLANNING
            logger.info(f"Changes requested by {reviewer} [gate={gate_type_str}]: {comments}")

        # Audit the decision
        if self.audit_logger:
            self.audit_logger.log_approval_decision(
                gate_type=gate_type_str,
                decision=decision,
                reviewer=reviewer,
                comments=comments,
                investigation_id=state.get("investigation_id", ""),
                trace_id=state.get("trace_id"),
            )

        return state

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def is_approved(self, state: dict[str, Any]) -> bool:
        result = state.get("approval_result")
        if result is None:
            return False
        return result.get("decision") == "approve"

    def is_rejected(self, state: dict[str, Any]) -> bool:
        result = state.get("approval_result")
        if result is None:
            return False
        return result.get("decision") == "reject"

    def is_pending(self, state: dict[str, Any]) -> bool:
        return state.get("approval_required", False) and state.get("approval_result") is None

    def get_gate_type(self, state: dict[str, Any]) -> str | None:
        ctx = state.get("context", {})
        return ctx.get("approval_gate_type")

    # ------------------------------------------------------------------
    # Gate type resolution
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_gate_type(trigger: str) -> ApprovalGateType | None:
        """Resolve a trigger string to an ApprovalGateType."""
        return _GATE_TRIGGERS.get(trigger) or _DECISION_GATES.get(trigger)

    @staticmethod
    def requires_approval(
        action_type: str, priority: str, gate_hint: str | None = None
    ) -> tuple[bool, ApprovalGateType | None]:
        """Determine if an action requires mandatory approval.

        Returns (requires_approval, gate_type).
        """
        if gate_hint:
            gate = _GATE_TRIGGERS.get(gate_hint) or _DECISION_GATES.get(gate_hint)
            if gate:
                return True, gate

        if priority in ("high", "critical"):
            if action_type in ("REPAIR", "PROCEDURE_UPDATE", "SHUTDOWN"):
                return True, ApprovalGateType.HIGH_PRIORITY_ACTION
            if action_type == "TEST":
                return True, ApprovalGateType.MAINTENANCE_STRATEGY

        return False, None
