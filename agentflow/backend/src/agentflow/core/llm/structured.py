"""
Structured output — reliable JSON extraction from LLM responses.

The reliability pattern for Kimi and other providers that don't support
native JSON mode:
  1. Inject the full JSON schema into the system prompt
  2. Use strong instructions: "respond ONLY with JSON, no text outside the object"
  3. Parse the response; extract from markdown code blocks if needed
  4. Validate with Pydantic; if invalid → raise StructuredOutputError
  5. node_runner catches it, injects validation errors into next attempt's prompt

For models that DO support response_format (OpenAI, Gemini), we also pass
{"type": "json_object"} as an extra reliability layer.

Security: schema is injected into the system prompt, not user messages,
to prevent user-content from overriding the output schema.
"""
from __future__ import annotations

import json
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel, ValidationError

from agentflow.core.llm.client import LLMResponse, complete, supports_json_mode

log = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(Exception):
    """Raised when the LLM output cannot be parsed or validated."""

    def __init__(self, message: str, raw_output: str, validation_errors: list[str]) -> None:
        super().__init__(message)
        self.raw_output = raw_output
        self.validation_errors = validation_errors


async def complete_structured(
    messages: list[dict[str, str]],
    output_model: type[T],
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    validation_feedback: str | None = None,
    api_key: str | None = None,
) -> tuple[T, LLMResponse]:
    """
    Call the LLM and parse+validate the response into a Pydantic model.

    Works with ALL providers including Kimi/Moonshot (no JSON mode required).

    Strategy:
      - Always inject JSON schema into system prompt (works for all providers)
      - For providers that support JSON mode (OpenAI, Gemini), also pass
        response_format={"type": "json_object"} as an extra layer
      - If validation_feedback is provided, inject it as a correction request

    Returns:
        (validated_instance, llm_response)

    Raises:
        StructuredOutputError: if JSON parsing or Pydantic validation fails.
    """
    from agentflow.config import settings
    effective_model = model or settings.default_model

    # Build JSON schema instruction
    schema_str = json.dumps(output_model.model_json_schema(), indent=2)
    schema_instruction = (
        f"\n\n## REQUIRED OUTPUT FORMAT\n"
        f"You MUST respond with ONLY a valid JSON object. "
        f"No explanation, no markdown, no text before or after the JSON.\n"
        f"The JSON must match this exact schema:\n"
        f"```json\n{schema_str}\n```\n"
        f"Start your response with {{ and end with }}. Nothing else."
    )

    augmented_messages = _inject_schema_instruction(messages, schema_instruction)

    # Add validation feedback for retry attempts
    if validation_feedback:
        augmented_messages = augmented_messages + [{
            "role": "user",
            "content": (
                f"Your previous response failed validation with these errors:\n"
                f"{validation_feedback}\n\n"
                f"Fix these issues and respond with corrected JSON only. "
                f"No explanation text — just the JSON object."
            ),
        }]

    # Only pass response_format for models that support it
    response_format = (
        {"type": "json_object"}
        if supports_json_mode(effective_model)
        else None
    )

    llm_response = await complete(
        messages=augmented_messages,
        model=effective_model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
        api_key=api_key,
    )

    raw = llm_response.content.strip()

    # Parse JSON — try direct parse, then extract from markdown blocks
    data = _parse_json_safely(raw)
    if data is None:
        raise StructuredOutputError(
            f"LLM did not return valid JSON. Raw output:\n{raw[:500]}",
            raw_output=raw,
            validation_errors=["JSON parse error: could not decode response as JSON"],
        )

    # Validate with Pydantic
    try:
        instance = output_model.model_validate(data)
    except ValidationError as e:
        errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
        raise StructuredOutputError(
            "Output failed schema validation:\n" + "\n".join(errors),
            raw_output=raw,
            validation_errors=errors,
        ) from e

    log.debug(
        "structured_output_ok",
        output_model=output_model.__name__,
        model=effective_model,
        tokens=llm_response.total_tokens,
    )

    return instance, llm_response


def _inject_schema_instruction(
    messages: list[dict[str, str]],
    instruction: str,
) -> list[dict[str, str]]:
    """Append JSON schema instruction to the system message (or prepend one)."""
    result = list(messages)
    for i, msg in enumerate(result):
        if msg.get("role") == "system":
            result[i] = {**msg, "content": msg["content"] + instruction}
            return result
    # No system message found — prepend one
    result.insert(0, {"role": "system", "content": instruction.lstrip()})
    return result


def _parse_json_safely(text: str) -> Any | None:
    """Try to parse JSON from raw text, including from markdown code blocks."""
    import re

    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract from ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find a JSON object anywhere in the text (first { to last })
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None
