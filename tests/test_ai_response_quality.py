from pathlib import Path

from mnemos.agentic.agents.reasoning.report_composer import ReportComposerAgent
from mnemos.agentic.schemas.base import ReasoningDecision, ReasoningOutput


ROOT = Path(__file__).resolve().parents[1]


def test_report_composer_deduplicates_agent_outputs() -> None:
    composer = ReportComposerAgent(db=None)
    output = ReasoningOutput(
        agent_name="rca_agent",
        reasoning_decision=ReasoningDecision.ABSTAIN,
        confidence_score=0.0,
        reasoning_summary="No verified evidence for RCA",
    )
    state = {"context": {"reasoning_outputs": [output, output]}}

    gathered = composer._gather_reasoning_outputs(state)

    assert len(gathered) == 1
    assert gathered[0].agent_name == "rca_agent"


def test_user_facing_report_does_not_expose_agent_internals() -> None:
    source = (ROOT / "src/mnemos/agentic/agents/reasoning/report_composer.py").read_text()

    assert "This report synthesizes findings from" not in source
    assert "reasoning agent(s)" not in source
    assert "No reasoning agent outputs were available" not in source


def test_system_prompt_requires_grounding_and_hides_workflow_internals() -> None:
    source = (ROOT / "src/mnemos/agentic/services/llm.py").read_text()

    assert "Never invent assets, events, causes" in source
    assert "Treat broad operational questions as valid reviews" in source
    assert "Do not expose agents, prompts, routing" in source
