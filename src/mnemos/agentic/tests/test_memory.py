"""Tests for the Agent Memory System.

Covers ConversationBuffer, WorkingMemory, AgentMemory,
and integration with InvestigationState and base agents.
"""

from __future__ import annotations

import time

from mnemos.agentic.runtime.memory import (
    AgentMemory,
    ConversationBuffer,
    MemoryEntry,
    MemoryQuery,
    MemoryType,
    WorkingMemory,
)
from mnemos.agentic.runtime.state import create_initial_state

# =====================================================================
# Test: MemoryEntry
# =====================================================================


class TestMemoryEntry:
    def test_entry_creation(self):
        entry = MemoryEntry(
            agent_name="rca_agent",
            memory_type=MemoryType.OBSERVATION,
            content="Bearing temperature is high",
        )
        assert entry.agent_name == "rca_agent"
        assert entry.memory_type == MemoryType.OBSERVATION
        assert entry.memory_id.startswith("mem_")
        assert entry.timestamp > 0

    def test_entry_with_metadata(self):
        entry = MemoryEntry(
            agent_name="rca_agent",
            memory_type=MemoryType.DECISION,
            content="Root cause is bearing wear",
            metadata={"confidence": 0.85, "source": "temperature_data"},
            tags=["bearing", "temperature"],
        )
        assert entry.metadata["confidence"] == 0.85
        assert "bearing" in entry.tags

    def test_entry_with_parent(self):
        parent = MemoryEntry(
            agent_name="rca_agent",
            memory_type=MemoryType.HYPOTHESIS,
            content="Possible bearing failure",
        )
        child = MemoryEntry(
            agent_name="rca_agent",
            memory_type=MemoryType.EVIDENCE,
            content="Temperature data confirms",
            parent_id=parent.memory_id,
        )
        assert child.parent_id == parent.memory_id

    def test_entry_serialization(self):
        entry = MemoryEntry(
            agent_name="test",
            memory_type=MemoryType.SUMMARY,
            content="Summary text",
        )
        d = entry.model_dump(mode="json")
        restored = MemoryEntry(**d)
        assert restored.memory_id == entry.memory_id
        assert restored.content == entry.content


# =====================================================================
# Test: MemoryType enum
# =====================================================================


class TestMemoryType:
    def test_all_types(self):
        types = [t.value for t in MemoryType]
        expected = [
            "observation",
            "decision",
            "hypothesis",
            "tool_result",
            "evidence",
            "reasoning",
            "question",
            "answer",
            "feedback",
            "error",
            "summary",
        ]
        assert sorted(types) == sorted(expected)

    def test_type_count(self):
        assert len(MemoryType) == 11


# =====================================================================
# Test: ConversationBuffer
# =====================================================================


class TestConversationBuffer:
    def test_record_and_retrieve(self):
        buf = ConversationBuffer()
        entry = buf.record(
            agent_name="rca_agent",
            memory_type=MemoryType.OBSERVATION,
            content="Temperature spike detected",
        )
        assert entry.memory_id.startswith("mem_")
        assert buf.count() == 1

    def test_query_by_agent(self):
        buf = ConversationBuffer()
        buf.record("rca_agent", MemoryType.OBSERVATION, "Obs 1")
        buf.record("compliance_agent", MemoryType.OBSERVATION, "Obs 2")
        buf.record("rca_agent", MemoryType.DECISION, "Dec 1")

        q = MemoryQuery(agent_name="rca_agent")
        results = buf.query(q)
        assert len(results) == 2
        assert all(e.agent_name == "rca_agent" for e in results)

    def test_query_by_type(self):
        buf = ConversationBuffer()
        buf.record("rca_agent", MemoryType.OBSERVATION, "Obs 1")
        buf.record("rca_agent", MemoryType.DECISION, "Dec 1")
        buf.record("rca_agent", MemoryType.HYPOTHESIS, "Hyp 1")

        q = MemoryQuery(memory_type=MemoryType.DECISION)
        results = buf.query(q)
        assert len(results) == 1
        assert results[0].memory_type == MemoryType.DECISION

    def test_query_by_text(self):
        buf = ConversationBuffer()
        buf.record("rca_agent", MemoryType.OBSERVATION, "Bearing temperature is high")
        buf.record("rca_agent", MemoryType.OBSERVATION, "Pump pressure is normal")
        buf.record("rca_agent", MemoryType.OBSERVATION, "Bearing vibration detected")

        q = MemoryQuery(text_search="bearing")
        results = buf.query(q)
        assert len(results) == 2

    def test_query_by_tags(self):
        buf = ConversationBuffer()
        buf.record("rca_agent", MemoryType.OBSERVATION, "Obs 1", tags=["bearing"])
        buf.record("rca_agent", MemoryType.OBSERVATION, "Obs 2", tags=["pump"])
        buf.record("rca_agent", MemoryType.OBSERVATION, "Obs 3", tags=["bearing", "pump"])

        q = MemoryQuery(tags=["bearing"])
        results = buf.query(q)
        assert len(results) == 2

    def test_query_limit(self):
        buf = ConversationBuffer()
        for i in range(20):
            buf.record("rca_agent", MemoryType.OBSERVATION, f"Obs {i}")

        q = MemoryQuery(limit=5)
        results = buf.query(q)
        assert len(results) == 5

    def test_get_recent(self):
        buf = ConversationBuffer()
        for i in range(10):
            buf.record("rca_agent", MemoryType.OBSERVATION, f"Obs {i}")

        recent = buf.get_recent(agent_name="rca_agent", limit=3)
        assert len(recent) == 3

    def test_get_by_id(self):
        buf = ConversationBuffer()
        entry = buf.record("rca_agent", MemoryType.OBSERVATION, "Obs 1")
        found = buf.get_by_id(entry.memory_id)
        assert found is not None
        assert found.content == "Obs 1"

    def test_get_by_id_not_found(self):
        buf = ConversationBuffer()
        found = buf.get_by_id("nonexistent")
        assert found is None

    def test_get_children(self):
        buf = ConversationBuffer()
        parent = buf.record("rca_agent", MemoryType.HYPOTHESIS, "Hypothesis 1")
        buf.record("rca_agent", MemoryType.EVIDENCE, "Evidence 1", parent_id=parent.memory_id)
        buf.record("rca_agent", MemoryType.EVIDENCE, "Evidence 2", parent_id=parent.memory_id)
        buf.record("rca_agent", MemoryType.EVIDENCE, "Evidence 3", parent_id="other")

        children = buf.get_children(parent.memory_id)
        assert len(children) == 2

    def test_auto_prune_by_count(self):
        buf = ConversationBuffer(max_entries=5)
        for i in range(10):
            buf.record("rca_agent", MemoryType.OBSERVATION, f"Obs {i}")
        assert buf.count() == 5

    def test_auto_prune_by_age(self):
        buf = ConversationBuffer(max_age_seconds=0.1)
        buf.record("rca_agent", MemoryType.OBSERVATION, "Old obs")
        time.sleep(0.2)
        buf.record("rca_agent", MemoryType.OBSERVATION, "New obs")
        assert buf.count() == 1

    def test_summary(self):
        buf = ConversationBuffer()
        buf.record("rca_agent", MemoryType.OBSERVATION, "Obs 1")
        buf.record("rca_agent", MemoryType.DECISION, "Dec 1")
        buf.record("compliance_agent", MemoryType.OBSERVATION, "Obs 2")

        s = buf.summary()
        assert s["total_entries"] == 3
        assert s["type_counts"]["observation"] == 2
        assert s["type_counts"]["decision"] == 1
        assert s["agent_counts"]["rca_agent"] == 2
        assert s["agent_counts"]["compliance_agent"] == 1

    def test_serialization_roundtrip(self):
        buf = ConversationBuffer()
        buf.record("rca_agent", MemoryType.OBSERVATION, "Obs 1")
        buf.record("rca_agent", MemoryType.DECISION, "Dec 1")

        data = buf.to_list()
        restored = ConversationBuffer.from_list(data)
        assert restored.count() == 2

    def test_empty_summary(self):
        buf = ConversationBuffer()
        s = buf.summary()
        assert s["total_entries"] == 0
        assert s["oldest_timestamp"] is None


# =====================================================================
# Test: WorkingMemory
# =====================================================================


class TestWorkingMemory:
    def test_set_and_get(self):
        wm = WorkingMemory()
        entry = wm.set(
            key="active_hypothesis",
            agent_name="rca_agent",
            memory_type=MemoryType.HYPOTHESIS,
            content="Bearing wear is root cause",
        )
        assert entry.content == "Bearing wear is root cause"

        found = wm.get("active_hypothesis")
        assert found is not None
        assert found.content == "Bearing wear is root cause"

    def test_set_overwrites(self):
        wm = WorkingMemory()
        wm.set("h1", "rca_agent", MemoryType.HYPOTHESIS, "Hypothesis v1")
        wm.set("h1", "rca_agent", MemoryType.HYPOTHESIS, "Hypothesis v2")

        found = wm.get("h1")
        assert found is not None
        assert found.content == "Hypothesis v2"
        assert wm.count() == 1

    def test_get_by_agent(self):
        wm = WorkingMemory()
        wm.set("rca_h1", "rca_agent", MemoryType.HYPOTHESIS, "H1")
        wm.set("rca_h2", "rca_agent", MemoryType.HYPOTHESIS, "H2")
        wm.set("comp_h1", "compliance_agent", MemoryType.HYPOTHESIS, "H3")

        rca_entries = wm.get_by_agent("rca_agent")
        assert len(rca_entries) == 2

    def test_remove(self):
        wm = WorkingMemory()
        wm.set("h1", "rca_agent", MemoryType.HYPOTHESIS, "H1")
        removed = wm.remove("h1")
        assert removed is True
        assert wm.get("h1") is None
        assert wm.count() == 0

    def test_remove_nonexistent(self):
        wm = WorkingMemory()
        removed = wm.remove("nonexistent")
        assert removed is False

    def test_keys(self):
        wm = WorkingMemory()
        wm.set("k1", "rca_agent", MemoryType.HYPOTHESIS, "H1")
        wm.set("k2", "rca_agent", MemoryType.HYPOTHESIS, "H2")
        assert sorted(wm.keys()) == ["k1", "k2"]

    def test_summary(self):
        wm = WorkingMemory()
        wm.set("k1", "rca_agent", MemoryType.HYPOTHESIS, "H1")
        wm.set("k2", "compliance_agent", MemoryType.DECISION, "D1")

        s = wm.summary()
        assert s["total_entries"] == 2
        assert s["agent_counts"]["rca_agent"] == 1
        assert s["type_counts"]["hypothesis"] == 1

    def test_serialization_roundtrip(self):
        wm = WorkingMemory()
        wm.set("k1", "rca_agent", MemoryType.HYPOTHESIS, "H1")
        wm.set("k2", "rca_agent", MemoryType.DECISION, "D1")

        data = wm.to_dict()
        restored = WorkingMemory.from_dict(data)
        assert restored.count() == 2
        assert restored.get("k1").content == "H1"


# =====================================================================
# Test: AgentMemory
# =====================================================================


class TestAgentMemory:
    def test_record_and_search(self):
        mem = AgentMemory(investigation_id="inv_001")
        mem.record("rca_agent", MemoryType.OBSERVATION, "Temperature spike at P-101")
        mem.record("rca_agent", MemoryType.DECISION, "Bearing wear is root cause")

        results = mem.search(text="temperature")
        assert len(results) == 1
        assert "temperature" in results[0].content.lower()

    def test_remember_and_recall(self):
        mem = AgentMemory(investigation_id="inv_001")
        mem.remember(
            "active_hypothesis",
            "rca_agent",
            MemoryType.HYPOTHESIS,
            "Bearing wear is root cause",
        )

        entry = mem.recall("active_hypothesis")
        assert entry is not None
        assert entry.content == "Bearing wear is root cause"

    def test_get_agent_context(self):
        mem = AgentMemory(investigation_id="inv_001")
        mem.record("rca_agent", MemoryType.OBSERVATION, "Obs 1")
        mem.record("rca_agent", MemoryType.DECISION, "Dec 1")
        mem.remember("k1", "rca_agent", MemoryType.HYPOTHESIS, "H1")

        ctx = mem.get_agent_context("rca_agent")
        assert ctx["agent_name"] == "rca_agent"
        assert len(ctx["recent_memories"]) == 2
        assert len(ctx["working_memory"]) == 1

    def test_summary(self):
        mem = AgentMemory(investigation_id="inv_001")
        mem.record("rca_agent", MemoryType.OBSERVATION, "Obs 1")
        mem.remember("k1", "rca_agent", MemoryType.HYPOTHESIS, "H1")

        s = mem.summary()
        assert s["investigation_id"] == "inv_001"
        assert s["conversation"]["total_entries"] == 1
        assert s["working_memory"]["total_entries"] == 1

    def test_serialization_roundtrip(self):
        mem = AgentMemory(investigation_id="inv_001")
        mem.record("rca_agent", MemoryType.OBSERVATION, "Obs 1")
        mem.remember("k1", "rca_agent", MemoryType.HYPOTHESIS, "H1")

        state_dict = mem.to_state_dict()
        restored = AgentMemory.from_state_dict(state_dict)
        assert restored.investigation_id == "inv_001"
        assert restored.conversation.count() == 1
        assert restored.working.count() == 1


# =====================================================================
# Test: InvestigationState Memory Integration
# =====================================================================


class TestInvestigationStateMemory:
    def test_create_initial_state_has_memory(self):
        state = create_initial_state(
            investigation_id="inv_001",
            query="Why did pump P-101 fail?",
        )
        memory = state["context"]["memory"]
        assert isinstance(memory, AgentMemory)
        assert memory.investigation_id == "inv_001"

    def test_memory_persists_across_state_updates(self):
        state = create_initial_state(
            investigation_id="inv_001",
            query="Why did pump P-101 fail?",
        )
        memory = state["context"]["memory"]
        memory.record("rca_agent", MemoryType.OBSERVATION, "Temperature spike")

        state2 = dict(state)
        state2["context"] = dict(state["context"])
        state2["context"]["memory"] = memory

        memory2 = state2["context"]["memory"]
        assert memory2.conversation.count() == 1

    def test_memory_not_overwritten_by_merge(self):
        state = create_initial_state(
            investigation_id="inv_001",
            query="Why did pump P-101 fail?",
        )
        state["context"]["memory"].record("rca_agent", MemoryType.OBSERVATION, "Obs 1")

        new_context = dict(state["context"])
        new_context["evidence_bundle"] = "some_bundle"
        state["context"] = new_context

        assert state["context"]["memory"].conversation.count() == 1
