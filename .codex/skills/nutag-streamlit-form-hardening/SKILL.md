---
name: nutag-streamlit-form-hardening
description: Use when changing or creating Nutag Streamlit forms, validation, dynamic rows, confirmation flows, session_state behavior, Russian UI messages, or UI testing instructions.
---

# Nutag Streamlit Form Hardening

Use this skill for Streamlit page work in `pages/*.py`, especially forms for purchases, preparations, production, orders, references, and destructive actions.

## Source Files

Read the current form before editing it. Useful references:

- `pages/2_Закупки_и_остатки.py` for dynamic purchase rows, text confirmation, and validation examples.
- `pages/3_Заготовки.py`, `pages/4_Производство.py`, `pages/5_Заказы.py` for upcoming staged form work.
- `IMPLEMENTATION_PLAN.md` for per-form approval status and next step.

## Required Workflow

1. Confirm the specific form is approved before implementation if the plan marks it `approval required`.
2. Keep UI labels, help text, errors, warnings, and statuses in Russian.
3. Validate before calling service functions:
   - required selections are present;
   - quantities are positive where needed;
   - prices/costs are non-negative;
   - partially filled rows produce explicit errors instead of being silently ignored;
   - destructive actions require explicit confirmation.
4. Keep service-layer validation as the source of truth for business invariants. UI validation is only a first line of defense.
5. Be careful with `st.session_state`:
   - do not mutate a widget key after that widget has been instantiated in the same run;
   - inside `st.form`, do not rely on `disabled=` changing based on another field in the same form;
   - prefer validating submitted values after `form_submit_button`.
6. For dynamic rows:
   - keep stable keys via a form version or row index strategy;
   - preserve entered data across reruns;
   - clear form state after successful save when duplicate submission is a risk.
7. For delete flows:
   - show an irreversible-action warning;
   - require exact text confirmation such as `УДАЛИТЬ`;
   - let the submit happen and validate confirmation after submit if the field is inside `st.form`.
8. After UI edits, run:
   - `.venv\Scripts\python.exe -m py_compile <changed page>`;
   - `.venv\Scripts\python.exe -m pytest` if service/business logic changed.
9. Provide a UI test checklist scoped only to the form or stage just changed.

## Avoid

- Do not suggest testing later stages before the current stage is stabilized.
- Do not duplicate business rules only in UI.
- Do not add English user-facing text.
