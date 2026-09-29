"""
Data mapping resolver — evaluates edge data_map expressions.

Supported expression syntax: {{node_id.output.field.nested}}

Design: We use a simple {{...}} template syntax rather than a full expression
language like Jinja2 or CEL, to keep it secure and auditable. The executor
resolves these templates after each node completes, before passing data to
the next node. In Phase 3 we'll add condition evaluation (e.g., "output.score >= 7").
"""
from __future__ import annotations

import re
from typing import Any

from agentflow.core.executor.context import RunContext

# Matches {{node_id.output.field}} or {{node_id.output.field.nested.path}}
_TEMPLATE_RE = re.compile(r"\{\{([\w.]+)\}\}")


def resolve_value(expr: str, context: RunContext) -> Any:
    """
    Resolve a template expression against the run context.

    Supports:
      - "{{node_id.output.field}}" → looks up node output
      - "{{shared.key}}" → looks up shared run context
      - Plain strings with no {{}} → returned as-is
      - Strings with multiple {{}} → each substituted, result is a string
    """
    matches = _TEMPLATE_RE.findall(expr)

    if not matches:
        return expr  # plain string

    if len(matches) == 1 and expr.strip() == f"{{{{{matches[0]}}}}}":
        # Single pure reference — resolve to the native type (dict, int, etc.)
        return _resolve_reference(matches[0], context)

    # Multiple references or mixed string — all become strings
    def replacer(m: re.Match[str]) -> str:
        val = _resolve_reference(m.group(1), context)
        return str(val) if val is not None else ""

    return _TEMPLATE_RE.sub(replacer, expr)


def _resolve_reference(path: str, context: RunContext) -> Any:
    """
    Resolve a dot-separated path like "node_id.output.field".

    Paths:
      - shared.key[.nested]  → RunContext.shared_context
      - node_id.output.field  → node output stored in context
    """
    parts = path.split(".")

    if parts[0] == "shared":
        obj: Any = context.run.shared_context
        for part in parts[1:]:
            if isinstance(obj, dict):
                obj = obj.get(part)
            else:
                return None
        return obj

    # Assume it's node_id.output.field[.nested...]
    if len(parts) < 2:
        return None

    node_id = parts[0]
    # parts[1] should be "output" (we could support "input" later)
    output = context.get_node_output(node_id)
    if output is None:
        return None

    obj = output
    for part in parts[2:]:
        if isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
    return obj


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


def evaluate_condition(condition: str | None, output: dict[str, Any]) -> bool:
    """
    Evaluate a simple edge condition against a node's output.

    Supported: "output.field >= value", "output.field == 'string'",
               "output.field < value", "output.field != value"

    Security note: We use a restricted eval with only the output dict in scope.
    No imports, no builtins beyond comparison. Phase 3 will replace this with
    a proper safe expression evaluator (e.g., simpleeval or CEL-Python).

    Returns True if condition is None (unconditional edge).
    """
    if condition is None:
        return True

    # Provide a minimal safe namespace: output dict + basic builtins
    safe_globals: dict[str, Any] = {"__builtins__": {}, "output": output}
    try:
        result = eval(condition, safe_globals)  # noqa: S307
        return bool(result)
    except Exception:
        # If condition can't be evaluated, treat as False (don't traverse edge)
        return False
