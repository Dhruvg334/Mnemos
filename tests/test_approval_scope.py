"""Approval authorization tests for tenant isolation and separation of duties."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from mnemos.agentic.runtime.api.approvals import (
    _require_request_access,
    _require_separation_of_duties,
    _visible_requests,
)
from mnemos.agentic.runtime.approval_queue import PendingApprovalRequest
from mnemos.api.deps import Principal


def _principal(user_id: str, *memberships: SimpleNamespace) -> Principal:
    user = SimpleNamespace(id=user_id, full_name=f"User {user_id}", email=f"{user_id}@test.local")
    return Principal(user=user, memberships=list(memberships))


def _membership(
    role: str,
    organisation_id: str,
    site_id: str | None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"mem-{role}-{organisation_id}-{site_id}",
        role=role,
        organisation_id=organisation_id,
        site_id=site_id,
    )


def _request(
    request_id: str,
    organisation_id: str | None,
    site_id: str | None,
    requested_by_user_id: str = "requester",
) -> PendingApprovalRequest:
    return PendingApprovalRequest(
        request_id=request_id,
        investigation_id=f"query-{request_id}",
        gate_type="rca_closure",
        organisation_id=organisation_id,
        site_id=site_id,
        requested_by_user_id=requested_by_user_id,
    )


def test_pending_requests_are_filtered_to_principal_scope() -> None:
    principal = _principal(
        "reviewer",
        _membership("approver", "org-a", "site-a"),
    )
    requests = [
        _request("visible", "org-a", "site-a"),
        _request("wrong-site", "org-a", "site-b"),
        _request("wrong-org", "org-b", "site-a"),
        _request("unscoped", None, None),
    ]

    visible = _visible_requests(principal, requests)

    assert [request.request_id for request in visible] == ["visible"]


def test_organisation_wide_approver_can_review_any_site_in_organisation() -> None:
    principal = _principal(
        "reviewer",
        _membership("organisation_admin", "org-a", None),
    )
    request = _request("request", "org-a", "site-b")

    reviewer = _require_request_access(principal, request)

    assert reviewer == "User reviewer"


def test_out_of_scope_request_is_concealed_as_not_found() -> None:
    principal = _principal(
        "reviewer",
        _membership("approver", "org-a", "site-a"),
    )
    request = _request("request", "org-b", "site-a")

    with pytest.raises(HTTPException) as exc_info:
        _require_request_access(principal, request)

    assert exc_info.value.status_code == 404


def test_requester_cannot_approve_own_governed_action() -> None:
    principal = _principal(
        "requester",
        _membership("approver", "org-a", "site-a"),
    )
    request = _request("request", "org-a", "site-a", requested_by_user_id="requester")

    with pytest.raises(HTTPException) as exc_info:
        _require_separation_of_duties(principal, request)

    assert exc_info.value.status_code == 403


def test_platform_admin_can_access_legacy_unscoped_request() -> None:
    principal = _principal(
        "platform",
        _membership("platform_admin", "platform", None),
    )
    request = _request("legacy", None, None)

    reviewer = _require_request_access(principal, request)

    assert reviewer == "User platform"
