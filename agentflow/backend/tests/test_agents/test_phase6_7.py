"""
Unit tests for Phase 6 Specialized Agents and Phase 7 Generation logic:
- HumanApprovalAgent
- SupervisorAgent
- RAGAgent
- MemoryAgent
- Workflow synthesis
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from agentflow.api.routes_workflows import _synthesize_workflow
from agentflow.core.agents.approval.approval_agent import HumanApprovalAgent
from agentflow.core.agents.memory.memory_agent import MemoryAgent
from agentflow.core.agents.rag.rag_agent import RAGAgent
from agentflow.core.agents.supervisor.supervisor_agent import SupervisorAgent
from agentflow.core.executor.context import RunContext
from agentflow.core.schemas.workflow import (
    AgentType,
    NodeConfig,
    NodeRunStatus,
    RunRecord,
    WorkflowDef,
)


@pytest.fixture
def context() -> RunContext:
    wf = WorkflowDef(id=uuid4(), name="phase6_wf", nodes=[], edges=[])
    run = RunRecord(workflow_id=wf.id, workflow_version=1)
    return RunContext(run=run, workflow=wf)


@pytest.mark.asyncio
async def test_human_approval_agent_pauses_and_resumes(context: RunContext):
    agent = HumanApprovalAgent()
    config = NodeConfig(system_prompt="Review payload before proceeding.")
    context.current_node_id = "approval_1"

    # 1. First execution — awaits approval
    msg = await agent.run(input_data={"order_id": 123, "amount": 999.0}, config=config, context=context, tools=[])
    assert msg.status == NodeRunStatus.AWAITING_APPROVAL
    assert msg.data["status"] == "awaiting_approval"
    assert "pending_approval_approval_1" in context.run.shared_context

    # 2. Decision supplied via shared context — approved
    context.set_shared("approval_approval_1", {
        "approved": True,
        "reviewer": "alice@example.com",
        "notes": "Looks good to merge.",
    })
    msg2 = await agent.run(input_data={"order_id": 123, "amount": 999.0}, config=config, context=context, tools=[])
    assert msg2.status == NodeRunStatus.COMPLETED
    assert msg2.data["approved"] is True
    assert msg2.data["reviewer"] == "alice@example.com"
    assert msg2.data["notes"] == "Looks good to merge."


@pytest.mark.asyncio
async def test_human_approval_agent_rejection(context: RunContext):
    agent = HumanApprovalAgent()
    config = NodeConfig()
    context.current_node_id = "approval_gate"

    context.set_shared("approval_approval_gate", {
        "approved": False,
        "reviewer": "compliance_bot",
        "notes": "Transaction flagged for review.",
    })
    msg = await agent.run(input_data={"score": 0.2}, config=config, context=context, tools=[])
    assert msg.status == NodeRunStatus.FAILED
    assert msg.data["approved"] is False
    assert len(msg.errors) > 0


@pytest.mark.asyncio
async def test_memory_agent_write_read_search(context: RunContext):
    agent = MemoryAgent()
    config = NodeConfig()

    # Write key
    w_msg = await agent.run(
        input_data={"action": "write", "memory_updates": {"customer_pref": {"lang": "en", "tier": "gold"}}},
        config=config,
        context=context,
        tools=[],
    )
    assert w_msg.status == NodeRunStatus.COMPLETED
    assert w_msg.data["action"] == "write"
    assert "customer_pref" in w_msg.data["recalled_memories"]

    # Read key
    r_msg = await agent.run(
        input_data={"action": "read"},
        config=config,
        context=context,
        tools=[],
    )
    assert r_msg.status == NodeRunStatus.COMPLETED
    assert r_msg.data["recalled_memories"]["customer_pref"]["tier"] == "gold"


@pytest.mark.asyncio
async def test_rag_agent_execution(context: RunContext):
    agent = RAGAgent()
    config = NodeConfig(system_prompt="Retrieve docs for refund policy")
    msg = await agent.run(
        input_data={"query": "What is the return window?", "documents": ["Items can be returned within 30 days."]},
        config=config,
        context=context,
        tools=[],
    )
    assert msg.status == NodeRunStatus.COMPLETED
    assert "answer" in msg.data
    assert len(msg.data["cited_passages"]) > 0


@pytest.mark.asyncio
async def test_supervisor_agent_execution(context: RunContext):
    agent = SupervisorAgent()
    config = NodeConfig(system_prompt="Break down market analysis")
    msg = await agent.run(
        input_data={"goal": "Analyze competitive landscape for SaaS AI tools"},
        config=config,
        context=context,
        tools=[],
    )
    assert msg.status == NodeRunStatus.COMPLETED
    assert "plan" in msg.data
    assert len(msg.data["plan"]) > 0
    assert "synthesis" in msg.data


def test_synthesize_workflow_generation():
    # Approval pipeline
    wf_approval = _synthesize_workflow("Create a workflow with human approval for customer discount requests")
    assert any(n.type == AgentType.HUMAN_APPROVAL for n in wf_approval.nodes)
    assert len(wf_approval.nodes) >= 3
    assert len(wf_approval.edges) >= 2

    # RAG pipeline
    wf_rag = _synthesize_workflow("Build a RAG knowledge base search for internal docs")
    assert any(n.type == AgentType.RAG for n in wf_rag.nodes)

    # Supervisor pipeline
    wf_sup = _synthesize_workflow("Supervisor multi-agent team to write a report")
    assert any(n.type == AgentType.SUPERVISOR for n in wf_sup.nodes)

    # General pipeline
    wf_gen = _synthesize_workflow("Analyze marketing trends and create copy")
    assert len(wf_gen.nodes) >= 3
    assert len(wf_gen.edges) >= 2
