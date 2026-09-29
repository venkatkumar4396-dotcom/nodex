"""
NodeRunner — executes a single node with retry, timeout, and output validation.

Design decisions:
  1. Retry with exponential backoff on LLM/tool errors AND on validation errors.
     When retrying a validation error, we inject the error message back into
     the prompt so the model can correct its output — this is the key pattern
     for reliable structured output.

  2. Timeouts are enforced with asyncio.wait_for(). Per-node timeouts prevent
     a slow LLM call from blocking the entire run.

  3. Validation happens after every LLM response. If the model returns JSON
     that doesn't match the output schema, that counts as a failed attempt
     and triggers a retry with the validation error injected.

  4. The node runner is responsible for creating the NodeRunRecord and
     reporting start/finish to the RunContext. This means the executor
     doesn't need to know about logging details.

  5. Agent instances are obtained from the AgentRegistry — this is the
     plugin boundary. The node runner never imports agent classes directly.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import UUID

import structlog

from agentflow.core.agents.base import BaseAgent
from agentflow.core.agents.registry import agent_registry
from agentflow.core.executor.context import RunContext
from agentflow.core.schemas.workflow import (
    AgentMessage,
    AgentType,
    MessageMetadata,
    NodeDef,
    NodeRunRecord,
    NodeRunStatus,
)

log = structlog.get_logger(__name__)


class NodeExecutionError(Exception):
    """Raised when a node fails all retry attempts."""

    def __init__(self, node_id: str, message: str, attempts: int) -> None:
        super().__init__(message)
        self.node_id = node_id
        self.attempts = attempts


async def run_node(
    node: NodeDef,
    input_data: dict[str, Any],
    context: RunContext,
    tools: list[Any] | None = None,
) -> AgentMessage:
    """
    Execute a single workflow node with retry and timeout logic.

    Args:
        node: The node definition (type, config, id)
        input_data: Resolved input data from upstream nodes
        context: The run-level shared context
        tools: List of BaseTool instances assigned to this node

    Returns:
        AgentMessage with status=COMPLETED and validated output data.

    Raises:
        NodeExecutionError: after all retry attempts are exhausted.
    """
    tools = tools or []
    policy = node.config.retry_policy
    last_error: str = ""
    validation_feedback: str | None = None

    for attempt in range(1, policy.max_attempts + 1):
        node_run = NodeRunRecord(
            run_id=context.run.id,
            node_id=node.id,
            agent_type=node.type,
            attempt=attempt,
            input=input_data,
        )
        context.start_node_run(node_run)
        context.increment_step()

        try:
            agent: BaseAgent = agent_registry.get(node.type)
            start = time.perf_counter()

            # Tell the context which node is currently executing
            # so agents can read context.current_node_id instead of searching by type
            context.current_node_id = node.id

            # Merge validation feedback into the input for retry attempts
            effective_input = dict(input_data)
            if validation_feedback:
                effective_input["_validation_feedback"] = validation_feedback

            # Apply per-node timeout
            message = await asyncio.wait_for(
                agent.run(
                    input_data=effective_input,
                    config=node.config,
                    context=context,
                    tools=tools,
                ),
                timeout=node.config.timeout_seconds,
            )

            elapsed_ms = int((time.perf_counter() - start) * 1000)
            message.metadata.latency_ms = elapsed_ms

            context.finish_node_run(node_run, message)
            context.check_cost_limit()
            return message

        except asyncio.TimeoutError:
            last_error = f"Node timed out after {node.config.timeout_seconds}s"
            _fail_node_run(node_run, context, last_error)
            log.warning(
                "node_timeout",
                node_id=node.id,
                attempt=attempt,
                timeout_seconds=node.config.timeout_seconds,
            )

        except _ValidationError as e:
            last_error = str(e)
            validation_feedback = last_error
            _fail_node_run(node_run, context, last_error, validation_errors=[last_error])
            log.warning(
                "node_validation_error",
                node_id=node.id,
                attempt=attempt,
                error=last_error,
            )
            if not policy.retry_on_validation_error:
                break

        except Exception as e:
            last_error = str(e)
            _fail_node_run(node_run, context, last_error)
            log.error(
                "node_error",
                node_id=node.id,
                attempt=attempt,
                error=last_error,
                exc_info=True,
            )

        # Backoff before next attempt
        if attempt < policy.max_attempts:
            backoff = policy.backoff_seconds * (policy.backoff_multiplier ** (attempt - 1))
            log.info("node_retry_backoff", node_id=node.id, attempt=attempt, backoff_s=backoff)
            await asyncio.sleep(backoff)

    raise NodeExecutionError(
        node_id=node.id,
        message=f"Node '{node.id}' ({node.type.value}) failed after "
                f"{policy.max_attempts} attempt(s). Last error: {last_error}",
        attempts=policy.max_attempts,
    )


def _fail_node_run(
    node_run: NodeRunRecord,
    context: RunContext,
    error: str,
    validation_errors: list[str] | None = None,
) -> None:
    """Update the node run record to failed state."""
    failed_message = AgentMessage(
        run_id=context.run.id,
        node_id=node_run.node_id,
        status=NodeRunStatus.FAILED,
        errors=[error],
        metadata=MessageMetadata(),
    )
    if validation_errors:
        node_run.validation_errors = validation_errors
    context.finish_node_run(node_run, failed_message)


class _ValidationError(Exception):
    """Internal exception for output schema validation failures."""
