"""
Pydantic V2 schemas for Meta-Agents (Workflow Architect, Run Doctor, Evaluator QA).
Strict JSON validation ensures that LLM outputs adhere to the exact contract
before being processed by the engine or presented to the user.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ── 1. Workflow Architect Schemas ──────────────────────────────────────────

class ArchitectNodeConfig(BaseModel):
    model: str = Field(default="openrouter/free")
    system_prompt: str = Field(default="")
    tools: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=60)
    max_loop_iterations: int = Field(default=3)


class ArchitectNode(BaseModel):
    id: str
    type: str
    label: str
    config: ArchitectNodeConfig = Field(default_factory=ArchitectNodeConfig)
    data_map: dict[str, Any] = Field(default_factory=dict)
    position: dict[str, float] | None = None


class ArchitectEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    condition: str | None = None


class WorkflowArchitectOutput(BaseModel):
    summary: str = Field(default="")
    assumptions: list[str] = Field(default_factory=list)
    nodes: list[ArchitectNode] = Field(default_factory=list)
    edges: list[ArchitectEdge] = Field(default_factory=list)
    required_credentials: list[str] = Field(default_factory=list)
    estimated_cost_per_run: Literal["low", "medium", "high", "unknown"] = "low"
    risks: list[str] = Field(default_factory=list)
    error: str | None = None
    missing_capabilities: list[str] = Field(default_factory=list)


class WorkflowArchitectRequest(BaseModel):
    user_goal: str
    constraints: str | None = None
    model: str | None = None


# ── 2. Run Doctor Schemas ──────────────────────────────────────────────────

class JsonPatchOperation(BaseModel):
    op: Literal["add", "remove", "replace", "move", "copy", "test"]
    path: str
    value: Any = None


class RunDoctorOutput(BaseModel):
    status: Literal["diagnosed", "insufficient_data"] = "diagnosed"
    root_cause_node: str = ""
    category: Literal[
        "config_error",
        "bad_prompt",
        "schema_mismatch",
        "missing_credential",
        "tool_failure",
        "rate_limit_or_timeout",
        "model_limitation",
        "bad_upstream_data",
        "runaway_loop",
        "cost_issue",
        "unknown",
    ] = "config_error"
    evidence: str = ""
    explanation: str = ""
    patch: list[JsonPatchOperation] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    safe_to_auto_apply: bool = False
    optimizations: list[str] = Field(default_factory=list)
    how_to_verify: str = ""


class RunDoctorRequest(BaseModel):
    workflow: dict[str, Any]
    run_trace: dict[str, Any]
    complaint: str | None = None
    model: str | None = None


class ApplyPatchRequest(BaseModel):
    workflow: dict[str, Any]
    patches: list[JsonPatchOperation]


# ── 3. Evaluator (QA) Schemas ─────────────────────────────────────────────

class TestCaseScores(BaseModel):
    correctness: float = Field(default=5.0, ge=0.0, le=5.0)
    completeness: float = Field(default=5.0, ge=0.0, le=5.0)
    format_compliance: float = Field(default=5.0, ge=0.0, le=5.0)
    faithfulness: float = Field(default=5.0, ge=0.0, le=5.0)
    safety: float = Field(default=5.0, ge=0.0, le=5.0)
    instruction_following: float = Field(default=5.0, ge=0.0, le=5.0)


class EvaluatorCase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    input: str | dict[str, Any]
    expected_behavior: str = ""
    scores: TestCaseScores = Field(default_factory=TestCaseScores)
    passed: bool = Field(default=True, alias="pass")
    issues: list[str] = Field(default_factory=list)
    evidence: str = ""


class EvaluatorOutput(BaseModel):
    mode: Literal["generate", "grade"] = "generate"
    cases: list[EvaluatorCase] = Field(default_factory=list)
    overall_score: float = Field(default=5.0, ge=0.0, le=5.0)
    pass_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    regressions: list[str] = Field(default_factory=list)
    top_3_fixes: list[str] = Field(default_factory=list)
    verdict: Literal["ship", "fix_first", "block"] = "ship"


class EvaluatorRequest(BaseModel):
    workflow: dict[str, Any]
    mode: Literal["generate", "grade"] = "generate"
    test_cases: list[dict[str, Any]] | None = None
    actual_outputs: list[dict[str, Any]] | None = None
    rubric: dict[str, Any] | None = None
    previous_results: dict[str, Any] | None = None
    model: str | None = None


# ── 4. Integration Builder Schemas ────────────────────────────────────────

class IntegrationActionRetry(BaseModel):
    max_retries: int = 3
    retry_on_status: list[int] = Field(default_factory=lambda: [429, 500, 502, 503, 504])
    backoff_factor: float = 1.5


class IntegrationAction(BaseModel):
    name: str  # verb_noun e.g. "search_records"
    description: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    path: str
    args_schema: dict[str, Any] = Field(default_factory=dict)
    response_mapping: dict[str, Any] = Field(default_factory=dict)
    destructive: bool = False
    retry: IntegrationActionRetry = Field(default_factory=IntegrationActionRetry)
    timeout_seconds: int = 30


class IntegrationTestCase(BaseModel):
    action: str
    sample_input: dict[str, Any] = Field(default_factory=dict)
    expected_output_shape: dict[str, Any] = Field(default_factory=dict)


class IntegrationBuilderOutput(BaseModel):
    connector_name: str = ""
    auth: dict[str, Any] = Field(default_factory=dict)  # e.g. {"type": "Bearer", "token_placeholder": "{{credentials.API_KEY}}"}
    base_url: str = ""
    actions: list[IntegrationAction] = Field(default_factory=list)
    tests: list[IntegrationTestCase] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    security_notes: list[str] = Field(default_factory=list)


class IntegrationBuilderRequest(BaseModel):
    api_docs: str
    goal: str
    tool_schema: str | None = None
    model: str | None = None


# ── 5. Security Red-Team Schemas ──────────────────────────────────────────

class RedTeamFinding(BaseModel):
    id: str
    severity: Literal["critical", "high", "medium", "low"] = "medium"
    nodes: list[str] = Field(default_factory=list)
    attack_example: str
    impact: str
    fix: str


class SecurityRedTeamOutput(BaseModel):
    findings: list[RedTeamFinding] = Field(default_factory=list)
    security_score: int = Field(default=100, ge=0, le=100)
    safe_to_publish: bool = True
    must_fix_before_publish: list[str] = Field(default_factory=list)


class SecurityRedTeamRequest(BaseModel):
    workflow: dict[str, Any]
    tools: list[str] | None = None
    model: str | None = None


# ── 6. Marketplace Publisher Schemas ──────────────────────────────────────

class MarketplacePublisherListing(BaseModel):
    title: str = Field(max_length=80)
    tagline: str = ""
    description: str = ""
    audience: str = ""
    setup_steps: list[str] = Field(default_factory=list)
    credentials: list[str] = Field(default_factory=list)
    inputs: list[dict[str, Any]] = Field(default_factory=list)
    outputs: list[dict[str, Any]] = Field(default_factory=list)
    cost_estimate: str = "low (< $0.05/run)"
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    difficulty: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    setup_minutes: int = 5


class MarketplacePublisherSafety(BaseModel):
    external_actions: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "low"
    concerns: list[str] = Field(default_factory=list)


class MarketplacePublisherOutput(BaseModel):
    sanitized_workflow: dict[str, Any] = Field(default_factory=dict)
    replacements: list[str] = Field(default_factory=list)
    had_secrets: bool = False
    listing: MarketplacePublisherListing = Field(default_factory=MarketplacePublisherListing)
    safety: MarketplacePublisherSafety = Field(default_factory=MarketplacePublisherSafety)
    publish_ready: bool = True
    blocking_issues: list[str] = Field(default_factory=list)


class MarketplacePublisherRequest(BaseModel):
    workflow: dict[str, Any]
    sample_runs: list[dict[str, Any]] | None = None
    notes: str | None = None
    model: str | None = None


# ── 7. Browser Operator Schemas ───────────────────────────────────────────

class BrowserActionPayload(BaseModel):
    type: Literal[
        "navigate",
        "click",
        "type",
        "select",
        "scroll",
        "extract",
        "wait",
        "ask_human",
        "finish",
        "fail",
    ]
    args: dict[str, Any] = Field(default_factory=dict)


class BrowserOperatorTurnOutput(BaseModel):
    thought: str = ""
    action: BrowserActionPayload
    possible_injection: bool = False
    progress: str = ""


class BrowserOperatorStepRequest(BaseModel):
    task: str
    allowed_domains: list[str]
    page_state: dict[str, Any]  # {url, title, visible_text, interactive_elements}
    history: list[dict[str, Any]] = Field(default_factory=list)
    max_steps: int = 20
    model: str | None = None

