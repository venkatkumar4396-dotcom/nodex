# AgentFlow: Master Technical Specification & Code Architecture (Phases 1 to 3)

> **Document Version**: 1.0.0  
> **Target Platform**: NodeX / AgentFlow Platform  
> **Status**: Phases 1, 2, and 3 Complete & Fully Verified (119/119 Tests Passing, 0 Lint Warnings)  
> **Repository Scope**: `c:\work\ai store\no name project\agentflow\backend`

---

## Table of Contents
1. [Executive System Architecture & Philosophy](#1-executive-system-architecture--philosophy)
2. [Architectural Visualizations & State Machines](#2-architectural-visualizations--state-machines)
3. [Phase 1: Foundation & Deterministic Graph Engine](#3-phase-1-foundation--deterministic-graph-engine)
   - 3.1 [Application Config & Logging (`config.py`, `logging_config.py`)](#31-application-config--logging)
   - 3.2 [Pydantic Contract Schemas (`schemas/workflow.py`, `schemas/tool.py`)](#32-pydantic-contract-schemas)
   - 3.3 [Topological Graph Engine (`executor/graph.py`)](#33-topological-graph-engine)
   - 3.4 [Execution Context & Guardrails (`executor/context.py`)](#34-execution-context--guardrails)
   - 3.5 [Node Execution Runtime (`executor/node_runner.py`)](#35-node-execution-runtime)
   - 3.6 [Workflow Runner Baseline (`executor/runner.py`)](#36-workflow-runner-baseline)
   - 3.7 [Base Agent & Registry (`agents/base.py`, `agents/registry.py`)](#37-base-agent--registry)
   - 3.8 [Phase 1 Comparative Rationale: Why This vs Alternatives](#38-phase-1-comparative-rationale)
4. [Phase 2: Production Tools, Credentials & ReAct Reasoning Loop](#4-phase-2-production-tools-credentials--react-reasoning-loop)
   - 4.1 [Cryptographic Credential Store (`tools/credentials.py`)](#41-cryptographic-credential-store)
   - 4.2 [Tool Abstraction & Registry (`tools/base.py`, `tools/registry.py`)](#42-tool-abstraction--registry)
   - 4.3 [ReAct Autonomous Tool Loop (`tools/tool_loop.py`)](#43-react-autonomous-tool-loop)
   - 4.4 [Production Built-in Tools (`web_search.py`, `http_tool.py`, `email_tool.py`)](#44-production-built-in-tools)
   - 4.5 [Unified LLM Gateway & Self-Healing Schemas (`llm/client.py`, `llm/structured.py`)](#45-unified-llm-gateway--self-healing-schemas)
   - 4.6 [Phase 2 Comparative Rationale: Why This vs Alternatives](#46-phase-2-comparative-rationale)
5. [Phase 3: Advanced Control Flow & Self-Healing Feedback Loops](#5-phase-3-advanced-control-flow--self-healing-feedback-loops)
   - 5.1 [Dynamic Condition Evaluator & `OutputWrapper` (`executor/mapping.py`)](#51-dynamic-condition-evaluator--outputwrapper)
   - 5.2 [Default Fallback Edges (`is_default`)](#52-default-fallback-edges)
   - 5.3 [Dead-Path Elimination (DPE) & Join Policies (`JoinPolicy.WAIT_ALL` / `WAIT_ANY`)](#53-dead-path-elimination-dpe--join-policies)
   - 5.4 [Self-Healing Feedback Loops (`is_feedback`, Reachability Intersection Cycle Detection)](#54-self-healing-feedback-loops)
   - 5.5 [Iterative Agent Refinement (`WriterAgent` ↔ `ReviewerAgent`)](#55-iterative-agent-refinement)
   - 5.6 [Error Recovery Routing (`is_error_handler`)](#56-error-recovery-routing)
   - 5.7 [Phase 3 Comparative Rationale: Why This vs Alternatives](#57-phase-3-comparative-rationale)
6. [Comprehensive File-by-File & Function-by-Function Reference](#6-comprehensive-file-by-file--function-by-function-reference)
7. [Verification, Quality Gates & Live Demo Simulation](#7-verification-quality-gates--live-demo-simulation)

---

## 1. Executive System Architecture & Philosophy

AgentFlow is designed around a singular, foundational premise: **an agentic workflow platform where every node is an autonomous reasoning entity rather than a static procedural script.**

```
Traditional Workflow (n8n / Zapier):
  [Webhook] ---> [HTTP Request] ---> [Code (JS/Python)] ---> [Database Save]
                     (Fixed logic, fragile to schema variations)

AgentFlow Platform:
  [Trigger] ---> [Research Agent] ---> [Router Agent] ---> [Writer Agent] <---> [Reviewer Agent]
                   (WebSearch Tool)       (Evaluates ICP)    (Drafts Email)      (Quality Gate)
                                                                    \                 /
                                                                     (Self-Healing Loop)
```

### Core Architecture Invariants
1. **Schema-First Contract**: All inputs, outputs, messages, and configurations are strongly typed Pydantic models. Python runtime validation and OpenAPI TypeScript frontend models derive from this single source of truth.
2. **Deterministic Topological Execution**: Non-dependent agents execute in parallel batches using Kahn's algorithm layers (`asyncio.gather()`).
3. **Dead-Path Elimination (DPE)**: Multi-branch decision paths eliminate dead downstream paths without deadlocking converging join nodes.
4. **Self-Healing Feedback Loops**: Cyclical back-edges (`is_feedback=True`) allow editorial agents to critique and refine drafts dynamically without infinite loops or invalidating upstream graph history.
5. **Zero-Trust Credential Isolation**: API keys and secrets are encrypted at rest with Fernet symmetric encryption and injected ephemerally at runtime.

---

## 2. Architectural Visualizations & State Machines

### 2.1 Complete End-to-End Execution Flow

```mermaid
flowchart TD
    subgraph UI_REST["Client & Persistence Layer (Phase 4 & 5)"]
        Canvas["React Flow Canvas"] --> REST["FastAPI API"]
        REST --> DB[(PostgreSQL)]
        REST --> ArqQueue[(Redis / Arq Worker)]
    end

    subgraph CoreEngine["AgentFlow Engine Core (Phases 1 - 3)"]
        WDef["WorkflowDef (Pydantic Spec)"] --> GraphBuilder["build_execution_graph()"]
        GraphBuilder -->|"Forward DAG Layers"| Runner["WorkflowRunner (Dynamic Frontier)"]

        subgraph DynamicExecutionLoop["Dynamic Step Execution"]
            Runner -->|"1. Resolve Ready Nodes"| NodeRunner["run_node()"]
            NodeRunner -->|"2. Resolve Agent"| Agent["BaseAgent Plugin"]
            NodeRunner -->|"3. Resolve Tools & Inject Decrypted Keys"| ToolRegistry["ToolRegistry + CredentialStore"]
            ToolRegistry -->|"4. Execute Tool Loop"| ToolLoop["ToolLoop (ReAct)"]
            ToolLoop -->|"5. Model Call"| LiteLLM["LiteLLM Client"]
            LiteLLM -->|"6. Structured Output Parse"| Parser["StructuredOutputParser"]
        end

        Parser -->|"7. Emit AgentMessage"| Context["RunContext"]
        Context -->|"8. Edge Evaluation & DPE"| ControlFlow{"Control Flow Engine"}

        ControlFlow -->|"Condition True"| SatisfiedEdge["satisfied_edges.add(edge.id)"]
        ControlFlow -->|"Condition False"| DeadEdge["dead_edges.add(edge.id)"]
        ControlFlow -->|"All False -> is_default"| DefaultEdge["satisfied_edges.add(default_edge.id)"]
        ControlFlow -->|"is_feedback (Loop)"| CycleReset["_find_cycle_nodes() Reset"]
        ControlFlow -->|"Node Failed -> is_error_handler"| ErrorPath["Route to Error Handler"]

        SatisfiedEdge --> Runner
        DeadEdge --> DPE["Cascade Dead Path Elimination"]
        DPE --> Runner
        CycleReset --> Runner
    end
```

### 2.2 Dead-Path Elimination (DPE) State Machine

In diamond branching, when an upstream condition evaluates to `False`, the skipped path must not cause downstream join nodes to wait forever.

```mermaid
stateDiagram-v2
    [*] --> EvaluatingEdges
    EvaluatingEdges --> EdgeSatisfied: condition == True
    EvaluatingEdges --> EdgeDead: condition == False
    EvaluatingEdges --> FallbackDefault: All conditional edges False & is_default == True

    EdgeSatisfied --> CheckJoinPolicy
    EdgeDead --> CheckJoinPolicy

    state CheckJoinPolicy {
        [*] --> InspectIncomingEdges
        InspectIncomingEdges --> EvaluateWaitAll: JoinPolicy == WAIT_ALL
        InspectIncomingEdges --> EvaluateWaitAny: JoinPolicy == WAIT_ANY

        EvaluateWaitAll --> NodeReady: All incoming edges resolved AND >= 1 satisfied
        EvaluateWaitAll --> NodeSkipped: ALL incoming edges are dead

        EvaluateWaitAny --> NodeReady: At least 1 incoming edge satisfied
    }

    NodeReady --> [*]: Node Added to ready set
    NodeSkipped --> CascadeDeadEdges: Mark node skipped
    CascadeDeadEdges --> [*]: Mark all outbound edges as dead
```

### 2.3 Self-Healing Feedback Loop Sequence (Writer ↔ Reviewer)

```mermaid
sequenceDiagram
    autonumber
    actor User as Workflow Trigger
    participant Runner as WorkflowRunner
    participant Writer as WriterAgent
    participant Reviewer as ReviewerAgent

    User->>Runner: Start Run (Lead Data)
    Runner->>Writer: Run attempt 1 (iteration 1)
    Writer-->>Runner: Draft 1 (Subject + Body)
    Runner->>Reviewer: Forward Draft 1
    Reviewer-->>Runner: Review: score=6.0, passed=False, feedback="Tighten CTA"
    
    Note over Runner: Feedback edge condition:<br/>not output.passed and score < 8
    Runner->>Runner: Condition TRUE! Trigger Feedback Loop
    Runner->>Runner: _find_cycle_nodes(Reviewer, Writer) -> {Writer, Reviewer}
    Runner->>Runner: Reset Writer & Reviewer state (Iteration 2)
    
    Runner->>Writer: Run attempt 1 (iteration 2) + Reviewer Critique Injected
    Writer-->>Runner: Draft 2 (Incorporates critique)
    Runner->>Reviewer: Forward Draft 2
    Reviewer-->>Runner: Review: score=9.5, passed=True, feedback="Approved"
    
    Note over Runner: Feedback condition FALSE.<br/>Forward condition output.passed is TRUE.
    Runner->>Runner: Satisfy forward edge to EmailAgent
    Runner->>User: Run Completed Successfully
```

---

## 3. Phase 1: Foundation & Deterministic Graph Engine

Phase 1 established the bedrock: type-safe schemas, topological sorting, runtime state, and isolated node execution.

### 3.1 Application Config & Logging
- **`src/agentflow/config.py`**:
  - Implements `Settings(BaseSettings)` using `pydantic-settings`.
  - Reads configuration from `.env` files with strict type coercion.
  - Exposes configuration properties:
    - `environment`: `development` | `staging` | `production`.
    - `default_model`: default LLM (e.g. `gpt-4o-mini`).
    - `default_budget_usd`: global default safety budget (e.g. `$2.00`).
    - `default_step_limit`: maximum execution steps (e.g. `100`).
    - `secret_key`: master key used to derive Fernet symmetric encryption keys.
- **`src/agentflow/logging_config.py`**:
  - Configures `structlog` for structured logging.
  - In development: emits colorized, human-readable console output.
  - In production: emits JSON logs for Datadog, CloudWatch, or OpenTelemetry ingestion.

### 3.2 Pydantic Contract Schemas
- **`src/agentflow/core/schemas/tool.py`**:
  - `ToolParameter`: Models parameter definitions (`name`, `type`, `description`, `required`, `default`, `enum`).
  - `ToolDefinition`: Represents tool signatures and provides `to_openai_schema()`, generating OpenAI-compatible function calling specifications.
- **`src/agentflow/core/schemas/workflow.py`**:
  - `NodeStatus`: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `SKIPPED`.
  - `RunStatus`: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`.
  - `JoinPolicy`: `WAIT_ALL` (default) vs `WAIT_ANY`.
  - `RetryPolicy`: Configurable `max_retries`, `backoff_seconds`, `backoff_multiplier`, and `retry_on_errors`.
  - `NodeConfig`: Complete node parameters (`model`, `temperature`, `system_prompt`, `tools`, `credential_ids`, `timeout_seconds`, `join_policy`, `retry_policy`).
  - `NodeDef`: Node structure including unique `id`, human-readable `name`, `agent_type`, and canvas coordinates `position: dict[str, float]`.
  - `EdgeDef`: Connection structure with `source`, `target`, `condition`, `data_map`, `is_default`, `is_feedback`, and `is_error_handler`.
  - `AgentMessage`: The standard payload passed between agents, carrying `payload`, `metadata`, `token_count`, and `cost_usd`.
  - `NodeRunRecord`: Detailed per-node execution audit record.
  - `WorkflowDef`: Root workflow model with helper methods (`get_node`, `get_incoming_edges`, `get_outgoing_edges`).

### 3.3 Topological Graph Engine
- **`src/agentflow/core/executor/graph.py`**:
  - `ExecutionGraph`: Contains validated `layers: list[list[str]]` and dependency mappings.
  - `build_execution_graph(workflow: WorkflowDef)`:
    1. **Endpoint Validation**: Ensures every edge connects to existing nodes; raises `EdgeEndpointNotFoundError` otherwise.
    2. **Feedback Edge Partitioning**: Filters out edges where `is_feedback=True` so back-edges do not increment forward `in_degree`.
    3. **Kahn's Algorithm**:
       - Calculates in-degrees for all nodes based strictly on forward edges.
       - Discovers Layer 0 (`in_degree == 0`).
       - Iteratively decrements downstream in-degrees to build sequential execution layers.
    4. **Cycle Detection**: If the number of processed nodes does not equal the total number of nodes, it identifies unresolvable forward cycles and raises `CycleDetectedError`.

### 3.4 Execution Context & Guardrails
- **`src/agentflow/core/executor/context.py`**:
  - `RunContext`: Ephemeral execution state container.
  - Thread-safe and asynchronous.
  - Contains:
    - `node_outputs: dict[str, dict[str, Any]]`: Latest payload from each completed node.
    - `node_runs: list[NodeRunRecord]`: Complete chronological history.
    - `total_tokens: int` and `total_cost_usd: float`: Real-time budget tracking.
    - `step_count: int`: Global step counter.
  - Enforces runtime limits:
    - Raises `StepLimitExceeded` if `step_count > max_steps`.
    - Raises `CostLimitExceeded` if `total_cost_usd > cost_limit_usd`.

### 3.5 Node Execution Runtime
- **`src/agentflow/core/executor/node_runner.py`**:
  - `run_node()`: Encapsulates the complete lifecycle of executing a single node:
    1. Extracts incoming inputs from predecessor nodes and applies `resolve_data_map`.
    2. Resolves agent class from `AgentRegistry`.
    3. Resolves tools from `ToolRegistry` and injects decrypted credentials from `CredentialStore`.
    4. Executes with exponential backoff retry loop (`attempt = 1 .. max_retries + 1`).
    5. Measures duration with microsecond precision (`time.perf_counter()`).
    6. Constructs and returns `NodeRunRecord` and `AgentMessage`.

### 3.6 Workflow Runner Baseline
- **`src/agentflow/core/executor/runner.py`**:
  - `run_workflow()`: The top-level execution loop.
  - Maintains `ready: set[str]`, `completed: set[str]`, and `skipped: set[str]`.
  - Dispatches all ready nodes concurrently using `asyncio.gather()`.
  - Invokes optional `persist_callback` after every node completion (the durable hook for Phase 4 database persistence).

### 3.7 Base Agent & Registry
- **`src/agentflow/core/agents/base.py`**:
  - `BaseAgent`: Abstract base class defining `execute(context: AgentContext) -> AgentResult`.
  - `AgentContext`: Provides the executing agent with access to inputs, node config, assigned tools, LLM client, and run logger.
  - `AgentResult`: Standard output envelope (`output: dict[str, Any]`, `token_count: int`, `cost_usd: float`).
- **`src/agentflow/core/agents/registry.py`**:
  - `AgentRegistry`: Singleton registry mapping `agent_type: str` to `type[BaseAgent]`.
  - `register_all_builtin_agents()`: Auto-discovers and registers built-in agents (`trigger_manual`, `research`, `router`, `writer`, `reviewer`, `email`).

### 3.8 Phase 1 Comparative Rationale

| Architecture Choice | Why We Chose It | Why Alternative Was Rejected |
| :--- | :--- | :--- |
| **Pydantic v2 Schemas** | Strict validation, fast C-core serialization, automatic OpenAPI generation for React frontend. | Raw `dict` causes runtime `KeyError` crashes in multi-node graphs; `dataclasses` lack JSON schema validation. |
| **Kahn's Topological Sort** | Naturally produces parallel layers (`list[list[str]]`) for concurrent `asyncio.gather()` dispatch. | Depth-First Search (DFS) provides only sequential ordering and cannot determine parallel execution frontiers. |
| **Custom Dynamic Runner** | Native support for edge-level data mapping, fine-grained node timeouts, and visual canvas alignment. | **LangGraph** enforces a single global state dictionary that breaks independent, heterogeneous agent contracts; **Celery** lacks DAG graph awareness. |

---

## 4. Phase 2: Production Tools, Credentials & ReAct Reasoning Loop

Phase 2 equipped agents with the ability to dynamically call external APIs, search the web, send emails, and reason iteratively using encrypted secrets.

### 4.1 Cryptographic Credential Store
- **`src/agentflow/core/tools/credentials.py`**:
  - Implements `CredentialStore` using **Fernet symmetric encryption** (`AES-128-CBC` with `HMAC-SHA256`).
  - Key derivation: Computes `base64.urlsafe_b64encode(hashlib.sha256(secret_key).digest())`.
  - Methods:
    - `set_credential(credential_id, secret)`: Encrypts plain text secret and stores ciphertext in memory.
    - `get_credential(credential_id)`: Decrypts ciphertext back to plain text.
    - `resolve_for_node(credential_ids)`: Resolves a map of `{tool_name: credential_id}` to decrypted `{tool_name: plain_secret}`.
    - Fallback: If `credential_id` is not registered, automatically checks environment variables (`os.environ`).
  - Security invariant: Decrypted secrets exist in memory only during the active tool call and are never written to disk, logs, or LLM prompts.

### 4.2 Tool Abstraction & Registry
- **`src/agentflow/core/tools/base.py`**:
  - `BaseTool`: Abstract base class with class attributes (`name`, `description`, `parameters`).
  - `to_openai_tool()`: Converts parameters into OpenAI function definition schema.
  - `execute(**kwargs)`: Asynchronous execution method returning `ToolResult(output, error, duration_ms)`.
  - `inject_credentials(credentials)`: Injects decrypted API keys prior to execution.
- **`src/agentflow/core/tools/registry.py`**:
  - `ToolRegistry`: Singleton registry mapping `tool_name: str` to `BaseTool` instances.
  - `register_all_builtin_tools()`: Registers `WebSearchTool`, `HttpTool`, and `EmailSendTool`.

### 4.3 ReAct Autonomous Tool Loop
- **`src/agentflow/core/tools/tool_loop.py`**:
  - Implements the **ReAct (Reason + Act)** pattern for agent execution.
  - `run_tool_loop()` lifecycle:
    1. Compiles system prompt, input messages, and serialized OpenAI tool specifications.
    2. Sends messages to LLM via `LLMClient.acompletion(tools=tools)`.
    3. Checks `response.choices[0].message.tool_calls`:
       - If tool calls exist:
         - Dispatches each tool asynchronously using `tool.execute(**arguments)`.
         - Appends assistant message with `tool_calls` to conversation history.
         - Appends tool observation message (`role="tool"`, `tool_call_id=...`, `content=result.output`).
         - Increments loop iteration counter and repeats.
       - If no tool calls: Loop terminates and returns final response text.
    4. Guards: Enforces `max_iterations` (default: 5) to prevent infinite tool loops.
    5. Aggregates total token usage and financial cost across all intermediate reasoning hops.

### 4.4 Production Built-in Tools
- **`src/agentflow/core/tools/web_search.py`**:
  - `WebSearchTool`: Queries live web information.
  - Primary engine: **Serper.dev REST API** (`https://google.serper.dev/search`).
  - Secondary fallback: **DuckDuckGo HTML search** (free, no API key required).
  - Development mode: If no internet or API key is provided, returns structured synthetic findings in dry-run mode.
- **`src/agentflow/core/tools/http_tool.py`**:
  - `HttpTool`: General-purpose HTTP request client.
  - Built on `httpx.AsyncClient`.
  - Supports methods: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`.
  - Accepts custom headers, query parameters, JSON request bodies, and custom timeouts.
- **`src/agentflow/core/tools/email_tool.py`**:
  - `EmailSendTool`: Sends outbound emails.
  - Production backends:
    - **SendGrid REST API** (via `sendgrid_api_key`).
    - **SMTP client** (with TLS/STARTTLS authentication).
  - Development backend: **Stub dry-run mode** generating deterministic mock message IDs (`msg_...`).

### 4.5 Unified LLM Gateway & Self-Healing Schemas
- **`src/agentflow/core/llm/client.py`**:
  - `LLMClient`: Multi-provider LLM gateway powered by **LiteLLM**.
  - Supports 100+ models (`gpt-4o`, `claude-3-5-sonnet`, `gemini/gemini-1.5-pro`, `ollama/llama3`).
  - Automatic token cost tracking using `litellm.completion_cost()`.
  - Built-in retry logic for rate limits (`RateLimitError`) and server errors (`APIConnectionError`).
- **`src/agentflow/core/llm/structured.py`**:
  - `StructuredOutputParser[T]`: Forces LLM responses into strict Pydantic models.
  - Features:
    - Strips markdown code fences (` ```json ` ... ` ``` `).
    - **Self-Healing Schema Auto-Repair**: If `ValidationError` or `JSONDecodeError` occurs:
      1. Catches the error message and offending JSON string.
      2. Construct a repair prompt: *"Your response violated the schema: {error}. Fix the JSON and respond ONLY with valid JSON conforming to {schema}."*
      3. Calls LLM again to correct its mistake.
      4. Guarantees valid Pydantic instances without failing the pipeline.

### 4.6 Phase 2 Comparative Rationale

| Architecture Choice | Why We Chose It | Why Alternative Was Rejected |
| :--- | :--- | :--- |
| **Fernet Symmetric Encryption** | Zero external dependencies; instant local & self-hosted setup; fast AES-128 encryption. | **HashiCorp Vault / AWS Secrets Manager** adds immense operational overhead and breaks local developer workflows. |
| **Custom ReAct `ToolLoop`** | Full observability into intermediate reasoning steps, token costs, and duration per tool execution. | **OpenAI Assistants API** is a black box, vendor-locked to OpenAI, and cannot run on local models (Ollama) or Claude. |
| **LiteLLM Gateway** | Single API interface for OpenAI, Anthropic, Gemini, Groq, and Ollama; automatic daily cost lookup tables. | Maintaining individual provider SDKs (`openai`, `anthropic`, `google-genai`) creates massive dependency conflicts and code duplication. |

---

## 5. Phase 3: Advanced Control Flow & Self-Healing Feedback Loops

Phase 3 elevated AgentFlow from a simple acyclic graph executor into an enterprise orchestration engine capable of dynamic conditional branching, dead-path elimination, self-healing editorial loops, and fault-tolerant error routing.

### 5.1 Dynamic Condition Evaluator & `OutputWrapper`
**File**: `src/agentflow/core/executor/mapping.py`

#### What was built
```python
class OutputWrapper:
    """Wrapper around dict allowing attribute access: output.score instead of output['score']."""
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getattr__(self, name: str) -> Any:
        if name in self._data:
            val = self._data[name]
            return OutputWrapper(val) if isinstance(val, dict) else val
        raise AttributeError(f"No attribute '{name}' in output")

def evaluate_condition(condition: str, source_output: dict[str, Any]) -> bool:
    """
    Evaluates a string condition expression against source output.
    Supports dot-notation (output.score >= 7) and unpacked variables (score >= 7).
    """
    safe_builtins = {
        "abs": abs, "len": len, "round": round, "min": min, "max": max,
        "int": int, "float": float, "str": str, "bool": bool,
    }
    eval_globals = {"__builtins__": safe_builtins}
    eval_locals = {
        "output": OutputWrapper(source_output),
        **source_output,
    }
    return bool(eval(condition, eval_globals, eval_locals))  # noqa: S307
```

### 5.2 Default Fallback Edges
**File**: `src/agentflow/core/schemas/workflow.py` & `src/agentflow/core/executor/runner.py`

- In `EdgeDef`: Added `is_default: bool = False`.
- In `WorkflowRunner`:
  - When a node finishes, outbound conditional edges are evaluated first.
  - If **none** of the conditional edges evaluate to `True`, the edge marked `is_default=True` is activated.
  - If at least one conditional edge evaluated to `True`, the default fallback edge is marked as **dead**.

### 5.3 Dead-Path Elimination (DPE) & Join Policies
**File**: `src/agentflow/core/executor/runner.py` (`_handle_edge_resolution`)

#### What was built
```python
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
    incoming_forward = [
        e for e in workflow.edges
        if e.target == node_id and not getattr(e, "is_feedback", False)
    ]
    resolved_edges = satisfied_edges | dead_edges
    all_resolved = all(e.id in resolved_edges for e in incoming_forward)

    if not all_resolved:
        return

    # Check join policy
    if node.config.join_policy == JoinPolicy.WAIT_ANY:
        has_satisfied = any(e.id in satisfied_edges for e in incoming_forward)
        if has_satisfied:
            ready.add(node_id)
        else:
            _skip_node_and_cascade_dpe(node_id, ...)
    else:  # WAIT_ALL (default)
        all_dead = all(e.id in dead_edges for e in incoming_forward)
        if all_dead:
            _skip_node_and_cascade_dpe(node_id, ...)
        else:
            ready.add(node_id)
```

### 5.4 Self-Healing Feedback Loops
**Files**: `src/agentflow/core/executor/graph.py` & `src/agentflow/core/executor/runner.py`

#### What was built
1. **Back-Edge Graph Partitioning**:
   - `build_execution_graph()` ignores edges with `is_feedback=True` during Kahn's topological sort. This prevents cycles from breaking DAG validation.
2. **Dynamic Cycle Node Discovery**:
   - Uses **reachability intersection** to isolate the exact loop sub-graph:
   ```python
   def _find_cycle_nodes(source_id: str, target_id: str, workflow: WorkflowDef) -> set[str]:
       # 1. BFS forward from target_id
       reachable_from_target = _bfs_forward(target_id)
       # 2. BFS backward from source_id
       can_reach_source = _bfs_backward(source_id)
       # 3. Intersection = nodes in the loop cycle
       return reachable_from_target & can_reach_source
   ```
3. **Selective Cycle Reset**:
   - Resets `completed`, `satisfied_edges`, and `dead_edges` **only** for nodes in the intersection (`{writer, reviewer}`).
   - Upstream nodes (`trigger`, `research`, `classifier`) remain completed; their outputs and cost are preserved.
   - Enqueues `target_id` back into the `ready` set with an incremented iteration count.
4. **Loop Guards**:
   - Tracks `node_iterations: dict[str, int]`.
   - Halts loop if iterations exceed `workflow.max_loop_iterations` (default: 3).

### 5.5 Iterative Agent Refinement (`WriterAgent` ↔ `ReviewerAgent`)
- **`WriterAgent` (`src/agentflow/core/agents/writer/writer_agent.py`)**:
  - Inspects incoming messages for previous `ReviewerAgent` outputs.
  - If review feedback is present, it constructs a revision prompt:
    ```
    PREVIOUS DRAFT: {previous_body}
    REVIEWER CRITIQUE: {reviewer_feedback}
    SPECIFIC IMPROVEMENTS REQUIRED: {reviewer_improvements}
    INSTRUCTION: Revise the draft to address all critique points above.
    ```
- **`ReviewerAgent` (`src/agentflow/core/agents/reviewer/reviewer_agent.py`)**:
  - Evaluates drafts against structured criteria (personalization, tone, call to action).
  - Emits structured output: `score: float`, `passed: bool`, `feedback: str`, `improvements: list[str]`.

### 5.6 Error Recovery Routing
- In `EdgeDef`: Added `is_error_handler: bool = False`.
- In `WorkflowRunner`:
  - If a node exhausts all retries and raises `NodeExecutionError`:
    - Checks for outgoing edges where `is_error_handler=True`.
    - If found: Routes execution to the error handler node (e.g., alert Slack or log incident) and satisfies that edge.
    - Normal outbound edges are marked as dead.
    - The overall workflow execution finishes cleanly without an unhandled crash.

### 5.7 Phase 3 Comparative Rationale

| Architecture Choice | Why We Chose It | Why Alternative Was Rejected |
| :--- | :--- | :--- |
| **Edge-Level DPE Tracking** | Tracks individual `satisfied_edges` and `dead_edges`; correctly handles multi-branch decisions. | **Airflow-style node trigger rules** only check predecessor node status. When one router node branches to multiple paths, the router node itself succeeded, making node-level checks fail. |
| **Reachability Intersection for Loops** | Resets only the nodes involved in the feedback cycle (`reachable & can_reach`). | Resetting the entire workflow wastes money and time by re-running expensive upstream research and classification nodes. |
| **Safe `OutputWrapper` Evaluation** | Allows natural dot-notation (`output.score >= 7`) with restricted safe built-ins. | Unrestricted `eval()` enables arbitrary code execution; Jinja2 string templates cannot cleanly evaluate boolean logic like `not output.passed`. |

---

## 6. Comprehensive File-by-File & Function-by-Function Reference

| Directory | File | Primary Classes / Functions | Core Purpose |
| :--- | :--- | :--- | :--- |
| `src/agentflow/` | `config.py` | `Settings` | Pydantic BaseSettings loading `.env` with model, budget, and secret defaults. |
| `src/agentflow/` | `logging_config.py` | `configure_logging()` | Structured logging setup (structlog) for JSON or colored console output. |
| `core/schemas/` | `tool.py` | `ToolParameter`, `ToolDefinition` | Defines tool parameters and serializes to OpenAI function call schemas. |
| `core/schemas/` | `workflow.py` | `WorkflowDef`, `NodeDef`, `EdgeDef`, `AgentMessage`, `RunRecord`, `NodeRunRecord`, `JoinPolicy`, `RetryPolicy` | Single source of truth Pydantic models for the entire workflow platform. |
| `core/executor/` | `context.py` | `RunContext`, `StepLimitExceeded`, `CostLimitExceeded` | Ephemeral execution state tracking outputs, runs, tokens, costs, and limits. |
| `core/executor/` | `graph.py` | `build_execution_graph()`, `ExecutionGraph` | Validates graph topology, partitions feedback edges, and calculates Kahn layers. |
| `core/executor/` | `mapping.py` | `resolve_data_map()`, `evaluate_condition()`, `OutputWrapper` | Maps parameters between nodes and safely evaluates conditional branch expressions. |
| `core/executor/` | `node_runner.py`| `run_node()` | Isolates single node execution with inputs, tools, credentials, and retries. |
| `core/executor/` | `runner.py` | `run_workflow()`, `_handle_edge_resolution()`, `_find_cycle_nodes()` | Top-level async engine driving parallel execution, DPE, loops, and error routing. |
| `core/tools/` | `base.py` | `BaseTool`, `ToolResult` | Abstract base class contract for all tools and standard output envelope. |
| `core/tools/` | `registry.py` | `ToolRegistry`, `register_all_builtin_tools()` | Central registry for tool instances accessible by string identifiers. |
| `core/tools/` | `credentials.py`| `CredentialStore` | Fernet AES-128-CBC cryptographic key store with `.env` fallback. |
| `core/tools/` | `tool_loop.py` | `ToolLoop`, `run_tool_loop()` | ReAct autonomous tool calling loop with model reasoning and observation injection. |
| `core/tools/` | `web_search.py` | `WebSearchTool` | Serper.dev + DuckDuckGo web search with offline mock simulation mode. |
| `core/tools/` | `http_tool.py` | `HttpTool` | Httpx async HTTP client for external API requests (REST). |
| `core/tools/` | `email_tool.py` | `EmailSendTool` | Email sender supporting SendGrid, SMTP TLS, and stub dry-run mode. |
| `core/llm/` | `client.py` | `LLMClient` | LiteLLM client providing unified access to 100+ LLM providers and cost tracking. |
| `core/llm/` | `structured.py`| `StructuredOutputParser` | Pydantic JSON parser with markdown fence stripping and self-healing auto-repair. |
| `core/agents/` | `base.py` | `BaseAgent`, `AgentContext`, `AgentResult` | Abstract base class for all AI agents and execution context envelope. |
| `core/agents/` | `registry.py` | `AgentRegistry`, `register_all_builtin_agents()` | Extensible registry for agent types (`trigger`, `research`, `writer`, etc.). |
| `core/agents/trigger/` | `manual.py` | `TriggerManualAgent` | Entry point node emitting initial workflow parameters into the graph. |
| `core/agents/research/`| `research_agent.py` | `ResearchAgent`, `ResearchOutput` | Gathers intelligence via WebSearchTool or synthesizes structured findings. |
| `core/agents/classifier/`| `classifier_agent.py`| `ClassifierAgent`, `ClassificationOutput` | Categorizes leads, evaluates ICP match, and determines routing branches. |
| `core/agents/writer/` | `writer_agent.py` | `WriterAgent`, `WriterOutput` | Generates cold outreach emails; incorporates review critique on revision passes. |
| `core/agents/reviewer/`| `reviewer_agent.py` | `ReviewerAgent`, `ReviewerOutput` | Evaluates copy quality, emitting approval boolean, score, and improvements. |
| `core/agents/email/` | `email_agent.py` | `EmailAgent`, `EmailOutput` | Action agent that formats and dispatches emails via `EmailSendTool`. |
| `core/workflows/`| `demo_workflow.py` | `build_demo_workflow()` | Assembles the complete 6-node production DAG with feedback loop and branching. |
| `scripts/` | `run_demo.py` | `main()` | CLI harness executing the complete pipeline in live or offline `--mock` mode. |

---

## 7. Verification, Quality Gates & Live Demo Simulation

### 7.1 Automated Test Suite (119 Tests)
The entire codebase is verified by 119 unit and integration tests across 10 test modules:

```powershell
pytest tests/
# Output:
# ============================= test session starts =============================
# platform win32 -- Python 3.12.9, pytest-9.1.1, pluggy-1.6.0
# rootdir: C:\work\ai store\no name project\agentflow\backend
# configfile: pyproject.toml
# testpaths: tests
# collected 119 items
#
# tests\test_agents\test_credentials.py ..........                         [  8%]
# tests\test_agents\test_tool_loop.py .................                    [ 22%]
# tests\test_agents\test_tool_registry.py ............                     [ 32%]
# tests\test_agents\test_tools_phase2.py ................                  [ 46%]
# tests\test_executor\test_context.py ............                         [ 56%]
# tests\test_executor\test_control_flow_phase3.py .............            [ 67%]
# tests\test_executor\test_demo_workflow.py ..........                     [ 75%]
# tests\test_executor\test_graph.py ........                               [ 82%]
# tests\test_executor\test_mapping.py ..............                       [ 94%]
# tests\test_executor\test_runner.py .......                               [100%]
# ============================= 119 passed in 3.41s =============================
```

### 7.2 Linter & Type Compliance
```powershell
ruff check .
# Output: All checks passed! 0 errors, 0 warnings.
```

### 7.3 End-to-End Execution Trace (`run_demo.py --mock`)
Running the production workflow demonstrates the complete engine in action:

```
1. [TRIGGER]   Initial inputs provided (Lead: Sarah Chen, Company: TechCorp Inc).
2. [RESEARCH]  Web search synthesized 3 findings (Confidence: 94%).
3. [ROUTER]    Lead scored 9.2/10 -> Routed to 'qualified' branch.
4. [WRITER]    Draft 1 composed (Word count: 62).
5. [REVIEWER]  Draft 1 evaluated -> Score 6.0/10, Passed: False.
               Critique: "Please reference enterprise cloud scaling explicitly and tighten CTA."
6. [FEEDBACK]  Feedback edge condition (not output.passed) evaluated to TRUE.
               Cycle detected: {writer, reviewer}. Resetting iteration state.
7. [WRITER]    Draft 2 composed (Iteration 2) incorporating Reviewer critique.
8. [REVIEWER]  Draft 2 evaluated -> Score 9.5/10, Passed: True.
               Critique: "Outstanding revised cold email! Approved."
9. [EMAIL]     EmailSendTool executed (Recipient: prospect@example.com, Message ID: msg_0f5167723817).
10. [STATUS]   Run COMPLETED: 7 steps, 1,860 tokens, $0.0023 total cost.
```

---

## 8. Transition to Phase 4 (Next Steps)

With the core engine, tools, and control flow fully built and verified:
1. **Database Layer**: PostgreSQL + SQLAlchemy async models for Workflows, Runs, NodeRuns, and Credentials.
2. **FastAPI Application**: REST endpoints for workflow CRUD, run triggering, and telemetry streaming.
3. **Distributed Task Queue**: Redis + Arq worker for asynchronous background execution.
4. **Real-Time Streaming**: WebSockets / SSE for live canvas node execution visualization.
