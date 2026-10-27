# Part 4: Agents, Workflows & Production Scripts
## Exhaustive Code & Line-by-Line Architectural Guide

---

## 1. `src/agentflow/core/agents/base.py` & `src/agentflow/core/agents/registry.py`

### 1.1 Complete Source Code (`base.py`)
```python
"""BaseAgent — the interface every agent in AgentFlow must implement."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from agentflow.core.schemas.workflow import AgentMessage, AgentType, NodeConfig

if TYPE_CHECKING:
    from agentflow.core.executor.context import RunContext
    from agentflow.core.tools.base import BaseTool


class BaseAgent(ABC):
    """Abstract base class for all AgentFlow agents."""

    type_key: ClassVar[AgentType]

    @abstractmethod
    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        """Execute the agent logic and return an AgentMessage envelope."""
        ...
```

### 1.2 Complete Source Code (`registry.py`)
```python
"""AgentRegistry — singleton registry mapping AgentType to BaseAgent instances."""
from __future__ import annotations

from typing import TYPE_CHECKING
import structlog

from agentflow.core.schemas.workflow import AgentType

if TYPE_CHECKING:
    from agentflow.core.agents.base import BaseAgent

log = structlog.get_logger(__name__)


class AgentNotFoundError(KeyError):
    """Raised when an AgentType has no registered implementation."""


class AgentRegistry:
    def __init__(self) -> None:
        self._registry: dict[AgentType, BaseAgent] = {}

    def register(self, agent_cls: type[BaseAgent]) -> type[BaseAgent]:
        instance = agent_cls()
        self._registry[agent_cls.type_key] = instance
        log.debug("agent_registered", agent_type=agent_cls.type_key.value)
        return agent_cls

    def get(self, agent_type: AgentType | str) -> BaseAgent:
        if isinstance(agent_type, str):
            try:
                agent_type = AgentType(agent_type)
            except ValueError as e:
                raise AgentNotFoundError(f"Unknown agent type string: '{agent_type}'") from e

        agent = self._registry.get(agent_type)
        if agent is None:
            raise AgentNotFoundError(
                f"No agent registered for type '{agent_type.value}'. "
                f"Registered types: {[t.value for t in self._registry]}"
            )
        return agent

    def list_registered(self) -> list[str]:
        return [t.value for t in self._registry]


agent_registry = AgentRegistry()


def register_all_builtin_agents() -> None:
    from agentflow.core.agents.classifier.classifier_agent import ClassifierAgent
    from agentflow.core.agents.email.email_agent import EmailAgent
    from agentflow.core.agents.research.research_agent import ResearchAgent
    from agentflow.core.agents.reviewer.reviewer_agent import ReviewerAgent
    from agentflow.core.agents.trigger.manual import TriggerManualAgent
    from agentflow.core.agents.writer.writer_agent import WriterAgent

    agent_registry.register(TriggerManualAgent)
    agent_registry.register(ResearchAgent)
    agent_registry.register(ClassifierAgent)
    agent_registry.register(WriterAgent)
    agent_registry.register(ReviewerAgent)
    agent_registry.register(EmailAgent)

    log.info(
        "builtin_agents_registered",
        count=len(agent_registry.list_registered()),
        types=agent_registry.list_registered(),
    )
```

---

## 2. Trigger Node: `src/agentflow/core/agents/trigger/manual.py`

### 2.1 Complete Source Code
```python
"""Manual Trigger Agent — entry point for user-initiated workflow runs."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar
import structlog
from agentflow.core.agents.base import BaseAgent
from agentflow.core.schemas.workflow import (
    AgentMessage,
    AgentType,
    MessageMetadata,
    NodeConfig,
    NodeRunStatus,
)

if TYPE_CHECKING:
    from agentflow.core.executor.context import RunContext
    from agentflow.core.tools.base import BaseTool

log = structlog.get_logger(__name__)


class TriggerManualAgent(BaseAgent):
    type_key: ClassVar[AgentType] = AgentType.TRIGGER_MANUAL

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        return AgentMessage(
            run_id=context.run.id,
            node_id=context.current_node_id,
            status=NodeRunStatus.COMPLETED,
            data=input_data,
            metadata=MessageMetadata(),
        )
```

---

## 3. Lead Research Agent: `src/agentflow/core/agents/research/research_agent.py`

### 3.1 Overview & Logic
- **`ResearchOutput(BaseModel)`**: Emits `summary: str`, `key_findings: list[Finding]`, and `confidence_score: float`.
- **`run()`**:
  - Checks if `web_search` tool is assigned in `tools`.
  - If tool is available: Runs the ReAct `run_tool_loop()`, querying Google or DuckDuckGo for the company and lead details.
  - Extracts structured findings via `complete_structured()`.
  - In offline mode (`mock=True`), generates structured findings instantly without external API calls.

---

## 4. ICP Lead Classifier & Router: `src/agentflow/core/agents/classifier/classifier_agent.py`

### 4.1 Overview & Logic
- **`ClassificationOutput(BaseModel)`**:
  - `score: float`: Numeric score from 1.0 to 10.0 representing Ideal Customer Profile (ICP) alignment.
  - `branch: str`: `"qualified"` if `score >= 7.0`, else `"unqualified"`.
  - `category: str`: Lead priority tier.
  - `reasoning: str`: Detailed justification for the rating.
- **`run()`**:
  - Compares lead research against target persona criteria (enterprise scale, engineering headcount, cloud infrastructure needs).
  - Emits the structured decision envelope that powers downstream dynamic edge evaluation.

---

## 5. Cold Outreach Writer: `src/agentflow/core/agents/writer/writer_agent.py`

### 5.1 Self-Healing Revision Logic
- Inspects incoming inputs for `feedback` or `reviewer_feedback` emitted by a previous iteration of `ReviewerAgent`.
- If editorial critique is present:
  ```python
  if reviewer_feedback:
      user_content += f"""
  EDITORIAL REVISION REQUIRED:
  The previous draft was reviewed and received the following critique:
  "{reviewer_feedback}"
  Please revise the draft to address all the reviewer's feedback points.
  """
  ```
- Generates a revised `WriterOutput` with updated `subject`, `body`, `tone`, and `personalization_hooks`.

---

## 6. Editorial Reviewer & Quality Gate: `src/agentflow/core/agents/reviewer/reviewer_agent.py`

### 6.1 Scoring & Feedback Generation
- **`ReviewerOutput(BaseModel)`**:
  - `score: int`: 1 to 10 rating.
  - `passed: bool`: True only if `score >= threshold` (default: 8).
  - `feedback: str`: Concrete critique.
  - `improvements: list[str]`: Specific bullet points for the writer to address.
- In the workflow graph, a conditional feedback edge (`not output.passed and score < 8`) routes back to `WriterAgent`, triggering the self-healing cycle.

---

## 7. Email Dispatch Agent: `src/agentflow/core/agents/email/email_agent.py`

### 7.1 Action Execution
- **`EmailOutput(BaseModel)`**:
  - `sent: bool`
  - `to: str`
  - `subject: str`
  - `backend: str` (`"sendgrid"`, `"smtp"`, or `"stub"`)
  - `message_id: str`
- Dispatches the email through `EmailSendTool.execute(to=..., subject=..., body=...)`.

---

## 8. The Production Demo Pipeline: `demo_workflow.py` & `run_demo.py`

### 8.1 Complete DAG Assembly (`demo_workflow.py`)
```
[trigger: manual]
       │
       ▼
[research: web_search]
       │
       ▼
[classifier: router]
       │ (score >= 7.0)
       ▼
[writer: sales copy] ◄──────────────┐
       │                            │ (feedback loop: score < 8)
       ▼                            │
[reviewer: QA gate] ────────────────┘
       │ (output.passed == True)
       ▼
[email: outbound dispatch]
```

### 8.2 Execution Harness (`scripts/run_demo.py`)
- Provides CLI flags: `--lead`, `--company`, `--topic`, `--goal`, `--model`, and `--mock`.
- Initializes `register_all_builtin_agents()` and `register_all_builtin_tools()`.
- Runs the complete 6-node pipeline asynchronously using `run_workflow()`.
- Prints per-node formatted logs, execution latencies, token consumption, and dollar costs.
