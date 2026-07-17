"""MCP Server for the Mnemos agentic runtime.

Exposes 12 typed MCP tools to agents via the dispatch layer.
All tools are strictly typed, guardrail-checked, and audit-logged.
No agent may access databases directly.
"""

from __future__ import annotations

from typing import Any

from mnemos.agentic.mcp.dispatch import MCPToolDispatch
from mnemos.agentic.mcp.tools import (
    ActionCreationInput,
    ActionCreationOutput,
    ApprovalRecordingInput,
    ApprovalRecordingOutput,
    DocumentRetrievalInput,
    DocumentRetrievalOutput,
    EvidenceRulesInput,
    EvidenceRulesOutput,
    GenerateSourcePreviewInput,
    GenerateSourcePreviewOutput,
    GetCurrentProcedureInput,
    GetCurrentProcedureOutput,
    GraphTraversalInput,
    GraphTraversalOutput,
    ReportGenerationInput,
    ReportGenerationOutput,
    ResolveAssetTagInput,
    ResolveAssetTagOutput,
    RevisionCheckInput,
    RevisionCheckOutput,
    SimilarFailuresInput,
    SimilarFailuresOutput,
    TimelineInput,
    TimelineOutput,
)
from mnemos.agentic.runtime.audit import AuditLogger
from mnemos.agentic.schemas.base import MCPToolName
from mnemos.agentic.utils.guardrails import MnemosGuardrails
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("mcp.server")


class MnemosMCPServer:
    """Exposes 10 typed MCP tools to the AI layer.

    Every tool call goes through guardrails + audit + dispatch.
    No agent may bypass this to access databases directly.
    """

    def __init__(
        self,
        audit_logger: AuditLogger | None = None,
        guardrails: MnemosGuardrails | None = None,
    ) -> None:
        self.audit_logger = audit_logger or AuditLogger()
        self.guardrails = guardrails or MnemosGuardrails()
        self.dispatch = MCPToolDispatch(
            audit_logger=self.audit_logger,
            guardrails=self.guardrails,
        )
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register all 12 tool handlers with the dispatch layer."""
        self.dispatch.register_handler(MCPToolName.RESOLVE_ASSET_TAG, self._resolve_asset_tag)
        self.dispatch.register_handler(MCPToolName.GRAPH_TRAVERSAL, self._graph_traversal)
        self.dispatch.register_handler(MCPToolName.DOCUMENT_RETRIEVAL, self._document_retrieval)
        self.dispatch.register_handler(MCPToolName.TIMELINE, self._timeline)
        self.dispatch.register_handler(MCPToolName.SIMILAR_FAILURES, self._similar_failures)
        self.dispatch.register_handler(MCPToolName.REVISION_CHECK, self._revision_check)
        self.dispatch.register_handler(MCPToolName.EVIDENCE_RULES, self._evidence_rules)
        self.dispatch.register_handler(MCPToolName.APPROVAL_RECORDING, self._approval_recording)
        self.dispatch.register_handler(MCPToolName.ACTION_CREATION, self._action_creation)
        self.dispatch.register_handler(MCPToolName.REPORT_GENERATION, self._report_generation)
        self.dispatch.register_handler(MCPToolName.GET_CURRENT_PROCEDURE, self._get_current_procedure)
        self.dispatch.register_handler(MCPToolName.GENERATE_SOURCE_PREVIEW, self._generate_source_preview)

    async def call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        agent_name: str = "unknown",
        investigation_id: str = "",
        trace_id: str | None = None,
        user_context: dict[str, Any] | None = None,
    ) -> Any:
        """Dispatch a tool call through guardrails + audit."""
        return await self.dispatch.dispatch(
            tool_name=tool_name,
            arguments=arguments,
            agent_name=agent_name,
            investigation_id=investigation_id,
            trace_id=trace_id,
            user_context=user_context,
        )

    # ==================================================================
    # Tool 1: resolve_asset_tag
    # ==================================================================

    async def _resolve_asset_tag(self, input: ResolveAssetTagInput) -> ResolveAssetTagOutput:
        """Resolve an asset tag or name to a canonical entity.

        Queries the identity resolver to map fuzzy mentions like
        'P-101' or 'Boiler A' to verified canonical asset IDs.
        """
        # In production: query identity resolver
        return ResolveAssetTagOutput(
            resolved=True,
            entities=[{
                "entity_id": f"asset_{input.mention.lower().replace(' ', '_')}",
                "canonical_name": input.mention,
                "entity_type": "asset",
                "site_id": input.site_id,
            }],
        )

    # ==================================================================
    # Tool 2: graph_traversal
    # ==================================================================

    async def _graph_traversal(self, input: GraphTraversalInput) -> GraphTraversalOutput:
        """Traverse the knowledge graph from a starting node.

        Supports 6 graph types: asset hierarchy, component graph,
        incident graph, procedure graph, failure graph, requirement graph.
        """
        # In production: query Neo4j graph client
        return GraphTraversalOutput(
            nodes=[{
                "id": input.start_node_id,
                "type": "asset",
                "graph_type": input.graph_type,
            }],
            edges=[],
            total_nodes=1,
            truncated=False,
        )

    # ==================================================================
    # Tool 3: document_retrieval
    # ==================================================================

    async def _document_retrieval(self, input: DocumentRetrievalInput) -> DocumentRetrievalOutput:
        """Retrieve a specific document version with full provenance.

        Returns document content, metadata, and provenance chain.
        Verifies document status (Approved vs Draft).
        """
        # In production: query document store
        return DocumentRetrievalOutput(
            document_id=input.document_id,
            version=input.version or 1,
            title=f"Document {input.document_id}",
            status="APPROVED",
            content="",
            is_latest=True,
        )

    # ==================================================================
    # Tool 4: timeline
    # ==================================================================

    async def _timeline(self, input: TimelineInput) -> TimelineOutput:
        """Retrieve chronological failure and maintenance events for an asset.

        Returns events in chronological order with type filtering.
        """
        # In production: query structured retriever
        return TimelineOutput(
            asset_id=input.asset_id,
            events=[],
            total_events=0,
            date_range={"from": input.date_from, "to": input.date_to},
        )

    # ==================================================================
    # Tool 5: similar_failures
    # ==================================================================

    async def _similar_failures(self, input: SimilarFailuresInput) -> SimilarFailuresOutput:
        """Find similar failure patterns using graph similarity.

        Identifies recurring failure patterns and related incidents.
        """
        # In production: query graph similarity
        return SimilarFailuresOutput(
            asset_id=input.asset_id,
            similar_failures=[],
            total_found=0,
        )

    # ==================================================================
    # Tool 6: revision_check
    # ==================================================================

    async def _revision_check(self, input: RevisionCheckInput) -> RevisionCheckOutput:
        """Check document revision currency.

        Verifies that referenced document versions are current.
        """
        # In production: query document version store
        return RevisionCheckOutput(
            document_id=input.document_id,
            current_version=1,
            is_current=True,
            status="current",
            details=f"Document {input.document_id} is at current version.",
        )

    # ==================================================================
    # Tool 7: evidence_rules
    # ==================================================================

    async def _evidence_rules(self, input: EvidenceRulesInput) -> EvidenceRulesOutput:
        """Look up compliance and requirement rules.

        Searches for ISO standards, regulations, SOPs, and other
        requirement documents.
        """
        # In production: query compliance database
        return EvidenceRulesOutput(
            rules=[],
            total_found=0,
            coverage_gaps=[],
        )

    # ==================================================================
    # Tool 8: approval_recording
    # ==================================================================

    async def _approval_recording(self, input: ApprovalRecordingInput) -> ApprovalRecordingOutput:
        """Record a human approval decision.

        Stores the decision, reviewer identity, and any conditions.
        """
        audit_entry = self.audit_logger.log_approval_decision(
            gate_type=input.gate_type,
            decision=input.decision,
            reviewer=input.reviewer,
            comments=input.comments,
            investigation_id=input.investigation_id,
        )
        return ApprovalRecordingOutput(
            recorded=True,
            gate_type=input.gate_type,
            decision=input.decision,
            reviewer=input.reviewer,
            audit_id=audit_entry.audit_id,
        )

    # ==================================================================
    # Tool 9: action_creation
    # ==================================================================

    async def _action_creation(self, input: ActionCreationInput) -> ActionCreationOutput:
        """Create a maintenance, inspection, or repair action.

        Automatically determines if approval is required based on
        action type and priority.
        """
        import uuid

        from mnemos.agentic.runtime.approval import HumanApprovalNode

        requires_approval, gate_type = HumanApprovalNode.requires_approval(
            action_type=input.action_type,
            priority=input.priority,
        )

        action_id = f"act_{uuid.uuid4().hex[:8]}"

        return ActionCreationOutput(
            created=True,
            action_id=action_id,
            action_type=input.action_type,
            priority=input.priority,
            requires_approval=requires_approval,
            approval_gate_type=gate_type.value if gate_type else None,
        )

    # ==================================================================
    # Tool 10: report_generation
    # ==================================================================

    async def _report_generation(self, input: ReportGenerationInput) -> ReportGenerationOutput:
        """Generate a structured report.

        Supports: rca_report, compliance_report, audit_export,
        maintenance_strategy, knowledge_card, investigation_summary.
        """
        gate_type = None
        requires_approval = False

        if input.report_type == "audit_export":
            gate_type = "audit_export"
            requires_approval = True
        elif input.report_type == "maintenance_strategy":
            gate_type = "maintenance_strategy"
            requires_approval = True
        elif input.report_type == "knowledge_card":
            gate_type = "knowledge_publication"
            requires_approval = True

        return ReportGenerationOutput(
            generated=True,
            report_type=input.report_type,
            report_data={
                "investigation_id": input.investigation_id,
                "sections": input.sections,
                "format": input.format,
            },
            section_count=len(input.sections) if input.sections else 6,
            requires_approval=requires_approval,
            approval_gate_type=gate_type,
        )

    # ==================================================================
    # Tool 11: get_current_procedure
    # ==================================================================

    async def _get_current_procedure(self, input: GetCurrentProcedureInput) -> GetCurrentProcedureOutput:
        """Retrieve the current approved procedure for an asset.

        Checks procedure status, version currency, and flags any
        outdated procedures that need updating.
        """
        # In production: query procedure store via structured retriever
        # Simulate: return empty (no procedures found)
        return GetCurrentProcedureOutput(
            asset_id=input.asset_id,
            procedures=[],
            total_found=0,
            all_approved=True,
            outdated_procedures=[],
        )

    # ==================================================================
    # Tool 12: generate_source_preview
    # ==================================================================

    async def _generate_source_preview(self, input: GenerateSourcePreviewInput) -> GenerateSourcePreviewOutput:
        """Generate a preview link for an evidence source.

        Creates a time-limited URL that allows reviewers to inspect
        the original source document, evidence region, or graph node.
        """
        import uuid
        from datetime import UTC, datetime, timedelta

        preview_id = uuid.uuid4().hex[:12]
        expires = datetime.now(UTC) + timedelta(hours=24)

        # Build preview URL based on source type
        base_path = f"/evidence/preview/{input.source_type}/{input.source_id}"
        params = []
        if input.document_id:
            params.append(f"doc={input.document_id}")
        if input.page_number:
            params.append(f"page={input.page_number}")
        if input.highlight_text:
            params.append(f"highlight={input.highlight_text}")
        query_string = "&".join(params)
        preview_url = f"{base_path}?{query_string}" if query_string else base_path

        return GenerateSourcePreviewOutput(
            preview_url=preview_url,
            source_type=input.source_type,
            source_id=input.source_id,
            expires_at=expires.isoformat(),
            metadata={
                "preview_id": preview_id,
                "document_id": input.document_id,
                "page_number": input.page_number,
            },
        )

    # ==================================================================
    # Tool listing
    # ==================================================================

    def list_tools(self) -> list[dict[str, Any]]:
        """List all available MCP tools with their schemas."""
        return [
            {
                "name": MCPToolName.RESOLVE_ASSET_TAG,
                "description": "Resolve asset tags/names to canonical IDs.",
                "input_schema": ResolveAssetTagInput.model_json_schema(),
                "output_schema": ResolveAssetTagOutput.model_json_schema(),
            },
            {
                "name": MCPToolName.GRAPH_TRAVERSAL,
                "description": "Traverse the industrial knowledge graph.",
                "input_schema": GraphTraversalInput.model_json_schema(),
                "output_schema": GraphTraversalOutput.model_json_schema(),
            },
            {
                "name": MCPToolName.DOCUMENT_RETRIEVAL,
                "description": "Retrieve documents with full provenance.",
                "input_schema": DocumentRetrievalInput.model_json_schema(),
                "output_schema": DocumentRetrievalOutput.model_json_schema(),
            },
            {
                "name": MCPToolName.TIMELINE,
                "description": "Get chronological event history for an asset.",
                "input_schema": TimelineInput.model_json_schema(),
                "output_schema": TimelineOutput.model_json_schema(),
            },
            {
                "name": MCPToolName.SIMILAR_FAILURES,
                "description": "Find similar failure patterns via graph similarity.",
                "input_schema": SimilarFailuresInput.model_json_schema(),
                "output_schema": SimilarFailuresOutput.model_json_schema(),
            },
            {
                "name": MCPToolName.REVISION_CHECK,
                "description": "Check document revision currency.",
                "input_schema": RevisionCheckInput.model_json_schema(),
                "output_schema": RevisionCheckOutput.model_json_schema(),
            },
            {
                "name": MCPToolName.EVIDENCE_RULES,
                "description": "Look up compliance and requirement rules.",
                "input_schema": EvidenceRulesInput.model_json_schema(),
                "output_schema": EvidenceRulesOutput.model_json_schema(),
            },
            {
                "name": MCPToolName.APPROVAL_RECORDING,
                "description": "Record human approval decisions.",
                "input_schema": ApprovalRecordingInput.model_json_schema(),
                "output_schema": ApprovalRecordingOutput.model_json_schema(),
            },
            {
                "name": MCPToolName.ACTION_CREATION,
                "description": "Create maintenance/inspection/repair actions.",
                "input_schema": ActionCreationInput.model_json_schema(),
                "output_schema": ActionCreationOutput.model_json_schema(),
            },
            {
                "name": MCPToolName.REPORT_GENERATION,
                "description": "Generate structured reports.",
                "input_schema": ReportGenerationInput.model_json_schema(),
                "output_schema": ReportGenerationOutput.model_json_schema(),
            },
            {
                "name": MCPToolName.GET_CURRENT_PROCEDURE,
                "description": "Retrieve the current approved procedure for an asset.",
                "input_schema": GetCurrentProcedureInput.model_json_schema(),
                "output_schema": GetCurrentProcedureOutput.model_json_schema(),
            },
            {
                "name": MCPToolName.GENERATE_SOURCE_PREVIEW,
                "description": "Generate a preview link for an evidence source.",
                "input_schema": GenerateSourcePreviewInput.model_json_schema(),
                "output_schema": GenerateSourcePreviewOutput.model_json_schema(),
            },
        ]
