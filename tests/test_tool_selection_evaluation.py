"""CI regression gates for governed tool selection."""

from __future__ import annotations

from mnemos.agentic.evaluation.tool_selection import evaluate_tool_trajectory
from mnemos.agentic.schemas.base import QueryIntent


def _call(tool_name: str, arguments: dict, duration_ms: float = 25.0) -> dict:
    return {
        "agent_name": "evaluation_fixture",
        "tool_name": tool_name,
        "arguments": arguments,
        "success": True,
        "duration_ms": duration_ms,
    }


def test_rca_tool_selection_passes_with_scoped_complementary_tools() -> None:
    evaluation = evaluate_tool_trajectory(
        intent=QueryIntent.RCA,
        trajectory=[
            _call("resolve_asset_tag", {"mention": "P-101"}),
            _call("timeline", {"asset_id": "asset-101"}),
            _call("similar_failures", {"asset_id": "asset-101"}),
        ],
        scoped_asset_ids=["asset-101"],
    )

    assert evaluation.passed is True
    assert evaluation.score == 1.0
    assert evaluation.scope_violations == ()


def test_scope_violation_fails_tool_selection_gate() -> None:
    evaluation = evaluate_tool_trajectory(
        intent=QueryIntent.RCA,
        trajectory=[
            _call("resolve_asset_tag", {"mention": "P-101"}),
            _call("timeline", {"asset_id": "asset-outside-scope"}),
        ],
        scoped_asset_ids=["asset-101"],
    )

    assert evaluation.passed is False
    assert evaluation.scope_violations == (
        "timeline:asset_id=asset-outside-scope",
    )


def test_compliance_gate_rejects_wrong_and_missing_tool_choice() -> None:
    evaluation = evaluate_tool_trajectory(
        intent=QueryIntent.COMPLIANCE,
        trajectory=[_call("similar_failures", {"asset_id": "asset-101"})],
        scoped_asset_ids=["asset-101"],
    )

    assert evaluation.passed is False
    assert evaluation.unnecessary_tools == ("similar_failures",)
    assert evaluation.missing_required_groups == (("revision_check",),)


def test_latency_and_duplicate_calls_reduce_selection_score() -> None:
    call = _call("revision_check", {"document_id": "doc-1"}, duration_ms=5_500.0)
    evaluation = evaluate_tool_trajectory(
        intent=QueryIntent.COMPLIANCE,
        trajectory=[call, dict(call)],
        scoped_document_ids=["doc-1"],
    )

    assert evaluation.passed is False
    assert evaluation.duplicate_calls == 1
    assert len(evaluation.latency_violations) == 2
