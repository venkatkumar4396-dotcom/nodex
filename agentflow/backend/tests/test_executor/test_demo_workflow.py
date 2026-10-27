"""Tests for the demo workflow definition."""
from __future__ import annotations

from agentflow.core.executor.graph import build_execution_graph
from agentflow.core.schemas.workflow import AgentType
from agentflow.core.workflows.demo_workflow import build_demo_workflow


class TestDemoWorkflow:
    def test_workflow_has_all_expected_nodes(self) -> None:
        wf = build_demo_workflow()
        node_ids = {n.id for n in wf.nodes}
        assert "trigger" in node_ids
        assert "research" in node_ids
        assert "classifier" in node_ids
        assert "writer" in node_ids
        assert "reviewer" in node_ids

    def test_workflow_has_correct_node_types(self) -> None:
        wf = build_demo_workflow()
        type_map = {n.id: n.type for n in wf.nodes}
        assert type_map["trigger"] == AgentType.TRIGGER_MANUAL
        assert type_map["research"] == AgentType.RESEARCH
        assert type_map["classifier"] == AgentType.ROUTER
        assert type_map["writer"] == AgentType.WRITER
        assert type_map["reviewer"] == AgentType.REVIEWER

    def test_workflow_is_topologically_valid(self) -> None:
        """Demo workflow must be acyclic (passes graph build)."""
        wf = build_demo_workflow()
        graph = build_execution_graph(wf)
        assert len(graph.layers) > 0

    def test_classifier_to_writer_edge_has_condition(self) -> None:
        wf = build_demo_workflow()
        edges = {e.id: e for e in wf.edges}
        edge = edges.get("e_classifier_writer")
        assert edge is not None
        assert edge.condition is not None
        assert "7" in edge.condition  # threshold is 7

    def test_writer_to_reviewer_edge_has_data_map(self) -> None:
        wf = build_demo_workflow()
        edges = {e.id: e for e in wf.edges}
        edge = edges.get("e_writer_reviewer")
        assert edge is not None
        assert "subject" in edge.data_map
        assert "body" in edge.data_map

    def test_global_cost_limit_is_set(self) -> None:
        wf = build_demo_workflow()
        assert wf.global_max_cost_usd is not None
        assert wf.global_max_cost_usd > 0

    def test_nodes_have_retry_policies(self) -> None:
        wf = build_demo_workflow()
        for node in wf.nodes:
            if node.id != "trigger":
                assert node.config.retry_policy.max_attempts >= 2

    def test_writer_has_extra_config(self) -> None:
        wf = build_demo_workflow()
        writer = next(n for n in wf.nodes if n.id == "writer")
        assert "tone" in writer.config.extra
        assert "max_words" in writer.config.extra

    def test_reviewer_has_threshold_config(self) -> None:
        wf = build_demo_workflow()
        reviewer = next(n for n in wf.nodes if n.id == "reviewer")
        assert "threshold" in reviewer.config.extra
        assert reviewer.config.extra["threshold"] >= 7

    def test_workflow_serialization(self) -> None:
        """WorkflowDef can be serialized to JSON and deserialized."""
        wf = build_demo_workflow()
        wf_json = wf.model_dump_json()
        wf2 = build_demo_workflow().model_validate_json(wf_json)
        # New instance, different ID, but same structure
        assert len(wf2.nodes) == len(wf.nodes)
        assert len(wf2.edges) == len(wf.edges)
