# DECISIONS.md

Append-only log of significant technical decisions, newest first.

## 2026-08-31 — Test-paper selection and plugin name

- **Decision:** Plugin name stays **ditto**. Test papers: (1) **LoRA** (arXiv 2106.09685), (2) **DDPM** (arXiv 2006.11239), (3) **Grokking** (arXiv 2201.02177) as the deliberately underspecified paper.
- **Alternatives considered:** Renaming the plugin (rejected: name is used throughout the contracts, no motivating reason). For paper 3: Neural Turing Machines (1410.5401 — maximally underspecified, no official code, but reproductions are notoriously unstable, risking noise unrelated to the pipeline) and word2vec (1301.3781 — details live in the C code, but the official code makes unknowns fully resolvable, weakening the stress test).
- **Why:** LoRA is clean with an official repo and T2 is cheap at distilgpt2 scale. DDPM is math-heavy with T1/T2 feasible at MNIST scale. Grokking uses a tiny transformer on modular arithmetic — minutes-scale training — while leaving enough recipe vagueness to exercise the IR's `assumed`/`unknown` statuses; user picked it over NTM.
- **Consequences:** All three fixtures must fetch via arXiv e-print (Task 2 acceptance). Revisit if Grokking proves too well-specified to stress the IR in Task 5.

## 2026-08-31 — Source priority: arXiv e-print LaTeX → arXiv HTML → PDF hybrid

- **Decision:** `arxiv.org/e-print/{id}` tarball is the primary source; `arxiv.org/html/{id}` is the fallback; PDF is last resort (PyMuPDF text extraction + rendered page images at ~150 dpi).
- **Alternatives considered:** PDF-first (simplest single path); HTML-first (clean markup).
- **Why:** The e-print tarball is lossless for equations, pseudocode, tables, and figure assets. HTML keeps clean markup + images but is not available for all papers. PDF is token-hungry and lossy.
- **Consequences:** `pipeline/fetch.py` implements the three-way fallback; extraction (Task 3) needs a code path per source kind. Revisit if arXiv changes e-print availability.

## 2026-08-31 — Shared Paper IR with per-field provenance

- **Decision:** One `ir.yaml` per run with per-field `{value, status, src}`; status ∈ `stated | inferred | assumed | unknown`; `src` is a section/equation/page/figure pointer. The IR is an **index, not a replacement** — downstream skills zoom back into `source/` via `src` pointers when ambiguous.
- **Alternatives considered:** Free-form notes per skill (no machine-checkable provenance); IR as full replacement for the source (loses detail, invites fabrication).
- **Why:** Per-field status makes assumptions and unknowns first-class and mechanically auditable; `src` pointers make every claim checkable against the source.
- **Consequences:** `ir_validate.py` enforces status coverage and provenance; `implementation_notes.assumptions/unknowns` are derived from statuses. Schema freezes after Task 5.

## 2026-08-31 — Filesystem is the state

- **Decision:** All inter-skill state lives in the run workspace (`runs/<paper-slug>/`) plus `manifest.yaml`; never in conversation memory.
- **Alternatives considered:** Conversation-carried state (dies with the session); a database (overkill for per-paper artifacts).
- **Why:** Any skill invoked in a fresh session reads the manifest and picks up exactly where the last one stopped.
- **Consequences:** Contracts 1 and 3 (workspace layout, manifest schema) are the interface between skills; changes to either require a decision entry.

## 2026-08-31 — Verification tiers T0–T3 for ditto:code

- **Decision:** Four tiers — T0 code runs, T1 learns at all (single-batch overfit), T2 trend reproduces (scaled-down), T3 numbers reproduce. Target tier declared up front; two configs always produced (`config_paper.yaml` faithful, `config_small.yaml` runs in minutes). Default target T1, T2 where compute permits, T3 opt-in only.
- **Alternatives considered:** Binary "reproduced / not reproduced" (hides how far the reproduction actually got); always targeting paper-scale numbers (infeasible on session compute).
- **Why:** Tiers make the honesty of a reproduction claim explicit and cheap to verify incrementally.
- **Consequences:** Every tier claim requires evidence in `impl/logs/`; the manifest records `tier_target` vs `tier_reached`.

## 2026-08-31 — Official repo check is step zero of ditto:code

- **Decision:** If a reference implementation exists, the IR links it and validation diffs against it before any implementation work.
- **Alternatives considered:** Clean-room implementation always (wastes the strongest available ground truth).
- **Why:** An official repo is the highest-fidelity oracle for ambiguous paper details.
- **Consequences:** `ditto:ingest` records `official_repo` in the IR; `ditto:code` starts with the check.

## 2026-08-31 — Packaging: Claude Code plugin with thin skills over pipeline/

- **Decision:** Package as a Claude Code plugin: skills + reviewer subagents + shared `pipeline/` Python package. Skills stay thin; deterministic work lives in `pipeline/`, referenced via `${CLAUDE_PLUGIN_ROOT}`.
- **Alternatives considered:** Standalone CLI (loses skill triggering and subagent integration); logic embedded in SKILL.md prose (non-testable, drifts).
- **Why:** Deterministic work belongs in tested Python; judgment work belongs in skills. The plugin boundary keeps both installable as one unit.
- **Consequences:** Every skill invokes `pipeline/` rather than reimplementing; `${CLAUDE_PLUGIN_ROOT}` paths must resolve in a clean install (Task 12).

## 2026-08-31 — Stack: Python via uv, minimal core deps

- **Decision:** Python managed with `uv`. Core deps: `arxiv` (or plain HTTP to the export API), `PyMuPDF`, `PyYAML`, `pytest`; `latexpand` or a small Python flattener for multi-file LaTeX; `torch`, `einops`, `torchinfo` for the code skill; `matplotlib`, `graphviz`/`torchview` for visualize. No further deps without justification.
- **Alternatives considered:** pip/poetry (slower, more lockfile friction); heavier document-AI extraction stacks (unjustified while LaTeX source is primary).
- **Why:** uv is fast and reproducible; the dep list covers fetch/extract/implement/visualize with nothing speculative.
- **Consequences:** Dependencies are added in the task that first needs them, not up front — Task 1 ships only `pytest`.
