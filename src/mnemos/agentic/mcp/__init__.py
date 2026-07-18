"""Mnemos Internal Governed Tool Layer.

IMPORTANT — STATUS: INTERNAL TOOL LAYER (not protocol-compliant MCP)
======================================================================
The class ``MnemosMCPServer`` in this package is *not* a
protocol-compliant Model Context Protocol (MCP) server.  It is an
**internal, in-process governed tool dispatch layer** that:

- exposes 12 typed tools to reasoning agents
- enforces guardrails and audit logging on every call
- routes each tool to the real underlying service (PostgreSQL, Neo4j,
  pgvector, document store, asset identity resolver)
- prevents agents from accessing any datasource directly

The name "MCP" was chosen to reflect the tool-dispatch pattern, not
to imply compliance with the Anthropic Model Context Protocol
specification (streamable-HTTP transport, capability negotiation,
JSON-RPC sessions, etc.).

If a true protocol-compliant MCP server is required in future, the
following would be needed:
  A. An official MCP SDK (e.g. ``mcp`` Python package)
  B. Streamable HTTP or stdio transport
  C. MCP initialisation handshake + capability negotiation
  D. Protocol-based tool discovery (tools/list, tools/call)
  E. Structured JSON-RPC request/response messages
  F. Session management, cancellation, error responses
  G. Authentication and authorisation at the protocol level
  H. An MCP client used by each agent

Until that work is complete this package should be described as an
"internal governed tool layer", not as an MCP server.

Tools provided (all wired to real backend services):
1.  resolve_asset_tag       — fuzzy asset resolution via identity resolver
2.  graph_traversal         — Neo4j graph queries via GraphRAG
3.  document_retrieval      — document + version fetch from PostgreSQL
4.  timeline                — chronological failure/maintenance history
5.  similar_failures        — graph + SQL similar-failure search
6.  revision_check          — document currency check against latest version
7.  evidence_rules          — compliance requirement lookup
8.  approval_recording      — audit-log a human approval decision
9.  action_creation         — create a maintenance/inspection action
10. report_generation       — generate a structured investigation report
11. get_current_procedure   — retrieve current approved procedure
12. generate_source_preview — generate an evidence source preview link
"""

from mnemos.agentic.mcp.dispatch import MCPToolDispatch
from mnemos.agentic.mcp.interfaces import MCPResource, ToolDefinition
from mnemos.agentic.mcp.server import MnemosMCPServer
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

__all__ = [
    "MCPToolDispatch",
    "MnemosMCPServer",
    "MCPResource",
    "ToolDefinition",
    # Input schemas
    "ResolveAssetTagInput",
    "GraphTraversalInput",
    "DocumentRetrievalInput",
    "TimelineInput",
    "SimilarFailuresInput",
    "RevisionCheckInput",
    "EvidenceRulesInput",
    "ApprovalRecordingInput",
    "ActionCreationInput",
    "ReportGenerationInput",
    "GetCurrentProcedureInput",
    "GenerateSourcePreviewInput",
    # Output schemas
    "ResolveAssetTagOutput",
    "GraphTraversalOutput",
    "DocumentRetrievalOutput",
    "TimelineOutput",
    "SimilarFailuresOutput",
    "RevisionCheckOutput",
    "EvidenceRulesOutput",
    "ApprovalRecordingOutput",
    "ActionCreationOutput",
    "ReportGenerationOutput",
    "GetCurrentProcedureOutput",
    "GenerateSourcePreviewOutput",
]
