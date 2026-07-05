---
name: nutag-roadmap-maintenance
description: Use when updating Nutag's implementation plan, changing roadmap status, maintaining the execution queue, choosing the next step, documenting accepted/rejected decisions, or finishing work that affects project direction.
---

# Nutag Roadmap Maintenance

Use this skill whenever a change affects `IMPLEMENTATION_PLAN.md`, project direction, the execution queue, domain backlog, or the next step.

## Source Files

Read:

- `IMPLEMENTATION_PLAN.md` before changing roadmap state.
- `AGENTS.md` for permanent plan-maintenance rules.
- `docs/DECISIONS.md` when product direction, accepted/rejected decisions, MVP scope, or architectural tradeoffs change.
- `docs/CHANGELOG_IMPLEMENTATION.md` when implementation history or detailed handoff notes change.
- `docs/REQUIREMENTS_AUDIT.md` when original functional requirements are implemented, changed, rejected, deferred, or need review.
- Functional docs only when the roadmap decision depends on product scope: `README_FUNCTIONAL.md`, `01_scope_and_principles.md`, `02_registers_and_entities.md`, `03_calculation_rules.md`, `04_workflows_and_controls.md`.

## Required Workflow

1. Keep the plan as an operational roadmap, not a chronological dump.
2. Keep two separate layers:
   - `Execution Queue` / `Текущая очередь работ`: the only source of work order and next-step selection.
   - `Domain Backlog` / `Backlog по областям`: grouped requirements by product area; never use it directly to choose the next step.
3. Update existing roadmap sections instead of adding duplicate sections.
4. Maintain exactly one clear next step in section `6. Следующий шаг`, matching the first non-done item in `Execution Queue`.
5. Keep backlog and queue statuses explicit. Use existing statuses such as `done`, `partial`, `current`, `next`, `approval required`, `not started`, `blocked`, `rejected`, `legacy only`, `not in MVP`, `later`, `needs UI check`.
6. Before changing section `6. Следующий шаг`, audit `Execution Queue` / `Текущая очередь работ` first:
   - identify the first non-done queue item;
   - verify whether it is blocked, waiting for user confirmation, or already checked by the user;
   - only skip it when the user explicitly defers it or the plan says it is non-blocking.
7. When new work is discovered:
   - add or update the matching item in `Domain Backlog` / `Backlog по областям`;
   - decide whether it enters `Execution Queue` / `Текущая очередь работ` now, later, blocked, or not in MVP;
   - do not let scattered backlog items silently change the next step.
8. When completing a task:
   - mark the queue item `done`, `partial`, or `needs UI check`;
   - mark the matching domain backlog item consistently;
   - update section `6. Следующий шаг` to the next queue item when appropriate.
9. Preserve the user-approved execution queue unless the user explicitly changes it.
10. If product direction changes, move obsolete rules to the rejected/deprecated area instead of leaving contradictory active requirements.
11. For form-hardening work, keep approval requirements under the relevant domain backlog area, but choose implementation order through `Execution Queue`.
12. Keep linked documents role-based and non-duplicative:
   - `IMPLEMENTATION_PLAN.md`: execution queue, active backlog, next step.
   - `docs/DECISIONS.md`: reasons for active, changed, rejected, later, and not-in-MVP decisions.
   - `docs/CHANGELOG_IMPLEMENTATION.md`: detailed implementation history.
   - `docs/REQUIREMENTS_AUDIT.md`: current status of original functional requirements.
13. Before finishing any change that affects product logic, architecture, roadmap order, requirements, or user-visible behavior, perform a document impact check across plan, decisions, changelog, requirements audit, README, and functional docs.
14. If meaningful business logic, architecture, or roadmap state changed, include the relevant plan/decision/changelog/audit updates in the same commit unless the user asks otherwise.

## Avoid

- Do not append notes that obscure what is done, what remains, and what is next.
- Do not set multiple simultaneous next steps.
- Do not choose the next step from a domain backlog section while bypassing `Execution Queue` / `Текущая очередь работ`.
- Do not reorder the execution queue silently.
- Do not treat grouped domain sections as a chronological plan.
- Do not duplicate long-form history or decision rationale inside `IMPLEMENTATION_PLAN.md`; link to the responsible document.
