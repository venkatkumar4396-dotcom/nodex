"""
Workflow CRUD API routes.

All routes handle the lifecycle of workflow definitions:
  - POST   /api/workflows          → create
  - GET    /api/workflows          → list all
  - GET    /api/workflows/{id}     → get detail
  - PUT    /api/workflows/{id}     → update
  - DELETE /api/workflows/{id}     → delete
"""
from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agentflow.api.schemas import (
    BatchDeleteRequest,
    BatchResponse,
    BatchStatusRequest,
    BatchTagRequest,
    DeployDetail,
    DeployRequest,
    RunSummary,
    WorkflowCreate,
    WorkflowDetail,
    WorkflowGenerateRequest,
    WorkflowSummary,
    WorkflowUpdate,
)
from agentflow.config import settings
from agentflow.core.schemas.workflow import (
    AgentType,
    EdgeDef,
    NodeConfig,
    NodeDef,
    WorkflowDef,
)
from agentflow.db.engine import get_db_session
from agentflow.db.models import RunModel, WorkflowModel

router = APIRouter(prefix="/api/workflows", tags=["workflows"])
log = structlog.get_logger(__name__)


def _model_to_summary(wf: WorkflowModel, runs_info: dict | None = None) -> WorkflowSummary:
    """Convert ORM model to API summary response with execution state and preview."""
    defn = wf.definition or {}
    nodes = defn.get("nodes", [])
    edges = defn.get("edges", [])

    nodes_preview = [
        {
            "id": n.get("id", ""),
            "type": n.get("type", "prompt"),
            "label": n.get("label", ""),
            "x": float(n.get("position", {}).get("x", 0.0) if isinstance(n.get("position"), dict) else getattr(n.get("position", None), "x", 0.0) or 0.0),
            "y": float(n.get("position", {}).get("y", 0.0) if isinstance(n.get("position"), dict) else getattr(n.get("position", None), "y", 0.0) or 0.0),
        }
        for n in nodes
    ]

    edges_preview = [
        {
            "source": e.get("source", ""),
            "target": e.get("target", ""),
            "is_feedback": bool(e.get("is_feedback", False)),
        }
        for e in edges
    ]

    last_run_at = None
    last_run_status = None
    success_rate = None

    if runs_info:
        last_run_at = runs_info.get("last_run_at")
        last_run_status = runs_info.get("last_run_status")
        success_rate = runs_info.get("success_rate")

    # Inferred status or manual status override
    explicit_status = defn.get("status")
    if explicit_status in ("active", "draft", "failed"):
        status_val = explicit_status
    elif last_run_status == "failed":
        status_val = "failed"
    elif last_run_status in ("completed", "running", "paused"):
        status_val = "active"
    else:
        status_val = "draft"

    return WorkflowSummary(
        id=wf.id,
        name=wf.name,
        description=defn.get("description", ""),
        version=wf.version,
        tags=defn.get("tags", []),
        status=status_val,
        environment=defn.get("environment", "development"),
        node_count=len(nodes),
        edge_count=len(edges),
        last_run_at=last_run_at,
        last_run_status=last_run_status,
        success_rate=success_rate,
        nodes_preview=nodes_preview,
        edges_preview=edges_preview,
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )


def _model_to_detail(wf: WorkflowModel) -> WorkflowDetail:
    """Convert ORM model to API detail response."""
    defn = WorkflowDef.model_validate(wf.definition)
    return WorkflowDetail(
        id=wf.id,
        name=wf.name,
        description=defn.description or "",
        version=wf.version,
        tags=defn.tags or [],
        status=defn.status or "draft",
        environment=defn.environment or "development",
        nodes=defn.nodes,
        edges=defn.edges,
        global_max_cost_usd=defn.global_max_cost_usd,
        global_max_steps=defn.global_max_steps,
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )


@router.post(
    "",
    response_model=WorkflowDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workflow",
)
async def create_workflow(
    body: WorkflowCreate,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowDetail:
    """Create a new workflow from the provided definition."""
    wf_def = WorkflowDef(
        name=body.name,
        description=body.description,
        tags=body.tags,
        status=body.status,
        environment=body.environment,
        nodes=body.nodes,
        edges=body.edges,
        global_max_cost_usd=body.global_max_cost_usd,
        global_max_steps=body.global_max_steps,
    )
    model = WorkflowModel(
        id=wf_def.id,
        name=wf_def.name,
        version=wf_def.version,
        definition=wf_def.model_dump(mode="json"),
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return _model_to_detail(model)


@router.get("", response_model=list[WorkflowSummary], summary="List all workflows")
async def list_workflows(
    tag: str | None = None,
    environment: str | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> list[WorkflowSummary]:
    """Return a list of all saved workflows with operational execution stats and topology."""
    # Query workflows
    result = await db.execute(
        select(WorkflowModel).order_by(WorkflowModel.updated_at.desc())
    )
    rows = result.scalars().all()

    # Query recent runs to calculate operational state per workflow
    runs_res = await db.execute(
        select(RunModel.workflow_id, RunModel.status, RunModel.created_at)
        .order_by(RunModel.created_at.desc())
    )
    all_runs = runs_res.all()

    runs_by_wf: dict[UUID, dict] = {}
    for r_wfid, r_status, r_created in all_runs:
        if r_wfid not in runs_by_wf:
            runs_by_wf[r_wfid] = {
                "last_run_at": r_created,
                "last_run_status": r_status,
                "total": 0,
                "completed": 0,
            }
        runs_by_wf[r_wfid]["total"] += 1
        if r_status == "completed":
            runs_by_wf[r_wfid]["completed"] += 1

    summaries: list[WorkflowSummary] = []
    for wf in rows:
        info = runs_by_wf.get(wf.id)
        run_stats = None
        if info:
            run_stats = {
                "last_run_at": info["last_run_at"],
                "last_run_status": info["last_run_status"],
                "success_rate": round(info["completed"] / max(info["total"], 1) * 100, 1),
            }
        summary = _model_to_summary(wf, run_stats)

        # Filter by tag if requested
        if tag and tag.lower() not in [t.lower() for t in summary.tags]:
            continue
        # Filter by environment if requested
        if environment and summary.environment.lower() != environment.lower():
            continue

        summaries.append(summary)

    return summaries


def _parse_uuid_safe(val: str | UUID) -> UUID | None:
    if isinstance(val, UUID):
        return val
    try:
        return UUID(str(val).strip())
    except (ValueError, AttributeError):
        return None


@router.get("/{workflow_id}", response_model=WorkflowDetail, summary="Get workflow detail")
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowDetail:
    """Return the full workflow definition including nodes and edges.
    Supports UUID strings or workflow names/keys with safe fallback.
    """
    uid = _parse_uuid_safe(workflow_id)
    model = None
    if uid:
        model = await db.get(WorkflowModel, uid)

    if not model:
        # Fallback to search by name or key
        result = await db.execute(
            select(WorkflowModel).where(WorkflowModel.name == workflow_id)
        )
        model = result.scalars().first()

    if not model:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return _model_to_detail(model)


@router.put("/{workflow_id}", response_model=WorkflowDetail, summary="Update workflow")
async def update_workflow(
    workflow_id: str,
    body: WorkflowUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowDetail:
    """Update an existing workflow. Increments the version number."""
    uid = _parse_uuid_safe(workflow_id)
    model = await db.get(WorkflowModel, uid) if uid else None
    if not model:
        result = await db.execute(
            select(WorkflowModel).where(WorkflowModel.name == workflow_id)
        )
        model = result.scalars().first()

    if not model:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Load existing definition and merge updates
    existing = WorkflowDef.model_validate(model.definition)

    if body.name is not None:
        existing.name = body.name
        model.name = body.name
    if body.description is not None:
        existing.description = body.description
    if body.tags is not None:
        existing.tags = body.tags
    if body.status is not None:
        existing.status = body.status
    if body.environment is not None:
        existing.environment = body.environment
    if body.nodes is not None:
        existing.nodes = body.nodes
    if body.edges is not None:
        existing.edges = body.edges
    if body.global_max_cost_usd is not None:
        existing.global_max_cost_usd = body.global_max_cost_usd
    if body.global_max_steps is not None:
        existing.global_max_steps = body.global_max_steps

    # Bump version
    existing.version += 1
    model.version = existing.version
    model.definition = existing.model_dump(mode="json")

    await db.commit()
    await db.refresh(model)
    return _model_to_detail(model)


@router.delete(
    "/{workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workflow",
)
async def delete_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a workflow and all its associated runs (cascade)."""
    uid = _parse_uuid_safe(workflow_id)
    model = await db.get(WorkflowModel, uid) if uid else None
    if not model:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await db.delete(model)
    await db.commit()


@router.post(
    "/{workflow_id}/duplicate",
    response_model=WorkflowDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate workflow",
)
async def duplicate_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowDetail:
    """Duplicate an existing workflow with a new ID."""
    uid = _parse_uuid_safe(workflow_id)
    model = await db.get(WorkflowModel, uid) if uid else None
    if not model:
        raise HTTPException(status_code=404, detail="Workflow not found")

    existing = WorkflowDef.model_validate(model.definition)
    new_id = uuid4()
    existing.id = new_id
    existing.name = f"{existing.name} (Copy)"
    existing.version = 1

    new_model = WorkflowModel(
        id=new_id,
        name=existing.name,
        version=1,
        definition=existing.model_dump(mode="json"),
    )
    db.add(new_model)
    await db.commit()
    await db.refresh(new_model)
    return _model_to_detail(new_model)


# ═══════════════════════════════════════════════════════════════════════════════
# Batch Operations & Duplicate Cleanup
# ═══════════════════════════════════════════════════════════════════════════════


@router.post(
    "/batch/delete",
    response_model=BatchResponse,
    summary="Batch delete workflows",
)
async def batch_delete_workflows(
    body: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db_session),
) -> BatchResponse:
    """Delete multiple workflows by IDs in a single transaction."""
    if not body.ids:
        return BatchResponse(affected_count=0, message="No workflows provided")

    result = await db.execute(
        select(WorkflowModel).where(WorkflowModel.id.in_(body.ids))
    )
    models = result.scalars().all()
    count = len(models)
    for m in models:
        await db.delete(m)
    await db.commit()
    return BatchResponse(
        affected_count=count,
        message=f"Successfully deleted {count} workflow(s)",
    )


@router.post(
    "/batch/tag",
    response_model=BatchResponse,
    summary="Batch update workflow tags",
)
async def batch_tag_workflows(
    body: BatchTagRequest,
    db: AsyncSession = Depends(get_db_session),
) -> BatchResponse:
    """Add, remove, or set tags across multiple workflows."""
    if not body.ids or not body.tags:
        return BatchResponse(affected_count=0, message="No changes specified")

    result = await db.execute(
        select(WorkflowModel).where(WorkflowModel.id.in_(body.ids))
    )
    models = result.scalars().all()
    normalized_tags = [t.strip().lower() for t in body.tags if t.strip()]

    for m in models:
        defn = dict(m.definition or {})
        existing_tags = defn.get("tags", [])
        if body.mode == "add":
            updated_tags = list(set(existing_tags + normalized_tags))
        elif body.mode == "remove":
            updated_tags = [t for t in existing_tags if t.lower() not in normalized_tags]
        else:  # set
            updated_tags = list(set(normalized_tags))

        defn["tags"] = updated_tags
        m.definition = defn
        m.version += 1

    await db.commit()
    return BatchResponse(
        affected_count=len(models),
        message=f"Updated tags on {len(models)} workflow(s)",
    )


@router.post(
    "/batch/status",
    response_model=BatchResponse,
    summary="Batch set workflow status",
)
async def batch_status_workflows(
    body: BatchStatusRequest,
    db: AsyncSession = Depends(get_db_session),
) -> BatchResponse:
    """Update status (active, draft, failed) across multiple workflows."""
    if not body.ids:
        return BatchResponse(affected_count=0, message="No workflows specified")

    result = await db.execute(
        select(WorkflowModel).where(WorkflowModel.id.in_(body.ids))
    )
    models = result.scalars().all()

    for m in models:
        defn = dict(m.definition or {})
        defn["status"] = body.status
        m.definition = defn
        m.version += 1

    await db.commit()
    return BatchResponse(
        affected_count=len(models),
        message=f"Set status to '{body.status}' on {len(models)} workflow(s)",
    )


@router.post(
    "/batch/duplicate",
    response_model=BatchResponse,
    summary="Batch duplicate workflows",
)
async def batch_duplicate_workflows(
    body: BatchDeleteRequest,  # re-use list of IDs
    db: AsyncSession = Depends(get_db_session),
) -> BatchResponse:
    """Duplicate multiple workflows simultaneously."""
    if not body.ids:
        return BatchResponse(affected_count=0, message="No workflows specified")

    result = await db.execute(
        select(WorkflowModel).where(WorkflowModel.id.in_(body.ids))
    )
    models = result.scalars().all()

    for m in models:
        existing = WorkflowDef.model_validate(m.definition)
        new_id = uuid4()
        existing.id = new_id
        existing.name = f"{existing.name} (Copy)"
        existing.version = 1
        new_model = WorkflowModel(
            id=new_id,
            name=existing.name,
            version=1,
            definition=existing.model_dump(mode="json"),
        )
        db.add(new_model)

    await db.commit()
    return BatchResponse(
        affected_count=len(models),
        message=f"Duplicated {len(models)} workflow(s)",
    )


@router.post(
    "/cleanup-duplicates",
    response_model=BatchResponse,
    summary="Automated duplicate workflow cleanup",
)
async def cleanup_duplicate_workflows(
    db: AsyncSession = Depends(get_db_session),
) -> BatchResponse:
    """Identify duplicate workflows by name and delete older redundant copies, keeping latest."""
    result = await db.execute(
        select(WorkflowModel).order_by(WorkflowModel.updated_at.desc())
    )
    all_wfs = result.scalars().all()

    seen_names: set[str] = set()
    to_delete: list[WorkflowModel] = []

    for wf in all_wfs:
        norm_name = wf.name.strip().lower()
        if norm_name in seen_names:
            to_delete.append(wf)
        else:
            seen_names.add(norm_name)

    del_count = len(to_delete)
    for m in to_delete:
        await db.delete(m)

    await db.commit()
    return BatchResponse(
        affected_count=del_count,
        message=f"Cleaned up {del_count} redundant duplicate workflow(s). Kept {len(seen_names)} distinct graphs.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# One-Click Deployment Modes
# ═══════════════════════════════════════════════════════════════════════════════


@router.post(
    "/{workflow_id}/deploy",
    response_model=DeployDetail,
    summary="One-click deploy workflow to production REST/Webhook endpoint",
)
async def deploy_workflow(
    workflow_id: UUID,
    body: DeployRequest,
    db: AsyncSession = Depends(get_db_session),
) -> DeployDetail:
    """Turn any saved workflow into a production endpoint with authentication and embed code."""
    model = await db.get(WorkflowModel, workflow_id)
    if not model:
        raise HTTPException(status_code=404, detail="Workflow not found")

    defn = dict(model.definition or {})
    defn["environment"] = body.environment
    defn["status"] = "active"
    api_key = f"af_live_{str(model.id).replace('-', '')[:16]}"
    defn["api_key"] = api_key
    model.definition = defn
    await db.commit()

    endpoint = f"/api/deploy/{model.id}/execute"
    webhook = f"/api/deploy/{model.id}/webhook"

    curl_cmd = (
        f'curl -X POST "http://localhost:8000{endpoint}" \\\n'
        f'  -H "Authorization: Bearer {api_key}" \\\n'
        '  -H "Content-Type: application/json" \\\n'
        '  -d \'{"lead_name": "Acme Partner", "company": "Acme Corp"}\''
    )

    python_snippet = (
        "import requests\n\n"
        f'res = requests.post(\n'
        f'    "http://localhost:8000{endpoint}",\n'
        f'    headers={{"Authorization": "Bearer {api_key}"}},\n'
        '    json={"lead_name": "Acme Partner", "company": "Acme Corp"},\n'
        ")\n"
        "print(res.json())\n"
    )

    js_snippet = (
        f'const res = await fetch("http://localhost:8000{endpoint}", {{\n'
        '  method: "POST",\n'
        f'  headers: {{\n    "Authorization": "Bearer {api_key}",\n    "Content-Type": "application/json"\n  }},\n'
        '  body: JSON.stringify({ lead_name: "Acme Partner", company: "Acme Corp" })\n'
        '});\n'
        'const data = await res.json();\n'
    )

    widget_snippet = (
        f'<script src="https://cdn.agentflow.ai/widget.v1.js" '
        f'data-workflow="{model.id}" '
        f'data-key="{api_key}"></script>\n'
        '<div id="agentflow-container"></div>'
    )

    return DeployDetail(
        workflow_id=model.id,
        workflow_name=model.name,
        endpoint_url=endpoint,
        webhook_url=webhook,
        api_key=api_key,
        curl_example=curl_cmd,
        python_example=python_snippet,
        js_example=js_snippet,
        widget_snippet=widget_snippet,
        deployed_at=datetime.now(UTC),
    )


@router.post(
    "/deploy/{workflow_id}/execute",
    response_model=RunSummary,
    summary="Execute deployed workflow via REST API",
)
async def execute_deployed_workflow(
    workflow_id: UUID,
    payload: dict,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db_session),
) -> RunSummary:
    """Execute a deployed workflow with optional API Key authorization."""
    from agentflow.api.routes_runs import trigger_run
    from agentflow.api.schemas import RunCreate

    model = await db.get(WorkflowModel, workflow_id)
    if not model:
        raise HTTPException(status_code=404, detail="Deployed workflow not found")

    defn = model.definition or {}
    expected_key = defn.get("api_key")
    if expected_key:
        token = ""
        if authorization and authorization.startswith("Bearer "):
            token = authorization[7:].strip()
        if token != expected_key:
            raise HTTPException(status_code=401, detail="Invalid API Key authentication")

    run_req = RunCreate(trigger_data=payload, shared_context={})
    return await trigger_run(workflow_id=workflow_id, body=run_req, db=db)


def _synthesize_workflow(prompt: str, custom_name: str | None = None) -> WorkflowDef:
    p_lower = prompt.lower()
    wf_id = uuid4()

    if any(k in p_lower for k in ("approval", "review", "human", "sign-off", "gate", "compliance")):
        name = custom_name or "Human-in-the-Loop Review Pipeline"
        nodes = [
            NodeDef(
                id="trigger_input",
                type=AgentType.TRIGGER_MANUAL,
                label="Incoming Request",
                position_x=80,
                position_y=220,
                config=NodeConfig(system_prompt="Intake user submission for human-gated processing."),
            ),
            NodeDef(
                id="research_agent",
                type=AgentType.RESEARCH,
                label="Analysis & Fact Extraction",
                position_x=400,
                position_y=220,
                config=NodeConfig(
                    system_prompt=f"Analyze input in depth for: {prompt}. Extract critical risks, key points, and metrics.",
                    tools=["web_search"],
                ),
            ),
            NodeDef(
                id="human_approval_gate",
                type=AgentType.HUMAN_APPROVAL,
                label="Human Approval Gate",
                position_x=720,
                position_y=220,
                config=NodeConfig(
                    system_prompt="Verify analysis accuracy and sign off before publication or action.",
                ),
            ),
            NodeDef(
                id="final_writer",
                type=AgentType.WRITER,
                label="Executive Report Generator",
                position_x=1040,
                position_y=220,
                config=NodeConfig(
                    system_prompt="Compile final executive report incorporating approved findings and reviewer comments.",
                ),
            ),
        ]
        edges = [
            EdgeDef(id="e1", source="trigger_input", target="research_agent"),
            EdgeDef(id="e2", source="research_agent", target="human_approval_gate"),
            EdgeDef(id="e3", source="human_approval_gate", target="final_writer"),
        ]

    elif any(k in p_lower for k in ("rag", "doc", "document", "kb", "knowledge", "faq", "search", "retriev")):
        name = custom_name or "RAG Knowledge Retrieval & QA Pipeline"
        nodes = [
            NodeDef(
                id="user_query_trigger",
                type=AgentType.TRIGGER_MANUAL,
                label="User Query Trigger",
                position_x=80,
                position_y=220,
                config=NodeConfig(system_prompt="Receive user search query or question."),
            ),
            NodeDef(
                id="rag_retriever",
                type=AgentType.RAG,
                label="RAG Document Retriever",
                position_x=400,
                position_y=220,
                config=NodeConfig(
                    system_prompt=f"Retrieve and cite most relevant knowledge passages for query regarding: {prompt}.",
                    tools=["read_file"],
                ),
            ),
            NodeDef(
                id="answer_synthesizer",
                type=AgentType.SUMMARIZER,
                label="Grounded Synthesis Agent",
                position_x=720,
                position_y=220,
                config=NodeConfig(
                    system_prompt="Synthesize cited context into a clear, comprehensive, and accurate direct answer.",
                ),
            ),
            NodeDef(
                id="quality_auditor",
                type=AgentType.REVIEWER,
                label="Hallucination & Quality Auditor",
                position_x=1040,
                position_y=220,
                config=NodeConfig(
                    system_prompt="Audit answer against cited sources to ensure zero hallucination and high clarity.",
                ),
            ),
        ]
        edges = [
            EdgeDef(id="e1", source="user_query_trigger", target="rag_retriever"),
            EdgeDef(id="e2", source="rag_retriever", target="answer_synthesizer"),
            EdgeDef(id="e3", source="answer_synthesizer", target="quality_auditor"),
        ]

    elif any(k in p_lower for k in ("supervisor", "plan", "complex", "subtask", "multi-agent", "orchestrat")):
        name = custom_name or "Supervisor Multi-Agent Task Orchestrator"
        nodes = [
            NodeDef(
                id="goal_trigger",
                type=AgentType.TRIGGER_MANUAL,
                label="High-Level Goal",
                position_x=80,
                position_y=220,
                config=NodeConfig(system_prompt="Capture target objective and requirements."),
            ),
            NodeDef(
                id="supervisor_orchestrator",
                type=AgentType.SUPERVISOR,
                label="Supervisor Agent",
                position_x=380,
                position_y=220,
                config=NodeConfig(
                    system_prompt=f"Deconstruct objective into actionable subtasks: {prompt}.",
                ),
            ),
            NodeDef(
                id="domain_researcher",
                type=AgentType.RESEARCH,
                label="Specialized Researcher",
                position_x=680,
                position_y=140,
                config=NodeConfig(
                    system_prompt="Execute research tasks from supervisor plan.",
                    tools=["web_search"],
                ),
            ),
            NodeDef(
                id="code_specialist",
                type=AgentType.CODE,
                label="Technical Specialist",
                position_x=680,
                position_y=320,
                config=NodeConfig(
                    system_prompt="Execute code and data tasks identified by supervisor.",
                ),
            ),
            NodeDef(
                id="master_synthesizer",
                type=AgentType.WRITER,
                label="Master Synthesizer",
                position_x=1020,
                position_y=220,
                config=NodeConfig(
                    system_prompt="Consolidate research and technical deliverables into final cohesive output.",
                ),
            ),
        ]
        edges = [
            EdgeDef(id="e1", source="goal_trigger", target="supervisor_orchestrator"),
            EdgeDef(id="e2", source="supervisor_orchestrator", target="domain_researcher"),
            EdgeDef(id="e3", source="supervisor_orchestrator", target="code_specialist"),
            EdgeDef(id="e4", source="domain_researcher", target="master_synthesizer"),
            EdgeDef(id="e5", source="code_specialist", target="master_synthesizer"),
        ]

    elif any(k in p_lower for k in ("code", "developer", "git", "pr", "bug", "refactor")):
        name = custom_name or "Automated Code Review & Triage Pipeline"
        nodes = [
            NodeDef(
                id="git_trigger",
                type=AgentType.TRIGGER_WEBHOOK,
                label="Webhook Trigger",
                position_x=80,
                position_y=220,
                config=NodeConfig(system_prompt="Triggered on pull request or code push event."),
            ),
            NodeDef(
                id="security_analyst",
                type=AgentType.CODE,
                label="Code & Bug Analyzer",
                position_x=400,
                position_y=220,
                config=NodeConfig(
                    system_prompt="Analyze code changes for security vulnerabilities, syntax errors, and edge cases.",
                ),
            ),
            NodeDef(
                id="human_approval_gate",
                type=AgentType.HUMAN_APPROVAL,
                label="Tech Lead Approval",
                position_x=720,
                position_y=220,
                config=NodeConfig(system_prompt="Review code analysis and authorize merge or deployment."),
            ),
            NodeDef(
                id="pr_commenter",
                type=AgentType.WRITER,
                label="PR Summary & Release Note",
                position_x=1040,
                position_y=220,
                config=NodeConfig(
                    system_prompt="Draft clear summary of code changes, approval notes, and release highlights.",
                ),
            ),
        ]
        edges = [
            EdgeDef(id="e1", source="git_trigger", target="security_analyst"),
            EdgeDef(id="e2", source="security_analyst", target="human_approval_gate"),
            EdgeDef(id="e3", source="human_approval_gate", target="pr_commenter"),
        ]

    else:
        words = [w.capitalize() for w in prompt.split()[:4]]
        name = custom_name or f"{' '.join(words)} Pipeline"
        nodes = [
            NodeDef(
                id="trigger_input",
                type=AgentType.TRIGGER_MANUAL,
                label="Workflow Trigger",
                position_x=80,
                position_y=220,
                config=NodeConfig(system_prompt=f"Trigger execution for: {prompt}"),
            ),
            NodeDef(
                id="context_gatherer",
                type=AgentType.TOOL,
                label="Context Gatherer",
                position_x=420,
                position_y=220,
                config=NodeConfig(
                    system_prompt=f"Gather detailed contextual information and verified facts for: {prompt}",
                    tools=["web_search"],
                ),
            ),
            NodeDef(
                id="reasoning_engine",
                type=AgentType.PROMPT,
                label="Reasoning Engine",
                position_x=760,
                position_y=220,
                config=NodeConfig(
                    system_prompt="Analyze contextual data, evaluate trade-offs, and generate structured findings.",
                ),
            ),
            NodeDef(
                id="output_synthesizer",
                type=AgentType.SYNTHESIZER,
                label="Deliverable Synthesizer",
                position_x=1100,
                position_y=220,
                config=NodeConfig(
                    system_prompt=f"Synthesize final executive deliverable for: {prompt}",
                ),
            ),
        ]
        edges = [
            EdgeDef(id="e1", source="trigger_input", target="context_gatherer"),
            EdgeDef(id="e2", source="context_gatherer", target="reasoning_engine"),
            EdgeDef(id="e3", source="reasoning_engine", target="output_synthesizer"),
        ]

    return WorkflowDef(
        id=wf_id,
        name=name,
        nodes=nodes,
        edges=edges,
        global_max_cost_usd=5.0,
        global_max_steps=50,
    )


async def _ai_generate_workflow(prompt: str, custom_name: str | None = None) -> WorkflowDef:
    """Genuinely invoke LiteLLM to generate a customized DAG workflow matching the user's objective."""
    import json
    import uuid

    from agentflow.core.llm.client import complete

    system_prompt = (
        "You are an expert AI DAG Workflow Architect for AgentFlow.\n"
        "Design a custom, production-ready multi-agent DAG workflow tailored directly to the user's objective.\n\n"
        "Supported Core Node Types:\n"
        "- 'trigger_manual': Input entry point kickstarting DAG execution.\n"
        "- 'prompt': LLM reasoning, persona execution, instructions, and analysis.\n"
        "- 'tool': Autonomous tool-calling agent (supported tools: ['web_search', 'http_tool', 'email_tool']).\n"
        "- 'router': Decision classification and conditional branch routing.\n"
        "- 'human_approval': Human gate pausing workflow for sign-off/review.\n"
        "- 'code': Code computation, data transformation, and scripting.\n"
        "- 'synthesizer': Multi-branch aggregation and executive report delivery.\n\n"
        "Output ONLY a valid JSON object with this exact structure:\n"
        "{\n"
        '  "name": "Concise Workflow Title",\n'
        '  "nodes": [\n'
        '    {\n'
        '      "id": "snake_case_id",\n'
        '      "type": "one of the supported types",\n'
        '      "label": "Human readable label",\n'
        '      "position_x": 80,\n'
        '      "position_y": 220,\n'
        '      "config": {\n'
        '        "system_prompt": "Specific instructions for this agent",\n'
        '        "tools": []\n'
        '      }\n'
        '    }\n'
        '  ],\n'
        '  "edges": [\n'
        '    {\n'
        '      "id": "e1",\n'
        '      "source": "source_node_id",\n'
        '      "target": "target_node_id",\n'
        '      "label": "optional label",\n'
        '      "condition": null\n'
        '    }\n'
        '  ]\n'
        "}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Build a multi-agent workflow for this objective: {prompt}"},
    ]

    try:
        resp = await complete(
            messages=messages,
            temperature=0.2,
            max_tokens=3000,
            response_format={"type": "json_object"},
        )
        content = resp.content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        data = json.loads(content)

        wf_id = str(uuid.uuid4())
        name = custom_name or data.get("name") or f"{prompt[:40]} Workflow"
        nodes = []
        node_ids = set()

        raw_nodes = data.get("nodes", [])
        if raw_nodes:
            for idx, n in enumerate(raw_nodes):
                n_id = str(n.get("id") or f"node_{idx+1}")
                node_ids.add(n_id)
                n_type_str = n.get("type", "prompt")
                try:
                    agent_type = AgentType(n_type_str)
                except ValueError:
                    agent_type = AgentType.PROMPT

                cfg = n.get("config", {})
                tools_list = cfg.get("tools", [])
                if not isinstance(tools_list, list):
                    tools_list = []

                nodes.append(
                    NodeDef(
                        id=n_id,
                        type=agent_type,
                        label=n.get("label", n_id.replace("_", " ").title()),
                        position_x=float(n.get("position_x", 80 + idx * 340)),
                        position_y=float(n.get("position_y", 220)),
                        config=NodeConfig(
                            system_prompt=cfg.get("system_prompt", f"Agent instruction for {prompt}"),
                            tools=[t for t in tools_list if t in ("web_search", "http_tool", "email_tool")],
                            model=cfg.get("model", settings.default_model),
                            timeout_seconds=int(cfg.get("timeout_seconds", 60)),
                        ),
                    )
                )

            edges = []
            for idx, e in enumerate(data.get("edges", [])):
                src = e.get("source")
                tgt = e.get("target")
                if src in node_ids and tgt in node_ids:
                    edges.append(
                        EdgeDef(
                            id=str(e.get("id") or f"e_{idx+1}"),
                            source=src,
                            target=tgt,
                            label=e.get("label"),
                            condition=e.get("condition"),
                            is_feedback=bool(e.get("is_feedback", False)),
                            is_default=bool(e.get("is_default", False)),
                            is_error_handler=bool(e.get("is_error_handler", False)),
                        )
                    )

            if nodes and edges:
                log.info("ai_workflow_generated_successfully", name=name, nodes=len(nodes), edges=len(edges))
                return WorkflowDef(
                    id=wf_id,
                    name=name,
                    nodes=nodes,
                    edges=edges,
                    global_max_cost_usd=5.0,
                    global_max_steps=50,
                )
    except Exception as exc:
        log.warning("ai_workflow_generation_fallback", error=str(exc))

    return _synthesize_workflow(prompt, custom_name)


@router.post(
    "/generate",
    response_model=WorkflowDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Generate workflow with AI from natural language",
)
async def generate_workflow(
    body: WorkflowGenerateRequest,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowDetail:
    """Generate a complete DAG workflow definition from a natural language prompt."""
    wf_def = await _ai_generate_workflow(body.prompt, body.name)
    model = WorkflowModel(
        id=wf_def.id,
        name=wf_def.name,
        version=wf_def.version,
        definition=wf_def.model_dump(mode="json"),
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return _model_to_detail(model)

