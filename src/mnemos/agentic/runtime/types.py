"""Typed Agent Messages, enums, metadata models for the multi-agent runtime.

This module defines the entire type system for inter-agent communication,
agent metadata, checkpoints, events, and registry records. It contains
zero business logic -- only data contracts.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AgentRole(StrEnum):
    SUPERVISOR = "supervisor"
    REFLECTION = "reflection"
    RETRIEVAL = "retrieval"
    ANALYSIS = "analysis"
    VERIFICATION = "verification"
    COMPOSITION = "composition"
    HUMAN_APPROVAL = "human_approval"
    GENERIC = "generic"


class MessageType(StrEnum):
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    COMMAND = "command"
    QUERY = "query"
    FEEDBACK = "feedback"
    REPLAN = "replan"
    APPROVAL = "approval"


class InvestigationPhase(StrEnum):
    INITIALIZATION = "initialization"
    PLANNING = "planning"
    EVIDENCE_GATHERING = "evidence_gathering"
    ANALYSIS = "analysis"
    VERIFICATION = "verification"
    SYNTHESIS = "synthesis"
    REFLECTION = "reflection"
    APPROVAL = "approval"
    COMPLETION = "completion"
    ABSTENTION = "abstention"
    FAILED = "failed"
    OBSERVABILITY = "observability"


class AgentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class RetryStrategy(StrEnum):
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    NO_RETRY = "no_retry"


class CheckpointType(StrEnum):
    AUTOMATIC = "automatic"
    ON_FAILURE = "on_failure"
    BEFORE_AGENT = "before_agent"
    HUMAN_REQUESTED = "human_requested"


class EventType(StrEnum):
    INVESTIGATION_STARTED = "investigation_started"
    INVESTIGATION_COMPLETED = "investigation_completed"
    INVESTIGATION_FAILED = "investigation_failed"
    AGENT_INVOKED = "agent_invoked"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    AGENT_TIMEOUT = "agent_timeout"
    AGENT_RETRYING = "agent_retrying"
    PHASE_CHANGED = "phase_changed"
    EVIDENCE_COLLECTED = "evidence_collected"
    CLAIM_ADDED = "claim_added"
    CHECKPOINT_SAVED = "checkpoint_saved"
    CHECKPOINT_LOADED = "checkpoint_loaded"
    REPLAN_REQUESTED = "replan_requested"
    REPLAN_COMPLETED = "replan_completed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RECEIVED = "approval_received"
    SUPERVISOR_DECISION = "supervisor_decision"
    REFLECTION_COMPLETED = "reflection_completed"
    STATE_RECOVERED = "state_recovered"
    CONCURRENT_AGENTS_DISPATCHED = "concurrent_agents_dispatched"
    SPAN_COMPLETED = "span_completed"
    TELEMETRY_RECORDED = "telemetry_recorded"


class TerminationReason(StrEnum):
    SUFFICIENT_EVIDENCE = "sufficient_evidence"
    ABSTENTION = "abstention"
    MAX_ITERATIONS = "max_iterations"
    HUMAN_REJECTED = "human_rejected"
    ALL_AGENTS_FAILED = "all_agents_failed"
    SUPERVISOR_DECIDED = "supervisor_decided"


# ---------------------------------------------------------------------------
# Tool call tracking
# ---------------------------------------------------------------------------

class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result_summary: str = ""
    duration_ms: float = 0.0
    success: bool = True
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Agent Invocation Metadata
# ---------------------------------------------------------------------------

class AgentInvocationMetadata(BaseModel):
    """Produced by every agent invocation."""
    model_config = ConfigDict(use_enum_values=True)

    agent_name: str
    agent_role: AgentRole = AgentRole.GENERIC
    status: AgentStatus = AgentStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    execution_time_ms: float = 0.0
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning_summary: str = ""
    state_updates: list[str] = Field(default_factory=list)
    output_keys: list[str] = Field(default_factory=list)
    error: str | None = None
    retry_count: int = 0


# ---------------------------------------------------------------------------
# Typed Agent Messages
# ---------------------------------------------------------------------------

class AgentMessage(BaseModel):
    """Base message for inter-agent communication through shared state."""
    model_config = ConfigDict(use_enum_values=True)

    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    message_type: MessageType
    source_agent: str
    target_agent: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None


class AgentRequestMessage(BaseModel):
    message_type: Literal[MessageType.REQUEST] = MessageType.REQUEST
    required_capabilities: list[str] = Field(default_factory=list)
    timeout_seconds: float | None = None


class AgentResponseMessage(BaseModel):
    message_type: Literal[MessageType.RESPONSE] = MessageType.RESPONSE
    success: bool = True
    error: str | None = None


class AgentEventMessage(BaseModel):
    message_type: Literal[MessageType.EVENT] = MessageType.EVENT
    event_type: EventType = EventType.AGENT_COMPLETED
    data: dict[str, Any] = Field(default_factory=dict)


class ReplanRequest(BaseModel):
    message_type: Literal[MessageType.REPLAN] = MessageType.REPLAN
    reason: str = ""
    suggested_agents: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    phase: InvestigationPhase = InvestigationPhase.PLANNING


class ApprovalRequest(BaseModel):
    message_type: Literal[MessageType.APPROVAL] = MessageType.APPROVAL
    summary: str = ""
    findings: dict[str, Any] = Field(default_factory=dict)
    options: list[str] = Field(default_factory=lambda: ["approve", "reject", "request_changes"])
    timeout_seconds: float = 300.0


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

class CheckpointMetadata(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    checkpoint_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    investigation_id: str
    checkpoint_type: CheckpointType = CheckpointType.AUTOMATIC
    phase: InvestigationPhase = InvestigationPhase.INITIALIZATION
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent_name: str | None = None
    description: str = ""
    state_hash: str = ""


class Checkpoint(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    metadata: CheckpointMetadata
    state_snapshot: dict[str, Any] = Field(default_factory=dict)
    event_log_offset: int = 0


# ---------------------------------------------------------------------------
# Investigation Event
# ---------------------------------------------------------------------------

class InvestigationEvent(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    event_type: EventType
    investigation_id: str
    phase: InvestigationPhase = InvestigationPhase.INITIALIZATION
    agent_name: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None


# ---------------------------------------------------------------------------
# Supervisor Decision
# ---------------------------------------------------------------------------

class SupervisorDecision(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    decision_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    phase: InvestigationPhase
    agents_to_dispatch: list[str] = Field(default_factory=list)
    parallel: bool = False
    reasoning: str = ""
    should_continue: bool = True
    termination_reason: TerminationReason | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Agent Registry Record
# ---------------------------------------------------------------------------

class AgentCapability(BaseModel):
    """Describes what an agent can produce or consume."""
    name: str
    description: str = ""
    input_types: list[str] = Field(default_factory=list)
    output_types: list[str] = Field(default_factory=list)
    required_context: list[str] = Field(default_factory=list)
    produced_context: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list, description="Agent names this agent depends on")


class AgentRegistration(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    name: str
    role: AgentRole = AgentRole.GENERIC
    description: str = ""
    capabilities: list[AgentCapability] = Field(default_factory=list)
    max_retries: int = 2
    timeout_seconds: float = 120.0
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    can_run_in_parallel: bool = True
    requires_human_approval: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Reflection Output
# ---------------------------------------------------------------------------

class ReflectionOutput(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    agent_name: str = "reflection_agent"
    overall_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    identified_gaps: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    suggested_next_agents: list[str] = Field(default_factory=list)
    should_continue: bool = True
    should_abstain: bool = False
    abstention_reason: str | None = None
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Agent Result (returned by every agent invocation)
# ---------------------------------------------------------------------------

class AgentResult(BaseModel):
    """Structured result from any agent invocation."""
    model_config = ConfigDict(use_enum_values=True)

    agent_name: str
    status: AgentStatus = AgentStatus.COMPLETED
    output: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommended_next_agents: list[str] = Field(default_factory=list)
    metadata: AgentInvocationMetadata | None = None
    error: str | None = None
