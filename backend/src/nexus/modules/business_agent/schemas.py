"""Business agent request and response contracts."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PeriodInput(BaseModel):
    date_from: date
    date_to: date


class BusinessAgentRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    period_a: PeriodInput | None = None
    period_b: PeriodInput | None = None
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")


class AgentCitation(BaseModel):
    document_id: UUID
    document_name: str
    chunk_ordinal: int
    excerpt: str
    distance: float


class BusinessAgentResponse(BaseModel):
    run_id: UUID
    status: Literal["completed", "unsupported", "denied", "failed"]
    selected_tool: str | None
    answer: str
    citations: list[AgentCitation]
    transitions: list[str]
