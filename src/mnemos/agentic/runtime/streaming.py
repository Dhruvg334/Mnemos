"""Production Streaming Execution for the multi-agent runtime.

Wraps the investigation workflow in an async-generator that emits
``InvestigationProgressEvent`` objects at every significant state change.
Downstream consumers (APIs, UIs, logging pipelines) can subscribe to the
stream and react in real-time without polling.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from mnemos.agentic.runtime.approval import HumanApprovalNode
from mnemos.agentic.runtime.events import InvestigationEventLog
from mnemos.agentic.runtime.recovery import FailureRecoveryManager
from mnemos.agentic.runtime.reflection import ReflectionAgent
from mnemos.agentic.runtime.registry import AgentCapabilityRegistry, AgentRegistry
from mnemos.agentic.runtime.retry import (
    RetryPolicy,
    TimeoutManager,
    execute_with_retry,
)
from mnemos.agentic.runtime.state import (
    InvestigationState,
    create_initial_state,
)
from mnemos.agentic.runtime.supervisor import SupervisorAgent
from mnemos.agentic.runtime.types import (
    AgentInvocationMetadata,
    AgentRegistration,
    AgentStatus,
    EventType,
    InvestigationPhase,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("runtime.streaming")


# ======================================================================
# Progress event model
# ======================================================================


class InvestigationProgressEvent(BaseModel):
    """A single progress event emitted during streaming execution."""

    model_config = ConfigDict(use_enum_values=True)

    event_type: str  # phase_start | agent_start | agent_complete | agent_error |
                     # evidence_collected | confidence_updated | approval_required |
                     # reflection | workflow_complete
    phase: str
    agent_name: str | None = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    data: dict[str, Any] = Field(default_factory=dict)
    iteration: int = 0


# ======================================================================
# Agent execution result (internal, carries pending events)
# ======================================================================


class _AgentExecutionResult:
    """Internal container carrying the updated state plus progress events
    that should be yielded from the streaming generator."""

    __slots__ = ("state", "events")

    def __init__(
        self,
        state: dict[str, Any],
        events: list[InvestigationProgressEvent] | None = None,
    ) -> None:
        self.state = state
        self.events = events or []


# ======================================================================
# State merge helper
# ======================================================================


def _merge_state(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Merge *source* state into *target*, appending to list fields."""
    for key, value in source.items():
        if key in target and isinstance(target[key], list) and isinstance(value, list):
            target[key].extend(value)
        elif key in target and isinstance(target[key], dict) and isinstance(value, dict):
            target[key].update(value)
        else:
            target[key] = value


def _phase_str(phase: InvestigationPhase | str) -> str:
    """Coerce a phase value to a plain string."""
    return phase if isinstance(phase, str) else phase.value


# ======================================================================
# Streaming supervisor
# ======================================================================


class StreamingSupervisor:
    """Wraps the investigation workflow to emit progress events via async generator.

    Instead of running the compiled LangGraph graph, this class manually
    executes the supervisor -> gather -> reflection -> approval loop one step
    at a time, yielding an ``InvestigationProgressEvent`` at each
    significant decision point.
    """

    def __init__(
        self,
        agent_registry: AgentRegistry,
        agent_functions: dict[str, Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]],
        *,
        max_iterations: int = 10,
        evidence_confidence_threshold: float = 0.7,
    ) -> None:
        self.agent_registry = agent_registry
        self.agent_functions = agent_functions
        self.max_iterations = max_iterations
        self.evidence_confidence_threshold = evidence_confidence_threshold

        self._capability_registry = AgentCapabilityRegistry(agent_registry)
        self._event_log = InvestigationEventLog("streaming")
        self._failure_recovery = FailureRecoveryManager()
        self._reflection_agent = ReflectionAgent()
        self._approval_node = HumanApprovalNode()

        self._supervisor = SupervisorAgent(
            agent_registry=agent_registry,
            capability_registry=self._capability_registry,
            max_iterations=max_iterations,
            evidence_confidence_threshold=evidence_confidence_threshold,
        )

        # Build registration lookup for fast access
        self._agent_registrations: dict[str, AgentRegistration] = {}
        for reg in agent_registry.list_agents():
            self._agent_registrations[reg.name] = reg

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run_streaming(
        self,
        investigation_id: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[InvestigationProgressEvent, None]:
        """Run the investigation and yield progress events at each significant state change.

        This is the main entry point.  It creates the initial state and
        drives the workflow loop, yielding events at:
        - Phase transitions
        - Agent dispatch and completion
        - Evidence collection milestones
        - Confidence threshold crossings
        - Approval gate triggers
        - Reflection decisions
        - Workflow completion
        """
        state = create_initial_state(
            investigation_id=investigation_id,
            query=query,
            context=context,
            max_iterations=self.max_iterations,
        )

        yield InvestigationProgressEvent(
            event_type="phase_start",
            phase=InvestigationPhase.INITIALIZATION,
            iteration=0,
            data={
                "investigation_id": investigation_id,
                "query": query,
                "context_keys": list((context or {}).keys()),
            },
        )

        async for event in self._run_workflow_with_hooks(state):
            yield event

        final_phase = state.get("phase", InvestigationPhase.COMPLETION)
        final_phase_str = _phase_str(final_phase)
        termination = state.get("termination_reason")

        yield InvestigationProgressEvent(
            event_type="workflow_complete",
            phase=final_phase_str,
            iteration=state.get("iteration", 0),
            data={
                "termination_reason": str(termination) if termination else None,
                "is_complete": state.get("is_complete", False),
                "should_abstain": state.get("should_abstain", False),
                "total_evidence": len(state.get("evidence", [])),
                "total_claims": len(state.get("claims", [])),
                "agents_completed": list(state.get("completed_agents", [])),
                "total_errors": len(state.get("errors", [])),
                "total_iterations": state.get("iteration", 0),
            },
        )

    # ------------------------------------------------------------------
    # Workflow execution with hooks
    # ------------------------------------------------------------------

    async def _run_workflow_with_hooks(
        self,
        state: InvestigationState,
    ) -> AsyncGenerator[InvestigationProgressEvent, None]:
        """Execute the workflow, yielding events at each significant point.

        This manually replicates the supervisor -> gather -> reflection ->
        approval loop from ``workflow.py`` but yields ``InvestigationProgressEvent``
        objects at every decision boundary.
        """
        current_state: dict[str, Any] = dict(state)

        while True:
            iteration = current_state.get("iteration", 0)
            current_state["iteration"] = iteration + 1
            iteration = current_state["iteration"]

            # ---- Supervisor decides ----------------------------------------
            decision = self._supervisor.decide_next(current_state)

            self._event_log.append(
                EventType.SUPERVISOR_DECISION,
                phase=decision.phase,
                data={
                    "agents_to_dispatch": decision.agents_to_dispatch,
                    "parallel": decision.parallel,
                    "should_continue": decision.should_continue,
                    "termination_reason": (
                        decision.termination_reason.value
                        if decision.termination_reason
                        else None
                    ),
                    "reasoning": decision.reasoning,
                },
            )

            # ---- Termination check -----------------------------------------
            if not decision.should_continue:
                current_state["is_complete"] = True
                current_state["termination_reason"] = decision.termination_reason
                current_state["phase"] = decision.phase

                self._event_log.append(
                    EventType.INVESTIGATION_COMPLETED,
                    phase=decision.phase,
                    data={
                        "reason": (
                            decision.termination_reason.value
                            if decision.termination_reason
                            else "completed"
                        ),
                    },
                )

                yield InvestigationProgressEvent(
                    event_type="phase_start",
                    phase=_phase_str(decision.phase),
                    iteration=iteration,
                    data={
                        "reasoning": decision.reasoning,
                        "termination": (
                            decision.termination_reason.value
                            if decision.termination_reason
                            else None
                        ),
                    },
                )
                break

            # ---- Phase transition -------------------------------------------
            new_phase = decision.phase
            new_phase_str = _phase_str(new_phase)
            old_phase = current_state.get("phase", InvestigationPhase.INITIALIZATION)
            old_phase_str = _phase_str(old_phase)

            current_state["phase"] = new_phase
            current_state["pending_agents"] = decision.agents_to_dispatch

            # Record the supervisor decision in state
            decisions = list(current_state.get("supervisor_decisions", []))
            decisions.append(decision.model_dump())
            current_state["supervisor_decisions"] = decisions

            self._event_log.append(
                EventType.PHASE_CHANGED,
                phase=new_phase,
                data={
                    "from_phase": old_phase_str,
                    "to_phase": new_phase_str,
                    "iteration": iteration,
                },
            )

            yield InvestigationProgressEvent(
                event_type="phase_start",
                phase=new_phase_str,
                iteration=iteration,
                data={
                    "from_phase": old_phase_str,
                    "agents_to_dispatch": decision.agents_to_dispatch,
                    "parallel": decision.parallel,
                    "reasoning": decision.reasoning,
                },
            )

            # ---- Approval gate ----------------------------------------------
            if new_phase_str == InvestigationPhase.APPROVAL:
                yield InvestigationProgressEvent(
                    event_type="approval_required",
                    phase=new_phase_str,
                    iteration=iteration,
                    data={
                        "context": current_state.get("context", {}),
                        "summary": current_state.get("query", ""),
                    },
                )
                # Auto-approve after event emission (streaming mode)
                approval_result = {
                    "decision": "approve",
                    "reviewer": "streaming_auto",
                    "comments": "Auto-approved in streaming mode",
                    "conditions": [],
                    "gate_type": current_state.get("context", {}).get(
                        "approval_gate_type", "general"
                    ),
                }
                current_state["approval_result"] = approval_result
                current_state["approval_required"] = False
                current_state["pending_approval_request"] = None
                current_state["phase"] = InvestigationPhase.ANALYSIS
                continue

            # ---- Reflection --------------------------------------------------
            if new_phase_str == InvestigationPhase.REFLECTION:
                reflection_output = await self._reflection_agent.reflect(current_state)

                self._event_log.append(
                    EventType.REFLECTION_COMPLETED,
                    phase=InvestigationPhase.REFLECTION,
                    agent_name="reflection_agent",
                    data={
                        "quality": reflection_output.overall_quality,
                        "gaps": reflection_output.identified_gaps,
                        "should_continue": reflection_output.should_continue,
                        "should_abstain": reflection_output.should_abstain,
                    },
                )

                agent_outputs = dict(current_state.get("agent_outputs", {}))
                agent_outputs["reflection_agent"] = reflection_output.model_dump()
                current_state["agent_outputs"] = agent_outputs

                completed = list(current_state.get("completed_agents", []))
                if "reflection_agent" not in completed:
                    completed.append("reflection_agent")
                current_state["completed_agents"] = completed

                yield InvestigationProgressEvent(
                    event_type="reflection",
                    phase=InvestigationPhase.REFLECTION,
                    agent_name="reflection_agent",
                    iteration=iteration,
                    data={
                        "overall_quality": reflection_output.overall_quality,
                        "evidence_completeness": reflection_output.evidence_completeness,
                        "identified_gaps": reflection_output.identified_gaps,
                        "contradictions": reflection_output.contradictions,
                        "should_continue": reflection_output.should_continue,
                        "should_abstain": reflection_output.should_abstain,
                        "suggested_next_agents": reflection_output.suggested_next_agents,
                    },
                )

                if reflection_output.should_abstain:
                    current_state["should_abstain"] = True
                    current_state["abstention_reason"] = (
                        reflection_output.abstention_reason
                    )
                    current_state["phase"] = InvestigationPhase.ABSTENTION
                    continue

                if not reflection_output.should_continue and not reflection_output.should_abstain:
                    current_state["is_complete"] = True
                    current_state["termination_reason"] = (
                        reflection_output.abstention_reason
                    ) if reflection_output.abstention_reason else None
                    break

                continue

            # ---- Agent dispatch (gather) ------------------------------------
            pending = list(current_state.get("pending_agents", []))
            if not pending:
                continue

            # Determine parallel execution
            can_parallel = len(pending) > 1
            for name in pending:
                reg = self._agent_registrations.get(name)
                if reg and not reg.can_run_in_parallel:
                    can_parallel = False
                    break

            self._event_log.append(
                EventType.CONCURRENT_AGENTS_DISPATCHED,
                phase=new_phase,
                data={"agents": pending, "parallel": can_parallel},
            )

            # Emit agent_start for each agent
            for agent_name in pending:
                yield InvestigationProgressEvent(
                    event_type="agent_start",
                    phase=new_phase_str,
                    agent_name=agent_name,
                    iteration=iteration,
                    data={
                        "parallel": can_parallel,
                        "timeout_seconds": (
                            self._agent_registrations[agent_name].timeout_seconds
                            if agent_name in self._agent_registrations
                            else 120.0
                        ),
                    },
                )

            # Execute agents
            exec_result = await self._execute_agents(
                current_state, pending, can_parallel, new_phase, iteration,
            )
            current_state = exec_result.state

            # Yield all events produced during agent execution
            for event in exec_result.events:
                yield event

        # Propagate final state back to the caller's TypedDict reference.
        # TypedDict does not support .clear(), so we update each key individually.
        for key in list(state.keys()):
            if key in current_state:
                state[key] = current_state[key]  # type: ignore[literal-required]
            elif key in state:
                del state[key]  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Agent execution
    # ------------------------------------------------------------------

    async def _execute_agents(
        self,
        state: dict[str, Any],
        pending: list[str],
        can_parallel: bool,
        phase: InvestigationPhase | str,
        iteration: int,
    ) -> _AgentExecutionResult:
        """Execute the pending agents and return updated state with progress events.

        Agents are run sequentially or in parallel depending on
        *can_parallel*.  Each agent execution is wrapped in retry and
        timeout logic.
        """
        phase_str = _phase_str(phase)
        pending_events: list[InvestigationProgressEvent] = []

        if can_parallel and len(pending) > 1:
            # Parallel execution
            tasks: list[Awaitable[tuple[dict[str, Any], AgentStatus, int]]] = []
            agent_names: list[str] = []
            for name in pending:
                reg = self._agent_registrations.get(name)
                fn = self.agent_functions.get(name)
                if reg and fn:
                    tasks.append(self._execute_single_agent(name, fn, reg, state))
                    agent_names.append(name)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for name, result in zip(agent_names, results, strict=False):
                if isinstance(result, Exception):
                    state = self._handle_agent_error(
                        state, name, result, phase_str, iteration,
                    )
                    pending_events.append(
                        InvestigationProgressEvent(
                            event_type="agent_error",
                            phase=phase_str,
                            agent_name=name,
                            iteration=iteration,
                            data={"error": str(result)},
                        )
                    )
                elif isinstance(result, tuple):
                    result_state, _status, _attempts = result
                    if result_state is not None:
                        _merge_state(state, result_state)
                    pending_events.extend(
                        self._build_completion_events(
                            name, phase_str, iteration, state,
                        )
                    )
        else:
            # Sequential execution
            for name in pending:
                reg = self._agent_registrations.get(name)
                fn = self.agent_functions.get(name)
                if not reg or not fn:
                    continue

                try:
                    result_state, _status, _attempts = await self._execute_single_agent(
                        name, fn, reg, state,
                    )
                    if result_state is not None:
                        _merge_state(state, result_state)
                    pending_events.extend(
                        self._build_completion_events(
                            name, phase_str, iteration, state,
                        )
                    )
                except Exception as exc:
                    state = self._handle_agent_error(
                        state, name, exc, phase_str, iteration,
                    )
                    pending_events.append(
                        InvestigationProgressEvent(
                            event_type="agent_error",
                            phase=phase_str,
                            agent_name=name,
                            iteration=iteration,
                            data={"error": str(exc)},
                        )
                    )

        return _AgentExecutionResult(state=state, events=pending_events)

    async def _execute_single_agent(
        self,
        agent_name: str,
        agent_fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        registration: AgentRegistration,
        state: dict[str, Any],
    ) -> tuple[dict[str, Any], AgentStatus, int]:
        """Execute a single agent with retry and timeout, returning the result state."""
        retry_policy = RetryPolicy.from_registration(registration)
        timeout_manager = TimeoutManager()

        self._event_log.append(
            EventType.AGENT_INVOKED,
            phase=InvestigationPhase(state.get("phase", InvestigationPhase.INITIALIZATION)),
            agent_name=agent_name,
        )

        started_at = datetime.now(UTC)

        result_state, status, attempts = await execute_with_retry(
            agent_fn,
            state,
            retry_policy=retry_policy,
            timeout_manager=timeout_manager,
            timeout_seconds=registration.timeout_seconds,
        )

        elapsed_ms = (datetime.now(UTC) - started_at).total_seconds() * 1000

        if result_state is not None:
            metadata = AgentInvocationMetadata(
                agent_name=agent_name,
                agent_role=registration.role,
                status=status,
                execution_time_ms=elapsed_ms,
            )
            agent_metadata = result_state.get("agent_metadata", {})
            agent_metadata[agent_name] = metadata.model_dump()
            result_state["agent_metadata"] = agent_metadata

            completed = list(result_state.get("completed_agents", []))
            if status == AgentStatus.COMPLETED and agent_name not in completed:
                completed.append(agent_name)
            result_state["completed_agents"] = completed

            pending_list = list(result_state.get("pending_agents", []))
            if agent_name in pending_list:
                pending_list.remove(agent_name)
            result_state["pending_agents"] = pending_list

            steps = list(result_state.get("steps_completed", []))
            steps.append(agent_name)
            result_state["steps_completed"] = steps

        if status == AgentStatus.COMPLETED:
            self._failure_recovery.record_success(agent_name)
            self._event_log.append(
                EventType.AGENT_COMPLETED,
                phase=InvestigationPhase(state.get("phase", InvestigationPhase.INITIALIZATION)),
                agent_name=agent_name,
                data={"attempts": attempts, "elapsed_ms": elapsed_ms},
            )
        else:
            error_msg = (
                f"Agent {agent_name} failed with status {status} "
                f"after {attempts} attempts"
            )
            self._failure_recovery.record_failure(agent_name, error_msg)
            self._event_log.append(
                EventType.AGENT_FAILED,
                phase=InvestigationPhase(state.get("phase", InvestigationPhase.INITIALIZATION)),
                agent_name=agent_name,
                data={
                    "status": status,
                    "attempts": attempts,
                    "elapsed_ms": elapsed_ms,
                },
            )
            raise RuntimeError(error_msg)

        return result_state or state, status, attempts

    # ------------------------------------------------------------------
    # Event building helpers
    # ------------------------------------------------------------------

    def _build_completion_events(
        self,
        agent_name: str,
        phase_str: str,
        iteration: int,
        state: dict[str, Any],
    ) -> list[InvestigationProgressEvent]:
        """Build progress events for agent completion, evidence, and confidence."""
        events: list[InvestigationProgressEvent] = []

        events.append(
            InvestigationProgressEvent(
                event_type="agent_complete",
                phase=phase_str,
                agent_name=agent_name,
                iteration=iteration,
                data={"status": "completed"},
            )
        )

        # Evidence collected milestone
        evidence = state.get("evidence", [])
        if evidence:
            events.append(
                InvestigationProgressEvent(
                    event_type="evidence_collected",
                    phase=phase_str,
                    agent_name=agent_name,
                    iteration=iteration,
                    data={"total_evidence": len(evidence)},
                )
            )

        # Confidence update
        agent_outputs = state.get("agent_outputs", {})
        output = agent_outputs.get(agent_name, {})
        if isinstance(output, dict):
            confidence = output.get("confidence", None)
            if confidence is not None:
                events.append(
                    InvestigationProgressEvent(
                        event_type="confidence_updated",
                        phase=phase_str,
                        agent_name=agent_name,
                        iteration=iteration,
                        data={"confidence": confidence},
                    )
                )

        return events

    def _handle_agent_error(
        self,
        state: dict[str, Any],
        agent_name: str,
        error: Exception,
        phase_str: str,
        iteration: int,
    ) -> dict[str, Any]:
        """Record an agent error and update the state accordingly."""
        error_msg = f"{agent_name}: {error}"
        errors = list(state.get("errors", []))
        errors.append(error_msg)
        state["errors"] = errors

        self._event_log.append(
            EventType.AGENT_FAILED,
            phase=InvestigationPhase(phase_str),
            agent_name=agent_name,
            data={"error": str(error)},
        )

        # Remove from pending on failure
        pending_list = list(state.get("pending_agents", []))
        if agent_name in pending_list:
            pending_list.remove(agent_name)
        state["pending_agents"] = pending_list

        # Track step even on failure
        steps = list(state.get("steps_completed", []))
        steps.append(f"{agent_name}:failed")
        state["steps_completed"] = steps

        return state
