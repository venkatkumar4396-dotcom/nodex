"""
Supervisor Agent — meta-agent that coordinates subtasks, delegates work, and synthesizes results.

Phase 6: Multi-Agent Hierarchical Orchestration.
The Supervisor inspects the overarching goal and prior findings, breaks down requirements into discrete deliverables, evaluates whether objectives are met, and produces a unified strategic directive.
"""
from __future__ import annotations

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


class TaskPlanItem(BaseModel):
    task_id: str = Field(description="Unique task identifier, e.g. task_1")
    description: str = Field(description="Actionable task instruction")
    assigned_role: str = Field(description="Target role or agent type, e.g. researcher, writer")
    status: str = Field(default="pending", description="Task status: pending, completed, blocked")


class SupervisorOutput(BaseModel):
    """Structured output from the Supervisor agent."""
    goal: str = Field(description="Overarching goal being coordinated")
    plan: list[TaskPlanItem] = Field(description="Decomposed execution plan")
    synthesis: str = Field(description="Comprehensive synthesis of current stage and findings")
    is_complete: bool = Field(description="True if all sub-objectives are satisfied, False if further steps needed")
    next_action: str = Field(description="Clear next recommended action")
    confidence: float = Field(ge=0.0, le=1.0, default=0.9, description="Confidence in the execution plan")


class SupervisorAgent(BaseAgent):
    """
    Supervisor Agent: orchestrates multi-agent tasks and evaluates milestone completion.

    Expected input fields:
      - goal (str): overall objective
      - context_data (dict, optional): accumulated findings or prior outputs
    """

    type_key: ClassVar[AgentType] = AgentType.SUPERVISOR

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        goal = input_data.get("goal") or input_data.get("topic") or "Coordinate multi-agent execution"
        system_prompt = config.system_prompt or (
            "You are an executive AI Supervisor and Chief Orchestration Architect. "
            "Decompose high-level objectives into crisp sub-tasks, evaluate incoming data, "
            "and provide an authoritative synthesis with clear next actions."
        )

        user_content = (
            f"Overarching Goal: {goal}\n\n"
            f"Input Data & Prior Step Outputs:\n{input_data}\n\n"
            f"Please assess progress, formulate or update the task plan, synthesize key findings, "
            f"and determine if objectives are satisfied."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        parsed, llm_resp = await complete_structured(
            messages=messages,
            output_model=SupervisorOutput,
            model=config.model,
        )

        return AgentMessage(
            run_id=context.run.id,
            node_id=context.current_node_id or "supervisor",
            status=NodeRunStatus.COMPLETED,
            input_data=input_data,
            data={
                **{k: v for k, v in input_data.items() if not k.startswith("_")},
                **parsed.model_dump(),
            },
            metadata=MessageMetadata(
                prompt_tokens=llm_resp.prompt_tokens,
                completion_tokens=llm_resp.completion_tokens,
                total_tokens=llm_resp.total_tokens,
                cost_usd=llm_resp.cost_usd,
                model=llm_resp.model,
            ),
        )
