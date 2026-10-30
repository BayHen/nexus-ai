---
name: test-engineering
description: Design, implement, debug, or review automated tests with pytest or Playwright, including unit, integration, contract, security, and end-to-end coverage.
metadata:
  short-description: Engineer reliable automated tests
---

# Test Engineering

Build tests that provide stable evidence about behavior rather than mirror implementation details.

## Responsibilities

- Select the cheapest test level that proves the risk under review.
- Cover observable success, failure, authorization, tenant isolation, transaction, and concurrency behavior as relevant.
- Keep fixtures explicit, deterministic, isolated, and easy to understand.
- Diagnose flaky tests instead of masking them with unconditional retries or sleeps.

## Workflow

1. Identify the behavior, regression risk, and most informative boundary.
2. Inspect existing fixtures, factories, markers, and execution conventions.
3. Add focused tests with meaningful assertions and controlled dependencies.
4. Run the narrow test repeatedly when flakiness is plausible, then the affected suite.
5. Report failures caused by environment or missing services separately from product defects.

## Acceptance criteria

- Tests fail for the intended defect and pass for the intended behavior.
- Assertions validate outcomes, not incidental call sequences unless the interaction is the contract.
- Tenant and state isolation prevent cross-test leakage.
- Time, randomness, network, and concurrency are controlled appropriately.
- Test names communicate scenario and expected result.

## Verification

Run the exact new or changed tests and the nearest relevant suite. For Playwright, retain useful traces/screenshots only according to project policy. State skipped, deselected, or unavailable tests explicitly.
