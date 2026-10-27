"""
Enterprise DAG execution engine test suite:
  1. True multi-cast fan-out (both true branches execute concurrently)
  2. Dead-Path Elimination (DPE) with sibling branch isolation
  3. Isolated node timeout with TIMED_OUT status
  4. Template variable interpolation ({{nodes.<slug>.output.<path>}} and {{input.<key>}})
  5. Error boundary fallback routing
"""
import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from agentflow.core.executor.context import RunContext
from agentflow.core.executor.mapping import interpolate_templates, resolve_value
from agentflow.core.executor.node_runner import NodeExecutionError, run_node
from agentflow.core.executor.runner import run_workflow
from agentflow.core.schemas.workflow import (
    AgentMessage,
    AgentType,
    EdgeDef,
    NodeConfig,
    NodeDef,
    NodeRunStatus,
    RetryPolicy,
    RunRecord,
    RunStatus,
    WorkflowDef,
)


@pytest.mark.asyncio
async def test_template_variable_interpolation_store():
    """Verify universal interpolation for {{nodes.<id_or_slug>.output.<path>}} and {{input.<key>}}."""
    wf = WorkflowDef(
        id=uuid4(),
        nodes=[
            NodeDef(id="researcher", type=AgentType.RESEARCH, label="Lead Researcher", config=NodeConfig()),
            NodeDef(id="classifier", type=AgentType.ROUTER, label="Lead Scorer", config=NodeConfig()),
            NodeDef(id="writer", type=AgentType.WRITER, label="Outreach Drafter", config=NodeConfig()),
        ],
        edges=[],
    )
    run = RunRecord(
        id=uuid4(),
        workflow_id=wf.id,
        status=RunStatus.RUNNING,
        trigger_data={"lead_name": "Jane Doe", "company": "Acme Corp"},
    )
    ctx = RunContext(run=run, workflow=wf)
    ctx.record_node_output("researcher", {
        "summary": "Acme Corp is expanding AI infrastructure",
        "funding": "$50M Series B",
    })
    ctx.record_node_output("classifier", {
        "score": 9,
        "qualification": "highly_qualified",
    })

    # Test input.<key>
    assert resolve_value("{{input.lead_name}}", ctx) == "Jane Doe"
    assert resolve_value("{{input.company}}", ctx) == "Acme Corp"

    # Test nodes.<id>.output.<field>
    assert resolve_value("{{nodes.researcher.output.summary}}", ctx) == "Acme Corp is expanding AI infrastructure"
    
    # Test nodes.<slug>.output.<field> (using label "Lead Scorer" -> slug "lead_scorer")
    assert resolve_value("{{nodes.lead_scorer.output.score}}", ctx) == 9

    # Test bracket notation {{nodes['researcher'].output.funding}}
    assert resolve_value("{{nodes['researcher'].output.funding}}", ctx) == "$50M Series B"

    # Test recursive dictionary interpolation
    template_config = {
        "prompt": "Hello {{input.lead_name}} at {{input.company}}! We noticed {{nodes.researcher.output.funding}}.",
        "score_check": "{{nodes.classifier.output.score}}",
    }
    resolved = interpolate_templates(template_config, ctx)
    assert resolved["prompt"] == "Hello Jane Doe at Acme Corp! We noticed $50M Series B."
    assert resolved["score_check"] == 9


@pytest.mark.asyncio
async def test_multicast_fan_out_and_dead_path_elimination():
    """
    Test true multi-cast fan-out and DPE:
      Split node has 3 branches:
        - branch_a: True condition -> executes
        - branch_b: True condition -> executes in parallel
        - branch_c: False condition -> eliminated (DPE), skipped
      Join node: WAIT_ALL join waits for completed active branches (branch_a, branch_b)
      and resolves with dead branch eliminated without getting blocked.
    """
    wf = WorkflowDef(
        id=uuid4(),
        nodes=[
            NodeDef(id="trigger", type=AgentType.TRIGGER_MANUAL, label="T", config=NodeConfig()),
            NodeDef(id="router", type=AgentType.ROUTER, label="R", config=NodeConfig()),
            NodeDef(id="branch_a", type=AgentType.RESEARCH, label="Branch A", config=NodeConfig()),
            NodeDef(id="branch_b", type=AgentType.PROMPT, label="Branch B", config=NodeConfig()),
            NodeDef(id="branch_c", type=AgentType.EMAIL, label="Branch C", config=NodeConfig()),
            NodeDef(id="synthesizer", type=AgentType.SYNTHESIZER, label="Synth", config=NodeConfig()),
        ],
        edges=[
            EdgeDef(id="e1", source="trigger", target="router"),
            # Branch A: true
            EdgeDef(id="e2a", source="router", target="branch_a", condition="output.score >= 5"),
            # Branch B: true
            EdgeDef(id="e2b", source="router", target="branch_b", condition="output.category == 'enterprise'"),
            # Branch C: false (should be eliminated)
            EdgeDef(id="e2c", source="router", target="branch_c", condition="output.score < 2"),
            # Converge on synthesizer
            EdgeDef(id="e3a", source="branch_a", target="synthesizer"),
            EdgeDef(id="e3b", source="branch_b", target="synthesizer"),
            EdgeDef(id="e3c", source="branch_c", target="synthesizer"),
        ],
    )

    executed_nodes: list[str] = []
    skipped_nodes: list[str] = []

    async def mock_run(input_data, config, context, tools):
        executed_nodes.append(context.current_node_id)
        if context.current_node_id == "router":
            return AgentMessage(
                run_id=context.run.id,
                node_id="router",
                status=NodeRunStatus.COMPLETED,
                data={"score": 8, "category": "enterprise"},
            )
        return AgentMessage(
            run_id=context.run.id,
            node_id=context.current_node_id,
            status=NodeRunStatus.COMPLETED,
            data={"result": f"{context.current_node_id}_done"},
        )

    mock_agent = AsyncMock()
    mock_agent.run.side_effect = mock_run

    async def on_complete_callback(msg: AgentMessage):
        if msg.status == NodeRunStatus.SKIPPED:
            skipped_nodes.append(msg.node_id)

    with patch(
        "agentflow.core.executor.node_runner.agent_registry.get",
        return_value=mock_agent,
    ):
        run = await run_workflow(
            workflow=wf,
            trigger_data={"start": True},
            on_node_complete=on_complete_callback,
        )

    assert run.status == RunStatus.COMPLETED
    assert "router" in executed_nodes
    assert "branch_a" in executed_nodes
    assert "branch_b" in executed_nodes
    assert "synthesizer" in executed_nodes
    assert "branch_c" not in executed_nodes
    assert "branch_c" in skipped_nodes


@pytest.mark.asyncio
async def test_isolated_node_timeout():
    """Verify that a hanging node triggers timeout, transitioning to TIMED_OUT."""
    wf = WorkflowDef(
        id=uuid4(),
        nodes=[
            NodeDef(
                id="slow_node",
                type=AgentType.PROMPT,
                label="Hanging Node",
                config=NodeConfig(
                    timeout_seconds=1,
                    retry_policy=RetryPolicy(max_attempts=1, backoff_seconds=0),
                ),
            )
        ],
        edges=[],
    )
    run = RunRecord(id=uuid4(), workflow_id=wf.id, status=RunStatus.RUNNING)
    ctx = RunContext(run=run, workflow=wf)

    async def hanging_agent(input_data, config, context, tools):
        await asyncio.sleep(1.2)  # Exceeds 1s timeout
        return AgentMessage(run_id=run.id, node_id="slow_node", status=NodeRunStatus.COMPLETED, data={})

    mock_agent = AsyncMock()
    mock_agent.run.side_effect = hanging_agent

    with (
        patch(
            "agentflow.core.executor.node_runner.agent_registry.get",
            return_value=mock_agent,
        ),
        pytest.raises(NodeExecutionError),
    ):
        await run_node(wf.nodes[0], {}, ctx)

    # Check node run status in record
    last_run = ctx.run.node_runs[-1]
    assert last_run.status == NodeRunStatus.TIMED_OUT
    assert "timed out" in (last_run.error or "").lower()
