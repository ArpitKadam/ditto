# DECISIONS.md

Append-only log of significant technical decisions, newest first.

## 2026-08-31 — Task 4: IR skeleton in code; all-unknown init; mechanical mirror via `--derive`

- **Decision:** (a) `ir_build.py` generates the IR skeleton in code — no `templates/ir-skeleton.yaml` file — following the `workspace.new_manifest` precedent; guidance for filling (status legend, src format, validator rules) lives in a static YAML header comment prepended to the dump. (b) Every status-carrying leaf initializes to `status: unknown` and `implementation_notes.unknowns` is pre-derived, so a freshly built or partially filled IR validates clean by construction. (c) The `{value, status, src}` convention applies to *value-bearing* leaves only: `problem.statement/motivation`, `method.summary`, the ten `training.*` fields, and `architecture.layers[]` items. `method.components[]` and `mathematics.equations[]` keep their contract shapes (src required, no status); `paper.official_repo` is metadata (shape-checked, excluded from the mirror). (d) The assumptions/unknowns mirror is resynced mechanically by `python -m pipeline.ir_build <run> --derive` (preserves hand-written `basis` per field); `ir_validate.py` stays pure read-only — it never rewrites, and manifest updates are left to the ingest skill (Task 5). (e) "Parseable LaTeX" for equations = non-empty, balanced braces (escape-aware), and matched `\begin{X}`/`\end{X}` pairs — no LaTeX-parser dependency. (f) `ir.yaml` gains a top-level `figures:` inventory (`{id, file, caption}` from `figures/figures.yaml`, glob fallback for the PDF path) so the code/visualize skills see figures without re-reading the workspace; schema addition is pre-freeze (freeze is after Task 5).
- **Alternatives considered:** A `templates/ir-skeleton.yaml` file (second source of truth; pre-fill needs code anyway — the manifest already set the code-only precedent); initializing statuses empty (a partial IR could never validate clean, violating the acceptance criterion); requiring status on components/equations (contract 2 shows their shapes without it; equations are verbatim-from-paper by definition); making the validator auto-fix the mirror (validator must be a pure check so exit codes are trustworthy in the skill loop); full LaTeX parsing for equations (a dependency for what a 15-line balance check catches — truncation and mangling, the real failure modes).
- **Why:** Ponytail ladder + the Task 4 acceptance criteria: validator catches each seeded violation class, a hand-filled partial IR validates clean, and the contract's "auto-derived" notes actually are auto-derived.
- **Consequences:** `--derive` rewrites `ir.yaml`, dropping any inline comments Claude added (the static header survives; data belongs in fields). The status-leaf set is defined once (`ir_build.status_fields`) and imported by the validator, so schema drift between build and validate is impossible. Revisit the leaf set and the `figures:` section at the Task 5 quality gate.

## 2026-08-31 — Task 3: extraction is LaTeX-preserving, not detex'd

- **Decision:** `paper.md` keeps the LaTeX document body verbatim — comments and preamble stripped, but math environments, tables, and inline math left as LaTeX source. No conversion to prose/plain text. `\includegraphics` targets are rewritten to stable `figures/figN.<ext>` names (original extension kept, no rasterization), the asset copied, and provenance + a best-effort caption recorded in `figures/figures.yaml`. Parsing is regex + a depth-aware brace matcher, no LaTeX-parser dependency. PDF path uses the already-locked PyMuPDF; HTML path uses stdlib `html.parser`.
- **Alternatives considered:** (a) `pylatexenc`/full detex to prose — lossy for equations and adds a dep; the IR is an index that zooms back into `source/`, so fidelity beats readability here. (b) `pandoc` — heavy external binary. (c) Rasterizing PDF/EPS figures to PNG now — needs a renderer per figure and is only required when a skill must *view* a diagram (Task 5/7), so deferred. (d) `beautifulsoup4` for HTML — a dep the stdlib parser makes unnecessary for the fallback path.
- **Why:** Ponytail ladder — the acceptance criteria (equations present as valid LaTeX, figures copied, tables survive as LaTeX) are met by a preserve-and-rewrite pass without a parser dependency. Verified on all three papers.
- **Consequences:** `figures/figN` keeps mixed extensions (LoRA figures are `.pdf`). A skill that needs a raster diagram must rasterize on demand — tracked as a Task 5/7 follow-up. Caption cleanup strips inline-math macros (`\times` → gone) in the *convenience* `caption` field only; the faithful caption remains verbatim in `paper.md`. Same trust-boundary containment as Task 2 applies: `_within()` blocks `../` asset traversal out of `source/`.

## 2026-08-31 — Task 2: fetch implementation choices

- **Decision:** (a) Use stdlib `urllib` for the three arXiv endpoints (e-print, export API, /html) instead of the `arxiv` package or `requests`. (b) Flatten multi-file LaTeX with a small in-repo Python `\input`/`\include` resolver instead of `latexpand`. (c) Slug = bare arXiv id with `/` → `-` (old-style ids), or sanitized filename stem for local/PDF-URL inputs. (d) Network tests carry a `network` pytest marker and are deselected by default (`addopts = -m 'not network'`); run explicitly with `-m network`.
- **Alternatives considered:** `arxiv` PyPI package (adds a dep + transitive `feedparser`/`requests` for three simple GETs); `requests` (a dep for what `urllib` does); `latexpand` (Perl — not present on Windows, adds a non-Python runtime dep); running network tests by default (flaky, slow, rate-limited in CI).
- **Why:** Ponytail ladder — stdlib covers HTTP and gzip/tar; a ~20-line flattener covers the arXiv multi-file case without a Perl dependency. Marked network tests keep `uv run pytest` fast and offline-deterministic while still exercising live fetch on demand.
- **Consequences:** `pipeline/fetch.py` depends only on `PyYAML` beyond stdlib. LaTeX flattening resolves paths against the compilation-root dir (TeX semantics) and is containment-checked against untrusted e-print content. Revisit `latexpand` only if a real paper's `\input` structure defeats the simple resolver.

## 2026-08-31 — Task 2: hardening untrusted downloaded content (security)

- **Decision:** Treat downloaded e-print tarballs, arXiv API XML, and rendered HTML as untrusted at the trust boundary. Concretely: tar unpack uses `extractall(filter="data")` (PEP 706) — which sets the real floor `requires-python = ">=3.11.5"`; LaTeX `\input`/`\include` targets are rejected unless they resolve inside the source tree; XML is refused if it contains a DTD (`<!DOCTYPE`/`<!ENTITY`) before parsing, guarding XXE/billion-laughs; HTML `<img>` assets are downloaded only over `http(s)` from an `arxiv.org` host, blocking `file://` local reads and internal-host SSRF.
- **Alternatives considered:** Trusting arXiv content implicitly (arXiv is author-uploaded — a malicious paper is a realistic threat); `defusedxml` (an added dep; the DTD-reject guard covers the two relevant attacks for this single well-formed feed); leaving `requires-python = ">=3.11"` (allows 3.11.0–3.11.4 where the `filter` kwarg raises `TypeError`, silently disabling the tar guard).
- **Why:** Found by `security-review` (path traversal, HIGH; `file://`/SSRF, MED) and `cavecrew-reviewer` (the 3.11.5 `filter` floor). Each is a real exploit path triggered by merely fetching a crafted arXiv id; each fix is a few lines with a regression test.
- **Consequences:** Minimum Python is 3.11.5. Any future fetch path added must re-apply the boundary checks. Revisit `defusedxml` if the pipeline ever parses XML from more sources.

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
