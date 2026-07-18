"""API endpoints for human-in-the-loop approval (P0 #3).

Exposes a FastAPI router with endpoints for authorised reviewers to:

- ``GET  /approvals/pending``              – list all pending requests
- ``GET  /approvals/{request_id}``         – get a specific request
- ``POST /approvals/{request_id}/decision``– submit approve/reject/changes
- ``POST /approvals/{request_id}/cancel``  – cancel a pending request
- ``GET  /approvals/summary``              – queue summary stats

Authorization:
- A reviewer must supply a non-empty ``reviewer`` identifier.
- Decisions are validated: only ``approve``, ``reject``, or
  ``request_changes`` are accepted.
- Already-decided or expired requests return HTTP 409.
- Every decision is written to the durable approval queue so it
  survives process restarts and deployments.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from mnemos.agentic.runtime.approval_queue import (
    ApprovalDecision,
    ApprovalQueueBase,
)

_VALID_DECISIONS = frozenset({"approve", "reject", "request_changes"})


class DecisionRequest(BaseModel):
    """Request body for submitting an approval decision."""

    decision: str = Field(
        ...,
        description="Must be one of: approve, reject, request_changes",
    )
    reviewer: str = Field(
        ...,
        min_length=1,
        description="Non-empty identifier of the human reviewer",
    )
    comments: str = Field(default="", description="Reviewer comments")
    conditions: list[str] = Field(
        default_factory=list,
        description="Approval conditions or required changes",
    )

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        if v not in _VALID_DECISIONS:
            raise ValueError(
                f"decision must be one of: {sorted(_VALID_DECISIONS)}"
            )
        return v

    @field_validator("reviewer")
    @classmethod
    def validate_reviewer(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("reviewer must not be blank")
        return v


class CancelRequest(BaseModel):
    """Request body for cancelling an approval request."""

    reason: str = Field(default="", description="Cancellation reason")


def create_approval_router(
    approval_queue: ApprovalQueueBase,
) -> APIRouter:
    """Create a FastAPI router wired to an ApprovalQueueBase instance.

    Usage::

        from fastapi import FastAPI
        from mnemos.agentic.runtime.approval_queue import DurableApprovalQueue
        from mnemos.agentic.runtime.api.approvals import create_approval_router
        from mnemos.core.db import SessionLocal

        queue = DurableApprovalQueue(session_factory=SessionLocal)
        app = FastAPI()
        app.include_router(
            create_approval_router(queue), prefix="/approvals"
        )
    """
    router = APIRouter(tags=["approvals"])

    # ------------------------------------------------------------------
    # GET /pending
    # ------------------------------------------------------------------

    @router.get("/pending")
    async def list_pending() -> dict[str, Any]:
        """List all pending approval requests."""
        pending = await approval_queue.get_all_pending()
        return {
            "requests": [r.model_dump(mode="json") for r in pending],
            "count": len(pending),
        }

    # ------------------------------------------------------------------
    # GET /summary
    # ------------------------------------------------------------------

    @router.get("/summary")
    async def get_summary() -> dict[str, Any]:
        """Get approval queue summary stats."""
        return approval_queue.summary()

    # ------------------------------------------------------------------
    # GET /{request_id}
    # ------------------------------------------------------------------

    @router.get("/{request_id}")
    async def get_request(request_id: str) -> dict[str, Any]:
        """Get details of a specific approval request."""
        request = await approval_queue.get_request(request_id)
        if request is None:
            raise HTTPException(
                status_code=404,
                detail=f"Approval request '{request_id}' not found.",
            )
        decision = await approval_queue.get_decision(request_id)
        return {
            "request": request.model_dump(mode="json"),
            "decision": decision.model_dump(mode="json") if decision else None,
        }

    # ------------------------------------------------------------------
    # POST /{request_id}/decision
    # ------------------------------------------------------------------

    @router.post("/{request_id}/decision")
    async def submit_decision(
        request_id: str, body: DecisionRequest
    ) -> dict[str, Any]:
        """Submit an approval decision for a pending request.

        Only pending requests may receive a decision.  A request that
        is already decided, expired, or cancelled returns HTTP 409.
        """
        request = await approval_queue.get_request(request_id)
        if request is None:
            raise HTTPException(
                status_code=404,
                detail=f"Approval request '{request_id}' not found.",
            )

        if request.status.value != "pending":
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Request '{request_id}' is already in state "
                    f"'{request.status.value}' and cannot be decided again."
                ),
            )

        decision = ApprovalDecision(
            decision=body.decision,
            reviewer=body.reviewer,
            comments=body.comments,
            conditions=body.conditions,
        )

        updated = await approval_queue.submit_decision(request_id, decision)
        if updated is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to record the decision. Please retry.",
            )

        return {
            "success": True,
            "request_id": request_id,
            "status": updated.status.value,
            "decision": body.decision,
            "reviewer": body.reviewer,
        }

    # ------------------------------------------------------------------
    # POST /{request_id}/cancel
    # ------------------------------------------------------------------

    @router.post("/{request_id}/cancel")
    async def cancel_request(
        request_id: str,
        body: CancelRequest | None = None,
    ) -> dict[str, Any]:
        """Cancel a pending approval request."""
        cancelled = await approval_queue.cancel(request_id)
        if not cancelled:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Request '{request_id}' not found or is not pending."
                ),
            )
        return {
            "success": True,
            "request_id": request_id,
            "cancelled": True,
            "reason": (body.reason if body else ""),
        }

    return router
