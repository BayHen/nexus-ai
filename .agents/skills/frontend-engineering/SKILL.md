---
name: frontend-engineering
description: Build or modify the Next.js, React, and TypeScript frontend, including accessible UI, typed API integration, state handling, and component or Playwright tests.
metadata:
  short-description: Engineer the web frontend
---

# Frontend Engineering

Implement accessible, resilient frontend behavior that respects backend contracts and tenant permissions.

## Responsibilities

- Use semantic HTML, keyboard support, responsive layouts, and perceivable state changes.
- Keep server/client boundaries intentional and API contracts typed.
- Handle loading, empty, error, unauthorized, and stale states.
- Avoid treating hidden UI as authorization; backend enforcement remains authoritative.
- Reuse the project design system before adding new primitives.

## Workflow

1. Inspect routes, component patterns, design tokens, API clients, and test setup.
2. Define user flow and all meaningful states before composing components.
3. Implement the smallest accessible feature with typed data boundaries.
4. Add component or E2E coverage for critical interactions.
5. Run type checking, linting, tests, and production build when configured.

## Acceptance criteria

- The feature works across intended viewport and input modes.
- Loading, empty, error, and permission states are explicit.
- TypeScript does not rely on unjustified casts or suppressed errors.
- Accessible names, focus behavior, and form errors are usable.
- No secret or privileged decision is placed in client code.

## Verification

Run configured lint, type-check, component tests, and relevant Playwright flows. Use a production build for changes affecting routing, rendering mode, or bundling. Report any visual checks as manual unless automated evidence exists.
