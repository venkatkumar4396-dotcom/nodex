"""
Pydantic schemas for AgentFlow Marketplace and Quality Gate.
"""
from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from agentflow.meta.schemas import (
    EvaluatorOutput,
    MarketplacePublisherOutput,
    SecurityRedTeamOutput,
)


class MarketplaceItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    name: str
    title: str
    tagline: str = ""
    description: str = ""
    version: str = "1.0.0"
    author: str = "AgentFlow Community"
    rating: float = Field(default=5.0, ge=1.0, le=5.0)
    rating_count: int = 1
    run_count: int = 0
    fork_count: int = 0
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    difficulty: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    cost_estimate: str = "< $0.02 / run"
    risk_level: Literal["low", "medium", "high"] = "low"
    safety_concerns: list[str] = Field(default_factory=list)
    external_actions: list[str] = Field(default_factory=list)
    credentials_needed: list[str] = Field(default_factory=list)
    inputs_schema: list[dict[str, Any]] = Field(default_factory=list)
    outputs_schema: list[dict[str, Any]] = Field(default_factory=list)
    sample_inputs: dict[str, Any] = Field(default_factory=dict)
    demo_video_url: str | None = None
    screenshots: list[str] = Field(default_factory=list)
    workflow: dict[str, Any] = Field(default_factory=dict)
    security_score: int = 95
    evaluation_score: float = 4.8
    created_at: str = "2026-10-09T00:00:00Z"
    updated_at: str = "2026-10-09T00:00:00Z"


class PublishGateRequest(BaseModel):
    workflow: dict[str, Any]
    sample_runs: list[dict[str, Any]] | None = None
    notes: str | None = None
    model: str | None = None


class PublishGateResult(BaseModel):
    passed: bool
    gate_stage: Literal["red_team", "evaluator", "publisher", "passed", "failed"]
    red_team_output: SecurityRedTeamOutput | None = None
    evaluator_output: EvaluatorOutput | None = None
    publisher_output: MarketplacePublisherOutput | None = None
    listing_item: MarketplaceItem | None = None
    reasons: list[str] = Field(default_factory=list)


class InstallTemplateRequest(BaseModel):
    template_id: str
    credentials: dict[str, str] = Field(default_factory=dict)
    target_name: str | None = None


class SandboxTestRequest(BaseModel):
    template_id: str
    sample_inputs: dict[str, Any] | None = None


class RateTemplateRequest(BaseModel):
    template_id: str
    rating: float = Field(ge=1.0, le=5.0)
    comment: str | None = None


class ForkTemplateRequest(BaseModel):
    template_id: str
    new_name: str | None = None
