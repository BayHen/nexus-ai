---
name: ai-rag-engineering
description: Build or evaluate OpenAI integrations, document ingestion, embeddings, pgvector retrieval, RAG generation, prompts, structured output, and AI quality or safety checks.
metadata:
  short-description: Engineer AI and RAG systems
---

# AI and RAG Engineering

Create measurable, tenant-safe AI behavior with explicit model boundaries and fallbacks.

## Responsibilities

- Separate ingestion, chunking, embedding, retrieval, reranking, generation, and evaluation.
- Enforce tenant filters before vector ranking and preserve source provenance.
- Use structured outputs and validate model responses before side effects.
- Track model/config version, latency, token usage, quality, and failure modes.
- Treat retrieved content and user prompts as untrusted data.

## Workflow

1. Define the user outcome, quality metric, safety constraints, and cost/latency budget.
2. Inspect corpus, tenant ownership, current AI abstractions, and evaluation data.
3. Implement through provider ports with timeouts, retry limits, and deterministic validation.
4. Add representative evaluation cases, including injection and no-answer scenarios.
5. Compare results to a recorded baseline and document limitations.

## Acceptance criteria

- Retrieval cannot cross tenant boundaries.
- Answers expose reliable citations or explicitly decline when evidence is insufficient.
- Model output is validated before trusted use.
- Evaluation covers quality and safety risks relevant to the change.
- Secrets and sensitive prompt content are not logged.

## Verification

Run unit tests with deterministic fakes and integration/evaluation suites only when credentials and cost authorization are available. Record model/config, dataset version, metrics, and whether calls were mocked or live.
