---
name: api-design
description: Design or review REST API contracts, FastAPI routes, schemas, errors, pagination, versioning, idempotency, and OpenAPI behavior.
metadata:
  short-description: Design stable REST APIs
---

# API Design

Design REST contracts that are consistent, secure, evolvable, and aligned with application use cases.

## Responsibilities

- Model resources, commands, status codes, validation, errors, pagination, and filtering.
- Keep transport schemas separate from domain entities.
- Require authentication, authorization, tenant context, and idempotency where risk demands it.
- Protect backward compatibility and document intentional breaking changes.

## Workflow

1. Inspect existing routes, OpenAPI conventions, consumers, and application contracts.
2. Define request, response, error, authorization, and retry semantics before implementation.
3. Implement thin presentation adapters that call application use cases.
4. Add contract tests for success, validation, authorization, and conflict behavior.
5. Inspect generated OpenAPI and examples for consistency.

## Acceptance criteria

- Resource naming and HTTP semantics are coherent.
- Schemas reject invalid or ambiguous input.
- Error responses are stable and do not leak sensitive details.
- Tenant and permission checks cannot be bypassed through alternate routes.
- OpenAPI matches actual runtime behavior.

## Verification

Run API/contract tests and generate or inspect OpenAPI using repository tooling. Verify representative unauthorized, forbidden, not-found, conflict, and validation cases where applicable.
