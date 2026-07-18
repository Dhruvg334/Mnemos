"""Regression test preventing deprecated FastAPI event hooks from returning."""

from __future__ import annotations

import ast
from pathlib import Path


def test_main_uses_lifespan_instead_of_on_event() -> None:
    source = Path("src/mnemos/main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert ".on_event(" not in source
    assert "lifespan=lifespan" in source
    assert any(
        isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == "lifespan"
        for node in ast.walk(tree)
    )
