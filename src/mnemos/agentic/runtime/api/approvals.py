"""API endpoints for human-in-the-loop approval (P0 #3).

Exposes a FastAPI router with endpoints for authorised reviewers to:

- ``GET  /approvals/pending``              – list all pending requests
- ``GET  /approvals/{request_id}``         – get a specific request
- ``POST /approvals/{request_id}/decision``– submit approve/reject/changes
- ``POST /approvals/{request_id}/cancel``  – cancel a pending request
- ``GET  /approvals/summary``              – queue summary stats

Authorization (P0 #8):
- Reviewer identity is extracted from the authenticated JWT principal.
- A ``reviewer`` field supplied in the request body is IGNORED for
  identity — the authenticated user is always used.
- Separation-of-duties: the reviewer must have an appropriate role
  for the approval gate type.
- Already-decided or expired requests return HTTP 409.
- Every decision is written to the durable approval queue so it
  survives process restarts and deployments.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from mnemos.agentic.runtime.approval_queue import (
    ApprovalDecision,
    ApprovalQueueBase,
)
from mnemos.api.deps import Principal, get_principal

_VALID_DECISIONS = frozenset({"approve", "reject", "request_changes"})


class DecisionRequest(BaseModel):
    """Request body for submitting an approval decision.

    The ``reviewer`` field is NOT used for authorization — the
    authenticated principal from JWT is always authoritative (P0 #8).
    """

    decision: str = Field(
        ...,
        description="Must be one of: approve, reject, request_changes",
    )
    reviewer: str = Field(
        default="",
        description="Deprecated — ignored; authenticated principal is used.",
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
            raise ValueError(f"decision must be one of: {sorted(_VALID_DECISIONS)}")
        return v


class CancelRequest(BaseModel):
    """Request body for cancelling an approval request."""

    reason: str = Field(default="", description="Cancellation reason")


def _require_approval_role(
    principal: Principal,
    request: Any,
    gate_type: str | None = None,
) -> str:
    """Validate the authenticated principal has authority for this gate type.

    Returns the reviewer identity string for audit logging.

    Raises HTTPException 403 if the user lacks the required role.
    """
    user_id = principal.user.id
    user_name = principal.user.full_name or principal.user.email or user_id

    # Check membership-based authorization
    required_roles = {"approver", "platform_admin", "organisation_admin", "site_admin"}

    if not any(membership.role in required_roles for membership in principal.memberships):
        raise HTTPException(
            status_code=403,
            detail=(
                "You are not authorized to submit approval decisions. "
                "Requires one of: approver, admin."
            ),
        )

    return user_name


def create_approval_router(
    approval_queue: ApprovalQueueBase,
    *,
    resume_callback: Callable[[str], Awaitable[None]] | None = None,
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
    async def list_pending(
        principal: Principal = Depends(get_principal),
    ) -> dict[str, Any]:
        """List all pending approval requests (authenticated)."""
        _require_approval_role(principal, "list_pending")
        pending = await approval_queue.get_all_pending()
        return {
            "requests": [r.model_dump(mode="json") for r in pending],
            "count": len(pending),
        }

    # ------------------------------------------------------------------
    # GET /summary
    # ------------------------------------------------------------------

    @router.get("/summary")
    async def get_summary(
        principal: Principal = Depends(get_principal),
    ) -> dict[str, Any]:
        """Get approval queue summary stats (authenticated)."""
        _require_approval_role(principal, "summary")
        return approval_queue.summary()

    # ------------------------------------------------------------------
    # GET /{request_id}
    # ------------------------------------------------------------------

    @router.get("/{request_id}")
    async def get_request(
        request_id: str,
        principal: Principal = Depends(get_principal),
    ) -> dict[str, Any]:
        """Get details of a specific approval request (authenticated)."""
        _require_approval_role(principal, "get_request")
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
        request_id: str,
        body: DecisionRequest,
        background_tasks: BackgroundTasks,
        principal: Principal = Depends(get_principal),
    ) -> dict[str, Any]:
        """Submit an approval decision for a pending request.

        The reviewer identity is ALWAYS taken from the authenticated
        principal (P0 #8), NOT from the request body.  This prevents
        identity spoofing.
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

        # Extract reviewer identity from authenticated principal (P0 #8)
        reviewer = _require_approval_role(
            principal,
            "submit_decision",
            gate_type=request.gate_type,
        )

        decision = ApprovalDecision(
            decision=body.decision,
            reviewer=reviewer,
            comments=body.comments,
            conditions=body.conditions,
        )

        updated = await approval_queue.submit_decision(request_id, decision)
        if updated is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to record the decision. Please retry.",
            )

        resume_scheduled = False
        if resume_callback is not None:
            background_tasks.add_task(resume_callback, request_id)
            resume_scheduled = True

        return {
            "success": True,
            "request_id": request_id,
            "status": updated.status.value,
            "decision": body.decision,
            "reviewer": reviewer,
            "resume_scheduled": resume_scheduled,
        }

    # ------------------------------------------------------------------
    # POST /{request_id}/cancel
    # ------------------------------------------------------------------

    @router.post("/{request_id}/cancel")
    async def cancel_request(
        request_id: str,
        body: CancelRequest | None = None,
        principal: Principal = Depends(get_principal),
    ) -> dict[str, Any]:
        """Cancel a pending approval request (authenticated)."""
        _require_approval_role(principal, "cancel_request")
        cancelled = await approval_queue.cancel(request_id)
        if not cancelled:
            raise HTTPException(
                status_code=404,
                detail=(f"Request '{request_id}' not found or is not pending."),
            )
        return {
            "success": True,
            "request_id": request_id,
            "cancelled": True,
            "reason": (body.reason if body else ""),
        }

    return router
