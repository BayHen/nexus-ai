---
name: database-design
description: Design or change PostgreSQL schemas, SQLAlchemy mappings, Alembic migrations, indexes, constraints, transaction boundaries, or pgvector persistence.
metadata:
  short-description: Design safe database changes
---

# Database Design

Create durable data models and reversible migrations that preserve tenant isolation and transactional integrity.

## Responsibilities

- Model invariants with constraints and suitable data types, not application checks alone.
- Include tenant scope in ownership, uniqueness, foreign keys, indexes, and query plans where required.
- Separate ORM convenience from database truth.
- Plan backfills, locking, compatibility windows, rollback, and data-volume effects.

## Workflow

1. Inspect current models, migrations, data access patterns, and deployment assumptions.
2. Define invariants, relationships, tenant ownership, indexes, and migration strategy.
3. Implement mapping and migration as a coherent pair.
4. Test upgrade behavior and critical queries against PostgreSQL when available.
5. Review generated SQL, downgrade safety, and application compatibility.

## Acceptance criteria

- Constraints express material invariants and references preserve tenant ownership.
- Migration ordering and data transitions are deterministic.
- Indexes support demonstrated access patterns without redundant cost.
- Existing data and mixed-version deployment risks are addressed.
- Destructive changes have an explicit safe rollout or user authorization.

## Verification

Run migration upgrade on a disposable database, execute affected integration tests, and inspect schema or generated SQL. Test downgrade only when the project promises downgrade support; otherwise document the recovery strategy.
