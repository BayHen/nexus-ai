---
name: devops-cloud
description: Build or review Docker, GitHub Actions, Terraform, AWS infrastructure, deployment workflows, IAM, secrets, networking, and release automation.
metadata:
  short-description: Engineer delivery and AWS infrastructure
---

# DevOps and Cloud

Create repeatable, least-privilege delivery and infrastructure changes with safe review boundaries.

## Responsibilities

- Keep builds reproducible and runtime images minimal and non-root where feasible.
- Use Terraform for managed infrastructure and isolate environments and state.
- Apply least privilege to IAM, networking, credentials, and CI permissions.
- Separate validation/plan from apply; external deployment requires explicit authorization.
- Include rollback, backup, migration ordering, and secret rotation considerations.

## Workflow

1. Inspect existing deployment topology, environments, state ownership, and CI conventions.
2. Define desired change, blast radius, prerequisites, rollback, and cost implications.
3. Implement declarative configuration with pinned or constrained versions.
4. Run local validation, static checks, image builds, or Terraform plan as authorized.
5. Summarize plan effects and request approval before external apply or release actions.

## Acceptance criteria

- Configuration is environment-aware and contains no embedded secret.
- IAM and network exposure are no broader than required.
- CI jobs use explicit permissions and fail clearly.
- Stateful changes include backup and rollback considerations.
- Plans and deployments are not represented as equivalent.

## Verification

Run configured Docker, workflow, and Terraform validation tools. Review Terraform plan for replacements and destructive operations. Do not apply infrastructure, push images, or deploy without explicit user authorization.
