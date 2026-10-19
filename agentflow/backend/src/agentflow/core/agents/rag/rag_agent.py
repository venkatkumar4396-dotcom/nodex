"""
RAG Agent — Retrieval-Augmented Generation agent.

Phase 6: Grounded Knowledge Retrieval & Citations.
The RAG agent searches internal knowledge documents or contextual data, extracts the most relevant excerpts, and generates factual answers with explicit citations.
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


class CitedPassage(BaseModel):
    source_title: str = Field(description="Name or identifier of source document")
    excerpt: str = Field(description="Direct relevant quote or excerpt")
    relevance_score: float = Field(ge=0.0, le=1.0, description="Relevance score of excerpt")


class RAGOutput(BaseModel):
    """Structured output from the RAG agent."""
    query: str = Field(description="Query that was investigated")
    answer: str = Field(description="Comprehensive answer strictly grounded in provided knowledge")
    cited_passages: list[CitedPassage] = Field(default_factory=list, description="Grounding source citations")
    confidence: float = Field(ge=0.0, le=1.0, default=0.9, description="Confidence score")
    key_entities: list[str] = Field(default_factory=list, description="Key concepts or entities identified")


class RAGAgent(BaseAgent):
    """
    RAG Agent: answers domain-specific queries using grounded knowledge context.

    Expected input fields:
      - query (str): question or search topic
      - knowledge_documents (list[str] or str, optional): document corpus or context
    """

    type_key: ClassVar[AgentType] = AgentType.RAG
    allowed_tools: ClassVar[set[str] | None] = {
        "vector_search", "web_search", "search", "document_parser", "scraper",
    }

    async def run(
        self,
        input_data: dict[str, Any],
        config: NodeConfig,
        context: RunContext,
        tools: list[BaseTool],
    ) -> AgentMessage:
        query = (
            input_data.get("query")
            or input_data.get("topic")
            or input_data.get("question")
            or "Retrieve grounded knowledge"
        )
        documents = (
            input_data.get("knowledge_documents")
            or input_data.get("documents")
            or input_data.get("context")
            or input_data.get("summary")
            or "Default corporate knowledge base & verified operational manuals."
        )

        system_prompt = config.system_prompt or (
            "You are a rigorous Retrieval-Augmented Generation (RAG) agent. "
            "Your answers must be grounded strictly in the provided document context. "
            "Never hallucinate facts. Always provide citations for assertions made."
        )

        user_content = (
            f"Query: {query}\n\n"
            f"Knowledge Corpus Context:\n{documents}\n\n"
            f"Additional Inputs:\n{input_data}\n\n"
            f"Please synthesize a grounded response with cited passages and relevance scores."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        parsed, llm_resp = await complete_structured(
            messages=messages,
            output_model=RAGOutput,
            model=config.model,
        )

        return AgentMessage(
            run_id=context.run.id,
            node_id=context.current_node_id or "rag",
            status=NodeRunStatus.COMPLETED,
            input_data=input_data,
            data=parsed.model_dump(),
            metadata=MessageMetadata(
                prompt_tokens=llm_resp.prompt_tokens,
                completion_tokens=llm_resp.completion_tokens,
                total_tokens=llm_resp.total_tokens,
                cost_usd=llm_resp.cost_usd,
                model=llm_resp.model,
            ),
        )
