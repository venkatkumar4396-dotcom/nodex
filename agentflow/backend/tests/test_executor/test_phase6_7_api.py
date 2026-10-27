"""
Tests for Phase 6 & 7 API Endpoints:
- GET /api/agent-types
- GET /api/tools
- POST /api/workflows/generate
- GET /api/analytics
- POST /api/runs/{id}/cancel
- POST /api/runs/{id}/approve & reject
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from agentflow.api.app import app
from agentflow.db.engine import Base, engine


@pytest.fixture(autouse=True)
async def init_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_agent_types():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/agent-types")
        assert res.status_code == 200
        types = [item["type"] for item in res.json()]
        assert "human_approval" in types
        assert "supervisor" in types
        assert "rag" in types
        assert "memory" in types


@pytest.mark.asyncio
async def test_get_tools():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/tools")
        assert res.status_code == 200
        tool_names = [t["name"] for t in res.json()]
        assert "web_search" in tool_names


@pytest.mark.asyncio
async def test_generate_workflow_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/workflows/generate",
            json={"prompt": "Build customer complaint triage workflow with human approval"},
        )
        assert res.status_code == 201
        data = res.json()
        assert "id" in data
        assert len(data["nodes"]) >= 3
        assert any(n["type"] == "human_approval" for n in data["nodes"])


@pytest.mark.asyncio
async def test_get_analytics_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/analytics")
        assert res.status_code == 200
        data = res.json()
        assert "total_runs" in data
        assert "success_rate" in data
        assert "top_agents" in data


@pytest.mark.asyncio
async def test_run_cancellation_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a workflow
        wf_res = await client.post(
            "/api/workflows/generate",
            json={"prompt": "Simple research pipeline"},
        )
        wf_id = wf_res.json()["id"]

        # 2. Trigger run
        run_res = await client.post(
            f"/api/workflows/{wf_id}/run",
            json={"trigger_data": {"topic": "AI test"}},
        )
        assert run_res.status_code == 202
        run_id = run_res.json()["id"]

        # 3. Cancel run
        cancel_res = await client.post(f"/api/runs/{run_id}/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_run_approval_and_resume_api():
    import asyncio
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a direct trigger -> human_approval workflow
        wf_res = await client.post(
            "/api/workflows",
            json={
                "name": "Direct Approval Test",
                "nodes": [
                    {"id": "t", "type": "trigger_manual", "label": "Start", "config": {}},
                    {"id": "appr", "type": "human_approval", "label": "Approval", "config": {}},
                ],
                "edges": [
                    {"id": "e1", "source": "t", "target": "appr"},
                ],
            },
        )
        assert wf_res.status_code == 201
        wf_id = wf_res.json()["id"]

        # Trigger run
        run_res = await client.post(
            f"/api/workflows/{wf_id}/run",
            json={"trigger_data": {"amount": 500}},
        )
        assert run_res.status_code == 202
        run_id = run_res.json()["id"]

        # Wait for run to pause at approval gate
        for _ in range(300):
            await asyncio.sleep(0.05)
            detail_res = await client.get(f"/api/runs/{run_id}")
            if detail_res.json()["status"] == "paused":
                break

        detail = (await client.get(f"/api/runs/{run_id}")).json()
        assert detail["status"] == "paused"

        # Approve run
        approve_res = await client.post(
            f"/api/runs/{run_id}/approve",
            json={"reviewer": "manager@company.com", "notes": "Approved for VIP customer"},
        )
        assert approve_res.status_code == 200
        assert approve_res.json()["status"] == "running"

        # Wait for run to complete
        for _ in range(300):
            await asyncio.sleep(0.05)
            detail_res = await client.get(f"/api/runs/{run_id}")
            if detail_res.json()["status"] in ("completed", "failed"):
                break

        final_detail = (await client.get(f"/api/runs/{run_id}")).json()
        assert final_detail["status"] == "completed"


@pytest.mark.asyncio
async def test_run_rejection_api():
    import asyncio
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a direct trigger -> human_approval workflow
        wf_res = await client.post(
            "/api/workflows",
            json={
                "name": "Direct Rejection Test",
                "nodes": [
                    {"id": "t", "type": "trigger_manual", "label": "Start", "config": {}},
                    {"id": "appr", "type": "human_approval", "label": "Approval", "config": {}},
                ],
                "edges": [
                    {"id": "e1", "source": "t", "target": "appr"},
                ],
            },
        )
        assert wf_res.status_code == 201
        wf_id = wf_res.json()["id"]

        # Trigger run
        run_res = await client.post(
            f"/api/workflows/{wf_id}/run",
            json={"trigger_data": {"amount": 50000}},
        )
        assert run_res.status_code == 202
        run_id = run_res.json()["id"]

        # Wait for pause
        for _ in range(300):
            await asyncio.sleep(0.05)
            detail_res = await client.get(f"/api/runs/{run_id}")
            if detail_res.json()["status"] == "paused":
                break

        detail = (await client.get(f"/api/runs/{run_id}")).json()
        assert detail["status"] == "paused"

        # Reject run
        reject_res = await client.post(
            f"/api/runs/{run_id}/reject",
            json={"reviewer": "fraud_officer", "notes": "Exceeds threshold"},
        )
        assert reject_res.status_code == 200
        assert reject_res.json()["status"] == "failed"
