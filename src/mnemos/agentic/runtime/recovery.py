"""Failure Recovery and State Recovery for the multi-agent runtime.

Provides strategies for recovering from agent failures, reconstructing
investigation state from the event log, and computing recovery plans.
No business logic -- only infrastructure-level recovery mechanics.
"""

from __future__ import annotations

from typing import Any

from mnemos.agentic.runtime.checkpoint import CheckpointManager
from mnemos.agentic.runtime.events import InvestigationEventLog
from mnemos.agentic.runtime.types import (
    EventType,
    InvestigationPhase,
)


class StateRecoveryManager:
    """Reconstructs investigation state from the event log and checkpoints.

    When an investigation needs to be resumed (e.g. after a process
    restart), this manager replays events and restores the last
    checkpoint to rebuild a consistent state.
    """

    def __init__(
        self,
        investigation_id: str,
        event_log: InvestigationEventLog,
        checkpoint_manager: CheckpointManager,
    ) -> None:
        self.investigation_id = investigation_id
        self.event_log = event_log
        self.checkpoint_manager = checkpoint_manager

    def recover_from_checkpoint(self) -> dict[str, Any] | None:
        """Load the most recent checkpoint and return its state snapshot."""
        checkpoint = self.checkpoint_manager.load_latest()
        if checkpoint is None:
            return None
        return self.checkpoint_manager.restore_state(checkpoint)

    def recover_from_event_log(self) -> dict[str, Any]:
        """Replay the event log to reconstruct a minimal state dict.

        This is a lightweight recovery that captures which agents ran,
        which phase was reached, and what errors occurred -- without
        needing a full checkpoint.
        """
        events = self.event_log.events
        recovered: dict[str, Any] = {
            "investigation_id": self.investigation_id,
            "phase": InvestigationPhase.INITIALIZATION,
            "completed_agents": [],
            "errors": [],
            "steps_completed": [],
        }

        for event in events:
            if event.event_type == EventType.PHASE_CHANGED:
                recovered["phase"] = event.data.get("phase", recovered["phase"])
            elif event.event_type == EventType.AGENT_COMPLETED:
                agent = event.agent_name or "unknown"
                recovered["completed_agents"].append(agent)
                recovered["steps_completed"].append(agent)
            elif event.event_type == EventType.AGENT_FAILED:
                agent = event.agent_name or "unknown"
                error = event.data.get("error", "Unknown error")
                recovered["errors"].append(f"{agent}: {error}")
            elif event.event_type == EventType.EVIDENCE_COLLECTED:
                recovered.setdefault("evidence_count", 0)
                recovered["evidence_count"] += event.data.get("count", 1)

        return recovered

    def get_recovery_plan(self) -> RecoveryPlan:
        """Analyse the event log and checkpoints to produce a recovery plan."""
        checkpoint = self.checkpoint_manager.load_latest()

        failed_agents: list[str] = []
        for event in self.event_log.filter_by_type(EventType.AGENT_FAILED):
            if event.agent_name:
                failed_agents.append(event.agent_name)

        completed_agents: list[str] = []
        for event in self.event_log.filter_by_type(EventType.AGENT_COMPLETED):
            if event.agent_name:
                completed_agents.append(event.agent_name)

        last_phase = InvestigationPhase.INITIALIZATION
        for event in reversed(self.event_log.events):
            if event.event_type == EventType.PHASE_CHANGED:
                last_phase = InvestigationPhase(event.data.get("phase", last_phase))
                break

        has_checkpoint = checkpoint is not None
        event_count = self.event_log.length

        return RecoveryPlan(
            investigation_id=self.investigation_id,
            has_checkpoint=has_checkpoint,
            checkpoint_id=checkpoint.metadata.checkpoint_id if checkpoint else None,
            event_count=event_count,
            last_phase=last_phase,
            completed_agents=completed_agents,
            failed_agents=failed_agents,
            recommended_action=self._recommend(
                has_checkpoint, event_count, failed_agents, completed_agents
            ),
        )

    def _recommend(
        self,
        has_checkpoint: bool,
        event_count: int,
        failed_agents: list[str],
        completed_agents: list[str],
    ) -> str:
        if failed_agents and has_checkpoint:
            return "resume_from_checkpoint"
        if failed_agents and not has_checkpoint:
            return "replay_events"
        if event_count == 0:
            return "start_fresh"
        if completed_agents and not failed_agents:
            return "continue_from_last_phase"
        return "start_fresh"


class FailureRecoveryManager:
    """Handles agent-level failure recovery.

    When an agent invocation fails, this manager decides whether to
    retry, skip, or abort based on the agent's retry policy and
    the investigation's tolerance.
    """

    def __init__(self, max_consecutive_failures: int = 3) -> None:
        self.max_consecutive_failures = max_consecutive_failures
        self._consecutive_failures: int = 0
        self._agent_failures: dict[str, list[str]] = {}

    def record_failure(self, agent_name: str, error: str) -> None:
        self._consecutive_failures += 1
        self._agent_failures.setdefault(agent_name, []).append(error)

    def record_success(self, agent_name: str) -> None:
        self._consecutive_failures = 0

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    def should_abort(self) -> bool:
        return self._consecutive_failures >= self.max_consecutive_failures

    def get_agent_failure_count(self, agent_name: str) -> int:
        return len(self._agent_failures.get(agent_name, []))

    def get_agent_errors(self, agent_name: str) -> list[str]:
        return list(self._agent_failures.get(agent_name, []))

    def get_failed_agents(self) -> list[str]:
        return [name for name, errors in self._agent_failures.items() if errors]

    def reset(self) -> None:
        self._consecutive_failures = 0
        self._agent_failures.clear()

    def summary(self) -> dict[str, Any]:
        return {
            "consecutive_failures": self._consecutive_failures,
            "max_consecutive_failures": self.max_consecutive_failures,
            "should_abort": self.should_abort(),
            "agent_failures": {
                name: len(errors)
                for name, errors in self._agent_failures.items()
            },
        }


class RecoveryPlan:
    """Describes how to recover a failed investigation."""

    def __init__(
        self,
        investigation_id: str,
        has_checkpoint: bool,
        checkpoint_id: str | None,
        event_count: int,
        last_phase: InvestigationPhase,
        completed_agents: list[str],
        failed_agents: list[str],
        recommended_action: str,
    ) -> None:
        self.investigation_id = investigation_id
        self.has_checkpoint = has_checkpoint
        self.checkpoint_id = checkpoint_id
        self.event_count = event_count
        self.last_phase = last_phase
        self.completed_agents = completed_agents
        self.failed_agents = failed_agents
        self.recommended_action = recommended_action

    def to_dict(self) -> dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "has_checkpoint": self.has_checkpoint,
            "checkpoint_id": self.checkpoint_id,
            "event_count": self.event_count,
            "last_phase": self.last_phase,
            "completed_agents": self.completed_agents,
            "failed_agents": self.failed_agents,
            "recommended_action": self.recommended_action,
        }
