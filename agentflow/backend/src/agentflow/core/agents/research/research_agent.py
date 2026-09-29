"""
Research Agent — investigates a topic and returns structured findings.

Phase 1 implementation: LLM-powered research using the model's training data.
Phase 2 will add actual web search tool calls.

Output schema:
  - summary: concise overview
  - key_findings: list of finding objects with title, detail, relevance_score
  - sources: list of URLs (Phase 1: empty — Phase 2: real URLs from web search)
  - confidence: overall confidence 0.0-1.0
"""
from __future__ import annotations

import structlog
from typing import Any, ClassVar, TYPE_CHECKING
from pydantic import BaseModel, Field

from agentflow.core.agents.base import BaseAgent
from agentflow.core.llm.structured import complete_structured, StructuredOutputError
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


# ── Output schema ─────────────────────────────────────────────────────────────

class KeyFinding(BaseModel):
    title: str = Field(description="Short title of the finding")
    detail: str = Field(description="1-3 sentence explanation")
    relevance_score: float = Field(ge=0.0, le=1.0, description="0=irrelevant, 1=critical")


class ResearchOutput(BaseModel):
    """Structured output from the Research agent."""
    summary: str = Field(description="Concise overview of research findings (2-4 sentences)")
    key_findings: list[KeyFinding] = Field(
        min_length=1, max_length=10,
        description="Individual findings with relevance scores"
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Source URLs (empty in Phase 1, populated in Phase 2)"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Overall confidence in the research quality"
    )
    lead_name: str | None = Field(default=None, description="Lead/subject being researched")
    company: str | None = Field(default=None, description="Company being researched")


# ── Agent ─────────────────────────────────────────────────────────────────────

class ResearchAgent(BaseAgent):
    """
    Research agent: investigates a topic, person, or company.

    Expected input fields (from trigger or edge data_map):
      - topic (str): what to research
      - lead_name (str, optional): person's name
      - company (str, optional): company name
      - goal (str, optional): what the research is for

    Phase 1: Uses LLM knowledge only.
    Phase 2: Will call web_search and http_tool to get real data.
    
    Prompt injection defense: in Phase 2 when web content is retrieved,
    it will be wrapped in <web_content> tags and the system prompt will
    explicitly instruct the model to treat it as external untrusted data.
    """

    type_key: ClassVar[AgentType] = AgentType.RESEARCH

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: "RunContext",
        tools: list["BaseTool"],
    ) -> AgentMessage:
        topic = input_data.get("topic", "")
        lead_name = input_data.get("lead_name", "")
        company = input_data.get("company", "")
        goal = input_data.get("goal", "")
        validation_feedback = input_data.get("_validation_feedback")

        system_prompt = config.system_prompt or (
            "You are a professional B2B research analyst. "
            "Your job is to research leads, companies, and market opportunities. "
            "Be factual, concise, and evidence-based. "
            "Assign honest relevance scores — don't inflate them."
        )

        user_content = f"""Research the following:

Lead/Person: {lead_name or "Not specified"}
Company: {company or "Not specified"}
Topic: {topic or "General company research"}
Goal: {goal or "Assess fit and opportunity"}

Provide structured research findings covering:
1. Company overview and market position
2. Relevant signals (growth, hiring, news, funding)
3. Pain points this lead/company might have
4. Why this lead may or may not be a good fit
"""

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            result, llm_resp = await complete_structured(
                messages=messages,
                output_model=ResearchOutput,
                model=config.model,
                validation_feedback=validation_feedback,
            )
        except StructuredOutputError as e:
            raise  # Let node_runner handle retry

        output_data = result.model_dump()
        # Preserve pass-through fields for downstream agents
        output_data.setdefault("lead_name", lead_name)
        output_data.setdefault("company", company)
        output_data.setdefault("goal", goal)

        log.info(
            "research_completed",
            node_id="research",
            lead_name=lead_name,
            company=company,
            confidence=result.confidence,
            findings_count=len(result.key_findings),
        )

        return AgentMessage(
            run_id=context.run.id,
            node_id=context.current_node_id or "research",
            status=NodeRunStatus.COMPLETED,
            data=output_data,
            metadata=MessageMetadata(
                prompt_tokens=llm_resp.prompt_tokens,
                completion_tokens=llm_resp.completion_tokens,
                total_tokens=llm_resp.total_tokens,
                cost_usd=llm_resp.cost_usd,
                model=llm_resp.model,
            ),
        )
