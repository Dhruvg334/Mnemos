"""Complete Audit Logging for the Mnemos agentic runtime.

Every agent, tool, decision, approval, and state transition is recorded
as an immutable AuditEntry. The log is append-only and supports
filtering, querying, and export for compliance purposes.

No audit entry can be modified after creation.
"""

from __future__ import annotations

import uuid
from typing import Any

from mnemos.agentic.schemas.base import (
    AuditAction,
    AuditEntry,
    GuardrailCheckType,
    GuardrailVerdict,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("runtime.audit")


class AuditLogger:
    """Append-only audit log for the agentic runtime.

    Records every significant action in the system:
    - Tool calls and results
    - Agent invocations and completions
    - Supervisor decisions
    - Guardrail checks and violations
    - Approval requests and decisions
    - State transitions
    - Evidence collection and claim creation

    The audit log is the single source of truth for system traceability.
    """

    def __init__(self, investigation_id: str = "default") -> None:
        self.investigation_id = investigation_id
        self._entries: list[AuditEntry] = []

    def log(
        self,
        action: AuditAction,
        *,
        agent_name: str | None = None,
        tool_name: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        guardrail_checks: list[GuardrailCheckType] | None = None,
        guardrail_verdicts: list[GuardrailVerdict] | None = None,
        approval_gate: str | None = None,
        approval_decision: str | None = None,
        success: bool = True,
        error: str | None = None,
        trace_id: str | None = None,
        investigation_id: str | None = None,
        duration_ms: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Record an audit entry. Returns the created entry."""
        entry = AuditEntry(
            audit_id=f"aud_{uuid.uuid4().hex[:12]}",
            investigation_id=investigation_id or self.investigation_id,
            trace_id=trace_id,
            agent_name=agent_name,
            action=action,
            tool_name=tool_name,
            resource_type=resource_type,
            resource_id=resource_id,
            input_data=input_data or {},
            output_data=output_data or {},
            guardrail_checks=guardrail_checks or [],
            guardrail_verdicts=guardrail_verdicts or [],
            approval_gate=approval_gate,
            approval_decision=approval_decision,
            success=success,
            error=error,
            metadata={"duration_ms": duration_ms, **(metadata or {})},
        )
        self._entries.append(entry)
        logger.info(
            f"AUDIT: {action.value} | agent={agent_name} | tool={tool_name} | "
            f"success={success} | id={entry.audit_id}"
        )
        return entry

    def log_agent_invoked(
        self, agent_name: str, investigation_id: str = "", trace_id: str | None = None
    ) -> AuditEntry:
        return self.log(
            AuditAction.AGENT_INVOKED,
            agent_name=agent_name,
            investigation_id=investigation_id,
            trace_id=trace_id,
        )

    def log_agent_completed(
        self,
        agent_name: str,
        investigation_id: str = "",
        trace_id: str | None = None,
        duration_ms: float = 0.0,
    ) -> AuditEntry:
        return self.log(
            AuditAction.AGENT_COMPLETED,
            agent_name=agent_name,
            investigation_id=investigation_id,
            trace_id=trace_id,
            duration_ms=duration_ms,
        )

    def log_agent_failed(
        self,
        agent_name: str,
        error: str,
        investigation_id: str = "",
        trace_id: str | None = None,
    ) -> AuditEntry:
        return self.log(
            AuditAction.AGENT_FAILED,
            agent_name=agent_name,
            investigation_id=investigation_id,
            trace_id=trace_id,
            success=False,
            error=error,
        )

    def log_decision(
        self,
        agent_name: str,
        decision: str,
        reasoning: str = "",
        investigation_id: str = "",
        trace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        return self.log(
            AuditAction.DECISION_MADE,
            agent_name=agent_name,
            investigation_id=investigation_id,
            trace_id=trace_id,
            output_data={"decision": decision, "reasoning": reasoning},
            metadata=metadata,
        )

    def log_approval_requested(
        self,
        gate_type: str,
        agent_name: str,
        summary: str = "",
        investigation_id: str = "",
        trace_id: str | None = None,
    ) -> AuditEntry:
        return self.log(
            AuditAction.APPROVAL_REQUESTED,
            agent_name=agent_name,
            investigation_id=investigation_id,
            trace_id=trace_id,
            approval_gate=gate_type,
            output_data={"summary": summary},
        )

    def log_approval_decision(
        self,
        gate_type: str,
        decision: str,
        reviewer: str,
        comments: str = "",
        investigation_id: str = "",
        trace_id: str | None = None,
    ) -> AuditEntry:
        action = (
            AuditAction.APPROVAL_GRANTED
            if decision == "approve"
            else AuditAction.APPROVAL_DENIED
            if decision == "reject"
            else AuditAction.APPROVAL_CHANGES
        )
        return self.log(
            action,
            investigation_id=investigation_id,
            trace_id=trace_id,
            approval_gate=gate_type,
            approval_decision=decision,
            output_data={"reviewer": reviewer, "comments": comments},
        )

    def log_state_transition(
        self,
        from_phase: str,
        to_phase: str,
        agent_name: str | None = None,
        investigation_id: str = "",
        trace_id: str | None = None,
    ) -> AuditEntry:
        return self.log(
            AuditAction.STATE_TRANSITION,
            agent_name=agent_name,
            investigation_id=investigation_id,
            trace_id=trace_id,
            input_data={"from_phase": from_phase},
            output_data={"to_phase": to_phase},
        )

    def log_evidence_collected(
        self,
        agent_name: str,
        evidence_count: int,
        investigation_id: str = "",
        trace_id: str | None = None,
    ) -> AuditEntry:
        return self.log(
            AuditAction.EVIDENCE_COLLECTED,
            agent_name=agent_name,
            investigation_id=investigation_id,
            trace_id=trace_id,
            output_data={"evidence_count": evidence_count},
        )

    def log_claim_added(
        self,
        agent_name: str,
        claim_id: str,
        claim_text: str = "",
        investigation_id: str = "",
        trace_id: str | None = None,
    ) -> AuditEntry:
        return self.log(
            AuditAction.CLAIM_ADDED,
            agent_name=agent_name,
            investigation_id=investigation_id,
            trace_id=trace_id,
            resource_type="claim",
            resource_id=claim_id,
            output_data={"claim_text": claim_text[:200]},
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    @property
    def length(self) -> int:
        return len(self._entries)

    def filter_by_action(self, action: AuditAction) -> list[AuditEntry]:
        return [e for e in self._entries if e.action == action]

    def filter_by_agent(self, agent_name: str) -> list[AuditEntry]:
        return [e for e in self._entries if e.agent_name == agent_name]

    def filter_by_tool(self, tool_name: str) -> list[AuditEntry]:
        return [e for e in self._entries if e.tool_name == tool_name]

    def filter_by_gate(self, gate_type: str) -> list[AuditEntry]:
        return [e for e in self._entries if e.approval_gate == gate_type]

    def get_violations(self) -> list[AuditEntry]:
        return [e for e in self._entries if e.action == AuditAction.GUARDRAIL_VIOLATION]

    def get_failures(self) -> list[AuditEntry]:
        return [e for e in self._entries if not e.success]

    def get_recent(self, n: int = 10) -> list[AuditEntry]:
        return list(self._entries[-n:])

    def summary(self) -> dict[str, Any]:
        action_counts: dict[str, int] = {}
        agent_counts: dict[str, int] = {}
        tool_counts: dict[str, int] = {}
        violation_count = 0
        failure_count = 0

        for entry in self._entries:
            action_counts[entry.action.value] = action_counts.get(entry.action.value, 0) + 1
            if entry.agent_name:
                agent_counts[entry.agent_name] = agent_counts.get(entry.agent_name, 0) + 1
            if entry.tool_name:
                tool_counts[entry.tool_name] = tool_counts.get(entry.tool_name, 0) + 1
            if entry.action == AuditAction.GUARDRAIL_VIOLATION:
                violation_count += 1
            if not entry.success:
                failure_count += 1

        return {
            "investigation_id": self.investigation_id,
            "total_entries": len(self._entries),
            "action_counts": action_counts,
            "agent_counts": agent_counts,
            "tool_counts": tool_counts,
            "violation_count": violation_count,
            "failure_count": failure_count,
            "first_entry": self._entries[0].timestamp.isoformat() if self._entries else None,
            "last_entry": self._entries[-1].timestamp.isoformat() if self._entries else None,
        }

    def to_dicts(self) -> list[dict[str, Any]]:
        return [e.model_dump(mode="json") for e in self._entries]

    @classmethod
    def from_dicts(cls, investigation_id: str, data: list[dict[str, Any]]) -> AuditLogger:
        log = cls(investigation_id)
        log._entries = [AuditEntry(**d) for d in data]
        return log
