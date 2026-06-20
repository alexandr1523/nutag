---
name: nutag-roadmap-maintenance
description: Use when updating Nutag's implementation plan, changing roadmap status, choosing the next step, documenting accepted/rejected decisions, or finishing work that affects project direction.
---

# Nutag Roadmap Maintenance

Use this skill whenever a change affects `IMPLEMENTATION_PLAN.md`, project direction, staged delivery order, or the next step.

## Source Files

Read:

- `IMPLEMENTATION_PLAN.md` before changing roadmap state.
- `AGENTS.md` for permanent plan-maintenance rules.
- Functional docs only when the roadmap decision depends on product scope: `README_FUNCTIONAL.md`, `01_scope_and_principles.md`, `02_registers_and_entities.md`, `03_calculation_rules.md`, `04_workflows_and_controls.md`.

## Required Workflow

1. Keep the plan as an operational roadmap, not a chronological dump.
2. Update existing roadmap sections instead of adding duplicate sections.
3. Maintain exactly one clear next step in section `6. Следующий шаг`.
4. Keep backlog statuses explicit. Use existing statuses such as `done`, `partial`, `approval required`, `not started`, `rejected`, `legacy only`, `not in MVP`.
5. Preserve the staged delivery order unless the user explicitly changes it:
   - `Закупки`;
   - `Заготовки`;
   - `Производство`;
   - `Заказы`.
6. When completing a task:
   - mark the relevant item `done` or `partial`;
   - update the next step to the next unresolved item in the same stage when appropriate;
   - only move to the next stage when the current stage is sufficiently stabilized.
7. When a product decision is rejected or replaced, move it to the rejected/deprecated area instead of leaving contradictory active requirements.
8. For form-hardening work, keep approval requirements under the relevant stage, not in a separate form-protection stage.
9. If meaningful business logic, architecture, or roadmap state changed, include the plan change in the same commit unless the user asks otherwise.

## Avoid

- Do not append notes that obscure what is done, what remains, and what is next.
- Do not set multiple simultaneous next steps.
- Do not promote later-stage UI testing while earlier stages are still being stabilized.
