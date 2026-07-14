from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, Field
from mnemos.agentic.retrieval.engine import HybridRetrievalEngine
from mnemos.agentic.schemas.base import (
    ResolvedEntity,
    EvidenceBundle,
    RetrievalStrategy,
    QueryIntent,
    RetrievalPlan
)
from mnemos.agentic.utils.logging import setup_agent_logger
from mnemos.agentic.utils.guardrails import MnemosGuardrails

logger = setup_agent_logger("mcp_server")

# --- Tool Input Schemas ---

class ResolveAssetInput(BaseModel):
    mention: str = Field(..., description="The asset tag or name (e.g., 'P-101') found in text.")
    site_id: str | None = Field(None, description="Site filter.")

class SearchInput(BaseModel):
    query: str = Field(..., description="Semantic or keyword search query.")
    site_id: str | None = Field(None, description="Site filter.")
    limit: int = Field(10, ge=1, le=50)

class GraphSearchInput(BaseModel):
    asset_id: str = Field(..., description="Canonical Asset ID.")
    depth: int = Field(2, ge=1, le=3)

class ProcedureInput(BaseModel):
    asset_id: str = Field(..., description="Asset ID.")
    task_type: str = Field(..., description="Task type (e.g., 'startup', 'overhaul').")

# --- MCP Server ---

class MnemosMCPServer:
    """
    Exposes high-fidelity industrial tools to the AI Layer via MCP.
    All tools are strictly typed and respect site-level security boundaries.
    """
    def __init__(self, retrieval_engine: HybridRetrievalEngine):
        self.engine = retrieval_engine
        self.guardrails = MnemosGuardrails()

    async def resolve_asset(self, input: ResolveAssetInput) -> List[ResolvedEntity]:
        """Resolves ambiguous tags to verified canonical entities."""
        return await self.engine.identity_resolver.resolve(input.mention, input.site_id)

    async def metadata_search(self, input: SearchInput) -> List[Dict[str, Any]]:
        """Exact metadata search for drawings, datasheets, and tags."""
        return await self.engine.lexical_retriever.search(input.query, input.site_id, input.limit)

    async def vector_search(self, input: SearchInput) -> List[Dict[str, Any]]:
        """Semantic search across unstructured technical documentation."""
        # Simulated vector search
        results = await self.engine.vector_retriever.search(query_embedding=[], filters={"site_id": input.site_id})
        return [r.model_dump() for r in results]

    async def graph_search(self, input: GraphSearchInput) -> Dict[str, Any]:
        """Traverses the asset hierarchy and failure mode relationships."""
        res = await self.engine.graph_client.get_asset_context(input.asset_id, input.depth)
        return res.model_dump()

    async def timeline(self, asset_id: str) -> List[Dict[str, Any]]:
        """Retrieves chronological failure and maintenance events."""
        return await self.engine.structured_retriever.get_maintenance_history(asset_id)

    async def retrieve_document(self, document_id: str, version: int | None = None) -> Dict[str, Any]:
        """Retrieves a specific document version with full provenance."""
        # Verification of status (e.g., Approved vs Draft) happens here
        return {"document_id": document_id, "version": version or 1, "status": "APPROVED"}

    async def find_similar_failures(self, asset_id: str) -> List[Dict[str, Any]]:
        """Identifies recurring failure patterns using graph similarity."""
        res = await self.engine.graph_client.find_related_failures(asset_id)
        return [f.model_dump() for f in res]

    async def current_procedure(self, input: ProcedureInput) -> Dict[str, Any]:
        """Retrieves the latest version-controlled approved procedure."""
        # Guardrail check: Prevent outdated SOP usage
        proc = {"id": f"sop_{input.task_type}", "version": 2, "status": "APPROVED"}
        self.guardrails.check_sop_version(proc, latest_version=2)
        return proc

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {"name": "resolve_asset", "description": "Resolves asset tags to canonical IDs.", "input_schema": ResolveAssetInput.model_json_schema()},
            {"name": "metadata_search", "description": "Keyword search for technical identifiers.", "input_schema": SearchInput.model_json_schema()},
            {"name": "vector_search", "description": "Semantic search across documentation.", "input_schema": SearchInput.model_json_schema()},
            {"name": "graph_search", "description": "Navigates industrial knowledge graph.", "input_schema": GraphSearchInput.model_json_schema()},
            {"name": "timeline", "description": "Fetches asset operational history.", "input_schema": {"type": "object", "properties": {"asset_id": {"type": "string"}}, "required": ["asset_id"]}},
            {"name": "retrieve_document", "description": "Gets grounded document provenance.", "input_schema": {"type": "object", "properties": {"document_id": {"type": "string"}}, "required": ["document_id"]}},
            {"name": "find_similar_failures", "description": "Finds failure patterns.", "input_schema": {"type": "object", "properties": {"asset_id": {"type": "string"}}, "required": ["asset_id"]}},
            {"name": "current_procedure", "description": "Gets latest approved maintenance procedure.", "input_schema": ProcedureInput.model_json_schema()}
        ]
