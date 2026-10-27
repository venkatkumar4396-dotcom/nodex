"""
Tests for meta-agent API endpoints (/api/meta/architect, /api/meta/run-doctor, /api/meta/apply-patch, /api/meta/evaluator).
"""
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from agentflow.api.app import app
from agentflow.core.llm.client import LLMResponse


@pytest.mark.asyncio
async def test_apply_patch_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        initial_workflow = {
            "name": "Initial Workflow",
            "nodes": [
                {"id": "node_1", "type": "prompt", "config": {"system_prompt": "Old prompt"}},
            ],
            "edges": [],
        }
        patches = [
            {"op": "replace", "path": "/nodes/0/config/system_prompt", "value": "New patched prompt"},
            {"op": "add", "path": "/description", "value": "Patched description"},
        ]

        resp = await client.post(
            "/api/meta/apply-patch",
            json={"workflow": initial_workflow, "patches": patches},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["workflow"]["nodes"][0]["config"]["system_prompt"] == "New patched prompt"
        assert data["workflow"]["description"] == "Patched description"


@pytest.mark.asyncio
async def test_run_doctor_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        mock_doctor_json = """
        {
          "status": "diagnosed",
          "root_cause_node": "research_node",
          "category": "tool_failure",
          "evidence": "DuckDuckGo API rate limit exceeded in research_node",
          "explanation": "The research node failed because the web search tool reached its queries quota.",
          "patch": [
            { "op": "replace", "path": "/nodes/0/config/model", "value": "openrouter/free" }
          ],
          "confidence": 0.95,
          "safe_to_auto_apply": true,
          "optimizations": ["Add caching to research results"],
          "how_to_verify": "Re-run the workflow with the fallback model"
        }
        """

        mock_llm_resp = LLMResponse(
            content=mock_doctor_json,
            prompt_tokens=100,
            completion_tokens=80,
            total_tokens=180,
            cost_usd=0.0,
            model="openrouter/free",
        )

        with patch("agentflow.meta.routes_meta.complete", return_value=mock_llm_resp):
            resp = await client.post(
                "/api/meta/run-doctor",
                json={
                    "workflow": {"id": "wf_1", "nodes": []},
                    "run_trace": {"research_node": {"status": "failed", "error": "rate limit"}},
                    "complaint": "Research failed",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "diagnosed"
            assert data["root_cause_node"] == "research_node"
            assert data["category"] == "tool_failure"
            assert data["safe_to_auto_apply"] is True
            assert len(data["patch"]) == 1


@pytest.mark.asyncio
async def test_evaluator_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        mock_evaluator_json = """
        {
          "mode": "generate",
          "cases": [
            {
              "id": "tc_1",
              "input": "Acme Corp lead analysis",
              "expected_behavior": "Extract revenue and score lead",
              "scores": {
                "correctness": 5,
                "completeness": 5,
                "format_compliance": 5,
                "faithfulness": 5,
                "safety": 5,
                "instruction_following": 5
              },
              "pass": true,
              "issues": [],
              "evidence": ""
            }
          ],
          "overall_score": 5.0,
          "pass_rate": 1.0,
          "regressions": [],
          "top_3_fixes": [],
          "verdict": "ship"
        }
        """

        mock_llm_resp = LLMResponse(
            content=mock_evaluator_json,
            prompt_tokens=120,
            completion_tokens=90,
            total_tokens=210,
            cost_usd=0.0,
            model="openrouter/free",
        )

        with patch("agentflow.meta.routes_meta.complete", return_value=mock_llm_resp):
            resp = await client.post(
                "/api/meta/evaluator",
                json={
                    "workflow": {"id": "wf_1", "nodes": []},
                    "mode": "generate",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["mode"] == "generate"
            assert len(data["cases"]) == 1
            assert data["verdict"] == "ship"
            assert data["pass_rate"] == 1.0


@pytest.mark.asyncio
async def test_architect_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        mock_architect_json = """
        {
          "summary": "Researches competitor pricing and sends a Slack notification.",
          "assumptions": ["Competitor URLs are public"],
          "nodes": [
            {
              "id": "trigger_start",
              "type": "trigger_manual",
              "label": "Start Research",
              "config": { "model": "openrouter/free", "system_prompt": "Trigger prompt", "tools": [] },
              "data_map": {}
            },
            {
              "id": "research_agent",
              "type": "research",
              "label": "Competitor Researcher",
              "config": { "model": "openrouter/free", "system_prompt": "Scrape competitor", "tools": ["web_search"] },
              "data_map": {}
            }
          ],
          "edges": [
            { "from": "trigger_start", "to": "research_agent", "condition": null }
          ],
          "required_credentials": [],
          "estimated_cost_per_run": "low",
          "risks": []
        }
        """

        mock_llm_resp = LLMResponse(
            content=mock_architect_json,
            prompt_tokens=200,
            completion_tokens=150,
            total_tokens=350,
            cost_usd=0.0,
            model="openrouter/free",
        )

        with patch("agentflow.meta.routes_meta.complete", return_value=mock_llm_resp):
            resp = await client.post(
                "/api/meta/architect",
                json={"user_goal": "Research competitor prices"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "competitor" in data["summary"].lower()
            assert len(data["nodes"]) == 2
            assert len(data["edges"]) == 1
            assert data["nodes"][0]["position"]["x"] is not None
