"""Shared bounded tool-execution helpers for Mnemos agents."""

from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any

MAX_TOOL_CALLS_PER_AGENT = 8
TOOL_CALL_TIMEOUT_SECONDS = 15.0


def _safe_summary(value: Any, limit: int = 240) -> str:
    text = str(value)
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


async def execute_governed_tool(
    *,
    agent_name: str,
    server: Any,
    tool_name: str,
    arguments: dict[str, Any],
    state: dict[str, Any] | None,
) -> Any:
    """Execute one scoped tool call and append a bounded trajectory record."""
    if server is None:
        return {"success": False, "error": "Tool server not injected"}

    runtime_state = state or {}
    context = runtime_state.setdefault("context", {})
    counts = context.setdefault("tool_call_counts", {})
    current_count = int(counts.get(agent_name, 0))
    if current_count >= MAX_TOOL_CALLS_PER_AGENT:
        return {
            "success": False,
            "error": f"Tool call budget exhausted for agent '{agent_name}'",
        }

    counts[agent_name] = current_count + 1
    investigation_id = runtime_state.get("investigation_id", "")
    trace_id = runtime_state.get("trace_id")
    user_context = {
        "org_id": context.get("org_id", ""),
        "site_id": context.get("site_id", ""),
        "user_id": context.get("user_id", ""),
        "role": context.get("role", "engineer"),
        "access_classifications": context.get("access_classifications", ["internal"]),
        "asset_ids": context.get("asset_ids", []),
        "document_ids": context.get("document_ids", []),
    }

    started = perf_counter()
    try:
        async with asyncio.timeout(TOOL_CALL_TIMEOUT_SECONDS):
            result = await server.call(
                tool_name=tool_name,
                arguments=arguments,
                agent_name=agent_name,
                investigation_id=investigation_id,
                trace_id=trace_id,
                user_context=user_context,
            )
        success = bool(getattr(result, "success", False))
        data = getattr(result, "data", None)
        error = getattr(result, "error", None)
    except TimeoutError:
        success = False
        data = None
        error = f"Tool '{tool_name}' timed out after {TOOL_CALL_TIMEOUT_SECONDS:.0f}s"
    except Exception as exc:  # noqa: BLE001 - tool boundaries must fail closed
        success = False
        data = None
        error = f"Tool '{tool_name}' failed: {type(exc).__name__}"

    duration_ms = round((perf_counter() - started) * 1000, 2)
    trajectory = context.setdefault("tool_trajectory", [])
    trajectory.append(
        {
            "agent_name": agent_name,
            "tool_name": tool_name,
            "arguments": arguments,
            "success": success,
            "duration_ms": duration_ms,
            "result_summary": _safe_summary(data if success else error),
            "error": None if success else _safe_summary(error),
        }
    )

    if success:
        return data
    return {"success": False, "error": error or "Tool execution failed"}
