# EXPLANATION.md

Append-only log: what was built, how it works, how it was verified. One entry per completed task.

## 2026-08-31 — Task 1: Repo scaffold, decisions, test-paper selection

- **What changed:** Created the plugin skeleton: `.claude-plugin/plugin.json`, `pipeline/` package (five docstring-only stub modules), `pyproject.toml` (uv-managed, `package = false`, pytest wired), `tests/test_scaffold.py`, `.gitignore` (runs/, .venv/, caches). Seeded `DECISIONS.md` with the seven locked decisions plus the test-paper/name selection. Created `ARCHITECTURE.md` from the four contracts. Marked Task 1 done in `TASK.md`.
- **How it works:** `pipeline/` is a plain root-level package; pytest finds it via `pythonpath = ["."]` in `pyproject.toml`. `uv sync` builds nothing (`package = false`) — the project is a dependency container only. The scaffold test imports every pipeline module and checks `plugin.json` has name/version/description. Test papers: LoRA (2106.09685), DDPM (2006.11239), Grokking (2201.02177, user-picked as the underspecified stress case).
- **How it was verified:** `uv run pytest -q` → `1 passed in 0.02s`. `claude plugin validate .` → "Validation passed with warnings" (one warning: root `CLAUDE.md` is not loaded as plugin context — intended; it's the dev operating contract, not shipped context; revisit at Task 12 packaging).
- **Limitations / follow-ups:** `skills/`, `agents/`, `templates/` directories not created — git doesn't track empty dirs; each is created by the task that first fills it (5, 6, 7, 4). Only `pytest` installed; remaining deps land in the task that first needs them (per the stack decision). Full "claude session lists the plugin" install check deferred to Task 12; `claude plugin validate` used as the Task 1 proxy.
