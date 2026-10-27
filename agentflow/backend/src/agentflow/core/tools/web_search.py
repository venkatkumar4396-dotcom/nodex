"""
WebSearchTool — search the web and return structured results.

Supports two backends (configured via credentials/env):
  1. Serper.dev  (SERPER_API_KEY)  — default, cheapest ($0.001/query)
  2. Brave Search (BRAVE_SEARCH_API_KEY) — fallback

When no API key is configured (offline/test mode), returns a clearly labeled
stub result so the pipeline still runs without failing.

Prompt injection defense:
  - All web content is returned as data in the ToolResult, not instructions.
  - Agents that consume this tool MUST wrap content in <web_content> tags
    and instruct the LLM to treat it as external untrusted data.
"""
from __future__ import annotations

from typing import Any, ClassVar

import structlog

from agentflow.core.schemas.tool import ToolResult
from agentflow.core.tools.base import BaseTool

log = structlog.get_logger(__name__)


class WebSearchTool(BaseTool):
    """
    Web search tool. Returns top-N organic results with title, URL, snippet.

    Arguments (JSON Schema below):
      query    (str)  : search query
      num_results (int, optional): number of results, default 5, max 10

    Returns ToolResult.data:
      {
        "results": [
          {"title": ..., "url": ..., "snippet": ..., "position": 1},
          ...
        ],
        "query": "...",
        "backend": "serper" | "brave" | "stub"
      }
    """

    name: ClassVar[str] = "web_search"
    description: ClassVar[str] = (
        "Search the web for current information. Use this to find recent news, "
        "company information, pricing, documentation, or any publicly available data. "
        "Returns titles, URLs, and snippets for the top results."
    )
    parameters_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query (be specific for better results)",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (1–10, default 5)",
                "default": 5,
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": ["query"],
    }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        query: str = arguments.get("query", "")
        num_results: int = min(int(arguments.get("num_results", 5)), 10)

        if not query.strip():
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="query must be a non-empty string",
            )

        log.info("web_search_execute", query=query, num_results=num_results)

        # Try Serper first, then Brave, then stub
        result = await self._try_serper(query, num_results)
        if result is not None:
            return result

        result = await self._try_brave(query, num_results)
        if result is not None:
            return result

        # No API key configured — return stub so agents can still run
        log.warning("web_search_no_key", msg="No search API key found; returning stub results")
        return self._stub_result(query, num_results)

    async def _try_serper(self, query: str, num_results: int) -> ToolResult | None:
        """Call Serper.dev API."""
        from agentflow.core.tools.credentials import credential_store
        api_key = credential_store.get("serper_api_key")
        if not api_key:
            return None

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://google.serper.dev/search",
                    headers={
                        "X-API-KEY": api_key,
                        "Content-Type": "application/json",
                    },
                    json={"q": query, "num": num_results},
                )
                response.raise_for_status()
                data = response.json()

            results = []
            for i, item in enumerate(data.get("organic", [])[:num_results], start=1):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "position": i,
                })

            log.info("web_search_serper_ok", query=query, count=len(results))
            return ToolResult(
                tool_name=self.name,
                success=True,
                data={"results": results, "query": query, "backend": "serper"},
                metadata={"result_count": len(results)},
            )
        except Exception as e:
            log.warning("web_search_serper_failed", error=str(e))
            return None

    async def _try_brave(self, query: str, num_results: int) -> ToolResult | None:
        """Call Brave Search API."""
        from agentflow.core.tools.credentials import credential_store
        api_key = credential_store.get("brave_search_key")
        if not api_key:
            return None

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": api_key,
                    },
                    params={"q": query, "count": num_results},
                )
                response.raise_for_status()
                data = response.json()

            results = []
            for i, item in enumerate(
                data.get("web", {}).get("results", [])[:num_results], start=1
            ):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", ""),
                    "position": i,
                })

            log.info("web_search_brave_ok", query=query, count=len(results))
            return ToolResult(
                tool_name=self.name,
                success=True,
                data={"results": results, "query": query, "backend": "brave"},
                metadata={"result_count": len(results)},
            )
        except Exception as e:
            log.warning("web_search_brave_failed", error=str(e))
            return None

    def _stub_result(self, query: str, num_results: int) -> ToolResult:
        """Return labelled stub results when no API key is configured."""
        results = [
            {
                "title": f"[STUB] Result {i} for: {query}",
                "url": f"https://example.com/result-{i}",
                "snippet": (
                    f"No search API key configured. This is a stub result {i} for "
                    f"the query '{query}'. Set SERPER_API_KEY or BRAVE_SEARCH_API_KEY "
                    f"in .env to enable real web search."
                ),
                "position": i,
            }
            for i in range(1, num_results + 1)
        ]
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={"results": results, "query": query, "backend": "stub"},
            metadata={"stub": True},
        )
