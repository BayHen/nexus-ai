"""Framework-independent RAG contracts and values."""

from dataclasses import dataclass
from typing import Literal, Protocol

DocumentVisibility = Literal["organization", "private"]


class KnowledgeValidationError(ValueError):
    """Raised when an uploaded document is unsafe or unsupported."""


class KnowledgeNotFoundError(LookupError):
    """Raised when a document is not visible to the active actor."""


@dataclass(frozen=True)
class RetrievedEvidence:
    document_id: str
    document_name: str
    chunk_ordinal: int
    content: str
    distance: float


class EmbeddingProvider(Protocol):
    model_name: str

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class AnswerProvider(Protocol):
    model_name: str

    async def answer(self, question: str, evidence: list[RetrievedEvidence]) -> str: ...
