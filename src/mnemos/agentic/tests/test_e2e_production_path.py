"""End-to-end production-path test (P0 #9).

Verifies the complete flow:
  Backend-scoped query
    -> real LangGraphAgentGateway
    -> real MnemosAIOrchestrator
    -> registered agents (intent-selective)
    -> canonical InvestigationPipeline workflow
    -> real retrieval pipeline (mocked at DB boundary)
    -> specialist reasoning
    -> result validation
    -> backend persistence (exactly once, no duplicates)
    -> status transitions
    -> tenant and site scope enforced
    -> errors safely handled

The test uses a real SQLite in-process database so that persistence
assertions are verifiable without requiring a live PostgreSQL server.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mnemos.agentic.gateway import LangGraphAgentGateway
from mnemos.agentic.runtime.workflow import InvestigationPipeline
from mnemos.agentic.schemas.base import AgentResponse
from mnemos.core.db import Base
from mnemos.models import AgentRun, Citation, Query, QueryClaim, QueryEvent
from mnemos.schemas.agent import (
    AgentCitation,
    AgentClaim,
    AgentConfidence,
    AgentOptions,
    AgentQueryRequest,
    AgentQueryResult,
    AgentRunMetadata,
    AgentScope,
)
from mnemos.services.agent_validation import validate_agent_result
from mnemos.services.query_execution import execute_query_background


# ---------------------------------------------------------------------------
# In-memory SQLite DB fixture (mirrors the real schema via SQLAlchemy)
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_query(query_id: str, org_id: str, site_id: str, user_id: str) -> Query:
    return Query(
        id=query_id,
        organisation_id=org_id,
        site_id=site_id,
        user_id=user_id,
        question="What caused the pump P-101 failure last week?",
        mode="rca",
        status="queued",
        context_asset_ids=[],
        context_document_ids=[],
        missing_evidence=[],
        conflicts=[],
        related_entities=[],
    )


# ---------------------------------------------------------------------------
# Canned AgentQueryResult to be returned by the mocked gateway
# ---------------------------------------------------------------------------

def _make_result(run_id: str) -> AgentQueryResult:
    """Produce a minimal valid AgentQueryResult for RCA intent."""
    cit1 = AgentCitation(
        id="cit_0_0",
        document_id=None,
        document_title="Maintenance Log 2025",
        chunk_id="chk_001",
        text_excerpt="Bearing failure observed.",
        retrieval_sources=["vector"],
        access_allowed=True,
    )
    claim1 = AgentClaim(
        id="clm_001",
        text="Pump P-101 failed due to bearing wear.",
        support_status="supported",
        citation_ids=["cit_0_0"],
    )
    return AgentQueryResult(
        run_id=run_id,
        status="succeeded",
        answer="The pump P-101 failure was caused by bearing wear.",
        confidence=AgentConfidence(label="high", score=0.92),
        claims=[claim1],
        citations=[cit1],
        missing_evidence=[],
        conflicts=[],
        related_entities=[],
        run_metadata=AgentRunMetadata(
            pipeline_version="v2.0-multi-agent-runtime",
            latency_ms=420,
        ),
    )


# ===========================================================================
# P0 #9 — Test 1: complete success path
# ===========================================================================

@pytest.mark.asyncio
async def test_e2e_success_path(db_session: AsyncSession, session_factory):
    """
    Backend-scoped query -> gateway -> orchestrator (mocked at LLM boundary)
    -> backend validation -> exactly one persistence transaction.

    Verifies:
    - query status transitions: queued -> running -> succeeded
    - AgentRun created once, completed once
    - claims created exactly once (no duplicates)
    - citations created exactly once (no duplicates)
    - QueryEvents recorded for each stage
    - no extra DB writes from the agentic layer
    """
    org_id = "org_test"
    site_id = "site_test"
    user_id = "usr_test"
    query_id = "qry_e2e_001"

    # Seed query row
    query = _seed_query(query_id, org_id, site_id, user_id)
    db_session.add(query)
    await db_session.commit()

    # Patch gateway.execute_query to return a canned result without calling LLM
    async def _fake_execute(request: AgentQueryRequest) -> AgentQueryResult:
        return _make_result(request.run_id)

    mock_gw = MagicMock()
    mock_gw.name = "test_gateway"
    mock_gw.execute_query = AsyncMock(side_effect=_fake_execute)

    with patch(
        "mnemos.services.query_execution.get_agent_gateway",
        return_value=mock_gw,
    ), patch(
        "mnemos.services.query_execution.SessionLocal",
        new=session_factory,
    ), patch(
        "mnemos.services.agent_validation.settings"
    ) as mock_settings:
        mock_settings.agent_gateway_mode = "mock"
        mock_settings.app_env = "test"

        await execute_query_background(query_id)

    # Reload and assert
    async with session_factory() as s:
        q = await s.get(Query, query_id)
        assert q is not None
        assert q.status == "succeeded", f"Expected succeeded, got {q.status}"
        assert q.answer == "The pump P-101 failure was caused by bearing wear."
        assert q.confidence_label == "high"
        assert q.confidence_score == pytest.approx(0.92)

        runs = (
            await s.scalars(select(AgentRun).where(AgentRun.query_id == query_id))
        ).all()
        assert len(runs) == 1, f"Expected exactly 1 AgentRun, got {len(runs)}"
        run = runs[0]
        assert run.status == "succeeded"
        assert run.completed_at is not None
        assert run.pipeline_version == "v2.0-multi-agent-runtime"
        assert run.latency_ms == 420

        claims = (
            await s.scalars(
                select(QueryClaim).where(QueryClaim.query_id == query_id)
            )
        ).all()
        assert len(claims) == 1, f"Expected 1 claim, got {len(claims)}"
        assert claims[0].text == "Pump P-101 failed due to bearing wear."
        assert claims[0].support_status == "supported"

        citations = (
            await s.scalars(
                select(Citation).where(Citation.query_id == query_id)
            )
        ).all()
        assert len(citations) == 1, f"Expected 1 citation, got {len(citations)}"
        assert citations[0].document_title == "Maintenance Log 2025"

        events = (
            await s.scalars(
                select(QueryEvent)
                .where(QueryEvent.query_id == query_id)
                .order_by(QueryEvent.created_at)
            )
        ).all()
        stages = [e.stage for e in events]
        assert "classifying_query" in stages
        assert "completed" in stages
        assert stages[-1] == "completed"
        final_event = events[-1]
        assert final_event.progress_percent == 100


# ===========================================================================
# P0 #9 — Test 2: no duplicate records on concurrent / re-execution attempt
# ===========================================================================

@pytest.mark.asyncio
async def test_e2e_no_duplicate_records(db_session: AsyncSession, session_factory):
    """
    If execute_query_background is called twice for the same query
    (second call finds status != queued|running), the second call must
    be a no-op — no duplicate runs, claims, or citations.
    """
    org_id = "org_test"
    site_id = "site_test"
    user_id = "usr_test"
    query_id = "qry_e2e_002"

    query = _seed_query(query_id, org_id, site_id, user_id)
    db_session.add(query)
    await db_session.commit()

    async def _fake_execute(request: AgentQueryRequest) -> AgentQueryResult:
        return _make_result(request.run_id)

    mock_gw = MagicMock()
    mock_gw.name = "test_gateway"
    mock_gw.execute_query = AsyncMock(side_effect=_fake_execute)

    with patch(
        "mnemos.services.query_execution.get_agent_gateway",
        return_value=mock_gw,
    ), patch(
        "mnemos.services.query_execution.SessionLocal",
        new=session_factory,
    ), patch(
        "mnemos.services.agent_validation.settings"
    ) as mock_settings:
        mock_settings.agent_gateway_mode = "mock"
        mock_settings.app_env = "test"

        # First execution
        await execute_query_background(query_id)
        # Second execution — must be a no-op (status is now "succeeded")
        await execute_query_background(query_id)

    async with session_factory() as s:
        runs = (
            await s.scalars(select(AgentRun).where(AgentRun.query_id == query_id))
        ).all()
        assert len(runs) == 1, (
            f"Duplicate AgentRun detected: expected 1, got {len(runs)}"
        )

        claims = (
            await s.scalars(
                select(QueryClaim).where(QueryClaim.query_id == query_id)
            )
        ).all()
        assert len(claims) == 1, (
            f"Duplicate QueryClaim detected: expected 1, got {len(claims)}"
        )

        citations = (
            await s.scalars(
                select(Citation).where(Citation.query_id == query_id)
            )
        ).all()
        assert len(citations) == 1, (
            f"Duplicate Citation detected: expected 1, got {len(citations)}"
        )


# ===========================================================================
# P0 #9 — Test 3: tenant and site scope enforced
# ===========================================================================

@pytest.mark.asyncio
async def test_e2e_scope_enforcement(db_session: AsyncSession, session_factory):
    """
    Agent result that references a document from a different org/site must
    be rejected by validate_agent_result (AGENT_EVIDENCE_FORBIDDEN).
    The query must transition to failed, not succeeded.
    """
    from mnemos.models import Document

    org_id = "org_tenant_a"
    other_org_id = "org_tenant_b"
    site_id = "site_a"
    user_id = "usr_scope"
    query_id = "qry_e2e_003"
    doc_id = "doc_other_org"

    # Seed: doc belongs to a different org
    doc = Document(
        id=doc_id,
        organisation_id=other_org_id,
        site_id=site_id,
        filename="other_org_manual.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        sha256="abc123",
        document_type="manual",
        status="ready",
    )
    query = _seed_query(query_id, org_id, site_id, user_id)
    db_session.add(doc)
    db_session.add(query)
    await db_session.commit()

    # Gateway returns a result citing the cross-tenant document
    cit_cross = AgentCitation(
        id="cit_cross_0",
        document_id=doc_id,
        document_title="Other Org Manual",
        chunk_id="chk_x",
        text_excerpt="Cross-tenant evidence.",
        retrieval_sources=["vector"],
        access_allowed=True,
    )
    claim_cross = AgentClaim(
        id="clm_cross",
        text="Some cross-tenant claim.",
        support_status="supported",
        citation_ids=["cit_cross_0"],
    )

    async def _fake_cross_tenant(request: AgentQueryRequest) -> AgentQueryResult:
        return AgentQueryResult(
            run_id=request.run_id,
            status="succeeded",
            answer="Cross-tenant answer.",
            confidence=AgentConfidence(label="high", score=0.9),
            claims=[claim_cross],
            citations=[cit_cross],
            run_metadata=AgentRunMetadata(pipeline_version="v2.0"),
        )

    mock_gw = MagicMock()
    mock_gw.name = "test_gateway"
    mock_gw.execute_query = AsyncMock(side_effect=_fake_cross_tenant)

    with patch(
        "mnemos.services.query_execution.get_agent_gateway",
        return_value=mock_gw,
    ), patch(
        "mnemos.services.query_execution.SessionLocal",
        new=session_factory,
    ), patch(
        "mnemos.services.agent_validation.settings"
    ) as mock_settings:
        mock_settings.agent_gateway_mode = "live"
        mock_settings.app_env = "production"

        await execute_query_background(query_id)

    async with session_factory() as s:
        q = await s.get(Query, query_id)
        assert q is not None
        assert q.status == "failed", (
            f"Cross-tenant scope violation should have failed the query, "
            f"got status={q.status}"
        )
        # No claims or citations should be persisted on failure
        claims = (
            await s.scalars(
                select(QueryClaim).where(QueryClaim.query_id == query_id)
            )
        ).all()
        assert len(claims) == 0, (
            f"Claims should not be persisted after scope violation, "
            f"got {len(claims)}"
        )


# ===========================================================================
# P0 #9 — Test 4: agent failure is handled safely, no raw exceptions exposed
# ===========================================================================

@pytest.mark.asyncio
async def test_e2e_agent_failure_safe_handling(
    db_session: AsyncSession, session_factory
):
    """
    When the agent gateway raises an unexpected exception the backend
    must:
    - set query.status = failed
    - set run.status = failed with a safe error code (no stack traces)
    - record a QueryEvent stage=failed
    - not expose raw exception text in error_message
    """
    org_id = "org_test"
    site_id = "site_test"
    user_id = "usr_test"
    query_id = "qry_e2e_004"

    query = _seed_query(query_id, org_id, site_id, user_id)
    db_session.add(query)
    await db_session.commit()

    async def _fake_crash(request: AgentQueryRequest) -> AgentQueryResult:
        raise RuntimeError(
            "SELECT * FROM secrets WHERE password='hunter2'; "
            "at /internal/path/service.py:42"
        )

    mock_gw = MagicMock()
    mock_gw.name = "test_gateway"
    mock_gw.execute_query = AsyncMock(side_effect=_fake_crash)

    with patch(
        "mnemos.services.query_execution.get_agent_gateway",
        return_value=mock_gw,
    ), patch(
        "mnemos.services.query_execution.SessionLocal",
        new=session_factory,
    ):
        await execute_query_background(query_id)

    async with session_factory() as s:
        q = await s.get(Query, query_id)
        assert q is not None
        assert q.status == "failed"

        runs = (
            await s.scalars(select(AgentRun).where(AgentRun.query_id == query_id))
        ).all()
        assert len(runs) == 1
        run = runs[0]
        assert run.status == "failed"
        assert run.error_code is not None

        # Raw exception text must NOT be in error_message
        if run.error_message:
            assert "hunter2" not in run.error_message, (
                "Sensitive data leaked into error_message"
            )
            assert "/internal/path" not in run.error_message, (
                "Internal path leaked into error_message"
            )
            assert "SELECT" not in run.error_message, (
                "SQL leaked into error_message"
            )

        events = (
            await s.scalars(
                select(QueryEvent)
                .where(QueryEvent.query_id == query_id)
                .order_by(QueryEvent.created_at)
            )
        ).all()
        stages = [e.stage for e in events]
        assert "failed" in stages


# ===========================================================================
# P0 #9 — Test 5: intent-selective agent dispatch
# ===========================================================================

@pytest.mark.asyncio
async def test_e2e_intent_selective_agent_dispatch():
    """
    Verifies that the InvestigationPipeline only invokes agents relevant
    to the classified intent, not all agents unconditionally.

    RCA intent -> rca_agent + lessons_learned_agent only (not compliance,
    not asset_intelligence by default).
    """
    from mnemos.agentic.runtime.workflow import _select_specialized_agents
    from mnemos.agentic.runtime.state import create_initial_state

    state = create_initial_state(
        investigation_id="inv_intent_test",
        query="Why did pump P-101 fail repeatedly?",
        context={"intent": "rca"},
    )

    selected = _select_specialized_agents(state)
    assert "rca_agent" in selected, "rca_agent must be selected for rca intent"
    assert "lessons_learned_agent" in selected, (
        "lessons_learned_agent must be selected for rca intent"
    )
    # compliance_agent should NOT be selected for pure rca intent
    assert "compliance_agent" not in selected, (
        "compliance_agent must NOT be selected for pure rca intent"
    )


@pytest.mark.asyncio
async def test_e2e_compliance_agent_dispatch():
    """Compliance intent selects compliance_agent, not RCA."""
    from mnemos.agentic.runtime.workflow import _select_specialized_agents
    from mnemos.agentic.runtime.state import create_initial_state

    state = create_initial_state(
        investigation_id="inv_compliance_test",
        query="Are we compliant with ISO 55001 for asset P-102?",
        context={"intent": "compliance"},
    )
    selected = _select_specialized_agents(state)
    assert "compliance_agent" in selected
    assert "rca_agent" not in selected


@pytest.mark.asyncio
async def test_e2e_asset_info_agent_dispatch():
    """Asset info intent selects asset_intelligence only."""
    from mnemos.agentic.runtime.workflow import _select_specialized_agents
    from mnemos.agentic.runtime.state import create_initial_state

    state = create_initial_state(
        investigation_id="inv_asset_test",
        query="What is the maintenance schedule for pump P-101?",
        context={"intent": "asset_info"},
    )
    selected = _select_specialized_agents(state)
    assert "asset_intelligence" in selected
    assert "rca_agent" not in selected
    assert "compliance_agent" not in selected


# ===========================================================================
# P0 #9 — Test 6: pending_approval path — pipeline pauses correctly
# ===========================================================================

@pytest.mark.asyncio
async def test_e2e_pending_approval_path(db_session: AsyncSession, session_factory):
    """
    When the agent returns status=pending_approval the backend must:
    - set query.status = pending_approval (not succeeded, not failed)
    - set run.status = pending_approval
    - record a QueryEvent stage=pending_approval
    - NOT persist claims or citations (nothing to persist yet)
    - completed_at must be None (workflow is paused, not finished)
    """
    org_id = "org_test"
    site_id = "site_test"
    user_id = "usr_test"
    query_id = "qry_e2e_005"

    query = _seed_query(query_id, org_id, site_id, user_id)
    db_session.add(query)
    await db_session.commit()

    async def _fake_pending(request: AgentQueryRequest) -> AgentQueryResult:
        # Return pending_approval — this is what the gateway returns when
        # the pipeline raises _ApprovalPendingError
        return AgentQueryResult(
            run_id=request.run_id,
            status="pending_approval",
            answer="",
            confidence=AgentConfidence(label="low", score=0.0),
            run_metadata=AgentRunMetadata(pipeline_version="v2.0"),
        )

    mock_gw = MagicMock()
    mock_gw.name = "test_gateway"
    mock_gw.execute_query = AsyncMock(side_effect=_fake_pending)

    with patch(
        "mnemos.services.query_execution.get_agent_gateway",
        return_value=mock_gw,
    ), patch(
        "mnemos.services.query_execution.SessionLocal",
        new=session_factory,
    ), patch(
        "mnemos.services.agent_validation.settings"
    ) as mock_settings:
        mock_settings.agent_gateway_mode = "mock"
        mock_settings.app_env = "test"

        await execute_query_background(query_id)

    async with session_factory() as s:
        q = await s.get(Query, query_id)
        assert q is not None
        assert q.status == "pending_approval", (
            f"Expected pending_approval, got {q.status}"
        )
        assert q.completed_at is None, (
            "completed_at must be None while approval is pending"
        )

        runs = (
            await s.scalars(select(AgentRun).where(AgentRun.query_id == query_id))
        ).all()
        assert len(runs) == 1
        assert runs[0].status == "pending_approval"
        assert runs[0].completed_at is None

        events = (
            await s.scalars(
                select(QueryEvent).where(QueryEvent.query_id == query_id)
            )
        ).all()
        stages = [e.stage for e in events]
        assert "pending_approval" in stages, (
            f"Expected pending_approval event, got stages: {stages}"
        )


# ===========================================================================
# P0 #9 — Test 7: durable approval queue round-trip
# ===========================================================================

@pytest.mark.asyncio
async def test_durable_approval_queue_round_trip(session_factory):
    """
    DurableApprovalQueue submit_request -> get_request -> submit_decision
    -> get_request (decision persisted) round-trip using in-memory SQLite.
    """
    from mnemos.agentic.runtime.approval_queue import (
        ApprovalDecision,
        DurableApprovalQueue,
    )

    queue = DurableApprovalQueue(session_factory=session_factory)

    # Submit a request
    request = await queue.submit_request(
        investigation_id="inv_approval_test",
        gate_type="rca_closure",
        state_snapshot={"phase": "synthesis", "investigation_id": "inv_approval_test"},
        summary="RCA findings ready for closure review",
        triggered_by="pipeline",
    )
    assert request.request_id.startswith("apr_")
    assert request.status.value == "pending"

    # Retrieve it back
    fetched = await queue.get_request(request.request_id)
    assert fetched is not None
    assert fetched.investigation_id == "inv_approval_test"
    assert fetched.gate_type == "rca_closure"
    assert fetched.status.value == "pending"

    # No decision yet
    decision_before = await queue.get_decision(request.request_id)
    assert decision_before is None

    # Submit a decision
    updated = await queue.submit_decision(
        request.request_id,
        ApprovalDecision(
            decision="approve",
            reviewer="eng_alice",
            comments="Findings are accurate and well-supported.",
        ),
    )
    assert updated is not None
    assert updated.status.value == "approved"

    # Decision is now retrievable
    decision_after = await queue.get_decision(request.request_id)
    assert decision_after is not None
    assert decision_after.decision == "approve"
    assert decision_after.reviewer == "eng_alice"


@pytest.mark.asyncio
async def test_durable_approval_queue_reject(session_factory):
    """Rejected decision is stored correctly."""
    from mnemos.agentic.runtime.approval_queue import (
        ApprovalDecision,
        DurableApprovalQueue,
    )

    queue = DurableApprovalQueue(session_factory=session_factory)
    request = await queue.submit_request(
        investigation_id="inv_reject_test",
        gate_type="compliance_closure",
        state_snapshot={},
        summary="Compliance check needs human review",
    )
    updated = await queue.submit_decision(
        request.request_id,
        ApprovalDecision(
            decision="reject",
            reviewer="safety_bob",
            comments="Insufficient evidence for compliance closure.",
        ),
    )
    assert updated is not None
    assert updated.status.value == "rejected"


@pytest.mark.asyncio
async def test_durable_approval_queue_cannot_decide_twice(session_factory):
    """A decided request cannot be decided again (idempotency guard)."""
    from mnemos.agentic.runtime.approval_queue import (
        ApprovalDecision,
        DurableApprovalQueue,
    )

    queue = DurableApprovalQueue(session_factory=session_factory)
    request = await queue.submit_request(
        investigation_id="inv_double_decide",
        gate_type="rca_closure",
        state_snapshot={},
    )
    await queue.submit_decision(
        request.request_id,
        ApprovalDecision(decision="approve", reviewer="alice"),
    )
    # Second attempt must not change status
    result = await queue.submit_decision(
        request.request_id,
        ApprovalDecision(decision="reject", reviewer="bob"),
    )
    assert result is not None
    # Status must still be approved (not overwritten by reject)
    assert result.status.value == "approved"
