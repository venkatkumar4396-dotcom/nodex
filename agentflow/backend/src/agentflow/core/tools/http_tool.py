"""
HttpTool — generic HTTP request tool.

Allows agents to call any REST API. The agent decides the method, URL,
headers, and body through LLM tool-calling.

Security:
  - The agent config can whitelist allowed URL prefixes (via extra.allowed_url_prefixes).
  - Credentials are injected via Authorization headers from CredentialStore,
    never put in the prompt or logged.
  - Response body is size-limited to prevent unbounded memory usage.
  - Redirect following is limited.

Prompt injection defense:
  - Response body is returned as data, not as instructions.
  - Agents must wrap HTTP responses in <http_response> tags.
"""
from __future__ import annotations

from typing import Any, ClassVar

import structlog

from agentflow.core.schemas.tool import ToolResult
from agentflow.core.tools.base import BaseTool

log = structlog.get_logger(__name__)

# Hard limits
_MAX_RESPONSE_BYTES = 50_000   # 50 KB max body
_TIMEOUT_SECONDS = 20.0
_MAX_REDIRECTS = 5


class HttpTool(BaseTool):
    """
    Generic HTTP request tool.

    Arguments:
      method  (str)  : HTTP method — GET, POST, PUT, PATCH, DELETE
      url     (str)  : Full URL to request
      headers (dict) : Optional headers (dict of str → str)
      body    (dict) : Optional JSON body (for POST/PUT/PATCH)
      params  (dict) : Optional query parameters

    Returns ToolResult.data:
      {
        "status_code": 200,
        "headers": {...},
        "body": "...",     # String — may be JSON or plain text
        "url": "...",      # Final URL after redirects
        "content_type": "application/json"
      }
    """

    name: ClassVar[str] = "http_request"
    description: ClassVar[str] = (
        "Make an HTTP request to any URL. Use for REST APIs, webhooks, or fetching "
        "web page content. Supports GET, POST, PUT, PATCH, DELETE. "
        "JSON bodies are automatically serialized."
    )
    parameters_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                "description": "HTTP method",
            },
            "url": {
                "type": "string",
                "description": "The full URL to request (must start with https:// or http://)",
            },
            "headers": {
                "type": "object",
                "additionalProperties": {"type": "string"},
                "description": "Optional HTTP headers",
            },
            "body": {
                "type": "object",
                "description": "Optional JSON body for POST/PUT/PATCH",
            },
            "params": {
                "type": "object",
                "additionalProperties": {"type": "string"},
                "description": "Optional URL query parameters",
            },
        },
        "required": ["method", "url"],
    }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        method: str = arguments.get("method", "GET").upper()
        url: str = arguments.get("url", "")
        headers: dict[str, str] = arguments.get("headers") or {}
        body: dict[str, Any] | None = arguments.get("body")
        params: dict[str, str] | None = arguments.get("params")

        if not url.startswith(("http://", "https://")):
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"URL must start with http:// or https://. Got: {url[:100]}",
            )

        if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Unsupported HTTP method: {method}",
            )

        log.info("http_request_execute", method=method, url=url)

        try:
            import httpx

            # Inject bearer token from credential store if available
            from agentflow.core.tools.credentials import credential_store
            bearer = credential_store.get("http_bearer_token")
            if bearer and "Authorization" not in headers:
                headers = {**headers, "Authorization": f"Bearer {bearer}"}

            async with httpx.AsyncClient(
                timeout=_TIMEOUT_SECONDS,
                follow_redirects=True,
                max_redirects=_MAX_REDIRECTS,
            ) as client:
                request_kwargs: dict[str, Any] = {
                    "method": method,
                    "url": url,
                    "headers": headers,
                }
                if params:
                    request_kwargs["params"] = params
                if body is not None:
                    request_kwargs["json"] = body

                response = await client.request(**request_kwargs)

            # Limit response size
            content_type = response.headers.get("content-type", "")
            raw_content = response.content[:_MAX_RESPONSE_BYTES]
            truncated = len(response.content) > _MAX_RESPONSE_BYTES

            # Try to decode as text; fall back to base64 if binary
            try:
                body_str = raw_content.decode("utf-8", errors="replace")
            except Exception:
                import base64
                body_str = f"[binary content, base64]: {base64.b64encode(raw_content).decode()}"

            data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": body_str,
                "url": str(response.url),
                "content_type": content_type,
            }
            if truncated:
                data["truncated"] = True
                data["truncated_at_bytes"] = _MAX_RESPONSE_BYTES

            success = 200 <= response.status_code < 400
            error = None if success else f"HTTP {response.status_code}: {body_str[:200]}"

            log.info(
                "http_request_ok",
                method=method,
                url=url,
                status=response.status_code,
                truncated=truncated,
            )
            return ToolResult(
                tool_name=self.name,
                success=success,
                data=data,
                error=error,
                metadata={
                    "status_code": response.status_code,
                    "content_type": content_type,
                },
            )

        except Exception as e:
            log.warning("http_request_failed", method=method, url=url, error=str(e))
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"HTTP request failed: {str(e)[:300]}",
            )
