"""Reusable multi-agent runtime for the Mnemos AI layer.

This package provides the entire orchestration infrastructure for a
collaborative multi-agent system built on LangGraph.  It contains
zero business logic -- only the framework for:

- Typed inter-agent messages
- Shared investigation state
- Event-sourced execution log
- Agent and capability registries
- Supervisor-driven dispatch
- Reflection and gap analysis
- Human-in-the-loop approval
- Checkpoint and resume
- Failure recovery with retry and timeout
- Concurrent agent execution

Usage::

    from mnemos.agentic.runtime import (
        InvestigationState,
        create_initial_state,
        create_investigation_workflow,
        AgentRegistry,
        AgentRegistration,
        AgentCapability,
        AgentRole,
    )

    # 1. Register agents
    registry = AgentRegistry()
    registry.register(AgentRegistration(
        name="my_agent",
        role=AgentRole.ANALYSIS,
        capabilities=[AgentCapability(
            name="analysis",
            input_types=["evidence"],
            output_types=["analysis_result"],
        )],
    ))

    # 2. Build workflow
    workflow = create_investigation_workflow(
        agent_registry=registry,
        agent_functions={"my_agent": my_agent_fn},
    )

    # 3. Run
    state = create_initial_state(
        investigation_id="inv_001",
        query="What is the failure mode?",
    )
    result = workflow.invoke(state)
"""

from mnemos.agentic.runtime.approval import HumanApprovalNode
from mnemos.agentic.runtime.checkpoint import CheckpointManager
from mnemos.agentic.runtime.events import InvestigationEventLog
from mnemos.agentic.runtime.recovery import (
    FailureRecoveryManager,
    RecoveryPlan,
    StateRecoveryManager,
)
from mnemos.agentic.runtime.reflection import ReflectionAgent
from mnemos.agentic.runtime.registry import (
    AgentCapabilityRegistry,
    AgentRegistry,
)
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
    AgentCapability,
    AgentInvocationMetadata,
    AgentMessage,
    AgentRegistration,
    AgentResult,
    AgentRole,
    AgentStatus,
    Checkpoint,
    CheckpointMetadata,
    CheckpointType,
    EventType,
    InvestigationEvent,
    InvestigationPhase,
    MessageType,
    ReflectionOutput,
    ReplanRequest,
    RetryStrategy,
    SupervisorDecision,
    TerminationReason,
    ToolCallRecord,
)
from mnemos.agentic.runtime.workflow import (
    AgentExecutor,
    create_investigation_workflow,
)

__all__ = [
    # State
    "InvestigationState",
    "create_initial_state",
    # Types
    "AgentRole",
    "AgentStatus",
    "MessageType",
    "InvestigationPhase",
    "EventType",
    "RetryStrategy",
    "CheckpointType",
    "TerminationReason",
    # Messages
    "AgentMessage",
    "ReplanRequest",
    # Metadata
    "AgentInvocationMetadata",
    "ToolCallRecord",
    "AgentResult",
    "AgentCapability",
    "AgentRegistration",
    "AgentMessage",
    # Registry
    "AgentRegistry",
    "AgentCapabilityRegistry",
    # Events
    "InvestigationEventLog",
    "InvestigationEvent",
    # Checkpoint
    "CheckpointManager",
    "Checkpoint",
    "CheckpointMetadata",
    # Recovery
    "StateRecoveryManager",
    "FailureRecoveryManager",
    "RecoveryPlan",
    # Retry
    "RetryPolicy",
    "TimeoutManager",
    "execute_with_retry",
    # Orchestration
    "SupervisorAgent",
    "ReflectionAgent",
    "HumanApprovalNode",
    "AgentExecutor",
    # Workflow
    "create_investigation_workflow",
    # Reflection
    "ReflectionOutput",
    # Decision
    "SupervisorDecision",
]
