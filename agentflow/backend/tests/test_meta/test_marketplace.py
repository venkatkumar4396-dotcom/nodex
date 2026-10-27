"""
Tests for Marketplace endpoints and Automatic Quality Gate:
  - Listing templates and details
  - Automatic Quality Gate (#7 Red-Team + #4 Evaluator must pass before #6 Publisher lists)
  - 1-Click Install with credential substitution
  - Sandbox Test Run
  - Fork & Remix
  - Rating system
"""
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from agentflow.api.app import app
from agentflow.core.llm.client import LLMResponse


@pytest.mark.asyncio
async def test_marketplace_list_and_get():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # List templates
        resp = await client.get("/api/marketplace/templates")
        assert resp.status_code == 200
        templates = resp.json()
        assert len(templates) >= 4

        # Verify showcase template
        tpl_ids = [t["id"] for t in templates]
        assert "tpl-lead-outreach" in tpl_ids

        # Filter by category
        cat_resp = await client.get("/api/marketplace/templates?category=Sales")
        assert cat_resp.status_code == 200
        cat_items = cat_resp.json()
        assert any(t["id"] == "tpl-lead-outreach" for t in cat_items)

        # Get specific template
        get_resp = await client.get("/api/marketplace/templates/tpl-lead-outreach")
        assert get_resp.status_code == 200
        lead_tpl = get_resp.json()
        assert lead_tpl["title"] == "Lead Enrichment & Outreach with Approval Guard"
        assert lead_tpl["risk_level"] == "low"
        assert len(lead_tpl["credentials_needed"]) == 2


@pytest.mark.asyncio
async def test_marketplace_automatic_gate_failure_on_red_team():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Simulate Red-Team detecting critical vulnerability
        mock_redteam_failed = """
        {
          "findings": [
            {
              "id": "SEC-BLOCK-01",
              "severity": "critical",
              "nodes": ["unapproved_delete"],
              "attack_example": "Direct deletion of database without human confirmation",
              "impact": "Irreversible catastrophic data destruction",
              "fix": "Mandatory human approval gate before destructive node"
            }
          ],
          "security_score": 45,
          "safe_to_publish": false,
          "must_fix_before_publish": ["Add human approval gate to node unapproved_delete"]
        }
        """

        mock_llm_resp = LLMResponse(
            content=mock_redteam_failed,
            prompt_tokens=400,
            completion_tokens=150,
            total_tokens=550,
            cost_usd=0.0,
            model="openrouter/free",
        )

        with patch("agentflow.marketplace.routes_marketplace.complete", return_value=mock_llm_resp):
            resp = await client.post(
                "/api/marketplace/publish",
                json={
                    "workflow": {
                        "name": "Dangerous Auto-Delete Flow",
                        "nodes": [{"id": "unapproved_delete", "type": "code"}],
                        "edges": [],
                    }
                },
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["passed"] is False
            assert data["gate_stage"] == "red_team"
            assert data["listing_item"] is None
            assert any("below the 70 point threshold" in r for r in data["reasons"])


@pytest.mark.asyncio
async def test_marketplace_automatic_gate_full_pass_and_publish():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 1: Red-Team passes
        mock_redteam_pass = """
        {
          "findings": [],
          "security_score": 95,
          "safe_to_publish": true,
          "must_fix_before_publish": []
        }
        """
        # Step 2: Evaluator passes
        mock_evaluator_pass = """
        {
          "mode": "generate",
          "cases": [],
          "overall_score": 4.8,
          "pass_rate": 0.95,
          "regressions": [],
          "top_3_fixes": [],
          "verdict": "ship"
        }
        """
        # Step 3: Publisher sanitizes and documents
        mock_publisher_pass = """
        {
          "sanitized_workflow": {"name": "Certified Safe Lead Flow"},
          "replacements": ["Sanitized secret key"],
          "had_secrets": false,
          "listing": {
            "title": "Certified Safe Lead Flow",
            "tagline": "Safe verified lead flow",
            "description": "Passed all automated security and quality gates.",
            "audience": "Enterprises",
            "setup_steps": ["Deploy and configure"],
            "credentials": ["API_KEY"],
            "inputs": [{"name": "lead_id", "type": "string"}],
            "outputs": [{"name": "lead_score", "type": "number"}],
            "cost_estimate": "< $0.01 / run",
            "categories": ["Sales"],
            "tags": ["certified", "safe"],
            "difficulty": "beginner",
            "setup_minutes": 2
          },
          "safety": {
            "external_actions": [],
            "risk_level": "low",
            "concerns": []
          },
          "publish_ready": true,
          "blocking_issues": []
        }
        """

        responses = [
            LLMResponse(content=mock_redteam_pass, prompt_tokens=100, completion_tokens=50, total_tokens=150, cost_usd=0.0, model="openrouter/free"),
            LLMResponse(content=mock_evaluator_pass, prompt_tokens=100, completion_tokens=50, total_tokens=150, cost_usd=0.0, model="openrouter/free"),
            LLMResponse(content=mock_publisher_pass, prompt_tokens=100, completion_tokens=50, total_tokens=150, cost_usd=0.0, model="openrouter/free"),
        ]

        with patch("agentflow.marketplace.routes_marketplace.complete", side_effect=responses):
            resp = await client.post(
                "/api/marketplace/publish",
                json={
                    "workflow": {"name": "Certified Safe Lead Flow", "nodes": [], "edges": []},
                    "notes": "Fully verified enterprise workflow",
                },
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["passed"] is True
            assert data["gate_stage"] == "passed"
            assert data["listing_item"] is not None
            assert data["listing_item"]["title"] == "Certified Safe Lead Flow"
            assert data["listing_item"]["security_score"] == 95
            assert data["listing_item"]["evaluation_score"] == 4.8


@pytest.mark.asyncio
async def test_marketplace_install_with_credentials():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/marketplace/install",
            json={
                "template_id": "tpl-lead-outreach",
                "credentials": {
                    "EMAIL_API_KEY": "sk-real-email-key-12345",
                    "CRM_API_KEY": "crm-secret-xyz",
                },
                "target_name": "My Custom Production Outreach",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["workflow"]["name"] == "My Custom Production Outreach"


@pytest.mark.asyncio
async def test_marketplace_sandbox_test():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/marketplace/sandbox-test",
            json={
                "template_id": "tpl-lead-outreach",
                "sample_inputs": {"lead_name": "Alice Johnson", "company": "Starlight Inc"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["sandbox_mode"] is True
        assert len(data["execution_trace"]) >= 4


@pytest.mark.asyncio
async def test_marketplace_fork_and_rate():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Fork template
        fork_resp = await client.post(
            "/api/marketplace/fork",
            json={"template_id": "tpl-competitor-monitor", "new_name": "My Custom Price Tracker"},
        )
        assert fork_resp.status_code == 200
        fork_data = fork_resp.json()
        assert fork_data["status"] == "success"
        forked_id = fork_data["forked_template"]["id"]
        assert "fork-" in forked_id

        # Rate template
        rate_resp = await client.post(
            "/api/marketplace/rate",
            json={"template_id": "tpl-competitor-monitor", "rating": 5.0, "comment": "Saved 10 hours a week!"},
        )
        assert rate_resp.status_code == 200
        rate_data = rate_resp.json()
        assert rate_data["status"] == "success"
        assert rate_data["new_rating"] >= 4.0
