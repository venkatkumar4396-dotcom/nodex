"""
run_demo.py — Phase 1 CLI entry point for AgentFlow.

Usage:
    python -m agentflow.scripts.run_demo
    python -m agentflow.scripts.run_demo --lead "Sarah Chen" --company "Acme Corp"
    python -m agentflow.scripts.run_demo --model "claude-3-5-sonnet-20241022"

This script:
  1. Loads settings from .env
  2. Registers all built-in agents
  3. Builds the demo workflow (pure Python, no DB)
  4. Executes it via WorkflowRunner
  5. Prints a formatted run summary with per-node logs
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

# Ensure UTF-8 output on Windows consoles to prevent cp1252 charmap encoding errors
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Configure logging before any imports that use structlog
import agentflow.logging_config  # noqa: F401  (side effect: configures structlog)

import structlog

from agentflow.config import settings
from agentflow.core.agents.registry import register_all_builtin_agents
from agentflow.core.executor.runner import run_workflow
from agentflow.core.schemas.workflow import NodeRunStatus, RunStatus
from agentflow.core.workflows.demo_workflow import build_demo_workflow

log = structlog.get_logger(__name__)


async def main(
    lead_name: str,
    company: str,
    topic: str,
    goal: str,
    model: str | None,
    mock: bool = False,
) -> None:
    """Execute the demo workflow and print results."""

    print("\n" + "=" * 70)
    print("  [*] AgentFlow - Phase 1 Demo")
    print("  Lead Research & Qualified Outreach Pipeline")
    if mock:
        print("  [MOCK MODE ACTIVE - Offline DAG Simulation]")
    print("=" * 70 + "\n")

    # Register all built-in agents
    register_all_builtin_agents()

    if mock:
        _register_mock_agents(lead_name, company)

    # Build workflow
    workflow = build_demo_workflow()

    # Override model if specified via CLI
    if model:
        for node in workflow.nodes:
            node.config.model = model
        print(f"[*] Using model: {model}\n")
    elif mock:
        print("[*] Using model: mock/synthetic-agent\n")
    else:
        print(f"[*] Using model: {settings.default_model}\n")

    print(f"[*] Workflow: {workflow.name}")
    print(f"   Nodes: {len(workflow.nodes)} ({', '.join(n.id for n in workflow.nodes)})")
    print(f"   Budget: ${workflow.global_max_cost_usd} max\n")

    # Trigger data — this is what the user would provide in the UI
    trigger_data = {
        "lead_name": lead_name,
        "company": company,
        "topic": topic or f"Research {company} for B2B outreach",
        "goal": goal,
    }

    print(f"[*] Starting run...")
    print(f"   Lead: {lead_name}")
    print(f"   Company: {company}")
    print(f"   Goal: {goal}")
    print("-" * 70 + "\n")

    # Execute
    run = await run_workflow(
        workflow=workflow,
        trigger_data=trigger_data,
    )

    # ── Print summary ──────────────────────────────────────────────────────────
    status_icon = "[OK]" if run.status == RunStatus.COMPLETED else "[FAIL]"
    print(f"\n{'-' * 70}")
    print(f"{status_icon} Run {str(run.id)[:8]}... - {run.status.value.upper()}")
    if run.error:
        print(f"   Error: {run.error}")
    print(f"   Total tokens: {run.total_tokens:,}")
    print(f"   Total cost:   ${run.total_cost_usd:.6f}")
    duration = (
        (run.completed_at - run.started_at) if run.completed_at and run.started_at else 0
    )
    print(f"   Duration:     {duration:.1f}s")
    print(f"\n{'=' * 70}")
    print("  Execution Log (Per-Node)")
    print("=" * 70)

    for nr in run.node_runs:
        status_sym = {
            NodeRunStatus.COMPLETED: "[OK]",
            NodeRunStatus.FAILED: "[FAIL]",
            NodeRunStatus.SKIPPED: "[SKIP]",
            NodeRunStatus.PENDING: "[PEND]",
        }.get(nr.status, "[?]")

        print(f"\n{status_sym} {nr.node_id} ({nr.agent_type.value}) - attempt {nr.attempt}")
        print(f"   Status:   {nr.status.value}")
        print(f"   Duration: {nr.duration_ms}ms")
        print(f"   Tokens:   {nr.prompt_tokens + nr.completion_tokens}")
        print(f"   Cost:     ${nr.cost_usd:.6f}")

        if nr.error:
            print(f"   Error:    {nr.error}")
        if nr.validation_errors:
            print(f"   Validation: {nr.validation_errors}")

        if nr.output:
            print(f"   Output:")
            _print_output(nr.node_id, nr.output)

    print(f"\n{'=' * 70}\n")


def _print_output(node_id: str, output: dict) -> None:
    """Pretty-print node output relevant to the demo."""
    if node_id == "research":
        print(f"     Summary: {output.get('summary', '')[:200]}")
        findings = output.get("key_findings", [])
        print(f"     Findings: {len(findings)} items")
        for f in findings[:3]:
            score = f.get("relevance_score", 0)
            title = f.get("title", "")
            print(f"       [{score:.1f}] {title}")
        print(f"     Confidence: {output.get('confidence', 0):.0%}")

    elif node_id == "classifier":
        print(f"     Score:    {output.get('score', 0)}/10")
        print(f"     Branch:   {output.get('branch', 'unknown')}")
        print(f"     Category: {output.get('category', 'unknown')}")
        print(f"     Reason:   {output.get('reasoning', '')[:150]}")

    elif node_id == "writer":
        print(f"     Subject:  {output.get('subject', '')}")
        print(f"     Words:    {output.get('word_count', 0)}")
        print(f"     Tone:     {output.get('tone', '')}")
        body = output.get("body", "")
        print(f"     Body preview: {body[:300]}...")

    elif node_id == "reviewer":
        print(f"     Score:    {output.get('score', 0)}/10")
        print(f"     Passed:   {output.get('passed', False)}")
        print(f"     Feedback: {output.get('feedback', '')[:200]}")
        improvements = output.get("improvements", [])
        if improvements:
            print(f"     Improvements:")
            for imp in improvements[:3]:
                print(f"       - {imp}")

    else:
        # Generic: just print the dict compactly
        try:
            print(f"     {json.dumps(output, indent=6, default=str)[:400]}")
        except Exception:
            print(f"     {str(output)[:400]}")


def _register_mock_agents(lead_name: str, company: str) -> None:
    """Register mock agent implementations for offline / zero-API-cost simulation."""
    from agentflow.core.agents.base import BaseAgent
    from agentflow.core.agents.registry import agent_registry
    from agentflow.core.schemas.workflow import (
        AgentMessage,
        AgentType,
        MessageMetadata,
        NodeRunStatus,
    )

    class MockResearchAgent(BaseAgent):
        type_key = AgentType.RESEARCH

        async def run(self, input_data, config, context, tools):
            data = {
                "summary": f"{company} is a high-growth cloud company expanding developer tooling and enterprise workflow automation.",
                "key_findings": [
                    {
                        "title": "Enterprise Growth",
                        "detail": f"{company} recently scaled its platform for enterprise integrations.",
                        "relevance_score": 0.95,
                    },
                    {
                        "title": "Decision Maker",
                        "detail": f"{lead_name} spearheads strategic infrastructure and AI initiatives.",
                        "relevance_score": 0.92,
                    },
                    {
                        "title": "Tech Modernization",
                        "detail": "Prioritizing modular agentic architectures and API security.",
                        "relevance_score": 0.88,
                    },
                ],
                "confidence": 0.94,
                "market_signals": [
                    "Series B scaling",
                    "Hiring enterprise engineers",
                    "Active API expansion",
                ],
            }
            return AgentMessage(
                run_id=context.run.id,
                node_id="research",
                status=NodeRunStatus.COMPLETED,
                data=data,
                metadata=MessageMetadata(
                    prompt_tokens=180,
                    completion_tokens=110,
                    total_tokens=290,
                    cost_usd=0.0004,
                    model="mock-model",
                ),
            )

    class MockClassifierAgent(BaseAgent):
        type_key = AgentType.ROUTER

        async def run(self, input_data, config, context, tools):
            data = {
                "score": 9.2,
                "category": "High Priority Tier-1 Prospect",
                "branch": "qualified",
                "reasoning": f"{company} strongly matches ICP with high executive relevance and active budget allocation.",
                "priority": "high",
            }
            return AgentMessage(
                run_id=context.run.id,
                node_id="classifier",
                status=NodeRunStatus.COMPLETED,
                data=data,
                metadata=MessageMetadata(
                    prompt_tokens=120,
                    completion_tokens=60,
                    total_tokens=180,
                    cost_usd=0.0002,
                    model="mock-model",
                ),
            )

    class MockWriterAgent(BaseAgent):
        type_key = AgentType.WRITER

        async def run(self, input_data, config, context, tools):
            body = (
                f"Hi {lead_name},\n\n"
                f"I've been following {company}'s rapid scaling in enterprise developer tooling. "
                f"Engineering teams often struggle when connecting autonomous AI agents into reliable, production workflows.\n\n"
                f"With NodeX, we give teams deterministic topological DAG orchestration, structured output validation, "
                f"and full token telemetry out of the box.\n\n"
                f"Would you be open to a quick 10-minute demo next Tuesday?\n\n"
                f"Best regards,\nNodeX Team"
            )
            data = {
                "subject": f"Modernizing Agentic Workflows at {company}",
                "body": body,
                "tone": "consultative and technical",
                "word_count": len(body.split()),
            }
            return AgentMessage(
                run_id=context.run.id,
                node_id="writer",
                status=NodeRunStatus.COMPLETED,
                data=data,
                metadata=MessageMetadata(
                    prompt_tokens=240,
                    completion_tokens=140,
                    total_tokens=380,
                    cost_usd=0.0005,
                    model="mock-model",
                ),
            )

    class MockReviewerAgent(BaseAgent):
        type_key = AgentType.REVIEWER

        async def run(self, input_data, config, context, tools):
            data = {
                "score": 9.4,
                "passed": True,
                "feedback": "Outstanding cold email. Highly personalized, addresses specific pain points, clear value proposition, and low-friction call to action.",
                "improvements": ["Consider adding a one-line customer case study metric."],
            }
            return AgentMessage(
                run_id=context.run.id,
                node_id="reviewer",
                status=NodeRunStatus.COMPLETED,
                data=data,
                metadata=MessageMetadata(
                    prompt_tokens=190,
                    completion_tokens=70,
                    total_tokens=260,
                    cost_usd=0.0003,
                    model="mock-model",
                ),
            )

    agent_registry.register(AgentType.RESEARCH, MockResearchAgent())
    agent_registry.register(AgentType.ROUTER, MockClassifierAgent())
    agent_registry.register(AgentType.WRITER, MockWriterAgent())
    agent_registry.register(AgentType.REVIEWER, MockReviewerAgent())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AgentFlow Phase 1 Demo — Lead Research & Outreach"
    )
    parser.add_argument("--lead", default="Sarah Chen", help="Lead/contact name")
    parser.add_argument("--company", default="TechCorp Inc", help="Company name")
    parser.add_argument("--topic", default="", help="Research topic override")
    parser.add_argument(
        "--goal",
        default="Qualify this lead for B2B SaaS sales outreach and write a personalized email",
        help="Run goal",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="LLM model override (e.g. 'gpt-4o', 'claude-3-5-sonnet-20241022')",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in offline mock mode (simulates agents without live LLM API calls)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        main(
            lead_name=args.lead,
            company=args.company,
            topic=args.topic,
            goal=args.goal,
            model=args.model,
            mock=args.mock,
        )
    )
