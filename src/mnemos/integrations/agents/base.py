from typing import Protocol

from mnemos.schemas.agent import AgentQueryRequest, AgentQueryResult


class AgentGateway(Protocol):
    name: str

    async def execute_query(self, request: AgentQueryRequest) -> AgentQueryResult: ...
