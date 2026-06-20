---
name: nutag-batch-inventory-workflow
description: Use when changing Nutag batch-based inventory behavior, stock consumption, purchase/preparation/production/order services, selected source batches, inventory reports, or tests that affect traceable stock balances.
---

# Nutag Batch Inventory Workflow

Use this skill when a task can affect stock balances, selected source batches, cost source selection, or traceability across purchases, preparations, production, and orders.

## Source Files

Read the relevant current files before changing behavior:

- `AGENTS.md` for permanent product invariants.
- `IMPLEMENTATION_PLAN.md` for active roadmap state and next step.
- `nutag/services/inventory.py` for stock batch listing and availability checks.
- `nutag/services/purchases.py`, `preparations.py`, `production.py`, `orders.py` for domain operations.
- Matching tests in `tests/test_inventory.py`, `tests/test_services.py`, `tests/test_preparations.py`, `tests/test_production.py`, `tests/test_orders.py`.

## Required Workflow

1. Identify which stock entity is affected: ingredient, packaging, consumable, preparation, or finished product.
2. Preserve the user-selected source batch/preparation/output when stock is consumed.
3. Validate in the service layer, not only in Streamlit:
   - selected source exists;
   - item type matches;
   - item id matches;
   - unit matches;
   - requested quantity does not exceed current available stock.
4. Use the selected source as the cost source. Do not trust UI-entered cost when a source batch is selected.
5. Keep legacy reconciliation type-safe. Never match records only by overlapping numeric IDs.
6. For edit/delete operations, block changes that would mutate a consumed source batch unless the task explicitly designs a safe reversal workflow.
7. Update or add pytest coverage for:
   - successful selected-source consumption;
   - overdraft rejection;
   - wrong type/item/unit rejection;
   - cumulative consumption within one service call when relevant;
   - edit/delete protection for used batches when relevant.
8. Run `.venv\Scripts\python.exe -m pytest` after business logic changes.

## Avoid

- Do not reintroduce cumulative weighted-average logic as the source of truth for new stock operations.
- Do not put business invariants only in Streamlit pages.
- Do not silently fall back to FIFO if the user selected a specific source and that source is invalid.
