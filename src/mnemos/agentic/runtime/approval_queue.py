"""Durable Approval Queue for real human-in-the-loop approval (P0 #3).

When the pipeline hits an approval gate it:
1. Persists the approval request + state snapshot to ``runtime_approval_requests``
2. Suspends execution and returns ``status=pending_approval`` to the backend
3. The backend exposes the approval API to authorised reviewers

Reviewers submit decisions via the API, which:
1. Validates the reviewer's role and scope
2. Updates the DB record with the decision
3. Records the review decision in the runtime audit log
4. Returns the updated request so the workflow can resume

The ``DurableApprovalQueue`` (default) writes through to PostgreSQL.
``InMemoryApprovalQueue`` is kept for tests and local development.

No approval is ever auto-approved.  A missing reviewer or decision is
treated as still-pending, not approved.
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


class PendingApprovalRequest(BaseModel):
    """A serialisable view of an approval request."""

    request_id: str = Field(default_factory=lambda: f"apr_{uuid.uuid4().hex[:10]}")
    investigation_id: str
    gate_type: str
    summary: str = ""
    findings: dict[str, Any] = Field(default_factory=dict)
    options: list[str] = Field(
        default_factory=lambda: ["approve", "reject", "request_changes"]
    )
    created_at: float = Field(default_factory=time.time)
    expires_at: float | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    state_snapshot: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    triggered_by: str = "supervisor"


class ApprovalDecision(BaseModel):
    """A submitted approval decision."""

    decision: str  # approve | reject | request_changes
    reviewer: str
    comments: str = ""
    conditions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class ApprovalQueueBase(ABC):
    """Protocol shared by all approval queue backends."""

    @abstractmethod
    async def submit_request(
        self,
        investigation_id: str,
        gate_type: str,
        state_snapshot: dict[str, Any],
        *,
        summary: str = "",
        findings: dict[str, Any] | None = None,
        options: list[str] | None = None,
        trace_id: str | None = None,
        triggered_by: str = "supervisor",
        timeout_seconds: float | None = None,
    ) -> PendingApprovalRequest: ...

    @abstractmethod
    async def submit_decision(
        self,
        request_id: str,
        decision: ApprovalDecision,
    ) -> PendingApprovalRequest | None: ...

    @abstractmethod
    async def get_request(self, request_id: str) -> PendingApprovalRequest | None: ...

    @abstractmethod
    async def get_decision(self, request_id: str) -> ApprovalDecision | None: ...

    @abstractmethod
    async def get_pending_for_investigation(
        self, investigation_id: str
    ) -> list[PendingApprovalRequest]: ...

    @abstractmethod
    async def get_all_pending(self) -> list[PendingApprovalRequest]: ...

    @abstractmethod
    async def cancel(self, request_id: str) -> bool: ...

    def count(self) -> int:  # noqa: D102
        return 0

    def summary(self) -> dict[str, Any]:  # noqa: D102
        return {"pending_count": 0}

    async def is_approved(self, request_id: str) -> bool:
        """Return True if the request has been approved."""
        req = await self.get_request(request_id)
        if req is None:
            return False
        return req.status.value == "approved"

    async def is_pending(self, request_id: str) -> bool:
        """Return True if the request is still pending."""
        req = await self.get_request(request_id)
        if req is None:
            return False
        return req.status.value == "pending"


# ---------------------------------------------------------------------------
# In-memory implementation (tests / local dev only)
# ---------------------------------------------------------------------------


class InMemoryApprovalQueue(ApprovalQueueBase):
    """Async in-memory approval queue.

    Suitable for tests and local development only.  State is lost on
    process restart — do not use in production.
    """

    def __init__(self, default_timeout_seconds: float = 600.0) -> None:
        self._requests: dict[str, PendingApprovalRequest] = {}
        self._decisions: dict[str, ApprovalDecision] = {}
        self._default_timeout = default_timeout_seconds

    async def submit_request(
        self,
        investigation_id: str,
        gate_type: str,
        state_snapshot: dict[str, Any],
        *,
        summary: str = "",
        findings: dict[str, Any] | None = None,
        options: list[str] | None = None,
        trace_id: str | None = None,
        triggered_by: str = "supervisor",
        timeout_seconds: float | None = None,
    ) -> PendingApprovalRequest:
        timeout = timeout_seconds or self._default_timeout
        request = PendingApprovalRequest(
            investigation_id=investigation_id,
            gate_type=gate_type,
            summary=summary,
            findings=findings or {},
            options=options or ["approve", "reject", "request_changes"],
            expires_at=time.time() + timeout,
            state_snapshot=state_snapshot,
            trace_id=trace_id,
            triggered_by=triggered_by,
        )
        self._requests[request.request_id] = request
        logger.info(
            "InMemoryApprovalQueue: request %s submitted "
            "(investigation=%s, gate=%s)",
            request.request_id,
            investigation_id,
            gate_type,
        )
        return request

    async def submit_decision(
        self,
        request_id: str,
        decision: ApprovalDecision,
    ) -> PendingApprovalRequest | None:
        request = self._requests.get(request_id)
        if request is None:
            return None
        if request.status != ApprovalStatus.PENDING:
            return request

        self._decisions[request_id] = decision
        _status_map = {
            "approve": ApprovalStatus.APPROVED,
            "reject": ApprovalStatus.REJECTED,
            "request_changes": ApprovalStatus.CHANGES_REQUESTED,
        }
        request.status = _status_map.get(
            decision.decision, ApprovalStatus.PENDING
        )
        logger.info(
            "InMemoryApprovalQueue: decision '%s' by '%s' for request %s",
            decision.decision,
            decision.reviewer,
            request_id,
        )
        return request

    async def get_request(self, request_id: str) -> PendingApprovalRequest | None:
        req = self._requests.get(request_id)
        if req and req.expires_at and time.time() > req.expires_at:
            req.status = ApprovalStatus.EXPIRED
        return req

    async def get_decision(self, request_id: str) -> ApprovalDecision | None:
        return self._decisions.get(request_id)

    async def get_pending_for_investigation(
        self, investigation_id: str
    ) -> list[PendingApprovalRequest]:
        return [
            r
            for r in self._requests.values()
            if r.investigation_id == investigation_id
            and r.status == ApprovalStatus.PENDING
        ]

    async def get_all_pending(self) -> list[PendingApprovalRequest]:
        now = time.time()
        pending: list[PendingApprovalRequest] = []
        for r in self._requests.values():
            if r.status == ApprovalStatus.PENDING:
                if r.expires_at and now > r.expires_at:
                    r.status = ApprovalStatus.EXPIRED
                else:
                    pending.append(r)
        return pending

    async def cancel(self, request_id: str) -> bool:
        req = self._requests.get(request_id)
        if req is None or req.status != ApprovalStatus.PENDING:
            return False
        req.status = ApprovalStatus.CANCELLED
        return True

    def count(self) -> int:
        return sum(
            1
            for r in self._requests.values()
            if r.status == ApprovalStatus.PENDING
        )

    def summary(self) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        for r in self._requests.values():
            status_counts[r.status.value] = (
                status_counts.get(r.status.value, 0) + 1
            )
        return {
            "total_requests": len(self._requests),
            "status_counts": status_counts,
            "pending_count": self.count(),
        }


# ---------------------------------------------------------------------------
# Durable DB-backed implementation (P0 #3)
# ---------------------------------------------------------------------------


class DurableApprovalQueue(ApprovalQueueBase):
    """PostgreSQL-backed approval queue (production).

    Approval requests are persisted to ``runtime_approval_requests``
    immediately.  For high-impact approval gates, the queue FAILS CLOSED
    (P0 #9): database errors raise so the workflow stays paused and no
    decision is accepted without durable persistence.

    Designed to be used as a singleton shared across the FastAPI app.
    Inject via dependency injection; do NOT create per-request.
    """

    def __init__(
        self,
        session_factory: Any,  # async_sessionmaker[AsyncSession]
        default_timeout_seconds: float = 3600.0,
    ) -> None:
        self._session_factory = session_factory
        self._default_timeout = default_timeout_seconds
        self._mirror: dict[str, PendingApprovalRequest] = {}

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def submit_request(
        self,
        investigation_id: str,
        gate_type: str,
        state_snapshot: dict[str, Any],
        *,
        summary: str = "",
        findings: dict[str, Any] | None = None,
        options: list[str] | None = None,
        trace_id: str | None = None,
        triggered_by: str = "supervisor",
        timeout_seconds: float | None = None,
    ) -> PendingApprovalRequest:
        from mnemos.models.entities import RuntimeApprovalRequest

        timeout = timeout_seconds or self._default_timeout
        request_id = f"apr_{uuid.uuid4().hex[:10]}"
        now = datetime.now(UTC)
        expires_dt = now + timedelta(seconds=timeout)

        request = PendingApprovalRequest(
            request_id=request_id,
            investigation_id=investigation_id,
            gate_type=gate_type,
            summary=summary,
            findings=findings or {},
            options=options or ["approve", "reject", "request_changes"],
            created_at=now.timestamp(),
            expires_at=expires_dt.timestamp(),
            state_snapshot=state_snapshot,
            trace_id=trace_id,
            triggered_by=triggered_by,
        )

        async with self._session_factory() as db:
            try:
                db.add(
                    RuntimeApprovalRequest(
                        id=request_id,
                        investigation_id=investigation_id,
                        trace_id=trace_id,
                        gate_type=gate_type,
                        summary=summary,
                        findings_json=findings or {},
                        options_json=options or [
                            "approve",
                            "reject",
                            "request_changes",
                        ],
                        triggered_by=triggered_by,
                        status="pending",
                        state_snapshot=state_snapshot,
                        created_at=now,
                        expires_at=expires_dt,
                    )
                )
                await db.commit()
                self._mirror[request_id] = request
                logger.info(
                    "DurableApprovalQueue: persisted request %s "
                    "(investigation=%s, gate=%s)",
                    request_id,
                    investigation_id,
                    gate_type,
                )
            except Exception as exc:
                logger.error(
                    "DurableApprovalQueue: failed to persist request %s to DB: %s "
                    "(approval NOT submitted — fail closed)",
                    request_id,
                    exc,
                )
                await db.rollback()
                raise RuntimeError(
                    f"Approval request {request_id} could not be persisted: "
                    f"database unavailable"
                ) from exc

        return request

    async def submit_decision(
        self,
        request_id: str,
        decision: ApprovalDecision,
    ) -> PendingApprovalRequest | None:
        """Persist the reviewer's decision and update the request status.

        The decision is written atomically.  If the request is not
        pending (already decided or expired) the call is rejected.
        """
        from mnemos.models.entities import RuntimeApprovalRequest

        _status_map = {
            "approve": "approved",
            "reject": "rejected",
            "request_changes": "changes_requested",
        }
        new_status = _status_map.get(decision.decision)
        if new_status is None:
            logger.warning(
                "DurableApprovalQueue: invalid decision value '%s' "
                "for request %s — must be approve|reject|request_changes",
                decision.decision,
                request_id,
            )
            return None

        now = datetime.now(UTC)

        try:
            async with self._session_factory() as db:
                from sqlalchemy import select

                row = await db.scalar(
                    select(RuntimeApprovalRequest)
                    .where(RuntimeApprovalRequest.id == request_id)
                    .with_for_update()
                )
                if row is None:
                    logger.warning(
                        "DurableApprovalQueue: request %s not found", request_id
                    )
                    return None
                if row.status != "pending":
                    logger.warning(
                        "DurableApprovalQueue: request %s already in state '%s'",
                        request_id,
                        row.status,
                    )
                    # Return current DB state
                    return _row_to_model(row)

                row.status = new_status
                row.reviewer = decision.reviewer
                row.reviewer_decision = decision.decision
                row.reviewer_comments = decision.comments
                row.conditions_json = decision.conditions
                row.decided_at = now
                await db.commit()
                await db.refresh(row)
                result = _row_to_model(row)

            # Update in-memory mirror
            if request_id in self._mirror:
                self._mirror[request_id].status = ApprovalStatus(new_status)

            logger.info(
                "DurableApprovalQueue: decision '%s' by '%s' persisted for %s",
                decision.decision,
                decision.reviewer,
                request_id,
            )
            return result

        except Exception as exc:
            logger.error(
                "DurableApprovalQueue: failed to persist decision for %s: %s",
                request_id,
                exc,
            )
            await db.rollback()
            raise RuntimeError(
                f"Approval decision for {request_id} could not be persisted: "
                f"database unavailable"
            ) from exc

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_request(self, request_id: str) -> PendingApprovalRequest | None:
        from mnemos.models.entities import RuntimeApprovalRequest

        try:
            async with self._session_factory() as db:
                from sqlalchemy import select

                row = await db.scalar(
                    select(RuntimeApprovalRequest).where(
                        RuntimeApprovalRequest.id == request_id
                    )
                )
                if row is None:
                    return self._mirror.get(request_id)
                return _row_to_model(row)
        except Exception as exc:
            logger.warning(
                "DurableApprovalQueue: DB read failed for %s: %s "
                "(using mirror)",
                request_id,
                exc,
            )
            return self._mirror.get(request_id)

    async def get_decision(self, request_id: str) -> ApprovalDecision | None:
        req = await self.get_request(request_id)
        if req is None or req.status == ApprovalStatus.PENDING:
            return None
        # Reconstruct decision from the stored fields; these are set by submit_decision
        # For in-memory mirror we don't have separate decision objects, so we
        # return None when the request hasn't been decided yet.
        if req.status not in (
            ApprovalStatus.APPROVED,
            ApprovalStatus.REJECTED,
            ApprovalStatus.CHANGES_REQUESTED,
        ):
            return None
        # Try DB for reviewer details
        from mnemos.models.entities import RuntimeApprovalRequest

        try:
            async with self._session_factory() as db:
                from sqlalchemy import select

                row = await db.scalar(
                    select(RuntimeApprovalRequest).where(
                        RuntimeApprovalRequest.id == request_id
                    )
                )
                if row and row.reviewer_decision:
                    return ApprovalDecision(
                        decision=row.reviewer_decision,
                        reviewer=row.reviewer or "unknown",
                        comments=row.reviewer_comments or "",
                        conditions=row.conditions_json or [],
                    )
        except Exception:
            logger.warning("Failed to read decision for request '%s'", request_id, exc_info=True)
        return None

    async def get_pending_for_investigation(
        self, investigation_id: str
    ) -> list[PendingApprovalRequest]:
        from mnemos.models.entities import RuntimeApprovalRequest

        try:
            async with self._session_factory() as db:
                from sqlalchemy import select

                rows = (
                    await db.scalars(
                        select(RuntimeApprovalRequest)
                        .where(
                            RuntimeApprovalRequest.investigation_id
                            == investigation_id
                        )
                        .where(RuntimeApprovalRequest.status == "pending")
                        .order_by(RuntimeApprovalRequest.created_at.asc())
                    )
                ).all()
                return [_row_to_model(r) for r in rows]
        except Exception as exc:
            logger.warning(
                "DurableApprovalQueue: DB read failed for investigation %s: %s",
                investigation_id,
                exc,
            )
            return [
                r
                for r in self._mirror.values()
                if r.investigation_id == investigation_id
                and r.status == ApprovalStatus.PENDING
            ]

    async def get_all_pending(self) -> list[PendingApprovalRequest]:
        from mnemos.models.entities import RuntimeApprovalRequest

        try:
            async with self._session_factory() as db:
                from sqlalchemy import select

                rows = (
                    await db.scalars(
                        select(RuntimeApprovalRequest)
                        .where(RuntimeApprovalRequest.status == "pending")
                        .order_by(RuntimeApprovalRequest.created_at.asc())
                    )
                ).all()
                now = datetime.now(UTC)
                result: list[PendingApprovalRequest] = []
                for r in rows:
                    # Expire rows past their expiry time
                    if r.expires_at and r.expires_at < now:
                        r.status = "expired"
                        try:
                            await db.commit()
                        except Exception as exc:
                            logger.warning(
                                "Failed to expire request %s: %s", r.id, exc,
                            )
                            await db.rollback()
                    else:
                        result.append(_row_to_model(r))
                return result
        except Exception as exc:
            logger.warning(
                "DurableApprovalQueue: DB read for get_all_pending failed: %s",
                exc,
            )
            return await InMemoryApprovalQueue._get_all_pending_from(
                self._mirror
            )

    async def cancel(self, request_id: str) -> bool:
        from mnemos.models.entities import RuntimeApprovalRequest

        try:
            async with self._session_factory() as db:
                from sqlalchemy import select

                row = await db.scalar(
                    select(RuntimeApprovalRequest)
                    .where(RuntimeApprovalRequest.id == request_id)
                    .with_for_update()
                )
                if row is None or row.status != "pending":
                    return False
                row.status = "cancelled"
                row.decided_at = datetime.now(UTC)
                await db.commit()

            if request_id in self._mirror:
                self._mirror[request_id].status = ApprovalStatus.CANCELLED
            return True

        except Exception as exc:
            logger.warning(
                "DurableApprovalQueue: cancel %s failed: %s", request_id, exc
            )
            req = self._mirror.get(request_id)
            if req and req.status == ApprovalStatus.PENDING:
                req.status = ApprovalStatus.CANCELLED
                return True
            return False

    def count(self) -> int:
        return sum(
            1
            for r in self._mirror.values()
            if r.status == ApprovalStatus.PENDING
        )

    def summary(self) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        for r in self._mirror.values():
            status_counts[r.status.value] = (
                status_counts.get(r.status.value, 0) + 1
            )
        return {
            "total_requests_mirrored": len(self._mirror),
            "status_counts": status_counts,
            "pending_count": self.count(),
        }


# ---------------------------------------------------------------------------
# Default alias used by the rest of the codebase
# ---------------------------------------------------------------------------

# Resolved at import time: DurableApprovalQueue when a session factory can
# be injected, InMemoryApprovalQueue for standalone / test usage.
ApprovalQueue = InMemoryApprovalQueue  # overridden in app initialisation


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _row_to_model(row: Any) -> PendingApprovalRequest:
    """Convert a RuntimeApprovalRequest ORM row to PendingApprovalRequest."""
    expires_ts = row.expires_at.timestamp() if row.expires_at else None
    created_ts = row.created_at.timestamp() if row.created_at else time.time()
    return PendingApprovalRequest(
        request_id=row.id,
        investigation_id=row.investigation_id,
        gate_type=row.gate_type,
        summary=row.summary or "",
        findings=row.findings_json or {},
        options=row.options_json or ["approve", "reject", "request_changes"],
        created_at=created_ts,
        expires_at=expires_ts,
        status=ApprovalStatus(row.status),
        state_snapshot=row.state_snapshot or {},
        trace_id=row.trace_id,
        triggered_by=row.triggered_by or "supervisor",
    )
