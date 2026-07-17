"""Production Observability Dashboard for the multi-agent runtime.

Provides real-time metrics, agent activity tracking, tool usage analytics,
workflow graph state, timing percentiles, confidence evolution, and retrieval
statistics. All data is derived from the InvestigationEventLog and AuditLogger
-- no synthetic data is produced.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from mnemos.agentic.runtime.audit import AuditLogger
from mnemos.agentic.runtime.events import InvestigationEventLog
from mnemos.agentic.runtime.types import (
    EventType,
    InvestigationPhase,
)
from mnemos.agentic.schemas.base import AuditAction


class ObservabilityDashboard:
    """Production dashboard for monitoring investigations in real-time.

    Reads exclusively from the ``InvestigationEventLog`` and ``AuditLogger``
    to derive actionable metrics.  Every method returns concrete data or
    safe defaults when no data is available -- no stubs, no placeholders.
    """

    def __init__(
        self,
        event_log: InvestigationEventLog,
        audit_logger: AuditLogger,
    ) -> None:
        self.event_log = event_log
        self.audit_logger = audit_logger

    # ------------------------------------------------------------------
    # Active agents
    # ------------------------------------------------------------------

    def get_active_agents(self) -> list[dict[str, Any]]:
        """Return list of currently active/running agents with their status."""
        active: list[dict[str, Any]] = []

        # Scan the most recent events to determine agent status.
        # An agent is "running" if we saw AGENT_INVOKED but no
        # AGENT_COMPLETED or AGENT_FAILED for it after that point.
        last_seen: dict[str, EventType] = {}
        last_event_for_agent: dict[str, dict[str, Any]] = {}

        for event in self.event_log.events:
            if event.agent_name is None:
                continue
            name = event.agent_name
            last_seen[name] = event.event_type
            last_event_for_agent[name] = {
                "event_type": event.event_type,
                "phase": event.phase,
                "timestamp": event.timestamp.isoformat(),
                "data": event.data,
            }

        # Also check the audit logger for richer status information
        agent_audit_status: dict[str, dict[str, Any]] = {}
        for entry in self.audit_logger.entries:
            if entry.agent_name is None:
                continue
            name = entry.agent_name
            if name not in agent_audit_status:
                agent_audit_status[name] = {
                    "last_action": entry.action,
                    "success": entry.success,
                    "duration_ms": entry.metadata.get("duration_ms", 0.0),
                    "timestamp": entry.timestamp.isoformat(),
                }
            else:
                if entry.timestamp.isoformat() > agent_audit_status[name]["timestamp"]:
                    agent_audit_status[name] = {
                        "last_action": entry.action,
                        "success": entry.success,
                        "duration_ms": entry.metadata.get("duration_ms", 0.0),
                        "timestamp": entry.timestamp.isoformat(),
                    }

        for name, last_type in last_seen.items():
            if last_type == EventType.AGENT_INVOKED:
                status = "running"
            elif last_type == EventType.AGENT_RETRYING:
                status = "retrying"
            elif last_type == EventType.AGENT_FAILED:
                status = "failed"
            elif last_type == EventType.AGENT_COMPLETED:
                status = "completed"
            else:
                status = "unknown"

            info: dict[str, Any] = {
                "agent_name": name,
                "status": status,
                "last_event": last_event_for_agent.get(name, {}),
            }

            audit_info = agent_audit_status.get(name)
            if audit_info:
                info["last_audit_action"] = audit_info["last_action"].value if hasattr(audit_info["last_action"], "value") else str(audit_info["last_action"])
                info["last_audit_success"] = audit_info["success"]
                info["last_duration_ms"] = audit_info["duration_ms"]

            active.append(info)

        return active

    # ------------------------------------------------------------------
    # Tool usage
    # ------------------------------------------------------------------

    def get_tool_usage(self) -> dict[str, Any]:
        """Return tool usage statistics: call counts, avg duration, success rate, error rate."""
        tool_calls: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for entry in self.audit_logger.entries:
            if entry.tool_name is None:
                continue
            tool_calls[entry.tool_name].append({
                "action": entry.action,
                "success": entry.success,
                "duration_ms": entry.metadata.get("duration_ms", 0.0),
                "timestamp": entry.timestamp.isoformat(),
                "error": entry.error,
            })

        if not tool_calls:
            return {
                "tools": {},
                "total_calls": 0,
                "overall_success_rate": 0.0,
                "overall_error_rate": 0.0,
            }

        tools_summary: dict[str, Any] = {}
        total_calls = 0
        total_success = 0
        total_failures = 0

        for tool_name, calls in tool_calls.items():
            durations = [c["duration_ms"] for c in calls if c["duration_ms"] > 0]
            successes = sum(1 for c in calls if c["success"])
            failures = sum(1 for c in calls if not c["success"])
            count = len(calls)

            tools_summary[tool_name] = {
                "call_count": count,
                "success_count": successes,
                "failure_count": failures,
                "success_rate": successes / count if count > 0 else 0.0,
                "error_rate": failures / count if count > 0 else 0.0,
                "avg_duration_ms": statistics.mean(durations) if durations else 0.0,
                "min_duration_ms": min(durations) if durations else 0.0,
                "max_duration_ms": max(durations) if durations else 0.0,
            }

            total_calls += count
            total_success += successes
            total_failures += failures

        return {
            "tools": tools_summary,
            "total_calls": total_calls,
            "overall_success_rate": total_success / total_calls if total_calls > 0 else 0.0,
            "overall_error_rate": total_failures / total_calls if total_calls > 0 else 0.0,
        }

    # ------------------------------------------------------------------
    # Workflow graph
    # ------------------------------------------------------------------

    def get_workflow_graph(self) -> dict[str, Any]:
        """Return the current workflow graph state: nodes visited, current phase, edges traversed."""
        nodes_visited: set[str] = set()
        edges: list[dict[str, str]] = []
        current_phase: str = InvestigationPhase.INITIALIZATION
        phase_transitions: list[dict[str, Any]] = []
        iteration = 0

        for event in self.event_log.events:
            phase_str = event.phase if isinstance(event.phase, str) else event.phase.value
            nodes_visited.add(phase_str)

            if event.event_type == EventType.PHASE_CHANGED:
                from_phase = current_phase
                to_phase = phase_str
                current_phase = to_phase
                edges.append({
                    "from": from_phase,
                    "to": to_phase,
                    "timestamp": event.timestamp.isoformat(),
                })
                phase_transitions.append({
                    "from": from_phase,
                    "to": to_phase,
                    "timestamp": event.timestamp.isoformat(),
                })

            if event.event_type == EventType.SUPERVISOR_DECISION:
                current_phase = phase_str
                decision_data = event.data
                if isinstance(decision_data, dict):
                    iteration = max(iteration, decision_data.get("from_iteration", 0))

            if event.event_type == EventType.INVESTIGATION_STARTED:
                current_phase = phase_str

        return {
            "current_phase": current_phase,
            "nodes_visited": sorted(nodes_visited),
            "edges_traversed": edges,
            "phase_transitions": phase_transitions,
            "total_transitions": len(edges),
            "iteration": iteration,
        }

    # ------------------------------------------------------------------
    # Agent timings
    # ------------------------------------------------------------------

    def get_agent_timings(self) -> dict[str, Any]:
        """Return per-agent timing stats: avg, p50, p95, p99, min, max execution times."""
        agent_durations: dict[str, list[float]] = defaultdict(list)

        for entry in self.audit_logger.entries:
            if entry.agent_name is None:
                continue
            duration = entry.metadata.get("duration_ms", 0.0)
            if duration > 0:
                agent_durations[entry.agent_name].append(duration)

        # Also pull timing from event data for agents tracked via events
        for event in self.event_log.events:
            if event.agent_name is None:
                continue
            data = event.data if isinstance(event.data, dict) else {}
            elapsed = data.get("elapsed_ms", 0.0)
            if elapsed > 0:
                agent_durations[event.agent_name].append(elapsed)

        if not agent_durations:
            return {
                "agents": {},
                "overall_avg_ms": 0.0,
                "overall_p50_ms": 0.0,
                "overall_p95_ms": 0.0,
            }

        agents_summary: dict[str, Any] = {}
        all_durations: list[float] = []

        for agent_name, durations in agent_durations.items():
            # Deduplicate by taking unique durations per agent (event and audit may overlap)
            unique_durations = sorted(set(durations))
            all_durations.extend(unique_durations)

            sorted_durs = sorted(unique_durations)
            count = len(sorted_durs)

            agents_summary[agent_name] = {
                "call_count": count,
                "avg_ms": statistics.mean(sorted_durs) if sorted_durs else 0.0,
                "min_ms": min(sorted_durs) if sorted_durs else 0.0,
                "max_ms": max(sorted_durs) if sorted_durs else 0.0,
                "p50_ms": _percentile(sorted_durs, 50),
                "p95_ms": _percentile(sorted_durs, 95),
                "p99_ms": _percentile(sorted_durs, 99),
                "stdev_ms": statistics.stdev(sorted_durs) if len(sorted_durs) > 1 else 0.0,
            }

        all_sorted = sorted(all_durations)
        return {
            "agents": agents_summary,
            "overall_avg_ms": statistics.mean(all_sorted) if all_sorted else 0.0,
            "overall_p50_ms": _percentile(all_sorted, 50),
            "overall_p95_ms": _percentile(all_sorted, 95),
        }

    # ------------------------------------------------------------------
    # Confidence evolution
    # ------------------------------------------------------------------

    def get_confidence_evolution(self) -> list[dict[str, Any]]:
        """Return confidence scores over time (per iteration/phase)."""
        evolution: list[dict[str, Any]] = []
        iteration = 0

        for event in self.event_log.events:
            if event.event_type == EventType.SUPERVISOR_DECISION:
                data = event.data if isinstance(event.data, dict) else {}
                new_iter = data.get("from_iteration", iteration)
                if isinstance(new_iter, int | float):
                    iteration = int(new_iter)

            if event.event_type == EventType.AGENT_COMPLETED and event.agent_name:
                data = event.data if isinstance(event.data, dict) else {}
                confidence = data.get("confidence", None)
                if confidence is None:
                    # Try to find confidence from agent metadata in the most recent audit entries
                    for entry in reversed(self.audit_logger.entries):
                        if entry.agent_name == event.agent_name and entry.action == AuditAction.AGENT_COMPLETED:
                            confidence = entry.output_data.get("confidence", 0.0)
                            break

                if confidence is not None:
                    evolution.append({
                        "iteration": iteration,
                        "agent_name": event.agent_name,
                        "confidence": float(confidence),
                        "phase": event.phase if isinstance(event.phase, str) else event.phase.value,
                        "timestamp": event.timestamp.isoformat(),
                    })

            if event.event_type == EventType.REFLECTION_COMPLETED:
                data = event.data if isinstance(event.data, dict) else {}
                quality = data.get("quality", None)
                if quality is not None:
                    evolution.append({
                        "iteration": iteration,
                        "agent_name": "reflection_agent",
                        "confidence": float(quality),
                        "phase": InvestigationPhase.REFLECTION,
                        "timestamp": event.timestamp.isoformat(),
                        "metric": "overall_quality",
                    })

        # Scan agent_outputs from audit entries for confidence signals
        seen = {(e["agent_name"], e["timestamp"]) for e in evolution}
        for entry in self.audit_logger.entries:
            output = entry.output_data
            if not output:
                continue
            conf = output.get("confidence")
            if conf is not None and entry.agent_name:
                key = (entry.agent_name, entry.timestamp.isoformat())
                if key not in seen:
                    evolution.append({
                        "iteration": iteration,
                        "agent_name": entry.agent_name,
                        "confidence": float(conf),
                        "phase": "unknown",
                        "timestamp": entry.timestamp.isoformat(),
                    })

        return evolution

    # ------------------------------------------------------------------
    # Retrieval statistics
    # ------------------------------------------------------------------

    def get_retrieval_statistics(self) -> dict[str, Any]:
        """Return retrieval stats: strategies used, candidates found, verified count, avg confidence."""
        strategies_used: set[str] = set()
        total_candidates = 0
        verified_count = 0
        confidences: list[float] = []
        retrieval_events = 0

        for event in self.event_log.events:
            if event.event_type == EventType.EVIDENCE_COLLECTED:
                retrieval_events += 1
                data = event.data if isinstance(event.data, dict) else {}
                count = data.get("count", 0)
                total_candidates += count
                strategies = data.get("strategies", [])
                if isinstance(strategies, list):
                    for _s in strategies:
                        strategies_used.add(str(_s))
                confidence = data.get("avg_confidence", None)
                if confidence is not None:
                    confidences.append(float(confidence))
                verified = data.get("verified_count", None)
                if verified is not None:
                    verified_count += int(verified)

        # Scan audit entries for evidence collection details
        for entry in self.audit_logger.entries:
            if entry.action == AuditAction.EVIDENCE_COLLECTED:
                retrieval_events += 1
                output = entry.output_data
                if output:
                    count = output.get("evidence_count", 0)
                    total_candidates += count

        # Scan agent outputs for retrieval plan and evidence bundle info
        for event in self.event_log.events:
            data = event.data if isinstance(event.data, dict) else {}
            # Look for retrieval plan strategies
            plan = data.get("retrieval_plan", None)
            if plan and isinstance(plan, dict):
                for strat in plan.get("strategies", []):
                    strategies_used.add(str(strat))
            # Look for evidence bundle stats
            bundle = data.get("evidence_bundle", None)
            if bundle and isinstance(bundle, dict):
                vc = bundle.get("verified_count", 0)
                verified_count += vc
                sigs = bundle.get("confidence_signals", [])
                if isinstance(sigs, list):
                    for sig in sigs:
                        if isinstance(sig, dict) and "signal_value" in sig:
                            confidences.append(float(sig["signal_value"]))

        avg_confidence = statistics.mean(confidences) if confidences else 0.0

        return {
            "strategies_used": sorted(strategies_used),
            "total_candidates_found": total_candidates,
            "verified_count": verified_count,
            "avg_confidence": avg_confidence,
            "retrieval_event_count": retrieval_events,
            "confidence_signals_count": len(confidences),
        }

    # ------------------------------------------------------------------
    # Dashboard snapshot
    # ------------------------------------------------------------------

    def get_dashboard_snapshot(self) -> dict[str, Any]:
        """Return complete dashboard snapshot combining all metrics above."""
        event_summary = self.event_log.summary()
        audit_summary = self.audit_logger.summary()

        return {
            "investigation_id": self.event_log.investigation_id,
            "event_summary": event_summary,
            "audit_summary": audit_summary,
            "active_agents": self.get_active_agents(),
            "tool_usage": self.get_tool_usage(),
            "workflow_graph": self.get_workflow_graph(),
            "agent_timings": self.get_agent_timings(),
            "confidence_evolution": self.get_confidence_evolution(),
            "retrieval_statistics": self.get_retrieval_statistics(),
            "investigation_summary": self.get_investigation_summary(),
        }

    # ------------------------------------------------------------------
    # Investigation summary
    # ------------------------------------------------------------------

    def get_investigation_summary(self) -> dict[str, Any]:
        """Return high-level investigation summary: phases visited, agents dispatched, errors, approvals."""
        phases_visited: set[str] = set()
        agents_dispatched: set[str] = set()
        agents_completed: set[str] = set()
        agents_failed: set[str] = set()
        errors: list[str] = []
        approvals_requested = 0
        approvals_granted = 0
        approvals_denied = 0
        reflection_count = 0
        replan_count = 0
        checkpoints_saved = 0

        for event in self.event_log.events:
            phase_str = event.phase if isinstance(event.phase, str) else event.phase.value
            phases_visited.add(phase_str)

            if event.agent_name:
                agents_dispatched.add(event.agent_name)

            if event.event_type == EventType.AGENT_COMPLETED and event.agent_name:
                agents_completed.add(event.agent_name)

            if event.event_type == EventType.AGENT_FAILED:
                agents_failed.add(event.agent_name or "unknown")
                data = event.data if isinstance(event.data, dict) else {}
                error_msg = data.get("error", "Unknown failure")
                errors.append(f"{event.agent_name or 'unknown'}: {error_msg}")

            if event.event_type == EventType.APPROVAL_REQUESTED:
                approvals_requested += 1

            if event.event_type == EventType.REFLECTION_COMPLETED:
                reflection_count += 1

            if event.event_type == EventType.REPLAN_REQUESTED:
                replan_count += 1

            if event.event_type == EventType.CHECKPOINT_SAVED:
                checkpoints_saved += 1

        # Audit-level approval counts
        for entry in self.audit_logger.entries:
            if entry.action == AuditAction.APPROVAL_GRANTED:
                approvals_granted += 1
            elif entry.action == AuditAction.APPROVAL_DENIED:
                approvals_denied += 1

        # Determine termination info
        is_complete = False
        termination_reason = None
        for event in reversed(self.event_log.events):
            if event.event_type == EventType.INVESTIGATION_COMPLETED:
                is_complete = True
                termination_reason = event.data.get("reason") if isinstance(event.data, dict) else None
                break
            if event.event_type == EventType.INVESTIGATION_FAILED:
                is_complete = True
                termination_reason = "failed"
                break

        # Duration
        first_event_ts = self.event_log.events[0].timestamp if self.event_log.events else None
        last_event_ts = self.event_log.events[-1].timestamp if self.event_log.events else None
        duration_seconds = 0.0
        if first_event_ts and last_event_ts:
            duration_seconds = (last_event_ts - first_event_ts).total_seconds()

        return {
            "phases_visited": sorted(phases_visited),
            "agents_dispatched": sorted(agents_dispatched),
            "agents_completed": sorted(agents_completed),
            "agents_failed": sorted(agents_failed),
            "errors": errors,
            "total_errors": len(errors),
            "approvals_requested": approvals_requested,
            "approvals_granted": approvals_granted,
            "approvals_denied": approvals_denied,
            "reflection_count": reflection_count,
            "replan_count": replan_count,
            "checkpoints_saved": checkpoints_saved,
            "is_complete": is_complete,
            "termination_reason": termination_reason,
            "total_events": self.event_log.length,
            "total_audit_entries": self.audit_logger.length,
            "duration_seconds": duration_seconds,
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _percentile(sorted_values: list[float], percentile: float) -> float:
    """Compute a percentile from a pre-sorted list of values."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (percentile / 100.0)
    f = int(k)
    c = f + 1
    if c >= len(sorted_values):
        return sorted_values[-1]
    d = k - f
    return sorted_values[f] + d * (sorted_values[c] - sorted_values[f])
