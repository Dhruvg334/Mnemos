"""Tenant-scoped human approval API.

Approval requests are visible and actionable only inside the authenticated
principal's organisation/site scope. Decision endpoints also enforce
separation of duties: the user who requested the governed action cannot
approve it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from mnemos.agentic.runtime.approval_queue import (
    ApprovalDecision,
    ApprovalQueueBase,
    PendingApprovalRequest,
)
from mnemos.api.deps import Principal, get_principal

_VALID_DECISIONS = frozenset({"approve", "reject", "request_changes"})
_APPROVAL_ROLES = frozenset({"approver", "platform_admin", "organisation_admin", "site_admin"})
_ADMIN_ROLES = frozenset({"platform_admin", "organisation_admin", "site_admin"})


class DecisionRequest(BaseModel):
    """A review decision; reviewer identity always comes from authentication."""

    decision: str = Field(..., description="approve, reject, or request_changes")
    reviewer: str = Field(default="", description="Deprecated and ignored.")
    comments: str = ""
    conditions: list[str] = Field(default_factory=list)

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, value: str) -> str:
        if value not in _VALID_DECISIONS:
            raise ValueError(f"decision must be one of: {sorted(_VALID_DECISIONS)}")
        return value


class CancelRequest(BaseModel):
    reason: str = ""


def _is_platform_admin(principal: Principal) -> bool:
    return any(membership.role == "platform_admin" for membership in principal.memberships)


def _matching_membership(
    principal: Principal,
    request: PendingApprovalRequest,
    *,
    allowed_roles: frozenset[str] = _APPROVAL_ROLES,
) -> Any | None:
    """Return an authorised membership for the request's exact tenant scope."""
    if _is_platform_admin(principal):
        return next(
            membership
            for membership in principal.memberships
            if membership.role == "platform_admin"
        )

    # Legacy/unscoped requests fail closed for non-platform users.
    if not request.organisation_id:
        return None

    candidates = []
    for membership in principal.memberships:
        if membership.role not in allowed_roles:
            continue
        if membership.organisation_id != request.organisation_id:
            continue
        if request.site_id is not None and membership.site_id not in (None, request.site_id):
            continue
        candidates.append(membership)

    # Prefer an exact site membership over organisation-wide access.
    candidates.sort(key=lambda item: item.site_id != request.site_id)
    return candidates[0] if candidates else None


def _require_request_access(
    principal: Principal,
    request: PendingApprovalRequest,
    *,
    allowed_roles: frozenset[str] = _APPROVAL_ROLES,
) -> str:
    membership = _matching_membership(principal, request, allowed_roles=allowed_roles)
    if membership is None:
        # Use 404 so callers cannot enumerate approval IDs outside their scope.
        raise HTTPException(status_code=404, detail="Approval request not found.")
    return principal.user.full_name or principal.user.email or principal.user.id


def _require_separation_of_duties(
    principal: Principal,
    request: PendingApprovalRequest,
) -> None:
    if request.requested_by_user_id and request.requested_by_user_id == principal.user.id:
        raise HTTPException(
            status_code=403,
            detail="The requester cannot approve their own governed action.",
        )


def _visible_requests(
    principal: Principal,
    requests: list[PendingApprovalRequest],
) -> list[PendingApprovalRequest]:
    return [request for request in requests if _matching_membership(principal, request) is not None]


def create_approval_router(
    approval_queue: ApprovalQueueBase,
    *,
    resume_callback: Callable[[str], Awaitable[None]] | None = None,
) -> APIRouter:
    router = APIRouter(tags=["approvals"])

    @router.get("/pending")
    async def list_pending(
        principal: Principal = Depends(get_principal),
    ) -> dict[str, Any]:
        pending = _visible_requests(principal, await approval_queue.get_all_pending())
        return {
            "requests": [request.model_dump(mode="json") for request in pending],
            "count": len(pending),
        }

    @router.get("/summary")
    async def get_summary(
        principal: Principal = Depends(get_principal),
    ) -> dict[str, Any]:
        pending = _visible_requests(principal, await approval_queue.get_all_pending())
        by_gate: dict[str, int] = {}
        for request in pending:
            by_gate[request.gate_type] = by_gate.get(request.gate_type, 0) + 1
        return {"pending_count": len(pending), "pending_by_gate": by_gate}

    @router.get("/{request_id}")
    async def get_request(
        request_id: str,
        principal: Principal = Depends(get_principal),
    ) -> dict[str, Any]:
        request = await approval_queue.get_request(request_id)
        if request is None:
            raise HTTPException(status_code=404, detail="Approval request not found.")
        _require_request_access(principal, request)
        decision = await approval_queue.get_decision(request_id)
        return {
            "request": request.model_dump(mode="json"),
            "decision": decision.model_dump(mode="json") if decision else None,
        }

    @router.post("/{request_id}/decision")
    async def submit_decision(
        request_id: str,
        body: DecisionRequest,
        background_tasks: BackgroundTasks,
        principal: Principal = Depends(get_principal),
    ) -> dict[str, Any]:
        request = await approval_queue.get_request(request_id)
        if request is None:
            raise HTTPException(status_code=404, detail="Approval request not found.")
        reviewer = _require_request_access(principal, request)
        _require_separation_of_duties(principal, request)

        if request.status.value != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Approval request is already '{request.status.value}'.",
            )

        updated = await approval_queue.submit_decision(
            request_id,
            ApprovalDecision(
                decision=body.decision,
                reviewer=reviewer,
                comments=body.comments,
                conditions=body.conditions,
            ),
        )
        if updated is None:
            raise HTTPException(status_code=503, detail="Approval decision could not be persisted.")

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

    @router.post("/{request_id}/cancel")
    async def cancel_request(
        request_id: str,
        body: CancelRequest | None = None,
        principal: Principal = Depends(get_principal),
    ) -> dict[str, Any]:
        request = await approval_queue.get_request(request_id)
        if request is None:
            raise HTTPException(status_code=404, detail="Approval request not found.")
        _require_request_access(principal, request, allowed_roles=_ADMIN_ROLES)
        cancelled = await approval_queue.cancel(request_id)
        if not cancelled:
            raise HTTPException(status_code=409, detail="Approval request is not pending.")
        return {
            "success": True,
            "request_id": request_id,
            "cancelled": True,
            "reason": body.reason if body else "",
        }

    return router
