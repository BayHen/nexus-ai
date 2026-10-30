---
name: feature-delivery
description: Deliver an end-to-end repository feature when a request spans implementation, tests, documentation, and handoff across one or more technical areas.
metadata:
  short-description: Coordinate complete feature delivery
---

# Feature Delivery

Coordinate a bounded feature from repository inspection through verified handoff. Use specialist project skills only when their domain materially applies.

## Responsibilities

- Establish scope, acceptance criteria, affected boundaries, dependencies, and explicit non-goals.
- Inspect existing code and preserve unrelated changes.
- Sequence the smallest coherent implementation across backend, frontend, data, tests, documentation, or infrastructure.
- Keep security, tenant isolation, transaction safety, compatibility, and rollback concerns visible.
- Produce an evidence-based completion report without expanding the user's authority.

## Workflow

1. Translate the request into observable outcomes and identify relevant specialist skills.
2. Inspect repository instructions, current state, and existing patterns before editing.
3. Implement in small coherent slices, updating tests and documentation with behavior.
4. Run proportionate verification and resolve failures caused by the change.
5. Report changed files, decisions, executed checks, limitations, and next readiness.

## Acceptance criteria

- The requested outcome is complete within the stated scope.
- Cross-layer contracts agree and unrelated behavior is preserved.
- Relevant tests and documentation accompany the change.
- Security and tenant boundaries are not bypassed.
- The handoff distinguishes verified facts from planned or unexecuted work.

## Verification

Run the narrowest relevant checks first, then broader affected suites when feasible. Record exact commands and outcomes. Never describe unexecuted checks as passing.
