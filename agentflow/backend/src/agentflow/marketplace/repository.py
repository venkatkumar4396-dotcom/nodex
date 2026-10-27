"""
Repository for Marketplace workflows, ratings, run tracking, and template downloads.
Pre-populated with production-grade showcase workflows.
"""
from __future__ import annotations

import copy

from agentflow.marketplace.schemas import MarketplaceItem


class MarketplaceRepository:
    """In-memory repository with built-in templates."""

    def __init__(self) -> None:
        self._items: dict[str, MarketplaceItem] = {}
        self._seed_builtin_templates()

    def _seed_builtin_templates(self) -> None:
        t1 = MarketplaceItem(
            id="tpl-lead-outreach",
            name="Autonomous Lead Enrichment & Outreach",
            title="Lead Enrichment & Outreach with Approval Guard",
            tagline="Enrich inbound B2B prospects and generate verified personalized outreach",
            description=(
                "Listens for new leads, enriches domain intelligence using web search and company databases, "
                "synthesizes a tailored value proposition, and pauses for human approval before dispatching emails."
            ),
            version="1.2.0",
            author="AgentFlow Official",
            rating=4.9,
            rating_count=38,
            run_count=420,
            fork_count=87,
            categories=["Sales", "Marketing", "Productivity"],
            tags=["crm", "lead-gen", "human-in-the-loop", "email"],
            difficulty="beginner",
            cost_estimate="< $0.02 / run",
            risk_level="low",
            safety_concerns=["External email dispatch guarded by mandatory human approval node."],
            external_actions=["send_email"],
            credentials_needed=["EMAIL_API_KEY", "CRM_API_KEY"],
            inputs_schema=[
                {"name": "lead_name", "type": "string", "example": "Sarah Chen"},
                {"name": "company", "type": "string", "example": "Acme Corp"},
                {"name": "email", "type": "string", "example": "sarah@acme.com"},
            ],
            outputs_schema=[
                {"name": "research_summary", "type": "string"},
                {"name": "email_draft", "type": "string"},
                {"name": "dispatch_status", "type": "string"},
            ],
            sample_inputs={
                "lead_name": "Sarah Chen",
                "company": "Acme Corp",
                "email": "sarah@acme.com",
            },
            security_score=98,
            evaluation_score=4.9,
            workflow={
                "name": "Lead Enrichment & Outreach",
                "nodes": [
                    {
                        "id": "trigger_manual",
                        "type": "trigger_manual",
                        "label": "Manual / Webhook Trigger",
                        "position": {"x": 100, "y": 150},
                        "config": {"system_prompt": "Emit lead event"},
                    },
                    {
                        "id": "research_agent",
                        "type": "research",
                        "label": "Company Intelligence Agent",
                        "position": {"x": 420, "y": 150},
                        "config": {"model": "openrouter/free", "tools": ["duckduckgo_search"]},
                        "data_map": {"company": "{{trigger_manual.output.company}}"},
                    },
                    {
                        "id": "writer_agent",
                        "type": "writer",
                        "label": "Outreach Copywriter",
                        "position": {"x": 740, "y": 150},
                        "config": {"model": "openrouter/free"},
                        "data_map": {
                            "lead_name": "{{trigger_manual.output.lead_name}}",
                            "research": "{{research_agent.output.content}}",
                        },
                    },
                    {
                        "id": "human_signoff",
                        "type": "human_approval",
                        "label": "Executive Approval Sign-off",
                        "position": {"x": 1060, "y": 150},
                        "config": {"system_prompt": "Approve personalized email draft"},
                        "data_map": {"draft": "{{writer_agent.output.content}}"},
                    },
                    {
                        "id": "email_node",
                        "type": "email",
                        "label": "SMTP / SendGrid Dispatcher",
                        "position": {"x": 1380, "y": 150},
                        "config": {"model": "openrouter/free"},
                        "data_map": {"approved_body": "{{human_signoff.output.draft}}"},
                    },
                ],
                "edges": [
                    {"from": "trigger_manual", "to": "research_agent"},
                    {"from": "research_agent", "to": "writer_agent"},
                    {"from": "writer_agent", "to": "human_signoff"},
                    {"from": "human_signoff", "to": "email_node"},
                ],
            },
        )

        t2 = MarketplaceItem(
            id="tpl-competitor-monitor",
            name="Competitor Price & Stock Monitor",
            title="Competitor Intelligence & Price Change Alert",
            tagline="Track product availability and price fluctuations across e-commerce sites",
            description=(
                "Regularly scrapes product pages, parses pricing structures and discounts, "
                "evaluates delta thresholds, and notifies Slack or Email when competitive prices drop."
            ),
            version="1.0.4",
            author="DataFlow Labs",
            rating=4.8,
            rating_count=24,
            run_count=980,
            fork_count=112,
            categories=["E-commerce", "Analytics", "Monitoring"],
            tags=["scraping", "monitoring", "pricing", "alerts"],
            difficulty="intermediate",
            cost_estimate="< $0.01 / run",
            risk_level="low",
            safety_concerns=["Read-only web scraping of public pricing pages."],
            external_actions=["messaging"],
            credentials_needed=["SLACK_WEBHOOK_URL"],
            inputs_schema=[
                {"name": "competitor_url", "type": "string", "example": "https://store.example.com/item"},
                {"name": "alert_threshold", "type": "number", "example": 50.0},
            ],
            outputs_schema=[
                {"name": "current_price", "type": "number"},
                {"name": "price_change_detected", "type": "boolean"},
            ],
            sample_inputs={
                "competitor_url": "https://store.example.com/item",
                "alert_threshold": 50.0,
            },
            security_score=96,
            evaluation_score=4.85,
            workflow={
                "name": "Competitor Price Monitor",
                "nodes": [
                    {
                        "id": "trigger_cron",
                        "type": "trigger_cron",
                        "label": "Hourly Schedule Trigger",
                        "position": {"x": 100, "y": 150},
                        "config": {"system_prompt": "Trigger hourly scan"},
                    },
                    {
                        "id": "scraper_node",
                        "type": "scraper",
                        "label": "HTML Product Scraper",
                        "position": {"x": 420, "y": 150},
                        "config": {"tools": ["fetch_url"]},
                    },
                    {
                        "id": "analyst_agent",
                        "type": "data_analyst",
                        "label": "Price Delta Analyst",
                        "position": {"x": 740, "y": 150},
                        "config": {"model": "openrouter/free"},
                    },
                    {
                        "id": "slack_alert",
                        "type": "messaging",
                        "label": "Slack Ops Notification",
                        "position": {"x": 1060, "y": 150},
                        "config": {"model": "openrouter/free"},
                    },
                ],
                "edges": [
                    {"from": "trigger_cron", "to": "scraper_node"},
                    {"from": "scraper_node", "to": "analyst_agent"},
                    {"from": "analyst_agent", "to": "slack_alert"},
                ],
            },
        )

        t3 = MarketplaceItem(
            id="tpl-github-reviewer",
            name="GitHub PR Reviewer & Automated Bug Triage",
            title="GitHub Pull Request Reviewer & Security Auditing",
            tagline="Deep automated code reviews, test suggestions, and vulnerability red-teaming for PRs",
            description=(
                "Receives GitHub webhook events on new PRs, diffs modified files, runs AST code analysis "
                "and security heuristics, and posts constructive line-by-line review comments."
            ),
            version="2.0.1",
            author="DevSecOps Collective",
            rating=4.95,
            rating_count=52,
            run_count=1340,
            fork_count=215,
            categories=["Engineering", "DevOps", "Security"],
            tags=["github", "code-review", "security", "ci-cd"],
            difficulty="advanced",
            cost_estimate="< $0.04 / run",
            risk_level="medium",
            safety_concerns=["Writes GitHub comments; requires repository write permissions."],
            external_actions=["github_ops"],
            credentials_needed=["GITHUB_TOKEN"],
            inputs_schema=[
                {"name": "repo", "type": "string", "example": "org/repo"},
                {"name": "pull_request_number", "type": "integer", "example": 42},
            ],
            outputs_schema=[
                {"name": "review_verdict", "type": "string"},
                {"name": "findings_count", "type": "integer"},
            ],
            sample_inputs={"repo": "acme/backend", "pull_request_number": 42},
            security_score=92,
            evaluation_score=4.92,
            workflow={
                "name": "GitHub PR Reviewer",
                "nodes": [
                    {
                        "id": "trigger_webhook",
                        "type": "trigger_webhook",
                        "label": "GitHub Webhook Receiver",
                        "position": {"x": 100, "y": 150},
                        "config": {"system_prompt": "Listen for pull_request.opened"},
                    },
                    {
                        "id": "code_auditor",
                        "type": "code",
                        "label": "Syntax & Diff Auditor",
                        "position": {"x": 420, "y": 150},
                        "config": {"model": "openrouter/free"},
                    },
                    {
                        "id": "security_scanner",
                        "type": "guardrail",
                        "label": "Security Guardrail Scanner",
                        "position": {"x": 740, "y": 150},
                        "config": {"model": "openrouter/free"},
                    },
                    {
                        "id": "gh_commenter",
                        "type": "github_ops",
                        "label": "GitHub Review Commenter",
                        "position": {"x": 1060, "y": 150},
                        "config": {"model": "openrouter/free"},
                    },
                ],
                "edges": [
                    {"from": "trigger_webhook", "to": "code_auditor"},
                    {"from": "code_auditor", "to": "security_scanner"},
                    {"from": "security_scanner", "to": "gh_commenter"},
                ],
            },
        )

        t4 = MarketplaceItem(
            id="tpl-browser-operator-scraper",
            name="Autonomous Browser Web Navigator",
            title="Browser Operator for Non-API Websites",
            tagline="Autonomous website navigation, form submission, and visual data extraction without APIs",
            description=(
                "Uses Browser Operator agent with domain allowlists and step limit controls to navigate complex "
                "dynamic JavaScript websites, search catalogs, and extract structured data tables directly."
            ),
            version="1.0.0",
            author="AgentFlow Core",
            rating=5.0,
            rating_count=19,
            run_count=310,
            fork_count=64,
            categories=["Autonomous", "Browser", "Extraction"],
            tags=["browser", "playwright", "no-api", "automation"],
            difficulty="intermediate",
            cost_estimate="< $0.03 / run",
            risk_level="low",
            safety_concerns=["Restricted to domain allowlist with maximum 15 step cap."],
            external_actions=["browser_operator"],
            credentials_needed=[],
            inputs_schema=[
                {"name": "task", "type": "string", "example": "Search for AI models on HuggingFace"},
                {"name": "start_url", "type": "string", "example": "https://huggingface.co"},
                {"name": "allowed_domains", "type": "list", "example": ["huggingface.co"]},
            ],
            outputs_schema=[
                {"name": "extracted_data", "type": "object"},
                {"name": "steps_taken", "type": "integer"},
            ],
            sample_inputs={
                "task": "Find top trending models",
                "start_url": "https://huggingface.co",
                "allowed_domains": ["huggingface.co"],
            },
            security_score=95,
            evaluation_score=4.9,
            workflow={
                "name": "Browser Operator Search",
                "nodes": [
                    {
                        "id": "trigger_manual",
                        "type": "trigger_manual",
                        "label": "User Query Trigger",
                        "position": {"x": 100, "y": 150},
                        "config": {"system_prompt": "Emit user navigation task"},
                    },
                    {
                        "id": "browser_operator_node",
                        "type": "browser_operator",
                        "label": "Browser Operator Agent",
                        "position": {"x": 450, "y": 150},
                        "config": {
                            "model": "openrouter/free",
                            "system_prompt": "Navigate website, inspect elements, and extract structured fields.",
                        },
                    },
                    {
                        "id": "synthesizer_node",
                        "type": "synthesizer",
                        "label": "Structured Report Synthesizer",
                        "position": {"x": 800, "y": 150},
                        "config": {"model": "openrouter/free"},
                    },
                ],
                "edges": [
                    {"from": "trigger_manual", "to": "browser_operator_node"},
                    {"from": "browser_operator_node", "to": "synthesizer_node"},
                ],
            },
        )

        for t in [t1, t2, t3, t4]:
            self._items[t.id] = t

    def list_templates(
        self,
        search: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        risk_level: str | None = None,
    ) -> list[MarketplaceItem]:
        items = list(self._items.values())
        if search:
            s = search.lower()
            items = [
                i for i in items
                if s in i.title.lower() or s in i.description.lower() or s in i.tagline.lower() or any(s in t.lower() for t in i.tags)
            ]
        if category and category != "All":
            items = [i for i in items if category.lower() in [c.lower() for c in i.categories]]
        if tag:
            items = [i for i in items if tag.lower() in [t.lower() for t in i.tags]]
        if risk_level and risk_level != "All":
            items = [i for i in items if i.risk_level.lower() == risk_level.lower()]
        return items

    def get_template(self, template_id: str) -> MarketplaceItem | None:
        return self._items.get(template_id)

    def save_template(self, item: MarketplaceItem) -> MarketplaceItem:
        self._items[item.id] = item
        return item

    def record_install(self, template_id: str) -> int:
        item = self._items.get(template_id)
        if item:
            item.run_count += 1
            return item.run_count
        return 0

    def record_fork(self, template_id: str) -> MarketplaceItem | None:
        item = self._items.get(template_id)
        if not item:
            return None
        item.fork_count += 1
        forked = copy.deepcopy(item)
        forked.id = f"fork-{item.id[:6]}-{item.fork_count}"
        forked.title = f"{item.title} (Remix)"
        forked.author = "You (Remixed)"
        forked.version = "1.0.0-remix"
        forked.run_count = 0
        forked.fork_count = 0
        self._items[forked.id] = forked
        return forked

    def record_rating(self, template_id: str, rating: float) -> float:
        item = self._items.get(template_id)
        if not item:
            return 0.0
        new_total = (item.rating * item.rating_count) + rating
        item.rating_count += 1
        item.rating = round(new_total / item.rating_count, 2)
        return item.rating


marketplace_repo = MarketplaceRepository()
