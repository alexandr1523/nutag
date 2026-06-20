# Nutag Agent Instructions

## Environment Constraints
- Use PowerShell-compatible commands.
- Do not chain commands with `&&`; use separate commands or PowerShell-safe separators.
- Use `.venv\Scripts\python.exe` for Python commands, including tests.
- Use standard non-interactive git commands.

## Working Rules
- Read the current file state before proposing or applying changes.
- Do not overwrite or revert user changes unless explicitly asked.
- After changing business logic, run `.venv\Scripts\python.exe -m pytest`.
- Keep changes minimal, targeted, and consistent with the existing codebase.

## Implementation Plan Maintenance
- Keep `IMPLEMENTATION_PLAN.md` as an operational roadmap, not a chronological dump of ideas.
- The plan must clearly separate: current implemented state, accepted product decisions, deprecated/rejected decisions, active backlog, next step, and change log.
- Every backlog item should have an explicit status such as `done`, `in progress`, `partial`, `blocked`, `not started`, or `rejected`.
- Keep exactly one clearly marked next step. When completing work, update that next step instead of only appending notes.
- When product direction changes, move obsolete rules to a deprecated/rejected section instead of leaving contradictory requirements in active sections.
- Do not add new plan sections that duplicate existing roadmap categories; update the existing category unless a genuinely new category is needed.
- When committing meaningful business-logic or architecture changes, update the plan status or change log if the change affects roadmap state.

## Product Rules
- Inventory is batch-based, not cumulative weighted-average based.
- When stock is consumed, the system must preserve the user-selected source batch or preparation.
- Batch-level stock balances must remain traceable and correct for ingredients, packaging, consumables, preparations, and finished goods.
- Legacy reconciliation logic must respect entity type boundaries and must not match records only by overlapping numeric IDs.
- All UI labels, item types, statuses, and user-facing text must be in Russian.

## Business Direction
- Equipment amortization should follow volume-based distribution across production volume.
- Users should be able to select specific available purchases or preparations that are still in stock.
- Real-time stock deduction after recording preparations or production is preferred over deferred reconciliation.
