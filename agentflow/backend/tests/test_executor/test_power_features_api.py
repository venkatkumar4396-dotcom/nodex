"""
Tests for Enhanced Power Features:
- Batch Operations (Delete, Tag, Status, Duplicate)
- Duplicate Workflow Cleanup
- One-Click Deployment (deploy endpoint, REST trigger with Bearer token)
- HITL Pending Approvals queue
- Mini preview & execution status fields on GET /api/workflows
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
async def test_workflows_summary_has_preview_and_status():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a sample workflow
        create_res = await client.post(
            "/api/workflows",
            json={
                "name": "Preview Test Workflow",
                "description": "A workflow to test mini previews",
                "tags": ["testing", "rag"],
                "status": "draft",
                "environment": "development",
                "nodes": [
                    {
                        "id": "node_1",
                        "type": "prompt",
                        "label": "Prompt Node",
                        "position": {"x": 100.0, "y": 200.0},
                        "config": {"system_prompt": "Hello"},
                    }
                ],
                "edges": [],
            },
        )
        assert create_res.status_code == 201
        wf_id = create_res.json()["id"]

        # List workflows and verify summary attributes
        list_res = await client.get("/api/workflows")
        assert list_res.status_code == 200
        summaries = list_res.json()
        target = next((s for s in summaries if s["id"] == wf_id), None)
        assert target is not None
        assert target["name"] == "Preview Test Workflow"
        assert target["status"] in ("draft", "active", "failed")
        assert "testing" in target["tags"]
        assert len(target["nodes_preview"]) == 1
        assert target["nodes_preview"][0]["id"] == "node_1"
        assert target["nodes_preview"][0]["x"] == 100.0


@pytest.mark.asyncio
async def test_batch_operations_and_cleanup():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create two duplicate workflows
        w1 = await client.post("/api/workflows", json={"name": "Duplicate Test Flow", "tags": ["dev"]})
        w2 = await client.post("/api/workflows", json={"name": "Duplicate Test Flow", "tags": ["dev"]})
        id1 = w1.json()["id"]
        id2 = w2.json()["id"]

        # 1. Test Batch Tagging
        tag_res = await client.post(
            "/api/workflows/batch/tag",
            json={"ids": [id1, id2], "tags": ["production", "batch-tagged"], "mode": "add"},
        )
        assert tag_res.status_code == 200
        assert tag_res.json()["affected_count"] == 2

        # 2. Test Batch Status
        status_res = await client.post(
            "/api/workflows/batch/status",
            json={"ids": [id1, id2], "status": "active"},
        )
        assert status_res.status_code == 200
        assert status_res.json()["affected_count"] == 2

        # 3. Test Duplicate Cleanup
        clean_res = await client.post("/api/workflows/cleanup-duplicates")
        assert clean_res.status_code == 200
        assert clean_res.json()["affected_count"] >= 1

        # 4. Test Batch Delete
        del_res = await client.post(
            "/api/workflows/batch/delete",
            json={"ids": [id1, id2]},
        )
        assert del_res.status_code == 200


@pytest.mark.asyncio
async def test_deploy_workflow_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create workflow
        w = await client.post(
            "/api/workflows",
            json={"name": "Deployable Graph", "nodes": [], "edges": []},
        )
        wf_id = w.json()["id"]

        # Deploy
        deploy_res = await client.post(
            f"/api/workflows/{wf_id}/deploy",
            json={"environment": "production"},
        )
        assert deploy_res.status_code == 200
        deploy_data = deploy_res.json()
        assert deploy_data["workflow_id"] == wf_id
        assert deploy_data["api_key"].startswith("af_live_")
        assert "curl" in deploy_data["curl_example"].lower()
        assert "<script" in deploy_data["widget_snippet"]


@pytest.mark.asyncio
async def test_hitl_pending_approvals_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/runs/pending-approvals")
        assert res.status_code == 200
        assert isinstance(res.json(), list)
