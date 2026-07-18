"""AI Orchestrator -- bridges the application layer with the runtime.

This module is responsible for:
1. Instantiating and registering all agents
2. Building the runtime workflow with registered agents
3. Executing the workflow
4. Returning the AgentResponse to the caller

The orchestrator performs NO persistence.  The backend query-execution
service validates and persists the result in exactly one transaction.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.runtime import (
    AgentCapability,
    AgentRegistration,
    AgentRegistry,
    AgentRole,
    RetryStrategy,
    create_initial_state,
    create_investigation_workflow,
)
from mnemos.agentic.schemas.base import AgentResponse
from mnemos.agentic.utils.logging import StructuredLogger, setup_trace

logger = StructuredLogger("orchestrator")


class MnemosAIOrchestrator:
    """High-performance AI orchestrator for industrial operations.

    Manages the execution of grounded reasoning workflows with full
    tracing and safety.  Uses the multi-agent runtime for
    supervisor-driven, collaborative execution.

    On initialisation the orchestrator eagerly instantiates every
    available agent (retrieval + reasoning) and registers it with the
    runtime so that ``run_query`` can dispatch work immediately.

    The orchestrator performs NO persistence.  It returns an
    ``AgentResponse`` and the backend service is responsible for
    validation and persistence in exactly one transaction.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._agent_functions: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {}
        self._registry = AgentRegistry()

    # ------------------------------------------------------------------
    # Agent registration
    # ------------------------------------------------------------------

    def register_agent(
        self,
        name: str,
        fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        *,
        role: AgentRole = AgentRole.GENERIC,
        capabilities: list[AgentCapability] | None = None,
        max_retries: int = 2,
        timeout_seconds: float = 120.0,
        retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        can_run_in_parallel: bool = True,
        requires_human_approval: bool = False,
    ) -> None:
        """Register an agent function with the runtime."""
        self._agent_functions[name] = fn
        self._registry.register(AgentRegistration(
            name=name,
            role=role,
            capabilities=capabilities or [],
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            retry_strategy=retry_strategy,
            can_run_in_parallel=can_run_in_parallel,
            requires_human_approval=requires_human_approval,
        ))

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run_query(self, query_id: str, run_id: str) -> AgentResponse:
        """Execute the multi-agent investigation for a specific query.

        Builds the runtime state, executes the workflow, and returns
        the final ``AgentResponse``.

        This method performs NO database writes.  The caller is
        responsible for persisting the result.
        """
        trace_id = setup_trace(f"query_{query_id}_{uuid.uuid4().hex[:8]}")

        initial_state = create_initial_state(
            investigation_id=query_id,
            query="",
            context={
                "query_id": query_id,
                "run_id": run_id,
                "trace_id": trace_id,
            },
            trace_id=trace_id,
        )

        workflow = create_investigation_workflow(
            agent_registry=self._registry,
            agent_functions=self._agent_functions,
        )

        compiled = workflow.compile()

        final_state = dict(initial_state)
        async for event in compiled.astream(
            initial_state,
            config={"configurable": {"thread_id": trace_id}},
        ):
            for _node_name, state_update in event.items():
                if isinstance(state_update, dict):
                    final_state.update(state_update)

        response = self._extract_response(final_state)

        if not response:
            if final_state.get("errors"):
                raise RuntimeError(
                    f"Workflow failed with errors: "
                    f"{final_state['errors']}"
                )
            raise RuntimeError(
                "Workflow terminated without a final response."
            )

        return response

    # ------------------------------------------------------------------
    # Response extraction
    # ------------------------------------------------------------------

    def _extract_response(self, state: dict[str, Any]) -> AgentResponse | None:
        """Extract the final response from the investigation state.

        Looks for a ``final_response`` in the state, or constructs one
        from agent outputs if not explicitly set.
        """
        final = state.get("final_response")
        if final is not None:
            if isinstance(final, AgentResponse):
                return final
            if isinstance(final, dict):
                return AgentResponse(**final)

        agent_outputs = state.get("agent_outputs", {})
        evidence = state.get("evidence", [])
        claims = state.get("claims", [])

        if not agent_outputs and not evidence and not claims:
            return None

        composition_output = agent_outputs.get("composition_agent", {})
        if composition_output:
            return AgentResponse(
                answer=composition_output.get("answer", ""),
                confidence_score=composition_output.get("confidence", 0.0),
                claims=claims if isinstance(claims, list) else [],
                missing_evidence=composition_output.get("missing_evidence", []),
                metadata={"trace_id": state.get("trace_id")},
            )

        parts = []
        total_confidence = 0.0
        count = 0
        for _name, output in agent_outputs.items():
            if isinstance(output, dict):
                if "answer" in output:
                    parts.append(output["answer"])
                if "confidence" in output:
                    total_confidence += output["confidence"]
                    count += 1

        avg_confidence = total_confidence / count if count else 0.0

        return AgentResponse(
            answer="\n\n".join(parts) if parts else "Investigation completed.",
            confidence_score=avg_confidence,
            claims=claims if isinstance(claims, list) else [],
            metadata={"trace_id": state.get("trace_id")},
        )