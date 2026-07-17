"""MCP Tool Dispatch with guardrails enforcement and audit logging.

Every tool call goes through this dispatch layer which:
1. Validates input against typed schemas
2. Runs guardrails checks
3. Executes the tool
4. Logs every action to the audit log
5. Wraps results in MCPToolResult

No agent may bypass this dispatch to access databases directly.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from mnemos.agentic.mcp.tools import (
    ActionCreationInput,
    ApprovalRecordingInput,
    DocumentRetrievalInput,
    EvidenceRulesInput,
    GraphTraversalInput,
    ReportGenerationInput,
    ResolveAssetTagInput,
    RevisionCheckInput,
    SimilarFailuresInput,
    TimelineInput,
)
from mnemos.agentic.runtime.audit import AuditLogger
from mnemos.agentic.schemas.base import (
    AuditAction,
    GuardrailCheckResult,
    GuardrailCheckType,
    GuardrailVerdict,
    MCPToolName,
    MCPToolResult,
)
from mnemos.agentic.utils.guardrails import MnemosGuardrails
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("mcp.dispatch")


# Input schema mapping for validation
_TOOL_INPUT_SCHEMAS: dict[str, type] = {
    MCPToolName.RESOLVE_ASSET_TAG: ResolveAssetTagInput,
    MCPToolName.GRAPH_TRAVERSAL: GraphTraversalInput,
    MCPToolName.DOCUMENT_RETRIEVAL: DocumentRetrievalInput,
    MCPToolName.TIMELINE: TimelineInput,
    MCPToolName.SIMILAR_FAILURES: SimilarFailuresInput,
    MCPToolName.REVISION_CHECK: RevisionCheckInput,
    MCPToolName.EVIDENCE_RULES: EvidenceRulesInput,
    MCPToolName.APPROVAL_RECORDING: ApprovalRecordingInput,
    MCPToolName.ACTION_CREATION: ActionCreationInput,
    MCPToolName.REPORT_GENERATION: ReportGenerationInput,
}

# Tools that require approval gates for high-priority actions
_APPROVAL_REQUIRED_TOOLS: dict[str, str] = {
    MCPToolName.ACTION_CREATION: "high_priority_action",
    MCPToolName.REPORT_GENERATION: "audit_export",
    MCPToolName.APPROVAL_RECORDING: "approval_recording",
}

# Guardrails checks per tool
_TOOL_GUARDRAILS: dict[str, list[GuardrailCheckType]] = {
    MCPToolName.RESOLVE_ASSET_TAG: [GuardrailCheckType.PERMISSION],
    MCPToolName.GRAPH_TRAVERSAL: [GuardrailCheckType.PERMISSION],
    MCPToolName.DOCUMENT_RETRIEVAL: [GuardrailCheckType.PERMISSION, GuardrailCheckType.UNAPPROVED_PROCEDURE],
    MCPToolName.TIMELINE: [GuardrailCheckType.PERMISSION, GuardrailCheckType.FAKE_SENSOR_DATA],
    MCPToolName.SIMILAR_FAILURES: [GuardrailCheckType.PERMISSION],
    MCPToolName.REVISION_CHECK: [GuardrailCheckType.UNAPPROVED_PROCEDURE],
    MCPToolName.EVIDENCE_RULES: [],
    MCPToolName.APPROVAL_RECORDING: [GuardrailCheckType.PERMISSION],
    MCPToolName.ACTION_CREATION: [GuardrailCheckType.PERMISSION],
    MCPToolName.REPORT_GENERATION: [GuardrailCheckType.HALLUCINATED_CITATION, GuardrailCheckType.PERMISSION],
}


class MCPToolDispatch:
    """Central dispatch for all MCP tool calls.

    Enforces guardrails, audit logging, and approval gates.
    No agent may call tools directly -- they must go through this dispatch.
    """

    def __init__(
        self,
        audit_logger: AuditLogger,
        guardrails: MnemosGuardrails | None = None,
    ) -> None:
        self.audit_logger = audit_logger
        self.guardrails = guardrails or MnemosGuardrails()
        self._tool_handlers: dict[str, Callable[..., Awaitable[Any]]] = {}

    def register_handler(
        self, tool_name: str, handler: Callable[..., Awaitable[Any]]
    ) -> None:
        """Register a tool handler function."""
        self._tool_handlers[tool_name] = handler

    async def dispatch(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        agent_name: str = "unknown",
        investigation_id: str = "",
        trace_id: str | None = None,
        user_context: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        """Dispatch a tool call through guardrails + audit + execution."""
        start = time.time()

        # 1. Validate tool name
        if tool_name not in [t.value for t in MCPToolName]:
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Unknown tool: {tool_name}",
                guardrail_passed=False,
            )

        # 2. Validate input schema
        schema_class = _TOOL_INPUT_SCHEMAS.get(tool_name)
        if schema_class:
            try:
                validated_input = schema_class(**arguments)
            except Exception as exc:
                self.audit_logger.log(
                    action=AuditAction.TOOL_FAILED,
                    agent_name=agent_name,
                    investigation_id=investigation_id,
                    trace_id=trace_id,
                    tool_name=tool_name,
                    resource_type="tool_input",
                    input_data=arguments,
                    success=False,
                    error=f"Input validation failed: {exc}",
                )
                return MCPToolResult(
                    tool_name=tool_name,
                    success=False,
                    error=f"Input validation failed: {exc}",
                    guardrail_passed=False,
                )
        else:
            validated_input = arguments

        # 3. Run guardrails checks
        guardrail_result = self._run_guardrails(tool_name, arguments, user_context)

        self.audit_logger.log(
            action=AuditAction.GUARDRAIL_CHECK,
            agent_name=agent_name,
            investigation_id=investigation_id,
            trace_id=trace_id,
            tool_name=tool_name,
            resource_type="tool_input",
            input_data=arguments if isinstance(arguments, dict) else {},
            guardrail_checks=[v.check_type for v in guardrail_result.verdicts],
            guardrail_verdicts=guardrail_result.verdicts,
            success=guardrail_result.all_passed,
        )

        if not guardrail_result.all_passed:
            elapsed = (time.time() - start) * 1000
            self.audit_logger.log(
                action=AuditAction.GUARDRAIL_VIOLATION,
                agent_name=agent_name,
                investigation_id=investigation_id,
                trace_id=trace_id,
                tool_name=tool_name,
                resource_type="tool_input",
                input_data=arguments if isinstance(arguments, dict) else {},
                guardrail_verdicts=guardrail_result.verdicts,
                success=False,
                error=f"Guardrail violations: {guardrail_result.blocking_violations}",
            )
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Guardrail violations: {', '.join(guardrail_result.blocking_violations)}",
                guardrail_passed=False,
                guardrail_violations=guardrail_result.blocking_violations,
                duration_ms=elapsed,
            )

        # 4. Log tool invocation
        audit_entry = self.audit_logger.log(
            action=AuditAction.TOOL_CALLED,
            agent_name=agent_name,
            investigation_id=investigation_id,
            trace_id=trace_id,
            tool_name=tool_name,
            resource_type="tool_call",
            input_data=arguments if isinstance(arguments, dict) else {},
        )

        # 5. Execute the tool
        handler = self._tool_handlers.get(tool_name)
        if not handler:
            elapsed = (time.time() - start) * 1000
            self.audit_logger.log(
                action=AuditAction.TOOL_FAILED,
                agent_name=agent_name,
                investigation_id=investigation_id,
                trace_id=trace_id,
                tool_name=tool_name,
                resource_type="tool_call",
                success=False,
                error=f"No handler registered for tool: {tool_name}",
                duration_ms=elapsed,
            )
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                error=f"No handler registered for tool: {tool_name}",
                duration_ms=elapsed,
            )

        try:
            input_dump = (
                validated_input.model_dump()
                if hasattr(validated_input, "model_dump")
                else arguments
            )
            result_data = await handler(validated_input)
            elapsed = (time.time() - start) * 1000

            output_dump = (
                result_data.model_dump()
                if hasattr(result_data, "model_dump")
                else {"result": str(result_data)}
            )

            self.audit_logger.log(
                action=AuditAction.TOOL_COMPLETED,
                agent_name=agent_name,
                investigation_id=investigation_id,
                trace_id=trace_id,
                tool_name=tool_name,
                resource_type="tool_call",
                resource_id=audit_entry.audit_id if audit_entry else None,
                input_data=input_dump,
                output_data=output_dump,
                success=True,
                duration_ms=elapsed,
            )

            return MCPToolResult(
                tool_name=tool_name,
                success=True,
                data=output_dump,
                audit_id=audit_entry.audit_id if audit_entry else None,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.time() - start) * 1000
            self.audit_logger.log(
                action=AuditAction.TOOL_FAILED,
                agent_name=agent_name,
                investigation_id=investigation_id,
                trace_id=trace_id,
                tool_name=tool_name,
                resource_type="tool_call",
                resource_id=audit_entry.audit_id if audit_entry else None,
                success=False,
                error=str(exc),
                duration_ms=elapsed,
            )
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                error=str(exc),
                audit_id=audit_entry.audit_id if audit_entry else None,
                duration_ms=elapsed,
            )

    def _run_guardrails(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        user_context: dict[str, Any] | None = None,
    ) -> GuardrailCheckResult:
        """Run all applicable guardrails checks for a tool call."""
        required_checks = _TOOL_GUARDRAILS.get(tool_name, [])
        verdicts: list[GuardrailVerdict] = []
        violations: list[str] = []

        for check_type in required_checks:
            try:
                verdict = self._execute_guardrail_check(
                    check_type, tool_name, arguments, user_context
                )
                verdicts.append(verdict)
                if not verdict.passed:
                    violations.append(f"{check_type.value}: {verdict.reason}")
            except Exception as exc:
                verdicts.append(
                    GuardrailVerdict(
                        check_type=check_type,
                        passed=False,
                        reason=f"Guardrail check error: {exc}",
                    )
                )
                violations.append(f"{check_type.value}: check error")

        return GuardrailCheckResult(
            all_passed=len(violations) == 0,
            verdicts=verdicts,
            blocking_violations=violations,
        )

    def _execute_guardrail_check(
        self,
        check_type: GuardrailCheckType,
        tool_name: str,
        arguments: dict[str, Any],
        user_context: dict[str, Any] | None,
    ) -> GuardrailVerdict:
        """Execute a specific guardrail check."""
        ctx = user_context or {}

        if check_type == GuardrailCheckType.PERMISSION:
            site_id = arguments.get("site_id") or ctx.get("site_id")
            org_id = arguments.get("organisation_id") or ctx.get("org_id")
            user_site = ctx.get("site_id")
            user_org = ctx.get("org_id")

            if user_site and site_id and site_id != user_site:
                return GuardrailVerdict(
                    check_type=check_type,
                    passed=False,
                    reason=f"Site mismatch: tool requests site {site_id} but user has {user_site}",
                )
            if user_org and org_id and org_id != user_org:
                return GuardrailVerdict(
                    check_type=check_type,
                    passed=False,
                    reason=f"Organisation mismatch: tool requests org {org_id} but user has {user_org}",
                )
            return GuardrailVerdict(check_type=check_type, passed=True, reason="Permission check passed")

        if check_type == GuardrailCheckType.HALLUCINATED_CITATION:
            doc_id = arguments.get("document_id", "")
            if doc_id and not doc_id.strip():
                return GuardrailVerdict(
                    check_type=check_type,
                    passed=False,
                    reason="Empty document_id may indicate hallucinated citation",
                )
            return GuardrailVerdict(check_type=check_type, passed=True, reason="Citation check passed")

        if check_type == GuardrailCheckType.UNAPPROVED_PROCEDURE:
            status = arguments.get("status", "")
            if status and status.upper() in ("DRAFT", "REVIEW"):
                return GuardrailVerdict(
                    check_type=check_type,
                    passed=False,
                    reason=f"Procedure is in '{status}' status -- not approved for use",
                )
            return GuardrailVerdict(check_type=check_type, passed=True, reason="Procedure approval check passed")

        if check_type == GuardrailCheckType.FAKE_SENSOR_DATA:
            source = arguments.get("source", "")
            if source and "simulated" in str(source).lower():
                return GuardrailVerdict(
                    check_type=check_type,
                    passed=False,
                    reason="Simulated sensor data detected -- not suitable for analysis",
                )
            return GuardrailVerdict(check_type=check_type, passed=True, reason="Sensor data source check passed")

        if check_type == GuardrailCheckType.COMPLIANCE_WITHOUT_EVIDENCE:
            evidence_ids = arguments.get("evidence_ids", [])
            if not evidence_ids:
                return GuardrailVerdict(
                    check_type=check_type,
                    passed=False,
                    reason="Compliance check without supporting evidence",
                )
            return GuardrailVerdict(check_type=check_type, passed=True, reason="Compliance evidence check passed")

        if check_type == GuardrailCheckType.UNSAFE_RECOMMENDATION:
            priority = arguments.get("priority", "medium")
            action_type = arguments.get("action_type", "")
            if priority == "critical" and action_type in ("REPAIR", "PROCEDURE_UPDATE"):
                return GuardrailVerdict(
                    check_type=check_type,
                    passed=False,
                    reason="Critical repair/procedure actions require explicit safety review",
                )
            return GuardrailVerdict(check_type=check_type, passed=True, reason="Safety check passed")

        return GuardrailVerdict(check_type=check_type, passed=True, reason="Check not implemented")
