"""Tests for runtime/feedback.py — continuous learning feedback loop."""

from __future__ import annotations

import time

import pytest

from mnemos.agentic.runtime.feedback import (
    AgentPerformanceTracker,
    FeedbackAnalyzer,
    FeedbackEntry,
    FeedbackPattern,
    FeedbackStore,
    FeedbackType,
    ImprovementSuggestion,
)


# ------------------------------------------------------------------ #
#  FeedbackEntry
# ------------------------------------------------------------------ #
class TestFeedbackEntry:
    def test_entry_creation(self):
        e = FeedbackEntry(
            investigation_id="inv_001",
            agent_name="rca",
            feedback_type=FeedbackType.USER_RATING,
            rating=0.85,
        )
        assert e.feedback_id.startswith("fb_")
        assert e.investigation_id == "inv_001"
        assert e.agent_name == "rca"
        assert e.rating == 0.85
        assert e.timestamp > 0

    def test_entry_defaults(self):
        e = FeedbackEntry(
            investigation_id="inv_001",
            agent_name="rca",
            feedback_type=FeedbackType.OUTCOME_TRACKING,
        )
        assert e.rating is None
        assert e.comment == ""
        assert e.metadata == {}
        assert e.outcome is None
        assert e.is_positive is None

    def test_entry_with_comment(self):
        e = FeedbackEntry(
            investigation_id="inv_002",
            agent_name="compliance",
            feedback_type=FeedbackType.EXPERT_REVIEW,
            rating=0.3,
            comment="Missing key evidence",
            is_positive=False,
        )
        assert e.comment == "Missing key evidence"
        assert e.is_positive is False

    def test_rating_bounds(self):
        e = FeedbackEntry(
            investigation_id="inv_001",
            agent_name="rca",
            feedback_type=FeedbackType.USER_RATING,
            rating=0.5,
        )
        assert 0 <= e.rating <= 1

    def test_entry_to_dict(self):
        e = FeedbackEntry(
            investigation_id="inv_001",
            agent_name="rca",
            feedback_type=FeedbackType.USER_RATING,
            rating=0.9,
            metadata={"key": "value"},
        )
        d = e.model_dump(mode="json")
        assert d["investigation_id"] == "inv_001"
        assert d["agent_name"] == "rca"
        assert d["rating"] == 0.9
        assert d["metadata"] == {"key": "value"}


# ------------------------------------------------------------------ #
#  FeedbackStore
# ------------------------------------------------------------------ #
class TestFeedbackStore:
    def test_add_and_count(self):
        store = FeedbackStore()
        assert store.count() == 0
        store.add(FeedbackEntry(
            investigation_id="inv_001",
            agent_name="rca",
            feedback_type=FeedbackType.USER_RATING,
        ))
        assert store.count() == 1

    def test_count_by_agent(self):
        store = FeedbackStore()
        for i in range(5):
            store.add(FeedbackEntry(
                investigation_id="inv_001",
                agent_name="rca",
                feedback_type=FeedbackType.USER_RATING,
            ))
        store.add(FeedbackEntry(
            investigation_id="inv_001",
            agent_name="compliance",
            feedback_type=FeedbackType.USER_RATING,
        ))
        assert store.count("rca") == 5
        assert store.count("compliance") == 1
        assert store.count() == 6

    def test_get_for_agent(self):
        store = FeedbackStore()
        for i in range(3):
            store.add(FeedbackEntry(
                investigation_id=f"inv_{i:03d}",
                agent_name="rca",
                feedback_type=FeedbackType.USER_RATING,
            ))
        results = store.get_for_agent("rca")
        assert len(results) == 3
        assert all(e.agent_name == "rca" for e in results)

    def test_get_for_agent_sorted_by_time(self):
        store = FeedbackStore()
        for i in range(3):
            e = FeedbackEntry(
                investigation_id="inv_001",
                agent_name="rca",
                feedback_type=FeedbackType.USER_RATING,
            )
            e.timestamp = 1000 + i
            store.add(e)
        results = store.get_for_agent("rca")
        assert results[0].timestamp >= results[1].timestamp >= results[2].timestamp

    def test_get_for_agent_limit(self):
        store = FeedbackStore()
        for i in range(10):
            store.add(FeedbackEntry(
                investigation_id="inv_001",
                agent_name="rca",
                feedback_type=FeedbackType.USER_RATING,
            ))
        results = store.get_for_agent("rca", limit=3)
        assert len(results) == 3

    def test_get_for_investigation(self):
        store = FeedbackStore()
        store.add(FeedbackEntry(
            investigation_id="inv_001", agent_name="rca",
            feedback_type=FeedbackType.USER_RATING,
        ))
        store.add(FeedbackEntry(
            investigation_id="inv_001", agent_name="compliance",
            feedback_type=FeedbackType.USER_RATING,
        ))
        store.add(FeedbackEntry(
            investigation_id="inv_002", agent_name="rca",
            feedback_type=FeedbackType.USER_RATING,
        ))
        results = store.get_for_investigation("inv_001")
        assert len(results) == 2

    def test_get_by_type(self):
        store = FeedbackStore()
        store.add(FeedbackEntry(
            investigation_id="inv_001", agent_name="rca",
            feedback_type=FeedbackType.USER_RATING,
        ))
        store.add(FeedbackEntry(
            investigation_id="inv_001", agent_name="rca",
            feedback_type=FeedbackType.OUTCOME_TRACKING,
        ))
        results = store.get_by_type(FeedbackType.USER_RATING)
        assert len(results) == 1

    def test_avg_rating(self):
        store = FeedbackStore()
        store.add(FeedbackEntry(
            investigation_id="inv_001", agent_name="rca",
            feedback_type=FeedbackType.USER_RATING, rating=0.8,
        ))
        store.add(FeedbackEntry(
            investigation_id="inv_001", agent_name="rca",
            feedback_type=FeedbackType.USER_RATING, rating=0.6,
        ))
        avg = store.avg_rating("rca")
        assert avg is not None
        assert abs(avg - 0.7) < 1e-9

    def test_avg_rating_no_entries(self):
        store = FeedbackStore()
        assert store.avg_rating("nonexistent") is None
        assert store.avg_rating() is None

    def test_avg_rating_all_entries(self):
        store = FeedbackStore()
        store.add(FeedbackEntry(
            investigation_id="inv_001", agent_name="rca",
            feedback_type=FeedbackType.USER_RATING, rating=0.8,
        ))
        store.add(FeedbackEntry(
            investigation_id="inv_001", agent_name="compliance",
            feedback_type=FeedbackType.USER_RATING, rating=0.4,
        ))
        avg = store.avg_rating()
        assert avg is not None
        assert abs(avg - 0.6) < 1e-9

    def test_agent_summary(self):
        store = FeedbackStore()
        store.add(FeedbackEntry(
            investigation_id="inv_001", agent_name="rca",
            feedback_type=FeedbackType.USER_RATING, rating=0.9, is_positive=True,
        ))
        store.add(FeedbackEntry(
            investigation_id="inv_001", agent_name="rca",
            feedback_type=FeedbackType.USER_RATING, rating=0.3, is_positive=False,
        ))
        s = store.agent_summary("rca")
        assert s["agent_name"] == "rca"
        assert s["total_feedback"] == 2
        assert s["rated_count"] == 2
        assert abs(s["avg_rating"] - 0.6) < 1e-9
        assert s["positive_count"] == 1
        assert s["negative_count"] == 1

    def test_agent_summary_no_feedback(self):
        store = FeedbackStore()
        s = store.agent_summary("nonexistent")
        assert s["total_feedback"] == 0
        assert s["avg_rating"] is None

    def test_summary(self):
        store = FeedbackStore()
        store.add(FeedbackEntry(
            investigation_id="inv_001", agent_name="rca",
            feedback_type=FeedbackType.USER_RATING, rating=0.7,
        ))
        store.add(FeedbackEntry(
            investigation_id="inv_002", agent_name="compliance",
            feedback_type=FeedbackType.OUTCOME_TRACKING,
        ))
        s = store.summary()
        assert s["total_entries"] == 2
        assert "user_rating" in s["type_counts"]
        assert "rca" in s["agent_counts"]

    def test_max_entries_limit(self):
        store = FeedbackStore(max_entries=3)
        for i in range(5):
            store.add(FeedbackEntry(
                investigation_id=f"inv_{i:03d}", agent_name="rca",
                feedback_type=FeedbackType.USER_RATING,
            ))
        assert store.count() == 3

    def test_to_list_and_from_list(self):
        store = FeedbackStore()
        store.add(FeedbackEntry(
            investigation_id="inv_001", agent_name="rca",
            feedback_type=FeedbackType.USER_RATING, rating=0.8,
        ))
        data = store.to_list()
        assert len(data) == 1
        restored = FeedbackStore.from_list(data)
        assert restored.count() == 1
        entries = restored.to_list()
        assert entries[0]["rating"] == 0.8


# ------------------------------------------------------------------ #
#  FeedbackAnalyzer
# ------------------------------------------------------------------ #
class TestFeedbackAnalyzer:
    def _make_store_with_negative_feedback(self, agent: str, count: int = 4) -> FeedbackStore:
        store = FeedbackStore()
        for i in range(count):
            store.add(FeedbackEntry(
                investigation_id=f"inv_{i:03d}",
                agent_name=agent,
                feedback_type=FeedbackType.USER_RATING,
                rating=0.2,
                is_positive=False,
                comment=f"Issue {i}",
            ))
        return store

    def test_detect_recurring_negative(self):
        store = self._make_store_with_negative_feedback("rca", count=4)
        analyzer = FeedbackAnalyzer(store)
        patterns = analyzer.detect_patterns("rca")
        pattern_types = [p.pattern_type for p in patterns]
        assert "recurring_negative_feedback" in pattern_types

    def test_detect_low_rating(self):
        store = FeedbackStore()
        for i in range(3):
            store.add(FeedbackEntry(
                investigation_id=f"inv_{i:03d}", agent_name="rca",
                feedback_type=FeedbackType.USER_RATING, rating=0.25,
            ))
        analyzer = FeedbackAnalyzer(store)
        patterns = analyzer.detect_patterns("rca")
        pattern_types = [p.pattern_type for p in patterns]
        assert "consistently_low_rating" in pattern_types

    def test_detect_outcome_pattern(self):
        store = FeedbackStore()
        for i in range(3):
            store.add(FeedbackEntry(
                investigation_id=f"inv_{i:03d}", agent_name="rca",
                feedback_type=FeedbackType.OUTCOME_TRACKING,
                outcome="false_positive",
            ))
        analyzer = FeedbackAnalyzer(store)
        patterns = analyzer.detect_patterns("rca")
        pattern_types = [p.pattern_type for p in patterns]
        assert "outcome_false_positive" in pattern_types

    def test_no_patterns_for_good_agent(self):
        store = FeedbackStore()
        for i in range(3):
            store.add(FeedbackEntry(
                investigation_id=f"inv_{i:03d}", agent_name="rca",
                feedback_type=FeedbackType.USER_RATING, rating=0.9, is_positive=True,
            ))
        analyzer = FeedbackAnalyzer(store)
        patterns = analyzer.detect_patterns("rca")
        assert len(patterns) == 0

    def test_no_patterns_for_empty_agent(self):
        store = FeedbackStore()
        analyzer = FeedbackAnalyzer(store)
        patterns = analyzer.detect_patterns("nonexistent")
        assert len(patterns) == 0

    def test_generate_suggestions_for_negative(self):
        store = self._make_store_with_negative_feedback("rca", count=4)
        analyzer = FeedbackAnalyzer(store)
        suggestions = analyzer.generate_suggestions("rca")
        categories = [s.category for s in suggestions]
        assert "quality" in categories

    def test_generate_suggestions_for_low_rating(self):
        store = FeedbackStore()
        for i in range(3):
            store.add(FeedbackEntry(
                investigation_id=f"inv_{i:03d}", agent_name="rca",
                feedback_type=FeedbackType.USER_RATING, rating=0.25,
            ))
        analyzer = FeedbackAnalyzer(store)
        suggestions = analyzer.generate_suggestions("rca")
        categories = [s.category for s in suggestions]
        assert "accuracy" in categories

    def test_suggestion_priority(self):
        store = self._make_store_with_negative_feedback("rca", count=4)
        analyzer = FeedbackAnalyzer(store)
        suggestions = analyzer.generate_suggestions("rca")
        high = [s for s in suggestions if s.priority == "high"]
        assert len(high) >= 1


# ------------------------------------------------------------------ #
#  AgentPerformanceTracker
# ------------------------------------------------------------------ #
class TestAgentPerformanceTracker:
    def test_record(self):
        tracker = AgentPerformanceTracker()
        tracker.record("rca", "inv_001", success=True, duration_ms=120.5, confidence=0.9)
        metrics = tracker.get_metrics("rca")
        assert len(metrics) == 1
        assert metrics[0]["success"] is True

    def test_success_rate(self):
        tracker = AgentPerformanceTracker()
        for i in range(4):
            tracker.record("rca", f"inv_{i:03d}", success=True)
        for i in range(2):
            tracker.record("rca", f"inv_{i+4:03d}", success=False)
        rate = tracker.success_rate("rca")
        assert rate is not None
        assert abs(rate - 4 / 6) < 1e-9

    def test_success_rate_empty(self):
        tracker = AgentPerformanceTracker()
        assert tracker.success_rate("nonexistent") is None

    def test_avg_duration(self):
        tracker = AgentPerformanceTracker()
        tracker.record("rca", "inv_001", success=True, duration_ms=100)
        tracker.record("rca", "inv_002", success=True, duration_ms=200)
        avg = tracker.avg_duration("rca")
        assert avg == 150.0

    def test_avg_duration_empty(self):
        tracker = AgentPerformanceTracker()
        assert tracker.avg_duration("nonexistent") is None

    def test_avg_duration_no_durations(self):
        tracker = AgentPerformanceTracker()
        tracker.record("rca", "inv_001", success=True)
        assert tracker.avg_duration("rca") is None

    def test_avg_confidence(self):
        tracker = AgentPerformanceTracker()
        tracker.record("rca", "inv_001", success=True, confidence=0.8)
        tracker.record("rca", "inv_002", success=True, confidence=0.6)
        avg = tracker.avg_confidence("rca")
        assert avg is not None
        assert abs(avg - 0.7) < 1e-9

    def test_avg_confidence_empty(self):
        tracker = AgentPerformanceTracker()
        assert tracker.avg_confidence("nonexistent") is None

    def test_summary(self):
        tracker = AgentPerformanceTracker()
        tracker.record("rca", "inv_001", success=True, duration_ms=100, confidence=0.9)
        tracker.record("compliance", "inv_001", success=True, duration_ms=50)
        s = tracker.summary()
        assert s["agents_tracked"] == 2
        assert "rca" in s["agent_details"]
        assert "compliance" in s["agent_details"]
        assert s["agent_details"]["rca"]["total_runs"] == 1

    def test_summary_empty(self):
        tracker = AgentPerformanceTracker()
        s = tracker.summary()
        assert s["agents_tracked"] == 0

    def test_multiple_agents(self):
        tracker = AgentPerformanceTracker()
        for agent in ["rca", "compliance", "expert_knowledge"]:
            tracker.record(agent, "inv_001", success=True, duration_ms=100)
        assert tracker.success_rate("rca") == 1.0
        assert tracker.success_rate("compliance") == 1.0
        assert tracker.success_rate("expert_knowledge") == 1.0


# ------------------------------------------------------------------ #
#  FeedbackPattern / ImprovementSuggestion
# ------------------------------------------------------------------ #
class TestModels:
    def test_feedback_pattern_creation(self):
        p = FeedbackPattern(
            agent_name="rca",
            pattern_type="recurring_negative",
            description="Test pattern",
            frequency=5,
            avg_rating=0.3,
        )
        assert p.pattern_id.startswith("pat_")
        assert p.frequency == 5

    def test_improvement_suggestion_creation(self):
        s = ImprovementSuggestion(
            agent_name="rca",
            category="accuracy",
            description="Needs improvement",
            priority="high",
            evidence=["evidence1"],
        )
        assert s.suggestion_id.startswith("sug_")
        assert s.evidence == ["evidence1"]


# ------------------------------------------------------------------ #
#  FeedbackType enum
# ------------------------------------------------------------------ #
class TestFeedbackType:
    def test_all_types(self):
        types = [t.value for t in FeedbackType]
        assert "user_rating" in types
        assert "outcome_tracking" in types
        assert "expert_review" in types
        assert "automated_check" in types
        assert "investigation_result" in types

    def test_string_value(self):
        assert FeedbackType.USER_RATING.value == "user_rating"
