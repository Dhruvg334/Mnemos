from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.orchestrator import MnemosAIOrchestrator, _build_context
from mnemos.models import Membership
from mnemos.schemas.agent import AgentQueryRequest, AgentScope
from mnemos.services.query_execution import _resolve_query_membership


def _request() -> AgentQueryRequest:
    return AgentQueryRequest(
        run_id="run_contract_001",
        query_id="qry_contract_001",
        organisation_id="org_north",
        site_id="site_north",
        user_id="usr_engineer",
        membership_id="mem_site_engineer",
        actor_role="reliability_engineer",
        query_type="rca",
        question="Why has P-117 repeatedly failed?",
        scope=AgentScope(
            asset_ids=["ast_p117_n"],
            document_ids=["doc_003", "doc_004"],
            allowed_document_types=["work_order", "inspection"],
            access_classifications=["internal", "restricted_engineering"],
        ),
    )


def test_runtime_context_preserves_authorization_and_query_contract() -> None:
    context = _build_context(_request())

    assert context["question"] == "Why has P-117 repeatedly failed?"
    assert context["organisation_id"] == "org_north"
    assert context["site_id"] == "site_north"
    assert context["user_id"] == "usr_engineer"
    assert context["membership_id"] == "mem_site_engineer"
    assert context["role"] == "reliability_engineer"
    assert context["asset_ids"] == ["ast_p117_n"]
    assert context["document_ids"] == ["doc_003", "doc_004"]
    assert context["permitted_document_types"] == ["work_order", "inspection"]
    assert context["access_classifications"] == [
        "internal",
        "restricted_engineering",
    ]


@pytest.mark.asyncio
async def test_orchestrator_passes_complete_context_to_canonical_pipeline() -> None:
    db = MagicMock(spec=AsyncSession)
    orchestrator = MnemosAIOrchestrator(db)
    request = _request()

    with patch("mnemos.agentic.orchestrator.InvestigationPipeline", autospec=True) as pipeline_cls:
        pipeline = pipeline_cls.return_value
        pipeline.run = AsyncMock(
            return_value={
                "final_response": {
                    "answer": "Grounded answer",
                    "confidence_score": 0.9,
                    "claims": [],
                    "missing_evidence": [],
                    "metadata": {},
                }
            }
        )

        result = await orchestrator.run_query(request)

    assert result.answer == "Grounded answer"
    pipeline.run.assert_awaited_once()
    call = pipeline.run.await_args.kwargs
    assert call["investigation_id"] == request.query_id
    assert call["query"] == request.question
    assert call["context"]["membership_id"] == request.membership_id
    assert call["context"]["role"] == request.actor_role
    assert call["context"]["site_id"] == request.site_id
    assert call["context"]["asset_ids"] == request.scope.asset_ids


@pytest.mark.asyncio
async def test_membership_resolution_prefers_site_specific_role() -> None:
    db = MagicMock(spec=AsyncSession)
    site_membership = Membership(
        id="mem_site",
        user_id="usr_1",
        organisation_id="org_1",
        site_id="site_1",
        role="reliability_engineer",
    )
    organisation_membership = Membership(
        id="mem_org",
        user_id="usr_1",
        organisation_id="org_1",
        site_id=None,
        role="organisation_admin",
    )
    scalar_result = MagicMock()
    scalar_result.all.return_value = [organisation_membership, site_membership]
    db.scalars = AsyncMock(return_value=scalar_result)

    result = await _resolve_query_membership(
        db,
        user_id="usr_1",
        organisation_id="org_1",
        site_id="site_1",
    )

    assert result.id == "mem_site"
    assert result.role == "reliability_engineer"
