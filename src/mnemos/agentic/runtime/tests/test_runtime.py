"""Architecture-level tests for the multi-agent runtime.

These tests verify the structural integrity of the runtime:
- All components can be instantiated
- The registry correctly manages agents
- The event log correctly tracks events
- The checkpoint system saves and loads
- The supervisor makes valid decisions
- The workflow compiles and runs with stub agents
- Recovery and retry mechanisms work correctly
"""

from __future__ import annotations

from typing import Any

import pytest

from mnemos.agentic.runtime import (
    AgentCapability,
    AgentCapabilityRegistry,
    AgentInvocationMetadata,
    AgentMessage,
    AgentRegistration,
    AgentRegistry,
    AgentRole,
    AgentStatus,
    CheckpointManager,
    EventType,
    FailureRecoveryManager,
    HumanApprovalNode,
    InvestigationEventLog,
    InvestigationPhase,
    InvestigationState,
    MessageType,
    ReflectionAgent,
    ReflectionOutput,
    RetryPolicy,
    RetryStrategy,
    StateRecoveryManager,
    TerminationReason,
    ToolCallRecord,
    create_initial_state,
    execute_with_retry,
)
from mnemos.agentic.runtime.supervisor import SupervisorAgent
from mnemos.agentic.runtime.types import SupervisorDecision
from mnemos.agentic.runtime.workflow import create_investigation_workflow

# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def agent_registry() -> AgentRegistry:
    reg = AgentRegistry()
    reg.register(
        AgentRegistration(
            name="retrieval_agent",
            role=AgentRole.RETRIEVAL,
            capabilities=[
                AgentCapability(
                    name="retrieval",
                    input_types=["query"],
                    output_types=["evidence"],
                )
            ],
            timeout_seconds=30.0,
        )
    )
    reg.register(
        AgentRegistration(
            name="analysis_agent",
            role=AgentRole.ANALYSIS,
            capabilities=[
                AgentCapability(
                    name="analysis",
                    input_types=["evidence"],
                    output_types=["analysis_result"],
                    dependencies=["retrieval_agent"],
                )
            ],
            timeout_seconds=60.0,
        )
    )
    reg.register(
        AgentRegistration(
            name="verification_agent",
            role=AgentRole.VERIFICATION,
            capabilities=[
                AgentCapability(
                    name="verification",
                    input_types=["analysis_result", "evidence"],
                    output_types=["verified_result"],
                    dependencies=["analysis_agent"],
                )
            ],
            timeout_seconds=45.0,
        )
    )
    return reg


@pytest.fixture
def capability_registry(agent_registry: AgentRegistry) -> AgentCapabilityRegistry:
    return AgentCapabilityRegistry(agent_registry)


@pytest.fixture
def event_log() -> InvestigationEventLog:
    return InvestigationEventLog("test_investigation")


@pytest.fixture
def checkpoint_manager() -> CheckpointManager:
    return CheckpointManager("test_investigation")


@pytest.fixture
def initial_state() -> InvestigationState:
    return create_initial_state(
        investigation_id="test_inv_001",
        query="What is the failure mode of P-101?",
        context={"site_id": "site_alpha", "org_id": "org_test"},
        trace_id="trace_test_001",
    )


# ======================================================================
# Types tests
# ======================================================================


class TestTypes:
    def test_agent_role_enum(self) -> None:
        assert AgentRole.SUPERVISOR == "supervisor"
        assert AgentRole.ANALYSIS == "analysis"

    def test_message_type_enum(self) -> None:
        assert MessageType.REQUEST == "request"
        assert MessageType.EVENT == "event"

    def test_investigation_phase_enum(self) -> None:
        assert InvestigationPhase.INITIALIZATION == "initialization"
        assert InvestigationPhase.COMPLETION == "completion"

    def test_agent_status_enum(self) -> None:
        assert AgentStatus.PENDING == "pending"
        assert AgentStatus.COMPLETED == "completed"

    def test_retry_strategy_enum(self) -> None:
        assert RetryStrategy.EXPONENTIAL_BACKOFF == "exponential_backoff"
        assert RetryStrategy.NO_RETRY == "no_retry"

    def test_agent_message_creation(self) -> None:
        msg = AgentMessage(
            message_type=MessageType.EVENT,
            source_agent="test_agent",
            payload={"key": "value"},
        )
        assert msg.message_type == MessageType.EVENT
        assert msg.source_agent == "test_agent"
        assert msg.message_id  # auto-generated

    def test_agent_registration_creation(self) -> None:
        reg = AgentRegistration(
            name="test_agent",
            role=AgentRole.ANALYSIS,
            capabilities=[
                AgentCapability(
                    name="test_cap",
                    input_types=["input_1"],
                    output_types=["output_1"],
                )
            ],
        )
        assert reg.name == "test_agent"
        assert reg.role == AgentRole.ANALYSIS
        assert len(reg.capabilities) == 1

    def test_agent_invocation_metadata(self) -> None:
        meta = AgentInvocationMetadata(
            agent_name="test_agent",
            agent_role=AgentRole.ANALYSIS,
            status=AgentStatus.COMPLETED,
            execution_time_ms=150.5,
            confidence=0.85,
            reasoning_summary="Test reasoning",
        )
        assert meta.agent_name == "test_agent"
        assert meta.execution_time_ms == 150.5
        assert meta.confidence == 0.85

    def test_tool_call_record(self) -> None:
        record = ToolCallRecord(
            tool_name="vector_search",
            arguments={"query": "test"},
            duration_ms=50.0,
        )
        assert record.tool_name == "vector_search"
        assert record.success is True

    def test_supervisor_decision(self) -> None:
        decision = SupervisorDecision(
            phase=InvestigationPhase.EVIDENCE_GATHERING,
            agents_to_dispatch=["retrieval_agent"],
            parallel=False,
            reasoning="Need more evidence",
        )
        assert decision.should_continue is True
        assert decision.agents_to_dispatch == ["retrieval_agent"]

    def test_agent_result(self) -> None:
        from mnemos.agentic.runtime.types import AgentResult

        result = AgentResult(
            agent_name="test",
            status=AgentStatus.COMPLETED,
            confidence=0.9,
        )
        assert result.agent_name == "test"
        assert result.confidence == 0.9


# ======================================================================
# State tests
# ======================================================================


class TestState:
    def test_create_initial_state(self) -> None:
        state = create_initial_state(
            investigation_id="inv_001",
            query="Test query",
        )
        assert state["investigation_id"] == "inv_001"
        assert state["query"] == "Test query"
        assert state["phase"] == InvestigationPhase.INITIALIZATION
        assert state["evidence"] == []
        assert state["claims"] == []
        assert state["iteration"] == 0
        assert state["is_complete"] is False
        assert state["should_abstain"] is False

    def test_create_initial_state_with_context(self) -> None:
        state = create_initial_state(
            investigation_id="inv_002",
            query="Test query",
            context={"site_id": "site_1"},
            max_iterations=5,
        )
        assert state["context"]["site_id"] == "site_1"
        assert state["max_iterations"] == 5


# ======================================================================
# Registry tests
# ======================================================================


class TestAgentRegistry:
    def test_register_and_get(self, agent_registry: AgentRegistry) -> None:
        reg = agent_registry.get("retrieval_agent")
        assert reg is not None
        assert reg.name == "retrieval_agent"
        assert reg.role == AgentRole.RETRIEVAL

    def test_register_duplicate_raises(self) -> None:
        reg = AgentRegistry()
        reg.register(AgentRegistration(name="dup", role=AgentRole.GENERIC))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(AgentRegistration(name="dup", role=AgentRole.GENERIC))

    def test_unregister(self, agent_registry: AgentRegistry) -> None:
        removed = agent_registry.unregister("retrieval_agent")
        assert removed is not None
        assert removed.name == "retrieval_agent"
        assert agent_registry.get("retrieval_agent") is None

    def test_list_agents(self, agent_registry: AgentRegistry) -> None:
        agents = agent_registry.list_agents()
        assert len(agents) == 3

    def test_get_by_role(self, agent_registry: AgentRegistry) -> None:
        retrieval_agents = agent_registry.get_by_role(AgentRole.RETRIEVAL)
        assert len(retrieval_agents) == 1
        assert retrieval_agents[0].name == "retrieval_agent"

    def test_get_by_capability(self, agent_registry: AgentRegistry) -> None:
        producers = agent_registry.get_by_capability("evidence")
        assert len(producers) == 1
        assert producers[0].name == "retrieval_agent"

    def test_get_dependencies(self, agent_registry: AgentRegistry) -> None:
        deps = agent_registry.get_dependencies("analysis_agent")
        assert "retrieval_agent" in deps

    def test_get_executable_agents(self, agent_registry: AgentRegistry) -> None:
        executable = agent_registry.get_executable_agents(completed=[], pending=[])
        names = [a.name for a in executable]
        assert "retrieval_agent" in names

    def test_get_executable_after_completion(self, agent_registry: AgentRegistry) -> None:
        executable = agent_registry.get_executable_agents(completed=["retrieval_agent"], pending=[])
        names = [a.name for a in executable]
        assert "analysis_agent" in names
        assert "retrieval_agent" not in names

    def test_summary(self, agent_registry: AgentRegistry) -> None:
        summary = agent_registry.summary()
        assert summary["total_agents"] == 3
        assert "retrieval_agent" in summary["agents"]


class TestCapabilityRegistry:
    def test_producers_of(self, capability_registry: AgentCapabilityRegistry) -> None:
        producers = capability_registry.producers_of("evidence")
        assert "retrieval_agent" in producers

    def test_consumers_of(self, capability_registry: AgentCapabilityRegistry) -> None:
        consumers = capability_registry.consumers_of("evidence")
        assert "analysis_agent" in consumers

    def test_unsatisfied_capabilities(self, capability_registry: AgentCapabilityRegistry) -> None:
        unsatisfied = capability_registry.unsatisfied_capabilities(completed_agents=[])
        assert "evidence" in unsatisfied or "analysis_result" in unsatisfied

    def test_unsatisfied_after_completion(
        self, capability_registry: AgentCapabilityRegistry
    ) -> None:
        unsatisfied = capability_registry.unsatisfied_capabilities(
            completed_agents=["retrieval_agent", "analysis_agent"]
        )
        assert "evidence" not in unsatisfied

    def test_dependency_chain(self, capability_registry: AgentCapabilityRegistry) -> None:
        chain = capability_registry.dependency_chain("verification_agent")
        assert len(chain) > 0


# ======================================================================
# Event log tests
# ======================================================================


class TestEventLog:
    def test_append_and_retrieve(self, event_log: InvestigationEventLog) -> None:
        event_log.append(EventType.AGENT_INVOKED, agent_name="test_agent")
        events = event_log.events
        assert len(events) == 1
        assert events[0].event_type == EventType.AGENT_INVOKED
        assert events[0].agent_name == "test_agent"

    def test_filter_by_phase(self, event_log: InvestigationEventLog) -> None:
        event_log.append(EventType.PHASE_CHANGED, phase=InvestigationPhase.PLANNING)
        event_log.append(EventType.AGENT_INVOKED, phase=InvestigationPhase.PLANNING)
        event_log.append(EventType.AGENT_COMPLETED, phase=InvestigationPhase.ANALYSIS)

        planning_events = event_log.filter_by_phase(InvestigationPhase.PLANNING)
        assert len(planning_events) == 2

    def test_filter_by_agent(self, event_log: InvestigationEventLog) -> None:
        event_log.append(EventType.AGENT_INVOKED, agent_name="agent_a")
        event_log.append(EventType.AGENT_COMPLETED, agent_name="agent_a")
        event_log.append(EventType.AGENT_INVOKED, agent_name="agent_b")

        agent_a_events = event_log.filter_by_agent("agent_a")
        assert len(agent_a_events) == 2

    def test_get_recent(self, event_log: InvestigationEventLog) -> None:
        for i in range(5):
            event_log.append(EventType.AGENT_INVOKED, data={"index": i})

        recent = event_log.get_recent(2)
        assert len(recent) == 2

    def test_summary(self, event_log: InvestigationEventLog) -> None:
        event_log.append(EventType.AGENT_INVOKED, agent_name="agent_a")
        event_log.append(EventType.AGENT_COMPLETED, agent_name="agent_a")

        summary = event_log.summary()
        assert summary["total_events"] == 2
        assert "agent_a" in summary["agents_invoked"]

    def test_serialisation(self, event_log: InvestigationEventLog) -> None:
        event_log.append(EventType.AGENT_INVOKED, agent_name="test")
        dicts = event_log.to_dicts()
        assert len(dicts) == 1

        restored = InvestigationEventLog.from_dicts("test_inv", dicts)
        assert restored.length == 1


# ======================================================================
# Checkpoint tests
# ======================================================================


class TestCheckpointManager:
    def test_save_and_load(self, checkpoint_manager: CheckpointManager) -> None:
        state = {"key": "value", "iteration": 5}
        cp = checkpoint_manager.save(state, phase=InvestigationPhase.PLANNING)
        assert cp.metadata.checkpoint_id
        assert cp.metadata.phase == InvestigationPhase.PLANNING

        loaded = checkpoint_manager.load_latest()
        assert loaded is not None
        assert loaded.metadata.checkpoint_id == cp.metadata.checkpoint_id

    def test_restore_state(self, checkpoint_manager: CheckpointManager) -> None:
        original = {"key": "value", "nested": {"a": 1}}
        cp = checkpoint_manager.save(original)

        restored = checkpoint_manager.restore_state(cp)
        assert restored["key"] == "value"
        assert restored["nested"]["a"] == 1

    def test_list_checkpoints(self, checkpoint_manager: CheckpointManager) -> None:
        checkpoint_manager.save({"a": 1})
        checkpoint_manager.save({"b": 2})

        listing = checkpoint_manager.list_checkpoints()
        assert len(listing) == 2

    def test_delete_checkpoint(self, checkpoint_manager: CheckpointManager) -> None:
        cp = checkpoint_manager.save({"a": 1})
        deleted = checkpoint_manager.delete(cp.metadata.checkpoint_id)
        assert deleted is True
        assert checkpoint_manager.count == 0

    def test_clear(self, checkpoint_manager: CheckpointManager) -> None:
        checkpoint_manager.save({"a": 1})
        checkpoint_manager.save({"b": 2})
        count = checkpoint_manager.clear()
        assert count == 2
        assert checkpoint_manager.count == 0


# ======================================================================
# Recovery tests
# ======================================================================


class TestRecovery:
    def test_state_recovery_from_event_log(self) -> None:
        log = InvestigationEventLog("test_inv")
        cp_mgr = CheckpointManager("test_inv")
        recovery = StateRecoveryManager("test_inv", log, cp_mgr)

        log.append(EventType.AGENT_COMPLETED, agent_name="agent_a")
        log.append(EventType.PHASE_CHANGED, data={"phase": "analysis"})
        log.append(EventType.AGENT_FAILED, agent_name="agent_b", data={"error": "timeout"})

        recovered = recovery.recover_from_event_log()
        assert "agent_a" in recovered["completed_agents"]
        assert len(recovered["errors"]) == 1

    def test_recovery_plan(self) -> None:
        log = InvestigationEventLog("test_inv")
        cp_mgr = CheckpointManager("test_inv")
        recovery = StateRecoveryManager("test_inv", log, cp_mgr)

        log.append(EventType.AGENT_FAILED, agent_name="agent_a", data={"error": "fail"})
        cp_mgr.save({"key": "value"})

        plan = recovery.get_recovery_plan()
        assert plan.has_checkpoint is True
        assert "agent_a" in plan.failed_agents
        assert plan.recommended_action == "resume_from_checkpoint"

    def test_failure_recovery(self) -> None:
        fr = FailureRecoveryManager(max_consecutive_failures=3)
        assert fr.should_abort() is False

        fr.record_failure("agent_a", "error 1")
        assert fr.consecutive_failures == 1

        fr.record_failure("agent_a", "error 2")
        fr.record_failure("agent_a", "error 3")
        assert fr.should_abort() is True

        fr.record_success("agent_b")
        assert fr.consecutive_failures == 0

    def test_failure_recovery_agent_tracking(self) -> None:
        fr = FailureRecoveryManager()
        fr.record_failure("agent_a", "error 1")
        fr.record_failure("agent_a", "error 2")
        fr.record_failure("agent_b", "error 3")

        assert fr.get_agent_failure_count("agent_a") == 2
        assert fr.get_agent_failure_count("agent_b") == 1
        assert set(fr.get_failed_agents()) == {"agent_a", "agent_b"}


# ======================================================================
# Retry tests
# ======================================================================


class TestRetry:
    def test_retry_policy_delays(self) -> None:
        policy = RetryPolicy(
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            max_retries=3,
            base_delay_seconds=1.0,
            jitter=False,
        )
        assert policy.get_delay(0) == 0.0
        assert policy.get_delay(1) == 1.0
        assert policy.get_delay(2) == 2.0
        assert policy.get_delay(3) == 4.0

    def test_retry_policy_fixed(self) -> None:
        policy = RetryPolicy(
            strategy=RetryStrategy.FIXED_DELAY,
            base_delay_seconds=2.0,
            jitter=False,
        )
        assert policy.get_delay(1) == 2.0
        assert policy.get_delay(2) == 2.0

    def test_retry_policy_no_retry(self) -> None:
        policy = RetryPolicy(strategy=RetryStrategy.NO_RETRY)
        assert policy.should_retry is False

    def test_retry_policy_max_delay(self) -> None:
        policy = RetryPolicy(
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay_seconds=1.0,
            max_delay_seconds=5.0,
            jitter=False,
        )
        assert policy.get_delay(10) == 5.0

    def test_retry_policy_from_registration(self) -> None:
        reg = AgentRegistration(
            name="test",
            max_retries=5,
            retry_strategy=RetryStrategy.LINEAR_BACKOFF,
        )
        policy = RetryPolicy.from_registration(reg)
        assert policy.max_retries == 5
        assert policy.strategy == RetryStrategy.LINEAR_BACKOFF

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self) -> None:
        call_count = 0

        async def succeed_on_third() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Not yet")
            return "success"

        result, status, attempts = await execute_with_retry(
            succeed_on_third,
            retry_policy=RetryPolicy(
                strategy=RetryStrategy.FIXED_DELAY,
                max_retries=3,
                base_delay_seconds=0.01,
                jitter=False,
            ),
        )
        assert result == "success"
        assert status == AgentStatus.COMPLETED
        assert attempts == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_exhausted(self) -> None:
        async def always_fail() -> str:
            raise ValueError("Always fails")

        result, status, attempts = await execute_with_retry(
            always_fail,
            retry_policy=RetryPolicy(
                strategy=RetryStrategy.FIXED_DELAY,
                max_retries=2,
                base_delay_seconds=0.01,
                jitter=False,
            ),
        )
        assert result is None
        assert status == AgentStatus.FAILED
        assert attempts == 3  # 1 initial + 2 retries


# ======================================================================
# Supervisor tests
# ======================================================================


class TestSupervisor:
    def test_supervisor_initial_dispatch(self, agent_registry: AgentRegistry) -> None:
        cap_reg = AgentCapabilityRegistry(agent_registry)
        supervisor = SupervisorAgent(agent_registry, cap_reg)

        state = create_initial_state("inv_001", "Test query")
        decision = supervisor.decide_next(state)

        assert decision.should_continue is True
        assert len(decision.agents_to_dispatch) > 0
        assert decision.agents_to_dispatch[0] == "retrieval_agent"

    def test_supervisor_after_completion(self, agent_registry: AgentRegistry) -> None:
        cap_reg = AgentCapabilityRegistry(agent_registry)
        supervisor = SupervisorAgent(agent_registry, cap_reg, max_iterations=10)

        state = create_initial_state("inv_001", "Test query")
        state["is_complete"] = True

        decision = supervisor.decide_next(state)
        assert decision.should_continue is False
        assert decision.termination_reason == TerminationReason.SUFFICIENT_EVIDENCE

    def test_supervisor_abstention(self, agent_registry: AgentRegistry) -> None:
        cap_reg = AgentCapabilityRegistry(agent_registry)
        supervisor = SupervisorAgent(agent_registry, cap_reg)

        state = create_initial_state("inv_001", "Test query")
        state["should_abstain"] = True
        state["abstention_reason"] = "Not enough data"

        decision = supervisor.decide_next(state)
        assert decision.should_continue is False
        assert decision.termination_reason == TerminationReason.ABSTENTION

    def test_supervisor_max_iterations(self, agent_registry: AgentRegistry) -> None:
        cap_reg = AgentCapabilityRegistry(agent_registry)
        supervisor = SupervisorAgent(agent_registry, cap_reg, max_iterations=5)

        state = create_initial_state("inv_001", "Test query")
        state["iteration"] = 5

        decision = supervisor.decide_next(state)
        assert decision.should_continue is False
        assert decision.termination_reason == TerminationReason.MAX_ITERATIONS

    def test_supervisor_uses_reflection_when_no_agents(self, agent_registry: AgentRegistry) -> None:
        cap_reg = AgentCapabilityRegistry(agent_registry)
        supervisor = SupervisorAgent(agent_registry, cap_reg)

        state = create_initial_state("inv_001", "Test query")
        state["completed_agents"] = ["retrieval_agent", "analysis_agent", "verification_agent"]
        state["agent_outputs"] = {
            "retrieval_agent": {"confidence": 0.5},
            "analysis_agent": {"confidence": 0.5},
            "verification_agent": {"confidence": 0.5},
        }

        decision = supervisor.decide_next(state)
        # Should go to reflection since all agents are completed
        assert "reflection_agent" in decision.agents_to_dispatch or not decision.should_continue


# ======================================================================
# Reflection tests
# ======================================================================


class TestReflection:
    @pytest.mark.asyncio
    async def test_reflection_on_empty_state(self) -> None:
        agent = ReflectionAgent()
        state = create_initial_state("inv_001", "Test query")

        output = await agent.reflect(state)
        assert isinstance(output, ReflectionOutput)
        assert output.evidence_completeness < 0.5
        assert len(output.identified_gaps) > 0

    @pytest.mark.asyncio
    async def test_reflection_with_evidence(self) -> None:
        agent = ReflectionAgent()
        state = create_initial_state("inv_001", "Test query")
        state["evidence"] = [
            {"text": "evidence 1", "score": 0.9},
            {"text": "evidence 2", "score": 0.8},
            {"text": "evidence 3", "score": 0.7},
        ]
        state["claims"] = [
            {"text": "claim 1", "status": "supported"},
        ]
        state["agent_outputs"] = {
            "retrieval_agent": {"confidence": 0.8},
            "analysis_agent": {"confidence": 0.7},
        }
        state["completed_agents"] = ["retrieval_agent", "analysis_agent"]

        output = await agent.reflect(state)
        assert output.evidence_completeness > 0.5
        assert output.overall_quality > 0.3


# ======================================================================
# Approval tests
# ======================================================================


class TestApproval:
    @pytest.mark.asyncio
    async def test_request_approval(self) -> None:
        node = HumanApprovalNode()
        state = create_initial_state("inv_001", "Test query")

        result = await node.request_approval(
            state,
            summary="High-risk finding detected",
            findings={"risk_level": "high"},
        )

        assert result["approval_required"] is True
        assert result["phase"] == InvestigationPhase.APPROVAL
        assert result["pending_approval_request"] is not None

    @pytest.mark.asyncio
    async def test_approve(self) -> None:
        node = HumanApprovalNode()
        state = create_initial_state("inv_001", "Test query")
        await node.request_approval(state, summary="Test")

        result = await node.process_response(state, decision="approve", reviewer="dr_smith")

        assert result["approval_required"] is False
        assert node.is_approved(result)

    @pytest.mark.asyncio
    async def test_reject(self) -> None:
        node = HumanApprovalNode()
        state = create_initial_state("inv_001", "Test query")
        await node.request_approval(state, summary="Test")

        result = await node.process_response(
            state, decision="reject", reviewer="dr_smith", comments="Unsafe"
        )

        assert result["should_abstain"] is True
        assert node.is_rejected(result)

    @pytest.mark.asyncio
    async def test_request_changes(self) -> None:
        node = HumanApprovalNode()
        state = create_initial_state("inv_001", "Test query")
        await node.request_approval(state, summary="Test")

        result = await node.process_response(state, decision="request_changes", reviewer="dr_smith")

        assert result["phase"] == InvestigationPhase.PLANNING
        assert not node.is_approved(result)
        assert not node.is_rejected(result)


# ======================================================================
# Workflow integration tests
# ======================================================================


class TestWorkflow:
    def test_workflow_compiles(self, agent_registry: AgentRegistry) -> None:
        async def stub_agent(state: dict[str, Any]) -> dict[str, Any]:
            return state

        agent_functions = {
            "retrieval_agent": stub_agent,
            "analysis_agent": stub_agent,
            "verification_agent": stub_agent,
        }

        workflow = create_investigation_workflow(
            agent_registry=agent_registry,
            agent_functions=agent_functions,
            max_iterations=3,
        )
        compiled = workflow.compile()
        assert compiled is not None

    @pytest.mark.asyncio
    async def test_workflow_runs_with_stub_agents(self, agent_registry: AgentRegistry) -> None:
        async def stub_agent(state: dict[str, Any]) -> dict[str, Any]:
            state = dict(state)
            agent_outputs = dict(state.get("agent_outputs", {}))
            agent_outputs[
                state.get("pending_agents", ["unknown"])[0]
                if state.get("pending_agents")
                else "unknown"
            ] = {
                "confidence": 0.8,
                "answer": "stub answer",
            }
            state["agent_outputs"] = agent_outputs
            evidence = list(state.get("evidence", []))
            evidence.append({"text": "stub evidence"})
            state["evidence"] = evidence
            return state

        agent_functions = {
            "retrieval_agent": stub_agent,
            "analysis_agent": stub_agent,
            "verification_agent": stub_agent,
        }

        workflow = create_investigation_workflow(
            agent_registry=agent_registry,
            agent_functions=agent_functions,
            max_iterations=3,
            evidence_confidence_threshold=0.5,
        )
        compiled = workflow.compile()

        initial_state = create_initial_state(
            investigation_id="inv_001",
            query="Test query",
        )

        result = await compiled.ainvoke(initial_state)

        assert result is not None
        assert result.get("is_complete") is True
        assert len(result.get("completed_agents", [])) > 0

    @pytest.mark.asyncio
    async def test_workflow_with_failing_agent(self) -> None:
        reg = AgentRegistry()
        reg.register(
            AgentRegistration(
                name="failing_agent",
                role=AgentRole.ANALYSIS,
                capabilities=[
                    AgentCapability(
                        name="analysis",
                        input_types=[],
                        output_types=["result"],
                    )
                ],
                max_retries=1,
                timeout_seconds=5.0,
            )
        )

        async def failing_agent(state: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("Agent failure simulation")

        workflow = create_investigation_workflow(
            agent_registry=reg,
            agent_functions={"failing_agent": failing_agent},
            max_iterations=2,
        )
        compiled = workflow.compile()

        initial_state = create_initial_state(
            investigation_id="inv_002",
            query="Test query",
        )

        result = await compiled.ainvoke(initial_state)
        assert result is not None
        # The workflow should still complete (with errors)
        assert "errors" in result
