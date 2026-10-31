"""Knowledge base API schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeDocumentResponse(BaseModel):
    id: UUID
    filename: str
    media_type: str
    file_size: int
    visibility: Literal["organization", "private"]
    status: Literal["ready", "failed"]
    chunk_count: int
    embedding_model: str
    created_at: datetime


class KnowledgeQuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class KnowledgeCitation(BaseModel):
    document_id: UUID
    document_name: str
    chunk_ordinal: int
    excerpt: str
    distance: float


class KnowledgeAnswerResponse(BaseModel):
    answer: str
    supported: bool
    citations: list[KnowledgeCitation]
