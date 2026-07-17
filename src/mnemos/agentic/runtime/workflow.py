"""LangGraph Workflow Definition for the multi-agent runtime.

Defines the compiled StateGraph that drives the investigation through
its lifecycle.  The workflow is fully generic -- it dispatches to
registered agents through the supervisor and contains zero business
logic of its own.

Architecture:

    START
      |
      v
   supervisor ────────────────────────────────────────> END
      |
      |── (parallel agents) ──> gather_results ──> supervisor
      |── (reflection)        ──> supervisor
      |── (approval)          ──> supervisor
      |── (checkpoint)        ──> supervisor
      |── (terminate)
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, StateGraph

from mnemos.agentic.runtime.approval import HumanApprovalNode
from mnemos.agentic.runtime.checkpoint import CheckpointManager
from mnemos.agentic.runtime.events import InvestigationEventLog
from mnemos.agentic.runtime.recovery import FailureRecoveryManager
from mnemos.agentic.runtime.reflection import ReflectionAgent
from mnemos.agentic.runtime.registry import AgentCapabilityRegistry, AgentRegistry
from mnemos.agentic.runtime.retry import RetryPolicy, TimeoutManager, execute_with_retry
from mnemos.agentic.runtime.state import InvestigationState
from mnemos.agentic.runtime.supervisor import SupervisorAgent
from mnemos.agentic.runtime.types import (
    AgentInvocationMetadata,
    AgentRegistration,
    AgentStatus,
    CheckpointType,
    EventType,
    InvestigationPhase,
    TerminationReason,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("runtime.workflow")


# ======================================================================
# State merge helper
# ======================================================================

def _merge_state(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Merge source state into target, appending to list fields."""
    for key, value in source.items():
        if key in target and isinstance(target[key], list) and isinstance(value, list):
            target[key].extend(value)
        elif key in target and isinstance(target[key], dict) and isinstance(value, dict):
            target[key].update(value)
        else:
            target[key] = value


# ======================================================================
# Agent executor wrapper
# ======================================================================

class AgentExecutor:
    """Wraps a registered agent callable with retry, timeout, and
    event emission.

    Agents are plain async callables that receive the full investigation
    state dict and return an updated state dict.  This wrapper adds:
    - Retry with configurable backoff
    - Per-agent timeout
    - Metadata capture (timing, tool calls, confidence)
    - Event emission
    - Failure recovery
    """

    def __init__(
        self,
        agent_fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        registration: AgentRegistration,
        event_log: InvestigationEventLog,
        failure_recovery: FailureRecoveryManager,
    ) -> None:
        self.agent_fn = agent_fn
        self.registration = registration
        self.event_log = event_log
        self.failure_recovery = failure_recovery

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        agent_name = self.registration.name
        retry_policy = RetryPolicy.from_registration(self.registration)
        timeout_manager = TimeoutManager()

        started_at = time.time()

        self.event_log.append(
            EventType.AGENT_INVOKED,
            phase=InvestigationPhase(state.get("phase", InvestigationPhase.INITIALIZATION)),
            agent_name=agent_name,
        )

        result_state, status, attempts = await execute_with_retry(
            self.agent_fn,
            state,
            retry_policy=retry_policy,
            timeout_manager=timeout_manager,
            timeout_seconds=self.registration.timeout_seconds,
            on_retry=lambda attempt, exc: self._on_retry(agent_name, attempt, exc),
        )

        elapsed_ms = (time.time() - started_at) * 1000

        if status == AgentStatus.COMPLETED:
            self.failure_recovery.record_success(agent_name)
            self.event_log.append(
                EventType.AGENT_COMPLETED,
                phase=InvestigationPhase(state.get("phase", InvestigationPhase.INITIALIZATION)),
                agent_name=agent_name,
                data={"elapsed_ms": elapsed_ms, "attempts": attempts},
            )
        else:
            error_msg = f"Agent {agent_name} failed with status {status} after {attempts} attempts"
            self.failure_recovery.record_failure(agent_name, error_msg)
            self.event_log.append(
                EventType.AGENT_FAILED,
                phase=InvestigationPhase(state.get("phase", InvestigationPhase.INITIALIZATION)),
                agent_name=agent_name,
                data={"status": status, "attempts": attempts, "elapsed_ms": elapsed_ms},
            )

        if result_state is None:
            result_state = state

        # Record metadata
        metadata = AgentInvocationMetadata(
            agent_name=agent_name,
            agent_role=self.registration.role,
            status=status,
            execution_time_ms=elapsed_ms,
        )
        agent_metadata = result_state.get("agent_metadata", {})
        agent_metadata[agent_name] = metadata.model_dump()
        result_state["agent_metadata"] = agent_metadata

        # Track completion
        completed = list(result_state.get("completed_agents", []))
        if status == AgentStatus.COMPLETED and agent_name not in completed:
            completed.append(agent_name)
        result_state["completed_agents"] = completed

        # Remove from pending
        pending = list(result_state.get("pending_agents", []))
        if agent_name in pending:
            pending.remove(agent_name)
        result_state["pending_agents"] = pending

        # Track step
        steps = list(result_state.get("steps_completed", []))
        steps.append(agent_name)
        result_state["steps_completed"] = steps

        return result_state

    async def _on_retry(self, agent_name: str, attempt: int, exc: Exception) -> None:
        self.event_log.append(
            EventType.AGENT_RETRYING,
            agent_name=agent_name,
            data={"attempt": attempt, "error": str(exc)},
        )


# ======================================================================
# Workflow node functions
# ======================================================================

def _create_supervisor_node(
    supervisor: SupervisorAgent,
    event_log: InvestigationEventLog,
) -> Callable[[InvestigationState], dict[str, Any]]:
    """Create the supervisor node that decides the next action."""

    async def supervisor_node(state: InvestigationState) -> dict[str, Any]:
        iteration = state.get("iteration", 0)
        state["iteration"] = iteration + 1

        decision = supervisor.decide_next(state)

        event_log.append(
            EventType.SUPERVISOR_DECISION,
            phase=decision.phase,
            data={
                "agents_to_dispatch": decision.agents_to_dispatch,
                "parallel": decision.parallel,
                "should_continue": decision.should_continue,
                "termination_reason": decision.termination_reason,
            },
        )

        if not decision.should_continue:
            state["is_complete"] = True
            state["termination_reason"] = decision.termination_reason
            state["phase"] = decision.phase
            event_log.append(
                EventType.INVESTIGATION_COMPLETED,
                phase=decision.phase,
                data={"reason": decision.termination_reason},
            )
            return state

        state["phase"] = decision.phase
        state["pending_agents"] = decision.agents_to_dispatch
        state["supervisor_decisions"] = list(state.get("supervisor_decisions", [])) + [decision]

        event_log.append(
            EventType.PHASE_CHANGED,
            phase=decision.phase,
            data={"from_iteration": iteration},
        )

        return state

    return supervisor_node


def _create_gather_node(
    agent_registrations: dict[str, AgentRegistration],
    agent_functions: dict[str, Callable],
    event_log: InvestigationEventLog,
    failure_recovery: FailureRecoveryManager,
) -> Callable[[InvestigationState], dict[str, Any]]:
    """Create the gather node that dispatches agents (possibly in parallel)
    and collects their results."""

    async def gather_node(state: InvestigationState) -> dict[str, Any]:
        pending = list(state.get("pending_agents", []))
        if not pending:
            return state

        phase = state.get("phase", InvestigationPhase.EVIDENCE_GATHERING)

        # Determine if agents can run in parallel
        can_parallel = len(pending) > 1
        for name in pending:
            reg = agent_registrations.get(name)
            if reg and not reg.can_run_in_parallel:
                can_parallel = False
                break

        event_log.append(
            EventType.CONCURRENT_AGENTS_DISPATCHED,
            phase=phase,
            data={"agents": pending, "parallel": can_parallel},
        )

        current_state = dict(state)

        if can_parallel and len(pending) > 1:
            # Parallel execution
            executors = []
            for name in pending:
                reg = agent_registrations.get(name)
                fn = agent_functions.get(name)
                if reg and fn:
                    executors.append(
                        AgentExecutor(fn, reg, event_log, failure_recovery)
                    )

            async def run_executor(ex: AgentExecutor) -> dict[str, Any]:
                return await ex.execute(current_state)

            results = await asyncio.gather(
                *[run_executor(ex) for ex in executors],
                return_exceptions=True,
            )

            # Merge results into state
            for result in results:
                if isinstance(result, dict):
                    _merge_state(current_state, result)
                elif isinstance(result, Exception):
                    event_log.append(
                        EventType.AGENT_FAILED,
                        phase=phase,
                        data={"error": str(result)},
                    )
                    errors = list(current_state.get("errors", []))
                    errors.append(f"PARALLEL_FAILURE: {result}")
                    current_state["errors"] = errors
        else:
            # Sequential execution
            for name in pending:
                reg = agent_registrations.get(name)
                fn = agent_functions.get(name)
                if reg and fn:
                    executor = AgentExecutor(fn, reg, event_log, failure_recovery)
                    result = await executor.execute(current_state)
                    current_state = result

        return current_state

    return gather_node


def _create_reflection_node(
    reflection_agent: ReflectionAgent,
    event_log: InvestigationEventLog,
) -> Callable[[InvestigationState], dict[str, Any]]:
    """Create the reflection node."""

    async def reflection_node(state: InvestigationState) -> dict[str, Any]:
        output = await reflection_agent.reflect(state)

        event_log.append(
            EventType.REFLECTION_COMPLETED,
            phase=InvestigationPhase.REFLECTION,
            agent_name="reflection_agent",
            data={
                "quality": output.overall_quality,
                "gaps": output.identified_gaps,
                "should_continue": output.should_continue,
            },
        )

        agent_outputs = dict(state.get("agent_outputs", {}))
        agent_outputs["reflection_agent"] = output.model_dump()
        state["agent_outputs"] = agent_outputs

        completed = list(state.get("completed_agents", []))
        if "reflection_agent" not in completed:
            completed.append("reflection_agent")
        state["completed_agents"] = completed

        if output.should_abstain:
            state["should_abstain"] = True
            state["abstention_reason"] = output.abstention_reason

        if not output.should_continue and not output.should_abstain:
            state["is_complete"] = True
            state["termination_reason"] = TerminationReason.SUFFICIENT_EVIDENCE

        return state

    return reflection_node


def _create_approval_node(
    approval_node: HumanApprovalNode,
    event_log: InvestigationEventLog,
) -> Callable[[InvestigationState], dict[str, Any]]:
    """Create the human approval node."""

    async def approval_fn(state: InvestigationState) -> dict[str, Any]:
        result = await approval_node.request_approval(
            state,
            summary=state.get("query", ""),
            triggered_by="supervisor",
        )

        event_log.append(
            EventType.APPROVAL_REQUESTED,
            phase=InvestigationPhase.APPROVAL,
            agent_name="human_approval",
        )

        return result

    return approval_fn


def _create_checkpoint_node(
    checkpoint_manager: CheckpointManager,
    event_log: InvestigationEventLog,
) -> Callable[[InvestigationState], dict[str, Any]]:
    """Create the checkpoint node."""

    async def checkpoint_fn(state: InvestigationState) -> dict[str, Any]:
        checkpoint = checkpoint_manager.save(
            state,
            phase=InvestigationPhase(state.get("phase", InvestigationPhase.INITIALIZATION)),
            checkpoint_type=CheckpointType.AUTOMATIC,
            description=f"Auto-checkpoint at iteration {state.get('iteration', 0)}",
            event_log_offset=event_log.get_offset(),
        )

        event_log.append(
            EventType.CHECKPOINT_SAVED,
            phase=InvestigationPhase(state.get("phase", InvestigationPhase.INITIALIZATION)),
            data={"checkpoint_id": checkpoint.metadata.checkpoint_id},
        )

        state["last_checkpoint_id"] = checkpoint.metadata.checkpoint_id
        checkpoints = list(state.get("checkpoints", []))
        checkpoints.append(checkpoint)
        state["checkpoints"] = checkpoints

        return state

    return checkpoint_fn


# ======================================================================
# Routing logic
# ======================================================================

def route_after_supervisor(state: InvestigationState) -> str:
    """Decide where to go after the supervisor node."""
    if state.get("is_complete"):
        return "end"

    pending = state.get("pending_agents", [])
    phase = state.get("phase", InvestigationPhase.INITIALIZATION)

    if not pending:
        if phase == InvestigationPhase.REFLECTION:
            return "reflection"
        if phase == InvestigationPhase.APPROVAL:
            return "approval"
        if phase == InvestigationPhase.COMPLETION:
            return "checkpoint_then_end"
        return "supervisor"

    return "gather"


def route_after_gather(state: InvestigationState) -> str:
    """After gathering agent results, go back to supervisor."""
    if state.get("is_complete"):
        return "end"
    return "supervisor"


def route_after_reflection(state: InvestigationState) -> str:
    """After reflection, go back to supervisor."""
    if state.get("is_complete"):
        return "end"
    if state.get("should_abstain"):
        return "end"
    return "supervisor"


# ======================================================================
# Workflow builder
# ======================================================================

def create_investigation_workflow(
    agent_registry: AgentRegistry,
    agent_functions: dict[str, Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]],
    *,
    max_iterations: int = 10,
    evidence_confidence_threshold: float = 0.7,
    auto_checkpoint_interval: int = 3,
) -> StateGraph:
    """Build and compile the LangGraph StateGraph for investigations.

    This is the main entry point for constructing the runtime workflow.
    It wires together:
    - Supervisor node
    - Agent gather node (with parallel support)
    - Reflection node
    - Human approval node
    - Checkpoint node
    - All routing logic

    Args:
        agent_registry: Registry of all available agents.
        agent_functions: Mapping of agent name -> async callable.
        max_iterations: Maximum supervisor iterations before forced stop.
        evidence_confidence_threshold: Minimum confidence to consider evidence sufficient.
        auto_checkpoint_interval: Save checkpoint every N iterations.

    Returns:
        A compiled LangGraph StateGraph ready for ``.invoke()`` or ``.astream()``.
    """
    # Build supporting infrastructure
    capability_registry = AgentCapabilityRegistry(agent_registry)
    event_log = InvestigationEventLog("runtime")
    failure_recovery = FailureRecoveryManager()
    checkpoint_manager = CheckpointManager("runtime")
    approval_node = HumanApprovalNode()
    reflection_agent = ReflectionAgent()

    supervisor = SupervisorAgent(
        agent_registry=agent_registry,
        capability_registry=capability_registry,
        max_iterations=max_iterations,
        evidence_confidence_threshold=evidence_confidence_threshold,
    )

    # Build registration lookup
    agent_registrations: dict[str, AgentRegistration] = {}
    for reg in agent_registry.list_agents():
        agent_registrations[reg.name] = reg

    # Create node functions
    supervisor_fn = _create_supervisor_node(supervisor, event_log)
    gather_fn = _create_gather_node(
        agent_registrations, agent_functions, event_log, failure_recovery
    )
    reflection_fn = _create_reflection_node(reflection_agent, event_log)
    approval_fn = _create_approval_node(approval_node, event_log)
    checkpoint_fn = _create_checkpoint_node(checkpoint_manager, event_log)

    # Build graph
    graph = StateGraph(InvestigationState)

    graph.add_node("supervisor", supervisor_fn)
    graph.add_node("gather", gather_fn)
    graph.add_node("reflection", reflection_fn)
    graph.add_node("approval", approval_fn)
    graph.add_node("checkpoint", checkpoint_fn)

    # Entry point
    graph.set_entry_point("supervisor")

    # Supervisor routing
    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "gather": "gather",
            "reflection": "reflection",
            "approval": "approval",
            "checkpoint_then_end": "checkpoint",
            "supervisor": "supervisor",
            "end": END,
        },
    )

    # After gather -> back to supervisor
    graph.add_conditional_edges(
        "gather",
        route_after_gather,
        {
            "supervisor": "supervisor",
            "end": END,
        },
    )

    # After reflection -> back to supervisor
    graph.add_conditional_edges(
        "reflection",
        route_after_reflection,
        {
            "supervisor": "supervisor",
            "end": END,
        },
    )

    # After approval -> back to supervisor
    graph.add_edge("approval", "supervisor")

    # After checkpoint -> end
    graph.add_edge("checkpoint", END)

    return graph
