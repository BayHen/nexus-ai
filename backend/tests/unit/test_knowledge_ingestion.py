"""Safe extraction, chunking, and deterministic embedding tests."""

import json
from pathlib import Path

import pytest

from nexus.modules.knowledge.domain import KnowledgeValidationError, RetrievedEvidence
from nexus.modules.knowledge.providers import DeterministicAIProvider
from nexus.modules.knowledge.service import CHUNK_SIZE, extract_text, safe_filename, split_text

pytestmark = pytest.mark.anyio


def test_text_markdown_extraction_and_safe_filename() -> None:
    assert safe_filename("../../handbook.md") == "handbook.md"
    assert extract_text("notes.txt", "text/plain", b"Tenant safe notes") == "Tenant safe notes"
    assert extract_text("guide.md", "text/markdown", b"# Guide") == "# Guide"


def test_invalid_type_encoding_signature_and_empty_content_are_rejected() -> None:
    cases = [
        ("malware.exe", "application/octet-stream", b"unsafe", "unsupported_file_type"),
        ("fake.pdf", "application/pdf", b"not-pdf", "invalid_pdf_signature"),
        ("bad.txt", "text/plain", b"\xff", "text_must_be_utf8"),
        ("empty.md", "text/markdown", b"   ", "document_has_no_text"),
    ]
    for filename, media_type, content, code in cases:
        with pytest.raises(KnowledgeValidationError, match=code):
            extract_text(filename, media_type, content)


def test_chunking_is_bounded_and_overlapping() -> None:
    text = " ".join(f"word-{index}" for index in range(600))
    chunks = split_text(text)
    assert len(chunks) > 1
    assert all(len(chunk) <= CHUNK_SIZE for chunk in chunks)
    assert set(chunks[0].split()[-10:]).intersection(chunks[1].split()[:30])


async def test_deterministic_embeddings_reward_shared_terms() -> None:
    provider = DeterministicAIProvider()
    vectors = await provider.embed(
        ["refund policy orange", "refund policy", "warehouse inventory blue"]
    )

    def dot(left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right, strict=True))

    assert dot(vectors[0], vectors[1]) > dot(vectors[0], vectors[2])


async def test_retrieval_evaluation_dataset_local_baseline() -> None:
    dataset_path = Path(__file__).parents[1] / "evaluation" / "knowledge_retrieval.json"
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    provider = DeterministicAIProvider()
    passed = 0
    for case in cases:
        document_vector, question_vector = await provider.embed(
            [case["document"], case["question"]]
        )
        similarity = sum(
            left * right
            for left, right in zip(document_vector, question_vector, strict=True)
        )
        supported = similarity >= 0.40
        assert supported is case["supported"], case["id"]
        if supported:
            answer = await provider.answer(
                case["question"],
                [
                    RetrievedEvidence(
                        document_id="00000000-0000-0000-0000-000000000001",
                        document_name="evaluation.txt",
                        chunk_ordinal=0,
                        content=case["document"],
                        distance=1 - similarity,
                    )
                ],
            )
            assert case["expected_keyword"] in answer
        passed += 1
    assert passed == 3
