from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.gateway import LangGraphAgentGateway
from mnemos.agentic.orchestrator import MnemosAIOrchestrator
from mnemos.agentic.runtime import (
    AgentCapability,
    AgentRole,
)
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
async def test_orchestrator_auto_registers_agents(mock_db):
    """Verifies that the orchestrator auto-registers all available agents on init."""
    orchestrator = MnemosAIOrchestrator(mock_db)

    # The registry should contain agents that were successfully imported
    registered = orchestrator._registry.list_agents()
    registered_names = {r.name for r in registered}

    # At least the agent classes that can be imported should be registered
    # (all 11 agents are in-tree, so all should register)
    expected_names = {
        "query_router",
        "retrieval_planner",
        "evidence_retrieval",
        "evidence_verification",
        "retrieval_reflection",
        "rca_agent",
        "compliance_agent",
        "asset_intelligence",
        "lessons_learned_agent",
        "expert_knowledge_agent",
        "report_composer",
    }
    assert expected_names == registered_names, (
        f"Missing agents: {expected_names - registered_names}, "
        f"Unexpected agents: {registered_names - expected_names}"
    )

    # Each registered agent should have a callable function
    for name in expected_names:
        assert name in orchestrator._agent_functions
        fn = orchestrator._agent_functions[name]
        assert callable(fn)

@pytest.mark.asyncio
async def test_orchestrator_manual_registration_still_works(mock_db):
    """Verifies that manual registration still works alongside auto-registration."""
    orchestrator = MnemosAIOrchestrator(mock_db)

    initial_count = len(orchestrator._agent_functions)

    async def stub_agent(state):
        return state

    orchestrator.register_agent(
        "custom_agent",
        stub_agent,
        role=AgentRole.ANALYSIS,
        capabilities=[AgentCapability(
            name="test",
            input_types=[],
            output_types=["test_out"],
        )],
    )
    assert "custom_agent" in orchestrator._agent_functions
    assert orchestrator._registry.is_registered("custom_agent")
    assert len(orchestrator._agent_functions) == initial_count + 1

@pytest.mark.asyncio
async def test_orchestrator_run_query(mock_db, mock_query, mock_run):
    """Verifies that the orchestrator executes the workflow end-to-end."""
    mock_db.get.side_effect = [mock_query, mock_run]

    orchestrator = MnemosAIOrchestrator(mock_db)

    with patch('mnemos.agentic.orchestrator.create_investigation_workflow') as mock_create:
        mock_workflow = MagicMock()
        mock_compiled = MagicMock()

        async def mock_astream(*args, **kwargs):
            yield {
                "supervisor": {
                    "is_complete": True,
                    "phase": "completion",
                    "agent_outputs": {
                        "composition_agent": {
                            "answer": "Test answer from orchestrator",
                            "confidence": 0.9,
                        }
                    },
                    "completed_agents": ["composition_agent"],
                }
            }

        mock_compiled.astream = mock_astream
        mock_workflow.compile.return_value = mock_compiled
        mock_create.return_value = mock_workflow

        from mnemos.schemas.agent import AgentQueryRequest, AgentScope

        request = AgentQueryRequest(
            run_id="run_test_001",
            query_id="qry_test_001",
            organisation_id="org_mnemos",
            site_id="site_alpha",
            user_id="usr_001",
            query_type="general",
            question="What is the pressure limit for P-101?",
            scope=AgentScope(),
        )
        result = await orchestrator.run_query(request)

        assert result.answer == "Test answer from orchestrator"

        # Verify status updates were attempted
        assert mock_db.add.called
        added_objects = [args[0] for args, _ in mock_db.add.call_args_list]
        assert any(isinstance(obj, QueryEvent) for obj in added_objects)

@pytest.mark.asyncio
async def test_result_persistence_mapping(mock_db, mock_query, mock_run):
    """Verifies that complex AI schemas map correctly to relational tables."""
    orchestrator = MnemosAIOrchestrator(mock_db)

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
        confidence_score=1.0,
        relevance_score=0.95,
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

    assert mock_query.answer == "The limit is 40 bar."
    assert mock_query.status == "succeeded"
    assert mock_run.status == "succeeded"

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
        assert result.run_metadata.pipeline_version == "v2.0-multi-agent-runtime"
