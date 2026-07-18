"""Architecture tests for the single Mnemos production runtime."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_orchestrator_uses_only_canonical_pipeline_factory() -> None:
    source = _source("src/mnemos/agentic/orchestrator.py")
    tree = ast.parse(source)

    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert "build_investigation_pipeline" in imported_names
    assert "create_investigation_workflow" not in imported_names
    assert "AgentRegistry" not in imported_names
    assert "InvestigationPipeline" not in imported_names

    assert "build_investigation_pipeline(db=self.db)" in source
    assert "self._registry" not in source
    assert "self._agent_functions" not in source


def test_public_agentic_api_exports_only_canonical_runtime() -> None:
    runtime_init = _source("src/mnemos/agentic/runtime/__init__.py")
    agentic_init = _source("src/mnemos/agentic/__init__.py")
    legacy_init = _source("src/mnemos/agentic/langgraph/__init__.py")

    assert '"build_investigation_pipeline"' in runtime_init
    assert '"InvestigationPipeline"' in runtime_init
    assert "create_investigation_workflow" not in runtime_init

    assert '"build_investigation_pipeline"' in agentic_init
    assert '"InvestigationPipeline"' in agentic_init
    assert "create_investigation_workflow" not in agentic_init

    assert "__all__: list[str] = []" in legacy_init


def test_pipeline_construction_has_one_production_factory() -> None:
    factory = _source("src/mnemos/agentic/runtime/factory.py")
    tree = ast.parse(factory)

    function_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert function_names == {"build_investigation_pipeline"}
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "InvestigationPipeline"
    ]
    assert len(calls) == 1

    keyword_names = {keyword.arg for keyword in calls[0].keywords}
    assert keyword_names == {
        "db",
        "checkpoint_store",
        "event_store",
        "audit_sink",
        "approval_queue",
        "node_registry",
    }
