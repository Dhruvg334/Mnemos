"""Human Approval Node for the multi-agent runtime.

Provides a structural checkpoint where the investigation can pause
and wait for human review and approval before continuing.  The node
does not implement any UI -- it only manages the state transitions
for approval workflows.
"""

from __future__ import annotations

from typing import Any

from mnemos.agentic.runtime.types import (
    ApprovalRequest,
    InvestigationPhase,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("runtime.approval")


class HumanApprovalNode:
    """Manages human-in-the-loop approval checkpoints.

    When an investigation requires human review (e.g. high-risk findings,
    compliance decisions, or critical recommendations), this node:

    1. Pauses the investigation
    2. Records what needs approval
    3. Processes the human response
    4. Updates the investigation state accordingly
    """

    def __init__(self, auto_approve_timeout_seconds: float = 300.0) -> None:
        self.auto_approve_timeout_seconds = auto_approve_timeout_seconds

    async def request_approval(
        self,
        state: dict[str, Any],
        *,
        summary: str = "",
        findings: dict[str, Any] | None = None,
        options: list[str] | None = None,
        triggered_by: str = "supervisor",
    ) -> dict[str, Any]:
        """Create an approval request and pause the investigation.

        Returns the updated state with approval metadata populated.
        """
        approval_request = ApprovalRequest(
            summary=summary,
            findings=findings or {},
            options=options or ["approve", "reject", "request_changes"],
            timeout_seconds=self.auto_approve_timeout_seconds,
        )

        state["approval_required"] = True
        state["phase"] = InvestigationPhase.APPROVAL
        state["pending_approval_request"] = approval_request.model_dump(mode="json")
        state["approval_result"] = None

        logger.info(
            f"Approval requested by {triggered_by}: {summary[:100]}"
        )

        return state

    async def process_response(
        self,
        state: dict[str, Any],
        *,
        decision: str,
        reviewer: str = "human",
        comments: str = "",
    ) -> dict[str, Any]:
        """Process a human approval response.

        Args:
            decision: One of "approve", "reject", "request_changes".
            reviewer: Identifier of the human reviewer.
            comments: Optional reviewer comments.
        """
        result = {
            "decision": decision,
            "reviewer": reviewer,
            "comments": comments,
        }

        state["approval_result"] = result
        state["approval_required"] = False
        state["pending_approval_request"] = None

        if decision == "approve":
            state["phase"] = InvestigationPhase.ANALYSIS
            logger.info(f"Approved by {reviewer}")
        elif decision == "reject":
            state["should_abstain"] = True
            state["abstention_reason"] = (
                f"Rejected by {reviewer}: {comments}"
                if comments
                else f"Rejected by {reviewer}"
            )
            state["phase"] = InvestigationPhase.ABSTENTION
            logger.info(f"Rejected by {reviewer}")
        elif decision == "request_changes":
            state["phase"] = InvestigationPhase.PLANNING
            logger.info(f"Changes requested by {reviewer}: {comments}")

        return state

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
