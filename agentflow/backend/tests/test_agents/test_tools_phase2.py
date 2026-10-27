"""
Phase 2 tests — Tools: WebSearchTool, HttpTool, EmailSendTool.

These tests use pytest-mock / respx to mock HTTP calls so they run offline.
No real API keys required.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── WebSearchTool tests ───────────────────────────────────────────────────────

class TestWebSearchTool:
    @pytest.fixture
    def tool(self):
        from agentflow.core.tools.web_search import WebSearchTool
        return WebSearchTool()

    def test_tool_def(self, tool):
        """Tool has correct name, description, and schema."""
        td = tool.to_def()
        assert td.name == "web_search"
        assert "search" in td.description.lower()
        assert td.parameters["required"] == ["query"]

    def test_to_openai_tool(self, tool):
        ot = tool.to_openai_tool()
        assert ot["type"] == "function"
        assert ot["function"]["name"] == "web_search"
        assert "query" in ot["function"]["parameters"]["properties"]

    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self, tool):
        result = await tool.execute({"query": "  "})
        assert result.success is False
        assert "non-empty" in (result.error or "")

    @pytest.mark.asyncio
    async def test_stub_result_when_no_key(self, tool):
        """When no API key is configured, returns stub results."""
        from agentflow.core.tools.credentials import credential_store
        # Ensure no keys are set for this test
        with patch.object(credential_store, "get", return_value=None):
            result = await tool.execute({"query": "test query", "num_results": 3})

        assert result.success is True
        assert result.data["backend"] == "stub"
        assert len(result.data["results"]) == 3
        assert result.metadata.get("stub") is True

    @pytest.mark.asyncio
    async def test_serper_success(self, tool):
        """Successful Serper API call returns parsed results."""
        serper_response = {
            "organic": [
                {"title": "Test Result", "link": "https://example.com", "snippet": "A snippet"},
                {"title": "Result 2", "link": "https://example2.com", "snippet": "Another"},
            ]
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = serper_response
        mock_response.raise_for_status = MagicMock()

        from agentflow.core.tools.credentials import credential_store
        with (
            patch.object(credential_store, "get", return_value="fake-serper-key"),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await tool.execute({"query": "test", "num_results": 2})

        assert result.success is True
        assert result.data["backend"] == "serper"
        assert len(result.data["results"]) == 2
        assert result.data["results"][0]["title"] == "Test Result"
        assert result.data["results"][0]["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_num_results_capped_at_10(self, tool):
        """num_results > 10 is capped to 10."""
        from agentflow.core.tools.credentials import credential_store
        with patch.object(credential_store, "get", return_value=None):
            result = await tool.execute({"query": "test", "num_results": 99})

        # Stub returns exactly min(capped, 10) results
        assert result.success is True
        assert len(result.data["results"]) == 10


# ── HttpTool tests ────────────────────────────────────────────────────────────

class TestHttpTool:
    @pytest.fixture
    def tool(self):
        from agentflow.core.tools.http_tool import HttpTool
        return HttpTool()

    def test_tool_name(self, tool):
        assert tool.name == "http_request"

    @pytest.mark.asyncio
    async def test_rejects_non_http_url(self, tool):
        result = await tool.execute({"method": "GET", "url": "ftp://badproto.com"})
        assert result.success is False
        assert "http" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_rejects_invalid_method(self, tool):
        result = await tool.execute({"method": "TRACE", "url": "https://example.com"})
        assert result.success is False
        assert "method" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_successful_get(self, tool):
        """GET request returns status, headers, and body."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.content = b'{"key": "value"}'
        mock_response.url = "https://api.example.com/data"

        from agentflow.core.tools.credentials import credential_store
        with (
            patch.object(credential_store, "get", return_value=None),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await tool.execute({
                "method": "GET",
                "url": "https://api.example.com/data",
            })

        assert result.success is True
        assert result.data["status_code"] == 200
        assert result.data["body"] == '{"key": "value"}'

    @pytest.mark.asyncio
    async def test_http_error_returns_failure(self, tool):
        """4xx/5xx status codes return success=False."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.content = b"Not Found"
        mock_response.url = "https://api.example.com/missing"

        from agentflow.core.tools.credentials import credential_store
        with (
            patch.object(credential_store, "get", return_value=None),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await tool.execute({
                    "method": "GET",
                    "url": "https://api.example.com/missing",
                })

        assert result.success is False
        assert "404" in (result.error or "")


# ── EmailSendTool tests ───────────────────────────────────────────────────────

class TestEmailSendTool:
    @pytest.fixture
    def tool(self):
        from agentflow.core.tools.email_tool import EmailSendTool
        return EmailSendTool()

    def test_tool_name(self, tool):
        assert tool.name == "email_send"

    @pytest.mark.asyncio
    async def test_invalid_email_returns_error(self, tool):
        result = await tool.execute({
            "to": "not-an-email",
            "subject": "Test",
            "body": "Hello",
        })
        assert result.success is False
        assert "invalid" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_missing_subject_returns_error(self, tool):
        result = await tool.execute({
            "to": "test@example.com",
            "subject": "",
            "body": "Hello",
        })
        assert result.success is False

    @pytest.mark.asyncio
    async def test_stub_mode_when_no_backend(self, tool):
        """Without API key or SMTP config, returns stub success."""
        from agentflow.core.tools.credentials import credential_store
        with (
            patch.object(credential_store, "get", return_value=None),
            patch.dict("os.environ", {
                "SMTP_HOST": "",
                "SMTP_USER": "",
            }),
        ):
            result = await tool.execute({
                "to": "test@example.com",
                "subject": "Test Subject",
                "body": "Test body content",
            })

        assert result.success is True
        assert result.data["backend"] == "stub"
        assert result.data["sent"] is False  # Not actually sent
        assert result.metadata.get("stub") is True

    @pytest.mark.asyncio
    async def test_sendgrid_success(self, tool):
        """Successful SendGrid API call."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.headers = {"X-Message-Id": "abc123"}
        mock_response.text = ""

        from agentflow.core.tools.credentials import credential_store
        with (
            patch.object(credential_store, "get", return_value="SG.fake-key"),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await tool.execute({
                "to": "recipient@example.com",
                "subject": "Hello from AgentFlow",
                "body": "This is a test email.",
            })

        assert result.success is True
        assert result.data["sent"] is True
        assert result.data["backend"] == "sendgrid"
        assert result.data["to"] == "recipient@example.com"
