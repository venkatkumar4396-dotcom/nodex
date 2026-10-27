"""
Tests for Context Cascading and End-to-End Pipeline Data Passing.

Verifies:
1. Multi-hop context propagation: Trigger and research context (lead_name, company, summary)
   cascades through intermediate nodes (supervisor, code_sandbox) to copywriter and router.
2. HumanApprovalAgent unwraps approved data to top level so downstream dispatchers receive it.
3. ClassifierAgent receives context, recognizes human approval, and passes through outreach content.
4. WriterAgent cleanly substitutes leftover raw template brackets (e.g. {{First Name}}, {{Company}}).
5. Downstream dispatch nodes execute rather than getting eliminated via dead-path elimination.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from agentflow.core.agents.approval.approval_agent import HumanApprovalAgent
from agentflow.core.agents.classifier.classifier_agent import ClassifierAgent
from agentflow.core.agents.writer.writer_agent import WriterAgent
from agentflow.core.executor.context import RunContext
from agentflow.core.executor.runner import run_workflow
from agentflow.core.schemas.workflow import (
    AgentMessage,
    AgentType,
    EdgeDef,
    NodeConfig,
    NodeDef,
    NodeRunStatus,
    RunRecord,
    RunStatus,
    WorkflowDef,
)


@pytest.mark.asyncio
async def test_context_cascade_multi_hop():
    """Verify context cascades from trigger through multi-hop nodes to writer and router."""
    wf = WorkflowDef(
        id=uuid4(),
        nodes=[
            NodeDef(id="trigger", type=AgentType.TRIGGER_MANUAL, label="Trigger", config=NodeConfig()),
            NodeDef(id="research", type=AgentType.RESEARCH, label="Research", config=NodeConfig()),
            NodeDef(id="supervisor", type=AgentType.SUPERVISOR, label="Supervisor", config=NodeConfig()),
            NodeDef(id="code", type=AgentType.CODE, label="Code", config=NodeConfig()),
            NodeDef(id="writer", type=AgentType.WRITER, label="Writer", config=NodeConfig()),
            NodeDef(id="approval", type=AgentType.HUMAN_APPROVAL, label="Approval", config=NodeConfig()),
            NodeDef(id="router", type=AgentType.ROUTER, label="Router", config=NodeConfig()),
            NodeDef(id="email", type=AgentType.EMAIL, label="Email", config=NodeConfig()),
        ],
        edges=[
            EdgeDef(id="e1", source="trigger", target="research"),
            EdgeDef(id="e2", source="research", target="supervisor"),
            EdgeDef(id="e3", source="supervisor", target="code"),
            EdgeDef(id="e4", source="code", target="writer"),
            EdgeDef(id="e5", source="writer", target="approval"),
            EdgeDef(id="e6", source="approval", target="router"),
            EdgeDef(id="e7", source="router", target="email", condition="output.get('score', 0) >= 7"),
        ],
    )

    received_inputs: dict[str, dict] = {}

    async def fake_agent_run(node, input_data, context, iteration):
        received_inputs[node.id] = dict(input_data)
        if node.type == AgentType.RESEARCH:
            return AgentMessage(
                run_id=context.run.id,
                node_id=node.id,
                status=NodeRunStatus.COMPLETED,
                data={
                    "summary": "Acme Corp is an enterprise AI company.",
                    "key_findings": [{"title": "OSS repo", "detail": "15k stars", "relevance_score": 0.9}],
                    "confidence": 0.85,
                },
            )
        elif node.type == AgentType.SUPERVISOR:
            return AgentMessage(
                run_id=context.run.id,
                node_id=node.id,
                status=NodeRunStatus.COMPLETED,
                data={"plan": ["task1"], "synthesis": "Target Acme Corp."},
            )
        elif node.type == AgentType.CODE:
            return AgentMessage(
                run_id=context.run.id,
                node_id=node.id,
                status=NodeRunStatus.COMPLETED,
                data={"result": "processed_sandbox", "status": "completed"},
            )
        elif node.type == AgentType.WRITER:
            return AgentMessage(
                run_id=context.run.id,
                node_id=node.id,
                status=NodeRunStatus.COMPLETED,
                data={
                    "subject": f"Quick idea for {input_data.get('company')}",
                    "body": f"Hi {input_data.get('lead_name')}, let's chat.",
                    "lead_name": input_data.get("lead_name"),
                    "company": input_data.get("company"),
                },
            )
        elif node.type == AgentType.HUMAN_APPROVAL:
            # Emulate an approved node
            agent = HumanApprovalAgent()
            context.set_shared(f"approval_{node.id}", {
                "approved": True,
                "reviewer": "Reviewer",
                "notes": "Approved by user",
            })
            return await agent.run(input_data, node.config, context, [])
        elif node.type == AgentType.ROUTER:
            return AgentMessage(
                run_id=context.run.id,
                node_id=node.id,
                status=NodeRunStatus.COMPLETED,
                data={
                    "score": 9,
                    "branch": "qualified",
                    "subject": input_data.get("subject"),
                    "body": input_data.get("body"),
                    "lead_name": input_data.get("lead_name"),
                    "company": input_data.get("company"),
                },
            )
        elif node.type == AgentType.EMAIL:
            return AgentMessage(
                run_id=context.run.id,
                node_id=node.id,
                status=NodeRunStatus.COMPLETED,
                data={"sent": True, "subject": input_data.get("subject"), "body": input_data.get("body")},
            )
        return AgentMessage(run_id=context.run.id, node_id=node.id, status=NodeRunStatus.COMPLETED, data={})

    with patch("agentflow.core.executor.runner.run_node", side_effect=fake_agent_run):
        run = await run_workflow(
            wf,
            trigger_data={
                "lead_name": "Sarah Chen",
                "company": "Acme Corp",
                "topic": "Multi-Agent Automation",
                "goal": "Schedule demo",
            },
        )

    assert run.status == RunStatus.COMPLETED

    # 1. Verify Writer received cascaded lead_name & company despite passing through supervisor & code
    writer_input = received_inputs.get("writer", {})
    assert writer_input.get("lead_name") == "Sarah Chen"
    assert writer_input.get("company") == "Acme Corp"
    assert writer_input.get("summary") == "Acme Corp is an enterprise AI company."

    # 2. Verify Approval unpacked payload at root
    approval_output = run.node_runs[-3].output if len(run.node_runs) >= 3 else {}
    assert isinstance(approval_output, dict)
    # Router received subject and body from approval
    router_input = received_inputs.get("router", {})
    assert router_input.get("lead_name") == "Sarah Chen"
    assert router_input.get("company") == "Acme Corp"
    assert "Quick idea for Acme Corp" in router_input.get("subject", "")
    assert router_input.get("approved") is True

    # 3. Verify Email dispatcher received the message and was NOT skipped
    email_input = received_inputs.get("email", {})
    assert "Quick idea for Acme Corp" in email_input.get("subject", "")
    assert "Sarah Chen" in email_input.get("body", "")


@pytest.mark.asyncio
async def test_approval_agent_unpacks_at_root():
    """Verify HumanApprovalAgent output contains input fields at the top level."""
    agent = HumanApprovalAgent()
    wf = WorkflowDef(id=uuid4(), name="approval_test", nodes=[], edges=[])
    run = RunRecord(workflow_id=wf.id, workflow_version=1)
    context = RunContext(run=run, workflow=wf)
    context.current_node_id = "test_approval"

    context.set_shared("approval_test_approval", {
        "approved": True,
        "reviewer": "Security Admin",
        "notes": "Verified lead authenticity",
    })

    input_data = {
        "lead_name": "Sarah Chen",
        "company": "Acme Corp",
        "subject": "Demo invitation",
        "body": "Hi Sarah, check out our demo.",
    }

    msg = await agent.run(input_data=input_data, config=NodeConfig(), context=context, tools=[])
    assert msg.status == NodeRunStatus.COMPLETED
    assert msg.data["approved"] is True
    assert msg.data["reviewer"] == "Security Admin"
    assert msg.data["subject"] == "Demo invitation"
    assert msg.data["body"] == "Hi Sarah, check out our demo."
    assert msg.data["lead_name"] == "Sarah Chen"
    assert msg.data["company"] == "Acme Corp"


@pytest.mark.asyncio
async def test_writer_agent_substitutes_raw_placeholders():
    """Verify WriterAgent cleans up raw {{First Name}} and {{Company}} placeholders."""
    agent = WriterAgent()
    wf = WorkflowDef(id=uuid4(), name="writer_test", nodes=[], edges=[])
    run = RunRecord(workflow_id=wf.id, workflow_version=1, trigger_data={"lead_name": "Sarah Chen", "company": "Acme Corp"})
    context = RunContext(run=run, workflow=wf)
    context.current_node_id = "writer"

    from agentflow.core.agents.writer.writer_agent import WriterOutput
    fake_output = WriterOutput(
        subject="Quick idea for {{Company}}'s workflow",
        body="Hi {{First Name}},\n\nMost leaders at {{Company}} are losing hours. Best, Alex",
        tone="Professional",
        word_count=20,
        personalization_hooks=[],
    )

    fake_resp = AsyncMock()
    fake_resp.prompt_tokens = 50
    fake_resp.completion_tokens = 50
    fake_resp.total_tokens = 100
    fake_resp.cost_usd = 0.001
    fake_resp.model = "test-model"

    with patch("agentflow.core.agents.writer.writer_agent.complete_structured", return_value=(fake_output, fake_resp)):
        msg = await agent.run(
            input_data={"summary": "Enterprise multi-agent automation."},
            config=NodeConfig(),
            context=context,
            tools=[],
        )

    assert msg.status == NodeRunStatus.COMPLETED
    # Verify placeholders were substituted with trigger_data
    assert msg.data["subject"] == "Quick idea for Acme Corp's workflow"
    assert "Hi Sarah," in msg.data["body"]
    assert "leaders at Acme Corp" in msg.data["body"]
    assert "{{First Name}}" not in msg.data["body"]
    assert "{{Company}}" not in msg.data["body"]


@pytest.mark.asyncio
async def test_classifier_agent_context_fallback_and_passthrough():
    """Verify ClassifierAgent falls back to upstream outputs and passes through outreach content."""
    agent = ClassifierAgent()
    wf = WorkflowDef(id=uuid4(), name="classifier_test", nodes=[], edges=[])
    run = RunRecord(workflow_id=wf.id, workflow_version=1, trigger_data={"lead_name": "Sarah Chen", "company": "Acme Corp"})
    context = RunContext(run=run, workflow=wf)
    context.current_node_id = "classifier"

    # Pre-populate upstream research output in context
    context.record_node_output("deep_research", {
        "summary": "Acme Corp has 15,400 GitHub stars and Sarah Chen is VP of Product.",
        "key_findings": [{"title": "High traction", "detail": "Active repo", "relevance_score": 0.9}],
        "confidence": 0.85,
    })

    from agentflow.core.agents.classifier.classifier_agent import ClassifierOutput
    fake_output = ClassifierOutput(
        score=9,
        category="enterprise",
        branch="qualified",
        reasoning="Strong technical signals and verified product leadership.",
        recommendation="Proceed with demo scheduling.",
    )
    fake_resp = AsyncMock()
    fake_resp.prompt_tokens = 50
    fake_resp.completion_tokens = 50
    fake_resp.total_tokens = 100
    fake_resp.cost_usd = 0.001
    fake_resp.model = "test-model"

    with patch("agentflow.core.agents.classifier.classifier_agent.complete_structured", return_value=(fake_output, fake_resp)):
        msg = await agent.run(
            input_data={
                "approved": True,
                "subject": "Quick idea for Acme Corp",
                "body": "Hi Sarah, let's schedule an architecture demo.",
            },
            config=NodeConfig(),
            context=context,
            tools=[],
        )

    assert msg.status == NodeRunStatus.COMPLETED
    assert msg.data["score"] == 9
    assert msg.data["branch"] == "qualified"
    # Verify lead_name and company were populated from context
    assert msg.data["lead_name"] == "Sarah Chen"
    assert msg.data["company"] == "Acme Corp"
    # Verify subject and body passed through for downstream dispatcher nodes
    assert msg.data["subject"] == "Quick idea for Acme Corp"
    assert msg.data["body"] == "Hi Sarah, let's schedule an architecture demo."

