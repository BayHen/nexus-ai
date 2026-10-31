"""Deterministic retrieval-quality baseline for the Task 22 evaluation dataset."""

import json
from pathlib import Path

import pytest

from nexus.modules.knowledge.domain import RetrievedEvidence
from nexus.modules.knowledge.providers import DeterministicAIProvider

pytestmark = pytest.mark.anyio


async def test_task22_retrieval_quality_baseline() -> None:
    dataset = json.loads(
        (Path(__file__).parents[1] / "evaluation" / "mcp_ai_evaluation.json").read_text(
            encoding="utf-8"
        )
    )
    provider = DeterministicAIProvider()
    passed = 0
    for case in dataset["retrieval_cases"]:
        evidence_vector, question_vector = await provider.embed(
            [case["evidence"], case["question"]]
        )
        similarity = sum(
            left * right for left, right in zip(evidence_vector, question_vector, strict=True)
        )
        supported = similarity >= 0.40
        assert supported is case["expected_supported"]
        if supported:
            answer = await provider.answer(
                case["question"],
                [
                    RetrievedEvidence(
                        document_id="00000000-0000-0000-0000-000000000001",
                        document_name="task22-evaluation.txt",
                        chunk_ordinal=0,
                        content=case["evidence"],
                        distance=1 - similarity,
                    )
                ],
            )
            assert case["expected_token"] in answer
        passed += 1
    assert passed == 3
