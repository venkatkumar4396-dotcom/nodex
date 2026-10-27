"""
Unit tests for the DAG integrity validator for Workflow Architect output.
"""
from agentflow.meta.schemas import (
    ArchitectEdge,
    ArchitectNode,
    ArchitectNodeConfig,
    WorkflowArchitectOutput,
)
from agentflow.meta.validator import validate_architect_graph


def test_valid_dag_passes():
    valid_output = WorkflowArchitectOutput(
        summary="A test valid workflow",
        nodes=[
            ArchitectNode(id="trigger_1", type="trigger_manual", label="Start"),
            ArchitectNode(id="research_1", type="research", label="Research"),
            ArchitectNode(
                id="writer_1",
                type="writer",
                label="Writer",
                data_map={"input_text": "{{research_1.output.findings}}"},
            ),
        ],
        edges=[
            ArchitectEdge(**{"from": "trigger_1", "to": "research_1"}),
            ArchitectEdge(**{"from": "research_1", "to": "writer_1"}),
        ],
    )
    violations = validate_architect_graph(
        valid_output,
        valid_node_types={"trigger_manual", "research", "writer"},
        valid_tools={"web_search"},
    )
    assert len(violations) == 0


def test_detects_multiple_triggers():
    output = WorkflowArchitectOutput(
        nodes=[
            ArchitectNode(id="trigger_1", type="trigger_manual", label="Start 1"),
            ArchitectNode(id="trigger_2", type="trigger_cron", label="Start 2"),
            ArchitectNode(id="writer_1", type="writer", label="Writer"),
        ],
        edges=[
            ArchitectEdge(**{"from": "trigger_1", "to": "writer_1"}),
            ArchitectEdge(**{"from": "trigger_2", "to": "writer_1"}),
        ],
    )
    violations = validate_architect_graph(
        output,
        valid_node_types={"trigger_manual", "trigger_cron", "writer"},
        valid_tools=set(),
    )
    assert any("exactly 1 trigger node" in v for v in violations)


def test_detects_orphan_nodes():
    output = WorkflowArchitectOutput(
        nodes=[
            ArchitectNode(id="trigger_1", type="trigger_manual", label="Start"),
            ArchitectNode(id="writer_1", type="writer", label="Writer"),
            ArchitectNode(id="lonely_1", type="research", label="Orphan"),
        ],
        edges=[
            ArchitectEdge(**{"from": "trigger_1", "to": "writer_1"}),
        ],
    )
    violations = validate_architect_graph(
        output,
        valid_node_types={"trigger_manual", "writer", "research"},
        valid_tools=set(),
    )
    assert any("orphan/unconnected" in v for v in violations)


def test_detects_invalid_forward_data_reference():
    output = WorkflowArchitectOutput(
        nodes=[
            ArchitectNode(
                id="trigger_1",
                type="trigger_manual",
                label="Start",
                data_map={"bad_ref": "{{writer_1.output.text}}"},  # writer is downstream!
            ),
            ArchitectNode(id="writer_1", type="writer", label="Writer"),
        ],
        edges=[
            ArchitectEdge(**{"from": "trigger_1", "to": "writer_1"}),
        ],
    )
    violations = validate_architect_graph(
        output,
        valid_node_types={"trigger_manual", "writer"},
        valid_tools=set(),
    )
    assert any("not upstream/ancestor" in v for v in violations)


def test_detects_excessive_feedback_loop_iterations():
    output = WorkflowArchitectOutput(
        nodes=[
            ArchitectNode(id="trigger_1", type="trigger_manual", label="Start"),
            ArchitectNode(
                id="writer_1",
                type="writer",
                label="Writer",
                config=ArchitectNodeConfig(max_loop_iterations=10),  # > 3 forbidden!
            ),
            ArchitectNode(id="reviewer_1", type="reviewer", label="Reviewer"),
        ],
        edges=[
            ArchitectEdge(**{"from": "trigger_1", "to": "writer_1"}),
            ArchitectEdge(**{"from": "writer_1", "to": "reviewer_1"}),
            ArchitectEdge(**{"from": "reviewer_1", "to": "writer_1", "condition": "needs_revision"}),
        ],
    )
    violations = validate_architect_graph(
        output,
        valid_node_types={"trigger_manual", "writer", "reviewer"},
        valid_tools=set(),
    )
    assert any("excessive max_loop_iterations" in v for v in violations)
