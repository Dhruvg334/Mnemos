"""Tests for the Approval Queue and API endpoints.

Covers:
- ApprovalQueue: submit, decide, query, cancel, expiry
- API endpoints: list pending, submit decision, get request, cancel
"""

from __future__ import annotations

import pytest

from mnemos.agentic.runtime.approval_queue import (
    ApprovalDecision,
    ApprovalQueue,
    ApprovalStatus,
    PendingApprovalRequest,
)

# =====================================================================
# Test: PendingApprovalRequest
# =====================================================================


class TestPendingApprovalRequest:
    def test_request_creation(self):
        req = PendingApprovalRequest(
            investigation_id="inv_001",
            gate_type="rca_closure",
            summary="RCA needs review",
        )
        assert req.request_id.startswith("apr_")
        assert req.investigation_id == "inv_001"
        assert req.gate_type == "rca_closure"
        assert req.status == ApprovalStatus.PENDING

    def test_request_serialization(self):
        req = PendingApprovalRequest(
            investigation_id="inv_001",
            gate_type="rca_closure",
            summary="RCA needs review",
        )
        d = req.model_dump(mode="json")
        restored = PendingApprovalRequest(**d)
        assert restored.request_id == req.request_id
        assert restored.summary == req.summary


# =====================================================================
# Test: ApprovalDecision
# =====================================================================


class TestApprovalDecision:
    def test_decision_creation(self):
        dec = ApprovalDecision(
            decision="approve",
            reviewer="admin",
            comments="Looks good",
        )
        assert dec.decision == "approve"
        assert dec.reviewer == "admin"

    def test_decision_serialization(self):
        dec = ApprovalDecision(
            decision="reject",
            reviewer="admin",
            comments="Unsafe",
        )
        d = dec.model_dump(mode="json")
        restored = ApprovalDecision(**d)
        assert restored.decision == "reject"


# =====================================================================
# Test: ApprovalQueue
# =====================================================================


class TestApprovalQueue:
    def setup_method(self):
        self.queue = ApprovalQueue(default_timeout_seconds=300.0)

    @pytest.mark.asyncio
    async def test_submit_request(self):
        request = await self.queue.submit_request(
            investigation_id="inv_001",
            gate_type="rca_closure",
            state_snapshot={"phase": "approval"},
            summary="RCA needs review",
        )
        assert request.request_id.startswith("apr_")
        assert request.status == ApprovalStatus.PENDING
        assert self.queue.count() == 1

    @pytest.mark.asyncio
    async def test_submit_decision_approve(self):
        request = await self.queue.submit_request(
            investigation_id="inv_001",
            gate_type="rca_closure",
            state_snapshot={},
        )
        decision = ApprovalDecision(
            decision="approve",
            reviewer="admin",
            comments="LGTM",
        )
        updated = await self.queue.submit_decision(request.request_id, decision)
        assert updated is not None
        assert updated.status == ApprovalStatus.APPROVED
        assert self.queue.count() == 0

    @pytest.mark.asyncio
    async def test_submit_decision_reject(self):
        request = await self.queue.submit_request(
            investigation_id="inv_001",
            gate_type="compliance_closure",
            state_snapshot={},
        )
        decision = ApprovalDecision(
            decision="reject",
            reviewer="admin",
            comments="Unsafe procedure",
        )
        updated = await self.queue.submit_decision(request.request_id, decision)
        assert updated.status == ApprovalStatus.REJECTED

    @pytest.mark.asyncio
    async def test_submit_decision_request_changes(self):
        request = await self.queue.submit_request(
            investigation_id="inv_001",
            gate_type="knowledge_publication",
            state_snapshot={},
        )
        decision = ApprovalDecision(
            decision="request_changes",
            reviewer="admin",
            comments="Add more evidence",
        )
        updated = await self.queue.submit_decision(request.request_id, decision)
        assert updated.status == ApprovalStatus.CHANGES_REQUESTED

    @pytest.mark.asyncio
    async def test_get_request(self):
        request = await self.queue.submit_request(
            investigation_id="inv_001",
            gate_type="rca_closure",
            state_snapshot={},
        )
        found = await self.queue.get_request(request.request_id)
        assert found is not None
        assert found.investigation_id == "inv_001"

    @pytest.mark.asyncio
    async def test_get_request_not_found(self):
        found = await self.queue.get_request("nonexistent")
        assert found is None

    @pytest.mark.asyncio
    async def test_get_decision(self):
        request = await self.queue.submit_request(
            investigation_id="inv_001",
            gate_type="rca_closure",
            state_snapshot={},
        )
        decision = ApprovalDecision(decision="approve", reviewer="admin")
        await self.queue.submit_decision(request.request_id, decision)

        found = await self.queue.get_decision(request.request_id)
        assert found is not None
        assert found.decision == "approve"

    @pytest.mark.asyncio
    async def test_get_pending_for_investigation(self):
        await self.queue.submit_request(
            investigation_id="inv_001",
            gate_type="rca_closure",
            state_snapshot={},
        )
        await self.queue.submit_request(
            investigation_id="inv_001",
            gate_type="compliance_closure",
            state_snapshot={},
        )
        await self.queue.submit_request(
            investigation_id="inv_002",
            gate_type="rca_closure",
            state_snapshot={},
        )

        pending = await self.queue.get_pending_for_investigation("inv_001")
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_get_all_pending(self):
        await self.queue.submit_request(
            investigation_id="inv_001",
            gate_type="rca_closure",
            state_snapshot={},
        )
        await self.queue.submit_request(
            investigation_id="inv_002",
            gate_type="rca_closure",
            state_snapshot={},
        )

        pending = await self.queue.get_all_pending()
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_is_approved(self):
        request = await self.queue.submit_request(
            investigation_id="inv_001",
            gate_type="rca_closure",
            state_snapshot={},
        )
        assert await self.queue.is_approved(request.request_id) is False

        decision = ApprovalDecision(decision="approve", reviewer="admin")
        await self.queue.submit_decision(request.request_id, decision)
        assert await self.queue.is_approved(request.request_id) is True

    @pytest.mark.asyncio
    async def test_is_pending(self):
        request = await self.queue.submit_request(
            investigation_id="inv_001",
            gate_type="rca_closure",
            state_snapshot={},
        )
        assert await self.queue.is_pending(request.request_id) is True

        decision = ApprovalDecision(decision="approve", reviewer="admin")
        await self.queue.submit_decision(request.request_id, decision)
        assert await self.queue.is_pending(request.request_id) is False

    @pytest.mark.asyncio
    async def test_cancel(self):
        request = await self.queue.submit_request(
            investigation_id="inv_001",
            gate_type="rca_closure",
            state_snapshot={},
        )
        cancelled = await self.queue.cancel(request.request_id)
        assert cancelled is True
        assert await self.queue.is_pending(request.request_id) is False

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self):
        cancelled = await self.queue.cancel("nonexistent")
        assert cancelled is False

    @pytest.mark.asyncio
    async def test_decision_after_approve_ignored(self):
        request = await self.queue.submit_request(
            investigation_id="inv_001",
            gate_type="rca_closure",
            state_snapshot={},
        )
        decision1 = ApprovalDecision(decision="approve", reviewer="admin")
        await self.queue.submit_decision(request.request_id, decision1)

        decision2 = ApprovalDecision(decision="reject", reviewer="other")
        updated = await self.queue.submit_decision(request.request_id, decision2)
        assert updated is not None
        assert updated.status == ApprovalStatus.APPROVED

    @pytest.mark.asyncio
    async def test_summary(self):
        await self.queue.submit_request(
            investigation_id="inv_001",
            gate_type="rca_closure",
            state_snapshot={},
        )
        await self.queue.submit_request(
            investigation_id="inv_002",
            gate_type="rca_closure",
            state_snapshot={},
        )
        request3 = await self.queue.submit_request(
            investigation_id="inv_003",
            gate_type="rca_closure",
            state_snapshot={},
        )
        decision = ApprovalDecision(decision="approve", reviewer="admin")
        await self.queue.submit_decision(request3.request_id, decision)

        s = self.queue.summary()
        assert s["total_requests"] == 3
        assert s["status_counts"]["pending"] == 2
        assert s["status_counts"]["approved"] == 1
        assert s["pending_count"] == 2

    @pytest.mark.asyncio
    async def test_state_snapshot_preserved(self):
        state = {"phase": "approval", "iteration": 3, "agent_outputs": {"rca_agent": {}}}
        request = await self.queue.submit_request(
            investigation_id="inv_001",
            gate_type="rca_closure",
            state_snapshot=state,
        )
        found = await self.queue.get_request(request.request_id)
        assert found is not None
        assert found.state_snapshot["phase"] == "approval"
        assert found.state_snapshot["iteration"] == 3


# =====================================================================
# Test: Approval API Endpoints
# =====================================================================


class TestApprovalAPI:
    def setup_method(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from mnemos.agentic.runtime.api.approvals import create_approval_router

        self.queue = ApprovalQueue(default_timeout_seconds=300.0)
        self.app = FastAPI()
        self.app.include_router(create_approval_router(self.queue), prefix="/approvals")
        self.client = TestClient(self.app)

    def _submit_request(self) -> str:
        import asyncio
        request = asyncio.get_event_loop().run_until_complete(
            self.queue.submit_request(
                investigation_id="inv_001",
                gate_type="rca_closure",
                state_snapshot={"phase": "approval"},
                summary="RCA needs review",
            )
        )
        return request.request_id

    def test_list_pending_empty(self):
        response = self.client.get("/approvals/pending")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0

    def test_list_pending_with_requests(self):
        self._submit_request()
        self._submit_request()
        response = self.client.get("/approvals/pending")
        assert response.status_code == 200
        assert response.json()["count"] == 2

    def test_get_request(self):
        request_id = self._submit_request()
        response = self.client.get(f"/approvals/{request_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["request"]["investigation_id"] == "inv_001"
        assert data["decision"] is None

    def test_get_request_not_found(self):
        response = self.client.get("/approvals/nonexistent")
        assert response.status_code == 404

    def test_submit_decision_approve(self):
        request_id = self._submit_request()
        response = self.client.post(
            f"/approvals/{request_id}/decision",
            json={
                "decision": "approve",
                "reviewer": "admin",
                "comments": "Looks good",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "approved"

    def test_submit_decision_reject(self):
        request_id = self._submit_request()
        response = self.client.post(
            f"/approvals/{request_id}/decision",
            json={
                "decision": "reject",
                "reviewer": "admin",
                "comments": "Unsafe",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

    def test_submit_decision_invalid(self):
        request_id = self._submit_request()
        response = self.client.post(
            f"/approvals/{request_id}/decision",
            json={
                "decision": "maybe",
                "reviewer": "admin",
            },
        )
        # Pydantic field_validator raises ValidationError -> FastAPI returns 422
        assert response.status_code in (400, 422)

    def test_submit_decision_not_found(self):
        response = self.client.post(
            "/approvals/nonexistent/decision",
            json={"decision": "approve", "reviewer": "admin"},
        )
        assert response.status_code == 404

    def test_submit_decision_already_decided(self):
        request_id = self._submit_request()
        self.client.post(
            f"/approvals/{request_id}/decision",
            json={"decision": "approve", "reviewer": "admin"},
        )
        response = self.client.post(
            f"/approvals/{request_id}/decision",
            json={"decision": "reject", "reviewer": "other"},
        )
        assert response.status_code == 409

    def test_cancel_request(self):
        request_id = self._submit_request()
        response = self.client.post(f"/approvals/{request_id}/cancel")
        assert response.status_code == 200
        assert response.json()["cancelled"] is True

    def test_cancel_not_found(self):
        response = self.client.post("/approvals/nonexistent/cancel")
        assert response.status_code == 404

    def test_summary(self):
        self._submit_request()
        self._submit_request()
        response = self.client.get("/approvals/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_requests"] == 2
        assert data["pending_count"] == 2
