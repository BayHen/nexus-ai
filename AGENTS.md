# NEXUS AI Codex Instructions

## Scope and architecture

- Build NEXUS AI as a modular monolith following Clean Architecture principles.
- Keep module boundaries explicit. Business modules own their domain, application, infrastructure, and presentation concerns.
- Do not introduce microservices unless an approved architecture decision explicitly requires them.
- Preserve multi-tenant isolation, transaction safety, secure authentication, and RBAC in every relevant change.
- Treat AI agents, RAG, integrations, and asynchronous jobs as bounded platform capabilities, not shortcuts around domain rules.
- Work task by task. Do not implement work assigned to a later roadmap task unless the user explicitly changes the scope.
- Prefer the smallest dependency set that satisfies the current task.

## Language policy

- Write the root `README.md` entirely in Vietnamese.
- Write every document under `docs/` in Vietnamese.
- Use English for source code, function names, class names, APIs, database identifiers, filenames for source code, and technical identifiers.
- Use English for Git commit messages.
- `AGENTS.md` and `SKILL.md` may be written in English.
- Common technical terms such as API, JWT, Docker, PostgreSQL, RAG, MCP, and Agent Skills may remain in English in Vietnamese documentation.

## Engineering workflow

- Inspect existing files before modifying them and preserve unrelated user changes.
- Do not overwrite existing files blindly.
- Keep framework code out of domain layers and dependencies pointing inward.
- Keep tenant context explicit at application and persistence boundaries.
- Design write workflows around clear transaction boundaries; never hide partial failure.
- Never commit secrets. Update `.env.example` when a new environment variable is introduced.
- Add or update tests in proportion to behavior changes.
- Do not claim a test, formatter, linter, migration, or build passed unless it was executed.
- Record material architecture decisions in Vietnamese under `docs/architecture/`.

## Skill-Driven Development

- Check `.agents/skills/` for a relevant project skill before starting specialized work.
- Discover project skills from their `SKILL.md` frontmatter. A skill may be selected automatically when its description matches the request, or explicitly when the user names it as `$skill-name` or plain text.
- Before acting on a selected skill, read its complete `SKILL.md` and only the references relevant to the current work.
- If multiple skills apply, use the smallest set that covers the request and state the order in which they will be used.
- Tell the user when a skill affects an action or causes work to pause. Do not claim a skill was activated merely because it exists in the registry.
- A project skill must have a focused purpose, a `SKILL.md`, clear triggers, and only the supporting resources it needs.
- Keep reusable scripts and templates inside the owning skill directory.
- Do not place credentials, generated build artifacts, or environment-specific state in a skill.
- When creating or updating a skill, validate it and document how it affects the workflow.
- Run `python scripts/validate_skills.py` after changing project skills or the registry.

## Verification and delivery

- Run only verification relevant to the current task and report exact commands and outcomes.
- Distinguish implemented, planned, and blocked work explicitly.
- End each task with changed files, verification results, remaining issues, and readiness for the next roadmap task.
