"""
RunContext — the shared mutable state for a single workflow run.

All agents receive a reference to the RunContext. They can:
  - Read any previously completed node's output via get_node_output()
  - Write to shared_context (key-value bag for cross-agent communication)
  - Check run-level limits (cost, steps)

Design note: RunContext is deliberately NOT a God object. Agents should 
prefer the explicit data mappings on edges over reading from shared_context.
Shared context is for things like "session_id" or "user_timezone" that 
every agent might need but that don't flow naturally through edges.
"""
from __future__ import annotations

import time
from typing import Any
from uuid import UUID

import structlog

from agentflow.core.schemas.workflow import (
    AgentMessage,
    NodeRunRecord,
    NodeRunStatus,
    RunRecord,
    RunStatus,
    WorkflowDef,
)

log = structlog.get_logger(__name__)


class CostLimitExceeded(Exception):
    """Raised when a run exceeds its total cost budget."""


class StepLimitExceeded(Exception):
    """Raised when a run exceeds its max step count."""


class RunContext:
    """
    Mutable run-level state passed to every node executor.

    Thread-safety note: In Phase 1 this runs in a single asyncio event loop
    with cooperative multitasking. In Phase 4 (worker processes) each run
    gets its own RunContext instance, so no locking is needed.
    """

    def __init__(self, run: RunRecord, workflow: WorkflowDef) -> None:
        self.run = run
        self.workflow = workflow
        self._node_outputs: dict[str, dict[str, Any]] = {}
        self._step_count: int = 0
        self._loop_counts: dict[str, int] = {}  # edge_id -> iteration count
        self.current_node_id: str = ""  # set by node_runner before calling agent.run()

    # ── Node output registry ─────────────────────────────────────────────────

    def record_node_output(self, node_id: str, data: dict[str, Any]) -> None:
        """Store a node's validated output so downstream nodes can reference it."""
        self._node_outputs[node_id] = data

    def get_node_output(self, node_id: str) -> dict[str, Any] | None:
        return self._node_outputs.get(node_id)

    def get_all_outputs(self) -> dict[str, dict[str, Any]]:
        return dict(self._node_outputs)

    # ── Shared context ────────────────────────────────────────────────────────

    def set_shared(self, key: str, value: Any) -> None:
        self.run.shared_context[key] = value

    def get_shared(self, key: str, default: Any = None) -> Any:
        return self.run.shared_context.get(key, default)

    # ── Cost & step tracking ─────────────────────────────────────────────────

    def add_cost(self, cost_usd: float) -> None:
        self.run.total_cost_usd += cost_usd
        self.run.total_tokens += 0  # tokens updated separately

    def add_tokens(self, prompt: int, completion: int) -> None:
        self.run.total_tokens += prompt + completion

    def increment_step(self) -> None:
        self._step_count += 1
        max_steps = self.workflow.global_max_steps
        if self._step_count > max_steps:
            raise StepLimitExceeded(
                f"Run exceeded max_steps={max_steps}. "
                "Increase global_max_steps or check for loops."
            )

    def check_cost_limit(self) -> None:
        limit = self.workflow.global_max_cost_usd
        if limit is not None and self.run.total_cost_usd > limit:
            raise CostLimitExceeded(
                f"Run cost ${self.run.total_cost_usd:.4f} exceeded "
                f"budget ${limit:.4f}"
            )

    # ── Loop tracking ─────────────────────────────────────────────────────────

    def get_loop_count(self, edge_id: str) -> int:
        return self._loop_counts.get(edge_id, 0)

    def increment_loop(self, edge_id: str) -> int:
        self._loop_counts[edge_id] = self._loop_counts.get(edge_id, 0) + 1
        return self._loop_counts[edge_id]

    # ── Node run record management ────────────────────────────────────────────

    def start_node_run(self, node_run: NodeRunRecord) -> None:
        node_run.status = NodeRunStatus.RUNNING
        node_run.started_at = time.time()
        self.run.node_runs.append(node_run)
        log.info(
            "node_started",
            run_id=str(self.run.id),
            node_id=node_run.node_id,
            agent_type=node_run.agent_type.value,
            attempt=node_run.attempt,
        )

    def finish_node_run(
        self,
        node_run: NodeRunRecord,
        message: AgentMessage,
    ) -> None:
        node_run.status = message.status
        node_run.output = message.data
        node_run.completed_at = time.time()
        if node_run.started_at:
            node_run.duration_ms = int((node_run.completed_at - node_run.started_at) * 1000)
        node_run.prompt_tokens = message.metadata.prompt_tokens
        node_run.completion_tokens = message.metadata.completion_tokens
        node_run.cost_usd = message.metadata.cost_usd

        self.add_tokens(message.metadata.prompt_tokens, message.metadata.completion_tokens)
        self.add_cost(message.metadata.cost_usd)

        if message.status == NodeRunStatus.COMPLETED:
            self.record_node_output(node_run.node_id, message.data)
            log.info(
                "node_completed",
                run_id=str(self.run.id),
                node_id=node_run.node_id,
                duration_ms=node_run.duration_ms,
                tokens=message.metadata.total_tokens,
                cost_usd=message.metadata.cost_usd,
            )
        else:
            node_run.error = "; ".join(message.errors)
            log.error(
                "node_failed",
                run_id=str(self.run.id),
                node_id=node_run.node_id,
                errors=message.errors,
            )

    def finalize_run(self, status: RunStatus, error: str | None = None) -> None:
        self.run.status = status
        self.run.error = error
        self.run.completed_at = time.time()
        log.info(
            "run_completed",
            run_id=str(self.run.id),
            status=status.value,
            total_tokens=self.run.total_tokens,
            total_cost_usd=self.run.total_cost_usd,
            step_count=self._step_count,
        )
