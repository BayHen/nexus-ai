---
name: security-review
description: Perform a focused application security review of authentication, authorization, tenant isolation, secrets, input handling, dependencies, AI tools, or infrastructure boundaries.
metadata:
  short-description: Review application security
---

# Security Review

Find actionable security defects using repository evidence. A review request authorizes inspection and reporting, not unrelated remediation or production changes.

## Responsibilities

- Trace trust boundaries, identities, tenant context, permissions, sensitive data, and external inputs.
- Prioritize exploitable findings over theoretical hardening suggestions.
- Review authentication/session behavior, injection risks, secret handling, SSRF, unsafe deserialization, and dependency exposure as relevant.
- Include AI prompt/tool authorization and MCP trust boundaries when present.

## Workflow

1. Establish review scope, assets, actors, and attacker-controlled inputs.
2. Trace critical paths from entry point to authorization, persistence, and side effects.
3. Validate suspected issues against code and tests; avoid findings based only on filenames or patterns.
4. Rank findings by impact, likelihood, and reachability with precise locations.
5. Recommend the smallest effective remediation and a regression test.

## Acceptance criteria

- Findings are reproducible or supported by a concrete code path.
- Severity and tenant impact are justified.
- False positives and uncertain assumptions are labeled.
- Sensitive values are not exposed in the report.
- No fix is claimed unless it was implemented and verified in scope.

## Verification

Use targeted tests or safe static analysis when configured. For each finding, verify preconditions and affected boundary. Never probe live systems or mutate external state without explicit authorization.
