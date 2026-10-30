---
name: observability
description: Design or implement structured logging, metrics, tracing, health checks, dashboards, alerts, SLOs, and operational diagnostics across API, workers, queues, databases, and AI calls.
metadata:
  short-description: Engineer observable systems
---

# Observability

Make system behavior diagnosable while controlling noise, cardinality, privacy, and operational cost.

## Responsibilities

- Correlate requests, jobs, events, and AI calls across boundaries.
- Define signals from user-visible failure modes and service objectives.
- Avoid secrets, raw tokens, unnecessary prompt content, and unsafe tenant data in telemetry.
- Distinguish liveness, readiness, dependency health, and business health.
- Keep metric labels bounded and alerts actionable.

## Workflow

1. Identify the operational question or failure mode the signal must answer.
2. Inspect existing telemetry conventions, exporters, retention, and dashboards.
3. Add the minimum structured signal and propagate correlation context.
4. Test normal, degraded, and failure paths; inspect emitted attributes.
5. Document interpretation, alert threshold rationale, and runbook link where applicable.

## Acceptance criteria

- Signals answer a defined operational question.
- Correlation works across affected asynchronous and synchronous boundaries.
- Sensitive information and unbounded-cardinality labels are excluded.
- Health endpoints reflect their stated semantics.
- Alerts identify an owner or actionable response.

## Verification

Run telemetry tests or a local collector when configured. Trigger representative success and failure paths, inspect output, and confirm redaction and cardinality behavior. State when dashboards or alerts were only validated statically.
