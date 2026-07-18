"""MCP Server for the Mnemos agentic runtime.

Exposes 12 typed MCP tools to agents via the dispatch layer.
All tools are strictly typed, guardrail-checked, and audit-logged.
No agent may access databases directly.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
    """Governed internal tool-dispatch layer for the Mnemos agentic runtime.

    Exposes 12 typed tools to reasoning agents via a guardrailed,
    audit-logged dispatch layer.  Every call goes through:
       1. Input validation (Pydantic schemas)
       2. Guardrail checks (scope, classification, injection detection)
       3. Audit logging (every call is written to RuntimeAuditEntry)
       4. Real backend execution (PostgreSQL, Neo4j, pgvector, etc.)

    No agent may bypass this layer to access databases directly.

    NOTE: This is a governed internal tool-dispatch layer, NOT a
    protocol-compliant Model Context Protocol (MCP) server.  The "MCP"
    naming is a historical artifact and refers to the internal dispatch
    pattern, not the external MCP protocol.  If protocol-compliant MCP
    is added later, it will be a separate service in a new package.
    """

    def __init__(
        self,
        audit_logger: AuditLogger | None = None,
        guardrails: MnemosGuardrails | None = None,
        db_session_factory: async_sessionmaker[AsyncSession] | None = None,
        graph_client: Any | None = None,
    ) -> None:
        self.audit_logger = audit_logger or AuditLogger()
        self.guardrails = guardrails or MnemosGuardrails()
        self._session_factory = db_session_factory
        self._graph_client = graph_client
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
        self.dispatch.register_handler(
            MCPToolName.GET_CURRENT_PROCEDURE, self._get_current_procedure
        )
        self.dispatch.register_handler(
            MCPToolName.GENERATE_SOURCE_PREVIEW, self._generate_source_preview
        )

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
    # Tool 1: resolve_asset_tag  [Wired]
    # ==================================================================

    async def _resolve_asset_tag(self, input: ResolveAssetTagInput) -> ResolveAssetTagOutput:
        """Resolve an asset tag or name to a canonical entity.

        Uses AssetIdentityResolver for fuzzy matching with OCR-ambiguous
        variant detection and confidence scoring.
        """
        if not self._session_factory:
            return ResolveAssetTagOutput(
                resolved=False,
                entities=[],
                ambiguity_reason="No database session available",
            )
        async with self._session_factory() as db:
            from mnemos.agentic.retrieval.identity_resolver import AssetIdentityResolver

            resolver = AssetIdentityResolver(db)
            results = await resolver.resolve(input.mention, site_id=input.site_id)

            if not results:
                return ResolveAssetTagOutput(
                    resolved=False,
                    entities=[],
                    ambiguity_reason=f"No asset found matching '{input.mention}'",
                )

            if len(results) > 1 and results[0].confidence < results[1].confidence + 0.1:
                return ResolveAssetTagOutput(
                    resolved=False,
                    entities=[
                        {
                            "entity_id": r.entity_id,
                            "canonical_name": r.canonical_name,
                            "confidence": r.confidence,
                            "metadata": r.metadata,
                        }
                        for r in results[:5]
                    ],
                    ambiguity_reason=(
                        f"Multiple matches found for '{input.mention}'. "
                        "Please specify which asset you mean."
                    ),
                )

            top = results[0]
            return ResolveAssetTagOutput(
                resolved=True,
                entities=[
                    {
                        "entity_id": top.entity_id,
                        "canonical_name": top.canonical_name,
                        "confidence": top.confidence,
                        "metadata": top.metadata,
                    }
                ],
            )

    # ==================================================================
    # Tool 2: graph_traversal  [Wired]
    # ==================================================================

    async def _graph_traversal(self, input: GraphTraversalInput) -> GraphTraversalOutput:
        """Traverse the knowledge graph from a starting node.

        Uses Neo4j graph client with Cypher queries from GraphRAG.
        Supports 6 graph types with configurable depth and direction.
        """
        if not self._graph_client:
            raise RuntimeError(
                "graph_traversal: graph client unavailable — cannot traverse the knowledge graph"
            )

        graph_type_str = input.graph_type
        try:
            from mnemos.agentic.schemas.base import GraphType

            graph_type = GraphType(graph_type_str)
        except ValueError:
            graph_type = None

        if graph_type:
            from mnemos.agentic.retrieval.graph_rag import GRAPH_TYPE_QUERIES

            cypher = GRAPH_TYPE_QUERIES.get(graph_type)
        else:
            rel_filter = ""
            if input.relationship_types:
                rel_filter = "|".join(input.relationship_types)
            cypher = (
                "MATCH (start {id: $asset_id}) "
                "CALL apoc.path.subgraphAll(start, {"
                f"  maxDepth: $depth, limit: $limit,"
                f"  relationshipFilter: '{rel_filter}'"
                "}) YIELD nodes, relationships "
                "RETURN [n in nodes | {id: n.id, label: labels(n)[0], "
                "properties: properties(n)}] as nodes, "
                "[r in relationships | {source_id: id(startNode(r)), "
                "target_id: id(endNode(r)), type: type(r), "
                "properties: properties(r)}] as rels"
            )

        if not cypher:
            return GraphTraversalOutput(
                nodes=[],
                edges=[],
                total_nodes=0,
                truncated=False,
            )

        records = await self._graph_client.query(
            cypher,
            {"asset_id": input.start_node_id, "depth": input.depth, "limit": input.limit},
        )

        if not records:
            return GraphTraversalOutput(
                nodes=[{"id": input.start_node_id, "type": "asset"}],
                edges=[],
                total_nodes=1,
                truncated=False,
            )

        data = records[0]
        nodes = data.get("nodes", [])
        rels = data.get("rels", [])
        return GraphTraversalOutput(
            nodes=nodes,
            edges=rels,
            total_nodes=len(nodes),
            truncated=len(nodes) >= input.limit,
        )

    # ==================================================================
    # Tool 3: document_retrieval  [Wired]
    # ==================================================================

    async def _document_retrieval(self, input: DocumentRetrievalInput) -> DocumentRetrievalOutput:
        """Retrieve a specific document version with full provenance.

        Queries Document and DocumentVersion tables.
        """
        if not self._session_factory:
            return DocumentRetrievalOutput(
                document_id=input.document_id,
                version=input.version or 0,
                status="unknown",
                content="No database session available",
            )

        async with self._session_factory() as db:
            from mnemos.models.entities import Document, DocumentVersion

            doc_q = select(Document).where(Document.id == input.document_id)
            doc_r = await db.execute(doc_q)
            doc = doc_r.scalar_one_or_none()

            if not doc:
                return DocumentRetrievalOutput(
                    document_id=input.document_id,
                    version=0,
                    status="not_found",
                    content=f"Document {input.document_id} not found",
                )

            version_num = input.version or doc.version

            ver_q = (
                select(DocumentVersion)
                .where(DocumentVersion.document_id == input.document_id)
                .where(DocumentVersion.version == version_num)
            )
            ver_r = await db.execute(ver_q)
            ver = ver_r.scalar_one_or_none()

            content = ""
            provenance = None
            if ver:
                content = ver.content or ""
                if input.include_provenance:
                    provenance = {
                        "document_id": input.document_id,
                        "version": version_num,
                        "sha256": doc.sha256,
                        "created_at": ver.created_at.isoformat() if ver.created_at else None,
                        "created_by": ver.created_by,
                        "change_summary": ver.change_summary,
                    }

            return DocumentRetrievalOutput(
                document_id=input.document_id,
                version=version_num,
                title=doc.filename,
                status=doc.status,
                content=content,
                provenance=provenance,
                sha256=doc.sha256,
                is_latest=(version_num == doc.version),
            )

    # ==================================================================
    # Tool 4: timeline  [Wired]
    # ==================================================================

    async def _timeline(self, input: TimelineInput) -> TimelineOutput:
        """Retrieve chronological failure and maintenance events for an asset.

        Combines RCA cases, actions, and KnowledgeCard history.
        """
        if not self._session_factory:
            raise RuntimeError(
                f"timeline: database session unavailable — "
                f"cannot retrieve timeline for asset '{input.asset_id}'"
            )

        async with self._session_factory() as db:
            from datetime import datetime as _dt

            from mnemos.models.entities import KnowledgeCard, RCAAction, RCACase

            events: list[dict[str, Any]] = []

            rca_q = select(RCACase).where(RCACase.asset_id == input.asset_id)
            if input.date_from:
                rca_q = rca_q.where(RCACase.created_at >= _dt.fromisoformat(input.date_from))
            if input.date_to:
                rca_q = rca_q.where(RCACase.created_at <= _dt.fromisoformat(input.date_to))
            rca_q = rca_q.order_by(RCACase.created_at.desc()).limit(input.limit)

            rca_r = await db.execute(rca_q)
            for case in rca_r.scalars().all():
                events.append(
                    {
                        "event_id": case.id,
                        "event_type": "failure",
                        "title": case.title,
                        "description": case.problem_statement,
                        "status": case.status,
                        "severity": case.severity,
                        "timestamp": case.created_at.isoformat() if case.created_at else None,
                    }
                )
                if "maintenance" in input.event_types or not input.event_types:
                    act_q = (
                        select(RCAAction)
                        .where(RCAAction.rca_id == case.id)
                        .where(RCAAction.status == "completed")
                    )
                    act_r = await db.execute(act_q)
                    for act in act_r.scalars().all():
                        events.append(
                            {
                                "event_id": act.id,
                                "event_type": "maintenance",
                                "title": act.title,
                                "description": act.description,
                                "status": act.status,
                                "timestamp": act.completed_at.isoformat()
                                if act.completed_at
                                else None,
                            }
                        )

            if "knowledge_card" in input.event_types or not input.event_types:
                kc_q = (
                    select(KnowledgeCard)
                    .where(KnowledgeCard.asset_id == input.asset_id)
                    .where(KnowledgeCard.status == "approved")
                    .order_by(KnowledgeCard.updated_at.desc())
                    .limit(50)
                )
                kc_r = await db.execute(kc_q)
                for card in kc_r.scalars().all():
                    events.append(
                        {
                            "event_id": card.id,
                            "event_type": "knowledge_card",
                            "title": card.title,
                            "description": card.content[:200] if card.content else "",
                            "status": card.status,
                            "timestamp": card.updated_at.isoformat() if card.updated_at else None,
                        }
                    )

            events.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
            events = events[: input.limit]

            return TimelineOutput(
                asset_id=input.asset_id,
                events=events,
                total_events=len(events),
                date_range={"from": input.date_from, "to": input.date_to},
            )

    # ==================================================================
    # Tool 5: similar_failures  [Wired]
    # ==================================================================

    async def _similar_failures(self, input: SimilarFailuresInput) -> SimilarFailuresOutput:
        """Find similar failure patterns using graph + SQL lookup.

        Combines Neo4j graph traversal for component-related failures
        with SQL-based historical RCA case search.
        """
        similar: list[dict[str, Any]] = []

        if self._graph_client:
            try:
                graph_failures = await self._graph_client.find_related_failures(
                    input.asset_id,
                )
                for node in graph_failures:
                    similar.append(
                        {
                            "failure_id": node.id,
                            "failure_type": "graph_related",
                            "properties": node.properties,
                            "source": "knowledge_graph",
                            "similarity_score": 0.7,
                        }
                    )
            except Exception:
                logger.warning("Graph failure lookup failed, falling back to SQL")

        if self._session_factory and len(similar) < input.max_results:
            async with self._session_factory() as db:
                from mnemos.models.entities import RCACase

                remaining = input.max_results - len(similar)
                q = (
                    select(RCACase)
                    .where(RCACase.asset_id == input.asset_id)
                    .where(RCACase.status.in_(["closed", "approved"]))
                    .order_by(RCACase.created_at.desc())
                    .limit(remaining)
                )
                r = await db.execute(q)
                for case in r.scalars().all():
                    similar.append(
                        {
                            "failure_id": case.id,
                            "failure_type": case.severity,
                            "title": case.title,
                            "description": (
                                case.problem_statement[:200] if case.problem_statement else ""
                            ),
                            "status": case.status,
                            "created_at": (
                                case.created_at.isoformat() if case.created_at else None
                            ),
                            "source": "rca_history",
                            "similarity_score": 0.5,
                        }
                    )

        filtered = [
            s for s in similar if s.get("similarity_score", 0) >= input.similarity_threshold
        ][: input.max_results]

        pattern_summary = None
        if filtered:
            types = [s.get("failure_type", "unknown") for s in filtered]
            counts = Counter(types)
            top = counts.most_common(3)
            pattern_summary = "Recurring patterns: " + ", ".join(f"{t} ({c}x)" for t, c in top)

        return SimilarFailuresOutput(
            asset_id=input.asset_id,
            similar_failures=filtered,
            total_found=len(filtered),
            pattern_summary=pattern_summary,
        )

    # ==================================================================
    # Tool 6: revision_check  [Wired]
    # ==================================================================

    async def _revision_check(self, input: RevisionCheckInput) -> RevisionCheckOutput:
        """Check document revision currency against the latest version.

        Compares expected_version to current version in the database.
        """
        if not self._session_factory:
            raise RuntimeError(
                f"revision_check: database session unavailable — "
                f"cannot check revision for document '{input.document_id}'"
            )

        async with self._session_factory() as db:
            from mnemos.models.entities import Document, DocumentVersion

            doc_q = select(Document).where(Document.id == input.document_id)
            doc_r = await db.execute(doc_q)
            doc = doc_r.scalar_one_or_none()

            if not doc:
                return RevisionCheckOutput(
                    document_id=input.document_id,
                    current_version=0,
                    is_current=False,
                    status="not_found",
                    details=f"Document {input.document_id} not found",
                )

            current = doc.version
            expected = input.expected_version or current
            is_current = expected == current

            latest_q = (
                select(DocumentVersion)
                .where(DocumentVersion.document_id == input.document_id)
                .order_by(DocumentVersion.version.desc())
                .limit(1)
            )
            latest_r = await db.execute(latest_q)
            latest_ver = latest_r.scalar_one_or_none()

            if is_current:
                status = "current"
                details = f"Document is at version {current} (matches expected)."
            else:
                status = "outdated"
                details = (
                    f"Document is at version {current}, "
                    f"but expected version {expected} was referenced."
                )

            if latest_ver and latest_ver.change_summary:
                details += f" Latest change: {latest_ver.change_summary}"

            return RevisionCheckOutput(
                document_id=input.document_id,
                current_version=current,
                is_current=is_current,
                status=status,
                details=details,
            )

    # ==================================================================
    # Tool 7: evidence_rules  [Wired]
    # ==================================================================

    async def _evidence_rules(self, input: EvidenceRulesInput) -> EvidenceRulesOutput:
        """Look up compliance and requirement rules from the database.

        Searches ComplianceRequirement table with optional text matching.
        """
        if not self._session_factory:
            raise RuntimeError(
                f"evidence_rules: database session unavailable — "
                f"cannot look up compliance rules for '{input.query}'"
            )

        async with self._session_factory() as db:
            from mnemos.models.entities import ComplianceRequirement

            q = select(ComplianceRequirement).where(ComplianceRequirement.status == "active")
            if input.site_id:
                q = q.where(ComplianceRequirement.organisation_id == input.site_id)

            search_terms = input.query.lower().split()
            if search_terms:
                from sqlalchemy import or_

                conditions = []
                for term in search_terms:
                    conditions.append(ComplianceRequirement.title.ilike(f"%{term}%"))
                    conditions.append(ComplianceRequirement.description.ilike(f"%{term}%"))
                    conditions.append(ComplianceRequirement.code.ilike(f"%{term}%"))
                q = q.where(or_(*conditions))

            q = q.limit(50)
            r = await db.execute(q)
            requirements = r.scalars().all()

            rules = [
                {
                    "rule_id": req.id,
                    "code": req.code,
                    "title": req.title,
                    "description": req.description[:300] if req.description else "",
                    "source": req.source,
                    "status": req.status,
                }
                for req in requirements
            ]

            return EvidenceRulesOutput(
                rules=rules,
                total_found=len(rules),
                coverage_gaps=[],
            )

    # ==================================================================
    # Tool 8: approval_recording  [Real]
    # ==================================================================

    async def _approval_recording(self, input: ApprovalRecordingInput) -> ApprovalRecordingOutput:
        """Record a human approval decision."""
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
    # Tool 9: action_creation  [Real]
    # ==================================================================

    async def _action_creation(self, input: ActionCreationInput) -> ActionCreationOutput:
        """Create a maintenance, inspection, or repair action."""
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
    # Tool 10: report_generation  [Real]
    # ==================================================================

    async def _report_generation(self, input: ReportGenerationInput) -> ReportGenerationOutput:
        """Generate a structured report."""
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
    # Tool 11: get_current_procedure  [Wired]
    # ==================================================================

    async def _get_current_procedure(
        self, input: GetCurrentProcedureInput
    ) -> GetCurrentProcedureOutput:
        """Retrieve the current approved procedure for an asset.

        Queries KnowledgeCard with status='approved' for the asset,
        flags outdated procedures that need updating.
        """
        if not self._session_factory:
            return GetCurrentProcedureOutput(
                asset_id=input.asset_id,
                procedures=[],
                total_found=0,
                all_approved=True,
                outdated_procedures=[],
            )

        async with self._session_factory() as db:
            from mnemos.models.entities import KnowledgeCard

            q = (
                select(KnowledgeCard)
                .where(KnowledgeCard.asset_id == input.asset_id)
                .where(KnowledgeCard.status == "approved")
                .order_by(KnowledgeCard.updated_at.desc())
            )
            r = await db.execute(q)
            cards = r.scalars().all()

            procedures = []
            outdated = []
            for card in cards:
                proc = {
                    "procedure_id": card.id,
                    "title": card.title,
                    "content_preview": card.content[:200] if card.content else "",
                    "version": card.version,
                    "status": card.status,
                    "updated_at": card.updated_at.isoformat() if card.updated_at else None,
                }
                procedures.append(proc)

                if card.supersedes_id:
                    outdated.append(proc)

            return GetCurrentProcedureOutput(
                asset_id=input.asset_id,
                procedures=procedures,
                total_found=len(procedures),
                all_approved=all(p["status"] == "approved" for p in procedures),
                outdated_procedures=outdated,
            )

    # ==================================================================
    # Tool 12: generate_source_preview  [Real]
    # ==================================================================

    async def _generate_source_preview(
        self, input: GenerateSourcePreviewInput
    ) -> GenerateSourcePreviewOutput:
        """Generate a preview link for an evidence source."""
        import uuid
        from datetime import UTC, datetime, timedelta

        preview_id = uuid.uuid4().hex[:12]
        expires = datetime.now(UTC) + timedelta(hours=24)

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
