"""
Tests for isolated code agent sandbox and security controls.
"""
from __future__ import annotations

import pytest

import uuid

from agentflow.core.agents.code.code_agent import CodeAgent
from agentflow.core.executor.context import RunContext
from agentflow.core.sandbox import (
    SandboxExecutionError,
    SandboxSecurityError,
    SandboxTimeoutError,
    run_in_sandbox,
    run_in_sandbox_sync,
)
from agentflow.core.schemas.workflow import (
    NodeConfig,
    NodeRunStatus,
    RunRecord,
    WorkflowDef,
)


@pytest.fixture
def mock_run_context() -> RunContext:
    wf_id = uuid.uuid4()
    wf = WorkflowDef(id=wf_id, name="Sandbox Test WF", nodes=[], edges=[])
    run = RunRecord(workflow_id=wf_id, workflow_version=1)
    return RunContext(run=run, workflow=wf)


class TestSandboxSecurityAndIsolation:
    """Verify that isolated sandbox blocks malicious attempts and executes safe code."""

    def test_safe_data_transformation(self) -> None:
        code = """
result = {
    'total': data['a'] + data['b'],
    'message': f"Hello {data['name']}"
}
"""
        res = run_in_sandbox_sync(code, input_data={"a": 10, "b": 25, "name": "Alice"})
        assert res["total"] == 35
        assert res["message"] == "Hello Alice"

    def test_transform_function_pattern(self) -> None:
        code = """
def transform(d):
    return {"squared": [x ** 2 for x in d["numbers"]]}
"""
        res = run_in_sandbox_sync(code, input_data={"numbers": [1, 2, 3, 4]})
        assert res["squared"] == [1, 4, 9, 16]

    def test_blocks_reading_etc_passwd(self) -> None:
        code = """
with open('/etc/passwd') as f:
    result = f.read()
"""
        with pytest.raises(SandboxSecurityError) as exc_info:
            run_in_sandbox_sync(code, input_data={})
        assert "denied by sandbox security policy" in str(exc_info.value).lower() or "permissionerror" in str(exc_info.value).lower()

    def test_blocks_reading_etc_passwd_via_pathlib(self) -> None:
        code = """
from pathlib import Path
result = Path('/etc/passwd').read_text()
"""
        with pytest.raises(SandboxSecurityError) as exc_info:
            run_in_sandbox_sync(code, input_data={})
        assert "denied by sandbox security policy" in str(exc_info.value).lower() or "permissionerror" in str(exc_info.value).lower()

    def test_blocks_socket_network_calls(self) -> None:
        code = """
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('1.1.1.1', 80))
result = 'connected'
"""
        with pytest.raises(SandboxSecurityError) as exc_info:
            run_in_sandbox_sync(code, input_data={})
        assert "network access is disabled" in str(exc_info.value).lower() or "permissionerror" in str(exc_info.value).lower()

    def test_blocks_urllib_network_calls(self) -> None:
        code = """
import urllib.request
resp = urllib.request.urlopen('http://example.com')
result = resp.read()
"""
        with pytest.raises(SandboxSecurityError) as exc_info:
            run_in_sandbox_sync(code, input_data={})
        assert "network access is disabled" in str(exc_info.value).lower() or "permissionerror" in str(exc_info.value).lower()

    def test_blocks_process_spawning(self) -> None:
        code = """
import os
os.system('echo exploit')
result = 'spawned'
"""
        with pytest.raises(SandboxSecurityError) as exc_info:
            run_in_sandbox_sync(code, input_data={})
        assert "process creation is disabled" in str(exc_info.value).lower() or "permissionerror" in str(exc_info.value).lower()

    def test_timeout_enforcement(self) -> None:
        code = """
import time
time.sleep(3)
result = 'done'
"""
        with pytest.raises(SandboxTimeoutError):
            run_in_sandbox_sync(code, input_data={}, timeout_seconds=0.5)


class TestCodeAgentIntegration:
    """Verify CodeAgent execution with sandbox enforcement."""

    @pytest.mark.asyncio
    async def test_code_agent_runs_safe_code(self, mock_run_context: RunContext) -> None:
        agent = CodeAgent()
        config = NodeConfig(
            extra={
                "code": "result = {'doubled': data['val'] * 2}",
                "execution_mode": "deterministic",
            }
        )
        msg = await agent.run(input_data={"val": 21}, config=config, context=mock_run_context, tools=[])
        assert msg.status == NodeRunStatus.COMPLETED
        assert msg.data["doubled"] == 42
        assert msg.data["val"] == 21
        assert msg.metadata.model == "sandbox/isolated"

    @pytest.mark.asyncio
    async def test_code_agent_blocks_etc_passwd_exploit(self, mock_run_context: RunContext) -> None:
        agent = CodeAgent()
        config = NodeConfig(
            extra={
                "code": "result = open('/etc/passwd').read()",
                "execution_mode": "deterministic",
            }
        )
        msg = await agent.run(input_data={}, config=config, context=mock_run_context, tools=[])
        assert msg.status == NodeRunStatus.FAILED
        assert any("Security violation blocked" in err for err in msg.errors)
        assert msg.data["status"] == "blocked"

    @pytest.mark.asyncio
    async def test_code_agent_blocks_network_exploit(self, mock_run_context: RunContext) -> None:
        agent = CodeAgent()
        config = NodeConfig(
            extra={
                "code": "import socket; s = socket.socket(); s.connect(('8.8.8.8', 53))",
                "execution_mode": "deterministic",
            }
        )
        msg = await agent.run(input_data={}, config=config, context=mock_run_context, tools=[])
        assert msg.status == NodeRunStatus.FAILED
        assert any("Security violation blocked" in err for err in msg.errors)
        assert any("Network access is disabled" in err for err in msg.errors)
        assert msg.data["status"] == "blocked"
