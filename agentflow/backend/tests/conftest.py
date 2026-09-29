"""Shared pytest fixtures for the AgentFlow test suite."""
from __future__ import annotations

import pytest
from uuid import uuid4

from agentflow.core.schemas.workflow import (
    AgentType,
    EdgeDef,
    NodeConfig,
    NodeDef,
    Position,
    RunRecord,
    WorkflowDef,
)
from agentflow.core.executor.context import RunContext


@pytest.fixture
def simple_linear_workflow() -> WorkflowDef:
    """A minimal 3-node linear workflow: A → B → C"""
    return WorkflowDef(
        id=uuid4(),
        name="test_linear",
        nodes=[
            NodeDef(id="a", type=AgentType.TRIGGER_MANUAL, label="A", config=NodeConfig()),
            NodeDef(id="b", type=AgentType.RESEARCH, label="B", config=NodeConfig()),
            NodeDef(id="c", type=AgentType.ROUTER, label="C", config=NodeConfig()),
        ],
        edges=[
            EdgeDef(id="e_ab", source="a", target="b"),
            EdgeDef(id="e_bc", source="b", target="c"),
        ],
    )


@pytest.fixture
def parallel_workflow() -> WorkflowDef:
    """Fan-out then fan-in: A → (B, C) → D"""
    return WorkflowDef(
        id=uuid4(),
        name="test_parallel",
        nodes=[
            NodeDef(id="a", type=AgentType.TRIGGER_MANUAL, label="A", config=NodeConfig()),
            NodeDef(id="b", type=AgentType.RESEARCH, label="B", config=NodeConfig()),
            NodeDef(id="c", type=AgentType.SUMMARIZER, label="C", config=NodeConfig()),
            NodeDef(id="d", type=AgentType.ROUTER, label="D", config=NodeConfig()),
        ],
        edges=[
            EdgeDef(id="e_ab", source="a", target="b"),
            EdgeDef(id="e_ac", source="a", target="c"),
            EdgeDef(id="e_bd", source="b", target="d"),
            EdgeDef(id="e_cd", source="c", target="d"),
        ],
    )


@pytest.fixture
def cyclic_workflow() -> WorkflowDef:
    """A workflow with a cycle: A → B → A (should be detected)"""
    return WorkflowDef(
        id=uuid4(),
        name="test_cyclic",
        nodes=[
            NodeDef(id="a", type=AgentType.TRIGGER_MANUAL, label="A", config=NodeConfig()),
            NodeDef(id="b", type=AgentType.RESEARCH, label="B", config=NodeConfig()),
        ],
        edges=[
            EdgeDef(id="e_ab", source="a", target="b"),
            EdgeDef(id="e_ba", source="b", target="a"),  # cycle!
        ],
    )


@pytest.fixture
def run_record(simple_linear_workflow: WorkflowDef) -> RunRecord:
    return RunRecord(
        workflow_id=simple_linear_workflow.id,
        workflow_version=1,
    )


@pytest.fixture
def run_context(
    run_record: RunRecord,
    simple_linear_workflow: WorkflowDef,
) -> RunContext:
    return RunContext(run=run_record, workflow=simple_linear_workflow)
