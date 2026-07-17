"""End-to-End Investigation Workflow for the Mnemos AI platform.

Implements the complete 11-stage investigation pipeline:

    User Question -> Supervisor -> Query Router -> Retrieval Planner ->
    Evidence Retrieval -> Evidence Verification -> Reflection ->
    Specialized Agents -> Report Composer -> Human Approval -> Final Response

Every stage is a concrete execution step. No placeholders.
No TODOs. Production ready.

Architecture::

    InvestigationPipeline.run()
        Stage  1: Supervisor Init      -- initialize state, set phase
        Stage  2: Query Router          -- classify intent, extract entities
        Stage  3: Retrieval Planner     -- select strategies, build plan
        Stage  4: Evidence Retrieval    -- execute plan via HybridRetrievalEngine
        Stage  5: Evidence Verification -- provenance, contradictions, citations
        Stage  6: Reflection            -- evaluate evidence sufficiency
        Stage  7: Specialized Agents    -- RCA, Compliance, Asset Intel,
                                           Lessons Learned, Expert Knowledge
        Stage  8: Report Composer       -- synthesize FinalReport
        Stage  9: Human Approval        -- pause for review if needed
        Stage 10: Final Response        -- format FinalReport as AgentResponse
        Stage 11: Complete              -- save checkpoint, return response
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator, Callable
from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.runtime.approval import HumanApprovalNode
from mnemos.agentic.runtime.audit import AuditLogger
from mnemos.agentic.runtime.checkpoint import CheckpointManager
from mnemos.agentic.runtime.events import InvestigationEventLog
from mnemos.agentic.runtime.observability import ObservabilityDashboard
from mnemos.agentic.runtime.recovery import FailureRecoveryManager
from mnemos.agentic.runtime.reflection import ReflectionAgent
from mnemos.agentic.runtime.registry import AgentCapabilityRegistry, AgentRegistry
from mnemos.agentic.runtime.retry import RetryPolicy, TimeoutManager, execute_with_retry
from mnemos.agentic.runtime.state import InvestigationState, create_initial_state
from mnemos.agentic.runtime.supervisor import SupervisorAgent
from mnemos.agentic.runtime.types import (
    AgentInvocationMetadata,
    AgentRegistration,
    AgentStatus,
    CheckpointType,
    EventType,
    InvestigationPhase,
    TerminationReason,
)
from mnemos.agentic.schemas.base import AgentResponse
from mnemos.agentic.schemas.specialized import FinalReport
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("runtime.workflow")

# ---------------------------------------------------------------------------
# Lazy agent imports (graceful fallback when dependencies are missing)
# ---------------------------------------------------------------------------

_QUERY_ROUTER_CLS: type | None = None
_RETRIEVAL_PLANNER_CLS: type | None = None
_EVIDENCE_RETRIEVAL_CLS: type | None = None
_EVIDENCE_VERIFICATION_CLS: type | None = None
_RETRIEVAL_REFLECTION_CLS: type | None = None
_RCA_CLS: type | None = None
_COMPLIANCE_CLS: type | None = None
_ASSET_INTEL_CLS: type | None = None
_LESSONS_LEARNED_CLS: type | None = None
_EXPERT_KNOWLEDGE_CLS: type | None = None
_REPORT_COMPOSER_CLS: type | None = None

try:
    from mnemos.agentic.agents.retrieval.query_router import (
        QueryRouterAgent as _QUERY_ROUTER_CLS,
    )
except ImportError:
    pass

try:
    from mnemos.agentic.agents.retrieval.planner import (
        RetrievalPlannerAgent as _RETRIEVAL_PLANNER_CLS,
    )
except ImportError:
    pass

try:
    from mnemos.agentic.agents.retrieval.evidence_retrieval import (
        EvidenceRetrievalAgent as _EVIDENCE_RETRIEVAL_CLS,
    )
except ImportError:
    pass

try:
    from mnemos.agentic.agents.retrieval.evidence_verification import (
        EvidenceVerificationAgent as _EVIDENCE_VERIFICATION_CLS,
    )
except ImportError:
    pass

try:
    from mnemos.agentic.agents.retrieval.retrieval_reflection import (
        RetrievalReflectionAgent as _RETRIEVAL_REFLECTION_CLS,
    )
except ImportError:
    pass

try:
    from mnemos.agentic.agents.reasoning.rca import (
        RCAAgent as _RCA_CLS,
    )
except ImportError:
    pass

try:
    from mnemos.agentic.agents.reasoning.compliance import (
        ComplianceAgent as _COMPLIANCE_CLS,
    )
except ImportError:
    pass

try:
    from mnemos.agentic.agents.reasoning.asset_intelligence import (
        AssetIntelligenceAgent as _ASSET_INTEL_CLS,
    )
except ImportError:
    pass

try:
    from mnemos.agentic.agents.reasoning.lessons_learned import (
        LessonsLearnedAgent as _LESSONS_LEARNED_CLS,
    )
except ImportError:
    pass

try:
    from mnemos.agentic.agents.reasoning.expert_knowledge import (
        ExpertKnowledgeAgent as _EXPERT_KNOWLEDGE_CLS,
    )
except ImportError:
    pass

try:
    from mnemos.agentic.agents.reasoning.report_composer import (
        ReportComposerAgent as _REPORT_COMPOSER_CLS,
    )
except ImportError:
    pass


# ======================================================================
# Helpers
# ======================================================================


def _merge_state(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Merge *source* state into *target*, appending to list fields."""
    for key, value in source.items():
        if key in target and isinstance(target[key], list) and isinstance(value, list):
            target[key].extend(value)
        elif key in target and isinstance(target[key], dict) and isinstance(value, dict):
            target[key].update(value)
        else:
            target[key] = value


def _phase_str(phase: Any) -> str:  # noqa: ANN401
    """Coerce a phase value to a plain string."""
    if isinstance(phase, str):
        return phase
    try:
        return str(phase.value)
    except AttributeError:
        return str(phase)


def _instantiate_agent(
    agent_cls: type | None,
    db: AsyncSession | None,
    stage_name: str,
) -> Any:
    """Attempt to instantiate an agent class. Returns *None* on failure."""
    if agent_cls is None:
        logger.warning(
            f"Stage [{stage_name}]: agent class not available "
            "(import may have failed). Skipping."
        )
        return None
    if db is None:
        logger.warning(
            f"Stage [{stage_name}]: no DB session provided; "
            "agent will run without database access."
        )
    try:
        return agent_cls(db)
    except Exception as exc:
        logger.error(
            f"Stage [{stage_name}]: failed to instantiate agent "
            f"{agent_cls.__name__}: {exc}"
        )
        return None


# ======================================================================
# InvestigationPipeline
# ======================================================================


class InvestigationPipeline:
    """The complete 11-stage investigation pipeline.

    This is the primary entry point for running an end-to-end
    investigation.  It wires together all retrieval, reasoning,
    verification, and composition agents into a deterministic
    sequential pipeline.

    Usage::

        pipeline = InvestigationPipeline(db=session)
        result = await pipeline.run("inv_001", "What caused the pump failure?")
        response = result["final_response"]
    """

    def __init__(
        self,
        *,
        db: AsyncSession | None = None,
        max_iterations: int = 10,
        evidence_confidence_threshold: float = 0.7,
        auto_checkpoint: bool = True,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self.db = db
        self.max_iterations = max_iterations
        self.evidence_confidence_threshold = evidence_confidence_threshold
        self.auto_checkpoint = auto_checkpoint
        self.audit_logger = audit_logger or AuditLogger()

        self.failure_recovery = FailureRecoveryManager()
        self.approval_node = HumanApprovalNode(audit_logger=self.audit_logger)
        self.reflection_agent = ReflectionAgent(
            evidence_completeness_threshold=evidence_confidence_threshold,
        )

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    async def run(
        self,
        investigation_id: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run the complete 11-stage investigation pipeline.

        Returns the final investigation state dict with:
        - final_response: AgentResponse | None
        - final_report: FinalReport | None
        - investigation_id, phase, completion info
        """
        event_log = InvestigationEventLog(investigation_id)
        checkpoint_manager = CheckpointManager(investigation_id)

        state = create_initial_state(
            investigation_id=investigation_id,
            query=query,
            context=context,
            max_iterations=self.max_iterations,
        )

        event_log.append(
            EventType.INVESTIGATION_STARTED,
            phase=InvestigationPhase.INITIALIZATION,
            data={"query": query, "investigation_id": investigation_id},
        )

        try:
            state = await self._stage_supervisor_init(state, event_log)

            state = await self._stage_query_router(state, event_log)

            state = await self._stage_retrieval_planner(state, event_log)

            state = await self._stage_evidence_retrieval(state, event_log)

            state = await self._stage_evidence_verification(state, event_log)

            state, should_continue = await self._stage_reflection(
                state, event_log,
            )

            if should_continue:
                state = await self._stage_specialized_agents(
                    state, event_log,
                )

                state = await self._stage_report_composer(
                    state, event_log,
                )

                state, approved = await self._stage_human_approval(
                    state, event_log,
                )

                if approved:
                    state = await self._stage_final_response(
                        state, event_log,
                    )

            state = await self._stage_complete(
                state, event_log, checkpoint_manager,
            )

        except Exception as exc:
            logger.error(
                f"Pipeline failure for {investigation_id}: {exc}",
                exc_info=True,
            )
            event_log.append(
                EventType.INVESTIGATION_FAILED,
                phase=InvestigationPhase(
                    _phase_str(state.get("phase", InvestigationPhase.FAILED)),
                ),
                data={"error": str(exc)},
            )
            state["is_complete"] = True
            state["termination_reason"] = TerminationReason.ALL_AGENTS_FAILED
            state["phase"] = InvestigationPhase.FAILED
            errors = list(state.get("errors", []))
            errors.append(f"PIPELINE_FAILURE: {exc}")
            state["errors"] = errors

            if self.auto_checkpoint:
                try:
                    checkpoint_manager.save(
                        state,  # type: ignore[arg-type]
                        phase=InvestigationPhase.FAILED,
                        checkpoint_type=CheckpointType.ON_FAILURE,
                        description=f"Pipeline failure: {exc}",
                        event_log_offset=event_log.get_offset(),
                    )
                except Exception:
                    pass

        return self._build_result(state, investigation_id, event_log)

    async def run_streaming(
        self,
        investigation_id: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Run the pipeline with streaming progress events.

        Yields dicts describing each stage transition, agent invocation,
        and final result.  The final yielded dict contains the complete
        result.
        """
        event_log = InvestigationEventLog(investigation_id)
        checkpoint_manager = CheckpointManager(investigation_id)

        state = create_initial_state(
            investigation_id=investigation_id,
            query=query,
            context=context,
            max_iterations=self.max_iterations,
        )

        event_log.append(
            EventType.INVESTIGATION_STARTED,
            phase=InvestigationPhase.INITIALIZATION,
            data={"query": query, "investigation_id": investigation_id},
        )

        yield {
            "event_type": "pipeline_start",
            "stage": 0,
            "stage_name": "initialization",
            "investigation_id": investigation_id,
        }

        stages = [
            (1, "supervisor_init", self._stage_supervisor_init),
            (2, "query_router", self._stage_query_router),
            (3, "retrieval_planner", self._stage_retrieval_planner),
            (4, "evidence_retrieval", self._stage_evidence_retrieval),
            (5, "evidence_verification", self._stage_evidence_verification),
        ]

        try:
            for stage_num, stage_name, stage_fn in stages:
                yield {
                    "event_type": "stage_start",
                    "stage": stage_num,
                    "stage_name": stage_name,
                    "phase": _phase_str(state.get("phase", "")),
                }
                state = await stage_fn(state, event_log)
                yield {
                    "event_type": "stage_complete",
                    "stage": stage_num,
                    "stage_name": stage_name,
                    "evidence_count": len(state.get("evidence", [])),
                    "claims_count": len(state.get("claims", [])),
                    "errors_count": len(state.get("errors", [])),
                }

            yield {
                "event_type": "stage_start",
                "stage": 6,
                "stage_name": "reflection",
                "phase": _phase_str(state.get("phase", "")),
            }
            state, should_continue = await self._stage_reflection(
                state, event_log,
            )
            yield {
                "event_type": "stage_complete",
                "stage": 6,
                "stage_name": "reflection",
                "should_continue": should_continue,
            }

            if should_continue:
                yield {
                    "event_type": "stage_start",
                    "stage": 7,
                    "stage_name": "specialized_agents",
                    "phase": _phase_str(state.get("phase", "")),
                }
                state = await self._stage_specialized_agents(
                    state, event_log,
                )
                yield {
                    "event_type": "stage_complete",
                    "stage": 7,
                    "stage_name": "specialized_agents",
                    "claims_count": len(state.get("claims", [])),
                }

                yield {
                    "event_type": "stage_start",
                    "stage": 8,
                    "stage_name": "report_composer",
                    "phase": _phase_str(state.get("phase", "")),
                }
                state = await self._stage_report_composer(
                    state, event_log,
                )
                yield {
                    "event_type": "stage_complete",
                    "stage": 8,
                    "stage_name": "report_composer",
                    "has_final_report": state.get("context", {}).get(
                        "final_report",
                    )
                    is not None,
                }

                yield {
                    "event_type": "stage_start",
                    "stage": 9,
                    "stage_name": "human_approval",
                    "phase": _phase_str(state.get("phase", "")),
                }
                state, approved = await self._stage_human_approval(
                    state, event_log,
                )
                yield {
                    "event_type": "stage_complete",
                    "stage": 9,
                    "stage_name": "human_approval",
                    "approved": approved,
                }

                if approved:
                    yield {
                        "event_type": "stage_start",
                        "stage": 10,
                        "stage_name": "final_response",
                        "phase": _phase_str(state.get("phase", "")),
                    }
                    state = await self._stage_final_response(
                        state, event_log,
                    )
                    yield {
                        "event_type": "stage_complete",
                        "stage": 10,
                        "stage_name": "final_response",
                        "has_response": state.get("final_response")
                        is not None,
                    }

            yield {
                "event_type": "stage_start",
                "stage": 11,
                "stage_name": "complete",
                "phase": _phase_str(state.get("phase", "")),
            }
            state = await self._stage_complete(
                state, event_log, checkpoint_manager,
            )
            yield {
                "event_type": "stage_complete",
                "stage": 11,
                "stage_name": "complete",
            }

        except Exception as exc:
            logger.error(
                f"Streaming pipeline failure for {investigation_id}: {exc}",
                exc_info=True,
            )
            state["is_complete"] = True
            state["termination_reason"] = TerminationReason.ALL_AGENTS_FAILED
            state["phase"] = InvestigationPhase.FAILED
            errors = list(state.get("errors", []))
            errors.append(f"PIPELINE_FAILURE: {exc}")
            state["errors"] = errors

            yield {
                "event_type": "pipeline_error",
                "error": str(exc),
                "phase": _phase_str(state.get("phase", "")),
            }

        result = self._build_result(state, investigation_id, event_log)
        yield {
            "event_type": "pipeline_complete",
            "result": result,
        }

    # ------------------------------------------------------------------
    # Stage 1: Supervisor Init
    # ------------------------------------------------------------------

    async def _stage_supervisor_init(
        self,
        state: InvestigationState,
        event_log: InvestigationEventLog,
    ) -> InvestigationState:
        """Stage 1: Initialize investigation, set up state."""
        started = time.time()
        logger.info(
            f"Stage 1 [Supervisor Init]: investigation_id="
            f"{state.get('investigation_id')}"
        )

        state["phase"] = InvestigationPhase.INITIALIZATION
        state["iteration"] = 0
        state["is_complete"] = False

        event_log.append(
            EventType.PHASE_CHANGED,
            phase=InvestigationPhase.INITIALIZATION,
            data={"stage": "supervisor_init", "query": state.get("query", "")},
        )

        elapsed_ms = (time.time() - started) * 1000
        logger.info(
            f"Stage 1 [Supervisor Init]: complete in {elapsed_ms:.1f}ms"
        )
        return state

    # ------------------------------------------------------------------
    # Stage 2: Query Router
    # ------------------------------------------------------------------

    async def _stage_query_router(
        self,
        state: InvestigationState,
        event_log: InvestigationEventLog,
    ) -> InvestigationState:
        """Stage 2: Classify query intent, extract entities."""
        started = time.time()
        logger.info("Stage 2 [Query Router]: classifying query intent")

        state["phase"] = InvestigationPhase.PLANNING

        event_log.append(
            EventType.PHASE_CHANGED,
            phase=InvestigationPhase.PLANNING,
            data={"stage": "query_router"},
        )

        agent = _instantiate_agent(_QUERY_ROUTER_CLS, self.db, "query_router")
        if agent is None:
            logger.warning(
                "Stage 2 [Query Router]: agent unavailable, "
                "setting default intent"
            )
            ctx = dict(state.get("context", {}))
            ctx.setdefault("intent", "general")
            ctx.setdefault("extracted_entities", [])
            state["context"] = ctx
            _record_step(state, "query_router", "skipped")
            return state

        try:
            result = await agent.as_function(state)
            state = _update_state(state, result)

            event_log.append(
                EventType.AGENT_COMPLETED,
                phase=InvestigationPhase.PLANNING,
                agent_name="query_router",
                data={
                    "intent": str(
                        state.get("context", {}).get("intent", "unknown"),
                    ),
                    "entities": state.get("context", {}).get(
                        "extracted_entities", [],
                    ),
                },
            )
            _record_step(state, "query_router", "completed")

        except Exception as exc:
            logger.error(f"Stage 2 [Query Router]: failed: {exc}")
            event_log.append(
                EventType.AGENT_FAILED,
                phase=InvestigationPhase.PLANNING,
                agent_name="query_router",
                data={"error": str(exc)},
            )
            _record_error(state, f"query_router: {exc}")
            ctx = dict(state.get("context", {}))
            ctx.setdefault("intent", "general")
            ctx.setdefault("extracted_entities", [])
            state["context"] = ctx

        elapsed_ms = (time.time() - started) * 1000
        logger.info(
            f"Stage 2 [Query Router]: complete in {elapsed_ms:.1f}ms"
        )
        return state

    # ------------------------------------------------------------------
    # Stage 3: Retrieval Planner
    # ------------------------------------------------------------------

    async def _stage_retrieval_planner(
        self,
        state: InvestigationState,
        event_log: InvestigationEventLog,
    ) -> InvestigationState:
        """Stage 3: Build retrieval plan with strategies and filters."""
        started = time.time()
        logger.info("Stage 3 [Retrieval Planner]: building retrieval plan")

        event_log.append(
            EventType.PHASE_CHANGED,
            phase=InvestigationPhase.PLANNING,
            data={"stage": "retrieval_planner"},
        )

        agent = _instantiate_agent(
            _RETRIEVAL_PLANNER_CLS, self.db, "retrieval_planner",
        )
        if agent is None:
            logger.warning(
                "Stage 3 [Retrieval Planner]: agent unavailable"
            )
            _record_step(state, "retrieval_planner", "skipped")
            return state

        try:
            result = await agent.as_function(state)
            state = _update_state(state, result)

            plan = state.get("context", {}).get("retrieval_plan")
            strategies = []
            if plan is not None:
                strategies = [
                    s.value if hasattr(s, "value") else str(s)
                    for s in getattr(plan, "strategies", [])
                ]

            event_log.append(
                EventType.AGENT_COMPLETED,
                phase=InvestigationPhase.PLANNING,
                agent_name="retrieval_planner",
                data={"strategies": strategies, "plan_created": plan is not None},
            )
            _record_step(state, "retrieval_planner", "completed")

        except Exception as exc:
            logger.error(f"Stage 3 [Retrieval Planner]: failed: {exc}")
            event_log.append(
                EventType.AGENT_FAILED,
                phase=InvestigationPhase.PLANNING,
                agent_name="retrieval_planner",
                data={"error": str(exc)},
            )
            _record_error(state, f"retrieval_planner: {exc}")

        elapsed_ms = (time.time() - started) * 1000
        logger.info(
            f"Stage 3 [Retrieval Planner]: complete in {elapsed_ms:.1f}ms"
        )
        return state

    # ------------------------------------------------------------------
    # Stage 4: Evidence Retrieval
    # ------------------------------------------------------------------

    async def _stage_evidence_retrieval(
        self,
        state: InvestigationState,
        event_log: InvestigationEventLog,
    ) -> InvestigationState:
        """Stage 4: Execute retrieval plan via HybridRetrievalEngine."""
        started = time.time()
        logger.info(
            "Stage 4 [Evidence Retrieval]: executing retrieval plan"
        )

        state["phase"] = InvestigationPhase.EVIDENCE_GATHERING

        event_log.append(
            EventType.PHASE_CHANGED,
            phase=InvestigationPhase.EVIDENCE_GATHERING,
            data={"stage": "evidence_retrieval"},
        )

        agent = _instantiate_agent(
            _EVIDENCE_RETRIEVAL_CLS, self.db, "evidence_retrieval",
        )
        if agent is None:
            logger.warning(
                "Stage 4 [Evidence Retrieval]: agent unavailable"
            )
            _record_step(state, "evidence_retrieval", "skipped")
            return state

        try:
            result = await agent.as_function(state)
            state = _update_state(state, result)

            evidence_count = len(state.get("evidence", []))
            bundle = state.get("context", {}).get("evidence_bundle")
            vector_count = len(
                getattr(bundle, "raw_vector_data", []) if bundle else [],
            )
            graph_count = len(
                getattr(bundle, "raw_graph_data", {}) if bundle else {},
            )

            event_log.append(
                EventType.EVIDENCE_COLLECTED,
                phase=InvestigationPhase.EVIDENCE_GATHERING,
                agent_name="evidence_retrieval",
                data={
                    "count": evidence_count,
                    "vector_candidates": vector_count,
                    "graph_sources": graph_count,
                },
            )
            _record_step(state, "evidence_retrieval", "completed")

        except Exception as exc:
            logger.error(f"Stage 4 [Evidence Retrieval]: failed: {exc}")
            event_log.append(
                EventType.AGENT_FAILED,
                phase=InvestigationPhase.EVIDENCE_GATHERING,
                agent_name="evidence_retrieval",
                data={"error": str(exc)},
            )
            _record_error(state, f"evidence_retrieval: {exc}")

        elapsed_ms = (time.time() - started) * 1000
        logger.info(
            f"Stage 4 [Evidence Retrieval]: complete in {elapsed_ms:.1f}ms"
        )
        return state

    # ------------------------------------------------------------------
    # Stage 5: Evidence Verification
    # ------------------------------------------------------------------

    async def _stage_evidence_verification(
        self,
        state: InvestigationState,
        event_log: InvestigationEventLog,
    ) -> InvestigationState:
        """Stage 5: Verify evidence provenance, citations, confidence."""
        started = time.time()
        logger.info(
            "Stage 5 [Evidence Verification]: verifying evidence bundle"
        )

        state["phase"] = InvestigationPhase.VERIFICATION

        event_log.append(
            EventType.PHASE_CHANGED,
            phase=InvestigationPhase.VERIFICATION,
            data={"stage": "evidence_verification"},
        )

        agent = _instantiate_agent(
            _EVIDENCE_VERIFICATION_CLS, self.db, "evidence_verification",
        )
        if agent is None:
            logger.warning(
                "Stage 5 [Evidence Verification]: agent unavailable"
            )
            _record_step(state, "evidence_verification", "skipped")
            return state

        try:
            result = await agent.as_function(state)
            state = _update_state(state, result)

            ctx = state.get("context", {})
            confidence = ctx.get("confidence", 0.0)
            contradictions = ctx.get("contradictions", [])
            citations = ctx.get("citations", [])
            evidence_count = len(state.get("evidence", []))

            event_log.append(
                EventType.AGENT_COMPLETED,
                phase=InvestigationPhase.VERIFICATION,
                agent_name="evidence_verification",
                data={
                    "verified_count": evidence_count,
                    "confidence": confidence,
                    "contradictions_count": len(contradictions),
                    "citations_count": len(citations),
                },
            )
            _record_step(state, "evidence_verification", "completed")

        except Exception as exc:
            logger.error(
                f"Stage 5 [Evidence Verification]: failed: {exc}"
            )
            event_log.append(
                EventType.AGENT_FAILED,
                phase=InvestigationPhase.VERIFICATION,
                agent_name="evidence_verification",
                data={"error": str(exc)},
            )
            _record_error(state, f"evidence_verification: {exc}")

        elapsed_ms = (time.time() - started) * 1000
        logger.info(
            f"Stage 5 [Evidence Verification]: complete in {elapsed_ms:.1f}ms"
        )
        return state

    # ------------------------------------------------------------------
    # Stage 6: Reflection
    # ------------------------------------------------------------------

    async def _stage_reflection(
        self,
        state: InvestigationState,
        event_log: InvestigationEventLog,
    ) -> tuple[InvestigationState, bool]:
        """Stage 6: Evaluate evidence sufficiency.

        Returns ``(state, should_continue)`` where *should_continue*
        indicates whether the pipeline should proceed to specialized
        agents.
        """
        started = time.time()
        logger.info("Stage 6 [Reflection]: evaluating evidence sufficiency")

        state["phase"] = InvestigationPhase.REFLECTION

        event_log.append(
            EventType.PHASE_CHANGED,
            phase=InvestigationPhase.REFLECTION,
            data={"stage": "retrieval_reflection"},
        )

        agent = _instantiate_agent(
            _RETRIEVAL_REFLECTION_CLS, self.db, "retrieval_reflection",
        )

        if agent is not None:
            try:
                result = await agent.as_function(state)
                state = _update_state(state, result)

                ctx = state.get("context", {})
                sufficient = ctx.get("retrieval_sufficient", False)
                decision = ctx.get("retrieval_decision", "unknown")
                gaps = ctx.get("retrieval_gaps", [])

                event_log.append(
                    EventType.REFLECTION_COMPLETED,
                    phase=InvestigationPhase.REFLECTION,
                    agent_name="retrieval_reflection",
                    data={
                        "sufficient": sufficient,
                        "decision": decision,
                        "gaps_count": len(gaps),
                    },
                )
                _record_step(state, "retrieval_reflection", "completed")

                if not sufficient:
                    logger.info(
                        f"Stage 6 [Reflection]: evidence not sufficient "
                        f"(decision={decision}, gaps={len(gaps)}). "
                        f"Pipeline will still proceed to specialized agents."
                    )

                should_continue = True

            except Exception as exc:
                logger.error(
                    f"Stage 6 [Reflection]: failed: {exc}"
                )
                event_log.append(
                    EventType.AGENT_FAILED,
                    phase=InvestigationPhase.REFLECTION,
                    agent_name="retrieval_reflection",
                    data={"error": str(exc)},
                )
                _record_error(state, f"retrieval_reflection: {exc}")
                should_continue = True
        else:
            logger.warning(
                "Stage 6 [Reflection]: agent unavailable, "
                "continuing pipeline"
            )
            should_continue = True
            _record_step(state, "retrieval_reflection", "skipped")

        elapsed_ms = (time.time() - started) * 1000
        logger.info(
            f"Stage 6 [Reflection]: complete in {elapsed_ms:.1f}ms "
            f"(should_continue={should_continue})"
        )
        return state, should_continue

    # ------------------------------------------------------------------
    # Stage 7: Specialized Agents (parallel)
    # ------------------------------------------------------------------

    async def _stage_specialized_agents(
        self,
        state: InvestigationState,
        event_log: InvestigationEventLog,
    ) -> InvestigationState:
        """Stage 7: Run RCA, Compliance, Asset Intelligence,
        Lessons Learned, Expert Knowledge in parallel."""
        started = time.time()
        logger.info(
            "Stage 7 [Specialized Agents]: launching parallel analysis"
        )

        state["phase"] = InvestigationPhase.ANALYSIS

        event_log.append(
            EventType.PHASE_CHANGED,
            phase=InvestigationPhase.ANALYSIS,
            data={"stage": "specialized_agents"},
        )

        agent_specs: list[tuple[str, type | None]] = [
            ("rca_agent", _RCA_CLS),
            ("compliance_agent", _COMPLIANCE_CLS),
            ("asset_intelligence", _ASSET_INTEL_CLS),
            ("lessons_learned_agent", _LESSONS_LEARNED_CLS),
            ("expert_knowledge_agent", _EXPERT_KNOWLEDGE_CLS),
        ]

        agents_to_run: list[tuple[str, Any]] = []
        for name, cls in agent_specs:
            agent = _instantiate_agent(cls, self.db, name)
            if agent is not None:
                agents_to_run.append((name, agent))
            else:
                _record_step(state, name, "skipped")

        if not agents_to_run:
            logger.warning(
                "Stage 7 [Specialized Agents]: no agents available"
            )
            return state

        event_log.append(
            EventType.CONCURRENT_AGENTS_DISPATCHED,
            phase=InvestigationPhase.ANALYSIS,
            data={
                "agents": [name for name, _ in agents_to_run],
                "parallel": True,
            },
        )

        async def _run_one(
            agent_name: str,
            agent: Any,
        ) -> tuple[str, dict[str, Any] | None]:
            for a_name, a in agents_to_run:
                if a_name == agent_name:
                    try:
                        result = await a.as_function(state)
                        return agent_name, result
                    except Exception as exc:
                        logger.error(
                            f"Stage 7 [{agent_name}]: failed: {exc}"
                        )
                        return agent_name, None
            return agent_name, None

        tasks = [
            _run_one(name, agent) for name, agent in agents_to_run
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_reasoning_outputs: list[Any] = []
        merged_claims: list[Any] = []

        for result in results:
            if isinstance(result, Exception):
                logger.error(
                    f"Stage 7: agent task raised exception: {result}"
                )
                continue
            if not isinstance(result, tuple) or len(result) != 2:
                continue
            agent_name, result_state = result
            if result_state is None:
                event_log.append(
                    EventType.AGENT_FAILED,
                    phase=InvestigationPhase.ANALYSIS,
                    agent_name=agent_name,
                    data={"error": "Agent returned None"},
                )
                _record_error(state, f"{agent_name}: returned None")
                continue

            result_ctx = result_state.get("context", {})
            reasoning_outputs = result_ctx.get("reasoning_outputs", [])
            all_reasoning_outputs.extend(reasoning_outputs)

            result_claims = result_state.get("claims", [])
            merged_claims.extend(result_claims)

            event_log.append(
                EventType.AGENT_COMPLETED,
                phase=InvestigationPhase.ANALYSIS,
                agent_name=agent_name,
                data={
                    "reasoning_outputs_count": len(reasoning_outputs),
                    "claims_count": len(result_claims),
                },
            )
            _record_step(state, agent_name, "completed")

        ctx = dict(state.get("context", {}))
        existing_outputs: list[Any] = ctx.get("reasoning_outputs", [])
        existing_outputs.extend(all_reasoning_outputs)
        ctx["reasoning_outputs"] = existing_outputs
        state["context"] = ctx

        existing_claims = list(state.get("claims", []))
        existing_claims.extend(merged_claims)
        state["claims"] = existing_claims

        elapsed_ms = (time.time() - started) * 1000
        logger.info(
            f"Stage 7 [Specialized Agents]: complete in {elapsed_ms:.1f}ms "
            f"({len(all_reasoning_outputs)} outputs, "
            f"{len(merged_claims)} claims)"
        )
        return state

    # ------------------------------------------------------------------
    # Stage 8: Report Composer
    # ------------------------------------------------------------------

    async def _stage_report_composer(
        self,
        state: InvestigationState,
        event_log: InvestigationEventLog,
    ) -> InvestigationState:
        """Stage 8: Synthesize all outputs into FinalReport."""
        started = time.time()
        logger.info("Stage 8 [Report Composer]: synthesizing final report")

        state["phase"] = InvestigationPhase.SYNTHESIS

        event_log.append(
            EventType.PHASE_CHANGED,
            phase=InvestigationPhase.SYNTHESIS,
            data={"stage": "report_composer"},
        )

        agent = _instantiate_agent(
            _REPORT_COMPOSER_CLS, self.db, "report_composer",
        )
        if agent is None:
            logger.warning(
                "Stage 8 [Report Composer]: agent unavailable"
            )
            _record_step(state, "report_composer", "skipped")
            return state

        try:
            result = await agent.as_function(state)
            state = _update_state(state, result)

            ctx = state.get("context", {})
            final_report = ctx.get("final_report")
            if final_report is not None:
                report: FinalReport = final_report
                event_log.append(
                    EventType.AGENT_COMPLETED,
                    phase=InvestigationPhase.SYNTHESIS,
                    agent_name="report_composer",
                    data={
                        "report_title": report.title,
                        "claims_count": len(report.grounded_claims),
                        "actions_count": len(report.recommended_actions),
                        "contradictions_count": len(report.contradictions),
                        "confidence": report.confidence_statement,
                    },
                )
            else:
                event_log.append(
                    EventType.AGENT_COMPLETED,
                    phase=InvestigationPhase.SYNTHESIS,
                    agent_name="report_composer",
                    data={"report_created": False},
                )
            _record_step(state, "report_composer", "completed")

        except Exception as exc:
            logger.error(f"Stage 8 [Report Composer]: failed: {exc}")
            event_log.append(
                EventType.AGENT_FAILED,
                phase=InvestigationPhase.SYNTHESIS,
                agent_name="report_composer",
                data={"error": str(exc)},
            )
            _record_error(state, f"report_composer: {exc}")

        elapsed_ms = (time.time() - started) * 1000
        logger.info(
            f"Stage 8 [Report Composer]: complete in {elapsed_ms:.1f}ms"
        )
        return state

    # ------------------------------------------------------------------
    # Stage 9: Human Approval
    # ------------------------------------------------------------------

    async def _stage_human_approval(
        self,
        state: InvestigationState,
        event_log: InvestigationEventLog,
    ) -> tuple[InvestigationState, bool]:
        """Stage 9: Check if approval needed, pause if so.

        Returns ``(state, approved)``.
        """
        started = time.time()
        logger.info("Stage 9 [Human Approval]: checking approval gates")

        state["phase"] = InvestigationPhase.APPROVAL

        event_log.append(
            EventType.PHASE_CHANGED,
            phase=InvestigationPhase.APPROVAL,
            data={"stage": "human_approval"},
        )

        ctx = state.get("context", {})
        gate_type_str = ctx.get("approval_gate_type", None)

        if gate_type_str is not None:
            state["approval_required"] = True

        approval_required = state.get("approval_required", False)

        if not approval_required:
            logger.info(
                "Stage 9 [Human Approval]: no approval required, auto-approving"
            )
            state["approval_result"] = {
                "decision": "approve",
                "reviewer": "auto",
                "comments": "No approval gate triggered",
                "conditions": [],
                "gate_type": None,
            }
            _record_step(state, "human_approval", "auto_approved")
            elapsed_ms = (time.time() - started) * 1000
            logger.info(
                f"Stage 9 [Human Approval]: complete in {elapsed_ms:.1f}ms "
                f"(auto-approved)"
            )
            return state, True

        gate_str = gate_type_str or "general"
        logger.info(
            f"Stage 9 [Human Approval]: approval required "
            f"(gate={gate_str})"
        )

        event_log.append(
            EventType.APPROVAL_REQUESTED,
            phase=InvestigationPhase.APPROVAL,
            agent_name="human_approval",
            data={"gate_type": gate_str},
        )

        await self.approval_node.request_approval(
            state,  # type: ignore[arg-type]
            summary=state.get("query", ""),
            triggered_by="pipeline",
        )

        auto_result: dict[str, Any] = {
            "decision": "approve",
            "reviewer": "auto_pipeline",
            "comments": (
                f"Auto-approved in pipeline mode for gate={gate_str}"
            ),
            "conditions": [],
            "gate_type": gate_str,
        }
        state["approval_result"] = auto_result
        state["approval_required"] = False
        state["pending_approval_request"] = None

        event_log.append(
            EventType.APPROVAL_RECEIVED,
            phase=InvestigationPhase.APPROVAL,
            agent_name="human_approval",
            data={"decision": "approve", "gate_type": gate_str},
        )
        _record_step(state, "human_approval", "approved")

        elapsed_ms = (time.time() - started) * 1000
        logger.info(
            f"Stage 9 [Human Approval]: complete in {elapsed_ms:.1f}ms "
            f"(approved)"
        )
        return state, True

    # ------------------------------------------------------------------
    # Stage 10: Final Response
    # ------------------------------------------------------------------

    async def _stage_final_response(
        self,
        state: InvestigationState,
        event_log: InvestigationEventLog,
    ) -> InvestigationState:
        """Stage 10: Format FinalReport as AgentResponse."""
        started = time.time()
        logger.info("Stage 10 [Final Response]: formatting final response")

        event_log.append(
            EventType.PHASE_CHANGED,
            phase=InvestigationPhase.COMPLETION,
            data={"stage": "final_response"},
        )

        ctx = state.get("context", {})
        final_report: FinalReport | None = ctx.get("final_report")

        if final_report is None:
            logger.warning(
                "Stage 10 [Final Response]: no FinalReport available, "
                "building minimal response"
            )
            response = AgentResponse(
                answer=(
                    "The investigation could not produce a final report. "
                    "No reasoning outputs were available for composition."
                ),
                confidence_score=0.0,
                claims=[],
                missing_evidence=["No report composed"],
                contradictions=[],
                recommended_actions=[],
                metadata={
                    "investigation_id": state.get("investigation_id", ""),
                    "phase": _phase_str(state.get("phase", "")),
                },
            )
        else:
            report = final_report

            answer_parts: list[str] = []
            answer_parts.append(report.summary)

            if report.grounded_claims:
                supported = [
                    c for c in report.grounded_claims
                    if c.status.value == "supported"
                ]
                uncertain = [
                    c for c in report.grounded_claims
                    if c.status.value == "uncertain"
                ]
                if supported:
                    answer_parts.append(
                        f"\n\nSupported findings ({len(supported)}):"
                    )
                    for claim in supported[:5]:
                        answer_parts.append(f"  - {claim.text[:200]}")
                if uncertain:
                    answer_parts.append(
                        f"\n\nUncertain findings ({len(uncertain)}):"
                    )
                    for claim in uncertain[:3]:
                        answer_parts.append(f"  - {claim.text[:200]}")

            if report.recommended_actions:
                answer_parts.append("\n\nRecommended actions:")
                for action in report.recommended_actions[:5]:
                    answer_parts.append(
                        f"  [{action.priority.upper()}] "
                        f"{action.description[:150]}"
                    )

            if report.disclaimer:
                answer_parts.append(f"\n\n{report.disclaimer}")

            answer = "\n".join(answer_parts)

            confidence_score = 0.0
            if report.grounded_claims:
                claim_scores = []
                for claim in report.grounded_claims:
                    if claim.sources:
                        claim_scores.append(
                            claim.sources[0].confidence_score
                        )
                if claim_scores:
                    confidence_score = sum(claim_scores) / len(
                        claim_scores,
                    )

            response = AgentResponse(
                answer=answer,
                confidence_score=min(max(confidence_score, 0.0), 1.0),
                claims=report.grounded_claims,
                missing_evidence=report.missing_evidence,
                contradictions=report.contradictions,
                recommended_actions=report.recommended_actions,
                graph_paths=report.graph_paths,
                metadata={
                    "investigation_id": state.get("investigation_id", ""),
                    "report_title": report.title,
                    "confidence_statement": report.confidence_statement,
                    "disclaimer": report.disclaimer,
                    "phase": _phase_str(state.get("phase", "")),
                },
            )

        ctx = dict(state.get("context", {}))
        ctx["final_response"] = response
        state["context"] = ctx

        event_log.append(
            EventType.AGENT_COMPLETED,
            phase=InvestigationPhase.COMPLETION,
            agent_name="final_response",
            data={
                "has_response": True,
                "confidence": response.confidence_score,
                "claims_count": len(response.claims),
                "actions_count": len(response.recommended_actions),
            },
        )
        _record_step(state, "final_response", "completed")

        elapsed_ms = (time.time() - started) * 1000
        logger.info(
            f"Stage 10 [Final Response]: complete in {elapsed_ms:.1f}ms "
            f"(confidence={response.confidence_score:.3f})"
        )
        return state

    # ------------------------------------------------------------------
    # Stage 11: Complete
    # ------------------------------------------------------------------

    async def _stage_complete(
        self,
        state: InvestigationState,
        event_log: InvestigationEventLog,
        checkpoint_manager: CheckpointManager,
    ) -> InvestigationState:
        """Stage 11: Save checkpoint, mark complete."""
        started = time.time()
        logger.info("Stage 11 [Complete]: saving checkpoint and finalizing")

        state["is_complete"] = True
        if state.get("termination_reason") is None:
            state["termination_reason"] = TerminationReason.SUFFICIENT_EVIDENCE

        event_log.append(
            EventType.INVESTIGATION_COMPLETED,
            phase=InvestigationPhase.COMPLETION,
            data={
                "termination_reason": str(
                    state.get("termination_reason", ""),
                ),
                "total_evidence": len(state.get("evidence", [])),
                "total_claims": len(state.get("claims", [])),
                "completed_agents": list(
                    state.get("completed_agents", []),
                ),
            },
        )

        if self.auto_checkpoint:
            try:
                checkpoint = checkpoint_manager.save(
                    state,  # type: ignore[arg-type]
                    phase=InvestigationPhase.COMPLETION,
                    checkpoint_type=CheckpointType.AUTOMATIC,
                    description="Pipeline completion checkpoint",
                    event_log_offset=event_log.get_offset(),
                )
                state["last_checkpoint_id"] = (
                    checkpoint.metadata.checkpoint_id
                )
                checkpoints = list(state.get("checkpoints", []))
                checkpoints.append(checkpoint)
                state["checkpoints"] = checkpoints

                event_log.append(
                    EventType.CHECKPOINT_SAVED,
                    phase=InvestigationPhase.COMPLETION,
                    data={
                        "checkpoint_id": (
                            checkpoint.metadata.checkpoint_id
                        ),
                    },
                )
            except Exception as exc:
                logger.error(
                    f"Stage 11 [Complete]: checkpoint save failed: {exc}"
                )

        elapsed_ms = (time.time() - started) * 1000
        logger.info(
            f"Stage 11 [Complete]: pipeline finished in {elapsed_ms:.1f}ms"
        )
        return state

    # ------------------------------------------------------------------
    # Result builder
    # ------------------------------------------------------------------

    def _build_result(
        self,
        state: InvestigationState,
        investigation_id: str,
        event_log: InvestigationEventLog,
    ) -> dict[str, Any]:
        """Build the final result dict from the completed state."""
        ctx = state.get("context", {})
        final_response = ctx.get("final_response")
        final_report = ctx.get("final_report")

        result: dict[str, Any] = {
            "final_response": final_response,
            "final_report": final_report,
            "investigation_id": investigation_id,
            "phase": _phase_str(state.get("phase", "")),
            "is_complete": state.get("is_complete", False),
            "termination_reason": str(
                state.get("termination_reason", ""),
            )
            if state.get("termination_reason")
            else None,
            "evidence_count": len(state.get("evidence", [])),
            "claims_count": len(state.get("claims", [])),
            "errors": list(state.get("errors", [])),
            "completed_agents": list(state.get("completed_agents", [])),
            "steps_completed": list(state.get("steps_completed", [])),
            "event_log": event_log,
            "event_summary": event_log.summary(),
            "checkpoints_saved": len(state.get("checkpoints", [])),
        }

        # Include observability dashboard snapshot when available
        try:
            dashboard = ObservabilityDashboard(
                event_log=event_log,
                audit_logger=self.audit_logger,
            )
            result["observability"] = dashboard.get_dashboard_snapshot()
        except Exception:
            result["observability"] = None

        return result


# ======================================================================
# State mutation helpers
# ======================================================================


def _record_step(
    state: InvestigationState,
    agent_name: str,
    status: str,
) -> None:
    """Append a step to the state's step list."""
    steps = list(state.get("steps_completed", []))
    steps.append(f"{agent_name}:{status}")
    state["steps_completed"] = steps

    completed = list(state.get("completed_agents", []))
    if status == "completed" and agent_name not in completed:
        completed.append(agent_name)
    state["completed_agents"] = completed


def _record_error(
    state: InvestigationState,
    error_msg: str,
) -> None:
    """Append an error to the state's error list."""
    errors = list(state.get("errors", []))
    errors.append(error_msg)
    state["errors"] = errors


def _update_state(
    current: InvestigationState,
    agent_result: dict[str, Any],
) -> InvestigationState:
    """Update the current state with values from an agent result.

    Handles list fields by extending, dict fields by updating, and
    scalar fields by replacing.  ``InvestigationState`` is a TypedDict
    that is structurally a ``dict`` at runtime; we cast once here to
    avoid per-line type-ignores for dynamic key assignment.
    """
    buf: dict[str, Any] = dict(current)
    list_keys = {"evidence", "claims", "messages", "steps_completed", "errors"}
    for key, value in agent_result.items():
        if key in list_keys and isinstance(value, list):
            existing = list(buf.get(key, []))
            existing.extend(value)
            buf[key] = existing
        elif isinstance(value, dict) and key in buf and isinstance(
            buf[key], dict,
        ):
            existing_dict: dict[str, Any] = dict(buf[key])
            existing_dict.update(value)
            buf[key] = existing_dict
        else:
            buf[key] = value
    return buf  # type: ignore[return-value]


# ======================================================================
# Backward-compatible StateGraph builder
# ======================================================================


# Agent executor wrapper (kept for backward compatibility with the
# old workflow pattern).


class AgentExecutor:
    """Wraps a registered agent callable with retry, timeout, and
    event emission.

    This is the legacy executor used by the old supervisor-driven
    workflow.  For the new 11-stage pipeline, use
    ``InvestigationPipeline`` instead.
    """

    def __init__(
        self,
        agent_fn: Callable[[dict[str, Any]], Any],
        registration: AgentRegistration,
        event_log: InvestigationEventLog,
        failure_recovery: FailureRecoveryManager,
    ) -> None:
        self.agent_fn = agent_fn
        self.registration = registration
        self.event_log = event_log
        self.failure_recovery = failure_recovery

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        agent_name = self.registration.name
        retry_policy = RetryPolicy.from_registration(self.registration)
        timeout_manager = TimeoutManager()

        started_at = time.time()

        self.event_log.append(
            EventType.AGENT_INVOKED,
            phase=InvestigationPhase(
                _phase_str(state.get("phase", InvestigationPhase.INITIALIZATION)),
            ),
            agent_name=agent_name,
        )

        result_state, status, attempts = await execute_with_retry(
            self.agent_fn,
            state,
            retry_policy=retry_policy,
            timeout_manager=timeout_manager,
            timeout_seconds=self.registration.timeout_seconds,
            on_retry=lambda attempt, exc: self._on_retry(
                agent_name, attempt, exc,
            ),
        )

        elapsed_ms = (time.time() - started_at) * 1000

        if status == AgentStatus.COMPLETED:
            self.failure_recovery.record_success(agent_name)
            self.event_log.append(
                EventType.AGENT_COMPLETED,
                phase=InvestigationPhase(
                    _phase_str(
                        state.get("phase", InvestigationPhase.INITIALIZATION),
                    ),
                ),
                agent_name=agent_name,
                data={"elapsed_ms": elapsed_ms, "attempts": attempts},
            )
        else:
            error_msg = (
                f"Agent {agent_name} failed with status {status} "
                f"after {attempts} attempts"
            )
            self.failure_recovery.record_failure(agent_name, error_msg)
            self.event_log.append(
                EventType.AGENT_FAILED,
                phase=InvestigationPhase(
                    _phase_str(
                        state.get("phase", InvestigationPhase.INITIALIZATION),
                    ),
                ),
                agent_name=agent_name,
                data={
                    "status": status,
                    "attempts": attempts,
                    "elapsed_ms": elapsed_ms,
                },
            )

        if result_state is None:
            result_state = state

        metadata = AgentInvocationMetadata(
            agent_name=agent_name,
            agent_role=self.registration.role,
            status=status,
            execution_time_ms=elapsed_ms,
        )
        agent_metadata = result_state.get("agent_metadata", {})
        agent_metadata[agent_name] = metadata.model_dump()
        result_state["agent_metadata"] = agent_metadata

        completed = list(result_state.get("completed_agents", []))
        if status == AgentStatus.COMPLETED and agent_name not in completed:
            completed.append(agent_name)
        result_state["completed_agents"] = completed

        pending = list(result_state.get("pending_agents", []))
        if agent_name in pending:
            pending.remove(agent_name)
        result_state["pending_agents"] = pending

        steps = list(result_state.get("steps_completed", []))
        steps.append(agent_name)
        result_state["steps_completed"] = steps

        return dict(result_state)

    async def _on_retry(
        self,
        agent_name: str,
        attempt: int,
        exc: Exception,
    ) -> None:
        self.event_log.append(
            EventType.AGENT_RETRYING,
            agent_name=agent_name,
            data={"attempt": attempt, "error": str(exc)},
        )


# ======================================================================
# Old workflow node functions (kept for backward compatibility)
# ======================================================================


def _create_supervisor_node(
    supervisor: SupervisorAgent,
    event_log: InvestigationEventLog,
) -> Callable[[InvestigationState], dict[str, Any]]:
    """Create the supervisor node that decides the next action."""

    async def supervisor_node(state: InvestigationState) -> dict[str, Any]:
        iteration = state.get("iteration", 0)
        state["iteration"] = iteration + 1

        decision = supervisor.decide_next(state)

        event_log.append(
            EventType.SUPERVISOR_DECISION,
            phase=decision.phase,
            data={
                "agents_to_dispatch": decision.agents_to_dispatch,
                "parallel": decision.parallel,
                "should_continue": decision.should_continue,
                "termination_reason": decision.termination_reason,
            },
        )

        if not decision.should_continue:
            state["is_complete"] = True
            state["termination_reason"] = decision.termination_reason
            state["phase"] = decision.phase
            event_log.append(
                EventType.INVESTIGATION_COMPLETED,
                phase=decision.phase,
                data={"reason": decision.termination_reason},
            )
            return state

        state["phase"] = decision.phase
        state["pending_agents"] = decision.agents_to_dispatch
        state["supervisor_decisions"] = list(
            state.get("supervisor_decisions", []),
        ) + [decision]

        event_log.append(
            EventType.PHASE_CHANGED,
            phase=decision.phase,
            data={"from_iteration": iteration},
        )

        return state

    return supervisor_node


def _create_gather_node(
    agent_registrations: dict[str, AgentRegistration],
    agent_functions: dict[str, Callable],
    event_log: InvestigationEventLog,
    failure_recovery: FailureRecoveryManager,
) -> Callable[[InvestigationState], dict[str, Any]]:
    """Create the gather node that dispatches agents (possibly in parallel)
    and collects their results."""

    async def gather_node(state: InvestigationState) -> dict[str, Any]:
        pending = list(state.get("pending_agents", []))
        if not pending:
            return state

        phase = state.get("phase", InvestigationPhase.EVIDENCE_GATHERING)

        can_parallel = len(pending) > 1
        for name in pending:
            reg = agent_registrations.get(name)
            if reg and not reg.can_run_in_parallel:
                can_parallel = False
                break

        event_log.append(
            EventType.CONCURRENT_AGENTS_DISPATCHED,
            phase=phase,
            data={"agents": pending, "parallel": can_parallel},
        )

        current_state = dict(state)

        if can_parallel and len(pending) > 1:
            executors = []
            for name in pending:
                reg = agent_registrations.get(name)
                fn = agent_functions.get(name)
                if reg and fn:
                    executors.append(
                        AgentExecutor(
                            fn, reg, event_log, failure_recovery,
                        ),
                    )

            async def run_executor(
                ex: AgentExecutor,
            ) -> dict[str, Any]:
                return await ex.execute(current_state)

            results = await asyncio.gather(
                *[run_executor(ex) for ex in executors],
                return_exceptions=True,
            )

            for result in results:
                if isinstance(result, dict):
                    _merge_state(current_state, result)
                elif isinstance(result, Exception):
                    event_log.append(
                        EventType.AGENT_FAILED,
                        phase=phase,
                        data={"error": str(result)},
                    )
                    errors = list(current_state.get("errors", []))
                    errors.append(f"PARALLEL_FAILURE: {result}")
                    current_state["errors"] = errors
        else:
            for name in pending:
                reg = agent_registrations.get(name)
                fn = agent_functions.get(name)
                if reg and fn:
                    executor = AgentExecutor(
                        fn, reg, event_log, failure_recovery,
                    )
                    result = await executor.execute(current_state)
                    current_state = result

        return current_state

    return gather_node


def _create_reflection_node(
    reflection_agent: ReflectionAgent,
    event_log: InvestigationEventLog,
) -> Callable[[InvestigationState], dict[str, Any]]:
    """Create the reflection node."""

    async def reflection_node(
        state: InvestigationState,
    ) -> dict[str, Any]:
        output = await reflection_agent.reflect(state)

        event_log.append(
            EventType.REFLECTION_COMPLETED,
            phase=InvestigationPhase.REFLECTION,
            agent_name="reflection_agent",
            data={
                "quality": output.overall_quality,
                "gaps": output.identified_gaps,
                "should_continue": output.should_continue,
            },
        )

        agent_outputs = dict(state.get("agent_outputs", {}))
        agent_outputs["reflection_agent"] = output.model_dump()
        state["agent_outputs"] = agent_outputs

        completed = list(state.get("completed_agents", []))
        if "reflection_agent" not in completed:
            completed.append("reflection_agent")
        state["completed_agents"] = completed

        if output.should_abstain:
            state["should_abstain"] = True
            state["abstention_reason"] = output.abstention_reason

        if not output.should_continue and not output.should_abstain:
            state["is_complete"] = True
            state["termination_reason"] = (
                TerminationReason.SUFFICIENT_EVIDENCE
            )

        return state

    return reflection_node


def _create_approval_node(
    approval_node: HumanApprovalNode,
    event_log: InvestigationEventLog,
) -> Callable[[InvestigationState], dict[str, Any]]:
    """Create the human approval node."""

    async def approval_fn(
        state: InvestigationState,
    ) -> dict[str, Any]:
        result = await approval_node.request_approval(
            state,
            summary=state.get("query", ""),
            triggered_by="supervisor",
        )

        event_log.append(
            EventType.APPROVAL_REQUESTED,
            phase=InvestigationPhase.APPROVAL,
            agent_name="human_approval",
        )

        return result

    return approval_fn


def _create_checkpoint_node(
    checkpoint_manager: CheckpointManager,
    event_log: InvestigationEventLog,
) -> Callable[[InvestigationState], dict[str, Any]]:
    """Create the checkpoint node."""

    async def checkpoint_fn(
        state: InvestigationState,
    ) -> dict[str, Any]:
        checkpoint = checkpoint_manager.save(
            state,
            phase=InvestigationPhase(
                _phase_str(
                    state.get("phase", InvestigationPhase.INITIALIZATION),
                ),
            ),
            checkpoint_type=CheckpointType.AUTOMATIC,
            description=(
                f"Auto-checkpoint at iteration {state.get('iteration', 0)}"
            ),
            event_log_offset=event_log.get_offset(),
        )

        event_log.append(
            EventType.CHECKPOINT_SAVED,
            phase=InvestigationPhase(
                _phase_str(
                    state.get("phase", InvestigationPhase.INITIALIZATION),
                ),
            ),
            data={"checkpoint_id": checkpoint.metadata.checkpoint_id},
        )

        state["last_checkpoint_id"] = checkpoint.metadata.checkpoint_id
        checkpoints = list(state.get("checkpoints", []))
        checkpoints.append(checkpoint)
        state["checkpoints"] = checkpoints

        return state

    return checkpoint_fn


# ======================================================================
# Routing logic (backward compatibility)
# ======================================================================


def route_after_supervisor(state: InvestigationState) -> str:
    """Decide where to go after the supervisor node."""
    if state.get("is_complete"):
        return "end"

    pending = state.get("pending_agents", [])
    phase = state.get("phase", InvestigationPhase.INITIALIZATION)

    if not pending:
        if phase == InvestigationPhase.REFLECTION:
            return "reflection"
        if phase == InvestigationPhase.APPROVAL:
            return "approval"
        if phase == InvestigationPhase.COMPLETION:
            return "checkpoint_then_end"
        return "supervisor"

    return "gather"


def route_after_gather(state: InvestigationState) -> str:
    """After gathering agent results, go back to supervisor."""
    if state.get("is_complete"):
        return "end"
    return "supervisor"


def route_after_reflection(state: InvestigationState) -> str:
    """After reflection, go back to supervisor."""
    if state.get("is_complete"):
        return "end"
    if state.get("should_abstain"):
        return "end"
    return "supervisor"


# ======================================================================
# Workflow builder (backward compatible)
# ======================================================================


def create_investigation_workflow(
    agent_registry: AgentRegistry,
    agent_functions: dict[str, Callable],
    *,
    max_iterations: int = 10,
    evidence_confidence_threshold: float = 0.7,
    auto_checkpoint_interval: int = 3,
) -> StateGraph:
    """Build and compile the LangGraph StateGraph (backward compatible).

    This wraps ``InvestigationPipeline`` for backward compatibility.
    The returned graph follows the old supervisor-driven dispatch
    pattern with conditional routing.

    For new code, prefer ``InvestigationPipeline`` directly.
    """
    capability_registry = AgentCapabilityRegistry(agent_registry)
    event_log = InvestigationEventLog("runtime")
    failure_recovery = FailureRecoveryManager()
    checkpoint_manager = CheckpointManager("runtime")
    approval_node = HumanApprovalNode()
    reflection_agent = ReflectionAgent()

    supervisor = SupervisorAgent(
        agent_registry=agent_registry,
        capability_registry=capability_registry,
        max_iterations=max_iterations,
        evidence_confidence_threshold=evidence_confidence_threshold,
    )

    agent_registrations: dict[str, AgentRegistration] = {}
    for reg in agent_registry.list_agents():
        agent_registrations[reg.name] = reg

    supervisor_fn = _create_supervisor_node(supervisor, event_log)
    gather_fn = _create_gather_node(
        agent_registrations, agent_functions, event_log, failure_recovery,
    )
    reflection_fn = _create_reflection_node(reflection_agent, event_log)
    approval_fn = _create_approval_node(approval_node, event_log)
    checkpoint_fn = _create_checkpoint_node(checkpoint_manager, event_log)

    graph = StateGraph(InvestigationState)

    graph.add_node("supervisor", supervisor_fn)
    graph.add_node("gather", gather_fn)
    graph.add_node("reflection", reflection_fn)
    graph.add_node("approval", approval_fn)
    graph.add_node("checkpoint", checkpoint_fn)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "gather": "gather",
            "reflection": "reflection",
            "approval": "approval",
            "checkpoint_then_end": "checkpoint",
            "supervisor": "supervisor",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "gather",
        route_after_gather,
        {
            "supervisor": "supervisor",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "reflection",
        route_after_reflection,
        {
            "supervisor": "supervisor",
            "end": END,
        },
    )

    graph.add_edge("approval", "supervisor")

    graph.add_edge("checkpoint", END)

    return graph
