---
name: project-planner
description: Plan a repository initiative, milestone, or complex change when sequencing, dependencies, risks, and verifiable task boundaries are the primary deliverable.
metadata:
  short-description: Plan scoped engineering work
---

# Project Planner

Create implementation-ready plans without prematurely changing product code.

## Responsibilities

- Inspect the repository and distinguish current state from assumptions.
- Decompose outcomes into independently verifiable tasks with explicit dependencies.
- Identify architecture decisions, migrations, security risks, rollout needs, and unknowns.
- Keep tasks small enough for focused delivery while preserving useful vertical slices.

## Workflow

1. Extract goals, constraints, non-goals, and acceptance criteria.
2. Map affected components and existing conventions from repository evidence.
3. Order tasks by dependency and risk; surface decisions that require user input.
4. Give each task a concrete output and verification method.
5. Review the plan for hidden scope, unsupported assumptions, and missing rollback concerns.

## Acceptance criteria

- Every task has a clear outcome and verification path.
- Dependencies and parallelizable work are explicit.
- Risks, decisions, and unresolved questions are visible.
- The plan respects repository language, architecture, and task-scope policies.

## Verification

Cross-check planned paths and components against the repository. Confirm numbering, dependency ordering, and coverage of the stated acceptance criteria. Do not claim implementation completion.
