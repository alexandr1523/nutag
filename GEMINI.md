# Nutag Project Instructions

## Environment Constraints
- **Shell:** Always use PowerShell compatible commands. Avoid `&&` for command chaining; use `;` or run commands separately.
- **Python:** Use `.venv\Scripts\python.exe` for running python modules (like pytest).
- **Git:** Use standard git commands via `run_shell_command`.

## Architectural Decisions
- **Inventory:** Moving from cumulative weighted average to batch-based selection (FIFO approach). Users should be able to select specific stock entries (purchases or preparations) that are still in stock.
- **Amortization:** Implement volume-based distribution (Cost per kg/unit) for equipment, calculated monthly across total production volume.
- **Localization:** All UI labels and item types must be in Russian.

## Workflow
- **Research first:** Always verify current file state before suggesting or applying changes.
- **Testing:** Run `.venv\Scripts\python.exe -m pytest` after changes to business logic.
