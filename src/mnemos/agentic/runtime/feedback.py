"""Continuous Learning Feedback Loop for the Mnemos agentic runtime.

Collects and analyzes feedback on agent outputs to enable continuous
improvement:
- FeedbackEntry: individual feedback item (rating, comments, outcome)
- FeedbackStore: in-memory store with aggregation
- FeedbackAnalyzer: detects patterns, generates improvement suggestions
- AgentPerformanceTracker: tracks agent accuracy over time

Zero business logic — only reusable feedback architecture.
Agents decide how to act on feedback insights.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("runtime.feedback")


class FeedbackType(StrEnum):
    """Types of feedback that can be collected."""
    USER_RATING = "user_rating"
    OUTCOME_TRACKING = "outcome_tracking"
    EXPERT_REVIEW = "expert_review"
    AUTOMATED_CHECK = "automated_check"
    INVESTIGATION_RESULT = "investigation_result"


class FeedbackEntry(BaseModel):
    """A single feedback item."""
    feedback_id: str = Field(default_factory=lambda: f"fb_{uuid.uuid4().hex[:10]}")
    investigation_id: str
    agent_name: str
    feedback_type: FeedbackType
    rating: float | None = Field(None, ge=0.0, le=1.0)
    comment: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    outcome: str | None = None
    is_positive: bool | None = None


class FeedbackPattern(BaseModel):
    """A detected pattern in feedback data."""
    pattern_id: str = Field(default_factory=lambda: f"pat_{uuid.uuid4().hex[:8]}")
    agent_name: str
    pattern_type: str
    description: str
    frequency: int = 0
    avg_rating: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImprovementSuggestion(BaseModel):
    """A suggestion for improving agent performance."""
    suggestion_id: str = Field(default_factory=lambda: f"sug_{uuid.uuid4().hex[:8]}")
    agent_name: str
    category: str
    description: str
    priority: str = "medium"
    evidence: list[str] = Field(default_factory=list)


class FeedbackStore:
    """In-memory store for feedback entries with aggregation."""

    def __init__(self, max_entries: int = 10000) -> None:
        self._entries: list[FeedbackEntry] = []
        self._max_entries = max_entries

    def add(self, entry: FeedbackEntry) -> FeedbackEntry:
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]
        return entry

    def get_for_agent(self, agent_name: str, limit: int = 100) -> list[FeedbackEntry]:
        results = [e for e in self._entries if e.agent_name == agent_name]
        return sorted(results, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_for_investigation(self, investigation_id: str) -> list[FeedbackEntry]:
        return [e for e in self._entries if e.investigation_id == investigation_id]

    def get_by_type(self, feedback_type: FeedbackType, limit: int = 100) -> list[FeedbackEntry]:
        results = [e for e in self._entries if e.feedback_type == feedback_type]
        return sorted(results, key=lambda e: e.timestamp, reverse=True)[:limit]

    def count(self, agent_name: str | None = None) -> int:
        if agent_name:
            return sum(1 for e in self._entries if e.agent_name == agent_name)
        return len(self._entries)

    def avg_rating(self, agent_name: str | None = None) -> float | None:
        entries = self._entries
        if agent_name:
            entries = [e for e in entries if e.agent_name == agent_name]
        rated = [e for e in entries if e.rating is not None]
        if not rated:
            return None
        return sum(e.rating for e in rated) / len(rated)

    def agent_summary(self, agent_name: str) -> dict[str, Any]:
        entries = [e for e in self._entries if e.agent_name == agent_name]
        rated = [e for e in entries if e.rating is not None]
        positive = [e for e in entries if e.is_positive is True]
        negative = [e for e in entries if e.is_positive is False]

        return {
            "agent_name": agent_name,
            "total_feedback": len(entries),
            "rated_count": len(rated),
            "avg_rating": sum(e.rating for e in rated) / len(rated) if rated else None,
            "positive_count": len(positive),
            "negative_count": len(negative),
            "positive_rate": len(positive) / len(entries) if entries else None,
        }

    def summary(self) -> dict[str, Any]:
        type_counts: dict[str, int] = {}
        agent_counts: dict[str, int] = {}
        for e in self._entries:
            type_counts[e.feedback_type.value] = type_counts.get(e.feedback_type.value, 0) + 1
            agent_counts[e.agent_name] = agent_counts.get(e.agent_name, 0) + 1

        return {
            "total_entries": len(self._entries),
            "type_counts": type_counts,
            "agent_counts": agent_counts,
            "overall_avg_rating": self.avg_rating(),
        }

    def to_list(self) -> list[dict[str, Any]]:
        return [e.model_dump(mode="json") for e in self._entries]

    @classmethod
    def from_list(cls, data: list[dict[str, Any]], max_entries: int = 10000) -> FeedbackStore:
        store = cls(max_entries=max_entries)
        store._entries = [FeedbackEntry(**d) for d in data]
        return store


class FeedbackAnalyzer:
    """Analyzes feedback to detect patterns and generate improvement suggestions."""

    def __init__(self, store: FeedbackStore) -> None:
        self._store = store

    def detect_patterns(self, agent_name: str) -> list[FeedbackPattern]:
        """Detect patterns in feedback for a specific agent."""
        entries = self._store.get_for_agent(agent_name)
        patterns: list[FeedbackPattern] = []

        negative_entries = [e for e in entries if e.is_positive is False]
        if len(negative_entries) >= 3:
            comments = [e.comment for e in negative_entries if e.comment]
            patterns.append(FeedbackPattern(
                agent_name=agent_name,
                pattern_type="recurring_negative_feedback",
                description=f"{len(negative_entries)} negative feedback entries for {agent_name}",
                frequency=len(negative_entries),
                metadata={"sample_comments": comments[:5]},
            ))

        low_rated = [e for e in entries if e.rating is not None and e.rating < 0.4]
        if len(low_rated) >= 2:
            avg_low = sum(e.rating for e in low_rated) / len(low_rated)
            patterns.append(FeedbackPattern(
                agent_name=agent_name,
                pattern_type="consistently_low_rating",
                description=f"Average rating {avg_low:.2f} across {len(low_rated)} low-rated entries",
                frequency=len(low_rated),
                avg_rating=avg_low,
            ))

        outcome_entries = [e for e in entries if e.outcome]
        if outcome_entries:
            outcome_counts: dict[str, int] = {}
            for e in outcome_entries:
                outcome_counts[e.outcome] = outcome_counts.get(e.outcome, 0) + 1
            for outcome, count in outcome_counts.items():
                if count >= 2:
                    patterns.append(FeedbackPattern(
                        agent_name=agent_name,
                        pattern_type=f"outcome_{outcome}",
                        description=f"Outcome '{outcome}' observed {count} times",
                        frequency=count,
                    ))

        return patterns

    def generate_suggestions(self, agent_name: str) -> list[ImprovementSuggestion]:
        """Generate improvement suggestions based on feedback patterns."""
        patterns = self.detect_patterns(agent_name)
        suggestions: list[ImprovementSuggestion] = []

        for pattern in patterns:
            if pattern.pattern_type == "recurring_negative_feedback":
                suggestions.append(ImprovementSuggestion(
                    agent_name=agent_name,
                    category="quality",
                    description=(
                        f"Agent {agent_name} has {pattern.frequency} negative feedback entries. "
                        "Review recent outputs for accuracy and completeness."
                    ),
                    priority="high",
                    evidence=[p.description for p in [pattern]],
                ))
            elif pattern.pattern_type == "consistently_low_rating":
                suggestions.append(ImprovementSuggestion(
                    agent_name=agent_name,
                    category="accuracy",
                    description=(
                        f"Agent {agent_name} has consistently low ratings "
                        f"(avg: {pattern.avg_rating:.2f}). Consider prompt adjustments."
                    ),
                    priority="high",
                ))
            elif pattern.pattern_type.startswith("outcome_"):
                outcome = pattern.pattern_type.replace("outcome_", "")
                suggestions.append(ImprovementSuggestion(
                    agent_name=agent_name,
                    category="outcome",
                    description=(
                        f"Agent {agent_name} frequently produces '{outcome}' outcomes "
                        f"({pattern.frequency} times). Review if this is expected."
                    ),
                    priority="medium",
                ))

        return suggestions

    def all_agent_summaries(self) -> dict[str, dict[str, Any]]:
        """Get summaries for all agents with feedback."""
        agent_names = set()
        for entry_data in self._store.to_list():
            agent_names.add(entry_data.get("agent_name", ""))

        summaries = {}
        for name in agent_names:
            if name:
                summaries[name] = self._store.agent_summary(name)
        return summaries


class AgentPerformanceTracker:
    """Tracks agent performance metrics over time."""

    def __init__(self) -> None:
        self._metrics: dict[str, list[dict[str, Any]]] = {}

    def record(
        self,
        agent_name: str,
        investigation_id: str,
        success: bool,
        duration_ms: float | None = None,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if agent_name not in self._metrics:
            self._metrics[agent_name] = []

        self._metrics[agent_name].append({
            "investigation_id": investigation_id,
            "success": success,
            "duration_ms": duration_ms,
            "confidence": confidence,
            "timestamp": time.time(),
            "metadata": metadata or {},
        })

    def get_metrics(self, agent_name: str) -> list[dict[str, Any]]:
        return self._metrics.get(agent_name, [])

    def success_rate(self, agent_name: str) -> float | None:
        metrics = self._metrics.get(agent_name, [])
        if not metrics:
            return None
        successes = sum(1 for m in metrics if m["success"])
        return successes / len(metrics)

    def avg_duration(self, agent_name: str) -> float | None:
        metrics = self._metrics.get(agent_name, [])
        durations = [m["duration_ms"] for m in metrics if m["duration_ms"] is not None]
        if not durations:
            return None
        return sum(durations) / len(durations)

    def avg_confidence(self, agent_name: str) -> float | None:
        metrics = self._metrics.get(agent_name, [])
        confs = [m["confidence"] for m in metrics if m["confidence"] is not None]
        if not confs:
            return None
        return sum(confs) / len(confs)

    def summary(self) -> dict[str, Any]:
        agent_summaries = {}
        for name, metrics in self._metrics.items():
            agent_summaries[name] = {
                "total_runs": len(metrics),
                "success_rate": self.success_rate(name),
                "avg_duration_ms": round(self.avg_duration(name) or 0, 2),
                "avg_confidence": round(self.avg_confidence(name) or 0, 4),
            }

        return {
            "agents_tracked": len(self._metrics),
            "agent_details": agent_summaries,
        }
