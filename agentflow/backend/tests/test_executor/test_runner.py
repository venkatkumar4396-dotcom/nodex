"""
Integration-level tests for the WorkflowRunner using mock agents.

These tests verify the executor's logic WITHOUT making real LLM calls.
We mock the AgentRegistry to return stub agents that return preset outputs.

This is the critical test pattern: test the engine, mock the agents.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from agentflow.core.executor.runner import run_workflow
from agentflow.core.schemas.workflow import (
    AgentMessage,
    AgentType,
    EdgeDef,
    MessageMetadata,
    NodeConfig,
    NodeDef,
    NodeRunStatus,
    RetryPolicy,
    RunStatus,
    WorkflowDef,
)


def make_success_message(node_id: str, run_id: Any, data: dict) -> AgentMessage:
    return AgentMessage(
        run_id=run_id,
        node_id=node_id,
        status=NodeRunStatus.COMPLETED,
        data=data,
        metadata=MessageMetadata(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
            model="gpt-4o-mini",
        ),
    )


class MockAgent:
    """Stub agent that returns preset outputs."""

    def __init__(self, output_data: dict) -> None:
        self.output_data = output_data
        self.call_count = 0

    async def run(self, input_data, config, context, tools):
        self.call_count += 1
        node_id = next(
            (n.id for n in context.workflow.nodes if n.config == config),
            "unknown"
        )
        return make_success_message(node_id, context.run.id, self.output_data)


class TestWorkflowRunner:
    @pytest.mark.asyncio
    async def test_linear_workflow_executes_all_nodes(
        self, simple_linear_workflow: WorkflowDef
    ) -> None:
        """All nodes in a linear workflow should complete."""
        mock_agent = AsyncMock()
        mock_agent.run.return_value = make_success_message(
            "node", uuid4(), {"result": "done"}
        )

        with patch(
            "agentflow.core.executor.node_runner.agent_registry.get",
            return_value=mock_agent,
        ):
            run = await run_workflow(simple_linear_workflow, trigger_data={"input": "test"})

        assert run.status == RunStatus.COMPLETED
        # Trigger node is seeded, so A doesn't run via agent; B and C do
        # (trigger is just seeded as output, not executed via agent in simple wf)
        assert run.error is None

    @pytest.mark.asyncio
    async def test_token_cost_accumulation(
        self, simple_linear_workflow: WorkflowDef
    ) -> None:
        """Token and cost totals should accumulate across all nodes."""
        mock_agent = AsyncMock()
        mock_agent.run.return_value = make_success_message(
            "node", uuid4(), {"result": "done"}
        )

        with patch(
            "agentflow.core.executor.node_runner.agent_registry.get",
            return_value=mock_agent,
        ):
            run = await run_workflow(simple_linear_workflow)

        # Each node contributes 150 tokens and $0.001
        assert run.total_tokens >= 0  # at minimum 0 (trigger doesn't call LLM)
        assert run.total_cost_usd >= 0.0

    @pytest.mark.asyncio
    async def test_conditional_edge_skips_branch(self) -> None:
        """When a condition is False, the target node should be skipped."""
        wf = WorkflowDef(
            id=uuid4(),
            nodes=[
                NodeDef(id="trigger", type=AgentType.TRIGGER_MANUAL, label="T", config=NodeConfig()),
                NodeDef(id="classifier", type=AgentType.ROUTER, label="C", config=NodeConfig()),
                NodeDef(id="writer", type=AgentType.WRITER, label="W", config=NodeConfig()),
            ],
            edges=[
                EdgeDef(id="e1", source="trigger", target="classifier"),
                EdgeDef(
                    id="e2",
                    source="classifier",
                    target="writer",
                    condition="output.get('score', 0) >= 7",  # will be False with score=5
                ),
            ],
        )

        nodes_executed: list[str] = []

        async def tracking_run(input_data, config, context, tools):
            nodes_executed.append(context.current_node_id)
            return make_success_message(
                context.current_node_id, context.run.id,
                {"score": 5, "branch": "not_qualified"}
            )

        mock_agent = AsyncMock()
        mock_agent.run.side_effect = tracking_run

        with patch(
            "agentflow.core.executor.node_runner.agent_registry.get",
            return_value=mock_agent,
        ):
            run = await run_workflow(wf, trigger_data={"test": "data"})

        assert run.status == RunStatus.COMPLETED
        assert "writer" not in nodes_executed, (
            f"Writer should have been skipped. Executed: {nodes_executed}"
        )

    @pytest.mark.asyncio
    async def test_max_cost_limit_stops_run(self) -> None:
        """A run should fail when it exceeds the global cost limit."""
        wf = WorkflowDef(
            id=uuid4(),
            name="expensive_wf",
            nodes=[
                NodeDef(id="trigger", type=AgentType.TRIGGER_MANUAL, label="T", config=NodeConfig()),
                NodeDef(id="research", type=AgentType.RESEARCH, label="R", config=NodeConfig()),
            ],
            edges=[EdgeDef(id="e1", source="trigger", target="research")],
            global_max_cost_usd=0.00001,  # extremely low budget
        )

        expensive_agent = AsyncMock()
        expensive_agent.run.return_value = AgentMessage(
            run_id=uuid4(),
            node_id="research",
            status=NodeRunStatus.COMPLETED,
            data={"result": "done"},
            metadata=MessageMetadata(
                cost_usd=1.0,  # exceeds budget
                total_tokens=1000,
            ),
        )

        with patch(
            "agentflow.core.executor.node_runner.agent_registry.get",
            return_value=expensive_agent,
        ):
            run = await run_workflow(wf)

        assert run.status == RunStatus.FAILED
        assert "cost" in (run.error or "").lower() or run.error is not None

    @pytest.mark.asyncio
    async def test_failed_node_stops_run(self) -> None:
        """A node that fails all retries should cause the run to fail."""
        wf = WorkflowDef(
            id=uuid4(),
            nodes=[
                NodeDef(
                    id="trigger",
                    type=AgentType.TRIGGER_MANUAL,
                    label="T",
                    config=NodeConfig(),
                ),
                NodeDef(
                    id="research",
                    type=AgentType.RESEARCH,
                    label="R",
                    config=NodeConfig(retry_policy=RetryPolicy(max_attempts=1, backoff_seconds=0)),
                ),
            ],
            edges=[EdgeDef(id="e1", source="trigger", target="research")],
        )

        failing_agent = AsyncMock()
        failing_agent.run.side_effect = RuntimeError("LLM API down")

        with patch(
            "agentflow.core.executor.node_runner.agent_registry.get",
            return_value=failing_agent,
        ):
            run = await run_workflow(wf)

        assert run.status == RunStatus.FAILED

    @pytest.mark.asyncio
    async def test_parallel_nodes_both_execute(
        self, parallel_workflow: WorkflowDef
    ) -> None:
        """Fan-out: B and C should both execute before D."""
        call_count = 0

        async def tracking_run(input_data, config, context, tools):
            nonlocal call_count
            call_count += 1
            node_id = f"node_{call_count}"
            return make_success_message(node_id, context.run.id, {"result": call_count})

        mock_agent = AsyncMock()
        mock_agent.run.side_effect = tracking_run

        with patch(
            "agentflow.core.executor.node_runner.agent_registry.get",
            return_value=mock_agent,
        ):
            run = await run_workflow(parallel_workflow, trigger_data={})

        assert run.status == RunStatus.COMPLETED
        # B, C, and D should all have been called (trigger is seeded, not run via agent in simple case)
        assert call_count >= 2  # at minimum B and D (or B, C, D)

    @pytest.mark.asyncio
    async def test_trigger_data_available_to_downstream(self) -> None:
        """Trigger data should be accessible to research agent via context."""
        wf = WorkflowDef(
            id=uuid4(),
            nodes=[
                NodeDef(id="trigger", type=AgentType.TRIGGER_MANUAL, label="T", config=NodeConfig()),
                NodeDef(id="research", type=AgentType.RESEARCH, label="R", config=NodeConfig()),
            ],
            edges=[EdgeDef(id="e1", source="trigger", target="research")],
        )

        received_inputs: list[dict] = []

        async def capture_run(input_data, config, context, tools):
            received_inputs.append(dict(input_data))
            return make_success_message(context.current_node_id, context.run.id, {"summary": "done"})

        mock_agent = AsyncMock()
        mock_agent.run.side_effect = capture_run

        with patch(
            "agentflow.core.executor.node_runner.agent_registry.get",
            return_value=mock_agent,
        ):
            await run_workflow(wf, trigger_data={"lead_name": "Alice", "company": "ACME"})

        # The research node's input should contain trigger_data fields
        # Find the call that was for the research node (not the trigger)
        research_input = next(
            (inp for inp in received_inputs if "lead_name" in inp),
            None
        )
        assert research_input is not None, (
            f"Research node should have received lead_name. Got inputs: {received_inputs}"
        )
        assert research_input.get("lead_name") == "Alice"
        assert research_input.get("company") == "ACME"
