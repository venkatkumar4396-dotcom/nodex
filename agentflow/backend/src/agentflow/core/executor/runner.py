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
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from agentflow.core.executor.context import (
    CostLimitExceeded,
    RunContext,
    StepLimitExceeded,
    TimeLimitExceeded,
)
from agentflow.core.executor.graph import build_execution_graph
from agentflow.core.executor.mapping import evaluate_condition, resolve_data_map
from agentflow.core.executor.node_runner import NodeExecutionError, run_node
from agentflow.core.schemas.workflow import (
    AgentMessage,
    EdgeDef,
    JoinPolicy,
    NodeDef,
    NodeRunStatus,
    RunRecord,
    RunStatus,
    WorkflowDef,
)

log = structlog.get_logger(__name__)

# Callback type for persistence hooks (Phase 4: save node_run to DB)
PersistCallback = Callable[[AgentMessage], Awaitable[None]]
StartCallback = Callable[[str], Awaitable[None]]


async def _noop_persist(message: AgentMessage) -> None:
    """Default no-op persistence callback used in Phase 1."""


async def _noop_start(node_id: str) -> None:
    """Default no-op node start callback."""


async def run_workflow(
    workflow: WorkflowDef,
    trigger_data: dict[str, Any] | None = None,
    shared_context: dict[str, Any] | None = None,
    on_node_complete: PersistCallback = _noop_persist,
    on_node_start: StartCallback = _noop_start,
) -> RunRecord:
    """
    Execute a workflow from start to finish.

    Args:
        workflow: The validated WorkflowDef to execute.
        trigger_data: Initial data from the trigger (manual, webhook, etc.)
        shared_context: Pre-populated shared run context (user timezone, etc.)
        on_node_complete: Async callback called after each node finishes.
                          Phase 4 passes a DB persist function here.
        on_node_start: Async callback called right as a node starts executing.

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

    # Track how many forward predecessors each node still has pending (excluding feedback loops)
    def forward_predecessors(nid: str) -> list[str]:
        return [
            e.source for e in workflow.edges
            if e.target == nid and not getattr(e, "is_feedback", False)
        ]

    pending_predecessors: dict[str, int] = {}
    for node_id in graph.node_ids:
        pending_predecessors[node_id] = len(forward_predecessors(node_id))

    # Trigger nodes are pre-seeded — mark them as already completed so the
    # execution loop skips running them through an agent call.
    # This ensures trigger output = trigger_data (not the agent's return value).
    completed: set[str] = set()
    skipped: set[str] = set()
    satisfied_edges: set[str] = set()
    dead_edges: set[str] = set()

    # If resuming a paused run, restore previously completed node outputs
    prior_outputs = (shared_context or {}).get("_completed_node_outputs")
    if prior_outputs:
        for nid, out_val in prior_outputs.items():
            completed.add(nid)
            context.record_node_output(nid, out_val)
            for out_edge in workflow.successors(nid):
                if not getattr(out_edge, "is_feedback", False) and not getattr(out_edge, "is_error_handler", False):
                    if evaluate_condition(out_edge.condition, out_val):
                        satisfied_edges.add(out_edge.id)
                    else:
                        dead_edges.add(out_edge.id)

    for node in workflow.nodes:
        if node.type.value.startswith("trigger_") and node.id not in completed:
            completed.add(node.id)
            for out_edge in workflow.successors(node.id):
                if not getattr(out_edge, "is_feedback", False):
                    satisfied_edges.add(out_edge.id)
            # Emit completed event for trigger node so DB and frontend reflect it
            trig_msg = AgentMessage(
                run_id=run.id,
                node_id=node.id,
                status=NodeRunStatus.COMPLETED,
                input_data=trigger_data or {},
                data=trigger_data or {},
            )
            await on_node_complete(trig_msg)

    ready: set[str] = set()
    for node_id in graph.node_ids:
        if node_id in completed:
            continue
        incoming_forward = [
            e for e in workflow.edges
            if e.target == node_id and not getattr(e, "is_feedback", False)
        ]
        if all(e.id in satisfied_edges for e in incoming_forward):
            ready.add(node_id)

    # Track iteration count per node (for loops/re-runs)
    node_iterations: dict[str, int] = defaultdict(int)
    all_failed_node_ids: set[str] = set()

    try:
        while ready:
            # Budget Governor: enforce run-level time and cost limits
            context.check_budget_limits()

            # Execute all ready nodes in parallel
            ready_nodes = [workflow.get_node(nid) for nid in ready]
            ready_nodes = [n for n in ready_nodes if n is not None]
            ready.clear()

            # Signal node start for all ready nodes
            await asyncio.gather(*[on_node_start(n.id) for n in ready_nodes])

            results = await asyncio.gather(
                *[
                    run_node(
                        node=node,
                        input_data=_build_node_input(node.id, workflow, context),
                        context=context,
                        iteration=node_iterations[node.id] + 1,
                    )
                    for node in ready_nodes
                ],
                return_exceptions=True,
            )

            for node in ready_nodes:
                node_iterations[node.id] += 1

            failed_nodes: list[tuple[NodeDef, Exception]] = []

            for node, result in zip(ready_nodes, results):
                if isinstance(result, (NodeExecutionError, Exception)):
                    # Check for error handler edges (Error Boundary)
                    error_edges = [
                        e for e in workflow.successors(node.id)
                        if getattr(e, "is_error_handler", False)
                    ]
                    if error_edges:
                        log.warning(
                            "workflow_node_failed_routing_to_handler",
                            run_id=str(run.id),
                            node_id=node.id,
                            error=str(result),
                            handler_nodes=[e.target for e in error_edges],
                        )
                        completed.add(node.id)
                        err_payload = {
                            "error": str(result),
                            "status": "failed",
                            "node_id": node.id,
                        }
                        context.record_node_output(node.id, err_payload)
                        fail_msg = AgentMessage(
                            run_id=run.id,
                            node_id=node.id,
                            status=NodeRunStatus.FAILED,
                            data=err_payload,
                            errors=[str(result)],
                        )
                        await on_node_complete(fail_msg)
                        for ee in error_edges:
                            if ee.target not in completed and ee.target not in skipped:
                                ready.add(ee.target)
                        continue

                    # No error handler: isolate failure to this branch
                    log.error(
                        "workflow_node_failed_isolated",
                        run_id=str(run.id),
                        node_id=node.id,
                        error=str(result),
                    )
                    all_failed_node_ids.add(node.id)
                    failed_nodes.append((node, result))
                    completed.add(node.id)
                    context.record_node_output(node.id, {
                        "error": str(result),
                        "status": "failed",
                        "node_id": node.id,
                    })
                    fail_msg = AgentMessage(
                        run_id=run.id,
                        node_id=node.id,
                        status=NodeRunStatus.FAILED,
                        data={"error": str(result), "status": "failed"},
                        errors=[str(result)],
                    )
                    await on_node_complete(fail_msg)

                    # Propagate dead path down this node's outgoing non-feedback edges
                    dead_edge_tasks = []
                    for out_edge in workflow.successors(node.id):
                        if not getattr(out_edge, "is_feedback", False):
                            dead_edge_tasks.append(
                                _handle_edge_resolution(
                                    edge=out_edge,
                                    is_satisfied=False,
                                    workflow=workflow,
                                    completed=completed,
                                    skipped=skipped,
                                    satisfied_edges=satisfied_edges,
                                    dead_edges=dead_edges,
                                    ready=ready,
                                    context=context,
                                    on_node_complete=on_node_complete,
                                )
                            )
                    
                    if dead_edge_tasks:
                        results = await asyncio.gather(*dead_edge_tasks, return_exceptions=True)
                        for e in results:
                            if isinstance(e, Exception):
                                log.error("dead_edge_resolution_failed", error=str(e))
                    continue

                message: AgentMessage = result
                if context.get_node_output(node.id) is None:
                    context.record_node_output(node.id, message.data)
                await on_node_complete(message)

                # Phase 6: Human Approval Gate — pause execution until human signs off
                if message.status == NodeRunStatus.AWAITING_APPROVAL:
                    log.info("workflow_run_awaiting_approval", run_id=str(run.id), node_id=node.id)
                    context.run.status = RunStatus.PAUSED
                    run.status = RunStatus.PAUSED
                    context.run.shared_context["_completed_node_outputs"] = context.get_all_outputs()
                    context.run.shared_context["_completed_nodes"] = list(completed)
                    run.shared_context = context.run.shared_context
                    return run

                completed.add(node.id)

                outgoing = workflow.successors(node.id)
                feedback_edges = [e for e in outgoing if getattr(e, "is_feedback", False)]
                forward_edges = [
                    e for e in outgoing
                    if not getattr(e, "is_feedback", False)
                    and not getattr(e, "is_error_handler", False)
                ]

                node_output = context.get_node_output(node.id) or {}

                # 1. Process feedback / loop edges
                loop_triggered = False
                for f_edge in feedback_edges:
                    if evaluate_condition(f_edge.condition, node_output):
                        target_node = workflow.get_node(f_edge.target)
                        max_iters = (
                            f_edge.max_iterations
                            or (target_node.config.max_loop_iterations if target_node else 3)
                        )
                        target_iters = node_iterations.get(f_edge.target, 0)
                        if target_iters < max_iters:
                            loop_triggered = True
                            log.info(
                                "feedback_loop_triggered",
                                run_id=str(run.id),
                                source=node.id,
                                target=f_edge.target,
                                iteration=target_iters + 1,
                                max_iterations=max_iters,
                            )
                            cycle_nodes = _find_cycle_nodes(node.id, f_edge.target, workflow)
                            for c_node in cycle_nodes:
                                completed.discard(c_node)
                                skipped.discard(c_node)
                                for e in workflow.edges:
                                    if e.source == c_node or e.target == c_node:
                                        satisfied_edges.discard(e.id)
                                        dead_edges.discard(e.id)
                            ready.add(f_edge.target)
                            break
                        log.warning(
                            "feedback_loop_limit_reached",
                            run_id=str(run.id),
                            source=node.id,
                            target=f_edge.target,
                            current_iterations=target_iters,
                            max_iterations=max_iters,
                        )

                if loop_triggered:
                    continue

                # 2. Process forward edges with multi-path branching, default fallback & dead-path elimination
                cond_edges = [e for e in forward_edges if not getattr(e, "is_default", False)]
                default_edges = [e for e in forward_edges if getattr(e, "is_default", False)]

                matched_any = False
                edge_tasks = []

                for edge in cond_edges:
                    is_sat = evaluate_condition(edge.condition, node_output)
                    if is_sat:
                        matched_any = True
                    edge_tasks.append(
                        _handle_edge_resolution(
                            edge=edge,
                            is_satisfied=is_sat,
                            workflow=workflow,
                            completed=completed,
                            skipped=skipped,
                            satisfied_edges=satisfied_edges,
                            dead_edges=dead_edges,
                            ready=ready,
                            context=context,
                            on_node_complete=on_node_complete,
                        )
                    )
                    
                    if not is_sat:
                        log.info(
                            "edge_condition_false",
                            run_id=str(run.id),
                            edge_id=edge.id,
                            source=edge.source,
                            target=edge.target,
                        )

                if not matched_any and default_edges:
                    log.info(
                        "taking_default_edges",
                        run_id=str(run.id),
                        source=node.id,
                        count=len(default_edges),
                    )
                    for edge in default_edges:
                        edge_tasks.append(
                            _handle_edge_resolution(
                                edge=edge,
                                is_satisfied=True,
                                workflow=workflow,
                                completed=completed,
                                skipped=skipped,
                                satisfied_edges=satisfied_edges,
                                dead_edges=dead_edges,
                                ready=ready,
                                context=context,
                                on_node_complete=on_node_complete,
                            )
                        )
                elif matched_any and default_edges:
                    for edge in default_edges:
                        edge_tasks.append(
                            _handle_edge_resolution(
                                edge=edge,
                                is_satisfied=False,
                                workflow=workflow,
                                completed=completed,
                                skipped=skipped,
                                satisfied_edges=satisfied_edges,
                                dead_edges=dead_edges,
                                ready=ready,
                                context=context,
                                on_node_complete=on_node_complete,
                            )
                        )
                        
                if edge_tasks:
                    results = await asyncio.gather(*edge_tasks, return_exceptions=True)
                    for e in results:
                        if isinstance(e, Exception):
                            log.error("edge_resolution_failed", error=str(e))

    except (CostLimitExceeded, StepLimitExceeded, TimeLimitExceeded) as e:
        context.run.shared_context["partial_results"] = context.get_all_outputs()
        context.finalize_run(RunStatus.FAILED, str(e))
        return run
    except Exception as e:
        log.exception("run_unexpected_error", run_id=str(run.id), error=str(e))
        context.finalize_run(RunStatus.FAILED, str(e))
        return run

    # Finalize run: if critical failures occurred with zero completed action nodes, mark run FAILED
    non_trigger_nodes = [
        n.id for n in workflow.nodes
        if not n.type.value.startswith("trigger_")
    ]
    successful_non_trigger = [
        nid for nid in non_trigger_nodes
        if nid in completed and nid not in all_failed_node_ids
    ]

    if all_failed_node_ids and not successful_non_trigger:
        err_msg = f"Workflow failed: node(s) {', '.join(all_failed_node_ids)} failed all attempts."
        context.run.error = err_msg
        context.finalize_run(RunStatus.FAILED, err_msg)
        return run
    elif all_failed_node_ids:
        context.run.error = f"Workflow completed with branch failure in node(s): {', '.join(all_failed_node_ids)}"

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
    Build the input dict for a node by cascading context:
      1. Workflow trigger_data (global initial parameters, e.g. lead_name, company, goal)
      2. Shared run context (excluding internal _ prefixed keys)
      3. Completed ancestor node outputs (cascading pipeline context)
      4. Incoming edges' source outputs and explicit data_maps (highest precedence)
    """
    merged: dict[str, Any] = {}

    # 1. Base workflow trigger inputs
    if context.run.trigger_data:
        merged.update(context.run.trigger_data)

    # 2. Shared context
    if context.run.shared_context:
        merged.update({k: v for k, v in context.run.shared_context.items() if not k.startswith("_")})

    # 3. Ancestor node outputs: find all ancestors reachable backwards via forward edges
    parents: dict[str, list[str]] = defaultdict(list)
    for edge in workflow.edges:
        if not getattr(edge, "is_feedback", False) and not getattr(edge, "is_error_handler", False):
            parents[edge.target].append(edge.source)

    ancestors: set[str] = set()
    queue = list(parents.get(node_id, []))
    while queue:
        p = queue.pop(0)
        if p not in ancestors:
            ancestors.add(p)
            queue.extend(parents.get(p, []))

    # Order ancestors topologically (Kahn's algorithm)
    anc_incoming: dict[str, int] = {a: 0 for a in ancestors}
    for a in ancestors:
        for p in parents.get(a, []):
            if p in ancestors:
                anc_incoming[a] += 1

    executed_order: list[str] = []
    ready_anc = [a for a, deg in anc_incoming.items() if deg == 0]
    while ready_anc:
        curr = ready_anc.pop(0)
        executed_order.append(curr)
        for edge in workflow.edges:
            if edge.source == curr and edge.target in ancestors:
                anc_incoming[edge.target] -= 1
                if anc_incoming[edge.target] == 0:
                    ready_anc.append(edge.target)

    for anc in ancestors:
        if anc not in executed_order:
            executed_order.append(anc)

    for anc_id in executed_order:
        anc_out = context.get_node_output(anc_id)
        if isinstance(anc_out, dict):
            if isinstance(anc_out.get("data_snapshot"), dict):
                merged.update(anc_out["data_snapshot"])
            merged.update(anc_out)

    # 4. Incoming direct edges (direct predecessor outputs and explicit data_maps)
    for edge in workflow.edges:
        if edge.target != node_id:
            continue
        if not edge.data_map:
            # No mapping — pass the entire source output as the input
            source_output = context.get_node_output(edge.source) or {}
            if isinstance(source_output, dict):
                if isinstance(source_output.get("data_snapshot"), dict):
                    merged.update(source_output["data_snapshot"])
                merged.update(source_output)
        else:
            resolved = resolve_data_map(edge.data_map, context)
            merged.update(resolved)

    return merged


def _find_cycle_nodes(
    source_id: str,
    target_id: str,
    workflow: WorkflowDef,
) -> set[str]:
    """
    Find all nodes on forward paths from target_id to source_id (the loop body).
    Uses intersection of forward reach from target_id and backward reach to source_id.
    """
    forward_adj: dict[str, list[str]] = defaultdict(list)
    backward_adj: dict[str, list[str]] = defaultdict(list)
    for edge in workflow.edges:
        if not getattr(edge, "is_feedback", False):
            forward_adj[edge.source].append(edge.target)
            backward_adj[edge.target].append(edge.source)

    reachable_from_target: set[str] = set()
    queue = [target_id]
    while queue:
        curr = queue.pop(0)
        if curr not in reachable_from_target:
            reachable_from_target.add(curr)
            for nxt in forward_adj[curr]:
                if nxt not in reachable_from_target:
                    queue.append(nxt)

    can_reach_source: set[str] = set()
    queue = [source_id]
    while queue:
        curr = queue.pop(0)
        if curr not in can_reach_source:
            can_reach_source.add(curr)
            for prev in backward_adj[curr]:
                if prev not in can_reach_source:
                    queue.append(prev)

    cycle_nodes = reachable_from_target & can_reach_source
    return cycle_nodes or {source_id, target_id}


async def _handle_edge_resolution(
    edge: EdgeDef,
    is_satisfied: bool,
    workflow: WorkflowDef,
    completed: set[str],
    skipped: set[str],
    satisfied_edges: set[str],
    dead_edges: set[str],
    ready: set[str],
    context: RunContext,
    on_node_complete: PersistCallback = _noop_persist,
) -> None:
    """
    Handle the resolution of a forward edge (either satisfied or dead).
    Performs Dead-Path Elimination (DPE) and evaluates node readiness against JoinPolicy.
    """
    if is_satisfied:
        satisfied_edges.add(edge.id)
    else:
        dead_edges.add(edge.id)

    node_id = edge.target
    if node_id in completed or node_id in skipped:
        return

    node = workflow.get_node(node_id)
    if not node:
        return

    incoming_forward = [
        e for e in workflow.edges
        if e.target == node_id
        and not getattr(e, "is_feedback", False)
        and not getattr(e, "is_error_handler", False)
    ]
    if not incoming_forward:
        return

    dead_count = sum(1 for e in incoming_forward if e.id in dead_edges or e.source in skipped)
    satisfied_count = sum(1 for e in incoming_forward if e.id in satisfied_edges)
    total_count = len(incoming_forward)

    # 1. Dead-Path Elimination: all incoming paths are dead
    if dead_count == total_count:
        skipped.add(node_id)
        log.info("node_skipped", run_id=str(context.run.id), node_id=node_id)
        # Notify callback so DB and frontend register the skip
        skip_msg = AgentMessage(
            run_id=context.run.id,
            node_id=node_id,
            status=NodeRunStatus.SKIPPED,
            input_data={},
            data={"status": "skipped", "reason": "Predecessor path condition not met (Dead-Path Elimination)"},
        )
        await on_node_complete(skip_msg)

        # Propagate skip to all outgoing edges
        skip_edge_tasks = []
        for out_edge in workflow.successors(node_id):
            if not getattr(out_edge, "is_feedback", False):
                skip_edge_tasks.append(
                    _handle_edge_resolution(
                        edge=out_edge,
                        is_satisfied=False,
                        workflow=workflow,
                        completed=completed,
                        skipped=skipped,
                        satisfied_edges=satisfied_edges,
                        dead_edges=dead_edges,
                        ready=ready,
                        context=context,
                        on_node_complete=on_node_complete,
                    )
                )
                
        if skip_edge_tasks:
            results = await asyncio.gather(*skip_edge_tasks, return_exceptions=True)
            for e in results:
                if isinstance(e, Exception):
                    log.error("skip_edge_resolution_failed", error=str(e))
        return

    # 2. Check readiness against JoinPolicy
    join_policy = getattr(node.config, "join_policy", JoinPolicy.WAIT_ALL)
    if join_policy == JoinPolicy.WAIT_ANY:
        if satisfied_count >= 1:
            ready.add(node_id)
    else:  # WAIT_ALL: execute when all active non-skipped predecessors have finished
        if satisfied_count + dead_count == total_count and satisfied_count >= 1:
            ready.add(node_id)
