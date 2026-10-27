"""
Run execution API routes — trigger, list, detail, and live SSE streaming.

Key routes:
  - POST /api/workflows/{id}/run    → trigger a new run (returns run_id immediately)
  - GET  /api/runs                  → list all runs
  - GET  /api/runs/{id}             → get run detail with node runs
  - GET  /api/runs/{id}/stream      → SSE stream of live execution events
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from agentflow.api.events import EventType, RunEvent, event_bus
from agentflow.api.schemas import (
    AnalyticsOverview,
    ApprovalDecision,
    NodeRunOut,
    PendingApprovalItem,
    RunCreate,
    RunDetail,
    RunSummary,
)
from agentflow.core.executor.runner import run_workflow
from agentflow.core.schemas.workflow import (
    AgentMessage,
    NodeRunStatus,
    RunStatus,
    WorkflowDef,
)
from agentflow.db.engine import async_session, get_db_session
from agentflow.db.models import NodeRunModel, RunModel, WorkflowModel

router = APIRouter(tags=["runs"])

# In-memory registry of active background execution tasks
_active_tasks: dict[UUID, asyncio.Task] = {}


# ═══════════════════════════════════════════════════════════════════════════════
# Trigger a run
# ═══════════════════════════════════════════════════════════════════════════════


@router.post(
    "/api/workflows/{workflow_id}/run",
    response_model=RunSummary,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a workflow run",
)
async def trigger_run(
    workflow_id: UUID,
    body: RunCreate,
    db: AsyncSession = Depends(get_db_session),
) -> RunSummary:
    """Trigger a new run of the specified workflow.

    The run starts asynchronously in the background. Use the SSE stream
    endpoint to watch live progress, or poll the run detail endpoint.
    """
    # Load workflow
    wf_model = await db.get(WorkflowModel, workflow_id)
    if not wf_model:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Parse definition
    wf_def = WorkflowDef.model_validate(wf_model.definition)

    # Create the run record in DB with explicit id and timestamps (avoids greenlet_spawn lazy-load errors)
    run_id = uuid4()
    now = datetime.now(UTC)
    run_model = RunModel(
        id=run_id,
        workflow_id=workflow_id,
        status="pending",
        trigger_data=body.trigger_data,
        shared_context=body.shared_context,
        total_tokens=0,
        total_cost_usd=0.0,
        created_at=now,
    )
    db.add(run_model)
    await db.commit()

    # Launch the engine in a background task
    task = asyncio.create_task(
        _execute_run_in_background(run_id, wf_def, body.trigger_data, body.shared_context)
    )
    _active_tasks[run_id] = task

    return RunSummary(
        id=run_id,
        workflow_id=workflow_id,
        status="pending",
        total_tokens=0,
        total_cost_usd=0.0,
        error=None,
        created_at=now,
        started_at=None,
        completed_at=None,
    )


async def _execute_run_in_background(
    run_id: UUID,
    wf_def: WorkflowDef,
    trigger_data: dict,
    shared_context: dict,
) -> None:
    """Background task: execute the workflow and persist results + publish events."""
    bus = event_bus

    # Publish run_started
    await bus.publish(RunEvent(
        run_id=str(run_id),
        event_type=EventType.RUN_STARTED,
        data={"workflow_name": wf_def.name},
        timestamp=time.time(),
    ))

    # Update DB status to running
    async with async_session() as db:
        run_model = await db.get(RunModel, run_id)
        if run_model:
            run_model.status = "running"
            run_model.started_at = datetime.now(UTC)
            await db.commit()

    # Start callback — publishes live SSE event when a node starts running
    async def on_node_start(node_id: str) -> None:
        wf_node = wf_def.get_node(node_id)
        node_agent_type = wf_node.type.value if wf_node else "agent"
        await bus.publish(RunEvent(
            run_id=str(run_id),
            event_type=EventType.NODE_STARTED,
            node_id=node_id,
            data={
                "status": "running",
                "agent_type": node_agent_type,
            },
            timestamp=time.time(),
        ))

    # Persistence callback — saves each node result to DB and publishes SSE events
    async def on_node_complete(message: AgentMessage) -> None:
        # Publish node event
        if message.status == NodeRunStatus.COMPLETED:
            event_type = EventType.NODE_COMPLETED
        elif message.status == NodeRunStatus.SKIPPED:
            event_type = EventType.NODE_SKIPPED
        else:
            event_type = EventType.NODE_FAILED

        wf_node = wf_def.get_node(message.node_id)
        node_agent_type = wf_node.type.value if wf_node else "agent"
        input_payload = getattr(message, "input_data", {}) or {}

        await bus.publish(RunEvent(
            run_id=str(run_id),
            event_type=event_type,
            node_id=message.node_id,
            data={
                "status": message.status.value,
                "agent_type": node_agent_type,
                "input": input_payload,
                "output": message.data,
                "tokens": message.metadata.total_tokens,
                "cost_usd": message.metadata.cost_usd,
                "latency_ms": message.metadata.latency_ms,
            },
            timestamp=time.time(),
        ))

        # Persist node run to DB
        async with async_session() as db:
            node_run = NodeRunModel(
                run_id=run_id,
                node_id=message.node_id,
                agent_type=node_agent_type,
                attempt=message.metadata.attempt,
                status=message.status.value,
                input_data=input_payload,
                output_data=message.data,
                prompt_tokens=message.metadata.prompt_tokens,
                completion_tokens=message.metadata.completion_tokens,
                cost_usd=message.metadata.cost_usd,
                duration_ms=message.metadata.latency_ms,
                error="; ".join(message.errors) if message.errors else None,
                completed_at=datetime.now(UTC),
            )
            db.add(node_run)
            if message.status == NodeRunStatus.AWAITING_APPROVAL:
                rm = await db.get(RunModel, run_id)
                if rm:
                    rm.status = "paused"
            await db.commit()

    try:
        # Run the engine (the same pure-async function from Phase 1-3)
        run_record = await run_workflow(
            workflow=wf_def,
            trigger_data=trigger_data,
            shared_context=shared_context,
            on_node_complete=on_node_complete,
            on_node_start=on_node_start,
        )

        # Update final run status in DB
        final_status = run_record.status.value
        async with async_session() as db:
            run_model = await db.get(RunModel, run_id)
            if run_model:
                run_model.status = final_status
                run_model.total_tokens = run_record.total_tokens
                run_model.total_cost_usd = run_record.total_cost_usd
                run_model.error = run_record.error
                run_model.shared_context = dict(run_record.shared_context)
                if final_status in ("completed", "failed"):
                    run_model.completed_at = datetime.now(UTC)
                await db.commit()

        # Publish event
        if run_record.status == RunStatus.PAUSED:
            await bus.publish(RunEvent(
                run_id=str(run_id),
                event_type=EventType.RUN_PAUSED,
                data={
                    "status": "paused",
                    "total_tokens": run_record.total_tokens,
                    "total_cost_usd": run_record.total_cost_usd,
                    "shared_context": run_record.shared_context,
                },
                timestamp=time.time(),
            ))
        else:
            terminal_event = (
                EventType.RUN_COMPLETED
                if run_record.status == RunStatus.COMPLETED
                else EventType.RUN_FAILED
            )
            await bus.publish(RunEvent(
                run_id=str(run_id),
                event_type=terminal_event,
                data={
                    "status": final_status,
                    "total_tokens": run_record.total_tokens,
                    "total_cost_usd": run_record.total_cost_usd,
                    "error": run_record.error,
                },
                timestamp=time.time(),
            ))

    except asyncio.CancelledError:
        await bus.publish(RunEvent(
            run_id=str(run_id),
            event_type=EventType.RUN_CANCELLED,
            data={"status": "cancelled"},
            timestamp=time.time(),
        ))
        raise

    except Exception as exc:
        # Update DB on unexpected error
        async with async_session() as db:
            run_model = await db.get(RunModel, run_id)
            if run_model:
                run_model.status = "failed"
                run_model.error = str(exc)
                run_model.completed_at = datetime.now(UTC)
                await db.commit()

        await bus.publish(RunEvent(
            run_id=str(run_id),
            event_type=EventType.RUN_FAILED,
            data={"error": str(exc)},
            timestamp=time.time(),
        ))
    finally:
        _active_tasks.pop(run_id, None)


# ═══════════════════════════════════════════════════════════════════════════════
# SSE streaming endpoint
# ═══════════════════════════════════════════════════════════════════════════════


@router.get(
    "/api/runs/{run_id}/stream",
    summary="Live SSE stream of run events",
)
async def stream_run(run_id: UUID):
    """Server-Sent Events stream for live execution monitoring.

    The client connects and receives events as the run progresses:
    - node_started, node_completed, node_failed
    - run_completed, run_failed

    The stream closes automatically when the run finishes.
    """
    async def event_generator():
        async for event in event_bus.subscribe(str(run_id)):
            yield {
                "event": "message",
                "data": json.dumps(event.to_sse_dict()),
            }

    return EventSourceResponse(event_generator())


# ═══════════════════════════════════════════════════════════════════════════════
# Run listing and detail
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/api/runs", response_model=list[RunSummary], summary="List all runs")
async def list_runs(
    workflow_id: UUID | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> list[RunSummary]:
    """List all runs, optionally filtered by workflow_id."""
    stmt = select(RunModel).order_by(RunModel.created_at.desc())
    if workflow_id:
        stmt = stmt.where(RunModel.workflow_id == workflow_id)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        RunSummary(
            id=r.id,
            workflow_id=r.workflow_id,
            status=r.status,
            total_tokens=r.total_tokens,
            total_cost_usd=r.total_cost_usd,
            error=r.error,
            created_at=r.created_at,
            started_at=r.started_at,
            completed_at=r.completed_at,
        )
        for r in rows
    ]


@router.get(
    "/api/runs/pending-approvals",
    response_model=list[PendingApprovalItem],
    summary="Get all paused workflow runs awaiting human approval across the system",
)
async def get_pending_approvals(
    db: AsyncSession = Depends(get_db_session),
) -> list[PendingApprovalItem]:
    """Centralized Human-in-the-Loop review queue for all running workflows."""
    result = await db.execute(
        select(RunModel, WorkflowModel)
        .join(WorkflowModel, RunModel.workflow_id == WorkflowModel.id)
        .where(RunModel.status == "paused")
        .order_by(RunModel.created_at.desc())
    )
    rows = result.all()
    items: list[PendingApprovalItem] = []

    for run_model, wf_model in rows:
        shared_ctx = run_model.shared_context or {}
        pending_data = {}
        target_node_id = "approval"
        message_summary = "Awaiting human review"

        for k, v in shared_ctx.items():
            if k.startswith("pending_approval_"):
                target_node_id = k.replace("pending_approval_", "")
                pending_data = v if isinstance(v, dict) else {}
                break

        try:
            wf_def = WorkflowDef.model_validate(wf_model.definition)
            node_def = wf_def.get_node(target_node_id)
            node_label = node_def.label if node_def else target_node_id.replace("_", " ").title()
            node_type = node_def.type.value if node_def else "human_approval"
        except Exception:
            node_label = target_node_id.replace("_", " ").title()
            node_type = "human_approval"

        if "message" in pending_data:
            message_summary = str(pending_data["message"])
        elif "topic" in pending_data:
            message_summary = f"Review topic: {pending_data['topic']}"

        items.append(
            PendingApprovalItem(
                run_id=run_model.id,
                workflow_id=wf_model.id,
                workflow_name=wf_model.name,
                node_id=target_node_id,
                node_label=node_label,
                node_type=node_type,
                paused_at=run_model.created_at,
                input_snapshot=pending_data,
                prompt_or_message=message_summary,
            )
        )

    return items


@router.get("/api/runs/{run_id}", response_model=RunDetail, summary="Get run detail")
async def get_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RunDetail:
    """Get full run detail including all node execution records."""
    result = await db.execute(
        select(RunModel)
        .options(selectinload(RunModel.node_runs))
        .where(RunModel.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return RunDetail(
        id=run.id,
        workflow_id=run.workflow_id,
        status=run.status,
        trigger_data=run.trigger_data,
        shared_context=run.shared_context,
        total_tokens=run.total_tokens,
        total_cost_usd=run.total_cost_usd,
        error=run.error,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        node_runs=[
            NodeRunOut(
                id=nr.id,
                node_id=nr.node_id,
                agent_type=nr.agent_type,
                attempt=nr.attempt,
                iteration=nr.iteration,
                status=nr.status,
                input_data=nr.input_data or {},
                output_data=nr.output_data,
                prompt_tokens=nr.prompt_tokens,
                completion_tokens=nr.completion_tokens,
                cost_usd=nr.cost_usd,
                duration_ms=nr.duration_ms,
                error=nr.error,
                started_at=nr.started_at,
                completed_at=nr.completed_at,
            )
            for nr in run.node_runs
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 6 & 7: Human Approval, Cancellation & Analytics
# ═══════════════════════════════════════════════════════════════════════════════


@router.post(
    "/api/runs/{run_id}/approve",
    response_model=RunSummary,
    summary="Approve a paused run and resume execution",
)
async def approve_run(
    run_id: UUID,
    body: ApprovalDecision,
    db: AsyncSession = Depends(get_db_session),
) -> RunSummary:
    """Approve a paused run and resume execution through downstream nodes."""
    run_model = await db.get(RunModel, run_id)
    if not run_model:
        raise HTTPException(status_code=404, detail="Run not found")
    if run_model.status != "paused":
        raise HTTPException(
            status_code=400,
            detail=f"Run is not paused (current status: {run_model.status})",
        )

    wf_model = await db.get(WorkflowModel, run_model.workflow_id)
    if not wf_model:
        raise HTTPException(status_code=404, detail="Associated workflow not found")
    wf_def = WorkflowDef.model_validate(wf_model.definition)

    # Determine approval node id
    shared_ctx = dict(run_model.shared_context or {})
    target_node_id = body.node_id
    if not target_node_id:
        for k in shared_ctx:
            if k.startswith("pending_approval_"):
                target_node_id = k.replace("pending_approval_", "")
                break
    if not target_node_id:
        for n in wf_def.nodes:
            if n.type.value == "human_approval":
                target_node_id = n.id
                break
        target_node_id = target_node_id or "approval"

    shared_ctx[f"approval_{target_node_id}"] = {
        "approved": True,
        "reviewer": body.reviewer or "user",
        "notes": body.notes or "",
        "timestamp": time.time(),
    }
    shared_ctx.pop(f"pending_approval_{target_node_id}", None)

    run_model.shared_context = shared_ctx
    run_model.status = "running"
    await db.commit()
    await db.refresh(run_model)

    await event_bus.publish(RunEvent(
        run_id=str(run_id),
        event_type=EventType.RUN_RESUMED,
        node_id=target_node_id,
        data={"approved": True, "reviewer": body.reviewer, "notes": body.notes},
        timestamp=time.time(),
    ))

    # Resume background task
    task = asyncio.create_task(
        _execute_run_in_background(run_id, wf_def, run_model.trigger_data or {}, shared_ctx)
    )
    _active_tasks[run_id] = task

    return RunSummary(
        id=run_model.id,
        workflow_id=run_model.workflow_id,
        status=run_model.status,
        total_tokens=run_model.total_tokens,
        total_cost_usd=run_model.total_cost_usd,
        error=run_model.error,
        created_at=run_model.created_at,
        started_at=run_model.started_at,
        completed_at=run_model.completed_at,
    )


@router.post(
    "/api/runs/{run_id}/reject",
    response_model=RunSummary,
    summary="Reject a paused run",
)
async def reject_run(
    run_id: UUID,
    body: ApprovalDecision,
    db: AsyncSession = Depends(get_db_session),
) -> RunSummary:
    """Reject a paused run and mark it as failed."""
    run_model = await db.get(RunModel, run_id)
    if not run_model:
        raise HTTPException(status_code=404, detail="Run not found")
    if run_model.status != "paused":
        raise HTTPException(
            status_code=400,
            detail=f"Run is not paused (current status: {run_model.status})",
        )

    shared_ctx = dict(run_model.shared_context or {})
    target_node_id = body.node_id or "approval"
    shared_ctx[f"approval_{target_node_id}"] = {
        "approved": False,
        "reviewer": body.reviewer or "user",
        "notes": body.notes or "Rejected by reviewer",
        "timestamp": time.time(),
    }
    shared_ctx.pop(f"pending_approval_{target_node_id}", None)

    run_model.shared_context = shared_ctx
    run_model.status = "failed"
    run_model.error = f"Rejected by {body.reviewer}: {body.notes}" if body.notes else f"Rejected by {body.reviewer}"
    run_model.completed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(run_model)

    await event_bus.publish(RunEvent(
        run_id=str(run_id),
        event_type=EventType.RUN_FAILED,
        node_id=target_node_id,
        data={"error": run_model.error, "rejected": True, "reviewer": body.reviewer, "notes": body.notes},
        timestamp=time.time(),
    ))

    return RunSummary(
        id=run_model.id,
        workflow_id=run_model.workflow_id,
        status=run_model.status,
        total_tokens=run_model.total_tokens,
        total_cost_usd=run_model.total_cost_usd,
        error=run_model.error,
        created_at=run_model.created_at,
        started_at=run_model.started_at,
        completed_at=run_model.completed_at,
    )


@router.post(
    "/api/runs/{run_id}/cancel",
    response_model=RunSummary,
    summary="Cancel an active or paused run",
)
async def cancel_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> RunSummary:
    """Cancel an active or paused execution."""
    run_model = await db.get(RunModel, run_id)
    if not run_model:
        raise HTTPException(status_code=404, detail="Run not found")

    run_model.status = "cancelled"
    run_model.completed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(run_model)

    if run_id in _active_tasks:
        task = _active_tasks.pop(run_id)
        task.cancel()

    await event_bus.publish(RunEvent(
        run_id=str(run_id),
        event_type=EventType.RUN_CANCELLED,
        data={"status": "cancelled"},
        timestamp=time.time(),
    ))

    return RunSummary(
        id=run_model.id,
        workflow_id=run_model.workflow_id,
        status=run_model.status,
        total_tokens=run_model.total_tokens,
        total_cost_usd=run_model.total_cost_usd,
        error=run_model.error,
        created_at=run_model.created_at,
        started_at=run_model.started_at,
        completed_at=run_model.completed_at,
    )


@router.get(
    "/api/analytics",
    response_model=AnalyticsOverview,
    summary="Get aggregated workflow telemetry and usage analytics",
)
async def get_analytics(
    db: AsyncSession = Depends(get_db_session),
) -> AnalyticsOverview:
    """Aggregate run metrics, cost, duration, and top agent usage."""
    runs_res = await db.execute(select(RunModel).order_by(RunModel.created_at.desc()))
    all_runs = runs_res.scalars().all()

    total_runs = len(all_runs)
    completed_runs = sum(1 for r in all_runs if r.status == "completed")
    failed_runs = sum(1 for r in all_runs if r.status == "failed")
    paused_runs = sum(1 for r in all_runs if r.status == "paused")
    cancelled_runs = sum(1 for r in all_runs if r.status == "cancelled")
    total_tokens = sum(r.total_tokens or 0 for r in all_runs)
    total_cost_usd = round(sum(r.total_cost_usd or 0.0 for r in all_runs), 6)

    success_rate = round((completed_runs / total_runs * 100), 1) if total_runs > 0 else 100.0

    durations = [
        (r.completed_at - r.started_at).total_seconds() * 1000
        for r in all_runs
        if r.started_at and r.completed_at and (r.completed_at >= r.started_at)
    ]
    avg_duration_ms = round(sum(durations) / len(durations), 1) if durations else 0.0

    runs_by_status = {
        "completed": completed_runs,
        "failed": failed_runs,
        "paused": paused_runs,
        "cancelled": cancelled_runs,
        "running": sum(1 for r in all_runs if r.status == "running"),
        "pending": sum(1 for r in all_runs if r.status == "pending"),
    }

    node_runs_res = await db.execute(select(NodeRunModel.agent_type))
    agent_types = [row[0] for row in node_runs_res.all()]
    agent_counts: dict[str, int] = defaultdict(int)
    for at in agent_types:
        agent_counts[at] += 1

    top_agents = [
        {"agent_type": at, "count": count, "share": round(count / max(len(agent_types), 1) * 100, 1)}
        for at, count in sorted(agent_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    ]

    recent_runs = [
        RunSummary(
            id=r.id,
            workflow_id=r.workflow_id,
            status=r.status,
            total_tokens=r.total_tokens,
            total_cost_usd=r.total_cost_usd,
            error=r.error,
            created_at=r.created_at,
            started_at=r.started_at,
            completed_at=r.completed_at,
        )
        for r in all_runs[:10]
    ]

    return AnalyticsOverview(
        total_runs=total_runs,
        completed_runs=completed_runs,
        failed_runs=failed_runs,
        paused_runs=paused_runs,
        cancelled_runs=cancelled_runs,
        success_rate=success_rate,
        total_tokens=total_tokens,
        total_cost_usd=total_cost_usd,
        avg_duration_ms=avg_duration_ms,
        runs_by_status=runs_by_status,
        top_agents=top_agents,
        recent_runs=recent_runs,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Single-Node Retry & Standalone Test Execution
# ═══════════════════════════════════════════════════════════════════════════════


@router.post(
    "/api/runs/{run_id}/nodes/{node_id}/retry",
    summary="Retry a single node using cached inputs without re-running the full DAG",
)
async def retry_single_node(
    run_id: UUID,
    node_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Re-executes a single node from a prior run using its cached input payload."""
    from agentflow.core.executor.context import RunContext
    from agentflow.core.executor.node_runner import run_node
    from agentflow.core.schemas.workflow import RunRecord

    # 1. Fetch run & workflow
    run_model = await db.get(RunModel, run_id)
    if not run_model:
        raise HTTPException(status_code=404, detail="Run not found")

    wf_model = await db.get(WorkflowModel, run_model.workflow_id)
    if not wf_model:
        raise HTTPException(status_code=404, detail="Workflow not found")

    wf_def = WorkflowDef.model_validate(wf_model.definition)
    target_node = wf_def.get_node(node_id)
    if not target_node:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found in workflow")

    # 2. Find previous node run or determine cached input
    nr_res = await db.execute(
        select(NodeRunModel)
        .where(NodeRunModel.run_id == run_id, NodeRunModel.node_id == node_id)
        .order_by(NodeRunModel.attempt.desc())
    )
    last_nr = nr_res.scalars().first()
    cached_input = (last_nr.input_data if last_nr else {}) or run_model.trigger_data or {}

    # 3. Build lightweight run context
    run_record = RunRecord(
        id=run_id,
        workflow_id=wf_model.id,
        status=RunStatus(run_model.status) if run_model.status in [s.value for s in RunStatus] else RunStatus.RUNNING,
        trigger_data=run_model.trigger_data or {},
        shared_context=run_model.shared_context or {},
    )
    ctx = RunContext(run=run_record, workflow=wf_def)

    # 4. Broadcast node started event
    await event_bus.publish(RunEvent(
        run_id=str(run_id),
        event_type=EventType.NODE_STARTED,
        node_id=node_id,
        data={"status": "running", "agent_type": target_node.type.value, "is_retry": True},
        timestamp=time.time(),
    ))

    # 5. Run single node
    try:
        msg = await run_node(
            node=target_node,
            input_data=cached_input,
            context=ctx,
            iteration=1,
        )
        status_val = msg.status.value
        output_payload = msg.data
        err_val = None
        latency = msg.metadata.latency_ms
        tokens = msg.metadata.total_tokens
        cost = msg.metadata.cost_usd
    except Exception as exc:
        status_val = NodeRunStatus.FAILED.value
        output_payload = {"error": str(exc), "status": "failed"}
        err_val = str(exc)
        latency = 0
        tokens = 0
        cost = 0.0

    # 6. Save or update NodeRunModel
    new_attempt = (last_nr.attempt + 1) if last_nr else 1
    new_nr = NodeRunModel(
        run_id=run_id,
        node_id=node_id,
        agent_type=target_node.type.value,
        attempt=new_attempt,
        status=status_val,
        input_data=cached_input,
        output_data=output_payload,
        duration_ms=latency,
        prompt_tokens=tokens,
        cost_usd=cost,
        error=err_val,
        completed_at=datetime.now(UTC),
    )
    db.add(new_nr)
    await db.commit()

    # 7. Publish completion event
    evt_type = EventType.NODE_COMPLETED if status_val == "completed" else EventType.NODE_FAILED
    await event_bus.publish(RunEvent(
        run_id=str(run_id),
        event_type=evt_type,
        node_id=node_id,
        data={
            "status": status_val,
            "agent_type": target_node.type.value,
            "input": cached_input,
            "output": output_payload,
            "tokens": tokens,
            "cost_usd": cost,
            "latency_ms": latency,
            "error": err_val,
            "is_retry": True,
        },
        timestamp=time.time(),
    ))

    return {
        "status": status_val,
        "node_id": node_id,
        "input": cached_input,
        "output": output_payload,
        "tokens": tokens,
        "cost_usd": cost,
        "duration_ms": latency,
        "error": err_val,
    }

