# AUDIT.md — Honest Architecture & Systems Audit (Phase 0)

> **Document Version**: 1.0.0  
> **Date**: October 18, 2026  
> **Repository**: `agentflow` (NodeX Platform)  
> **Auditor**: Principal AI Systems Architect & Core Platform Engineer  
> **Baseline Engine Status**: 133 Unit/Integration Tests Passing  

---

## Executive Audit Summary

An exhaustive, code-level and runtime-verified investigation was conducted across the entire AgentFlow codebase. This audit tests claims against reality with concrete command execution, source code inspection, and architectural stress tests.

| Audit Item | Area | Verdict | Summary Finding |
| :--- | :--- | :---: | :--- |
| **1** | Agent Autonomous Tool Loops | **PARTIAL** | Only 4 of 17 agents (`research`, `tool`, `email`, `universal`) invoke `run_tool_loop()`. Most agents make a single `complete_structured()` call or simulate operations in strings. |
| **2** | Real End-to-End LLM Execution | **PARTIAL** | Runs with real models (`openrouter/nvidia/nemotron-3.5-lightning:free`) execute successfully (495 tokens, 0.0 USD), but default hardcoded models (`moonshot/moonshot-v1-32k`) fail without keys and silently fall back to mock simulation. High latency (45–120s) triggers node timeouts. |
| **3** | Crash Safety & Restart Recovery | **FAIL** | Runs in progress when the server restarts remain permanently orphaned in `"running"` or `"paused"` state. Resuming an approved HITL run re-runs the entire workflow from Node 1 instead of continuing from the paused frontier. |
| **4** | Security Review | **FAIL** | Remote Code Execution (RCE) vulnerability in edge condition evaluation (`eval()` in `mapping.py:238`); `exec()` sandbox in `code_agent.py:71` is unisolated; no SSRF protection in HTTP tools; no domain enforcement at the network layer. |
| **5** | Auth & Multi-Tenancy | **FAIL** | Zero authentication (no JWT, sessions, API keys). Zero multi-tenancy (no `User`, `Tenant`, or `Workspace` models in DB). All REST/SSE endpoints are completely unauthenticated and public. |
| **6** | Execution Limits & Guardrails | **PARTIAL** | Step caps (100) and cost budgets ($5.0) are enforced by `RunContext`, but per-tool timeouts, run-level total time limits, and repeated-identical-call loop detection do not exist. |
| **7** | Frontend Robustness & SSE Reconnect | **PARTIAL** | Canvas handles live updates, but SSE error handler immediately closes the connection without auto-reconnect logic (falling back to a 1-second poll timer). Unconfigured nodes display no validation error badges. |
| **8** | Gaps Between Docs and Reality | **FAIL** | Significant overclaiming: Playwright browser execution, standard MCP protocol client, persistent cross-run memory, and Postgres/Arq workers are either mocked or in-memory stubs. |

---

## Detailed Audit Findings & Evidence

### 1. Autonomous Tool Loop vs Single LLM Call

**Verdict**: **PARTIAL**

#### Verified Agent Implementation Table

| Agent Type | Class Name | Autonomous Loop? | Tools Available | Configured Limits | Evidence / File Reference |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `trigger_manual` / `webhook` | `ManualTriggerAgent` | **No** | None | None | [`manual.py:35`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/trigger/manual.py#L35) — Passthrough of trigger payload. |
| `research` | `ResearchAgent` | **Yes** | `web_search`, `http_tool` | `MAX_TOOL_ROUNDS=10` | [`research_agent.py:151`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/research/research_agent.py#L151) — Calls `run_tool_loop()`, then `complete_structured()`. |
| `router` / `classifier` | `ClassifierAgent` | **No** | None | None | [`classifier_agent.py:141`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/classifier/classifier_agent.py#L141) — Single `complete_structured()` call. |
| `writer` | `WriterAgent` | **No** | None | None | [`writer_agent.py:140`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/writer/writer_agent.py#L140) — Single `complete_structured()` call. |
| `reviewer` | `ReviewerAgent` | **No** | None | None | [`reviewer_agent.py:145`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/reviewer/reviewer_agent.py#L145) — Single `complete_structured()` call. |
| `human_approval` | `HumanApprovalAgent` | **No** | None | None | [`approval_agent.py:52`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/approval/approval_agent.py#L52) — State machine check in shared context. |
| `supervisor` | `SupervisorAgent` | **No** | None | None | [`supervisor_agent.py:85`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/supervisor/supervisor_agent.py#L85) — Single `complete_structured()` returning `SupervisorOutput`; does NOT dynamically delegate or run sub-agents. |
| `rag` | `RAGAgent` | **No** | None | None | [`rag_agent.py:96`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/rag/rag_agent.py#L96) — Single `complete_structured()`. Context is read from raw `input_data["knowledge_documents"]` (no vector database or retriever). |
| `memory` | `MemoryAgent` | **No** | None | None | [`memory_agent.py:56`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/memory/memory_agent.py#L56) — In-memory dictionary merge in `context.get_shared("persistent_memory")`. Zero database persistence. |
| `browser_operator` | `BrowserOperatorAgent` | **No (Simulated)**| Simulated actions | `max_steps=10` | [`browser_agent.py:96`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/browser/browser_agent.py#L96) — Loops up to 10 turns, but actions append strings to a dictionary; does NOT launch Playwright or real browsers. |
| `code` | `CodeAgent` | **No** | None | None | [`code_agent.py:71`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/code/code_agent.py#L71) — Direct `exec(script)` with restricted `__builtins__`, or fallback single LLM call. |
| `mcp_client` | `MCPClientAgent` | **No** | SQLite, File reads | None | [`mcp_agent.py:57`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/mcp/mcp_agent.py#L57) — Direct local `sqlite3.connect()` or `Path.read_text()`. Does NOT communicate via the Model Context Protocol. |
| `synthesizer` | `SynthesizerAgent` | **No** | None | None | [`synthesizer_agent.py:64`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/synthesizer/synthesizer_agent.py#L64) — Single `complete()` call. |
| `prompt` | `PromptAgent` | **No** | None | None | [`prompt_agent.py:74`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/prompt/prompt_agent.py#L74) — Single `complete()` call. |
| `email` | `EmailAgent` | **Yes** | `email_send` | `MAX_TOOL_ROUNDS=10` | [`email_agent.py:142`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/email/email_agent.py#L142) — Calls `run_tool_loop()` when `tools` attached and not in `dry_run`. |
| `tool` | `ToolAgent` | **Yes** | Any attached | `MAX_TOOL_ROUNDS=10` | [`tool_agent.py:68`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/tool/tool_agent.py#L68) — Calls `run_tool_loop()` over all attached tools. |
| `universal` | `UniversalAgent` | **Yes** | Any attached | `MAX_TOOL_ROUNDS=10` | [`universal.py:197`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/universal.py#L197) — Calls `run_tool_loop()`. |

---

### 2. Real End-to-End LLM Execution

**Verdict**: **PARTIAL**

#### Test Execution Evidence
1. **Live Model Probe**: Verified live connectivity with OpenRouter via `litellm.completion` and `litellm.acompletion`:
   ```bash
   .venv\Scripts\python -c "import litellm; from agentflow.config import settings; res = litellm.completion(model='openrouter/nvidia/nemotron-3.5-lightning:free', messages=[{'role':'user','content':'Say hello in 3 words'}], api_key=settings.openrouter_api_key); print(res.choices[0].message.content)"
   ```
   * **Output**: `Hello there friend`
   * **Tokens**: 495 tokens
   * **Cost**: $0.000000 USD
   * **Latency**: ~48.2 seconds (due to free-tier queue congestion).
2. **Demo Workflow Execution (`run_demo.py`)**:
   - The default workflow definition in [`demo_workflow.py:55`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/workflows/demo_workflow.py#L55) hardcodes `model="moonshot/moonshot-v1-32k"`.
   - When run without Moonshot credentials, LiteLLM catches `Missing credentials`, logs:
     ```
     [warning] llm_key_attempt_failed error='Missing credentials... MOONSHOT_API_KEY' model=moonshot/moonshot-v1-32k
     [warning] llm_rate_limit_fallback_to_simulation model=moonshot/moonshot-v1-32k
     ```
   - **Silent Simulation Failure Mode**: Rather than raising a clear error, the engine silently falls back to synthetic mock data (`_generate_smart_mock_response`), obscuring real LLM failures.
   - When configured with OpenRouter (`openrouter/nvidia/nemotron-3.5-lightning:free`), the `research` node exceeded its 120-second timeout (`[error] node_failed errors=['Node timed out after 120s']`) due to provider latency, triggering retries and eventually stalling.

---

### 3. Crash Safety & Restart Recovery

**Verdict**: **FAIL**

#### Investigation & Evidence
1. **Process Crash Mid-Run**:
   - In [`routes_runs.py:100`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/api/routes_runs.py#L100), background runs are spawned as ephemeral in-memory tasks:
     ```python
     task = asyncio.create_task(_execute_run_in_background(run_id, wf_def, ...))
     _active_tasks[run_id] = task
     ```
   - If the FastAPI process is terminated (`SIGKILL` or crash) mid-run:
     - `_active_tasks` in memory is lost.
     - The database record in `runs` table remains permanently stuck in `status="running"`.
     - [`app.py:32`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/api/app.py#L32) (`lifespan`) has **no reconciliation hook** on startup to detect orphaned runs or resume them.
2. **HITL Resumption Flaw**:
   - When an `approval_agent` pauses a workflow, `run_model.status` is saved as `"paused"`.
   - When the operator approves the step via `POST /api/runs/{run_id}/approve` ([`routes_runs.py:531`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/api/routes_runs.py#L531)), the handler executes:
     ```python
     task = asyncio.create_task(
         _execute_run_in_background(run_id, wf_def, run_model.trigger_data or {}, shared_ctx)
     )
     ```
   - **Critical Bug**: `_execute_run_in_background` invokes `run_workflow(workflow=wf_def, ...)`. The engine re-executes the **entire DAG from Node 1 (Trigger -> Research -> Classifier -> Writer)**! It does NOT resume from the paused approval node. Preceding nodes run twice, re-billing tokens and re-calling external APIs.

---

### 4. Security Review

**Verdict**: **FAIL**

| Threat Surface | Vulnerability / Status | Severity | Code Location & Proof |
| :--- | :--- | :---: | :--- |
| **Edge Conditions** | Arbitrary Code Execution via `eval()` | **CRITICAL** | [`mapping.py:238`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/executor/mapping.py#L238): `result = eval(condition, safe_globals)`. In Python, `eval()` with `__builtins__` dictionaries is bypassable via object subclass traversal (e.g. `().__class__.__base__.__subclasses__()`), enabling full remote code execution. |
| **Code Agent Sandbox** | Unisolated `exec()` | **CRITICAL** | [`code_agent.py:71`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/code/code_agent.py#L71): `exec(script_to_run, safe_globals, safe_locals)`. Runs inside the host Python process. Zero containerization (no Docker, gVisor, or cgroups). |
| **SSRF** | Unrestricted HTTP Requests | **HIGH** | [`http_tool.py:77`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/tools/http_tool.py#L77): `httpx.AsyncClient.request(method, url)`. No IP allowlist or private network check (can query `http://169.254.169.254`, `http://localhost:6379`, or internal networks). |
| **Browser Agent Domain Policy** | Policy in mock only | **MEDIUM** | [`browser_agent.py:43`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/agents/browser/browser_agent.py#L43): Domain allowlist is evaluated in Python string checking, but no real browser is running. |
| **Prompt Injection** | Guardrail in Prompt Only | **MEDIUM** | [`tool_loop.py:433`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/tools/tool_loop.py#L433): Wraps tool results in `<tool_result>`. Effective against naive models, but no semantic defense or input/output guardrail node exists before destructive actions. |
| **CORS** | Open to Multiple Dev Ports | **LOW** | [`app.py:67`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/api/app.py#L67): Hardcoded to localhost ports `5173`, `3000`. |
| **Secrets in Logs** | Redacted in CredentialStore | **PASS** | [`credentials.py:81`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/tools/credentials.py#L81): Fernet symmetric encryption prevents key logging. However, ephemeral session keys are generated if `FERNET_KEY` is omitted from `.env`. |

---

### 5. Auth & Multi-Tenancy

**Verdict**: **FAIL**

1. **Authentication**: None. There is no user table, no password hashing, no JWT handler, and no session middleware.
2. **Authorization & Multi-Tenancy**:
   - `WorkflowModel` ([`models.py:49`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/db/models.py#L49)) has columns: `id`, `name`, `version`, `definition`, `created_at`, `updated_at`. There is no `owner_id` or `workspace_id`.
   - `RunModel` ([`models.py:90`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/db/models.py#L90)) has no tenancy scoping.
   - Any client calling `GET /api/workflows` or `DELETE /api/workflows/{id}` can view or delete any workflow in the database.
   - Rate limiting: Zero per-user or per-IP rate limiting implemented.

---

### 6. Execution Limits & Guardrails

**Verdict**: **PARTIAL**

| Limit Type | Status | Implementation Detail |
| :--- | :---: | :--- |
| **Max Steps** | **PASS** | Enforced in [`context.py:131`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/executor/context.py#L131) via `StepLimitExceeded` (default 100 steps). |
| **Cost Cap (USD)** | **PASS** | Enforced in [`context.py:139`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/executor/context.py#L139) via `CostLimitExceeded` (default $5.00). |
| **Per-Node Timeout** | **PASS** | Enforced in [`node_runner.py:126`](file:///c:/work/ai%20store/no%20name%20project/agentflow/backend/src/agentflow/core/executor/node_runner.py#L126) via `asyncio.wait_for()`. |
| **Run-Level Total Time** | **FAIL** | No overall timeout for the entire DAG run; long-running workflows with multiple slow nodes can execute indefinitely. |
| **Per-Tool Timeout** | **FAIL** | Tools invoked inside `tool_loop.py` have no per-tool timeout wrapper. If an external API hangs, the loop blocks until the entire node timeout expires. |
| **Repeated Call Detection**| **FAIL** | No hash check or loop detection on identical tool calls. An agent calling `web_search("same query")` 10 times in a row will execute all 10 calls. |

---

### 7. Frontend Robustness & SSE Reconnect

**Verdict**: **PARTIAL**

1. **SSE Reconnection Behavior**:
   - In [`frontend/src/store.js:2570`](file:///c:/work/ai%20store/no%20name%20project/agentflow/frontend/src/store.js#L2570):
     ```javascript
     eventSource.onerror = () => {
       eventSource.close();
     };
     ```
   - On connection error or network blip, the `EventSource` is closed and never reopened. The UI relies entirely on a background 1-second interval HTTP polling fallback ([`store.js:2501`](file:///c:/work/ai%20store/no%20name%20project/agentflow/frontend/src/store.js#L2501)).
2. **Unconfigured Node Handling**:
   - Canvas nodes ([`AgentNode.jsx`](file:///c:/work/ai%20store/no%20name%20project/agentflow/frontend/src/components/AgentNode.jsx)) display default icons and labels even if missing models, system prompts, or required tool credentials. No warning badges or validation panels exist on the canvas.
3. **Error Presentation**:
   - Failed nodes turn red and provide a "Retry" button. Errors are sent to the Execution Dock and toasts, but inline error stack inspection requires opening the modal inspector.

---

### 8. Gaps Between Docs and Reality

**Verdict**: **FAIL**

| Documented Claim | Source File | Actual Reality |
| :--- | :--- | :--- |
| *"Phase 4: PostgreSQL persistence + Arq worker + Redis queue"* | `README.md:50`, `PHASE_1_TO_3_COMPLETE_SPECIFICATION.md:76` | Production code uses zero-config SQLite with in-memory `asyncio.create_task()`. Arq/Redis queue is unintegrated into `/runs`. |
| *"Browser Agent: Autonomous website operator ... Playwright"* | `PHASE_1_TO_3_COMPLETE_SPECIFICATION.md:52` | `browser_agent.py` simulates clicks by string formatting in a Python dict. No Playwright dependency or browser automation is installed. |
| *"MCP Client: Native MCP Client node for standards-compliant data"* | `PHASE_1_TO_3_COMPLETE_SPECIFICATION.md:52` | `mcp_agent.py` connects directly to local SQLite via `sqlite3.connect()` or reads local files. It does not speak the JSON-RPC Model Context Protocol. |
| *"Memory Agent: Persistent semantic memory across sessions"* | `PHASE_1_TO_3_COMPLETE_SPECIFICATION.md:52` | Stores data in `context._shared["persistent_memory"]`. All data vanishes when the execution context ends. |
| *"Supervisor Agent: Dynamic hierarchical delegation"* | `PHASE_1_TO_3_COMPLETE_SPECIFICATION.md:52` | Returns static `SupervisorOutput` JSON from a single LLM prompt. Does not delegate sub-tasks to child agents in runtime. |
| *"RAG Agent with grounded citations"* | `PHASE_1_TO_3_COMPLETE_SPECIFICATION.md:52` | Reads unindexed text directly from `input_data`. No vector database, chunks, or embedding similarity search exist. |
| *"132 tests passing"* | `README.md:76` | Core engine test suite has 133 passing tests, but full suite triggers 11 errors due to pytest-asyncio fixture scope misconfigurations, plus 1 failure in a scratch test file (`test_kimi.py`). |

---

## Prioritized Implementation Roadmap

Based on this audit, work will proceed strictly according to the plan:

```
[Phase 0: Audit Complete]
       ↓
[Phase 1: Autonomy Core]
  - Hardened Agent Loop (hard caps, per-tool timeouts, loop deduplication, streamed reasoning)
  - Least-privilege tool allowlists & autonomy levels (suggest | ask_first | act)
  - Run-level Budget Governor (tokens, USD, wall-clock time)
       ↓
[Phase 2: Goal Mode (Headline Feature)]
  - Natural language goal submission (no initial graph required)
  - Pydantic Planner Agent -> live visual DAG generation
  - Dynamic Supervisor (re-planning, worker selection, max-delegation limit)
  - Critic Reflection Gate with bounded retries
       ↓
[Phase 3: Automation & Durability]
  - Real triggers: Webhooks with HMAC signatures, persistent cron, email triggers
  - Durable execution: Per-node state checkpointing & crash resumption (no re-running completed nodes)
  - DB-backed background worker queue
  - Webhook/Email notifications for failures & HITL pauses
       ↓
[Phase 4: Self-Improving Loop]
  - Run Doctor with safe auto-patching guardrails (no credential or destructive changes)
  - Evaluator test generation on every workflow version with regression gating
  - True persistent memory (database-backed semantic store across sessions)
       ↓
[Phase 5: Production Hardening]
  - JWT auth, workspace tenancy, and route-level authorization
  - Safe AST expression evaluator (zero eval())
  - Containerized/process sandboxing for code execution & SSRF network safeguards
  - Prompt injection wrapper & Fernet master key rotation
  - Structured observability with health/readiness endpoints
       ↓
[Phase 6: Product Polish & Verified Docs]
  - Frontend: Replay scrubber, validation panel with error links, SSE auto-reconnect with backoff
  - Verified README and architecture docs reflecting only measured reality
  - 3-Minute end-to-end demo script
```

---
*End of Phase 0 Audit. Ready to proceed to Phase 1: Autonomy Core upon confirmation.*
