from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.langgraph.nodes import (
    AssetAgentNode,
    ComplianceAgentNode,
    EntityResolverNode,
    EvidenceRetrievalNode,
    EvidenceVerificationNode,
    ExpertKnowledgeAgentNode,
    GeneralAgentNode,
    LessonsLearnedAgentNode,
    QueryRouterNode,
    RCAAgentNode,
    ResponseComposerNode,
    RetrievalPlannerNode,
)
from mnemos.agentic.schemas.base import QueryIntent
from mnemos.agentic.schemas.state import AgentState


def route_to_specialized_agent(state: AgentState) -> str:
    """
    Directs the workflow to the correct specialized intelligence agent
    based on the classified intent of the query.
    """
    intent = state.get("intent")

    if intent == QueryIntent.ASSET_INFO:
        return "asset_agent"
    elif intent == QueryIntent.RCA:
        return "rca_agent"
    elif intent == QueryIntent.COMPLIANCE:
        return "compliance_agent"
    elif intent == QueryIntent.LESSONS_LEARNED:
        return "lessons_learned_agent"
    elif intent == QueryIntent.GENERAL:
        return "expert_knowledge_agent"
    else:
        return "general_agent"


def create_agent_workflow(db: AsyncSession):
    """
    Constructs the Mnemos Industrial Intelligence workflow.
    Nodes are instantiated with a database session for live grounding.
    """
    workflow = StateGraph(AgentState)

    # 1. Pipeline Nodes
    router = QueryRouterNode(db)
    resolver = EntityResolverNode(db)
    planner = RetrievalPlannerNode(db)
    retriever = EvidenceRetrievalNode(db)
    verifier = EvidenceVerificationNode(db)

    # 2. Specialized Reasoning Agents
    asset_agent = AssetAgentNode(db)
    rca_agent = RCAAgentNode(db)
    compliance_agent = ComplianceAgentNode(db)
    ll_agent = LessonsLearnedAgentNode(db)
    expert_agent = ExpertKnowledgeAgentNode(db)
    general_agent = GeneralAgentNode(db)

    # 3. Report Synthesis
    composer = ResponseComposerNode(db)

    # Add Nodes
    workflow.add_node("query_router", router)
    workflow.add_node("entity_resolver", resolver)
    workflow.add_node("retrieval_planner", planner)
    workflow.add_node("evidence_retrieval", retriever)
    workflow.add_node("evidence_verification", verifier)
    workflow.add_node("asset_agent", asset_agent)
    workflow.add_node("rca_agent", rca_agent)
    workflow.add_node("compliance_agent", compliance_agent)
    workflow.add_node("lessons_learned_agent", ll_agent)
    workflow.add_node("expert_knowledge_agent", expert_agent)
    workflow.add_node("general_agent", general_agent)
    workflow.add_node("response_composer", composer)

    # Define Linear Path
    workflow.set_entry_point("query_router")
    workflow.add_edge("query_router", "entity_resolver")
    workflow.add_edge("entity_resolver", "retrieval_planner")
    workflow.add_edge("retrieval_planner", "evidence_retrieval")
    workflow.add_edge("evidence_retrieval", "evidence_verification")

    # Conditional Branching
    workflow.add_conditional_edges(
        "evidence_verification",
        route_to_specialized_agent,
        {
            "asset_agent": "asset_agent",
            "rca_agent": "rca_agent",
            "compliance_agent": "compliance_agent",
            "lessons_learned_agent": "lessons_learned_agent",
            "expert_knowledge_agent": "expert_knowledge_agent",
            "general_agent": "general_agent"
        }
    )

    # Convergence
    workflow.add_edge("asset_agent", "response_composer")
    workflow.add_edge("rca_agent", "response_composer")
    workflow.add_edge("compliance_agent", "response_composer")
    workflow.add_edge("lessons_learned_agent", "response_composer")
    workflow.add_edge("expert_knowledge_agent", "response_composer")
    workflow.add_edge("general_agent", "response_composer")

    workflow.add_edge("response_composer", END)

    return workflow.compile()
