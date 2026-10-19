"""
LiteLLM wrapper — provider-agnostic LLM client.

Supported providers (set model string accordingly):
  - Kimi/Moonshot: "moonshot/moonshot-v1-32k"  → set MOONSHOT_API_KEY
  - OpenAI:        "gpt-4o-mini"               → set OPENAI_API_KEY
  - Anthropic:     "claude-3-5-sonnet-20241022" → set ANTHROPIC_API_KEY
  - Gemini:        "gemini/gemini-1.5-flash"   → set GEMINI_API_KEY
  - Ollama (local):"ollama/llama3"             → no key needed

Design:
  1. We wrap LiteLLM so we can add unified cost tracking, swap it later,
     and handle provider quirks (e.g. JSON mode support) in one place.
  2. We always use the async API (acompletion) for parallel node execution.
  3. API keys are loaded from settings (env vars) on import.
  4. Cost: LiteLLM provides cost for known models; 0 for unknown/local.
"""
from __future__ import annotations

import os
import re
from typing import Any

import structlog

from agentflow.config import settings

log = structlog.get_logger(__name__)

# ── Inject API keys into environment for LiteLLM to pick up ─────────────────
if settings.moonshot_api_key:
    os.environ["MOONSHOT_API_KEY"] = settings.moonshot_api_key
if settings.openrouter_api_key:
    os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key
if settings.openai_api_key:
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key
if settings.anthropic_api_key:
    os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
if settings.gemini_api_key:
    os.environ["GEMINI_API_KEY"] = settings.gemini_api_key

# Models that natively support response_format={"type": "json_object"} (JSON mode)
# Kimi/Moonshot does NOT support response_format — we use prompt-only JSON mode for it.
_JSON_MODE_SUPPORTED_PREFIXES = (
    "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo",
    "gemini/", "vertex_ai/",
)


def supports_json_mode(model: str) -> bool:
    """Return True if this model supports response_format={type: json_object}."""
    return any(model.startswith(p) for p in _JSON_MODE_SUPPORTED_PREFIXES)


class LLMResponse:
    """Normalized LLM response, independent of provider."""

    def __init__(
        self,
        content: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost_usd: float,
        model: str,
    ) -> None:
        self.content = content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.cost_usd = cost_usd
        self.model = model

    def __repr__(self) -> str:
        return (
            f"LLMResponse(model={self.model!r}, "
            f"tokens={self.total_tokens}, "
            f"cost=${self.cost_usd:.6f})"
        )


def _clean_reasoning_tokens(text: str) -> str:
    """Cleanly strip chain-of-thought blocks and thinking preambles from LLM output."""
    if not text:
        return ""
    # 1. Remove XML/HTML style thinking tags like <think>...</think>, <thought>...</thought>, <reasoning>...</reasoning>
    cleaned = re.sub(
        r"<(?:think|thought|reasoning)[^>]*>[\s\S]*?</(?:think|thought|reasoning)>",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Also handle unclosed opening tags at the beginning if model truncated before closing tag
    if re.search(r"<(?:think|thought|reasoning)>", cleaned, re.IGNORECASE) and not re.search(
        r"</(?:think|thought|reasoning)>", cleaned, re.IGNORECASE
    ):
        cleaned = re.sub(r"<(?:think|thought|reasoning)>[\s\S]*$", "", cleaned, flags=re.IGNORECASE)

    # 2. Remove common reasoning preambles such as:
    # "Here's a thinking process: ... \n\n" or "Thinking Process:\n..."
    cleaned = re.sub(
        r"^(?:Here'?s a thinking process:?|Thinking Process:?|Thought Process:?)[\s\S]*?(?=\n\n(?:[A-Z0-9#*`{\[]|\b(?:Here is|Subject|Title|Notification|Hi|Hello|Dear|Alert|Status|Summary)))",
        "",
        cleaned.strip(),
        flags=re.IGNORECASE,
    )

    cleaned = cleaned.strip()
    return cleaned if cleaned else text.strip()


async def complete(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    response_format: dict[str, Any] | None = None,
    api_key: str | None = None,
    fallback_models: list[str] | None = None,
    **kwargs: Any,
) -> LLMResponse:
    """
    Async LLM completion via LiteLLM with dynamic self-healing fallbacks.

    Args:
        messages: OpenAI-format message list [{"role": ..., "content": ...}]
        model: LiteLLM model string. Defaults to settings.default_model.
        temperature: 0.0 for deterministic structured output.
        max_tokens: Max tokens in the completion.
        response_format: {"type": "json_object"} — only passed if model supports it.
        api_key: Per-call API key override (for workspace credentials in Phase 4).
        fallback_models: Optional list of fallback models (e.g. ['gpt-4o', 'moonshot/moonshot-v1-32k'])

    Returns:
        LLMResponse with normalized token counts and cost.
    """
    try:
        import litellm
    except ImportError as e:
        raise ImportError(
            "litellm is required. Install with: pip install litellm"
        ) from e

    effective_model = model or settings.default_model

    # Explicit opt-in simulation mode for offline dev or test environments
    if getattr(settings, "simulation_mode", False) or getattr(settings, "mock_llm", False):
        log.info("llm_simulation_mode_active", model=effective_model)
        mock_resp = _generate_smart_mock_response(messages, effective_model)
        if not mock_resp.content.startswith("[SIMULATED RESULT]"):
            mock_resp.content = f"[SIMULATED RESULT] {mock_resp.content}"
        return mock_resp

    # Build sequence of models to try for self-healing
    models_to_try = [effective_model]
    if fallback_models:
        for fb in fallback_models:
            if fb and fb not in models_to_try:
                models_to_try.append(fb)

    base_call_kwargs: dict[str, Any] = {
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        **kwargs,
    }
    if api_key:
        base_call_kwargs["api_key"] = api_key

    response = None
    used_model = effective_model

    for attempt_idx, candidate_model in enumerate(models_to_try):
        call_kwargs = dict(base_call_kwargs)
        actual_model = candidate_model
        if actual_model in ("free", "auto", "openrouter/free"):
            actual_model = "openrouter/nvidia/nemotron-3.5-lightning:free"
        call_kwargs["model"] = actual_model

        openrouter_keys = (
            settings.get_openrouter_api_keys()
            if (actual_model.startswith("openrouter/") and "api_key" not in call_kwargs)
            else [call_kwargs.get("api_key")]
        )
        if not openrouter_keys:
            openrouter_keys = [None]

        key_success = False
        for k_idx, current_key in enumerate(openrouter_keys):
            if current_key:
                call_kwargs["api_key"] = current_key

            try:
                response = await litellm.acompletion(**call_kwargs)
                used_model = candidate_model
                if k_idx > 0:
                    log.info("openrouter_backup_key_succeeded", key_index=k_idx)
                if attempt_idx > 0:
                    log.info(
                        "self_healing_fallback_succeeded",
                        original_model=effective_model,
                        fallback_model=candidate_model,
                    )
                key_success = True
                break
            except Exception as e:
                log.warning(
                    "openrouter_key_attempt_failed" if actual_model.startswith("openrouter/") else "llm_key_attempt_failed",
                    key_index=k_idx,
                    keys_total=len(openrouter_keys),
                    model=actual_model,
                    error=str(e),
                )
                if k_idx < len(openrouter_keys) - 1:
                    log.info("switching_to_backup_openrouter_key", next_key_index=k_idx + 1)
                    continue
                # If all available keys for this model failed, bubble up to model fallback/self-healing
                log.warning(
                    "llm_call_failed_trying_fallback",
                    model=candidate_model,
                    error=str(e),
                    fallbacks_left=len(models_to_try) - attempt_idx - 1,
                )
                if attempt_idx == len(models_to_try) - 1:
                    log.error("all_llm_models_failed", models=models_to_try, error=str(e))
                    raise

        if key_success:
            break

    # Extract normalized fields
    msg_obj = response.choices[0].message
    content = getattr(msg_obj, "content", "") or ""
    if not content.strip():
        content = (
            getattr(msg_obj, "reasoning", "")
            or getattr(msg_obj, "reasoning_content", "")
            or ""
        )
    content = _clean_reasoning_tokens(content)
    usage = response.usage or {}
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    total_tokens = getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0

    # LiteLLM provides cost for known models; 0.0 for unknown/local
    try:
        cost_usd = litellm.completion_cost(completion_response=response)
    except Exception:
        cost_usd = 0.0

    result = LLMResponse(
        content=content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        model=used_model,
    )

    log.debug(
        "llm_response",
        model=effective_model,
        tokens=total_tokens,
        cost_usd=cost_usd,
        content_length=len(content),
    )

    return result


def _generate_smart_mock_response(
    messages: list[dict[str, str]],
    model: str,
) -> LLMResponse:
    """Generate realistic structured or textual mock response for testing."""
    import json
    import time

    system_text = " ".join(str(m.get("content", "")) for m in messages if m.get("role") == "system")
    full_text = " ".join(str(m.get("content", "")) for m in messages)
    target_text = system_text if system_text else full_text

    # 1. Email agent output (Action agent)
    if "EmailAgentOutput" in target_text or ("body_preview" in target_text and "to_email" in target_text) or "body_preview" in full_text:
        content = json.dumps({
            "sent": True,
            "to_email": "executive.lead@innovationlabs.io",
            "subject": "Modernizing Workflow Automation with AgentFlow",
            "body_preview": "Hello, I reviewed your operational roadmap and identified high-impact opportunities to automate multi-agent workflows with AgentFlow. Would you be open to a 10-minute demo this week?",
            "backend": "stub",
            "message_id": "sim_outreach_msg_8849",
        }, indent=2)

    # 2. Memory agent output
    elif "MemoryOutput" in target_text or "recalled_memories" in target_text:
        content = json.dumps({
            "action": "merge",
            "recalled_memories": {
                "account_intent": "high",
                "stage": "qualified_opportunity",
                "last_contact": "executive_outreach_sent",
            },
            "memory_count": 3,
            "status": "synced",
        }, indent=2)

    # 3. Approval agent output
    elif "ApprovalOutput" in target_text or "data_snapshot" in target_text:
        content = json.dumps({
            "approved": True,
            "reviewer": "operations_manager",
            "notes": "Approved for executive dispatch",
            "decision_timestamp": time.time(),
            "data_snapshot": {},
        }, indent=2)

    # 4. Reviewer output
    elif "ReviewerOutput" in target_text or ("strengths" in target_text and "revised_subject" in target_text) or ("passed" in target_text and "score" in target_text and "feedback" in target_text):
        content = json.dumps({
            "score": 9,
            "passed": True,
            "feedback": "Clear value proposition, appropriate professional tone, and strong call to action.",
            "strengths": [
                "Concise messaging",
                "Direct value delivery",
                "Action-oriented ending",
            ],
            "improvements": [],
            "revised_subject": None,
        }, indent=2)

    # 5. Writer output
    elif "WriterOutput" in target_text or ("personalization_hooks" in target_text and "subject" in target_text) or ("personalization_hooks" in full_text):
        content = json.dumps({
            "subject": "Modernizing Workflow Automation with AgentFlow",
            "body": "Hello,\n\nI reviewed your latest operational roadmap and saw significant opportunity to streamline multi-agent workflows. AgentFlow allows you to visually design, monitor, and execute AI agent graphs with full persistence.\n\nWould you be open to a brief demo this week?\n\nBest regards,\nAgentFlow Specialist",
            "tone": "professional",
            "word_count": 45,
            "personalization_hooks": [
                "Operational roadmap review",
                "Multi-agent workflow deployment",
            ],
        }, indent=2)

    # 6. Classifier / Router output
    elif "ClassifierOutput" in target_text or ("category" in target_text and "branch" in target_text):
        content = json.dumps({
            "score": 9,
            "category": "enterprise",
            "branch": "qualified",
            "reasoning": "High relevance score and clear enterprise workflow requirements.",
            "recommendation": "Proceed to personalized outreach drafting.",
            "lead_name": "Executive Lead",
            "company": "Innovation Labs",
        }, indent=2)

    # 7. Supervisor output
    elif "SupervisorOutput" in target_text or ("plan" in target_text and "synthesis" in target_text):
        content = json.dumps({
            "goal": "Orchestrate enterprise research and outreach",
            "plan": [
                {"task_id": "task_1", "description": "Execute deep web intelligence search", "assigned_role": "research", "status": "completed"},
                {"task_id": "task_2", "description": "Draft personalized executive outreach", "assigned_role": "writer", "status": "pending"},
            ],
            "synthesis": "Target profile validated. High intent signals detected. Ready for personalized outreach drafting.",
            "is_complete": True,
            "next_action": "Proceed to draft personalized outreach",
            "confidence": 0.94,
        }, indent=2)

    # 8. RAG output
    elif "RAGOutput" in target_text or ("cited_passages" in target_text and "answer" in target_text):
        content = json.dumps({
            "query": "Domain knowledge grounding",
            "answer": "According to the verified knowledge documentation, AgentFlow orchestrates multi-agent DAG workflows with topological scheduling and self-healing retries.",
            "cited_passages": [
                {"source_title": "Architecture Specification", "excerpt": "Topological graph execution enables concurrent async node execution.", "relevance_score": 0.95},
                {"source_title": "Operator Manual", "excerpt": "Human approval gates pause execution until reviewer sign-off.", "relevance_score": 0.91},
            ],
            "confidence": 0.95,
            "key_entities": ["AgentFlow", "DAG", "Topological Execution"],
        }, indent=2)

    # 9. Research output
    elif "ResearchOutput" in target_text or "key_findings" in target_text:
        content = json.dumps({
            "summary": "Synthesized comprehensive market research and target organization analysis from multi-source intelligence.",
            "key_findings": [
                {
                    "title": "High Automation Opportunity",
                    "detail": "Target company has multiple repetitive manual workflows suitable for autonomous agent deployment.",
                    "relevance_score": 0.92,
                },
                {
                    "title": "Accelerating Growth Signals",
                    "detail": "Recent engineering expansion indicates strong technical adoption capacity.",
                    "relevance_score": 0.88,
                },
            ],
            "sources": [
                "https://techcrunch.com/company-analysis",
                "https://news.ycombinator.com",
            ],
            "confidence": 0.91,
            "lead_name": "Executive Lead",
            "company": "Innovation Labs",
        }, indent=2)

    # 10. Generic JSON schema requested
    elif "## REQUIRED OUTPUT FORMAT" in full_text or "```json" in full_text:
        content = json.dumps({
            "status": "success",
            "message": "Processed successfully by agent",
            "score": 0.95,
            "details": "Automated workflow execution completed successfully without issues.",
        }, indent=2)

    # 6. Default text response
    else:
        content = "Agent execution completed successfully. Processed inputs and generated results according to workflow specifications."

    return LLMResponse(
        content=content,
        prompt_tokens=150,
        completion_tokens=85,
        total_tokens=235,
        cost_usd=0.0001,
        model=f"{model} (simulation fallback)",
    )
