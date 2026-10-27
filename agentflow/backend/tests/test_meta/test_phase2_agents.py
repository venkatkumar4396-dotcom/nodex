"""
Unit tests for Phase 2 Meta-Agents:
  - Agent #2: Integration Builder (/api/meta/integration-builder, /api/meta/register-connector)
  - Agent #7: Security Red-Team (/api/meta/red-team)
  - Agent #6: Marketplace Publisher (/api/meta/publisher)
  - Agent #5: Browser Operator (/api/meta/browser-operator/step)
"""
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from agentflow.api.app import app
from agentflow.core.llm.client import LLMResponse


@pytest.mark.asyncio
async def test_integration_builder_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        mock_builder_json = """
        {
          "connector_name": "slack_connector",
          "auth": {
            "type": "Bearer",
            "token_placeholder": "{{credentials.SLACK_BOT_TOKEN}}"
          },
          "base_url": "https://slack.com/api",
          "actions": [
            {
              "name": "post_message",
              "description": "Sends a message to a channel.",
              "method": "POST",
              "path": "/chat.postMessage",
              "args_schema": {
                "type": "object",
                "properties": {
                  "channel": {"type": "string"},
                  "text": {"type": "string"}
                },
                "required": ["channel", "text"]
              },
              "response_mapping": {"ok": "ok", "ts": "ts"},
              "destructive": false,
              "retry": {
                "max_retries": 3,
                "retry_on_status": [429, 500],
                "backoff_factor": 1.5
              }
            }
          ],
          "tests": [
            {
              "action": "post_message",
              "sample_input": {"channel": "C123", "text": "hello"},
              "expected_output_shape": {"ok": true}
            }
          ],
          "open_questions": [],
          "security_notes": ["Requires chat:write scope"]
        }
        """

        mock_llm_resp = LLMResponse(
            content=mock_builder_json,
            prompt_tokens=400,
            completion_tokens=250,
            total_tokens=650,
            cost_usd=0.0,
            model="openrouter/free",
        )

        with patch("agentflow.meta.routes_meta.complete", return_value=mock_llm_resp):
            resp = await client.post(
                "/api/meta/integration-builder",
                json={
                    "api_docs": "POST /chat.postMessage with channel and text params using Bearer token",
                    "goal": "Send messages to Slack channels",
                },
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["connector_name"] == "slack_connector"
            assert len(data["actions"]) == 1
            assert data["actions"][0]["name"] == "post_message"
            assert data["actions"][0]["method"] == "POST"

            # Test connector registration into tool registry
            reg_resp = await client.post("/api/meta/register-connector", json=data)
            assert reg_resp.status_code == 200
            reg_data = reg_resp.json()
            assert reg_data["status"] == "success"
            assert "slack_connector_post_message" in reg_data["registered_actions"]


@pytest.mark.asyncio
async def test_security_red_team_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        mock_redteam_json = """
        {
          "findings": [
            {
              "id": "SEC-001",
              "severity": "high",
              "nodes": ["scraper_node", "email_node"],
              "attack_example": "Webpage injects malicious payload instructing LLM to email DB credentials",
              "impact": "Exfiltration of system credentials",
              "fix": "Insert guardrail before email node"
            }
          ],
          "security_score": 82,
          "safe_to_publish": true,
          "must_fix_before_publish": []
        }
        """

        mock_llm_resp = LLMResponse(
            content=mock_redteam_json,
            prompt_tokens=500,
            completion_tokens=200,
            total_tokens=700,
            cost_usd=0.0,
            model="openrouter/free",
        )

        with patch("agentflow.meta.routes_meta.complete", return_value=mock_llm_resp):
            resp = await client.post(
                "/api/meta/red-team",
                json={
                    "workflow": {
                        "name": "Scrape & Email",
                        "nodes": [{"id": "scraper_node", "type": "scraper"}, {"id": "email_node", "type": "email"}],
                    }
                },
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["security_score"] == 82
            assert data["safe_to_publish"] is True
            assert len(data["findings"]) == 1
            assert data["findings"][0]["id"] == "SEC-001"


@pytest.mark.asyncio
async def test_marketplace_publisher_meta_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        mock_publisher_json = """
        {
          "sanitized_workflow": {"name": "Sanitized Flow"},
          "replacements": ["Replaced secret API key with {{credentials.API_KEY}}"],
          "had_secrets": true,
          "listing": {
            "title": "Lead Enrichment Assistant",
            "tagline": "Enrich leads and draft emails",
            "description": "Automated workflow that researches leads and drafts personalized emails.",
            "audience": "Sales professionals",
            "setup_steps": ["Enter CRM credentials"],
            "credentials": ["CRM_API_KEY"],
            "inputs": [{"name": "lead_name", "type": "string"}],
            "outputs": [{"name": "email_body", "type": "string"}],
            "cost_estimate": "< $0.02 / run",
            "categories": ["Sales"],
            "tags": ["lead-gen", "email"],
            "difficulty": "beginner",
            "setup_minutes": 3
          },
          "safety": {
            "external_actions": ["send_email"],
            "risk_level": "low",
            "concerns": []
          },
          "publish_ready": true,
          "blocking_issues": []
        }
        """

        mock_llm_resp = LLMResponse(
            content=mock_publisher_json,
            prompt_tokens=600,
            completion_tokens=300,
            total_tokens=900,
            cost_usd=0.0,
            model="openrouter/free",
        )

        with patch("agentflow.meta.routes_meta.complete", return_value=mock_llm_resp):
            resp = await client.post(
                "/api/meta/publisher",
                json={
                    "workflow": {"name": "Raw Flow with sk-secret"},
                    "notes": "Community submission",
                },
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["had_secrets"] is True
            assert data["publish_ready"] is True
            assert data["listing"]["title"] == "Lead Enrichment Assistant"
            assert data["safety"]["risk_level"] == "low"


@pytest.mark.asyncio
async def test_browser_operator_step_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Allowed domain navigation test
        mock_turn_json = """
        {
          "thought": "I should search for the query in the input box",
          "action": {
            "type": "type",
            "args": {"element_id": "search-input", "text": "agentflow"}
          },
          "possible_injection": false,
          "progress": "Step 1: Filled search input"
        }
        """
        mock_llm_resp = LLMResponse(
            content=mock_turn_json,
            prompt_tokens=300,
            completion_tokens=80,
            total_tokens=380,
            cost_usd=0.0,
            model="openrouter/free",
        )

        with patch("agentflow.meta.routes_meta.complete", return_value=mock_llm_resp):
            resp = await client.post(
                "/api/meta/browser-operator/step",
                json={
                    "task": "Search for agentflow",
                    "allowed_domains": ["example.com"],
                    "page_state": {
                        "url": "https://example.com",
                        "title": "Example Domain",
                        "visible_text": "Welcome to Example Domain",
                        "interactive_elements": [{"id": "search-input", "tag": "input"}],
                    },
                    "history": [],
                    "max_steps": 10,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["action"]["type"] == "type"
            assert data["action"]["args"]["element_id"] == "search-input"
            assert data["possible_injection"] is False

        # 2. Blocked domain test (hard allowlist enforcement in code)
        resp_blocked = await client.post(
            "/api/meta/browser-operator/step",
            json={
                "task": "Hack another site",
                "allowed_domains": ["example.com"],
                "page_state": {
                    "url": "https://malicious-site.com/phishing",
                    "title": "Phishing",
                    "visible_text": "Phishing page",
                    "interactive_elements": [],
                },
                "history": [],
                "max_steps": 10,
            },
        )
        assert resp_blocked.status_code == 200
        data_blocked = resp_blocked.json()
        assert data_blocked["action"]["type"] == "fail"
        assert data_blocked["possible_injection"] is True
        assert "Domain not allowed" in data_blocked["action"]["args"]["reason"]
