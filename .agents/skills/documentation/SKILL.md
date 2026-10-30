---
name: documentation
description: Create or update repository documentation, architecture records, runbooks, API guides, task reports, and Vietnamese README or docs content.
metadata:
  short-description: Maintain accurate project documentation
---

# Documentation

Write evidence-based project documentation that matches implemented behavior and the repository language policy.

## Responsibilities

- Write root README and all files under `docs/` in Vietnamese; keep source identifiers and API names in English.
- Distinguish implemented, planned, deprecated, and unverified behavior.
- Prefer task-oriented instructions, explicit prerequisites, and executable examples.
- Update architecture decisions when a material trade-off is accepted.
- Preserve valid links, headings, terminology, and ownership.

## Workflow

1. Identify audience, decision or task, and authoritative repository evidence.
2. Inspect related code, configuration, tests, and existing documentation.
3. Write the smallest complete update using consistent terminology.
4. Validate links, commands, paths, examples, status labels, and language policy.
5. Report what was documented and what remains unverified.

## Acceptance criteria

- Documentation matches current repository behavior and scope.
- Required Vietnamese content is natural and technically precise.
- Commands identify prerequisites and do not imply unexecuted success.
- Links and referenced files resolve.
- Planned features are labeled `PLANNED` rather than presented as available.

## Verification

Run available Markdown/link checks and execute safe documented commands when practical. Otherwise inspect every changed link and path. Never invent test results, production state, or feature availability.
