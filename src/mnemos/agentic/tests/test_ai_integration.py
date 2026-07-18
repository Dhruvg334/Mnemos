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
from mnemos.schemas.agent import AgentQueryRequest, AgentScope


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

    assert hasattr(orchestrator, "_registry")
    assert hasattr(orchestrator, "_agent_functions")
    assert isinstance(orchestrator._registry, AgentRegistry)

    async def stub_agent(state):
        return state

    orchestrator.register_agent(
        "test_agent",
        stub_agent,
        role=AgentRole.ANALYSIS,
        capabilities=[
            AgentCapability(
                name="test",
                input_types=[],
                output_types=["test_out"],
            )
        ],
    )
    assert "test_agent" in orchestrator._agent_functions
    assert orchestrator._registry.is_registered("test_agent")


@pytest.mark.asyncio
async def test_orchestrator_run_query_no_persistence(mock_db):
    """P0 #1: Orchestrator must NOT write to the database.
    The backend query-execution service handles persistence.
    Uses a patched InvestigationPipeline to verify no DB writes."""
    orchestrator = MnemosAIOrchestrator(mock_db)

    request = AgentQueryRequest(
        run_id="run_test_001",
        query_id="qry_test_001",
        organisation_id="org_1",
        site_id="site_1",
        user_id="usr_1",
        membership_id="mem_1",
        actor_role="reliability_engineer",
        query_type="general",
        question="Test question",
        scope=AgentScope(),
    )

    with patch("mnemos.agentic.orchestrator.InvestigationPipeline", autospec=True) as MockPipeline:
        mock_inst = MockPipeline.return_value
        mock_inst.run = AsyncMock(
            return_value={
                "final_response": AgentResponse(
                    answer="Test answer from orchestrator",
                    confidence_score=0.9,
                    claims=[],
                    metadata={},
                ),
            }
        )

        result = await orchestrator.run_query(request=request)

        assert result.answer == "Test answer from orchestrator"

        # P0 #1: Orchestrator must NOT write to the database.
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_gateway_wrapping():
    """Ensures the LangGraph gateway correctly interfaces with the backend."""
    request = AgentQueryRequest(
        run_id="run_1",
        query_id="qry_1",
        organisation_id="org_1",
        site_id="site_1",
        user_id="usr_1",
        membership_id="mem_1",
        actor_role="reliability_engineer",
        query_type="general",
        question="Testing?",
        scope=AgentScope(),
    )

    gateway = LangGraphAgentGateway()

    with patch("mnemos.agentic.gateway.MnemosAIOrchestrator", autospec=True) as MockOrch:
        mock_inst = MockOrch.return_value
        mock_inst.run_query = AsyncMock(
            return_value=AgentResponse(
                answer="Gateway Success",
                confidence_score=1.0,
                claims=[],
                metadata={},
            )
        )

        result = await gateway.execute_query(request)

        assert result.status == "succeeded"
        assert result.answer == "Gateway Success"
        assert result.run_metadata.pipeline_version == "v2.0-multi-agent-runtime"
