# Nutag Agent Instructions

## Environment Constraints
- Use PowerShell-compatible commands.
- Do not chain commands with `&&`; use separate commands or PowerShell-safe separators.
- Use `.venv\Scripts\python.exe` for Python commands, including tests.
- Use standard non-interactive git commands.

## Codex Skills Validation
- On Windows, run Codex skill validation in Python UTF-8 mode to avoid default codepage decode errors on Russian text:
  `.venv\Scripts\python.exe -X utf8 C:\Users\alexa\.codex\skills\.system\skill-creator\scripts\quick_validate.py .codex\skills\skill-name`

## Working Rules
- Read the current file state before proposing or applying changes.
- Do not overwrite or revert user changes unless explicitly asked.
- After changing business logic, run `.venv\Scripts\python.exe -m pytest`.
- Keep changes minimal, targeted, and consistent with the existing codebase.

## Implementation Plan Maintenance
- Keep `IMPLEMENTATION_PLAN.md` as an operational roadmap, not a chronological dump of ideas.
- The plan must clearly separate: current implemented state, accepted product decisions, deprecated/rejected decisions, execution queue, domain backlog, next step, and change log.
- Treat the execution queue as the only source of work order. Domain backlog sections describe scope by product area, but do not determine what should be done next.
- Every backlog item should have an explicit status such as `done`, `in progress`, `partial`, `blocked`, `not started`, or `rejected`.
- Keep exactly one clearly marked next step and make it match the first non-done item in the execution queue. When completing work, update the queue and next step instead of only appending notes.
- Before changing the next step, audit the execution queue first. Do not choose a task directly from a domain backlog section unless it is first added to the execution queue or the user explicitly redirects.
- When new work is discovered, add it to the relevant domain backlog and explicitly classify it in the execution queue as `next`, `later`, `blocked`, or `not in MVP` if it affects work order.
- When product direction changes, move obsolete rules to a deprecated/rejected section instead of leaving contradictory requirements in active sections.
- Do not add new plan sections that duplicate existing roadmap categories; update the existing category unless a genuinely new category is needed.
- Keep project documents linked by role:
  - `IMPLEMENTATION_PLAN.md` is for execution queue and active backlog.
  - `docs/DECISIONS.md` is for active, changed, rejected, later, and not-in-MVP decisions with reasons.
  - `docs/CHANGELOG_IMPLEMENTATION.md` is for detailed implementation history.
  - `docs/REQUIREMENTS_AUDIT.md` maps original functional requirements to current status.
- Do not duplicate the same long-form content across these files. Move details to the responsible document and link to it.
- Before finishing any change that affects product logic, architecture, roadmap order, requirements, or user-visible behavior, perform a document impact check: decide whether `IMPLEMENTATION_PLAN.md`, `docs/DECISIONS.md`, `docs/CHANGELOG_IMPLEMENTATION.md`, `docs/REQUIREMENTS_AUDIT.md`, README, or functional docs need updates.
- When committing meaningful business-logic, architecture, or product-direction changes, update the plan plus decisions/changelog/requirements audit when the change affects them.

## Product Rules
- Inventory is batch-based, not cumulative weighted-average based.
- When stock is consumed, the system must preserve the user-selected source batch or preparation.
- Batch-level stock balances must remain traceable and correct for ingredients, packaging, consumables, preparations, and finished goods.
- Legacy reconciliation logic must respect entity type boundaries and must not match records only by overlapping numeric IDs.
- All UI labels, item types, statuses, and user-facing text must be in Russian.

## Business Direction
- Online mode for one real-data user is the current priority.
- PostgreSQL is the target database for real data and production-like checks, both locally and online.
- Online deployment must use an external PostgreSQL database via `NUTAG_DATABASE_URL`/secrets; do not rely on an app-host SQLite file for durable online data.
- Local SQLite remains only a dev/fallback mode for quick startup, tests, demos, and temporary local work.
- Do not build full registration, roles, or multi-user SaaS infrastructure unless explicitly approved; implement only minimal one-user access protection for the online MVP.
- Equipment amortization should follow volume-based distribution across production volume.
- Users should be able to select specific available purchases or preparations that are still in stock.
- Real-time stock deduction after recording preparations or production is preferred over deferred reconciliation.
