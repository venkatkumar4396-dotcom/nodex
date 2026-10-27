"""
Human Approval Agent — pauses workflow execution for human-in-the-loop validation.

Phase 6: Interactive Governance & Oversight.
When execution reaches this node, it inspects context:
  - If approval has already been granted (via UI resume), it outputs the approved decision and reviewer notes.
  - If pending, it raises an AwaitingApprovalInterrupt or marks status as awaiting_approval so the runner pauses.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import structlog
from pydantic import BaseModel, Field

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


class ApprovalOutput(BaseModel):
    """Structured output from Human Approval node."""
    approved: bool = Field(description="True if approved by human reviewer, False if rejected")
    reviewer: str = Field(default="user", description="Identity or email of reviewer")
    notes: str = Field(default="", description="Reviewer comments or modifications")
    decision_timestamp: float = Field(default=0.0, description="Unix timestamp of decision")
    data_snapshot: dict[str, Any] = Field(default_factory=dict, description="Snapshot of reviewed data payload")


class HumanApprovalAgent(BaseAgent):
    """
    Human Approval Agent: gates downstream action nodes behind human review.

    Expected input fields:
      - Any upstream output payload to be reviewed
      - reviewer_instructions (optional): guidance for the human approver
    """

    type_key: ClassVar[AgentType] = AgentType.HUMAN_APPROVAL

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        node_id = context.current_node_id or "approval"
        approval_key = f"approval_{node_id}"
        stored_decision = context.get_shared(approval_key)

        log.info("human_approval_check", node_id=node_id, has_decision=stored_decision is not None)

        # If user has already approved or rejected via the API/UI
        if stored_decision is not None:
            is_approved = bool(stored_decision.get("approved", True))
            status = NodeRunStatus.COMPLETED if is_approved else NodeRunStatus.FAILED

            output = ApprovalOutput(
                approved=is_approved,
                reviewer=stored_decision.get("reviewer", "user"),
                notes=stored_decision.get("notes", ""),
                decision_timestamp=stored_decision.get("timestamp", 0.0),
                data_snapshot=input_data,
            )

            merged_data = dict(input_data)
            if isinstance(input_data.get("data_snapshot"), dict):
                merged_data.update(input_data["data_snapshot"])
            merged_data.update(output.model_dump())

            return AgentMessage(
                run_id=context.run.id,
                node_id=node_id,
                status=status,
                input_data=input_data,
                data=merged_data,
                metadata=MessageMetadata(
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    cost_usd=0.0,
                    model="human-in-the-loop",
                ),
                errors=[] if is_approved else [f"Rejected by reviewer: {output.notes}"],
            )

        # First pass — node awaits approval from user
        # Store pending request details in shared context
        pending_payload = {
            "node_id": node_id,
            "status": "awaiting_approval",
            "input": input_data,
            "prompt": config.system_prompt or "Review required before proceeding.",
        }
        context.set_shared(f"pending_approval_{node_id}", pending_payload)

        return AgentMessage(
            run_id=context.run.id,
            node_id=node_id,
            status=NodeRunStatus.AWAITING_APPROVAL,
            input_data=input_data,
            data=pending_payload,
            metadata=MessageMetadata(
                model="human-in-the-loop",
            ),
        )
