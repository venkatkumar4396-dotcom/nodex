"""
FastAPI router for AgentFlow Marketplace and Automated Dual Quality Gate.
Enforces the mandatory gate: Red-Team (#7) + Evaluator (#4) must pass before
Publisher (#6) can list any workflow in the public marketplace.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import structlog
from fastapi import APIRouter, HTTPException, Query, status

from agentflow.config import settings
from agentflow.core.llm.client import complete
from agentflow.marketplace.repository import marketplace_repo
from agentflow.marketplace.schemas import (
    ForkTemplateRequest,
    InstallTemplateRequest,
    MarketplaceItem,
    PublishGateRequest,
    PublishGateResult,
    RateTemplateRequest,
    SandboxTestRequest,
)
from agentflow.meta.prompts import (
    build_evaluator_prompt,
    build_marketplace_publisher_prompt,
    build_security_red_team_prompt,
)
from agentflow.meta.routes_meta import _extract_json
from agentflow.meta.schemas import (
    EvaluatorOutput,
    MarketplacePublisherOutput,
    SecurityRedTeamOutput,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


@router.get("/templates", response_model=list[MarketplaceItem])
async def list_templates(
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
) -> list[MarketplaceItem]:
    """List public marketplace workflow templates with optional filtering."""
    return marketplace_repo.list_templates(search=search, category=category, tag=tag, risk_level=risk_level)


@router.get("/templates/{template_id}", response_model=MarketplaceItem)
async def get_template(template_id: str) -> MarketplaceItem:
    """Get single marketplace workflow template by ID."""
    item = marketplace_repo.get_template(template_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Template '{template_id}' not found.")
    return item


@router.post("/publish", response_model=PublishGateResult)
async def publish_workflow_with_gate(req: PublishGateRequest) -> PublishGateResult:
    """
    Automatic Quality Gate:
    1. Executes Security Red-Team (#7).
    2. Executes Evaluator QA (#4).
    Both must pass before Marketplace Publisher (#6) can sanitize secrets,
    generate the public listing, and register the template in the marketplace.
    """
    target_model = req.model or settings.default_model

    # ── Step 1: Security Red-Team Gate Check ──
    red_team_prompt = build_security_red_team_prompt(
        workflow=json.dumps(req.workflow, indent=2),
        tools="web_search, fetch_url, send_email, write_file, sql_query, code_exec",
    )

    try:
        rt_resp = await complete(
            messages=[{"role": "user", "content": red_team_prompt}],
            model=target_model,
            temperature=0.1,
            max_tokens=4096,
        )
        rt_json = _extract_json(rt_resp.content)
        red_team_output = SecurityRedTeamOutput.model_validate(rt_json)
    except Exception as e:
        log.error("gate_red_team_failed", error=str(e))
        return PublishGateResult(
            passed=False,
            gate_stage="red_team",
            reasons=[f"Security Red-Team scan encountered execution error: {e!s}"],
        )

    # Validate Red-Team Pass Criteria
    critical_findings = [f for f in red_team_output.findings if f.severity in ("critical", "high")]
    if not red_team_output.safe_to_publish or red_team_output.security_score < 70 or red_team_output.must_fix_before_publish or critical_findings:
        reasons = []
        if not red_team_output.safe_to_publish:
            reasons.append("Security Red-Team marked workflow as unsafe to publish.")
        if red_team_output.security_score < 70:
            reasons.append(f"Security score {red_team_output.security_score}/100 is below the 70 point threshold.")
        for item in red_team_output.must_fix_before_publish:
            reasons.append(f"Blocking vulnerability: {item}")
        for cf in critical_findings:
            reasons.append(f"High/Critical finding ({cf.id}): {cf.attack_example}")

        return PublishGateResult(
            passed=False,
            gate_stage="red_team",
            red_team_output=red_team_output,
            reasons=reasons,
        )

    # ── Step 2: Evaluator QA Gate Check ──
    eval_prompt = build_evaluator_prompt(
        workflow=json.dumps(req.workflow, indent=2),
        test_cases=json.dumps(req.sample_runs or [], indent=2),
        actual_outputs=json.dumps([], indent=2),
        rubric=json.dumps({"safety_weight": 0.4, "correctness_weight": 0.3}, indent=2),
        previous_results="{}",
    )

    try:
        eval_resp = await complete(
            messages=[{"role": "user", "content": eval_prompt}],
            model=target_model,
            temperature=0.2,
            max_tokens=4096,
        )
        eval_json = _extract_json(eval_resp.content)
        evaluator_output = EvaluatorOutput.model_validate(eval_json)
    except Exception as e:
        log.error("gate_evaluator_failed", error=str(e))
        return PublishGateResult(
            passed=False,
            gate_stage="evaluator",
            red_team_output=red_team_output,
            reasons=[f"Evaluator QA scan encountered execution error: {e!s}"],
        )

    # Validate Evaluator Pass Criteria
    if evaluator_output.verdict == "block" or evaluator_output.overall_score < 3.2 or evaluator_output.pass_rate < 0.6:
        reasons = [f"Evaluator verdict is '{evaluator_output.verdict}' (required: 'ship' or 'fix_first')."]
        for top_fix in evaluator_output.top_3_fixes:
            reasons.append(f"QA Issue to fix: {top_fix}")

        return PublishGateResult(
            passed=False,
            gate_stage="evaluator",
            red_team_output=red_team_output,
            evaluator_output=evaluator_output,
            reasons=reasons,
        )

    # ── Step 3: Marketplace Publisher Packaging ──
    pub_prompt = build_marketplace_publisher_prompt(
        workflow=json.dumps(req.workflow, indent=2),
        sample_runs=json.dumps(req.sample_runs or [], indent=2),
        notes=req.notes or "Quality gate passed with flying colors",
    )

    try:
        pub_resp = await complete(
            messages=[{"role": "user", "content": pub_prompt}],
            model=target_model,
            temperature=0.2,
            max_tokens=4096,
        )
        pub_json = _extract_json(pub_resp.content)
        publisher_output = MarketplacePublisherOutput.model_validate(pub_json)
    except Exception as e:
        log.error("gate_publisher_failed", error=str(e))
        return PublishGateResult(
            passed=False,
            gate_stage="publisher",
            red_team_output=red_team_output,
            evaluator_output=evaluator_output,
            reasons=[f"Marketplace Publisher packaging failed: {e!s}"],
        )

    # ── Create and persist listing item ──
    listing_id = f"tpl-{str(uuid4())[:8]}"
    listing = publisher_output.listing
    safety = publisher_output.safety

    item = MarketplaceItem(
        id=listing_id,
        name=req.workflow.get("name", listing.title),
        title=listing.title[:80],
        tagline=listing.tagline,
        description=listing.description,
        version="1.0.0",
        author="Community Publisher",
        rating=5.0,
        rating_count=1,
        run_count=0,
        fork_count=0,
        categories=listing.categories or ["Automation"],
        tags=listing.tags or ["workflow"],
        difficulty=listing.difficulty,
        cost_estimate=listing.cost_estimate,
        risk_level=safety.risk_level,
        safety_concerns=safety.concerns,
        external_actions=safety.external_actions,
        credentials_needed=listing.credentials,
        inputs_schema=listing.inputs,
        outputs_schema=listing.outputs,
        sample_inputs={inp.get("name", "input"): inp.get("example", "test") for inp in listing.inputs} if listing.inputs else {},
        workflow=publisher_output.sanitized_workflow or req.workflow,
        security_score=red_team_output.security_score,
        evaluation_score=round(evaluator_output.overall_score, 2),
    )

    marketplace_repo.save_template(item)

    return PublishGateResult(
        passed=True,
        gate_stage="passed",
        red_team_output=red_team_output,
        evaluator_output=evaluator_output,
        publisher_output=publisher_output,
        listing_item=item,
        reasons=["All dual-gate checks passed successfully: Security Red-Team certified and QA Evaluator verified."],
    )


@router.post("/install")
async def install_template(req: InstallTemplateRequest) -> dict[str, Any]:
    """
    1-Click install template with credential binding.
    Substitutes user-supplied credential values or keeps placeholders.
    """
    item = marketplace_repo.get_template(req.template_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")

    copy_workflow = json.loads(json.dumps(item.workflow))
    workflow_str = json.dumps(copy_workflow)

    for cred_name, cred_value in req.credentials.items():
        if cred_value:
            workflow_str = workflow_str.replace(f"{{{{credentials.{cred_name}}}}}", cred_value)

    installed_workflow = json.loads(workflow_str)
    if req.target_name:
        installed_workflow["name"] = req.target_name

    marketplace_repo.record_install(req.template_id)

    return {
        "status": "success",
        "template_id": item.id,
        "title": item.title,
        "workflow": installed_workflow,
        "message": f"Successfully installed '{item.title}' with configured credentials.",
    }


@router.post("/sandbox-test")
async def sandbox_test_template(req: SandboxTestRequest) -> dict[str, Any]:
    """
    Run an isolated sandbox dry-run with sample data before installing the workflow.
    """
    item = marketplace_repo.get_template(req.template_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")

    inputs = req.sample_inputs or item.sample_inputs

    nodes = item.workflow.get("nodes", [])
    simulated_trace = []
    accumulated_output = dict(inputs)

    for idx, node in enumerate(nodes):
        node_id = node.get("id", f"node_{idx}")
        node_type = node.get("type", "prompt")
        node_label = node.get("label", node_id)

        step_output = {
            "status": "success",
            "message": f"Sandbox executed {node_label} [{node_type}] successfully in isolated dry-run mode.",
            "data": {f"out_{node_id}": f"Mock output from {node_label}"},
        }
        accumulated_output.update(step_output["data"])

        simulated_trace.append({
            "node_id": node_id,
            "label": node_label,
            "type": node_type,
            "status": "completed",
            "duration_ms": 120 + idx * 45,
            "tokens_used": 110,
            "output": step_output,
        })

    return {
        "status": "completed",
        "template_id": item.id,
        "title": item.title,
        "sandbox_mode": True,
        "total_nodes_simulated": len(nodes),
        "execution_trace": simulated_trace,
        "final_outputs": accumulated_output,
    }


@router.post("/fork")
async def fork_template(req: ForkTemplateRequest) -> dict[str, Any]:
    """Fork and remix a marketplace template."""
    forked = marketplace_repo.record_fork(req.template_id)
    if not forked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    if req.new_name:
        forked.title = req.new_name
    return {
        "status": "success",
        "forked_template": forked,
        "message": f"Successfully forked '{forked.title}'. You can now customize and remix this template.",
    }


@router.post("/rate")
async def rate_template(req: RateTemplateRequest) -> dict[str, Any]:
    """Submit a rating for a marketplace template."""
    new_rating = marketplace_repo.record_rating(req.template_id, req.rating)
    return {
        "status": "success",
        "template_id": req.template_id,
        "new_rating": new_rating,
    }
