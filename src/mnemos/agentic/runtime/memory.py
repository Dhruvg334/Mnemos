"""Agent Memory System for the Mnemos agentic runtime.

Provides per-investigation, queryable memory for agents:
- ConversationBuffer: short-term agent interaction memory
- WorkingMemory: current investigation state/hypotheses
- MemoryEntry: typed memory items with metadata
- AgentMemory: unified interface combining both

Zero business logic — only reusable memory architecture.
Agents decide what to remember and when to recall.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(StrEnum):
    """Types of memory entries agents can record."""
    OBSERVATION = "observation"
    DECISION = "decision"
    HYPOTHESIS = "hypothesis"
    TOOL_RESULT = "tool_result"
    EVIDENCE = "evidence"
    REASONING = "reasoning"
    QUESTION = "question"
    ANSWER = "answer"
    FEEDBACK = "feedback"
    ERROR = "error"
    SUMMARY = "summary"


class MemoryEntry(BaseModel):
    """A single memory entry recorded by an agent."""
    memory_id: str = Field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:10]}")
    agent_name: str
    memory_type: MemoryType
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    relevance_score: float | None = None
    investigation_id: str = ""
    parent_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class MemoryQuery(BaseModel):
    """Query parameters for searching memory."""
    agent_name: str | None = None
    memory_type: MemoryType | None = None
    text_search: str | None = None
    tags: list[str] = Field(default_factory=list)
    since_timestamp: float | None = None
    limit: int = 20


class ConversationBuffer:
    """Short-term, investigation-scoped conversation memory.

    Stores agent interactions (tool calls, decisions, observations)
    within a single investigation. Supports text search, type filtering,
    and automatic pruning.
    """

    def __init__(self, max_entries: int = 500, max_age_seconds: float = 7200.0):
        self._entries: list[MemoryEntry] = []
        self._max_entries = max_entries
        self._max_age_seconds = max_age_seconds

    def record(
        self,
        agent_name: str,
        memory_type: MemoryType,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
        investigation_id: str = "",
        tags: list[str] | None = None,
        parent_id: str | None = None,
    ) -> MemoryEntry:
        """Record a new memory entry."""
        entry = MemoryEntry(
            agent_name=agent_name,
            memory_type=memory_type,
            content=content,
            metadata=metadata or {},
            investigation_id=investigation_id,
            tags=tags or [],
            parent_id=parent_id,
        )
        self._entries.append(entry)
        self._auto_prune()
        return entry

    def query(self, q: MemoryQuery) -> list[MemoryEntry]:
        """Search memory with filters."""
        results = list(self._entries)

        if q.agent_name:
            results = [e for e in results if e.agent_name == q.agent_name]
        if q.memory_type:
            results = [e for e in results if e.memory_type == q.memory_type]
        if q.since_timestamp:
            results = [e for e in results if e.timestamp >= q.since_timestamp]
        if q.tags:
            tag_set = set(q.tags)
            results = [e for e in results if tag_set.intersection(e.tags)]
        if q.text_search:
            search_lower = q.text_search.lower()
            results = [
                e for e in results
                if search_lower in e.content.lower()
                or any(search_lower in str(v).lower() for v in e.metadata.values())
            ]

        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[: q.limit]

    def get_recent(self, agent_name: str | None = None, limit: int = 10) -> list[MemoryEntry]:
        """Get most recent entries, optionally filtered by agent."""
        entries = self._entries
        if agent_name:
            entries = [e for e in entries if e.agent_name == agent_name]
        return sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_by_id(self, memory_id: str) -> MemoryEntry | None:
        """Get a specific memory entry by ID."""
        for e in self._entries:
            if e.memory_id == memory_id:
                return e
        return None

    def get_children(self, parent_id: str) -> list[MemoryEntry]:
        """Get all child entries of a given parent."""
        return [e for e in self._entries if e.parent_id == parent_id]

    def count(self, agent_name: str | None = None) -> int:
        """Count entries, optionally filtered by agent."""
        if agent_name:
            return sum(1 for e in self._entries if e.agent_name == agent_name)
        return len(self._entries)

    def summary(self) -> dict[str, Any]:
        """Get a summary of memory contents."""
        type_counts: dict[str, int] = {}
        agent_counts: dict[str, int] = {}
        for e in self._entries:
            type_counts[e.memory_type.value] = type_counts.get(e.memory_type.value, 0) + 1
            agent_counts[e.agent_name] = agent_counts.get(e.agent_name, 0) + 1

        return {
            "total_entries": len(self._entries),
            "type_counts": type_counts,
            "agent_counts": agent_counts,
            "oldest_timestamp": self._entries[0].timestamp if self._entries else None,
            "newest_timestamp": self._entries[-1].timestamp if self._entries else None,
        }

    def _auto_prune(self) -> None:
        """Remove entries that exceed max count or max age."""
        now = time.time()
        self._entries = [
            e for e in self._entries
            if (now - e.timestamp) < self._max_age_seconds
        ]
        if len(self._entries) > self._max_entries:
            excess = len(self._entries) - self._max_entries
            self._entries = self._entries[excess:]

    def to_list(self) -> list[dict[str, Any]]:
        """Serialize all entries to a list of dicts."""
        return [e.model_dump(mode="json") for e in self._entries]

    @classmethod
    def from_list(
        cls,
        data: list[dict[str, Any]],
        max_entries: int = 500,
        max_age_seconds: float = 7200.0,
    ) -> ConversationBuffer:
        """Deserialize from a list of dicts."""
        buf = cls(max_entries=max_entries, max_age_seconds=max_age_seconds)
        buf._entries = [MemoryEntry(**d) for d in data]
        return buf


class WorkingMemory:
    """Current investigation state: active hypotheses, in-progress decisions,
    pending tasks, and agent-specific working sets.

    Unlike ConversationBuffer (append-only log), WorkingMemory is a
    key-value store where entries can be updated/replaced.
    """

    def __init__(self) -> None:
        self._store: dict[str, MemoryEntry] = {}
        self._agent_keys: dict[str, list[str]] = {}

    def set(
        self,
        key: str,
        agent_name: str,
        memory_type: MemoryType,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> MemoryEntry:
        """Set or update a working memory entry by key."""
        entry = MemoryEntry(
            agent_name=agent_name,
            memory_type=memory_type,
            content=content,
            metadata=metadata or {},
            tags=tags or [],
        )
        self._store[key] = entry

        if agent_name not in self._agent_keys:
            self._agent_keys[agent_name] = []
        if key not in self._agent_keys[agent_name]:
            self._agent_keys[agent_name].append(key)

        return entry

    def get(self, key: str) -> MemoryEntry | None:
        """Get a working memory entry by key."""
        return self._store.get(key)

    def get_by_agent(self, agent_name: str) -> dict[str, MemoryEntry]:
        """Get all working memory entries for a specific agent."""
        keys = self._agent_keys.get(agent_name, [])
        return {k: self._store[k] for k in keys if k in self._store}

    def remove(self, key: str) -> bool:
        """Remove a working memory entry."""
        if key in self._store:
            entry = self._store.pop(key)
            agent_keys = self._agent_keys.get(entry.agent_name, [])
            if key in agent_keys:
                agent_keys.remove(key)
            return True
        return False

    def keys(self) -> list[str]:
        """List all working memory keys."""
        return list(self._store.keys())

    def count(self) -> int:
        """Count working memory entries."""
        return len(self._store)

    def summary(self) -> dict[str, Any]:
        """Summary of working memory state."""
        agent_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        for entry in self._store.values():
            agent_counts[entry.agent_name] = agent_counts.get(entry.agent_name, 0) + 1
            type_counts[entry.memory_type.value] = type_counts.get(entry.memory_type.value, 0) + 1

        return {
            "total_entries": len(self._store),
            "keys": list(self._store.keys()),
            "agent_counts": agent_counts,
            "type_counts": type_counts,
        }

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Serialize to dict."""
        return {k: v.model_dump(mode="json") for k, v in self._store.items()}

    @classmethod
    def from_dict(cls, data: dict[str, dict[str, Any]]) -> WorkingMemory:
        """Deserialize from dict."""
        wm = cls()
        for k, v in data.items():
            entry = MemoryEntry(**v)
            wm._store[k] = entry
            agent_name = entry.agent_name
            if agent_name not in wm._agent_keys:
                wm._agent_keys[agent_name] = []
            wm._agent_keys[agent_name].append(k)
        return wm


class AgentMemory:
    """Unified memory interface combining ConversationBuffer + WorkingMemory.

    Each investigation gets its own AgentMemory instance.
    Agents record observations/decisions via conversation buffer,
    and maintain active state via working memory.
    """

    def __init__(
        self,
        investigation_id: str = "",
        max_conversation_entries: int = 500,
        max_conversation_age: float = 7200.0,
    ) -> None:
        self.investigation_id = investigation_id
        self.conversation = ConversationBuffer(
            max_entries=max_conversation_entries,
            max_age_seconds=max_conversation_age,
        )
        self.working = WorkingMemory()

    def record(
        self,
        agent_name: str,
        memory_type: MemoryType,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> MemoryEntry:
        """Record a memory in the conversation buffer."""
        return self.conversation.record(
            agent_name=agent_name,
            memory_type=memory_type,
            content=content,
            metadata=metadata,
            investigation_id=self.investigation_id,
            tags=tags,
        )

    def remember(
        self,
        key: str,
        agent_name: str,
        memory_type: MemoryType,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> MemoryEntry:
        """Store/update a working memory entry."""
        return self.working.set(
            key=key,
            agent_name=agent_name,
            memory_type=memory_type,
            content=content,
            metadata=metadata,
            tags=tags,
        )

    def recall(self, key: str) -> MemoryEntry | None:
        """Retrieve a working memory entry."""
        return self.working.get(key)

    def search(
        self,
        text: str | None = None,
        agent_name: str | None = None,
        memory_type: MemoryType | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Search conversation memory."""
        q = MemoryQuery(
            agent_name=agent_name,
            memory_type=memory_type,
            text_search=text,
            limit=limit,
        )
        return self.conversation.query(q)

    def get_agent_context(self, agent_name: str, limit: int = 20) -> dict[str, Any]:
        """Get a full context snapshot for an agent: recent conversation + working memory."""
        recent = self.conversation.get_recent(agent_name=agent_name, limit=limit)
        working = self.working.get_by_agent(agent_name)

        return {
            "agent_name": agent_name,
            "recent_memories": [m.model_dump(mode="json") for m in recent],
            "working_memory": {k: v.model_dump(mode="json") for k, v in working.items()},
            "conversation_summary": self.conversation.summary(),
            "working_summary": self.working.summary(),
        }

    def summary(self) -> dict[str, Any]:
        """Full memory summary."""
        return {
            "investigation_id": self.investigation_id,
            "conversation": self.conversation.summary(),
            "working_memory": self.working.summary(),
        }

    def to_state_dict(self) -> dict[str, Any]:
        """Serialize for storage in InvestigationState."""
        return {
            "investigation_id": self.investigation_id,
            "conversation_entries": self.conversation.to_list(),
            "working_entries": self.working.to_dict(),
        }

    @classmethod
    def from_state_dict(cls, data: dict[str, Any]) -> AgentMemory:
        """Deserialize from InvestigationState storage."""
        mem = cls(investigation_id=data.get("investigation_id", ""))
        mem.conversation = ConversationBuffer.from_list(
            data.get("conversation_entries", [])
        )
        mem.working = WorkingMemory.from_dict(
            data.get("working_entries", {})
        )
        return mem
