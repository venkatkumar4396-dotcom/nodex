# AgentFlow Engine & Architectural Invariants

## 1. Schema Single Source of Truth
- All node inputs, outputs, messages, edges, and configurations must be strictly typed Pydantic models in `agentflow.core.schemas`.
- Never use raw untyped dictionaries for inter-agent communication.
- Node outputs are packaged into `AgentMessage` objects containing payload, metadata, token consumption, and cost tracking.

## 2. Topological Graph Execution & Feedback-Edge Partitioning
- Forward edges must form a Directed Acyclic Graph (DAG) validated using Kahn's algorithm.
- Feedback edges (`is_feedback=True`) represent iterative loops (e.g., Reviewer -> Writer). They MUST be excluded from forward in-degree computation during DAG validation to prevent false `CycleDetectedError` exceptions.
- The executor runner must resolve cycle nodes via reachability intersection (`_find_cycle_nodes`) to selectively reset iteration state while preserving upstream history.
- Every iterative loop must enforce `max_loop_iterations` and `max_steps` to guarantee termination.

## 3. Dead-Path Elimination (DPE) & Join Policies
- When evaluating conditional edges, track both `satisfied_edges` and `dead_edges` explicitly.
- Downstream nodes must evaluate readiness against their `JoinPolicy`:
  - `WAIT_ALL`: Node is ready when all incoming forward edges have resolved (satisfied or dead) and at least one is satisfied. If all incoming edges are dead, mark the node as `skipped` and cascade DPE downstream.
  - `WAIT_ANY`: Node is ready as soon as any incoming forward edge is satisfied.
- This prevents diamond-join deadlocks (e.g. IF/ELSE converging downstream).

## 4. Safe Dynamic Condition Evaluation
- Branch conditions must be evaluated using restricted namespaces with safe built-ins (`abs`, `len`, `round`, `min`, `max`, `int`, `float`, `str`, `bool`).
- Never use unrestricted `eval()` or `exec()`.
- Wrap outputs in `OutputWrapper` to permit both dot-notation (`output.score >= 7`) and direct unpacked key lookups (`score >= 7`).

## 5. Tool Registry & Credential Isolation
- Tools are registered by string identifier in the singleton `ToolRegistry`.
- Secrets (API keys, SMTP passwords) are encrypted via Fernet in `CredentialStore`.
- Credentials must be injected transiently at node runtime into tool instances. Never log credentials, never expose them to LLM prompts, and never serialize them in workflow definitions.

## 6. Zero-Regression Quality Gates
- All additions must pass `ruff check .` with 0 warnings.
- All additions must maintain 100% test pass rate with `pytest tests/`.
- Offline `--mock` simulation must remain functional for all end-to-end workflows without requiring live API keys.
