from typing import Any, Dict, List
from mnemos.agentic.agents.interfaces import BaseAgent
from mnemos.agentic.schemas.state import AgentState
from mnemos.agentic.schemas.base import EvidenceSource
from mnemos.agentic.schemas.specialized import AssetPassport, AssetTimelineEvent
from mnemos.agentic.utils.logging import setup_agent_logger
from mnemos.agentic.deps import get_prompt_manager

logger = setup_agent_logger("asset_agent")

class AssetIntelligenceAgent:
    """
    Agent responsible for synthesizing a comprehensive Asset Passport.
    Handles timeline construction, history aggregation, and health scoring.
    """
    def __init__(self):
        self.prompt_manager = get_prompt_manager()

    async def process(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Building Asset Passport from grounded evidence.")

        evidence: List[EvidenceSource] = state.get("evidence_bundle", {}).get("verified_evidence", [])
        entities = state.get("resolved_entities", [])

        if not entities:
            return {"error": "No entities resolved for asset intelligence."}

        # In production, this would be an LLM call using the 'asset_intelligence' template
        # for each resolved asset.

        passports = []
        for entity in entities:
            # Calculate Evidence Health Score: Average confidence of sources linked to this asset
            asset_evidence = [s for s in evidence if s.provenance.node_id == entity.entity_id or not s.provenance.node_id]
            health_score = sum(s.confidence_score for s in asset_evidence) / len(asset_evidence) if asset_evidence else 0.0

            passport = AssetPassport(
                asset_id=entity.entity_id,
                tag=entity.metadata.get("tag", "Unknown"),
                name=entity.canonical_name,
                type=entity.metadata.get("type", "Unknown"),
                status="Active", # To be derived from evidence
                site_context=state.get("context", {}).get("site_info", {}),
                specifications={}, # Extracted from evidence
                timeline=[], # Extracted from evidence
                maintenance_summary={}, # Extracted from evidence
                evidence_health_score=health_score
            )
            passports.append(passport.model_dump())

        return {"asset_passports": passports}
