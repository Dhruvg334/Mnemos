from mnemos.core.config import settings
from mnemos.integrations.agents.base import AgentGateway
from mnemos.integrations.agents.http import HttpAgentGateway
from mnemos.integrations.agents.mock import MockAgentGateway


def get_agent_gateway() -> AgentGateway:
    mode = settings.agent_gateway_mode.strip().lower()

    if mode == "langgraph":
        from mnemos.agentic.gateway import LangGraphAgentGateway
        return LangGraphAgentGateway()

    if mode == "http":
        return HttpAgentGateway()

    if mode == "mock":
        return MockAgentGateway()

    raise RuntimeError(f"Unsupported AGENT_GATEWAY_MODE: {settings.agent_gateway_mode}")
