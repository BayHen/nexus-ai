"""Authenticated API for the bounded business intelligence agent."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.bootstrap.config import Settings
from nexus.modules.auth.dependencies import get_transaction
from nexus.modules.business_agent.graph import BusinessAgent
from nexus.modules.business_agent.models import AgentRun
from nexus.modules.business_agent.schemas import (
    AgentCitation,
    BusinessAgentRequest,
    BusinessAgentResponse,
)
from nexus.modules.business_agent.tools import BusinessTools
from nexus.modules.knowledge.domain import AnswerProvider, EmbeddingProvider
from nexus.modules.knowledge.service import KnowledgeService
from nexus.modules.organizations.dependencies import TenantContextDependency

router = APIRouter(prefix="/agent", tags=["business-agent"])
SessionDependency = Annotated[AsyncSession, Depends(get_transaction)]


@router.post("/ask", response_model=BusinessAgentResponse)
async def ask_business_agent(
    body: BusinessAgentRequest,
    request: Request,
    session: SessionDependency,
    context: TenantContextDependency,
) -> BusinessAgentResponse:
    settings = cast(Settings, request.app.state.settings)
    run = AgentRun(
        organization_id=context.organization_id,
        user_id=context.user_id,
        status="running",
        correlation_id=request.state.request_id,
    )
    session.add(run)
    await session.flush()
    knowledge = KnowledgeService(
        session,
        cast(EmbeddingProvider, request.app.state.knowledge_embedding_provider),
        cast(AnswerProvider, request.app.state.knowledge_answer_provider),
    )
    tools = BusinessTools(
        session,
        context,
        knowledge,
        run_id=run.id,
        correlation_id=request.state.request_id,
        timeout_seconds=settings.agent_tool_timeout_seconds,
        retrieval_limit=settings.knowledge_retrieval_limit,
        distance_threshold=settings.knowledge_distance_threshold,
    )
    result = await BusinessAgent(session, context, tools, run, body).run()
    return BusinessAgentResponse(
        run_id=run.id,
        status=result["status"],
        selected_tool=result["selected_tool"],
        answer=result["answer"],
        citations=[AgentCitation.model_validate(item) for item in result["citations"]],
        transitions=result["transitions"],
    )
