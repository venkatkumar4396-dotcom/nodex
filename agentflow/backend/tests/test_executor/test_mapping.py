"""Tests for data mapping resolution."""
from __future__ import annotations

import pytest

from agentflow.core.executor.context import RunContext
from agentflow.core.executor.mapping import (
    evaluate_condition,
    resolve_data_map,
    resolve_value,
)
from agentflow.core.schemas.workflow import (
    RunRecord,
    WorkflowDef,
)


@pytest.fixture
def context_with_outputs(simple_linear_workflow: WorkflowDef) -> RunContext:
    run = RunRecord(workflow_id=simple_linear_workflow.id, workflow_version=1)
    ctx = RunContext(run=run, workflow=simple_linear_workflow)
    ctx.record_node_output("research", {
        "summary": "Acme Corp is a growing SaaS company",
        "confidence": 0.85,
        "key_findings": [{"title": "Hiring surge", "detail": "50 new engineers", "relevance_score": 0.9}],
    })
    ctx.record_node_output("classifier", {
        "score": 8,
        "branch": "qualified",
        "lead_name": "Sarah Chen",
    })
    ctx.run.shared_context["user_timezone"] = "UTC"
    return ctx


class TestResolveValue:
    def test_plain_string(self, context_with_outputs: RunContext) -> None:
        assert resolve_value("hello world", context_with_outputs) == "hello world"

    def test_simple_node_output_reference(self, context_with_outputs: RunContext) -> None:
        val = resolve_value("{{research.output.summary}}", context_with_outputs)
        assert val == "Acme Corp is a growing SaaS company"

    def test_nested_reference(self, context_with_outputs: RunContext) -> None:
        val = resolve_value("{{classifier.output.score}}", context_with_outputs)
        assert val == 8

    def test_shared_context_reference(self, context_with_outputs: RunContext) -> None:
        val = resolve_value("{{shared.user_timezone}}", context_with_outputs)
        assert val == "UTC"

    def test_missing_node_returns_none(self, context_with_outputs: RunContext) -> None:
        val = resolve_value("{{nonexistent.output.field}}", context_with_outputs)
        assert val is None

    def test_mixed_template_string(self, context_with_outputs: RunContext) -> None:
        """Multiple references in one string → all substituted as strings."""
        val = resolve_value(
            "Lead: {{classifier.output.lead_name}} scored {{classifier.output.score}}",
            context_with_outputs,
        )
        assert val == "Lead: Sarah Chen scored 8"

    def test_no_template_returns_original(self, context_with_outputs: RunContext) -> None:
        assert resolve_value("plain text", context_with_outputs) == "plain text"


class TestResolveDataMap:
    def test_resolves_all_fields(self, context_with_outputs: RunContext) -> None:
        data_map = {
            "summary": "{{research.output.summary}}",
            "score": "{{classifier.output.score}}",
            "tz": "{{shared.user_timezone}}",
        }
        result = resolve_data_map(data_map, context_with_outputs)
        assert result["summary"] == "Acme Corp is a growing SaaS company"
        assert result["score"] == 8
        assert result["tz"] == "UTC"


class TestEvaluateCondition:
    def test_none_condition_always_true(self) -> None:
        assert evaluate_condition(None, {}) is True

    def test_simple_comparison_true(self) -> None:
        assert evaluate_condition("output.get('score', 0) >= 7", {"score": 8}) is True

    def test_simple_comparison_false(self) -> None:
        assert evaluate_condition("output.get('score', 0) >= 7", {"score": 5}) is False

    def test_string_comparison(self) -> None:
        assert evaluate_condition("output.get('branch') == 'qualified'", {"branch": "qualified"}) is True

    def test_invalid_condition_returns_false(self) -> None:
        """Unparseable conditions default to False (safe failure)."""
        assert evaluate_condition("this is not valid python", {}) is False

    def test_empty_output(self) -> None:
        assert evaluate_condition("output.get('score', 0) >= 7", {}) is False

    def test_dunder_attribute_traversal_exploit_is_rejected(self) -> None:
        """Verify ().__class__.__base__.__subclasses__() and all dunder exploits are rejected and never executed."""
        assert evaluate_condition("().__class__.__base__.__subclasses__()", {}) is False
        assert evaluate_condition("output.__class__.__base__.__subclasses__()", {"score": 8}) is False
        assert evaluate_condition("().__class__.__mro__[1].__subclasses__()", {}) is False
        assert evaluate_condition("output.__globals__", {"score": 8}) is False

    def test_arbitrary_code_execution_is_rejected(self) -> None:
        """Arbitrary system imports and functions are rejected."""
        assert evaluate_condition("__import__('os').system('id')", {}) is False
        assert evaluate_condition("open('/etc/passwd').read()", {}) is False
        assert evaluate_condition("eval('1+1')", {}) is False

    def test_template_syntax_in_condition(self) -> None:
        """Template interpolation syntax like {{output.score}} >= 7 is safely supported."""
        assert evaluate_condition("{{output.score}} >= 7", {"score": 8}) is True
        assert evaluate_condition("{{output.score}} >= 7", {"score": 4}) is False
        assert evaluate_condition("{{score}} == 8 and {{details.tier}} == 'gold'", {"score": 8, "details": {"tier": "gold"}}) is True
