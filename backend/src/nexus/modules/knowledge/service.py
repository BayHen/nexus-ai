"""Safe document ingestion, chunking, tenant retrieval, and grounded answering."""

import asyncio
import hashlib
import re
from io import BytesIO
from pathlib import PurePath
from typing import cast
from uuid import UUID

from pypdf import PdfReader
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from nexus.modules.knowledge.domain import (
    AnswerProvider,
    DocumentVisibility,
    EmbeddingProvider,
    KnowledgeNotFoundError,
    KnowledgeValidationError,
    RetrievedEvidence,
)
from nexus.modules.knowledge.models import KnowledgeChunk, KnowledgeDocument
from nexus.modules.organizations.domain import MembershipRole

ALLOWED_FILES = {
    ".pdf": {"application/pdf"},
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
    ".markdown": {"text/markdown", "text/plain"},
}
MAX_PDF_PAGES = 200
MAX_EXTRACTED_CHARACTERS = 2_000_000
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
UNSUPPORTED_ANSWER = "Không đủ bằng chứng trong kho tri thức để trả lời câu hỏi này."


def safe_filename(filename: str) -> str:
    name = PurePath(filename.replace("\\", "/")).name.strip()
    if not name or len(name) > 255:
        raise KnowledgeValidationError("invalid_filename")
    return name


def extract_text(filename: str, media_type: str, content: bytes) -> str:
    extension = PurePath(filename).suffix.lower()
    if extension not in ALLOWED_FILES or media_type not in ALLOWED_FILES[extension]:
        raise KnowledgeValidationError("unsupported_file_type")
    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise KnowledgeValidationError("invalid_pdf_signature")
        try:
            reader = PdfReader(BytesIO(content), strict=False)
            if len(reader.pages) > MAX_PDF_PAGES:
                raise KnowledgeValidationError("pdf_page_limit_exceeded")
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        except KnowledgeValidationError:
            raise
        except Exception as exc:
            raise KnowledgeValidationError("pdf_extraction_failed") from exc
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise KnowledgeValidationError("text_must_be_utf8") from exc
    text = text.replace("\x00", "").strip()
    if not text:
        raise KnowledgeValidationError("document_has_no_text")
    if len(text) > MAX_EXTRACTED_CHARACTERS:
        raise KnowledgeValidationError("extracted_text_limit_exceeded")
    return text


def split_text(text: str) -> list[str]:
    normalized = re.sub(r"[ \t]+", " ", text)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + CHUNK_SIZE, len(normalized))
        if end < len(normalized):
            boundary = max(normalized.rfind("\n\n", start, end), normalized.rfind(". ", start, end))
            if boundary > start + CHUNK_SIZE // 2:
                end = boundary + 1
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


class KnowledgeService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider,
        answer_provider: AnswerProvider,
    ) -> None:
        self._session = session
        self._embedding_provider = embedding_provider
        self._answer_provider = answer_provider

    async def ingest(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        filename: str,
        media_type: str,
        content: bytes,
        visibility: DocumentVisibility,
    ) -> KnowledgeDocument:
        filename = safe_filename(filename)
        text = await asyncio.to_thread(extract_text, filename, media_type, content)
        chunks = split_text(text)
        embeddings = await self._embedding_provider.embed(chunks)
        if len(embeddings) != len(chunks):
            raise RuntimeError("embedding_count_mismatch")
        document = KnowledgeDocument(
            organization_id=organization_id,
            uploaded_by_user_id=user_id,
            filename=filename,
            media_type=media_type,
            file_size=len(content),
            content_sha256=hashlib.sha256(content).hexdigest(),
            visibility=visibility,
            status="ready",
            chunk_count=len(chunks),
            embedding_model=self._embedding_provider.model_name,
        )
        self._session.add(document)
        await self._session.flush()
        self._session.add_all(
            KnowledgeChunk(
                organization_id=organization_id,
                document_id=document.id,
                ordinal=ordinal,
                content=chunk,
                character_count=len(chunk),
                embedding=embedding,
            )
            for ordinal, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True))
        )
        await self._session.flush()
        return document

    async def list_documents(
        self, organization_id: UUID, user_id: UUID, role: MembershipRole
    ) -> list[KnowledgeDocument]:
        return list(
            await self._session.scalars(
                select(KnowledgeDocument)
                .where(self._document_acl(organization_id, user_id, role))
                .order_by(KnowledgeDocument.created_at.desc(), KnowledgeDocument.id)
            )
        )

    async def delete_document(
        self, document_id: UUID, organization_id: UUID, user_id: UUID, role: MembershipRole
    ) -> None:
        conditions = [
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.organization_id == organization_id,
        ]
        if role not in {"owner", "admin"}:
            conditions.append(KnowledgeDocument.uploaded_by_user_id == user_id)
        deleted_id = await self._session.scalar(
            delete(KnowledgeDocument)
            .where(*conditions)
            .returning(KnowledgeDocument.id)
        )
        if deleted_id is None:
            raise KnowledgeNotFoundError(str(document_id))

    async def retrieve(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
        query: str,
        limit: int,
        distance_threshold: float,
    ) -> list[RetrievedEvidence]:
        vectors = await self._embedding_provider.embed([query])
        distance = KnowledgeChunk.embedding.cosine_distance(vectors[0]).label("distance")
        rows = (
            await self._session.execute(
                select(KnowledgeChunk, KnowledgeDocument, distance)
                .join(
                    KnowledgeDocument,
                    and_(
                        KnowledgeDocument.organization_id == KnowledgeChunk.organization_id,
                        KnowledgeDocument.id == KnowledgeChunk.document_id,
                    ),
                )
                .where(
                    self._document_acl(organization_id, user_id, role),
                    distance <= distance_threshold,
                )
                .order_by(distance, KnowledgeChunk.id)
                .limit(limit)
            )
        ).all()
        typed_rows = cast(
            list[tuple[KnowledgeChunk, KnowledgeDocument, float]], rows
        )
        return [
            RetrievedEvidence(
                document_id=str(document.id),
                document_name=document.filename,
                chunk_ordinal=chunk.ordinal,
                content=chunk.content,
                distance=float(score),
            )
            for chunk, document, score in typed_rows
        ]

    async def answer(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
        question: str,
        limit: int,
        distance_threshold: float,
    ) -> tuple[str, list[RetrievedEvidence], bool]:
        evidence = await self.retrieve(
            organization_id=organization_id,
            user_id=user_id,
            role=role,
            query=question,
            limit=limit,
            distance_threshold=distance_threshold,
        )
        if not evidence:
            return UNSUPPORTED_ANSWER, [], False
        answer = (await self._answer_provider.answer(question, evidence)).strip()
        if not answer:
            return UNSUPPORTED_ANSWER, [], False
        return answer, evidence, True

    @staticmethod
    def _document_acl(
        organization_id: UUID, user_id: UUID, role: MembershipRole
    ) -> ColumnElement[bool]:
        visibility = KnowledgeDocument.visibility == "organization"
        if role in {"owner", "admin"}:
            visibility = or_(visibility, KnowledgeDocument.visibility == "private")
        else:
            visibility = or_(visibility, KnowledgeDocument.uploaded_by_user_id == user_id)
        return and_(KnowledgeDocument.organization_id == organization_id, visibility)
