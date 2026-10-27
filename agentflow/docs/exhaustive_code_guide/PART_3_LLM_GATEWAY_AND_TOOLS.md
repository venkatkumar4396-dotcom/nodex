# Part 3: LLM Gateway, Tools & The ReAct Loop
## Exhaustive Code & Line-by-Line Architectural Guide

---

## 1. `src/agentflow/core/llm/client.py`

### 1.1 Complete Source Code
```python
"""
LiteLLM wrapper — provider-agnostic LLM client.
"""
from __future__ import annotations

import os
from typing import Any

import structlog

from agentflow.config import settings

log = structlog.get_logger(__name__)

# Inject API keys into environment for LiteLLM to pick up
if settings.moonshot_api_key:
    os.environ["MOONSHOT_API_KEY"] = settings.moonshot_api_key
if settings.openai_api_key:
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key
if settings.anthropic_api_key:
    os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
if settings.gemini_api_key:
    os.environ["GEMINI_API_KEY"] = settings.gemini_api_key

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
    """Async LLM completion via LiteLLM."""
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

    content = response.choices[0].message.content or ""
    usage = response.usage or {}
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    total_tokens = getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0

    try:
        cost_usd = litellm.completion_cost(completion_response=response)
    except Exception:
        cost_usd = 0.0

    return LLMResponse(
        content=content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        model=effective_model,
    )
```

### 1.2 Line-by-Line Breakdown & Explanation
- **Lines 30–37**: Environment injection: Injects API keys from `settings` into `os.environ` where LiteLLM expects them.
- **Lines 39–49**: `supports_json_mode()`: Detects whether a model supports native OpenAI-style JSON mode (`{"type": "json_object"}`). Kimi / Moonshot and Anthropic Claude do not support `response_format` in this exact syntax, so passing it causes a 400 Bad Request error. This guard dynamically filters out `response_format` for unsupported models.
- **Lines 52–76**: `class LLMResponse`: Provider-agnostic response object. Normalizes `content`, `prompt_tokens`, `completion_tokens`, `total_tokens`, and calculated `cost_usd`.
- **Lines 79–101**: `complete()`: The main entry point for model queries. Uses async `litellm.acompletion` to prevent blocking the asyncio event loop.
- **Lines 147–151**: `litellm.completion_cost()`: Uses LiteLLM's internal token cost database to calculate dollar costs for known models. Defaults to `0.0` for local (Ollama) or custom endpoints.

---

## 2. `src/agentflow/core/llm/structured.py`

### 2.1 Complete Source Code
```python
"""
Structured output — reliable JSON extraction from LLM responses.
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
    """Call the LLM and parse+validate the response into a Pydantic model."""
    from agentflow.config import settings
    effective_model = model or settings.default_model

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

    data = _parse_json_safely(raw)
    if data is None:
        raise StructuredOutputError(
            f"LLM did not return valid JSON. Raw output:\n{raw[:500]}",
            raw_output=raw,
            validation_errors=["JSON parse error: could not decode response as JSON"],
        )

    try:
        instance = output_model.model_validate(data)
    except ValidationError as e:
        errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
        raise StructuredOutputError(
            "Output failed schema validation:\n" + "\n".join(errors),
            raw_output=raw,
            validation_errors=errors,
        ) from e

    return instance, llm_response


def _inject_schema_instruction(
    messages: list[dict[str, str]],
    instruction: str,
) -> list[dict[str, str]]:
    result = list(messages)
    for i, msg in enumerate(result):
        if msg.get("role") == "system":
            result[i] = {**msg, "content": msg["content"] + instruction}
            return result
    result.insert(0, {"role": "system", "content": instruction.lstrip()})
    return result


def _parse_json_safely(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract JSON inside markdown code blocks ```json ... ```
    if "```" in text:
        parts = text.split("```")
        for part in parts[1::2]:
            cleaned = part
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                continue

    # Extract outermost curly braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None
```

### 2.2 Line-by-Line Breakdown & Explanation
- **Lines 72–82**: Schema prompt injection: Extracts the Pydantic JSON Schema via `output_model.model_json_schema()` and appends it to the system message.
- **Lines 84–94**: Self-Healing Feedback Injection: If `validation_feedback` is passed (from a failed retry attempt in `node_runner`), injects the exact Pydantic error trace as a user message.
- **Lines 159–187**: `_parse_json_safely()`:
  - Attempt 1: Direct `json.loads(text)`.
  - Attempt 2: Searches for code fences (` ```json ` ... ` ``` `) and parses the inner content.
  - Attempt 3: Slices between first `{` and last `}`, removing conversational preamble or postscript (e.g. *"Here is your JSON: { ... } Hope this helps!"*).

---

## 3. `src/agentflow/core/tools/base.py` & `src/agentflow/core/tools/registry.py`

### 3.1 Complete Source Code (`base.py`)
```python
"""BaseTool — the interface every tool must implement."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from agentflow.core.schemas.tool import ToolDef, ToolResult


class BaseTool(ABC):
    """Abstract base for all AgentFlow tools."""

    name: ClassVar[str]
    description: ClassVar[str]
    parameters_schema: ClassVar[dict[str, Any]]

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        ...

    def to_def(self) -> ToolDef:
        return ToolDef(
            name=self.name,
            description=self.description,
            parameters=self.parameters_schema,
        )

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }
```

### 3.2 Complete Source Code (`registry.py`)
```python
"""ToolRegistry — the plugin registry for all tool implementations."""
from __future__ import annotations

from typing import TYPE_CHECKING
import structlog

if TYPE_CHECKING:
    from agentflow.core.tools.base import BaseTool

log = structlog.get_logger(__name__)


class ToolNotFoundError(KeyError):
    """Raised when a tool name has no registered implementation."""


class ToolRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._registry[tool.name] = tool
        log.debug("tool_registered", name=tool.name)

    def get(self, name: str) -> BaseTool:
        tool = self._registry.get(name)
        if tool is None:
            raise ToolNotFoundError(
                f"No tool registered with name '{name}'. "
                f"Registered tools: {list(self._registry)}"
            )
        return tool

    def resolve_tools(self, names: list[str]) -> list[BaseTool]:
        return [self.get(name) for name in names]

    def list_registered(self) -> list[str]:
        return list(self._registry.keys())

    def is_registered(self, name: str) -> bool:
        return name in self._registry


tool_registry = ToolRegistry()


def register_all_builtin_tools() -> None:
    from agentflow.core.tools.email_tool import EmailSendTool
    from agentflow.core.tools.http_tool import HttpTool
    from agentflow.core.tools.web_search import WebSearchTool

    tool_registry.register(WebSearchTool())
    tool_registry.register(HttpTool())
    tool_registry.register(EmailSendTool())

    log.info(
        "builtin_tools_registered",
        count=len(tool_registry.list_registered()),
        names=tool_registry.list_registered(),
    )
```

---

## 4. `src/agentflow/core/tools/credentials.py`

### 4.1 Complete Source Code
```python
"""
CredentialStore — encrypted credential management.
"""
from __future__ import annotations

import base64
import os
import structlog

log = structlog.get_logger(__name__)


def _get_or_create_fernet():
    try:
        from cryptography.fernet import Fernet
        key_str = os.environ.get("FERNET_KEY", "")
        if key_str:
            return Fernet(key_str.encode())
        else:
            key = Fernet.generate_key()
            log.warning(
                "fernet_ephemeral_key",
                msg="FERNET_KEY not set; using an ephemeral session key.",
            )
            return Fernet(key)
    except ImportError:
        return None


class CredentialStore:
    def __init__(self) -> None:
        self._fernet = _get_or_create_fernet()
        self._store: dict[str, bytes] = {}

    def set(self, cred_id: str, value: str) -> None:
        raw = value.encode("utf-8")
        if self._fernet:
            stored = self._fernet.encrypt(raw)
        else:
            stored = base64.b64encode(raw)
        self._store[cred_id] = stored
        log.debug("credential_stored", cred_id=cred_id)

    def get(self, cred_id: str) -> str | None:
        encrypted = self._store.get(cred_id)
        if encrypted is None:
            return None
        try:
            if self._fernet:
                return self._fernet.decrypt(encrypted).decode("utf-8")
            else:
                return base64.b64decode(encrypted).decode("utf-8")
        except Exception as e:
            log.error("credential_decrypt_failed", cred_id=cred_id, error=str(e))
            return None

    def load_from_env(self, mappings: dict[str, str]) -> None:
        for cred_id, env_var in mappings.items():
            value = os.environ.get(env_var, "")
            if value:
                self.set(cred_id, value)
                log.debug("credential_loaded_from_env", cred_id=cred_id, env_var=env_var)

    def resolve_for_node(self, credential_ids: dict[str, str]) -> dict[str, str]:
        result: dict[str, str] = {}
        for tool_name, cred_id in credential_ids.items():
            value = self.get(cred_id)
            if value is not None:
                result[tool_name] = value
        return result

    def has(self, cred_id: str) -> bool:
        return cred_id in self._store

    def list_ids(self) -> list[str]:
        return list(self._store.keys())


credential_store = CredentialStore()


def load_default_credentials_from_env() -> None:
    credential_store.load_from_env({
        "serper_api_key": "SERPER_API_KEY",
        "serpapi_key": "SERPAPI_KEY",
        "brave_search_key": "BRAVE_SEARCH_API_KEY",
        "sendgrid_key": "SENDGRID_API_KEY",
        "smtp_password": "SMTP_PASSWORD",
        "http_bearer_token": "HTTP_BEARER_TOKEN",
    })
```

---

## 5. `src/agentflow/core/tools/tool_loop.py`

### 5.1 Architecture & Implementation Breakdown
- **ReAct Execution Engine**: Manages iterative model reasoning and tool execution.
- **Lines 53**: `MAX_TOOL_ROUNDS = 10`: Enforces an internal guard to prevent runaway agents from making infinite API calls.
- **`run_tool_loop()`**:
  1. Serializes tools via `tool.to_openai_tool()`.
  2. Sends conversation + tool specs to LLM.
  3. Inspects `response.choices[0].message.tool_calls`.
  4. If tool calls exist:
     - Dispatches each tool call via `tool.execute(**arguments)`.
     - Wraps results in untrusted external data boundaries: `<tool_result tool="{tool_name}">...JSON...</tool_result>`.
     - Appends observation to history and loops back to LLM.
  5. If no tool calls: Loop terminates and returns conversation history for final structured extraction.
- **Prompt Injection Defense**: All tool results are explicitly labeled as external data in the message history, preventing external web pages or email bodies from overriding system prompts.

---

## 6. Built-in Production Tools (`web_search.py`, `http_tool.py`, `email_tool.py`)

1. **`WebSearchTool` (`src/agentflow/core/tools/web_search.py`)**:
   - Queries Google search via **Serper.dev** API (`POST https://google.serper.dev/search`).
   - If Serper key is missing, automatically falls back to **DuckDuckGo HTML search**.
   - If offline, generates synthetic structured research findings in dry-run mode.
2. **`HttpTool` (`src/agentflow/core/tools/http_tool.py`)**:
   - Executes arbitrary HTTP REST requests via `httpx.AsyncClient`.
   - Supports methods: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`.
   - Returns status codes, headers, response body, and execution latency.
3. **`EmailSendTool` (`src/agentflow/core/tools/email_tool.py`)**:
   - Primary: **SendGrid REST API** (`https://api.sendgrid.com/v3/mail/send`).
   - Secondary: Standard **SMTP client** with TLS.
   - Development fallback: **Stub mode** returning realistic mock message IDs (`msg_...`).
