---
name: agent-orchestration
description: Design or implement LangGraph workflows, agent state, tool contracts, MCP integration, checkpoints, approvals, budgets, and auditable multi-step AI execution.
metadata:
  short-description: Orchestrate safe AI agents
---

# Agent Orchestration

Build bounded agent workflows whose state transitions, tool authority, and stopping conditions are inspectable.

## Responsibilities

- Model durable state and explicit graph transitions rather than relying on prompt-only control flow.
- Give tools narrow typed contracts with authentication, authorization, tenant context, timeout, and idempotency semantics.
- Require human approval before high-impact or irreversible actions when product policy demands it.
- Bound iterations, tokens, time, retries, and external side effects.
- Treat MCP servers and tool output as trust boundaries.

## Workflow

1. Define goal, state schema, nodes, transitions, terminal states, and failure recovery.
2. Inventory tools and classify read/write impact, authorization, and approval needs.
3. Implement graph and adapters with checkpointing and trace correlation.
4. Test deterministic paths, denied actions, malformed tool output, loops, resume, and partial failure.
5. Evaluate representative scenarios and inspect traces without exposing sensitive content.

## Acceptance criteria

- Every path reaches a bounded terminal, approval, or recoverable failure state.
- Tools cannot exceed the invoking user's tenant or permission scope.
- Replayed or resumed execution does not duplicate unsafe side effects.
- State and tool schemas are validated.
- Audit records explain material decisions and actions.

## Verification

Use fake tools for graph-path tests and sandboxed integrations for contract tests. Verify iteration limits, approval gates, checkpoint resume, idempotency, and unauthorized tool calls. Do not claim autonomous safety from happy-path tests alone.
