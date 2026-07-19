"""Deterministic evaluation gates for governed agent tool selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mnemos.agentic.schemas.base import QueryIntent


@dataclass(frozen=True)
class ToolSelectionPolicy:
    """Expected governed-tool behaviour for one query intent."""

    allowed_tools: frozenset[str]
    required_any: tuple[frozenset[str], ...] = ()
    max_calls: int = 8
    per_call_latency_budget_ms: float = 5_000.0


@dataclass(frozen=True)
class ToolSelectionEvaluation:
    """Deterministic tool-selection quality result suitable for CI gating."""

    intent: str
    score: float
    selected_tools: tuple[str, ...]
    unnecessary_tools: tuple[str, ...]
    missing_required_groups: tuple[tuple[str, ...], ...]
    scope_violations: tuple[str, ...]
    latency_violations: tuple[str, ...]
    duplicate_calls: int
    total_calls: int

    @property
    def passed(self) -> bool:
        return (
            self.score >= 0.8
            and not self.scope_violations
            and not self.missing_required_groups
            and not self.latency_violations
        )


TOOL_SELECTION_POLICIES: dict[QueryIntent, ToolSelectionPolicy] = {
    QueryIntent.ASSET_INFO: ToolSelectionPolicy(
        allowed_tools=frozenset({"resolve_asset_tag", "timeline", "graph_traversal"}),
        required_any=(frozenset({"resolve_asset_tag", "timeline"}),),
    ),
    QueryIntent.RCA: ToolSelectionPolicy(
        allowed_tools=frozenset(
            {
                "resolve_asset_tag",
                "timeline",
                "graph_traversal",
                "similar_failures",
            }
        ),
        required_any=(
            frozenset({"resolve_asset_tag"}),
            frozenset({"timeline", "graph_traversal", "similar_failures"}),
        ),
    ),
    QueryIntent.COMPLIANCE: ToolSelectionPolicy(
        allowed_tools=frozenset({"resolve_asset_tag", "revision_check"}),
        required_any=(frozenset({"revision_check"}),),
    ),
    QueryIntent.LESSONS_LEARNED: ToolSelectionPolicy(
        allowed_tools=frozenset(
            {"resolve_asset_tag", "timeline", "graph_traversal", "similar_failures"}
        ),
        required_any=(frozenset({"similar_failures", "timeline"}),),
    ),
    QueryIntent.GENERAL: ToolSelectionPolicy(
        allowed_tools=frozenset({"resolve_asset_tag"}),
        max_calls=3,
    ),
}


def evaluate_tool_trajectory(
    *,
    intent: QueryIntent | str,
    trajectory: list[dict[str, Any]],
    scoped_asset_ids: list[str] | tuple[str, ...] = (),
    scoped_document_ids: list[str] | tuple[str, ...] = (),
) -> ToolSelectionEvaluation:
    """Evaluate selection, scope adherence, duplication, and latency deterministically."""
    resolved_intent = intent if isinstance(intent, QueryIntent) else QueryIntent(intent)
    policy = TOOL_SELECTION_POLICIES[resolved_intent]
    selected = tuple(str(call.get("tool_name", "")) for call in trajectory)
    unnecessary = tuple(sorted({name for name in selected if name not in policy.allowed_tools}))

    selected_set = set(selected)
    missing = tuple(
        tuple(sorted(group)) for group in policy.required_any if not selected_set.intersection(group)
    )

    scope_violations = _scope_violations(
        trajectory,
        scoped_asset_ids=set(scoped_asset_ids),
        scoped_document_ids=set(scoped_document_ids),
    )
    latency_violations = tuple(
        f"{call.get('tool_name', '<unknown>')}:{float(call.get('duration_ms', 0.0)):.2f}ms"
        for call in trajectory
        if float(call.get("duration_ms", 0.0)) > policy.per_call_latency_budget_ms
    )

    signatures = [
        (str(call.get("tool_name", "")), _freeze(call.get("arguments", {})))
        for call in trajectory
    ]
    duplicate_calls = len(signatures) - len(set(signatures))

    penalties = 0.0
    penalties += 0.25 * len(unnecessary)
    penalties += 0.30 * len(missing)
    penalties += 0.40 * len(scope_violations)
    penalties += 0.15 * len(latency_violations)
    penalties += 0.05 * duplicate_calls
    if len(trajectory) > policy.max_calls:
        penalties += min(0.5, 0.05 * (len(trajectory) - policy.max_calls))

    return ToolSelectionEvaluation(
        intent=resolved_intent.value,
        score=round(max(0.0, 1.0 - penalties), 4),
        selected_tools=selected,
        unnecessary_tools=unnecessary,
        missing_required_groups=missing,
        scope_violations=scope_violations,
        latency_violations=latency_violations,
        duplicate_calls=duplicate_calls,
        total_calls=len(trajectory),
    )


def _scope_violations(
    trajectory: list[dict[str, Any]],
    *,
    scoped_asset_ids: set[str],
    scoped_document_ids: set[str],
) -> tuple[str, ...]:
    violations: list[str] = []
    for call in trajectory:
        tool_name = str(call.get("tool_name", "<unknown>"))
        arguments = call.get("arguments", {})
        if not isinstance(arguments, dict):
            violations.append(f"{tool_name}:arguments_not_object")
            continue

        for key in ("asset_id", "source_asset_id", "target_asset_id"):
            value = arguments.get(key)
            if value and scoped_asset_ids and str(value) not in scoped_asset_ids:
                violations.append(f"{tool_name}:{key}={value}")

        for key in ("document_id", "source_document_id"):
            value = arguments.get(key)
            if value and scoped_document_ids and str(value) not in scoped_document_ids:
                violations.append(f"{tool_name}:{key}={value}")

    return tuple(violations)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    if isinstance(value, list | tuple | set | frozenset):
        return tuple(_freeze(item) for item in value)
    return value
