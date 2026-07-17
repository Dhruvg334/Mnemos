"""Model Context Protocol (MCP) server for the Mnemos AI layer.

Provides typed MCP tools that agents use to interact with external systems.
All external actions go through MCP -- no agent may access databases directly.

Tools:
1. resolve_asset_tag - Resolve asset tags to canonical IDs
2. graph_traversal - Traverse the knowledge graph
3. document_retrieval - Retrieve documents with provenance
4. timeline - Chronological event history
5. similar_failures - Find similar failure patterns
6. revision_check - Check document revision currency
7. evidence_rules - Look up compliance rules
8. approval_recording - Record human approvals
9. action_creation - Create maintenance actions
10. report_generation - Generate structured reports
"""

from mnemos.agentic.mcp.dispatch import MCPToolDispatch
from mnemos.agentic.mcp.interfaces import BaseMCPClient, MCPResource, ToolDefinition
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
    "BaseMCPClient",
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
]
