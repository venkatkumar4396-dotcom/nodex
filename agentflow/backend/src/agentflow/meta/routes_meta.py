"""
FastAPI endpoints for Meta-Agents:
  - POST /api/meta/architect      → Plain-English goal to validated multi-agent DAG
  - POST /api/meta/run-doctor     → Diagnoses failed runs and proposes RFC 6902 JSON patches
  - POST /api/meta/apply-patch    → Safely applies JSON patches to workflow definition
  - POST /api/meta/evaluator      → Generates 8-case QA test suite or grades workflow output
"""
from __future__ import annotations

import copy
import json
import re
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status

from agentflow.config import settings
from agentflow.core.llm.client import complete
from agentflow.core.schemas.workflow import AgentType
from agentflow.core.tools.registry import register_all_builtin_tools, tool_registry
from agentflow.meta.prompts import (
    build_architect_prompt,
    build_browser_operator_prompt,
    build_evaluator_prompt,
    build_integration_builder_prompt,
    build_marketplace_publisher_prompt,
    build_run_doctor_prompt,
    build_security_red_team_prompt,
)
from agentflow.meta.schemas import (
    ApplyPatchRequest,
    BrowserActionPayload,
    BrowserOperatorStepRequest,
    BrowserOperatorTurnOutput,
    EvaluatorOutput,
    EvaluatorRequest,
    IntegrationBuilderOutput,
    IntegrationBuilderRequest,
    JsonPatchOperation,
    MarketplacePublisherOutput,
    MarketplacePublisherRequest,
    RunDoctorOutput,
    RunDoctorRequest,
    SecurityRedTeamOutput,
    SecurityRedTeamRequest,
    WorkflowArchitectOutput,
    WorkflowArchitectRequest,
)
from agentflow.meta.validator import validate_architect_graph

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/meta", tags=["meta-agents"])


def _extract_json(text: str) -> dict[str, Any]:
    """Extract and parse JSON from LLM output, stripping markdown code blocks if present."""
    clean = text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)
    clean = clean.strip()
    return json.loads(clean)


def _apply_rfc6902_patch(doc: dict[str, Any], patches: list[JsonPatchOperation]) -> dict[str, Any]:
    """
    Minimal, safe pure-Python RFC 6902 patch applier for dictionaries and lists.
    Supports 'replace', 'add', 'remove'.
    """
    result = copy.deepcopy(doc)

    for patch in patches:
        tokens = [t.replace("~1", "/").replace("~0", "~") for t in patch.path.split("/") if t != ""]
        if not tokens:
            continue

        target = result
        for t in tokens[:-1]:
            if isinstance(target, list):
                idx = int(t)
                target = target[idx]
            elif isinstance(target, dict):
                target = target.setdefault(t, {})
            else:
                break

        last_token = tokens[-1]
        if patch.op == "replace":
            if isinstance(target, list):
                target[int(last_token)] = patch.value
            elif isinstance(target, dict):
                target[last_token] = patch.value
        elif patch.op == "add":
            if isinstance(target, list):
                if last_token == "-":
                    target.append(patch.value)
                else:
                    target.insert(int(last_token), patch.value)
            elif isinstance(target, dict):
                target[last_token] = patch.value
        elif patch.op == "remove":
            if isinstance(target, list):
                del target[int(last_token)]
            elif isinstance(target, dict):
                target.pop(last_token, None)

    return result


# ── 1. Workflow Architect ──────────────────────────────────────────────────

@router.post("/architect", response_model=WorkflowArchitectOutput)
async def generate_workflow_architecture(req: WorkflowArchitectRequest) -> WorkflowArchitectOutput:
    """
    Workflow Architect meta-agent.
    Translates a plain-language goal into a validated, runnable workflow graph.
    """
    register_all_builtin_tools()

    valid_types = {t.value for t in AgentType}
    valid_tools = set(tool_registry.list_registered())

    node_catalog_str = "\n".join([f"- {t.value}" for t in AgentType])
    tool_catalog_str = "\n".join([f"- {name}" for name in valid_tools])

    prompt = build_architect_prompt(
        node_catalog=node_catalog_str,
        tool_catalog=tool_catalog_str,
        user_goal=req.user_goal.strip(),
        constraints=req.constraints or "None specified",
    )

    target_model = req.model or settings.default_model

    try:
        resp = await complete(
            messages=[{"role": "user", "content": prompt}],
            model=target_model,
            temperature=0.1,
            max_tokens=4096,
        )
        raw_data = _extract_json(resp.content)
    except Exception as e:
        log.error("architect_llm_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Workflow Architect LLM completion failed: {e!s}",
        )

    try:
        validated_output = WorkflowArchitectOutput.model_validate(raw_data)
    except Exception as e:
        log.error("architect_pydantic_validation_failed", error=str(e), raw=raw_data)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Workflow Architect produced malformed JSON structure: {e!s}",
        )

    if validated_output.error:
        return validated_output

    # Deterministic DAG structural validation
    violations = validate_architect_graph(validated_output, valid_types, valid_tools)
    if violations:
        log.warning("architect_dag_violations_detected", violations=violations)
        # Attempt one automated self-repair pass if violations were detected
        repair_prompt = (
            f"{prompt}\n\n"
            f"PREVIOUS ATTEMPT OUTPUT:\n{resp.content}\n\n"
            f"VALIDATION ERRORS FOUND:\n" + "\n".join(f"- {v}" for v in violations) + "\n\n"
            "Fix ALL validation errors and output the corrected valid JSON graph:"
        )
        try:
            repair_resp = await complete(
                messages=[{"role": "user", "content": repair_prompt}],
                model=target_model,
                temperature=0.0,
                max_tokens=4096,
            )
            repaired_data = _extract_json(repair_resp.content)
            repaired_output = WorkflowArchitectOutput.model_validate(repaired_data)
            repaired_violations = validate_architect_graph(repaired_output, valid_types, valid_tools)
            if not repaired_violations:
                validated_output = repaired_output
                violations = []
            else:
                violations = repaired_violations
        except Exception as repair_exc:
            log.warning("architect_repair_pass_failed", error=str(repair_exc))

    if violations:
        # Include violations in risks so user is fully aware
        for v in violations:
            validated_output.risks.append(f"Validation Warning: {v}")

    # Compute pleasant visual layout positions for canvas
    for idx, node in enumerate(validated_output.nodes):
        if not node.position:
            node.position = {
                "x": float(80 + idx * 300),
                "y": float(180 + (idx % 2) * 50),
            }

    return validated_output


# ── 2. Run Doctor ──────────────────────────────────────────────────────────

@router.post("/run-doctor", response_model=RunDoctorOutput)
async def diagnose_failed_run(req: RunDoctorRequest) -> RunDoctorOutput:
    """
    Run Doctor meta-agent.
    Analyzes a failed workflow trace, identifies the root cause, and generates RFC 6902 patches.
    """
    prompt = build_run_doctor_prompt(
        workflow=json.dumps(req.workflow, indent=2),
        run_trace=json.dumps(req.run_trace, indent=2),
        complaint=req.complaint or "Run failed with an error or incorrect output.",
    )

    target_model = req.model or settings.default_model

    try:
        resp = await complete(
            messages=[{"role": "user", "content": prompt}],
            model=target_model,
            temperature=0.1,
            max_tokens=2048,
        )
        raw_data = _extract_json(resp.content)
        return RunDoctorOutput.model_validate(raw_data)
    except Exception as e:
        log.error("run_doctor_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Run Doctor analysis failed: {e!s}",
        )


@router.post("/apply-patch")
async def apply_doctor_patch(req: ApplyPatchRequest) -> dict[str, Any]:
    """
    Applies JSON patch operations to a workflow definition and returns the patched workflow.
    """
    try:
        patched_workflow = _apply_rfc6902_patch(req.workflow, req.patches)
        return {
            "status": "success",
            "message": f"Successfully applied {len(req.patches)} patch operation(s).",
            "workflow": patched_workflow,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to apply patch operations: {e!s}",
        )


# ── 3. Evaluator (QA) ─────────────────────────────────────────────────────

@router.post("/evaluator", response_model=EvaluatorOutput)
async def evaluate_workflow(req: EvaluatorRequest) -> EvaluatorOutput:
    """
    Evaluator (QA) meta-agent.
    Generates an 8-case test suite or grades workflow execution outputs against quality rubrics.
    """
    prompt = build_evaluator_prompt(
        workflow=json.dumps(req.workflow, indent=2),
        test_cases=json.dumps(req.test_cases or [], indent=2),
        actual_outputs=json.dumps(req.actual_outputs or [], indent=2),
        rubric=json.dumps(req.rubric or {}, indent=2),
        previous_results=json.dumps(req.previous_results or {}, indent=2),
    )

    target_model = req.model or settings.default_model

    try:
        resp = await complete(
            messages=[{"role": "user", "content": prompt}],
            model=target_model,
            temperature=0.2,
            max_tokens=4096,
        )
        raw_data = _extract_json(resp.content)
        return EvaluatorOutput.model_validate(raw_data)
    except Exception as e:
        log.error("evaluator_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluator execution failed: {e!s}",
        )


# ── 4. Integration Builder ────────────────────────────────────────────────

@router.post("/integration-builder", response_model=IntegrationBuilderOutput)
async def build_integration(req: IntegrationBuilderRequest) -> IntegrationBuilderOutput:
    """
    Integration Builder meta-agent.
    Generates a secure connector tool specification from raw API docs or OpenAPI specifications.
    """
    default_schema = json.dumps({
        "type": "function",
        "function": {
            "name": "verb_noun",
            "description": "One sentence description",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    }, indent=2)

    prompt = build_integration_builder_prompt(
        api_docs=req.api_docs,
        goal=req.goal,
        tool_schema=req.tool_schema or default_schema,
    )

    target_model = req.model or settings.default_model

    try:
        resp = await complete(
            messages=[{"role": "user", "content": prompt}],
            model=target_model,
            temperature=0.1,
            max_tokens=4096,
        )
        raw_data = _extract_json(resp.content)
        return IntegrationBuilderOutput.model_validate(raw_data)
    except Exception as e:
        log.error("integration_builder_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Integration Builder failed: {e!s}",
        )


@router.post("/register-connector")
async def register_connector(connector: IntegrationBuilderOutput) -> dict[str, Any]:
    """
    Registers the generated connector actions as executable tools in AgentFlow's tool registry.
    """
    from agentflow.core.tools.base import BaseTool

    registered_tools = []
    for action in connector.actions:
        tool_name = f"{connector.connector_name}_{action.name}".lower().replace(" ", "_")

        class DynamicConnectorTool(BaseTool):
            def __init__(self, act=action, base=connector.base_url, auth=connector.auth, tname=tool_name):
                self._action = act
                self._base = base
                self._auth = auth
                self._tname = tname

            @property
            def name(self) -> str:
                return self._tname

            @property
            def description(self) -> str:
                return f"[{self._action.method}] {self._action.description} (URL: {self._base}{self._action.path})"

            @property
            def parameters_schema(self) -> dict[str, Any]:
                return self._action.args_schema or {
                    "type": "object",
                    "properties": {},
                }

            async def execute(self, **kwargs: Any) -> Any:
                import httpx
                url = f"{self._base.rstrip('/')}/{self._action.path.lstrip('/')}"
                headers = {}
                auth_type = self._auth.get("type", "").lower()
                token = self._auth.get("token_placeholder", "")
                if "bearer" in auth_type:
                    headers["Authorization"] = f"Bearer {token}"
                elif "api_key" in auth_type or "key" in auth_type:
                    headers["X-API-Key"] = token

                async with httpx.AsyncClient(timeout=float(self._action.timeout_seconds)) as client:
                    if self._action.method == "GET":
                        r = await client.get(url, params=kwargs, headers=headers)
                    elif self._action.method in ("POST", "PUT", "PATCH"):
                        r = await client.request(self._action.method, url, json=kwargs, headers=headers)
                    elif self._action.method == "DELETE":
                        r = await client.delete(url, params=kwargs, headers=headers)
                    else:
                        r = await client.get(url, params=kwargs, headers=headers)
                    try:
                        return r.json()
                    except Exception:
                        return {"status_code": r.status_code, "text": r.text}

        tool_registry.register(DynamicConnectorTool())
        registered_tools.append(tool_name)

    return {
        "status": "success",
        "connector_name": connector.connector_name,
        "registered_actions": registered_tools,
        "message": f"Successfully registered {len(registered_tools)} actions into tool registry.",
    }


# ── 5. Security Red-Team ──────────────────────────────────────────────────

@router.post("/red-team", response_model=SecurityRedTeamOutput)
async def red_team_workflow(req: SecurityRedTeamRequest) -> SecurityRedTeamOutput:
    """
    Security Red-Team meta-agent.
    Simulates adversarial attacks (prompt injection, excessive agency, data exfiltration, runaway loops)
    and reports concrete attack examples, severities, and mandatory fixes.
    """
    if not tool_registry.list_registered():
        register_all_builtin_tools()

    tools_list = req.tools or tool_registry.list_registered()

    prompt = build_security_red_team_prompt(
        workflow=json.dumps(req.workflow, indent=2),
        tools=", ".join(tools_list),
    )

    target_model = req.model or settings.default_model

    try:
        resp = await complete(
            messages=[{"role": "user", "content": prompt}],
            model=target_model,
            temperature=0.1,
            max_tokens=4096,
        )
        raw_data = _extract_json(resp.content)
        return SecurityRedTeamOutput.model_validate(raw_data)
    except Exception as e:
        log.error("security_red_team_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Security Red-Team scan failed: {e!s}",
        )


# ── 6. Marketplace Publisher ──────────────────────────────────────────────

@router.post("/publisher", response_model=MarketplacePublisherOutput)
async def publish_workflow_meta(req: MarketplacePublisherRequest) -> MarketplacePublisherOutput:
    """
    Marketplace Publisher meta-agent.
    Sanitizes secrets, drafts documentation and setup steps, assesses safety, and packages workflow.
    """
    prompt = build_marketplace_publisher_prompt(
        workflow=json.dumps(req.workflow, indent=2),
        sample_runs=json.dumps(req.sample_runs or [], indent=2),
        notes=req.notes or "None provided",
    )

    target_model = req.model or settings.default_model

    try:
        resp = await complete(
            messages=[{"role": "user", "content": prompt}],
            model=target_model,
            temperature=0.2,
            max_tokens=4096,
        )
        raw_data = _extract_json(resp.content)
        return MarketplacePublisherOutput.model_validate(raw_data)
    except Exception as e:
        log.error("marketplace_publisher_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Marketplace Publisher failed: {e!s}",
        )


# ── 7. Browser Operator ───────────────────────────────────────────────────

def _check_domain_allowed(url: str, allowed_domains: list[str]) -> bool:
    """Enforce domain allowlist in python code, preventing navigation to unlisted sites."""
    from urllib.parse import urlparse
    if not url:
        return True
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if not domain and parsed.path:
        domain = parsed.path.split("/")[0].lower()
    for allowed in allowed_domains:
        allowed_clean = allowed.lower().strip()
        if domain == allowed_clean or domain.endswith(f".{allowed_clean}"):
            return True
    return False


@router.post("/browser-operator/step", response_model=BrowserOperatorTurnOutput)
async def browser_operator_turn(req: BrowserOperatorStepRequest) -> BrowserOperatorTurnOutput:
    """
    Browser Operator step.
    Receives current page state and history, and produces exactly one validated action.
    Hard domain allowlist and max-step caps are strictly enforced in Python code.
    """
    current_url = req.page_state.get("url", "")
    if current_url and not _check_domain_allowed(current_url, req.allowed_domains):
        return BrowserOperatorTurnOutput(
            thought=f"Access denied: URL '{current_url}' is not in the allowed domains: {req.allowed_domains}",
            action=BrowserActionPayload(type="fail", args={"reason": "Domain not allowed by security policy"}),
            possible_injection=True,
            progress="Blocked by domain allowlist filter.",
        )

    if len(req.history) >= req.max_steps:
        return BrowserOperatorTurnOutput(
            thought=f"Maximum step limit of {req.max_steps} reached.",
            action=BrowserActionPayload(type="finish", args={"result": "Step limit reached. Returning partial findings."}),
            possible_injection=False,
            progress=f"Completed {len(req.history)} steps (limit reached).",
        )

    prompt = build_browser_operator_prompt(
        task=req.task,
        allowed_domains=", ".join(req.allowed_domains),
        page_state=json.dumps(req.page_state, indent=2),
        history=json.dumps(req.history, indent=2),
        max_steps=str(req.max_steps),
    )

    target_model = req.model or settings.default_model

    try:
        resp = await complete(
            messages=[{"role": "user", "content": prompt}],
            model=target_model,
            temperature=0.1,
            max_tokens=2048,
        )
        raw_data = _extract_json(resp.content)
        turn_output = BrowserOperatorTurnOutput.model_validate(raw_data)

        # Enforce domain allowlist if the action is navigate
        if turn_output.action.type == "navigate":
            target_url = turn_output.action.args.get("url", "")
            if not _check_domain_allowed(target_url, req.allowed_domains):
                turn_output.action = BrowserActionPayload(
                    type="fail",
                    args={"reason": f"Target URL '{target_url}' violates domain allowlist {req.allowed_domains}"},
                )
                turn_output.thought += f" [Enforcement Warning: Target URL '{target_url}' blocked by domain allowlist.]"
                turn_output.possible_injection = True

        return turn_output
    except Exception as e:
        log.error("browser_operator_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Browser Operator turn failed: {e!s}",
        )

