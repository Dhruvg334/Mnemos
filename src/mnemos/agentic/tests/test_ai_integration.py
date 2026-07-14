from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.gateway import LangGraphAgentGateway
from mnemos.agentic.orchestrator import MnemosAIOrchestrator
from mnemos.agentic.schemas.base import (
    AgentResponse,
    ClaimSupportStatus,
    EvidenceSource,
    GroundedClaim,
    ProvenanceChain,
)
from mnemos.models import AgentRun, Query, QueryEvent


@pytest.fixture
def mock_db():
    db = MagicMock(spec=AsyncSession)
    db.get = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db

@pytest.fixture
def mock_query():
    return Query(
        id="qry_test_001",
        question="What is the pressure limit for P-101?",
        site_id="site_alpha",
        organisation_id="org_mnemos",
        user_id="usr_001",
        mode="general",
        status="queued"
    )

@pytest.fixture
def mock_run():
    return AgentRun(
        id="run_test_001",
        query_id="qry_test_001",
        status="running"
    )

@pytest.mark.asyncio
async def test_orchestrator_initialization(mock_db, mock_query, mock_run):
    """Verifies that the orchestrator loads context correctly."""
    mock_db.get.side_effect = [mock_query, mock_run]

    orchestrator = MnemosAIOrchestrator(mock_db)

    # We mock ainvoke to avoid real LLM calls during this check
    with patch.object(orchestrator.workflow, 'ainvoke', new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = {
            "final_response": AgentResponse(
                answer="Test Answer",
                confidence_score=0.9,
                claims=[],
                metadata={}
            )
        }

        # Mock astream to simulate progress
        with patch.object(orchestrator.workflow, 'astream', new_callable=MagicMock) as mock_stream:
            async def mock_stream_gen(*args, **kwargs):
                yield {"query_router": {}}
                yield {"response_composer": {}}
            mock_stream.return_value = mock_stream_gen()

            await orchestrator.run_query("qry_test_001", "run_test_001")

            # Verify status updates were attempted
            assert mock_db.add.called
            # Check if QueryEvent was added
            added_objects = [args[0] for args, _ in mock_db.add.call_args_list]
            assert any(isinstance(obj, QueryEvent) for obj in added_objects)

@pytest.mark.asyncio
async def test_result_persistence_mapping(mock_db, mock_query, mock_run):
    """Verifies that complex AI schemas map correctly to relational tables."""
    orchestrator = MnemosAIOrchestrator(mock_db)

    # Simulate a high-fidelity grounded response
    provenance = ProvenanceChain(
        evidence_region_id="reg_1",
        document_id="doc_1",
        document_version=1,
        source_filename="manual.pdf",
        sha256="abc",
        storage_key="s3://..."
    )
    evidence = EvidenceSource(
        text_excerpt="Pressure limit is 40 bar",
        provenance=provenance,
        confidence_score=1.0
    )
    claim = GroundedClaim(
        claim_id="clm_1",
        text="P-101 limit is 40 bar",
        status=ClaimSupportStatus.SUPPORTED,
        sources=[evidence]
    )
    response = AgentResponse(
        answer="The limit is 40 bar.",
        confidence_score=0.95,
        claims=[claim],
        metadata={}
    )

    await orchestrator._persist_final_report(mock_query, mock_run, response)

    # Verify DB updates
    assert mock_query.answer == "The limit is 40 bar."
    assert mock_query.status == "succeeded"
    assert mock_run.status == "succeeded"

    # Verify QueryClaim and Citation were added
    from mnemos.models import Citation, QueryClaim
    added_objects = [args[0] for args, _ in mock_db.add.call_args_list]
    assert any(isinstance(obj, QueryClaim) for obj in added_objects)
    assert any(isinstance(obj, Citation) for obj in added_objects)

@pytest.mark.asyncio
async def test_gateway_wrapping():
    """Ensures the LangGraph gateway correctly interfaces with the backend."""
    from mnemos.schemas.agent import AgentQueryRequest, AgentScope

    request = AgentQueryRequest(
        run_id="run_1",
        query_id="qry_1",
        organisation_id="org_1",
        site_id="site_1",
        user_id="usr_1",
        query_type="general",
        question="Testing?",
        scope=AgentScope()
    )

    gateway = LangGraphAgentGateway()

    # Mock the orchestrator inside the gateway
    with patch('mnemos.agentic.gateway.MnemosAIOrchestrator', autospec=True) as MockOrch:
        mock_inst = MockOrch.return_value
        mock_inst.run_query = AsyncMock(return_value=AgentResponse(
            answer="Gateway Success",
            confidence_score=1.0,
            claims=[],
            metadata={}
        ))

        result = await gateway.execute_query(request)

        assert result.status == "succeeded"
        assert result.answer == "Gateway Success"
        assert result.run_metadata.pipeline_version == "v1.0-langgraph"
