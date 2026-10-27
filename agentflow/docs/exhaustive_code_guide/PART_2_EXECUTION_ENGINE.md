# Part 2: The Topological Execution Engine
## Exhaustive Code & Line-by-Line Architectural Guide

---

## 1. `src/agentflow/core/executor/context.py`

### 1.1 Complete Source Code
```python
"""
RunContext — the shared mutable state for a single workflow run.

All agents receive a reference to the RunContext. They can:
  - Read any previously completed node's output via get_node_output()
  - Write to shared_context (key-value bag for cross-agent communication)
  - Check run-level limits (cost, steps)
"""
from __future__ import annotations

import time
from typing import Any

import structlog

from agentflow.core.schemas.workflow import (
    AgentMessage,
    NodeRunRecord,
    NodeRunStatus,
    RunRecord,
    RunStatus,
    WorkflowDef,
)

log = structlog.get_logger(__name__)


class CostLimitExceeded(Exception):
    """Raised when a run exceeds its total cost budget."""


class StepLimitExceeded(Exception):
    """Raised when a run exceeds its max step count."""


class RunContext:
    """Mutable run-level state passed to every node executor."""

    def __init__(self, run: RunRecord, workflow: WorkflowDef) -> None:
        self.run = run
        self.workflow = workflow
        self._node_outputs: dict[str, dict[str, Any]] = {}
        self._step_count: int = 0
        self._loop_counts: dict[str, int] = {}  # edge_id -> iteration count
        self.current_node_id: str = ""

    # ── Node output registry ─────────────────────────────────────────────────

    def record_node_output(self, node_id: str, data: dict[str, Any]) -> None:
        """Store a node's validated output so downstream nodes can reference it."""
        self._node_outputs[node_id] = data

    def get_node_output(self, node_id: str) -> dict[str, Any] | None:
        return self._node_outputs.get(node_id)

    def get_all_outputs(self) -> dict[str, dict[str, Any]]:
        return dict(self._node_outputs)

    # ── Shared context ────────────────────────────────────────────────────────

    def set_shared(self, key: str, value: Any) -> None:
        self.run.shared_context[key] = value

    def get_shared(self, key: str, default: Any = None) -> Any:
        return self.run.shared_context.get(key, default)

    # ── Cost & step tracking ─────────────────────────────────────────────────

    def add_cost(self, cost_usd: float) -> None:
        self.run.total_cost_usd += cost_usd
        self.run.total_tokens += 0  # tokens updated separately

    def add_tokens(self, prompt: int, completion: int) -> None:
        self.run.total_tokens += prompt + completion

    def increment_step(self) -> None:
        self._step_count += 1
        max_steps = self.workflow.global_max_steps
        if self._step_count > max_steps:
            raise StepLimitExceeded(
                f"Run exceeded max_steps={max_steps}. "
                "Increase global_max_steps or check for loops."
            )

    def check_cost_limit(self) -> None:
        limit = self.workflow.global_max_cost_usd
        if limit is not None and self.run.total_cost_usd > limit:
            raise CostLimitExceeded(
                f"Run cost ${self.run.total_cost_usd:.4f} exceeded "
                f"budget ${limit:.4f}"
            )

    # ── Loop tracking ─────────────────────────────────────────────────────────

    def get_loop_count(self, edge_id: str) -> int:
        return self._loop_counts.get(edge_id, 0)

    def increment_loop(self, edge_id: str) -> int:
        self._loop_counts[edge_id] = self._loop_counts.get(edge_id, 0) + 1
        return self._loop_counts[edge_id]

    # ── Node run record management ────────────────────────────────────────────

    def start_node_run(self, node_run: NodeRunRecord) -> None:
        node_run.status = NodeRunStatus.RUNNING
        node_run.started_at = time.time()
        self.run.node_runs.append(node_run)
        log.info(
            "node_started",
            run_id=str(self.run.id),
            node_id=node_run.node_id,
            agent_type=node_run.agent_type.value,
            attempt=node_run.attempt,
        )

    def finish_node_run(
        self,
        node_run: NodeRunRecord,
        message: AgentMessage,
    ) -> None:
        node_run.status = message.status
        node_run.output = message.data
        node_run.completed_at = time.time()
        if node_run.started_at:
            node_run.duration_ms = int((node_run.completed_at - node_run.started_at) * 1000)
        node_run.prompt_tokens = message.metadata.prompt_tokens
        node_run.completion_tokens = message.metadata.completion_tokens
        node_run.cost_usd = message.metadata.cost_usd

        self.add_tokens(message.metadata.prompt_tokens, message.metadata.completion_tokens)
        self.add_cost(message.metadata.cost_usd)

        if message.status == NodeRunStatus.COMPLETED:
            self.record_node_output(node_run.node_id, message.data)
            log.info(
                "node_completed",
                run_id=str(self.run.id),
                node_id=node_run.node_id,
                duration_ms=node_run.duration_ms,
                tokens=message.metadata.total_tokens,
                cost_usd=message.metadata.cost_usd,
            )
        else:
            node_run.error = "; ".join(message.errors)
            log.error(
                "node_failed",
                run_id=str(self.run.id),
                node_id=node_run.node_id,
                errors=message.errors,
            )

    def finalize_run(self, status: RunStatus, error: str | None = None) -> None:
        self.run.status = status
        self.run.error = error
        self.run.completed_at = time.time()
        log.info(
            "run_completed",
            run_id=str(self.run.id),
            status=status.value,
            total_tokens=self.run.total_tokens,
            total_cost_usd=self.run.total_cost_usd,
            step_count=self._step_count,
        )
```

### 1.2 Line-by-Line Breakdown & Explanation
- **Lines 33–38**: Custom exception classes `CostLimitExceeded` and `StepLimitExceeded`. Raising distinct exception classes allows the runner to categorize the failure and update the workflow status with clear error messages.
- **Lines 41–56**: `RunContext.__init__`:
  - `self.run = run`: References the mutable `RunRecord`.
  - `self.workflow = workflow`: References the immutable `WorkflowDef`.
  - `self._node_outputs`: Dictionary mapping `node_id -> output_dict`.
  - `self._step_count`: Global counter incremented on every node execution attempt.
  - `self._loop_counts`: Tracks cycle iterations per edge.
  - `self.current_node_id`: Context variable indicating which node is actively executing.
- **Lines 60–68**: `record_node_output()` and `get_node_output()`: Central registry for validated node outputs. When Node A finishes, its validated dictionary is stored here; downstream Node B resolves its `data_map` templates by reading from this registry.
- **Lines 72–76**: `set_shared()` and `get_shared()`: Provides global bag storage for run-wide metadata (e.g. `user_id`, `organization_id`) that applies to all agents without requiring explicit edge connections.
- **Lines 80–103**: Budget and step limit enforcement:
  - `add_cost()` and `add_tokens()`: Accumulates usage across all nodes.
  - `increment_step()`: Throws `StepLimitExceeded` if `step_count > workflow.global_max_steps`, preventing infinite execution loops.
  - `check_cost_limit()`: Throws `CostLimitExceeded` if accumulated dollar cost exceeds `workflow.global_max_cost_usd`.
- **Lines 115–162**: `start_node_run()` and `finish_node_run()`:
  - Transitions node status: `PENDING` $\rightarrow$ `RUNNING` $\rightarrow$ `COMPLETED` or `FAILED`.
  - Records execution duration: `duration_ms = int((completed_at - started_at) * 1000)`.
  - Extracts token counts and cost from `AgentMessage.metadata` and adds them to run totals.
- **Lines 163–175**: `finalize_run()`: Marks workflow status (`COMPLETED` or `FAILED`), records completion timestamp, and logs summary telemetry.

### 1.3 Why We Built This Instead of Alternatives
- **Why pass an explicit `RunContext` instead of global state or Python `contextvars`?**  
  In a production multi-tenant backend (FastAPI + Arq), hundreds of workflow runs execute simultaneously. Global variables cause cross-tenant state leaks. An explicit `RunContext` instance passed down the call chain guarantees total isolation and thread safety.

---

## 2. `src/agentflow/core/executor/graph.py`

### 2.1 Complete Source Code
```python
"""
Graph utilities: topological sort and execution layer builder.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from agentflow.core.schemas.workflow import EdgeDef, WorkflowDef


class CycleDetectedError(ValueError):
    """Raised if the workflow graph contains a cycle."""


@dataclass
class ExecutionGraph:
    """
    Processed representation of a WorkflowDef graph.
    """
    layers: list[list[str]] = field(default_factory=list)
    adjacency: dict[str, list[str]] = field(default_factory=dict)
    in_degree: dict[str, int] = field(default_factory=dict)
    node_ids: list[str] = field(default_factory=list)
    feedback_edges: list[EdgeDef] = field(default_factory=list)

    def successors(self, node_id: str) -> list[str]:
        return self.adjacency.get(node_id, [])

    def get_feedback_edges(self, node_id: str) -> list[EdgeDef]:
        """Return all outgoing feedback edges from the given node."""
        return [e for e in self.feedback_edges if e.source == node_id]


def build_execution_graph(workflow: WorkflowDef) -> ExecutionGraph:
    """
    Build an ExecutionGraph from a WorkflowDef using Kahn's algorithm.
    Partitions edges into forward DAG edges and cyclical feedback edges.
    """
    nodes = workflow.nodes
    edges = workflow.edges

    if not nodes:
        raise ValueError("Workflow has no nodes.")

    node_ids = [n.id for n in nodes]
    forward_edges = [e for e in edges if not getattr(e, "is_feedback", False)]
    feedback_edges = [e for e in edges if getattr(e, "is_feedback", False)]

    adjacency: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}

    for edge in forward_edges:
        adjacency[edge.source].append(edge.target)
        in_degree[edge.target] += 1

    # Kahn's BFS — groups nodes into layers
    queue: deque[str] = deque(nid for nid in node_ids if in_degree[nid] == 0)
    layers: list[list[str]] = []
    processed = 0

    while queue:
        layer_size = len(queue)
        current_layer: list[str] = []

        for _ in range(layer_size):
            node_id = queue.popleft()
            current_layer.append(node_id)
            processed += 1

            for successor in adjacency[node_id]:
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    queue.append(successor)

        layers.append(current_layer)

    if processed != len(node_ids):
        unprocessed = [nid for nid in node_ids if in_degree.get(nid, 0) > 0]
        raise CycleDetectedError(
            f"Workflow graph contains an unresolved cycle among forward edges. "
            f"Unresolved nodes: {unprocessed}. "
            "Set `is_feedback=True` on back-edges to declare intentional feedback loops."
        )

    return ExecutionGraph(
        layers=layers,
        adjacency=dict(adjacency),
        in_degree={nid: 0 for nid in node_ids},
        node_ids=node_ids,
        feedback_edges=feedback_edges,
    )
```

### 2.2 Line-by-Line Breakdown & Explanation
- **Lines 31–49**: `@dataclass class ExecutionGraph`: Holds precomputed graph metadata:
  - `layers: list[list[str]]`: Topological layers. Layer 0 has no dependencies. Nodes in each layer can execute in parallel.
  - `adjacency`: Directed forward graph adjacency list.
  - `in_degree`: In-degree counts for each node.
  - `feedback_edges`: List of back-edges used for self-healing loops.
- **Lines 84–85**: Edge partitioning:
  - `forward_edges`: Edges where `is_feedback is False`.
  - `feedback_edges`: Edges where `is_feedback is True`.
  - **Key architectural principle**: Feedback edges represent intentional iterative cycles (e.g. Reviewer $\rightarrow$ Writer). If included in topological sort, Kahn's algorithm would immediately flag them as an illegal cycle. Partitioning them allows forward validation while preserving loops.
- **Lines 87–93**: Adjacency list and in-degree calculation:
  - For every forward edge $u \rightarrow v$, increments `in_degree[v] += 1`.
- **Lines 95–114**: **Kahn's Topological Sort**:
  1. `queue = deque(nid for nid in node_ids if in_degree[nid] == 0)`: Seeds the queue with root nodes (Layer 0).
  2. In each iteration, `layer_size = len(queue)` captures all currently ready nodes.
  3. Pops each node in the layer, decrements its successors' in-degrees.
  4. If a successor's in-degree drops to 0, appends it to the queue for the next layer.
  5. Appends `current_layer` to `layers`.
- **Lines 115–122**: Cycle Detection:
  - If `processed != len(node_ids)`, nodes with `in_degree > 0` remain unvisited. This proves an accidental cyclical dependency exists in forward edges. Raises `CycleDetectedError` with the exact list of offending node IDs.

### 2.3 Why We Built This Instead of Alternatives
- **Why Kahn's algorithm instead of Tarjan's or Kosaraju's SCC?**  
  Tarjan's algorithm finds strongly connected components, but does not naturally produce **breadth-wise parallel execution layers**. Kahn's algorithm produces discrete layers: Layer 0, Layer 1, Layer 2. All nodes in Layer 1 can run simultaneously via `asyncio.gather()`, maximizing execution parallelism.

---

## 3. `src/agentflow/core/executor/mapping.py`

### 3.1 Complete Source Code
```python
"""
Data mapping resolver — evaluates edge data_map expressions and branch conditions.
"""
from __future__ import annotations

import re
from typing import Any

from agentflow.core.executor.context import RunContext

# Matches {{node_id.output.field}} or {{node_id.output.field.nested.path}}
_TEMPLATE_RE = re.compile(r"\{\{([\w.]+)\}\}")


def resolve_value(expr: str, context: RunContext) -> Any:
    """Resolve a template expression against the run context."""
    matches = _TEMPLATE_RE.findall(expr)

    if not matches:
        return expr

    if len(matches) == 1 and expr.strip() == f"{{{{{matches[0]}}}}}":
        return _resolve_reference(matches[0], context)

    def replacer(m: re.Match[str]) -> str:
        val = _resolve_reference(m.group(1), context)
        return str(val) if val is not None else ""

    return _TEMPLATE_RE.sub(replacer, expr)


def _resolve_reference(path: str, context: RunContext) -> Any:
    """Resolve a dot-separated path like 'node_id.output.field'."""
    parts = path.split(".")

    if parts[0] == "shared":
        obj: Any = context.run.shared_context
        for part in parts[1:]:
            if isinstance(obj, dict):
                obj = obj.get(part)
            else:
                return None
        return obj

    if len(parts) < 2:
        return None

    node_id = parts[0]
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
    """Resolve all template expressions in an edge's data_map."""
    return {key: resolve_value(tmpl, context) for key, tmpl in data_map.items()}


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


SAFE_BUILTINS: dict[str, Any] = {
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
    "True": True,
    "False": False,
    "None": None,
}


def evaluate_condition(condition: str | None, output: dict[str, Any]) -> bool:
    """
    Evaluate an edge condition against a node's output.

    Supported:
      - "output.score >= 7"
      - "score >= 7"
      - "output.passed == True"
      - "not passed"
      - "len(findings) > 0"
    """
    if condition is None:
        return True

    wrapped = OutputWrapper(output or {})
    safe_globals: dict[str, Any] = {
        "__builtins__": SAFE_BUILTINS,
        "output": wrapped,
    }
    for k, v in wrapped.items():
        if isinstance(k, str) and k.isidentifier():
            safe_globals[k] = v

    try:
        result = eval(condition, safe_globals)
        return bool(result)
    except Exception:
        return False
```

### 3.2 Line-by-Line Breakdown & Explanation
- **Lines 19–47**: `_TEMPLATE_RE` and `resolve_value`:
  - Matches double-curly templates: `{{node_id.output.field}}`.
  - If the entire expression is a single template (`{{...}}`), preserves native data types (lists, ints, dicts, booleans) without stringifying them.
  - If embedded in a string (`"Bearer {{auth.output.token}}"`), substitutes string representations via regex replacer.
- **Lines 49–85**: `_resolve_reference()`: Splits dot path (`research.output.findings.0`). Resolves against `context.shared_context` or `context.get_node_output()`. Traverses nested dictionaries safely, returning `None` if keys are missing.
- **Lines 100–120**: `OutputWrapper(dict)`: Subclasses `dict` to intercept `__getattr__`.
  - When evaluating expressions like `output.score >= 7`, Python invokes `__getattr__('score')`.
  - If the value is a nested dictionary, wraps it recursively in another `OutputWrapper`, allowing infinite dot-navigation: `output.lead.company.name`.
  - If a key doesn't exist, returns `None` instead of throwing `KeyError`.
- **Lines 122–138**: `SAFE_BUILTINS`: Strict whitelist of safe functions (`len`, `abs`, `round`, `min`, `max`, `int`, `float`, `str`, `bool`). Crucially excludes `__import__`, `open`, `eval`, `exec`, and file-system primitives.
- **Lines 140–172**: `evaluate_condition()`:
  - If `condition is None`: Evaluates unconditionally to `True`.
  - Unpacks output dictionary keys directly into scope: allows both `output.score >= 7` and `score >= 7`.
  - Executes expression inside restricted namespace: `eval(condition, safe_globals)`.
  - Catches any syntax or evaluation errors safely, returning `False` without crashing the engine.

### 3.3 Why We Built This Instead of Alternatives
- **Why `OutputWrapper` + restricted builtins instead of Jinja2 or raw `eval()`?**  
  Raw `eval()` allows Remote Code Execution (`__import__('os').system('rm -rf /')`). Jinja2 templates (`"{{ score >= 7 }}"`) evaluate to strings (`"True"`/`"False"`), which makes boolean expressions like `not passed` or nested comparison clumsy. `OutputWrapper` provides clean Python expression syntax with sandbox safety.

---

## 4. `src/agentflow/core/executor/node_runner.py`

### 4.1 Complete Source Code
```python
"""
NodeRunner — executes a single node with retry, timeout, and output validation.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from agentflow.core.agents.base import BaseAgent
from agentflow.core.agents.registry import agent_registry
from agentflow.core.executor.context import RunContext
from agentflow.core.schemas.workflow import (
    AgentMessage,
    MessageMetadata,
    NodeDef,
    NodeRunRecord,
    NodeRunStatus,
)

log = structlog.get_logger(__name__)


class NodeExecutionError(Exception):
    """Raised when a node fails all retry attempts."""

    def __init__(self, node_id: str, message: str, attempts: int) -> None:
        super().__init__(message)
        self.node_id = node_id
        self.attempts = attempts


async def run_node(
    node: NodeDef,
    input_data: dict[str, Any],
    context: RunContext,
    tools: list[Any] | None = None,
    iteration: int = 1,
) -> AgentMessage:
    """Execute a single workflow node with retry and timeout logic."""
    if tools is None:
        tools = _resolve_node_tools(node)

    policy = node.config.retry_policy
    last_error: str = ""
    validation_feedback: str | None = None

    for attempt in range(1, policy.max_attempts + 1):
        node_run = NodeRunRecord(
            run_id=context.run.id,
            node_id=node.id,
            agent_type=node.type,
            attempt=attempt,
            iteration=iteration,
            input=input_data,
        )
        context.start_node_run(node_run)
        context.increment_step()

        try:
            agent: BaseAgent = agent_registry.get(node.type)
            start = time.perf_counter()
            context.current_node_id = node.id

            effective_input = dict(input_data)
            if validation_feedback:
                effective_input["_validation_feedback"] = validation_feedback

            message = await asyncio.wait_for(
                agent.run(
                    input_data=effective_input,
                    config=node.config,
                    context=context,
                    tools=tools,
                ),
                timeout=node.config.timeout_seconds,
            )

            elapsed_ms = int((time.perf_counter() - start) * 1000)
            message.metadata.latency_ms = elapsed_ms

            context.finish_node_run(node_run, message)
            context.check_cost_limit()
            return message

        except TimeoutError:
            last_error = f"Node timed out after {node.config.timeout_seconds}s"
            _fail_node_run(node_run, context, last_error)
            log.warning(
                "node_timeout",
                node_id=node.id,
                attempt=attempt,
                timeout_seconds=node.config.timeout_seconds,
            )

        except _ValidationError as e:
            last_error = str(e)
            validation_feedback = last_error
            _fail_node_run(node_run, context, last_error, validation_errors=[last_error])
            log.warning(
                "node_validation_error",
                node_id=node.id,
                attempt=attempt,
                error=last_error,
            )
            if not policy.retry_on_validation_error:
                break

        except Exception as e:
            last_error = str(e)
            _fail_node_run(node_run, context, last_error)
            log.exception(
                "node_error",
                node_id=node.id,
                attempt=attempt,
                error=last_error,
            )

        # Backoff before next attempt
        if attempt < policy.max_attempts:
            backoff = policy.backoff_seconds * (policy.backoff_multiplier ** (attempt - 1))
            log.info("node_retry_backoff", node_id=node.id, attempt=attempt, backoff_s=backoff)
            await asyncio.sleep(backoff)

    raise NodeExecutionError(
        node_id=node.id,
        message=f"Node '{node.id}' ({node.type.value}) failed after "
                f"{policy.max_attempts} attempt(s). Last error: {last_error}",
        attempts=policy.max_attempts,
    )


def _resolve_node_tools(node: NodeDef) -> list[Any]:
    if not node.config.tools:
        return []

    try:
        from agentflow.core.tools.registry import tool_registry
    except ImportError:
        log.warning("tool_registry_unavailable", node_id=node.id)
        return []

    resolved = []
    for tool_name in node.config.tools:
        if tool_registry.is_registered(tool_name):
            resolved.append(tool_registry.get(tool_name))
        else:
            log.warning(
                "tool_not_registered",
                node_id=node.id,
                tool_name=tool_name,
                msg=f"Tool '{tool_name}' not found in registry; skipping",
            )

    if node.config.credential_ids:
        _inject_node_credentials(node.id, node.config.credential_ids)

    return resolved


def _inject_node_credentials(
    node_id: str,
    credential_ids: dict[str, str],
) -> None:
    try:
        from agentflow.core.tools.credentials import credential_store
        for tool_name, cred_id in credential_ids.items():
            if not credential_store.has(cred_id):
                log.warning(
                    "credential_not_found",
                    node_id=node_id,
                    tool_name=tool_name,
                    cred_id=cred_id,
                )
    except ImportError:
        pass


def _fail_node_run(
    node_run: NodeRunRecord,
    context: RunContext,
    error: str,
    validation_errors: list[str] | None = None,
) -> None:
    failed_message = AgentMessage(
        run_id=context.run.id,
        node_id=node_run.node_id,
        status=NodeRunStatus.FAILED,
        errors=[error],
        metadata=MessageMetadata(),
    )
    if validation_errors:
        node_run.validation_errors = validation_errors
    context.finish_node_run(node_run, failed_message)


class _ValidationError(Exception):
    """Internal exception for output schema validation failures."""
```

### 4.2 Line-by-Line Breakdown & Explanation
- **Lines 50–57**: `class NodeExecutionError(Exception)`: Captures the node ID and exhausted attempts count when retries fail.
- **Lines 59–83**: `run_node()` signature and documentation. Accepts `node`, `input_data`, `context`, `tools`, and `iteration`.
- **Lines 84–87**: If `tools` is not passed, resolves tools dynamically from `ToolRegistry` using the node's declared `config.tools`.
- **Lines 92–103**: Retry loop (`for attempt in range(1, policy.max_attempts + 1)`):
  - Instantiates `NodeRunRecord` for this attempt.
  - Registers start in `context.start_node_run(node_run)` and increments step count.
- **Lines 105–133**: Execution attempt:
  - Resolves agent instance via `agent_registry.get(node.type)`.
  - Injects `_validation_feedback` into `effective_input` if a previous attempt failed schema validation.
  - Enforces per-node timeout: `asyncio.wait_for(agent.run(...), timeout=node.config.timeout_seconds)`.
  - Computes microsecond duration: `int((time.perf_counter() - start) * 1000)`.
  - Finalizes node run record and checks cost limit. Returns `AgentMessage` on success.
- **Lines 134–166**: Exception handling:
  - `TimeoutError`: Handles node-level timeouts without crashing other parallel nodes.
  - `_ValidationError`: Catches schema failures and prepares feedback for the next attempt.
  - `Exception`: Catches unhandled runtime or network errors.
- **Lines 167–172**: Exponential backoff delay: `backoff_seconds * (backoff_multiplier ** (attempt - 1))`.
- **Lines 173–179**: If all retries fail, raises `NodeExecutionError`.
- **Lines 181–223**: `_resolve_node_tools()`: Resolves tool names into tool instances. Injects credentials from `CredentialStore`.
- **Lines 247–264**: `_fail_node_run()`: Updates `NodeRunRecord` status to `FAILED`.

### 4.3 Why We Built This Instead of Alternatives
- **Why wrap execution with `asyncio.wait_for()` per node?**  
  If a single LLM API hangs (e.g. cloud outage), without per-node timeouts the entire workflow would hang indefinitely. Per-node timeouts isolate hangs to the specific node and trigger its retry policy or error recovery path.

---

## 5. `src/agentflow/core/executor/runner.py`

### 5.1 Complete Source Code
```python
"""
WorkflowRunner — orchestrates the execution of an entire workflow.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from agentflow.core.executor.context import (
    CostLimitExceeded,
    RunContext,
    StepLimitExceeded,
)
from agentflow.core.executor.graph import build_execution_graph
from agentflow.core.executor.mapping import evaluate_condition, resolve_data_map
from agentflow.core.executor.node_runner import NodeExecutionError, run_node
from agentflow.core.schemas.workflow import (
    AgentMessage,
    EdgeDef,
    JoinPolicy,
    RunRecord,
    RunStatus,
    WorkflowDef,
)

log = structlog.get_logger(__name__)

PersistCallback = Callable[[AgentMessage], Awaitable[None]]


async def _noop_persist(message: AgentMessage) -> None:
    """Default no-op persistence callback used in Phase 1."""


async def run_workflow(
    workflow: WorkflowDef,
    trigger_data: dict[str, Any] | None = None,
    shared_context: dict[str, Any] | None = None,
    on_node_complete: PersistCallback = _noop_persist,
) -> RunRecord:
    """Execute a workflow from start to finish."""
    run = RunRecord(
        workflow_id=workflow.id,
        workflow_version=workflow.version,
        trigger_data=trigger_data or {},
        shared_context=shared_context or {},
        started_at=time.time(),
        status=RunStatus.RUNNING,
    )
    context = RunContext(run=run, workflow=workflow)
    graph = build_execution_graph(workflow)

    log.info(
        "run_started",
        run_id=str(run.id),
        workflow_id=str(workflow.id),
        workflow_name=workflow.name,
        node_count=len(workflow.nodes),
    )

    _seed_trigger_outputs(workflow, trigger_data or {}, context)

    def forward_predecessors(nid: str) -> list[str]:
        return [
            e.source for e in workflow.edges
            if e.target == nid and not getattr(e, "is_feedback", False)
        ]

    pending_predecessors: dict[str, int] = {}
    for node_id in graph.node_ids:
        pending_predecessors[node_id] = len(forward_predecessors(node_id))

    completed: set[str] = set()
    skipped: set[str] = set()
    satisfied_edges: set[str] = set()
    dead_edges: set[str] = set()

    for node in workflow.nodes:
        if node.type.value.startswith("trigger_"):
            completed.add(node.id)
            for out_edge in workflow.successors(node.id):
                if not getattr(out_edge, "is_feedback", False):
                    satisfied_edges.add(out_edge.id)

    ready: set[str] = set()
    for node_id in graph.node_ids:
        if node_id in completed:
            continue
        incoming_forward = [
            e for e in workflow.edges
            if e.target == node_id and not getattr(e, "is_feedback", False)
        ]
        if all(e.id in satisfied_edges for e in incoming_forward):
            ready.add(node_id)

    node_iterations: dict[str, int] = defaultdict(int)

    try:
        while ready:
            ready_nodes = [workflow.get_node(nid) for nid in ready]
            ready_nodes = [n for n in ready_nodes if n is not None]
            ready.clear()

            results = await asyncio.gather(
                *[
                    run_node(
                        node=node,
                        input_data=_build_node_input(node.id, workflow, context),
                        context=context,
                        iteration=node_iterations[node.id] + 1,
                    )
                    for node in ready_nodes
                ],
                return_exceptions=True,
            )

            for node in ready_nodes:
                node_iterations[node.id] += 1

            for node, result in zip(ready_nodes, results):
                if isinstance(result, NodeExecutionError):
                    error_edges = [
                        e for e in workflow.successors(node.id)
                        if getattr(e, "is_error_handler", False)
                    ]
                    if error_edges:
                        log.warning(
                            "workflow_node_failed_routing_to_handler",
                            run_id=str(run.id),
                            node_id=node.id,
                            error=str(result),
                            handler_nodes=[e.target for e in error_edges],
                        )
                        completed.add(node.id)
                        context.record_node_output(node.id, {
                            "error": str(result),
                            "status": "failed",
                            "node_id": node.id,
                        })
                        for ee in error_edges:
                            if ee.target not in completed and ee.target not in skipped:
                                ready.add(ee.target)
                        continue

                    context.run.status = RunStatus.FAILED
                    context.run.error = str(result)
                    log.error(
                        "workflow_node_failed",
                        run_id=str(run.id),
                        node_id=node.id,
                        error=str(result),
                    )
                    context.finalize_run(RunStatus.FAILED, str(result))
                    return run

                if isinstance(result, Exception):
                    raise result

                message: AgentMessage = result
                await on_node_complete(message)
                completed.add(node.id)

                outgoing = workflow.successors(node.id)
                feedback_edges = [e for e in outgoing if getattr(e, "is_feedback", False)]
                forward_edges = [
                    e for e in outgoing
                    if not getattr(e, "is_feedback", False)
                    and not getattr(e, "is_error_handler", False)
                ]

                node_output = context.get_node_output(node.id) or {}

                # 1. Process feedback / loop edges
                loop_triggered = False
                for f_edge in feedback_edges:
                    if evaluate_condition(f_edge.condition, node_output):
                        target_node = workflow.get_node(f_edge.target)
                        max_iters = (
                            f_edge.max_iterations
                            or (target_node.config.max_loop_iterations if target_node else 3)
                        )
                        target_iters = node_iterations.get(f_edge.target, 0)
                        if target_iters < max_iters:
                            loop_triggered = True
                            log.info(
                                "feedback_loop_triggered",
                                run_id=str(run.id),
                                source=node.id,
                                target=f_edge.target,
                                iteration=target_iters + 1,
                                max_iterations=max_iters,
                            )
                            cycle_nodes = _find_cycle_nodes(node.id, f_edge.target, workflow)
                            for c_node in cycle_nodes:
                                completed.discard(c_node)
                                skipped.discard(c_node)
                                for e in workflow.edges:
                                    if e.source == c_node or e.target == c_node:
                                        satisfied_edges.discard(e.id)
                                        dead_edges.discard(e.id)
                            ready.add(f_edge.target)
                            break
                        log.warning(
                            "feedback_loop_limit_reached",
                            run_id=str(run.id),
                            source=node.id,
                            target=f_edge.target,
                            current_iterations=target_iters,
                            max_iterations=max_iters,
                        )

                if loop_triggered:
                    continue

                # 2. Process forward edges with multi-path branching, default fallback & dead-path elimination
                cond_edges = [e for e in forward_edges if not getattr(e, "is_default", False)]
                default_edges = [e for e in forward_edges if getattr(e, "is_default", False)]

                matched_any = False
                for edge in cond_edges:
                    if evaluate_condition(edge.condition, node_output):
                        matched_any = True
                        _handle_edge_resolution(
                            edge=edge,
                            is_satisfied=True,
                            workflow=workflow,
                            completed=completed,
                            skipped=skipped,
                            satisfied_edges=satisfied_edges,
                            dead_edges=dead_edges,
                            ready=ready,
                            context=context,
                        )
                    else:
                        _handle_edge_resolution(
                            edge=edge,
                            is_satisfied=False,
                            workflow=workflow,
                            completed=completed,
                            skipped=skipped,
                            satisfied_edges=satisfied_edges,
                            dead_edges=dead_edges,
                            ready=ready,
                            context=context,
                        )

                if not matched_any and default_edges:
                    for edge in default_edges:
                        _handle_edge_resolution(
                            edge=edge,
                            is_satisfied=True,
                            workflow=workflow,
                            completed=completed,
                            skipped=skipped,
                            satisfied_edges=satisfied_edges,
                            dead_edges=dead_edges,
                            ready=ready,
                            context=context,
                        )
                elif matched_any and default_edges:
                    for edge in default_edges:
                        _handle_edge_resolution(
                            edge=edge,
                            is_satisfied=False,
                            workflow=workflow,
                            completed=completed,
                            skipped=skipped,
                            satisfied_edges=satisfied_edges,
                            dead_edges=dead_edges,
                            ready=ready,
                            context=context,
                        )

    except (CostLimitExceeded, StepLimitExceeded) as e:
        context.finalize_run(RunStatus.FAILED, str(e))
        return run
    except Exception as e:
        log.exception("run_unexpected_error", run_id=str(run.id), error=str(e))
        context.finalize_run(RunStatus.FAILED, str(e))
        return run

    context.finalize_run(RunStatus.COMPLETED)
    return run


def _seed_trigger_outputs(
    workflow: WorkflowDef,
    trigger_data: dict[str, Any],
    context: RunContext,
) -> None:
    for node in workflow.nodes:
        if node.type.value.startswith("trigger_"):
            context.record_node_output(node.id, trigger_data)


def _build_node_input(
    node_id: str,
    workflow: WorkflowDef,
    context: RunContext,
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for edge in workflow.edges:
        if edge.target != node_id:
            continue
        if not edge.data_map:
            source_output = context.get_node_output(edge.source) or {}
            merged.update(source_output)
        else:
            resolved = resolve_data_map(edge.data_map, context)
            merged.update(resolved)
    return merged


def _find_cycle_nodes(
    source_id: str,
    target_id: str,
    workflow: WorkflowDef,
) -> set[str]:
    """Find cycle nodes using reachability intersection."""
    forward_adj: dict[str, list[str]] = defaultdict(list)
    backward_adj: dict[str, list[str]] = defaultdict(list)
    for edge in workflow.edges:
        if not getattr(edge, "is_feedback", False):
            forward_adj[edge.source].append(edge.target)
            backward_adj[edge.target].append(edge.source)

    reachable_from_target: set[str] = set()
    queue = [target_id]
    while queue:
        curr = queue.pop(0)
        if curr not in reachable_from_target:
            reachable_from_target.add(curr)
            for nxt in forward_adj[curr]:
                if nxt not in reachable_from_target:
                    queue.append(nxt)

    can_reach_source: set[str] = set()
    queue = [source_id]
    while queue:
        curr = queue.pop(0)
        if curr not in can_reach_source:
            can_reach_source.add(curr)
            for prev in backward_adj[curr]:
                if prev not in can_reach_source:
                    queue.append(prev)

    cycle_nodes = reachable_from_target & can_reach_source
    return cycle_nodes or {source_id, target_id}


def _handle_edge_resolution(
    edge: EdgeDef,
    is_satisfied: bool,
    workflow: WorkflowDef,
    completed: set[str],
    skipped: set[str],
    satisfied_edges: set[str],
    dead_edges: set[str],
    ready: set[str],
    context: RunContext,
) -> None:
    if is_satisfied:
        satisfied_edges.add(edge.id)
    else:
        dead_edges.add(edge.id)

    node_id = edge.target
    if node_id in completed or node_id in skipped:
        return

    node = workflow.get_node(node_id)
    if not node:
        return

    incoming_forward = [
        e for e in workflow.edges
        if e.target == node_id
        and not getattr(e, "is_feedback", False)
        and not getattr(e, "is_error_handler", False)
    ]
    if not incoming_forward:
        return

    dead_count = sum(1 for e in incoming_forward if e.id in dead_edges or e.source in skipped)
    satisfied_count = sum(1 for e in incoming_forward if e.id in satisfied_edges)
    total_count = len(incoming_forward)

    # Dead-Path Elimination
    if dead_count == total_count:
        skipped.add(node_id)
        log.info("node_skipped", run_id=str(context.run.id), node_id=node_id)
        for out_edge in workflow.successors(node_id):
            if not getattr(out_edge, "is_feedback", False):
                _handle_edge_resolution(
                    edge=out_edge,
                    is_satisfied=False,
                    workflow=workflow,
                    completed=completed,
                    skipped=skipped,
                    satisfied_edges=satisfied_edges,
                    dead_edges=dead_edges,
                    ready=ready,
                    context=context,
                )
        return

    # JoinPolicy evaluation
    join_policy = getattr(node.config, "join_policy", JoinPolicy.WAIT_ALL)
    if join_policy == JoinPolicy.WAIT_ANY:
        if satisfied_count >= 1:
            ready.add(node_id)
    else:  # WAIT_ALL
        if satisfied_count + dead_count == total_count and satisfied_count >= 1:
            ready.add(node_id)
```

### 5.2 Line-by-Line Breakdown & Explanation
- **Lines 61–88**: `run_workflow()` initialization: Sets up `RunRecord`, `RunContext`, builds `ExecutionGraph`, logs run start.
- **Lines 101**: `_seed_trigger_outputs()`: Pre-seeds trigger node outputs so downstream agents can immediately reference trigger parameters.
- **Lines 117–128**: Marks trigger nodes as completed and satisfies their outgoing edges.
- **Lines 129–139**: Seeds the `ready` set with all nodes whose incoming forward edges are satisfied (or that have no incoming edges).
- **Lines 144–161**: Dynamic execution loop:
  - Takes all nodes in `ready` and clears the set.
  - Concurrently executes them via `asyncio.gather(*[run_node(...)], return_exceptions=True)`.
  - Increments each node's iteration counter.
- **Lines 167–202**: Error recovery routing:
  - If a node throws `NodeExecutionError`, checks for outgoing edges with `is_error_handler=True`.
  - If error edges exist, records the failure output and routes execution to the error handler target, continuing workflow execution.
  - If no handler exists, marks run as `FAILED` and terminates.
- **Lines 220–260**: Self-Healing Feedback Loop Trigger:
  - If an outgoing edge has `is_feedback=True` and its condition is satisfied:
    - Verifies loop iteration count $< \text{max\_iterations}$.
    - Calls `_find_cycle_nodes()` to determine the loop sub-graph.
    - Discards `completed`, `skipped`, `satisfied_edges`, and `dead_edges` **only** for cycle nodes.
    - Re-enqueues `target_id` into the `ready` set.
- **Lines 262–332**: Forward Edge Resolution & Default Edges:
  - Evaluates all conditional forward edges.
  - If none match and default edges (`is_default=True`) exist, takes the default edges.
  - Passes each edge to `_handle_edge_resolution()`.
- **Lines 384–422**: `_find_cycle_nodes()`:
  - Performs BFS forward from `target_id` $\rightarrow$ `reachable_from_target`.
  - Performs BFS backward from `source_id` $\rightarrow$ `can_reach_source`.
  - Computes set intersection: `reachable_from_target & can_reach_source`.
  - Isolates the exact nodes in the loop cycle.
- **Lines 424–493**: `_handle_edge_resolution()`:
  - Tracks `satisfied_edges` and `dead_edges`.
  - If all incoming edges are dead (`dead_count == total_count`), marks node as `skipped` and recursively marks outbound edges as dead (cascading Dead-Path Elimination).
  - If `join_policy == WAIT_ALL`, checks if `satisfied_count + dead_count == total_count` and `satisfied_count >= 1`. If satisfied, adds node to `ready`.
  - If `join_policy == WAIT_ANY`, unblocks as soon as `satisfied_count >= 1`.

### 5.3 Why We Built This Instead of Alternatives
- **Why explicit Dead-Path Elimination (DPE) with `satisfied_edges` and `dead_edges`?**  
  In standard DAG engines (like basic Airflow), checking if predecessor nodes succeeded fails when a router branches to multiple paths (the router succeeded, but one edge died!). Tracking edge states directly is the only mathematically sound way to handle diamond joins and multi-path branches without deadlocking.
