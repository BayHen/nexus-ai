---
name: python-backend
description: Build or modify Python backend code for FastAPI services, application use cases, domain logic, adapters, background jobs, and typed configuration.
metadata:
  short-description: Engineer the Python backend
---

# Python Backend

Implement maintainable Python backend behavior within the modular-monolith boundaries.

## Responsibilities

- Keep domain and application code independent from FastAPI, SQLAlchemy, and external clients.
- Use explicit types, dependency injection, clear transaction ownership, and structured errors.
- Preserve async correctness and avoid blocking I/O on async paths.
- Keep tenant context and authorization explicit at application boundaries.
- Add dependencies only when their value exceeds their maintenance cost.

## Workflow

1. Inspect package configuration, module boundaries, conventions, and relevant tests.
2. Place behavior in the owning layer and define ports before adapters when appropriate.
3. Implement the smallest coherent change, including error and cancellation paths.
4. Add unit or integration coverage at the boundary where behavior is observable.
5. Run formatter, linter, type checker, and affected tests when configured.

## Acceptance criteria

- Dependency direction follows Clean Architecture.
- Public behavior and errors are typed and predictable.
- Tenant, transaction, and authorization boundaries remain enforceable.
- Tests cover success and material failure paths.
- No secret or environment-specific value is embedded in code.

## Verification

Use the repository's configured Python commands. At minimum run affected tests; when configured, also run formatting checks, linting, type checking, and import/application startup checks. Report unavailable tooling explicitly.
