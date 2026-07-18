"""Tests for the awaited runtime checkpoint persistence boundary."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from mnemos.agentic.runtime.checkpoint import CheckpointManager
from mnemos.agentic.runtime.types import Checkpoint

ROOT = Path(__file__).resolve().parents[1]


class RecordingCheckpointManager(CheckpointManager):
    """Checkpoint manager that exposes whether async persistence completed."""

    def __init__(self, investigation_id: str) -> None:
        super().__init__(investigation_id)
        self.persisted = False

    async def _persist_async(self, checkpoint: Checkpoint) -> None:
        await asyncio.sleep(0)
        self.persisted = True


@pytest.mark.asyncio
async def test_save_async_waits_for_persistence() -> None:
    manager = RecordingCheckpointManager("inv_awaited")

    checkpoint = await manager.save_async({"query": "Why did P-117 fail?"})

    assert manager.persisted is True
    assert manager.last_checkpoint_id == checkpoint.metadata.checkpoint_id
    assert checkpoint.state_snapshot["query"] == "Why did P-117 fail?"


def test_production_workflow_does_not_use_sync_checkpoint_save() -> None:
    source = (ROOT / "src/mnemos/agentic/runtime/workflow.py").read_text(
        encoding="utf-8"
    )

    assert "checkpoint_manager.save(" not in source
    assert "checkpoint_manager.save_async(" in source


def test_checkpoint_manager_exposes_async_persistence_hook() -> None:
    manager = CheckpointManager("inv_contract")

    assert hasattr(manager, "save_async")
    assert hasattr(manager, "_persist_async")
