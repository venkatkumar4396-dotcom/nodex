"""
Writer Agent — composes tailored outreach emails or other written content.

Input: research summary + classifier output (score, category, lead context)
Output: structured email with subject, body, tone, word count

Design: The Writer's system prompt is configurable per-node (tone, style,
purpose). The demo uses it for cold outreach emails, but the same agent
can write blog posts, Slack messages, or support replies.

Prompt injection defense: research findings are wrapped as cited data,
not as direct instructions to the model.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, ClassVar

import structlog
from pydantic import BaseModel, Field

from agentflow.core.agents.base import BaseAgent
from agentflow.core.llm.structured import complete_structured
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


class WriterOutput(BaseModel):
    """Structured output from the Writer agent."""
    subject: str = Field(description="Email subject line (under 60 chars)")
    body: str = Field(description="Full email body in plain text")
    tone: str = Field(description="Tone used: professional, friendly, direct, etc.")
    word_count: int = Field(ge=10, description="Approximate word count of the body")
    personalization_hooks: list[str] = Field(
        default_factory=list,
        description="List of specific facts used to personalize the email"
    )


class WriterAgent(BaseAgent):
    """
    Writer agent: composes personalized outreach content.

    Expected input (from edge data_map):
      - summary: research summary
      - lead_name: person's name
      - company: company name
      - score: qualification score (from classifier)
      - category: lead category

    Config options (in NodeConfig.extra):
      - tone: "professional" | "friendly" | "direct" (default: "professional")
      - max_words: target max word count (default: 150)
      - purpose: what the email is for (default: "sales outreach")
    """

    type_key: ClassVar[AgentType] = AgentType.WRITER

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        # Fallback to trigger_data and context outputs if input_data is missing context
        trigger = context.run.trigger_data or {}
        lead_name = input_data.get("lead_name") or trigger.get("lead_name") or "Unknown"
        company = input_data.get("company") or trigger.get("company") or "Unknown Company"
        summary = input_data.get("summary", "")
        key_findings = input_data.get("key_findings", [])
        score = input_data.get("score", 0)
        category = input_data.get("category", "unknown")
        recommendation = input_data.get("recommendation", "")
        validation_feedback = input_data.get("_validation_feedback")

        if not summary:
            for out in context.get_all_outputs().values():
                if isinstance(out, dict) and out.get("summary"):
                    summary = out["summary"]
                    if not key_findings and out.get("key_findings"):
                        key_findings = out["key_findings"]
                    break

        if (not lead_name or lead_name == "Unknown") and trigger.get("lead_name"):
            lead_name = trigger["lead_name"]
        if (not company or company == "Unknown Company") and trigger.get("company"):
            company = trigger["company"]

        # Config-driven writing parameters
        tone = config.extra.get("tone", "professional")
        max_words = config.extra.get("max_words", 150)
        purpose = config.extra.get("purpose", "sales outreach")
        sender_name = config.extra.get("sender_name", "Alex")
        sender_company = config.extra.get("sender_company", "AgentFlow")

        system_prompt = config.system_prompt or (
            f"You are an expert B2B copywriter specializing in {purpose}. "
            f"Write in a {tone} tone. Be concise, specific, and human. "
            f"Never use generic openers like 'I hope this finds you well'. "
            f"Reference specific facts from the research to show you've done your homework. "
            f"Target length: {max_words} words maximum."
        )

        # Wrap research data as cited information (prompt injection defense)
        findings_text = "\n".join(
            f"- {f.get('title', '')}: {f.get('detail', '')}"
            for f in key_findings[:5]  # limit to top 5
        ) if key_findings else "General research data available."

        user_content = f"""Write a personalized {purpose} email.

RECIPIENT CONTEXT (use these facts for personalization):
- Name: {lead_name}
- Company: {company}
- Lead category: {category}
- Qualification score: {score}/10
- Research summary: {summary}
- Key facts to reference:
{findings_text}
- Recommended angle: {recommendation}

SENDER: {sender_name} from {sender_company}

Write a compelling, personalized email that:
1. Opens with something specific about them (not generic)
2. Connects their situation to your solution
3. Has a clear, low-friction call to action
4. Stays under {max_words} words
"""

        reviewer_feedback = input_data.get("feedback") or input_data.get("reviewer_feedback")
        suggested_subject = input_data.get("revised_subject")

        if reviewer_feedback:
            user_content += f"""
EDITORIAL REVISION REQUIRED:
The previous draft was reviewed and received the following critique:
"{reviewer_feedback}"
"""
            if suggested_subject:
                user_content += f"Suggested subject line to consider: {suggested_subject}\n"
            user_content += "Please revise the draft to address all the reviewer's feedback points."

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        result, llm_resp = await complete_structured(
            messages=messages,
            output_model=WriterOutput,
            model=config.model,
            validation_feedback=validation_feedback,
        )

        # Substitute any leftover raw template brackets in subject and body
        body = result.body
        subject = result.subject
        if lead_name and lead_name != "Unknown":
            first_name = lead_name.split()[0]
            for pat in [
                r"\{\{\s*(?:First\s*Name|first_name|Name|name)\s*\}\}",
                r"\[\s*(?:First\s*Name|first_name|Name|name)\s*\]",
            ]:
                body = re.sub(pat, first_name, body, flags=re.IGNORECASE)
                subject = re.sub(pat, first_name, subject, flags=re.IGNORECASE)
            for pat in [
                r"\{\{\s*(?:Full\s*Name|Lead\s*Name|lead_name)\s*\}\}",
                r"\[\s*(?:Full\s*Name|Lead\s*Name|lead_name)\s*\]",
            ]:
                body = re.sub(pat, lead_name, body, flags=re.IGNORECASE)
                subject = re.sub(pat, lead_name, subject, flags=re.IGNORECASE)

        if company and company != "Unknown Company":
            for pat in [
                r"\{\{\s*(?:Company|company|Company\s*Name)\s*\}\}",
                r"\[\s*(?:Company|company|Company\s*Name)\s*\]",
            ]:
                body = re.sub(pat, company, body, flags=re.IGNORECASE)
                subject = re.sub(pat, company, subject, flags=re.IGNORECASE)

        output_data = result.model_dump()
        output_data["body"] = body
        output_data["subject"] = subject
        output_data.update({"lead_name": lead_name, "company": company})

        log.info(
            "writer_completed",
            lead_name=lead_name,
            subject=result.subject,
            word_count=result.word_count,
        )

        return AgentMessage(
            run_id=context.run.id,
            node_id=context.current_node_id or "writer",
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
