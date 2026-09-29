"""
Demo workflow definition: Lead Research & Qualified Outreach

Graph:
  [Manual Trigger]
       ↓  {lead_name, company, topic, goal}
  [Research Agent]
       ↓  {summary, key_findings, confidence, lead_name, company}
  [Classifier Agent]
       ├─ output.score < 7  →  STOP (edge condition false, node skipped)
       └─ output.score >= 7 →
  [Writer Agent]
       ↓  {subject, body, tone, word_count}
  [Reviewer Agent]  ← Phase 1: no feedback loop (Phase 3 adds the Writer↔Reviewer edge)

This is a pure Python WorkflowDef — no database needed in Phase 1.
"""
from __future__ import annotations

from uuid import uuid4

from agentflow.core.schemas.workflow import (
    AgentType,
    EdgeDef,
    NodeConfig,
    NodeDef,
    Position,
    RetryPolicy,
    WorkflowDef,
)


def build_demo_workflow() -> WorkflowDef:
    """Construct the demo Lead Research & Qualified Outreach workflow."""

    # ── Node definitions ──────────────────────────────────────────────────────

    trigger = NodeDef(
        id="trigger",
        type=AgentType.TRIGGER_MANUAL,
        label="Manual Trigger",
        position=Position(x=100, y=100),
        config=NodeConfig(
            system_prompt="",
            timeout_seconds=5,
        ),
    )

    research = NodeDef(
        id="research",
        type=AgentType.RESEARCH,
        label="Research Agent",
        position=Position(x=100, y=250),
        config=NodeConfig(
            model="moonshot/moonshot-v1-32k",
            system_prompt=(
                "You are a professional B2B research analyst. "
                "Research the given lead and company thoroughly. "
                "Focus on recent signals: hiring, funding, product launches, pain points."
            ),
            retry_policy=RetryPolicy(max_attempts=3, backoff_seconds=2.0),
            timeout_seconds=120,
        ),
    )

    classifier = NodeDef(
        id="classifier",
        type=AgentType.ROUTER,
        label="Lead Scorer",
        position=Position(x=100, y=400),
        config=NodeConfig(
            model="moonshot/moonshot-v1-32k",
            system_prompt=(
                "You are a sales qualification expert. "
                "Score leads 1-10 based on ICP fit, intent signals, and company profile. "
                "Score >= 7 means qualified for outreach."
            ),
            retry_policy=RetryPolicy(max_attempts=3, backoff_seconds=2.0),
            timeout_seconds=60,
        ),
    )

    writer = NodeDef(
        id="writer",
        type=AgentType.WRITER,
        label="Email Writer",
        position=Position(x=300, y=550),
        config=NodeConfig(
            model="moonshot/moonshot-v1-32k",
            system_prompt=(
                "You are an expert B2B copywriter. "
                "Write personalized, concise outreach emails. "
                "Never use generic openers. Reference specific facts about the lead."
            ),
            retry_policy=RetryPolicy(max_attempts=3, backoff_seconds=2.0),
            timeout_seconds=90,
            extra={
                "tone": "professional",
                "max_words": 150,
                "purpose": "cold outreach",
                "sender_name": "Alex",
                "sender_company": "AgentFlow",
            },
        ),
    )

    reviewer = NodeDef(
        id="reviewer",
        type=AgentType.REVIEWER,
        label="Email Reviewer",
        position=Position(x=300, y=700),
        config=NodeConfig(
            model="moonshot/moonshot-v1-32k",
            system_prompt=(
                "You are a senior marketing editor. "
                "Evaluate B2B outreach emails rigorously. "
                "An email passes only if it is personalized, clear, and compelling."
            ),
            retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=2.0),
            timeout_seconds=60,
            extra={
                "threshold": 8,
                "criteria": [
                    "Personalization (references specific facts about the lead)",
                    "Clear value proposition",
                    "Concise (under 150 words)",
                    "Compelling, low-friction CTA",
                    "No generic phrases",
                ],
            },
        ),
    )

    # ── Edge definitions ──────────────────────────────────────────────────────

    # Trigger → Research: pass all trigger data through
    edge_trigger_to_research = EdgeDef(
        id="e_trigger_research",
        source="trigger",
        target="research",
        # No data_map = pass everything from trigger output to research
    )

    # Research → Classifier: pass research output
    edge_research_to_classifier = EdgeDef(
        id="e_research_classifier",
        source="research",
        target="classifier",
        # Pass full research output
    )

    # Classifier → Writer: only if score >= 7
    # Phase 3 note: in a real conditional workflow, we'd add a "not qualified"
    # branch too. Phase 1 demo just lets the run skip the writer if score < 7.
    edge_classifier_to_writer = EdgeDef(
        id="e_classifier_writer",
        source="classifier",
        target="writer",
        condition="output.get('score', 0) >= 7",
        # Map specific fields from classifier output to writer input
        data_map={
            "summary": "{{research.output.summary}}",
            "key_findings": "{{research.output.key_findings}}",
            "lead_name": "{{classifier.output.lead_name}}",
            "company": "{{classifier.output.company}}",
            "score": "{{classifier.output.score}}",
            "category": "{{classifier.output.category}}",
            "recommendation": "{{classifier.output.recommendation}}",
        },
    )

    # Writer → Reviewer: send email for review
    edge_writer_to_reviewer = EdgeDef(
        id="e_writer_reviewer",
        source="writer",
        target="reviewer",
        data_map={
            "subject": "{{writer.output.subject}}",
            "body": "{{writer.output.body}}",
            "tone": "{{writer.output.tone}}",
            "lead_name": "{{writer.output.lead_name}}",
            "company": "{{writer.output.company}}",
            "personalization_hooks": "{{writer.output.personalization_hooks}}",
        },
    )

    return WorkflowDef(
        id=uuid4(),
        name="Lead Research & Qualified Outreach",
        version=1,
        nodes=[trigger, research, classifier, writer, reviewer],
        edges=[
            edge_trigger_to_research,
            edge_research_to_classifier,
            edge_classifier_to_writer,
            edge_writer_to_reviewer,
        ],
        global_max_cost_usd=2.0,
        global_max_steps=20,
    )
