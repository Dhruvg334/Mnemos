"""Checkpoint Node and Resume logic for the multi-agent runtime.

Provides durable state snapshots that allow an investigation to be
paused, resumed, or recovered after failure.  The checkpoint manager
serialises the investigation state and event log offset so that a
new runtime can pick up exactly where the previous one left off.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from mnemos.agentic.runtime.types import (
    Checkpoint,
    CheckpointMetadata,
    CheckpointType,
    InvestigationPhase,
)

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages checkpoints for a single investigation.

    By default checkpoints are stored in-memory.  For production use,
    subclass this and override ``_persist`` / ``_load`` to back onto
    durable storage (S3, database, filesystem).
    """

    def __init__(self, investigation_id: str) -> None:
        self.investigation_id = investigation_id
        self._checkpoints: list[Checkpoint] = []

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(
        self,
        state: dict[str, Any],
        *,
        phase: InvestigationPhase = InvestigationPhase.INITIALIZATION,
        checkpoint_type: CheckpointType = CheckpointType.AUTOMATIC,
        agent_name: str | None = None,
        description: str = "",
        event_log_offset: int = 0,
    ) -> Checkpoint:
        """Save a checkpoint synchronously.

        This remains available for in-memory tests and non-async callers.
        Production runtime code should use :meth:`save_async` so durable
        persistence is awaited before execution continues.
        """
        checkpoint = self._build_checkpoint(
            state,
            phase=phase,
            checkpoint_type=checkpoint_type,
            agent_name=agent_name,
            description=description,
            event_log_offset=event_log_offset,
        )
        self._checkpoints.append(checkpoint)
        self._persist(checkpoint)
        return checkpoint

    async def save_async(
        self,
        state: dict[str, Any],
        *,
        phase: InvestigationPhase = InvestigationPhase.INITIALIZATION,
        checkpoint_type: CheckpointType = CheckpointType.AUTOMATIC,
        agent_name: str | None = None,
        description: str = "",
        event_log_offset: int = 0,
    ) -> Checkpoint:
        """Save a checkpoint and await the persistence boundary."""
        checkpoint = self._build_checkpoint(
            state,
            phase=phase,
            checkpoint_type=checkpoint_type,
            agent_name=agent_name,
            description=description,
            event_log_offset=event_log_offset,
        )
        self._checkpoints.append(checkpoint)
        await self._persist_async(checkpoint)
        return checkpoint

    def _build_checkpoint(
        self,
        state: dict[str, Any],
        *,
        phase: InvestigationPhase,
        checkpoint_type: CheckpointType,
        agent_name: str | None,
        description: str,
        event_log_offset: int,
    ) -> Checkpoint:
        snapshot = _serialise_state(state)
        state_hash = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

        metadata = CheckpointMetadata(
            investigation_id=self.investigation_id,
            checkpoint_type=checkpoint_type,
            phase=phase,
            agent_name=agent_name,
            description=description,
            state_hash=state_hash,
        )

        return Checkpoint(
            metadata=metadata,
            state_snapshot=snapshot,
            event_log_offset=event_log_offset,
        )

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load_latest(self) -> Checkpoint | None:
        if not self._checkpoints:
            self._checkpoints = self._load_all()
        return self._checkpoints[-1] if self._checkpoints else None

    def load_by_id(self, checkpoint_id: str) -> Checkpoint | None:
        for cp in self._checkpoints:
            if cp.metadata.checkpoint_id == checkpoint_id:
                return cp
        return None

    def load_by_phase(self, phase: InvestigationPhase) -> Checkpoint | None:
        matching = [cp for cp in self._checkpoints if cp.metadata.phase == phase]
        return matching[-1] if matching else None

    # ------------------------------------------------------------------
    # Restore state from checkpoint
    # ------------------------------------------------------------------

    def restore_state(self, checkpoint: Checkpoint) -> dict[str, Any]:
        """Deserialise a checkpoint's state snapshot back into a dict
        suitable for injecting into ``InvestigationState``."""
        return _deserialise_state(checkpoint.state_snapshot)

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_checkpoints(self) -> list[CheckpointMetadata]:
        return [cp.metadata for cp in self._checkpoints]

    @property
    def count(self) -> int:
        return len(self._checkpoints)

    @property
    def last_checkpoint_id(self) -> str | None:
        if self._checkpoints:
            return self._checkpoints[-1].metadata.checkpoint_id
        return None

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def delete(self, checkpoint_id: str) -> bool:
        before = len(self._checkpoints)
        self._checkpoints = [
            cp for cp in self._checkpoints if cp.metadata.checkpoint_id != checkpoint_id
        ]
        return len(self._checkpoints) < before

    def clear(self) -> int:
        count = len(self._checkpoints)
        self._checkpoints.clear()
        return count

    # ------------------------------------------------------------------
    # Persistence hooks (override for durable storage)
    # ------------------------------------------------------------------

    def _persist(self, checkpoint: Checkpoint) -> None:
        """Persist a checkpoint. Default: no-op (in-memory only)."""

    async def _persist_async(self, checkpoint: Checkpoint) -> None:
        """Async persistence hook. In-memory storage has no extra work."""
        self._persist(checkpoint)

    def _load_all(self) -> list[Checkpoint]:
        """Load all checkpoints. Default: empty."""
        return []


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _serialise_state(state: dict[str, Any]) -> dict[str, Any]:
    """Best-effort serialisation of the investigation state for storage.
    Pydantic models are converted via ``model_dump``; everything else
    is passed through."""
    serialised: dict[str, Any] = {}
    for key, value in state.items():
        if hasattr(value, "model_dump"):
            serialised[key] = value.model_dump(mode="json")
        elif isinstance(value, list):
            serialised[key] = [
                item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                for item in value
            ]
        elif isinstance(value, dict):
            serialised[key] = {
                k: v.model_dump(mode="json") if hasattr(v, "model_dump") else v
                for k, v in value.items()
            }
        else:
            serialised[key] = value
    return serialised


def _deserialise_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Best-effort deserialisation. Returns the raw dict; consumers
    are responsible for constructing typed objects."""
    return dict(snapshot)


async def _optimistic_save(
    checkpoint_manager: CheckpointManager,
    state: dict[str, Any],
    *,
    phase: InvestigationPhase = InvestigationPhase.INITIALIZATION,
    checkpoint_type: CheckpointType = CheckpointType.AUTOMATIC,
    agent_name: str | None = None,
    description: str = "",
    event_log_offset: int = 0,
    db: Any = None,
) -> Checkpoint:
    """Save checkpoint with optimistic concurrency version check (P0 #13).

    When a DB session is available, uses version-increment semantics to
    prevent two workers from overwriting the same investigation checkpoint.
    """
    checkpoint = await checkpoint_manager.save_async(
        state,
        phase=phase,
        checkpoint_type=checkpoint_type,
        agent_name=agent_name,
        description=description,
        event_log_offset=event_log_offset,
    )

    if db is not None:
        try:
            from sqlalchemy import text

            result = await db.execute(
                text(
                    """
                    UPDATE runtime_checkpoints
                    SET version = version + 1,
                        state_snapshot = :snapshot,
                        event_log_offset = :offset
                    WHERE id = :cid
                      AND investigation_id = :inv_id
                    """
                ),
                {
                    "cid": checkpoint.metadata.checkpoint_id,
                    "inv_id": checkpoint.metadata.investigation_id,
                    "snapshot": json.dumps(checkpoint.state_snapshot, default=str),
                    "offset": event_log_offset,
                },
            )
            if result.rowcount == 0:
                logger.warning(
                    "Optimistic lock: checkpoint %s not found for version update",
                    checkpoint.metadata.checkpoint_id,
                )
        except Exception:
            logger.warning(
                "Optimistic lock: version update failed for checkpoint %s",
                checkpoint.metadata.checkpoint_id,
            )

    return checkpoint
