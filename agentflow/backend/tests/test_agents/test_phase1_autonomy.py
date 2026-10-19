"""
Unit and integration tests for Phase 1: Autonomy Core Engine & Governance.

Tests:
- Hardened tool loop: per-tool timeout handling
- Hardened tool loop: repeated identical call detection
- Hardened tool loop: least-privilege tool allowlist enforcement
- Autonomy levels: SUGGEST (proposal only, no execution)
- Autonomy levels: ASK_FIRST (pauses for approval, executes if approved)
- Autonomy levels: ACT (full autonomous execution)
- Budget Governor: global_max_time_seconds budget limit & partial results preservation
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, ClassVar
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from agentflow.core.agents.email.email_agent import EmailAgent
from agentflow.core.executor.context import RunContext, TimeLimitExceeded
from agentflow.core.executor.node_runner import _resolve_node_tools
from agentflow.core.schemas.tool import ToolResult
from agentflow.core.schemas.workflow import (
    AgentType,
    AutonomyLevel,
    EdgeDef,
    NodeConfig,
    NodeDef,
    NodeRunStatus,
    RunRecord,
    RunStatus,
    WorkflowDef,
)
from agentflow.core.tools.base import BaseTool
from agentflow.core.tools.email_tool import EmailSendTool
from agentflow.core.tools.registry import tool_registry
from agentflow.core.tools.tool_loop import run_tool_loop


# ── Test Tools ────────────────────────────────────────────────────────────────

class SlowTool(BaseTool):
    """Tool that deliberately sleeps to test per-tool timeout."""
    name: str = "slow_tool"
    description: str = "A deliberately slow test tool"
    parameters_schema: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

    def __init__(self, delay: float = 1.0) -> None:
        self.delay = delay

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        await asyncio.sleep(self.delay)
        return ToolResult(tool_name=self.name, success=True, data={"status": "finished_slow"})


class EchoTool(BaseTool):
    """Tool that echoes input for repeatability tests."""
    name: str = "echo_tool"
    description: str = "Echo tool"
    parameters_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
    }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(tool_name=self.name, success=True, data={"echo": arguments.get("text", "")})


class DestructiveTestTool(BaseTool):
    """Destructive tool for autonomy testing."""
    name: str = "destructive_action"
    description: str = "Performs a permanent, destructive operation"
    parameters_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"target": {"type": "string"}},
    }
    is_destructive: ClassVar[bool] = True

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={"action": "deleted", "target": arguments.get("target", "unknown")},
        )


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def run_context():
    workflow_id = uuid4()
    workflow_def = WorkflowDef(
        id=workflow_id,
        name="Phase 1 Test Workflow",
        nodes=[
            NodeDef(
                id="node_1",
                type=AgentType.TOOL,
                label="Tool Node",
                config=NodeConfig(tools=["slow_tool", "echo_tool"]),
            )
        ],
        edges=[],
    )
    run = RunRecord(
        workflow_id=workflow_id,
        workflow_version=1,
    )
    ctx = RunContext(run=run, workflow=workflow_def)
    ctx.current_node_id = "node_1"
    return ctx


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tool_loop_per_tool_timeout(run_context):
    """Per-tool timeout triggers an observation error without crashing the loop."""
    slow_tool = SlowTool(delay=1.0)
    messages = [
        {"role": "user", "content": "Run slow tool"}
    ]

    mock_call_slow = {
        "thought": "Calling slow tool",
        "tool_call": {"name": "slow_tool", "arguments": {}},
    }
    mock_done = {
        "thought": "Done",
        "answer": "Completed after slow tool",
    }

    with patch("agentflow.core.tools.tool_loop.complete") as mock_complete:
        mock_complete.side_effect = [
            AsyncMock(content=f"```json\n{__import__('json').dumps(mock_call_slow)}\n```", prompt_tokens=10, completion_tokens=10, total_tokens=20, cost_usd=0.0001, model="test"),
            AsyncMock(content=f"```json\n{__import__('json').dumps(mock_done)}\n```", prompt_tokens=10, completion_tokens=10, total_tokens=20, cost_usd=0.0001, model="test"),
        ]

        result = await run_tool_loop(
            messages=messages,
            tools=[slow_tool],
            model="openrouter/free",
            max_rounds=5,
            tool_timeout_seconds=0.1,  # 100ms timeout vs 1s delay
            context=run_context,
            node_id="node_1",
        )

        assert len(result.tool_results) == 1
        assert result.tool_results[0].success is False
        assert "timed out after 0.1s" in (result.tool_results[0].error or "")
        assert len(result.trace) >= 1
        assert result.trace[0].success is False
        assert result.trace[0].status == "timed_out"


@pytest.mark.asyncio
async def test_tool_loop_repeated_identical_call_detection(run_context):
    """Repeated identical calls are intercepted immediately on duplicate invocation."""
    echo_tool = EchoTool()
    messages = [{"role": "user", "content": "Echo test"}]

    identical_call = {
        "thought": "Calling echo repeatedly",
        "tool_call": {"name": "echo_tool", "arguments": {"text": "hello"}},
    }
    mock_done = {"thought": "Finished", "answer": "Done"}

    with patch("agentflow.core.tools.tool_loop.complete") as mock_complete:
        # First call executes, second call is intercepted, then loop finishes
        mock_complete.side_effect = [
            AsyncMock(content=f"```json\n{__import__('json').dumps(identical_call)}\n```", prompt_tokens=5, completion_tokens=5, total_tokens=10, cost_usd=0.0, model="test"),
            AsyncMock(content=f"```json\n{__import__('json').dumps(identical_call)}\n```", prompt_tokens=5, completion_tokens=5, total_tokens=10, cost_usd=0.0, model="test"),
            AsyncMock(content=f"```json\n{__import__('json').dumps(mock_done)}\n```", prompt_tokens=5, completion_tokens=5, total_tokens=10, cost_usd=0.0, model="test"),
        ]

        result = await run_tool_loop(
            messages=messages,
            tools=[echo_tool],
            model="openrouter/free",
            max_rounds=5,
            context=run_context,
            node_id="node_1",
        )

        assert len(result.tool_results) == 2
        # First call succeeds
        assert result.tool_results[0].success is True
        # Second call with identical arguments is intercepted and blocked
        assert result.tool_results[1].success is False
        assert "Duplicate tool call blocked" in (result.tool_results[1].error or "")
        assert result.trace[1].status == "duplicate_blocked"


@pytest.mark.asyncio
async def test_least_privilege_tool_allowlist():
    """Agent cannot receive tools outside its allowed_tools set."""
    node = NodeDef(
        id="email_node",
        type=AgentType.EMAIL,
        label="Email Sender",
        config=NodeConfig(tools=["send_email", "web_search", "unauthorized_tool"]),
    )

    resolved = _resolve_node_tools(node)
    resolved_names = [t.name for t in resolved]

    # web_search is not in EmailAgent.allowed_tools
    assert "web_search" not in resolved_names
    assert "unauthorized_tool" not in resolved_names


@pytest.mark.asyncio
async def test_autonomy_suggest_mode(run_context):
    """Autonomy SUGGEST generates proposal for destructive tool without executing it."""
    dest_tool = DestructiveTestTool()
    messages = [{"role": "user", "content": "Delete database"}]

    call_destructive = {
        "thought": "Proposing delete",
        "tool_call": {"name": "destructive_action", "arguments": {"target": "prod_users"}},
    }
    mock_done = {"thought": "Finished", "answer": "I have proposed the deletion"}

    with patch("agentflow.core.tools.tool_loop.complete") as mock_complete:
        mock_complete.side_effect = [
            AsyncMock(content=f"```json\n{__import__('json').dumps(call_destructive)}\n```", prompt_tokens=5, completion_tokens=5, total_tokens=10, cost_usd=0.0, model="test"),
            AsyncMock(content=f"```json\n{__import__('json').dumps(mock_done)}\n```", prompt_tokens=5, completion_tokens=5, total_tokens=10, cost_usd=0.0, model="test"),
        ]

        result = await run_tool_loop(
            messages=messages,
            tools=[dest_tool],
            model="openrouter/free",
            autonomy=AutonomyLevel.SUGGEST,
            context=run_context,
            node_id="node_1",
        )

        assert len(result.tool_results) == 1
        assert result.tool_results[0].success is True
        assert result.tool_results[0].data.get("status") == "suggested_only"
        assert result.tool_results[0].data.get("executed") is False
        assert result.trace[0].status == "suggested_only"


@pytest.mark.asyncio
async def test_autonomy_ask_first_mode_pauses_for_approval(run_context):
    """Autonomy ASK_FIRST sets awaiting_approval when destructive tool is invoked."""
    dest_tool = DestructiveTestTool()
    messages = [{"role": "user", "content": "Delete production records"}]

    call_destructive = {
        "thought": "Need to delete",
        "tool_call": {"name": "destructive_action", "arguments": {"target": "prod_records"}},
    }

    with patch("agentflow.core.tools.tool_loop.complete") as mock_complete:
        mock_complete.side_effect = [
            AsyncMock(content=f"```json\n{__import__('json').dumps(call_destructive)}\n```", prompt_tokens=5, completion_tokens=5, total_tokens=10, cost_usd=0.0, model="test"),
        ]

        result = await run_tool_loop(
            messages=messages,
            tools=[dest_tool],
            model="openrouter/free",
            autonomy=AutonomyLevel.ASK_FIRST,
            context=run_context,
            node_id="node_1",
        )

        assert result.awaiting_approval is True
        assert len(result.trace) == 1
        assert result.trace[0].status == "awaiting_approval"
        pending = run_context.get_shared("pending_approval_node_1")
        assert pending is not None
        assert pending["tool_name"] == "destructive_action"
        assert pending["arguments"]["target"] == "prod_records"


@pytest.mark.asyncio
async def test_autonomy_ask_first_mode_executes_when_approved(run_context):
    """Autonomy ASK_FIRST executes destructive tool if pre-approved in context."""
    dest_tool = DestructiveTestTool()
    messages = [{"role": "user", "content": "Delete production records"}]

    run_context.set_shared("approved_node_1", True)

    call_destructive = {
        "thought": "Executing pre-approved delete",
        "tool_call": {"name": "destructive_action", "arguments": {"target": "prod_records"}},
    }
    mock_done = {"thought": "Finished", "answer": "Done deleting"}

    with patch("agentflow.core.tools.tool_loop.complete") as mock_complete:
        mock_complete.side_effect = [
            AsyncMock(content=f"```json\n{__import__('json').dumps(call_destructive)}\n```", prompt_tokens=5, completion_tokens=5, total_tokens=10, cost_usd=0.0, model="test"),
            AsyncMock(content=f"```json\n{__import__('json').dumps(mock_done)}\n```", prompt_tokens=5, completion_tokens=5, total_tokens=10, cost_usd=0.0, model="test"),
        ]

        result = await run_tool_loop(
            messages=messages,
            tools=[dest_tool],
            model="openrouter/free",
            autonomy=AutonomyLevel.ASK_FIRST,
            context=run_context,
            node_id="node_1",
        )

        assert result.awaiting_approval is False
        assert len(result.tool_results) == 1
        assert result.tool_results[0].success is True
        assert result.tool_results[0].data["action"] == "deleted"


@pytest.mark.asyncio
async def test_autonomy_act_mode(run_context):
    """Autonomy ACT executes destructive tool immediately without pausing."""
    dest_tool = DestructiveTestTool()
    messages = [{"role": "user", "content": "Delete records automatically"}]

    call_destructive = {
        "thought": "Autonomous delete",
        "tool_call": {"name": "destructive_action", "arguments": {"target": "archive_2024"}},
    }
    mock_done = {"thought": "Finished", "answer": "Deleted autonomously"}

    with patch("agentflow.core.tools.tool_loop.complete") as mock_complete:
        mock_complete.side_effect = [
            AsyncMock(content=f"```json\n{__import__('json').dumps(call_destructive)}\n```", prompt_tokens=5, completion_tokens=5, total_tokens=10, cost_usd=0.0, model="test"),
            AsyncMock(content=f"```json\n{__import__('json').dumps(mock_done)}\n```", prompt_tokens=5, completion_tokens=5, total_tokens=10, cost_usd=0.0, model="test"),
        ]

        result = await run_tool_loop(
            messages=messages,
            tools=[dest_tool],
            model="openrouter/free",
            autonomy=AutonomyLevel.ACT,
            context=run_context,
            node_id="node_1",
        )

        assert result.awaiting_approval is False
        assert len(result.tool_results) == 1
        assert result.tool_results[0].success is True
        assert result.tool_results[0].data["action"] == "deleted"
        assert result.tool_results[0].data["target"] == "archive_2024"


def test_budget_governor_time_limit():
    """Workflow execution stops when global_max_time_seconds is exceeded."""
    workflow_id = uuid4()
    workflow_def = WorkflowDef(
        id=workflow_id,
        name="Budget Test",
        global_max_time_seconds=1.0,
        nodes=[
            NodeDef(
                id="step_1",
                type=AgentType.RESEARCH,
                label="Step 1",
            ),
        ],
        edges=[],
    )
    run = RunRecord(
        workflow_id=workflow_id,
        workflow_version=1,
    )

    ctx = RunContext(run=run, workflow=workflow_def)
    ctx.record_node_output("step_1", {"lead_name": "Acme Corp"})

    # Set started_at to 2.0s ago
    ctx.run.started_at = time.time() - 2.0

    with pytest.raises(TimeLimitExceeded) as exc_info:
        ctx.check_budget_limits()

    assert "exceeded global time budget 1.00s" in str(exc_info.value)


@pytest.mark.asyncio
async def test_real_llm_failure_propagates_without_silent_mock():
    """Bad API key or provider failure raises real exception instead of returning fake smart mock."""
    from agentflow.config import settings
    from agentflow.core.llm.client import complete
    from agentflow.core.executor.node_runner import run_node, NodeExecutionError

    # Ensure simulation mode is strictly OFF
    settings.mock_llm = False
    settings.simulation_mode = False

    # Mock litellm to simulate real provider 401 AuthenticationError
    with patch("litellm.acompletion") as mock_acompletion:
        mock_acompletion.side_effect = Exception("AuthenticationError: 401 Invalid API Key provided")

        # 1. Direct LLM completion must raise, NOT return _generate_smart_mock_response
        with pytest.raises(Exception) as exc_info:
            await complete(
                messages=[{"role": "user", "content": "Analyze lead"}],
                model="openrouter/anthropic/claude-3.5-sonnet",
                api_key="sk-bad-key-9999",
            )
        assert "401 Invalid API Key" in str(exc_info.value)

        # 2. Node runner must fail with NodeExecutionError and status FAILED
        workflow_id = uuid4()
        workflow_def = WorkflowDef(
            id=workflow_id,
            name="Auth Failure Workflow",
            nodes=[
                NodeDef(
                    id="research_node",
                    type=AgentType.RESEARCH,
                    label="Research",
                    config=NodeConfig(
                        model="openrouter/anthropic/claude-3.5-sonnet",
                        retry_policy={"max_attempts": 1, "backoff_seconds": 0.01},
                    ),
                )
            ],
            edges=[],
        )
        run = RunRecord(workflow_id=workflow_id, workflow_version=1)
        ctx = RunContext(run=run, workflow=workflow_def)

        with pytest.raises(NodeExecutionError) as node_exc:
            await run_node(
                node=workflow_def.nodes[0],
                input_data={"lead_name": "Test Target"},
                context=ctx,
            )

        assert "401 Invalid API Key" in str(node_exc.value)
        # Verify node_run was marked FAILED, not COMPLETED
        assert len(ctx.run.node_runs) == 1
        assert ctx.run.node_runs[0].status == NodeRunStatus.FAILED
        assert "401 Invalid API Key" in (ctx.run.node_runs[0].error or "")


@pytest.mark.asyncio
async def test_simulation_mode_explicit_opt_in():
    """AGENTFLOW_SIMULATION_MODE=true visibly flags mock output with [SIMULATED RESULT]."""
    from agentflow.config import settings
    from agentflow.core.llm.client import complete

    settings.mock_llm = False
    settings.simulation_mode = True

    try:
        resp = await complete(
            messages=[{"role": "user", "content": "Draft outreach email"}],
            model="openrouter/free",
        )
        assert "[SIMULATED RESULT]" in resp.content
    finally:
        settings.simulation_mode = False
