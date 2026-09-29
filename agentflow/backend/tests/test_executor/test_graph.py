"""Tests for the graph topological sort and execution layer builder."""
from __future__ import annotations

import pytest

from agentflow.core.executor.graph import CycleDetectedError, build_execution_graph
from agentflow.core.schemas.workflow import (
    AgentType,
    EdgeDef,
    NodeConfig,
    NodeDef,
    WorkflowDef,
)
from uuid import uuid4


class TestBuildExecutionGraph:
    def test_single_node_workflow(self) -> None:
        """A workflow with one node has one layer."""
        wf = WorkflowDef(
            id=uuid4(),
            nodes=[NodeDef(id="a", type=AgentType.TRIGGER_MANUAL, label="A", config=NodeConfig())],
            edges=[],
        )
        graph = build_execution_graph(wf)
        assert graph.layers == [["a"]]
        assert graph.node_ids == ["a"]

    def test_linear_topology(self, simple_linear_workflow: WorkflowDef) -> None:
        """A → B → C produces three sequential layers."""
        graph = build_execution_graph(simple_linear_workflow)
        assert len(graph.layers) == 3
        assert graph.layers[0] == ["a"]
        assert graph.layers[1] == ["b"]
        assert graph.layers[2] == ["c"]

    def test_parallel_topology(self, parallel_workflow: WorkflowDef) -> None:
        """A → (B, C) → D produces layers [A], [B, C], [D]."""
        graph = build_execution_graph(parallel_workflow)
        assert len(graph.layers) == 3
        assert graph.layers[0] == ["a"]
        assert set(graph.layers[1]) == {"b", "c"}
        assert graph.layers[2] == ["d"]

    def test_cycle_detection(self, cyclic_workflow: WorkflowDef) -> None:
        """A graph with a cycle raises CycleDetectedError."""
        with pytest.raises(CycleDetectedError, match="cycle"):
            build_execution_graph(cyclic_workflow)

    def test_empty_workflow_raises(self) -> None:
        """A workflow with no nodes raises ValueError."""
        wf = WorkflowDef(id=uuid4(), nodes=[], edges=[])
        with pytest.raises(ValueError, match="no nodes"):
            build_execution_graph(wf)

    def test_successors(self, simple_linear_workflow: WorkflowDef) -> None:
        """successors() returns correct downstream nodes."""
        graph = build_execution_graph(simple_linear_workflow)
        assert graph.successors("a") == ["b"]
        assert graph.successors("b") == ["c"]
        assert graph.successors("c") == []

    def test_diamond_topology(self) -> None:
        """A → B, A → C, B → D, C → D — D should be in layer 3."""
        wf = WorkflowDef(
            id=uuid4(),
            nodes=[
                NodeDef(id="a", type=AgentType.TRIGGER_MANUAL, label="A", config=NodeConfig()),
                NodeDef(id="b", type=AgentType.RESEARCH, label="B", config=NodeConfig()),
                NodeDef(id="c", type=AgentType.SUMMARIZER, label="C", config=NodeConfig()),
                NodeDef(id="d", type=AgentType.ROUTER, label="D", config=NodeConfig()),
            ],
            edges=[
                EdgeDef(id="ab", source="a", target="b"),
                EdgeDef(id="ac", source="a", target="c"),
                EdgeDef(id="bd", source="b", target="d"),
                EdgeDef(id="cd", source="c", target="d"),
            ],
        )
        graph = build_execution_graph(wf)
        assert graph.layers[0] == ["a"]
        assert set(graph.layers[1]) == {"b", "c"}
        assert graph.layers[2] == ["d"]

    def test_multiple_roots(self) -> None:
        """Two unconnected root nodes should both be in layer 0."""
        wf = WorkflowDef(
            id=uuid4(),
            nodes=[
                NodeDef(id="a", type=AgentType.TRIGGER_MANUAL, label="A", config=NodeConfig()),
                NodeDef(id="b", type=AgentType.TRIGGER_MANUAL, label="B", config=NodeConfig()),
                NodeDef(id="c", type=AgentType.RESEARCH, label="C", config=NodeConfig()),
            ],
            edges=[
                EdgeDef(id="ac", source="a", target="c"),
                EdgeDef(id="bc", source="b", target="c"),
            ],
        )
        graph = build_execution_graph(wf)
        assert set(graph.layers[0]) == {"a", "b"}
        assert graph.layers[1] == ["c"]
