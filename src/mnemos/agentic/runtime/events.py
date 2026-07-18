"""Investigation Event Log for the multi-agent runtime.

Provides an append-only, event-sourced log that records every significant
state change during an investigation. Supports replay, filtering, and
checkpoint offset tracking.
"""

from __future__ import annotations

from typing import Any

from mnemos.agentic.runtime.types import (
    EventType,
    InvestigationEvent,
    InvestigationPhase,
)


class InvestigationEventLog:
    """Append-only event log for a single investigation lifecycle.

    Every agent invocation, supervisor decision, and state mutation is
    recorded as an immutable ``InvestigationEvent``.  The log supports
    filtering by phase, agent, and event type as well as replay from a
    given offset for checkpoint recovery.
    """

    def __init__(self, investigation_id: str) -> None:
        self.investigation_id = investigation_id
        self._events: list[InvestigationEvent] = []

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def append(
        self,
        event_type: EventType,
        *,
        phase: InvestigationPhase = InvestigationPhase.INITIALIZATION,
        agent_name: str | None = None,
        data: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> InvestigationEvent:
        event = InvestigationEvent(
            event_type=event_type,
            investigation_id=self.investigation_id,
            phase=phase,
            agent_name=agent_name,
            data=data or {},
            correlation_id=correlation_id,
        )
        self._events.append(event)
        return event

    def append_many(self, events: list[InvestigationEvent]) -> None:
        self._events.extend(events)

    async def flush_async(self) -> None:
        """Flush pending event records.

        The base event log is in-memory only. Durable implementations override
        this method and await their database writes.
        """

        return None

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @property
    def events(self) -> list[InvestigationEvent]:
        return list(self._events)

    @property
    def length(self) -> int:
        return len(self._events)

    def get_offset(self) -> int:
        return len(self._events)

    def events_from_offset(self, offset: int) -> list[InvestigationEvent]:
        return list(self._events[offset:])

    def filter_by_phase(self, phase: InvestigationPhase) -> list[InvestigationEvent]:
        return [e for e in self._events if e.phase == phase]

    def filter_by_agent(self, agent_name: str) -> list[InvestigationEvent]:
        return [e for e in self._events if e.agent_name == agent_name]

    def filter_by_type(self, event_type: EventType) -> list[InvestigationEvent]:
        return [e for e in self._events if e.event_type == event_type]

    def get_recent(self, n: int = 10) -> list[InvestigationEvent]:
        return list(self._events[-n:])

    def get_last_event(self) -> InvestigationEvent | None:
        return self._events[-1] if self._events else None

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    def replay(self) -> list[InvestigationEvent]:
        """Return all events in chronological order for full replay."""
        return list(self._events)

    def replay_from(self, checkpoint_offset: int) -> list[InvestigationEvent]:
        """Return events from a given offset for incremental replay."""
        return list(self._events[checkpoint_offset:])

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        agents_invoked: set[str] = set()
        phases_seen: set[str] = set()
        for e in self._events:
            if e.agent_name:
                agents_invoked.add(e.agent_name)
            phases_seen.add(e.phase)
        return {
            "investigation_id": self.investigation_id,
            "total_events": len(self._events),
            "agents_invoked": sorted(agents_invoked),
            "phases_seen": sorted(phases_seen),
            "first_event": self._events[0].timestamp.isoformat() if self._events else None,
            "last_event": self._events[-1].timestamp.isoformat() if self._events else None,
        }

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dicts(self) -> list[dict[str, Any]]:
        return [e.model_dump(mode="json") for e in self._events]

    @classmethod
    def from_dicts(cls, investigation_id: str, data: list[dict[str, Any]]) -> InvestigationEventLog:
        log = cls(investigation_id)
        log._events = [InvestigationEvent(**d) for d in data]
        return log
