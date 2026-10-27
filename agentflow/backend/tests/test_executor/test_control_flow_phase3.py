"""
Tests for Phase 3 Advanced Control Flow:
- Dynamic conditional branching (multi-path)
- Default fallback edges (is_default=True)
- Feedback loops / cycles (Writer ↔ Reviewer)
- Feedback loop max iteration caps
- Error handler routing (is_error_handler=True)
- Cycle detection (valid feedback loops vs invalid forward cycles)
- Safe condition evaluation with dot notation and builtins
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from agentflow.core.executor.graph import CycleDetectedError, build_execution_graph
from agentflow.core.executor.mapping import evaluate_condition
from agentflow.core.executor.runner import run_workflow
from agentflow.core.schemas.workflow import (
    AgentMessage,
    AgentType,
    EdgeDef,
    JoinPolicy,
    MessageMetadata,
    NodeConfig,
    NodeDef,
    NodeRunStatus,
    RetryPolicy,
    RunStatus,
    WorkflowDef,
)


def make_msg(node_id: str, run_id: Any, data: dict) -> AgentMessage:
    return AgentMessage(
        run_id=run_id,
        node_id=node_id,
        status=NodeRunStatus.COMPLETED,
        data=data,
        metadata=MessageMetadata(
            prompt_tokens=50,
            completion_tokens=25,
            total_tokens=75,
            cost_usd=0.0005,
            model="mock-model",
        ),
    )


class TestCycleDetection:
    def test_intentional_feedback_loop_does_not_raise_cycle_error(self) -> None:
        """Back-edges marked with is_feedback=True should be ignored by DAG check."""
        node_a = NodeDef(id="writer", type=AgentType.WRITER, label="Writer")
        node_b = NodeDef(id="reviewer", type=AgentType.REVIEWER, label="Reviewer")

        forward_edge = EdgeDef(id="e1", source="writer", target="reviewer")
        feedback_edge = EdgeDef(
            id="e2",
            source="reviewer",
            target="writer",
            is_feedback=True,
            condition="not output.passed",
        )

        wf = WorkflowDef(
            id=uuid4(),
            nodes=[node_a, node_b],
            edges=[forward_edge, feedback_edge],
        )

        graph = build_execution_graph(wf)
        assert len(graph.layers) == 2
        assert graph.layers[0] == ["writer"]
        assert graph.layers[1] == ["reviewer"]
        assert len(graph.feedback_edges) == 1
        assert graph.feedback_edges[0].id == "e2"

    def test_unmarked_cycle_raises_cycle_detected_error(self) -> None:
        """Cycles without is_feedback=True must raise CycleDetectedError."""
        node_a = NodeDef(id="a", type=AgentType.WRITER, label="A")
        node_b = NodeDef(id="b", type=AgentType.REVIEWER, label="B")

        edge_ab = EdgeDef(id="e1", source="a", target="b")
        edge_ba = EdgeDef(id="e2", source="b", target="a", is_feedback=False)

        wf = WorkflowDef(id=uuid4(), nodes=[node_a, node_b], edges=[edge_ab, edge_ba])

        with pytest.raises(CycleDetectedError):
            build_execution_graph(wf)


class TestEnhancedConditionEvaluation:
    def test_dot_notation_attribute_access(self) -> None:
        output = {"score": 9.5, "passed": True, "details": {"tier": "gold"}}
        assert evaluate_condition("output.score >= 9", output) is True
        assert evaluate_condition("output.passed == True", output) is True
        assert evaluate_condition("output.details.tier == 'gold'", output) is True

    def test_unpacked_identifiers(self) -> None:
        output = {"score": 8, "passed": False}
        assert evaluate_condition("score >= 7", output) is True
        assert evaluate_condition("not passed", output) is True
        assert evaluate_condition("passed", output) is False

    def test_safe_builtins(self) -> None:
        output = {"tags": ["saas", "enterprise", "cloud"], "val": -15}
        assert evaluate_condition("len(tags) == 3", output) is True
        assert evaluate_condition("abs(val) == 15", output) is True
        assert evaluate_condition("'saas' in tags", output) is True

    def test_unparseable_condition_returns_false_safely(self) -> None:
        output = {"score": 10}
        assert evaluate_condition("output.nonexistent.something[999]", output) is False
        assert evaluate_condition("syntax error !!!", output) is False


class TestConditionalBranchingAndDefault:
    @pytest.mark.asyncio
    async def test_multi_path_branching_takes_matching_branch(self) -> None:
        """Router branches: score >= 7 -> writer, score < 7 -> disqualified."""
        trigger = NodeDef(id="trigger", type=AgentType.TRIGGER_MANUAL, label="Trigger")
        router = NodeDef(id="router", type=AgentType.ROUTER, label="Router")
        writer = NodeDef(id="writer", type=AgentType.WRITER, label="Writer")
        disqualified = NodeDef(id="disqualified", type=AgentType.WRITER, label="Disqualified")

        edges = [
            EdgeDef(id="e_tr", source="trigger", target="router"),
            EdgeDef(id="e_rw", source="router", target="writer", condition="score >= 7"),
            EdgeDef(id="e_rd", source="router", target="disqualified", condition="score < 7"),
        ]

        wf = WorkflowDef(id=uuid4(), nodes=[trigger, router, writer, disqualified], edges=edges)

        executed_nodes: list[str] = []

        async def fake_run(input_data, config, context, tools):
            node_id = context.current_node_id
            executed_nodes.append(node_id)
            if node_id == "router":
                return make_msg(node_id, context.run.id, {"score": 9})
            return make_msg(node_id, context.run.id, {"done": True})

        mock_agent = AsyncMock()
        mock_agent.run.side_effect = fake_run

        with patch("agentflow.core.executor.node_runner.agent_registry.get", return_value=mock_agent):
            run = await run_workflow(wf, trigger_data={})

        assert run.status == RunStatus.COMPLETED
        assert "writer" in executed_nodes
        assert "disqualified" not in executed_nodes

    @pytest.mark.asyncio
    async def test_default_fallback_edge_taken_when_no_conditions_match(self) -> None:
        """When no explicit conditions match, edge with is_default=True is taken."""
        trigger = NodeDef(id="trigger", type=AgentType.TRIGGER_MANUAL, label="Trigger")
        router = NodeDef(id="router", type=AgentType.ROUTER, label="Router")
        vip_path = NodeDef(id="vip", type=AgentType.WRITER, label="VIP")
        default_path = NodeDef(id="default", type=AgentType.WRITER, label="Default")

        edges = [
            EdgeDef(id="e_tr", source="trigger", target="router"),
            EdgeDef(id="e_vip", source="router", target="vip", condition="category == 'vip'"),
            EdgeDef(id="e_def", source="router", target="default", is_default=True),
        ]

        wf = WorkflowDef(id=uuid4(), nodes=[trigger, router, vip_path, default_path], edges=edges)

        executed_nodes: list[str] = []

        async def fake_run(input_data, config, context, tools):
            node_id = context.current_node_id
            executed_nodes.append(node_id)
            if node_id == "router":
                return make_msg(node_id, context.run.id, {"category": "standard"})
            return make_msg(node_id, context.run.id, {"done": True})

        mock_agent = AsyncMock()
        mock_agent.run.side_effect = fake_run

        with patch("agentflow.core.executor.node_runner.agent_registry.get", return_value=mock_agent):
            run = await run_workflow(wf, trigger_data={})

        assert run.status == RunStatus.COMPLETED
        assert "vip" not in executed_nodes
        assert "default" in executed_nodes

    @pytest.mark.asyncio
    async def test_diamond_branching_with_dead_path_elimination(self) -> None:
        """
        Trigger -> Router -> Branch B (score >= 7) \
                          -> Branch C (score < 7)   -> Join Node D
        When score=9: B executes, C is skipped.
        Node D must NOT deadlock; D executes once B completes!
        """
        trigger = NodeDef(id="trigger", type=AgentType.TRIGGER_MANUAL, label="Trigger")
        router = NodeDef(id="router", type=AgentType.ROUTER, label="Router")
        branch_b = NodeDef(id="b", type=AgentType.WRITER, label="Qualified B")
        branch_c = NodeDef(id="c", type=AgentType.WRITER, label="Disqualified C")
        join_d = NodeDef(id="d", type=AgentType.EMAIL, label="Merge D")

        edges = [
            EdgeDef(id="e_tr", source="trigger", target="router"),
            EdgeDef(id="e_rb", source="router", target="b", condition="score >= 7"),
            EdgeDef(id="e_rc", source="router", target="c", condition="score < 7"),
            EdgeDef(id="e_bd", source="b", target="d"),
            EdgeDef(id="e_cd", source="c", target="d"),
        ]

        wf = WorkflowDef(id=uuid4(), nodes=[trigger, router, branch_b, branch_c, join_d], edges=edges)

        executed_nodes: list[str] = []

        async def fake_run(input_data, config, context, tools):
            node_id = context.current_node_id
            executed_nodes.append(node_id)
            if node_id == "router":
                return make_msg(node_id, context.run.id, {"score": 9})
            return make_msg(node_id, context.run.id, {"node": node_id})

        mock_agent = AsyncMock()
        mock_agent.run.side_effect = fake_run

        with patch("agentflow.core.executor.node_runner.agent_registry.get", return_value=mock_agent):
            run = await run_workflow(wf, trigger_data={})

        assert run.status == RunStatus.COMPLETED
        assert "b" in executed_nodes
        assert "c" not in executed_nodes
        assert "d" in executed_nodes

    @pytest.mark.asyncio
    async def test_join_policy_wait_any_triggers_on_first_completed(self) -> None:
        """Node with join_policy=WAIT_ANY triggers as soon as one branch completes."""
        trigger = NodeDef(id="trigger", type=AgentType.TRIGGER_MANUAL, label="Trigger")
        branch_1 = NodeDef(id="b1", type=AgentType.WRITER, label="Branch 1")
        branch_2 = NodeDef(id="b2", type=AgentType.WRITER, label="Branch 2")
        join_node = NodeDef(
            id="join",
            type=AgentType.EMAIL,
            label="Join Node",
            config=NodeConfig(join_policy=JoinPolicy.WAIT_ANY),
        )

        edges = [
            EdgeDef(id="e_t1", source="trigger", target="b1"),
            EdgeDef(id="e_t2", source="trigger", target="b2"),
            EdgeDef(id="e_1j", source="b1", target="join"),
            EdgeDef(id="e_2j", source="b2", target="join"),
        ]

        wf = WorkflowDef(id=uuid4(), nodes=[trigger, branch_1, branch_2, join_node], edges=edges)

        executed_nodes: list[str] = []

        async def fake_run(input_data, config, context, tools):
            node_id = context.current_node_id
            executed_nodes.append(node_id)
            return make_msg(node_id, context.run.id, {"from": node_id})

        mock_agent = AsyncMock()
        mock_agent.run.side_effect = fake_run

        with patch("agentflow.core.executor.node_runner.agent_registry.get", return_value=mock_agent):
            run = await run_workflow(wf, trigger_data={})

        assert run.status == RunStatus.COMPLETED
        assert "join" in executed_nodes


class TestFeedbackLoop:
    @pytest.mark.asyncio
    async def test_writer_reviewer_feedback_loop_succeeds_on_iteration_2(self) -> None:
        """
        Writer drafts email -> Reviewer rejects on round 1 with feedback ->
        Writer re-runs with feedback -> Reviewer approves on round 2 ->
        Email node executes!
        """
        trigger = NodeDef(id="trigger", type=AgentType.TRIGGER_MANUAL, label="Trigger")
        writer = NodeDef(id="writer", type=AgentType.WRITER, label="Writer")
        reviewer = NodeDef(id="reviewer", type=AgentType.REVIEWER, label="Reviewer")
        email = NodeDef(id="email", type=AgentType.EMAIL, label="Email Sender")

        edges = [
            EdgeDef(id="e_tw", source="trigger", target="writer"),
            EdgeDef(
                id="e_wr",
                source="writer",
                target="reviewer",
                data_map={"body": "{{writer.output.body}}"},
            ),
            # Feedback back-edge to writer:
            EdgeDef(
                id="e_rw_feedback",
                source="reviewer",
                target="writer",
                is_feedback=True,
                condition="not output.passed",
                data_map={"feedback": "{{reviewer.output.feedback}}"},
            ),
            # Forward edge to email once approved:
            EdgeDef(
                id="e_re_forward",
                source="reviewer",
                target="email",
                condition="output.passed",
            ),
        ]

        wf = WorkflowDef(id=uuid4(), nodes=[trigger, writer, reviewer, email], edges=edges)

        writer_calls = 0
        reviewer_calls = 0
        email_called = False
        writer_received_feedbacks = []

        async def fake_run(input_data, config, context, tools):
            nonlocal writer_calls, reviewer_calls, email_called
            node_id = context.current_node_id

            if node_id == "writer":
                writer_calls += 1
                feedback = input_data.get("feedback")
                writer_received_feedbacks.append(feedback)
                return make_msg(node_id, context.run.id, {
                    "body": f"Draft iteration {writer_calls}",
                })

            if node_id == "reviewer":
                reviewer_calls += 1
                if reviewer_calls == 1:
                    # Round 1: Reject with feedback
                    return make_msg(node_id, context.run.id, {
                        "score": 5,
                        "passed": False,
                        "feedback": "Needs specific customer case study metrics.",
                    })
                # Round 2: Approve
                return make_msg(node_id, context.run.id, {
                    "score": 9,
                    "passed": True,
                    "feedback": "Great draft.",
                })

            if node_id == "email":
                email_called = True
                return make_msg(node_id, context.run.id, {"sent": True})

            return make_msg(node_id, context.run.id, {})

        mock_agent = AsyncMock()
        mock_agent.run.side_effect = fake_run

        with patch("agentflow.core.executor.node_runner.agent_registry.get", return_value=mock_agent):
            run = await run_workflow(wf, trigger_data={})

        assert run.status == RunStatus.COMPLETED
        assert writer_calls == 2
        assert reviewer_calls == 2
        assert email_called is True
        # Verify iteration 1 had no feedback, but iteration 2 received the feedback from reviewer
        assert writer_received_feedbacks[0] is None
        assert writer_received_feedbacks[1] == "Needs specific customer case study metrics."

    @pytest.mark.asyncio
    async def test_feedback_loop_stops_at_max_iterations(self) -> None:
        """When reviewer persistently rejects, loop must stop after max_iterations."""
        trigger = NodeDef(id="trigger", type=AgentType.TRIGGER_MANUAL, label="Trigger")
        writer = NodeDef(
            id="writer",
            type=AgentType.WRITER,
            label="Writer",
            config=NodeConfig(max_loop_iterations=2),
        )
        reviewer = NodeDef(id="reviewer", type=AgentType.REVIEWER, label="Reviewer")

        edges = [
            EdgeDef(id="e_tw", source="trigger", target="writer"),
            EdgeDef(id="e_wr", source="writer", target="reviewer"),
            EdgeDef(
                id="e_rw_feedback",
                source="reviewer",
                target="writer",
                is_feedback=True,
                condition="not output.passed",
                max_iterations=2,
            ),
        ]

        wf = WorkflowDef(id=uuid4(), nodes=[trigger, writer, reviewer], edges=edges)

        writer_calls = 0

        async def fake_run(input_data, config, context, tools):
            nonlocal writer_calls
            node_id = context.current_node_id
            if node_id == "writer":
                writer_calls += 1
                return make_msg(node_id, context.run.id, {"draft": writer_calls})
            if node_id == "reviewer":
                # Always reject
                return make_msg(node_id, context.run.id, {"score": 4, "passed": False})
            return make_msg(node_id, context.run.id, {})

        mock_agent = AsyncMock()
        mock_agent.run.side_effect = fake_run

        with patch("agentflow.core.executor.node_runner.agent_registry.get", return_value=mock_agent):
            run = await run_workflow(wf, trigger_data={})

        # Run terminates after reaching loop iteration limit (2 calls to writer)
        assert writer_calls == 2
        assert run.status == RunStatus.COMPLETED


class TestErrorHandlerRouting:
    @pytest.mark.asyncio
    async def test_error_handler_edge_routed_on_node_failure(self) -> None:
        """When a node fails execution, edge with is_error_handler=True is routed."""
        trigger = NodeDef(id="trigger", type=AgentType.TRIGGER_MANUAL, label="Trigger")
        fragile_node = NodeDef(
            id="fragile",
            type=AgentType.RESEARCH,
            label="Fragile Node",
            config=NodeConfig(retry_policy=RetryPolicy(max_attempts=1)),
        )
        recovery_node = NodeDef(
            id="recovery",
            type=AgentType.WRITER,
            label="Recovery Node",
        )

        edges = [
            EdgeDef(id="e_tf", source="trigger", target="fragile"),
            EdgeDef(
                id="e_fr_err",
                source="fragile",
                target="recovery",
                is_error_handler=True,
            ),
        ]

        wf = WorkflowDef(id=uuid4(), nodes=[trigger, fragile_node, recovery_node], edges=edges)

        recovery_executed = False

        async def fake_run(input_data, config, context, tools):
            nonlocal recovery_executed
            node_id = context.current_node_id
            if node_id == "fragile":
                raise RuntimeError("Service unavailable")
            if node_id == "recovery":
                recovery_executed = True
                return make_msg(node_id, context.run.id, {"recovered": True})
            return make_msg(node_id, context.run.id, {})

        mock_agent = AsyncMock()
        mock_agent.run.side_effect = fake_run

        with patch("agentflow.core.executor.node_runner.agent_registry.get", return_value=mock_agent):
            run = await run_workflow(wf, trigger_data={})

        assert run.status == RunStatus.COMPLETED
        assert recovery_executed is True
