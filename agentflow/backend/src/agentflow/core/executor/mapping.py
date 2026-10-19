"""
Data mapping resolver — evaluates edge data_map expressions and node variable interpolation.

Supported expression syntax:
  - {{nodes.<node_name_or_id>.output.<path>}}
  - {{nodes.<node_name_or_id>.input.<path>}}
  - {{nodes.<node_name_or_id>.status}}
  - {{input.<key>}} / {{trigger.<key>}}
  - {{shared.<key>}}
  - {{node_id.output.<path>}} (legacy backward-compatible)

Design: Simple, secure {{...}} template syntax without arbitrary eval vulnerabilities.
"""
from __future__ import annotations

import ast
import re
from typing import Any

import structlog

from agentflow.core.executor.context import RunContext

log = structlog.get_logger(__name__)

# Matches {{...}} including dot notation and dictionary bracket indexing
_TEMPLATE_RE = re.compile(r"\{\{([^{}]+)\}\}")


def resolve_value(expr: str, context: RunContext) -> Any:
    """
    Resolve a template expression against the run context.

    Supports:
      - "{{nodes.researcher.output.summary}}" → looks up node output
      - "{{input.lead_name}}" → looks up workflow trigger data
      - "{{shared.key}}" → looks up shared run context
      - Plain strings with no {{}} → returned as-is
      - Strings with multiple {{}} → each substituted, result is a string
    """
    if not isinstance(expr, str):
        return expr

    matches = _TEMPLATE_RE.findall(expr)
    if not matches:
        return expr  # plain string

    stripped = expr.strip()
    if len(matches) == 1 and stripped == f"{{{{{matches[0]}}}}}":
        # Single pure reference — resolve to the native type (dict, list, int, etc.)
        return _resolve_reference(matches[0].strip(), context)

    # Multiple references or mixed string — interpolate all as strings
    def replacer(m: re.Match[str]) -> str:
        val = _resolve_reference(m.group(1).strip(), context)
        return str(val) if val is not None else ""

    return _TEMPLATE_RE.sub(replacer, expr)


def _resolve_reference(raw_path: str, context: RunContext) -> Any:
    """
    Resolve a reference path like:
      - nodes.scorer.output.score
      - nodes['scorer'].output.score
      - input.company_name
      - shared.user_id
      - node_1.output.result
    """
    # Normalize bracket notation: nodes['scorer'] or nodes["scorer"] -> nodes.scorer
    norm_path = re.sub(r"\[['\"]?([^'\"\]]+)['\"]?\]", r".\1", raw_path).strip()
    parts = [p.strip() for p in norm_path.split(".") if p.strip()]

    if not parts:
        return None

    root = parts[0]

    # 1. Global input / trigger references: {{input.<key>}} or {{trigger.<key>}}
    if root in ("input", "trigger"):
        trigger_dict = context.run.trigger_data or {}
        return _traverse(trigger_dict, parts[1:])

    # 2. Shared context references: {{shared.<key>}}
    if root == "shared":
        shared_dict = context.run.shared_context or {}
        return _traverse(shared_dict, parts[1:])

    # 3. Explicit node references: {{nodes.<node_id_or_slug>.<field>...}}
    if root == "nodes":
        if len(parts) < 2:
            return None
        node_ref = parts[1]
        node_id = context.resolve_node_id(node_ref) or node_ref
        snapshot = context.get_node_snapshot(node_id) or {}

        if len(parts) == 2:
            # Entire node snapshot
            return snapshot

        target_field = parts[2]
        if target_field == "output":
            node_out = snapshot.get("output") or context.get_node_output(node_id) or {}
            return _traverse(node_out, parts[3:])
        elif target_field == "input":
            node_inp = snapshot.get("input") or context.get_node_input(node_id) or {}
            return _traverse(node_inp, parts[3:])
        else:
            return _traverse(snapshot, parts[2:])

    # 4. Direct node ID / slug reference: {{<node_id>.output.<field>}} or {{<node_id>.<field>}}
    node_id = context.resolve_node_id(root) or root
    output = context.get_node_output(node_id)
    if output is not None:
        if len(parts) >= 2 and parts[1] == "output":
            return _traverse(output, parts[2:])
        elif len(parts) >= 2 and parts[1] == "input":
            inp = context.get_node_input(node_id) or {}
            return _traverse(inp, parts[2:])
        else:
            # Directly reference field on output (e.g. {{lead_scorer.score}})
            return _traverse(output, parts[1:])

    return None


def _traverse(obj: Any, path_parts: list[str]) -> Any:
    """Traverse dot-separated path components through dicts, lists, and objects."""
    curr = obj
    for part in path_parts:
        if curr is None:
            return None
        if isinstance(curr, dict):
            curr = curr.get(part)
        elif isinstance(curr, list):
            try:
                idx = int(part)
                curr = curr[idx] if 0 <= idx < len(curr) else None
            except ValueError:
                return None
        elif hasattr(curr, part):
            curr = getattr(curr, part)
        else:
            return None
    return curr


def resolve_data_map(
    data_map: dict[str, str],
    context: RunContext,
) -> dict[str, Any]:
    """
    Resolve all template expressions in an edge's data_map.

    Returns a dict of {target_field: resolved_value} ready to be
    merged into the target node's input.
    """
    return {key: resolve_value(tmpl, context) for key, tmpl in data_map.items()}


def interpolate_templates(val: Any, context: RunContext) -> Any:
    """
    Recursively interpolate template expressions within arbitrary data structures
    (strings, dictionaries, lists).
    """
    if isinstance(val, str):
        return resolve_value(val, context)
    elif isinstance(val, dict):
        return {k: interpolate_templates(v, context) for k, v in val.items()}
    elif isinstance(val, list):
        return [interpolate_templates(item, context) for item in val]
    return val


class OutputWrapper(dict):
    """
    Dict wrapper providing attribute-style dot access for edge condition expressions.
    e.g. output.score, output.passed, output.findings[0]
    """

    def __getattr__(self, name: str) -> Any:
        try:
            val = self[name]
        except KeyError:
            return None
        if isinstance(val, dict) and not isinstance(val, OutputWrapper):
            val = OutputWrapper(val)
        return val

    def get(self, key: str, default: Any = None) -> Any:
        val = super().get(key, default)
        if isinstance(val, dict) and not isinstance(val, OutputWrapper):
            val = OutputWrapper(val)
        return val


class SafeConditionEvaluator:
    """
    Strict whitelist AST expression evaluator for edge conditions.
    Never uses eval().
    Prevents all dunder/attribute escape vectors:
    ().__class__.__base__.__subclasses__(), __import__, etc.
    """

    ALLOWED_FUNCTIONS = {
        "len": len,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "min": min,
        "max": max,
        "abs": abs,
        "round": round,
        "all": all,
        "any": any,
    }

    ALLOWED_CONSTANTS = {
        "True": True,
        "False": False,
        "None": None,
    }

    ALLOWED_OPERATORS = {
        # Comparison
        ast.Eq: lambda a, b: a == b,
        ast.NotEq: lambda a, b: a != b,
        ast.Lt: lambda a, b: a < b,
        ast.LtE: lambda a, b: a <= b,
        ast.Gt: lambda a, b: a > b,
        ast.GtE: lambda a, b: a >= b,
        ast.In: lambda a, b: a in b,
        ast.NotIn: lambda a, b: a not in b,
        ast.Is: lambda a, b: a is b,
        ast.IsNot: lambda a, b: a is not b,
        # Binary arithmetic
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b if b != 0 else 0,
        ast.FloorDiv: lambda a, b: a // b if b != 0 else 0,
        ast.Mod: lambda a, b: a % b if b != 0 else 0,
        # Unary
        ast.Not: lambda a: not a,
        ast.UAdd: lambda a: +a,
        ast.USub: lambda a: -a,
    }

    def __init__(self, context_vars: dict[str, Any]) -> None:
        self.context_vars = context_vars

    def eval(self, expr_str: str) -> Any:
        cleaned = expr_str.strip()
        if not cleaned:
            return True
        # Allow syntax like {{output.score}} >= 7
        cleaned = re.sub(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}", r"\1", cleaned)
        try:
            tree = ast.parse(cleaned, mode="eval")
        except SyntaxError:
            return False

        return self._eval_node(tree.body)

    def _eval_node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            if node.id in self.ALLOWED_CONSTANTS:
                return self.ALLOWED_CONSTANTS[node.id]
            if node.id in self.ALLOWED_FUNCTIONS:
                return self.ALLOWED_FUNCTIONS[node.id]
            return self.context_vars.get(node.id)

        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_") or node.attr.endswith("_"):
                raise ValueError(f"Dunder and private attribute access forbidden: {node.attr}")
            obj = self._eval_node(node.value)
            if obj is None:
                return None
            if isinstance(obj, (dict, OutputWrapper)):
                val = obj.get(node.attr)
                if isinstance(val, dict) and not isinstance(val, OutputWrapper):
                    val = OutputWrapper(val)
                return val
            try:
                return getattr(obj, node.attr, None)
            except Exception:
                return None

        if isinstance(node, ast.Subscript):
            obj = self._eval_node(node.value)
            idx = self._eval_node(node.slice)
            if obj is None:
                return None
            try:
                val = obj[idx]
                if isinstance(val, dict) and not isinstance(val, OutputWrapper):
                    val = OutputWrapper(val)
                return val
            except (KeyError, IndexError, TypeError):
                return None

        if isinstance(node, ast.UnaryOp):
            op_fn = self.ALLOWED_OPERATORS.get(type(node.op))
            if not op_fn:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return op_fn(self._eval_node(node.operand))

        if isinstance(node, ast.BinOp):
            op_fn = self.ALLOWED_OPERATORS.get(type(node.op))
            if not op_fn:
                raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            if left is None or right is None:
                return None
            return op_fn(left, right)

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(bool(self._eval_node(v)) for v in node.values)
            if isinstance(node.op, ast.Or):
                return any(bool(self._eval_node(v)) for v in node.values)
            raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")

        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                op_fn = self.ALLOWED_OPERATORS.get(type(op))
                if not op_fn:
                    raise ValueError(f"Unsupported comparison operator: {type(op).__name__}")
                right = self._eval_node(comparator)
                if (left is None or right is None) and type(op) not in (ast.Eq, ast.NotEq, ast.Is, ast.IsNot):
                    return False
                if not op_fn(left, right):
                    return False
                left = right
            return True

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                method_name = node.func.attr
                if method_name.startswith("_"):
                    raise ValueError(f"Dunder method call forbidden: {method_name}")
                if method_name != "get":
                    raise ValueError(f"Method '{method_name}' is not allowed in edge conditions")
                target = self._eval_node(node.func.value)
                if target is None or not hasattr(target, "get"):
                    return None
                args = [self._eval_node(a) for a in node.args]
                return target.get(*args)
            elif isinstance(node.func, ast.Name):
                fn_name = node.func.id
                if fn_name not in self.ALLOWED_FUNCTIONS:
                    raise ValueError(f"Function call '{fn_name}' is not allowed in edge conditions")
                fn = self.ALLOWED_FUNCTIONS[fn_name]
                args = [self._eval_node(a) for a in node.args]
                return fn(*args)
            raise ValueError("Call type not supported")

        if isinstance(node, (ast.List, ast.Tuple)):
            return [self._eval_node(e) for e in node.elts]

        if isinstance(node, ast.Dict):
            return {
                self._eval_node(k): self._eval_node(v)
                for k, v in zip(node.keys, node.values)
                if k is not None
            }

        raise ValueError(f"AST node '{type(node).__name__}' is not allowed in conditions")


def evaluate_condition(condition: str | None, output: dict[str, Any]) -> bool:
    """
    Evaluate an edge condition against a node's output using a strict AST whitelist parser.
    Never uses eval().
    """
    if condition is None:
        return True

    cleaned = str(condition).strip()
    if not cleaned:
        return True

    wrapped = OutputWrapper(output or {})
    context_vars: dict[str, Any] = {
        "output": wrapped,
    }
    for k, v in wrapped.items():
        if isinstance(k, str) and k.isidentifier() and not k.startswith("_"):
            context_vars[k] = v

    try:
        evaluator = SafeConditionEvaluator(context_vars)
        result = evaluator.eval(cleaned)
        return bool(result)
    except Exception as e:
        log.warning("edge_condition_evaluation_rejected", condition=condition, error=str(e))
        return False
