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
from typing import Any

import structlog

from agentflow.config import settings

log = structlog.get_logger(__name__)

# ── Inject API keys into environment for LiteLLM to pick up ─────────────────
if settings.moonshot_api_key:
    os.environ["MOONSHOT_API_KEY"] = settings.moonshot_api_key
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


async def complete(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    response_format: dict[str, Any] | None = None,
    api_key: str | None = None,
    **kwargs: Any,
) -> LLMResponse:
    """
    Async LLM completion via LiteLLM.

    Args:
        messages: OpenAI-format message list [{"role": ..., "content": ...}]
        model: LiteLLM model string. Defaults to settings.default_model.
        temperature: 0.0 for deterministic structured output.
        max_tokens: Max tokens in the completion.
        response_format: {"type": "json_object"} — only passed if model supports it.
        api_key: Per-call API key override (for workspace credentials in Phase 4).

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

    call_kwargs: dict[str, Any] = {
        "model": effective_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        **kwargs,
    }

    # Only pass response_format if the model actually supports it
    if response_format and supports_json_mode(effective_model):
        call_kwargs["response_format"] = response_format

    if api_key:
        call_kwargs["api_key"] = api_key

    log.debug(
        "llm_call",
        model=effective_model,
        message_count=len(messages),
        json_mode=response_format is not None and supports_json_mode(effective_model),
    )

    try:
        response = await litellm.acompletion(**call_kwargs)
    except Exception as e:
        log.error("llm_call_failed", model=effective_model, error=str(e))
        raise

    # Extract normalized fields
    content = response.choices[0].message.content or ""
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
        model=effective_model,
    )

    log.debug(
        "llm_response",
        model=effective_model,
        tokens=total_tokens,
        cost_usd=cost_usd,
        content_length=len(content),
    )

    return result
