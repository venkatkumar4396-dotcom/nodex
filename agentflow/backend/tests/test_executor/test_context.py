"""Tests for RunContext — shared run state and lifecycle management."""
from __future__ import annotations

import pytest

from agentflow.core.executor.context import (
    CostLimitExceeded,
    RunContext,
    StepLimitExceeded,
)
from agentflow.core.schemas.workflow import (
    AgentMessage,
    AgentType,
    MessageMetadata,
    NodeRunRecord,
    NodeRunStatus,
    RunRecord,
    RunStatus,
    WorkflowDef,
)


@pytest.fixture
def ctx(simple_linear_workflow: WorkflowDef) -> RunContext:
    run = RunRecord(
        workflow_id=simple_linear_workflow.id,
        workflow_version=1,
    )
    return RunContext(run=run, workflow=simple_linear_workflow)


class TestRunContext:
    def test_record_and_get_node_output(self, ctx: RunContext) -> None:
        ctx.record_node_output("research", {"summary": "test", "score": 0.9})
        result = ctx.get_node_output("research")
        assert result == {"summary": "test", "score": 0.9}

    def test_get_missing_node_output(self, ctx: RunContext) -> None:
        assert ctx.get_node_output("nonexistent") is None

    def test_shared_context_set_get(self, ctx: RunContext) -> None:
        ctx.set_shared("key", "value")
        assert ctx.get_shared("key") == "value"
        assert ctx.get_shared("missing", "default") == "default"

    def test_cost_accumulation(self, ctx: RunContext) -> None:
        ctx.add_cost(0.01)
        ctx.add_cost(0.02)
        assert abs(ctx.run.total_cost_usd - 0.03) < 1e-9

    def test_token_accumulation(self, ctx: RunContext) -> None:
        ctx.add_tokens(100, 50)
        ctx.add_tokens(200, 100)
        assert ctx.run.total_tokens == 450

    def test_step_limit_exceeded(self, ctx: RunContext) -> None:
        ctx.workflow.global_max_steps = 2
        ctx.increment_step()
        ctx.increment_step()
        with pytest.raises(StepLimitExceeded):
            ctx.increment_step()

    def test_cost_limit_not_exceeded_initially(self, ctx: RunContext) -> None:
        ctx.workflow.global_max_cost_usd = 1.0
        ctx.add_cost(0.5)
        ctx.check_cost_limit()  # should not raise

    def test_cost_limit_exceeded(self, ctx: RunContext) -> None:
        ctx.workflow.global_max_cost_usd = 0.01
        ctx.add_cost(1.0)
        with pytest.raises(CostLimitExceeded):
            ctx.check_cost_limit()

    def test_no_cost_limit(self, ctx: RunContext) -> None:
        ctx.workflow.global_max_cost_usd = None
        ctx.add_cost(999.0)
        ctx.check_cost_limit()  # should not raise

    def test_loop_counter(self, ctx: RunContext) -> None:
        assert ctx.get_loop_count("edge_1") == 0
        ctx.increment_loop("edge_1")
        assert ctx.get_loop_count("edge_1") == 1
        ctx.increment_loop("edge_1")
        assert ctx.get_loop_count("edge_1") == 2

    def test_finish_node_run_updates_totals(self, ctx: RunContext) -> None:
        node_run = NodeRunRecord(
            run_id=ctx.run.id,
            node_id="research",
            agent_type=AgentType.RESEARCH,
        )
        ctx.start_node_run(node_run)

        message = AgentMessage(
            run_id=ctx.run.id,
            node_id="research",
            status=NodeRunStatus.COMPLETED,
            data={"result": "done"},
            metadata=MessageMetadata(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                cost_usd=0.002,
                model="gpt-4o-mini",
            ),
        )
        ctx.finish_node_run(node_run, message)

        assert ctx.run.total_tokens == 150
        assert abs(ctx.run.total_cost_usd - 0.002) < 1e-9
        assert ctx.get_node_output("research") == {"result": "done"}
        assert node_run.status == NodeRunStatus.COMPLETED

    def test_finalize_run(self, ctx: RunContext) -> None:
        ctx.finalize_run(RunStatus.COMPLETED)
        assert ctx.run.status == RunStatus.COMPLETED
        assert ctx.run.completed_at is not None
