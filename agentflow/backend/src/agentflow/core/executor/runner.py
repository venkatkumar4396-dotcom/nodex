"""
WorkflowRunner — orchestrates the execution of an entire workflow.

Design:
  1. We use the ExecutionGraph's layers for static topology, but actually
     execute nodes dynamically: after each node completes, we evaluate which
     downstream nodes are now "ready" (all predecessors done, edge conditions
     satisfied). This handles conditional branching naturally.

  2. Parallel execution: all "ready" nodes in a given step are gathered with
     asyncio.gather(). This gives us parallel fan-out for free.

  3. Durable execution hook: after each node completes, we call an optional
     persistence callback. In Phase 4 this saves to Postgres. In Phase 1 it's
     a no-op. This means Phase 4 just needs to provide the callback — zero
     engine changes.

  4. The runner is a pure async function, not a class, so it's easy to call
     from both the CLI (Phase 1) and the Arq worker (Phase 4).

  5. Failed nodes: if a node fails after all retries, we mark the run as
     FAILED and stop. Phase 3 will add error handler routing.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any, Callable, Awaitable
from uuid import UUID

import structlog

from agentflow.core.executor.context import (
    CostLimitExceeded,
    RunContext,
    StepLimitExceeded,
)
from agentflow.core.executor.graph import ExecutionGraph, build_execution_graph
from agentflow.core.executor.mapping import evaluate_condition, resolve_data_map
from agentflow.core.executor.node_runner import NodeExecutionError, run_node
from agentflow.core.schemas.workflow import (
    AgentMessage,
    NodeRunStatus,
    RunRecord,
    RunStatus,
    WorkflowDef,
)

log = structlog.get_logger(__name__)

# Callback type for persistence hooks (Phase 4: save node_run to DB)
PersistCallback = Callable[[AgentMessage], Awaitable[None]]


async def _noop_persist(message: AgentMessage) -> None:
    """Default no-op persistence callback used in Phase 1."""
    pass


async def run_workflow(
    workflow: WorkflowDef,
    trigger_data: dict[str, Any] | None = None,
    shared_context: dict[str, Any] | None = None,
    on_node_complete: PersistCallback = _noop_persist,
) -> RunRecord:
    """
    Execute a workflow from start to finish.

    Args:
        workflow: The validated WorkflowDef to execute.
        trigger_data: Initial data from the trigger (manual, webhook, etc.)
        shared_context: Pre-populated shared run context (user timezone, etc.)
        on_node_complete: Async callback called after each node finishes.
                          Phase 4 passes a DB persist function here.

    Returns:
        RunRecord with full execution log (node runs, totals, status).
    """
    run = RunRecord(
        workflow_id=workflow.id,
        workflow_version=workflow.version,
        trigger_data=trigger_data or {},
        shared_context=shared_context or {},
        started_at=time.time(),
        status=RunStatus.RUNNING,
    )
    context = RunContext(run=run, workflow=workflow)
    graph = build_execution_graph(workflow)

    log.info(
        "run_started",
        run_id=str(run.id),
        workflow_id=str(workflow.id),
        workflow_name=workflow.name,
        node_count=len(workflow.nodes),
    )

    # Seed the trigger node's output with trigger_data so downstream nodes
    # can reference it via {{trigger_node_id.output.field}}
    _seed_trigger_outputs(workflow, trigger_data or {}, context)

    # Track how many predecessors each node still has pending
    pending_predecessors: dict[str, int] = {}
    for node_id in graph.node_ids:
        preds = workflow.predecessors(node_id)
        pending_predecessors[node_id] = len(preds)

    # Trigger nodes are pre-seeded — mark them as already completed so the
    # execution loop skips running them through an agent call.
    # This ensures trigger output = trigger_data (not the agent's return value).
    completed: set[str] = set()
    skipped: set[str] = set()
    for node in workflow.nodes:
        if node.type.value.startswith("trigger_"):
            completed.add(node.id)

    # Initial ready set: nodes with no predecessors that AREN'T pre-completed triggers
    # (i.e., the immediate children of trigger nodes)
    ready: set[str] = set()
    for node_id in graph.node_ids:
        if node_id in completed:
            continue
        # Check if all predecessors are already completed (seeded triggers)
        preds = workflow.predecessors(node_id)
        if all(p in completed for p in preds):
            ready.add(node_id)
        # Also add nodes with no predecessors that aren't triggers
        if not preds and node_id not in completed:
            ready.add(node_id)

    try:
        while ready:
            # Execute all ready nodes in parallel
            ready_nodes = [workflow.get_node(nid) for nid in ready]
            ready_nodes = [n for n in ready_nodes if n is not None]
            ready.clear()

            results = await asyncio.gather(
                *[
                    run_node(
                        node=node,
                        input_data=_build_node_input(node.id, workflow, context),
                        context=context,
                    )
                    for node in ready_nodes
                ],
                return_exceptions=True,
            )

            for node, result in zip(ready_nodes, results):
                if isinstance(result, NodeExecutionError):
                    context.run.status = RunStatus.FAILED
                    context.run.error = str(result)
                    log.error(
                        "workflow_node_failed",
                        run_id=str(run.id),
                        node_id=node.id,
                        error=str(result),
                    )
                    context.finalize_run(RunStatus.FAILED, str(result))
                    return run

                if isinstance(result, Exception):
                    raise result

                message: AgentMessage = result
                await on_node_complete(message)
                completed.add(node.id)

                # Evaluate outgoing edges and enqueue newly ready nodes
                for edge in workflow.successors(node.id):
                    # Evaluate edge condition
                    node_output = context.get_node_output(node.id) or {}
                    if not evaluate_condition(edge.condition, node_output):
                        log.info(
                            "edge_condition_false",
                            run_id=str(run.id),
                            edge_id=edge.id,
                            source=edge.source,
                            target=edge.target,
                        )
                        # Mark downstream as skipped if ALL incoming edges skipped
                        _maybe_skip(edge.target, workflow, completed, skipped, context)
                        continue

                    pending_predecessors[edge.target] -= 1
                    if pending_predecessors[edge.target] == 0:
                        if edge.target not in completed and edge.target not in skipped:
                            ready.add(edge.target)

    except (CostLimitExceeded, StepLimitExceeded) as e:
        context.finalize_run(RunStatus.FAILED, str(e))
        return run
    except Exception as e:
        log.error("run_unexpected_error", run_id=str(run.id), error=str(e), exc_info=True)
        context.finalize_run(RunStatus.FAILED, str(e))
        return run

    context.finalize_run(RunStatus.COMPLETED)
    return run


def _seed_trigger_outputs(
    workflow: WorkflowDef,
    trigger_data: dict[str, Any],
    context: RunContext,
) -> None:
    """Pre-populate trigger node outputs from trigger_data."""
    for node in workflow.nodes:
        if node.type.value.startswith("trigger_"):
            context.record_node_output(node.id, trigger_data)


def _build_node_input(
    node_id: str,
    workflow: WorkflowDef,
    context: RunContext,
) -> dict[str, Any]:
    """
    Build the input dict for a node by resolving all incoming edge data_maps.

    The merged input is: shared_context + all resolved edge data_maps.
    Later edges' mappings override earlier ones (last write wins).
    """
    merged: dict[str, Any] = {}

    for edge in workflow.edges:
        if edge.target != node_id:
            continue
        if not edge.data_map:
            # No mapping — pass the entire source output as the input
            source_output = context.get_node_output(edge.source) or {}
            merged.update(source_output)
        else:
            resolved = resolve_data_map(edge.data_map, context)
            merged.update(resolved)

    return merged


def _maybe_skip(
    node_id: str,
    workflow: WorkflowDef,
    completed: set[str],
    skipped: set[str],
    context: RunContext,
) -> None:
    """
    Mark a node as skipped if all of its predecessors have been skipped 
    or produced False conditions.
    
    This is a simple heuristic for Phase 1. Phase 3 will implement proper
    dead-branch detection.
    """
    # Count how many incoming edges have live (non-skipped) sources
    live_predecessors = [
        e for e in workflow.edges
        if e.target == node_id and e.source in completed
    ]
    if not live_predecessors:
        skipped.add(node_id)
        log.info("node_skipped", run_id=str(context.run.id), node_id=node_id)
