# EXPLANATION.md

Append-only log: what was built, how it works, how it was verified. One entry per completed task.

## 2026-08-31 — Task 2: fetch.py + workspace.py

- **What changed:** Implemented `pipeline/workspace.py` (create run dir, build/read/write `manifest.yaml` per Contract 3) and `pipeline/fetch.py` (resolve any supported input → download source into `runs/<slug>/` → write manifest + `fetch_meta.yaml`). Added `PyYAML`. Added a `network` pytest marker, deselected by default. Tests: `tests/test_workspace.py`, `tests/test_fetch.py` (offline unit + network integration).
- **How it works:** `resolve_input` classifies the input (arXiv id/URL new+old id forms, direct PDF URL, local pdf/tex/txt) or raises `FetchError`. arXiv path downloads the e-print tarball, unpacks it safely, finds the main `.tex`, and flattens `\input`/`\include` into `main.flattened.tex`; if the e-print is a PDF it falls back to `/html/{id}`, else saves the PDF. Metadata (title/authors/year/abstract/official-repo candidates) comes from the export API Atom feed. `source_kind` (`latex`/`html`/`pdf`) is recorded in the manifest. Full flow in ARCHITECTURE.md → "Fetch pipeline".
- **How it was verified:**
  - `uv run pytest -q` → **31 passed, 3 deselected** (offline).
  - `uv run pytest -q -m network` → **3 passed** — LoRA (2106.09685), DDPM (2006.11239), Grokking (2201.02177) all fetch via e-print with figure assets present.
  - Manual CLI: `python -m pipeline.fetch <id>` for all three produced valid workspaces (`source_kind: latex`, flattened tex, 8/18/11 figure assets, official repos microsoft/LoRA, hojonathanho/diffusion, openai/grok). Garbage input → `fetch failed: unrecognized input …`, exit 2 (no stack trace).
  - `security-review` + `cavecrew-reviewer` run on the diff; all findings fixed and covered by regression tests (below).
- **Security findings fixed (Phase E):**
  1. **Path traversal (HIGH):** malicious e-print `\input{/etc/passwd}` / `../` read local files into the flattened source. Fixed with a source-tree containment check; test `test_flatten_rejects_out_of_tree_input`.
  2. **`file://`/SSRF (MED):** HTML `<img src>` could smuggle `file://` or internal hosts into `_download`. Fixed by restricting asset fetches to `http(s)` on `arxiv.org`; test `test_html_assets_reject_nonarxiv_and_filescheme`.
  3. **Python floor (correctness/security):** `tarfile` `filter="data"` needs ≥3.11.5; bumped `requires-python` so the tar guard is never silently disabled.
  4. XML `ParseError` and `None` author entries wrapped/filtered for explicit failure.
- **Limitations / follow-ups:** HTML and PDF acquisition paths run only when e-print is unavailable; not exercised by the three (all-LaTeX) test papers — `extract.py` (Task 3) is where the PDF/HTML branches get real coverage. `official_repo` is captured as *candidates* in `fetch_meta.yaml`; the IR promotes one to `official_repo` in Task 4/5. No `defusedxml` dep (DTD-reject guard is sufficient for the single arXiv feed).

## 2026-08-31 — Task 1: Repo scaffold, decisions, test-paper selection

- **What changed:** Created the plugin skeleton: `.claude-plugin/plugin.json`, `pipeline/` package (five docstring-only stub modules), `pyproject.toml` (uv-managed, `package = false`, pytest wired), `tests/test_scaffold.py`, `.gitignore` (runs/, .venv/, caches). Seeded `DECISIONS.md` with the seven locked decisions plus the test-paper/name selection. Created `ARCHITECTURE.md` from the four contracts. Marked Task 1 done in `TASK.md`.
- **How it works:** `pipeline/` is a plain root-level package; pytest finds it via `pythonpath = ["."]` in `pyproject.toml`. `uv sync` builds nothing (`package = false`) — the project is a dependency container only. The scaffold test imports every pipeline module and checks `plugin.json` has name/version/description. Test papers: LoRA (2106.09685), DDPM (2006.11239), Grokking (2201.02177, user-picked as the underspecified stress case).
- **How it was verified:** `uv run pytest -q` → `1 passed in 0.02s`. `claude plugin validate .` → "Validation passed with warnings" (one warning: root `CLAUDE.md` is not loaded as plugin context — intended; it's the dev operating contract, not shipped context; revisit at Task 12 packaging).
- **Limitations / follow-ups:** `skills/`, `agents/`, `templates/` directories not created — git doesn't track empty dirs; each is created by the task that first fills it (5, 6, 7, 4). Only `pytest` installed; remaining deps land in the task that first needs them (per the stack decision). Full "claude session lists the plugin" install check deferred to Task 12; `claude plugin validate` used as the Task 1 proxy.
