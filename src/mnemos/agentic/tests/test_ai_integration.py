from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.gateway import LangGraphAgentGateway
from mnemos.agentic.orchestrator import MnemosAIOrchestrator
from mnemos.agentic.runtime import (
    AgentCapability,
    AgentRegistry,
    AgentRole,
)
from mnemos.agentic.schemas.base import (
    AgentResponse,
)


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


@pytest.mark.asyncio
async def test_orchestrator_initialization(mock_db):
    """Verifies that the orchestrator initializes correctly."""
    orchestrator = MnemosAIOrchestrator(mock_db)

    assert hasattr(orchestrator, '_registry')
    assert hasattr(orchestrator, '_agent_functions')
    assert isinstance(orchestrator._registry, AgentRegistry)

    async def stub_agent(state):
        return state

    orchestrator.register_agent(
        "test_agent",
        stub_agent,
        role=AgentRole.ANALYSIS,
        capabilities=[AgentCapability(
            name="test",
            input_types=[],
            output_types=["test_out"],
        )],
    )
    assert "test_agent" in orchestrator._agent_functions
    assert orchestrator._registry.is_registered("test_agent")


@pytest.mark.asyncio
async def test_orchestrator_run_query_no_persistence(mock_db):
    """P0 #1: Orchestrator must NOT write to the database.
    The backend query-execution service handles persistence."""
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

        result = await orchestrator.run_query("qry_test_001", "run_test_001")

        assert result.answer == "Test answer from orchestrator"

        # P0 #1: Orchestrator must NOT write to the database.
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()


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