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
) -> None:
    """Execute the demo workflow and print results."""

    print("\n" + "═" * 70)
    print("  🤖  AgentFlow — Phase 1 Demo")
    print("  Lead Research & Qualified Outreach Pipeline")
    print("═" * 70 + "\n")

    # Register all built-in agents
    register_all_builtin_agents()

    # Build workflow
    workflow = build_demo_workflow()

    # Override model if specified via CLI
    if model:
        for node in workflow.nodes:
            node.config.model = model
        print(f"🔧 Using model: {model}\n")
    else:
        print(f"🔧 Using model: {settings.default_model}\n")

    print(f"📋 Workflow: {workflow.name}")
    print(f"   Nodes: {len(workflow.nodes)} ({', '.join(n.id for n in workflow.nodes)})")
    print(f"   Budget: ${workflow.global_max_cost_usd} max\n")

    # Trigger data — this is what the user would provide in the UI
    trigger_data = {
        "lead_name": lead_name,
        "company": company,
        "topic": topic or f"Research {company} for B2B outreach",
        "goal": goal,
    }

    print(f"🚀 Starting run...")
    print(f"   Lead: {lead_name}")
    print(f"   Company: {company}")
    print(f"   Goal: {goal}")
    print("─" * 70 + "\n")

    # Execute
    run = await run_workflow(
        workflow=workflow,
        trigger_data=trigger_data,
    )

    # ── Print summary ──────────────────────────────────────────────────────────
    status_icon = "✅" if run.status == RunStatus.COMPLETED else "❌"
    print(f"\n{'─' * 70}")
    print(f"{status_icon} Run {str(run.id)[:8]}... — {run.status.value.upper()}")
    if run.error:
        print(f"   Error: {run.error}")
    print(f"   Total tokens: {run.total_tokens:,}")
    print(f"   Total cost:   ${run.total_cost_usd:.6f}")
    duration = (
        (run.completed_at - run.started_at) if run.completed_at and run.started_at else 0
    )
    print(f"   Duration:     {duration:.1f}s")
    print(f"\n{'═' * 70}")
    print("  📊 Per-Node Execution Log")
    print("═" * 70)

    for nr in run.node_runs:
        status_sym = {
            NodeRunStatus.COMPLETED: "✅",
            NodeRunStatus.FAILED: "❌",
            NodeRunStatus.SKIPPED: "⏭️ ",
            NodeRunStatus.PENDING: "⏸️ ",
        }.get(nr.status, "❓")

        print(f"\n{status_sym} {nr.node_id} ({nr.agent_type.value}) — attempt {nr.attempt}")
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

    print(f"\n{'═' * 70}\n")


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
                print(f"       • {imp}")

    else:
        # Generic: just print the dict compactly
        try:
            print(f"     {json.dumps(output, indent=6, default=str)[:400]}")
        except Exception:
            print(f"     {str(output)[:400]}")


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
        )
    )
