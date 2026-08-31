# ARCHITECTURE.md

Current state of the **ditto** Claude Code plugin. Why-decisions live in `DECISIONS.md`; the task backlog lives in `TASK.md`.

## Overview

ditto turns a research paper into an explained, implemented, visualized, and reported reproduction. Five skills share one intermediate representation (the Paper IR) and communicate **only through the filesystem** — a per-paper run workspace plus a manifest. Any skill invoked in a fresh session reads the manifest and picks up.

```text
ditto:ingest ──> runs/<slug>/{source/, paper.md, figures/, ir.yaml, manifest.yaml}
                    │
     ┌──────────────┼───────────────┐
     v              v               v
ditto:explain   ditto:code     ditto:visualize
 explain.md     impl/           viz/
     └──────────────┴───────────────┘
                    v
              ditto:report → report.md
```

## Repository layout

Built so far (Task 1):

```text
ditto/
├── .claude-plugin/plugin.json   # plugin manifest
├── pipeline/                    # plain Python package; skills invoke, never reimplement
│   ├── __init__.py
│   ├── fetch.py                 # DONE: resolve input → download source (e-print / html / pdf / local)
│   ├── extract.py               # DONE: source → paper.md + figures/ (+ pages/ for pdf)
│   ├── ir_build.py              # DONE: scaffold ir.yaml skeleton for Claude to fill; --derive resync
│   ├── ir_validate.py           # DONE: schema check + provenance lint + status coverage + mirror
│   └── workspace.py             # DONE: run dir creation, manifest read/write
├── tests/                       # pytest; fixtures = the three test papers
├── pyproject.toml               # uv-managed, package = false, requires-python >=3.11.5
└── runs/                        # gitignored; per-paper workspaces
```

Pending (created by the task that first fills them): `skills/{ingest,explain,code,visualize,report}/`, `agents/{ir-auditor,implementation-reviewer,viz-reviewer}.md`, `templates/`. The IR skeleton is generated in code (`ir_build.skeleton`), not from a template file — same precedent as the manifest.

## IR build (`pipeline/ir_build.py`)

`build_ir(run_dir)` (CLI: `python -m pipeline.ir_build <run_dir>`) writes `ir.yaml`: the Contract 2 skeleton pre-filled with paper metadata (`manifest.yaml` + `fetch_meta.yaml`: id, title, authors, year, source_kind, first `official_repo_candidates` entry as `official_repo` with status `stated`) and the figure inventory (top-level `figures:` from `figures/figures.yaml`, glob fallback for the PDF path). Every status-carrying leaf starts `status: unknown` and `implementation_notes.unknowns` is pre-derived, so a fresh skeleton validates clean. Refuses to overwrite an existing `ir.yaml` without `--force`. A static header comment (status legend, src format, validator rules) is prepended on every write.

`--derive` resyncs `implementation_notes.assumptions/unknowns` from field statuses after Claude edits: assumptions keep hand-written `basis` text per field; unknowns become the exact list of `unknown`-tagged dotted paths. `status_fields(ir)` defines the status-leaf set once — `problem.statement/motivation`, `method.summary`, the ten `training.*` fields, `architecture.layers[]` items — and the validator imports it, so build and validate cannot drift.

## IR validate (`pipeline/ir_validate.py`)

`validate_run(run_dir)` / `validate_ir(ir, run_dir)` (CLI: `python -m pipeline.ir_validate <run_dir>`) is a pure read-only check returning a findings list (CLI: exit 0 clean, 1 with one finding per line, 2 operational error). Never rewrites the IR or manifest — manifest updates belong to the ingest skill. Rules: top-level sections present and no unknown extras; `paper.*` keys and `official_repo` shape; every status leaf is a mapping with status ∈ `stated | inferred | assumed | unknown`; `stated`/`inferred` require non-empty `src`; `method.components[]` require name + src; `mathematics.equations[]` require id, src, and parseable LaTeX (escape-aware brace balance + matched `\begin`/`\end` pairs — no LaTeX parser dep); `evaluation.headline_results[]` require src; `architecture.diagram` must be null or an existing file in the run dir; `implementation_notes.assumptions/unknowns` exactly mirror the `assumed`/`unknown`-tagged fields.

## Fetch pipeline (`pipeline/fetch.py`)

`fetch(raw, runs_dir)` is the entry point (also a CLI: `python -m pipeline.fetch <input>`). Flow:

1. `resolve_input(raw)` → `Resolved{kind, ...}`: `arxiv` (id or arXiv URL, new `1234.56789` and old `hep-th/9901001` id forms), `pdf_url` (direct `.pdf` link), or `local` (existing `.pdf`/`.tex`/`.txt`). Anything else raises `FetchError` — an explicit message, never a stack trace.
2. Source acquisition, per the priority decision: arXiv → download `e-print/{id}`; if it is a tarball, `_extract_eprint` unpacks (`extractall(filter="data")`), finds the main `.tex` (`\documentclass` + `\begin{document}`), and writes `main.flattened.tex` via `flatten_latex`. If e-print serves a PDF (source withheld), fall back to `/html/{id}` (`_fetch_arxiv_html`), else save the PDF. `pdf_url`/`local` copy bytes into `source/`.
3. `fetch_arxiv_metadata` (export API, Atom XML) fills `fetch_meta.yaml`: title, authors, year, abstract, and `official_repo_candidates` (github/gitlab URLs scraped from abstract+comment, sentence punctuation stripped).
4. `workspace.new_manifest` + `write_manifest` record `source_kind` (`latex`/`html`/`pdf`) and the pending stage tracker.

Trust-boundary invariants (all downloaded content is untrusted): LaTeX `\input`/`\include` cannot escape the source tree; XML with a DTD is refused; HTML image assets download only over `http(s)` from `arxiv.org`.

## Extract pipeline (`pipeline/extract.py`)

`extract(run_dir)` reads `manifest.yaml` `source_kind` (inferring from `source/` if absent) and dispatches:

- **LaTeX** (`extract_latex`): `strip_comments` (drops `%`-to-EOL, keeps `\%`) → `document_body` (between `\begin{document}`/`\end{document}`) → `_rewrite_graphics`. Each `\includegraphics` is located, its `{...}` argument read with the depth-aware `brace_arg` (handles `\iftoggle{hq}{A}{B}` nesting), and `resolve_asset` picks the first candidate image file that exists under `source/`. Resolved assets are copied to `figures/figN.<ext>` (first-appearance order, deduped by original path) and the reference in `paper.md` is rewritten to `figures/figN.<ext>`. `paper.md` is the cleaned body with math/tables preserved verbatim as LaTeX. `figures/figures.yaml` records `{id, file, original, caption}` per figure (caption from the enclosing `figure`/`wrapfigure` env). `count_equations` counts numbered display-equation environments.
- **PDF** (`extract_pdf`, last resort): PyMuPDF — text per page concatenated into `paper.md`, embedded images (deduped by xref) to `figures/figN.png`, full-page 150 dpi renders to `pages/pageNN.png`.
- **HTML** (`extract_html`, fallback): stdlib `HTMLParser` extracts visible text (skips `script`/`style`/`head`) and copies referenced `<img>` assets already downloaded under `source/` to `figures/`.

Trust boundary: `_within(source_dir, path)` blocks any `../`/symlink escape, so a crafted `\includegraphics`/`<img src>` cannot copy files from outside `source/`. Returns `{source_kind, equations, figures}`.

## Contract 1 — Run workspace

Created by `ditto:ingest`; every skill treats it as read/write ground truth.

```text
runs/<paper-slug>/
├── source/            # what was fetched: *.tex (flattened) | *.html | *.pdf
├── figures/           # extracted figure assets (png), stable names figN.png
├── pages/             # pdf path only: rendered pages page01.png …
├── paper.md           # normalized text extraction (LaTeX preserved in math blocks)
├── ir.yaml            # the Paper IR
├── manifest.yaml      # stage tracker (Contract 3)
├── impl/              # ditto:code output — package, tests, configs, logs
├── viz/               # ditto:visualize output
├── explain.md         # ditto:explain output
└── report.md          # ditto:report output
```

## Contract 2 — Paper IR schema v0

Draft until the Task 5 quality gate; frozen after. Field convention everywhere: `{value, status, src}` with status ∈ `stated | inferred | assumed | unknown` and `src` a section/equation/page/figure pointer. The IR is an **index, not a replacement**: downstream skills zoom back into `source/` via `src` when ambiguous.

```yaml
paper:
  id:            # arxiv id or slug
  title:
  authors: []
  year:
  source_kind:   # latex | html | pdf
  official_repo: {url: null, status: unknown}   # checked at ingest
  dependencies:  # cited works this paper leans on for setup/method
    - {cite: "[23]", arxiv_id: null, needed_for: "training recipe"}

problem:
  statement: {value: "", src: ""}
  motivation: {value: "", src: ""}

method:
  summary: {value: "", src: ""}
  components:
    - {name: "", role: "", src: ""}

architecture:
  inputs: []
  layers: []           # ordered; each {name, spec, status, src}
  diagram: null        # figures/figN.png if one exists — code skill must view it

mathematics:
  equations:
    - {id: eq4, latex: "", meaning: "", implements: "", src: "§3.2"}

training:
  dataset:    {value: "", status: "", src: ""}
  objective:  {value: "", status: "", src: ""}   # loss, exactly
  optimizer:  {value: "", status: "", src: ""}
  lr:         {value: "", status: "", src: ""}
  schedule:   {value: "", status: "", src: ""}
  batch_size: {value: "", status: "", src: ""}
  epochs_or_steps: {value: "", status: "", src: ""}
  init:       {value: "", status: "", src: ""}
  regularization: {value: "", status: "", src: ""}
  hardware:   {value: "", status: "", src: ""}

evaluation:
  metrics: []
  headline_results: []   # claimed numbers with src — feeds ditto:report

experiments:
  baselines: []
  ablations: []

figures:             # inventory copied from figures/figures.yaml at build time
  - {id: fig1, file: figures/fig1.pdf, caption: ""}

implementation_notes:
  assumptions: []   # auto-derived (`ir_build --derive`): every field with status assumed → {field, value, basis}
  unknowns: []      # auto-derived: every field with status unknown (dotted paths)
  deviations: []    # appended by ditto:code as they happen
```

The `{value, status, src}` convention applies to value-bearing leaves (`problem.*`, `method.summary`, `training.*`, `architecture.layers[]`); `method.components[]` and `mathematics.equations[]` keep the shapes shown (src required, no status); `paper.official_repo` is shape-checked metadata outside the mirror (see the Task 4 decision).

## Contract 3 — Manifest schema

```yaml
paper_id:
created:
source_kind:      # latex | html | pdf
stages:
  ingest:    {status: pending}          # pending | done | failed
  ir:        {status: pending, validated: false}
  explain:   {status: pending}
  code:      {status: pending, tier_target: null, tier_reached: null}
  visualize: {status: pending}
  report:    {status: pending}
```

## Contract 4 — Verification tiers (ditto:code)

| Tier | Meaning | Evidence required |
| ---- | ------- | ----------------- |
| T0 | Code runs | imports clean; forward pass on dummy data; shape assertions pass |
| T1 | Learns at all | overfit a single batch to ~zero loss; loss curve saved to `impl/logs/` |
| T2 | Trend reproduces | scaled-down training; method beats baseline directionally on `config_small` |
| T3 | Numbers reproduce | matches paper's headline results within stated tolerance |

Default target **T1**, T2 where compute permits, T3 opt-in only.

## Invariants

- All inter-skill state lives on the filesystem; nothing depends on conversation memory.
- Every IR leaf field carries `status`; every `stated`/`inferred` field carries a non-empty `src`.
- `implementation_notes.assumptions/unknowns` exactly mirror the fields tagged `assumed`/`unknown`.
- Tier claims require evidence files in `impl/logs/`; `tier_reached` is recorded honestly in the manifest.
- Skills stay thin: deterministic work lives in `pipeline/`, invoked via `${CLAUDE_PLUGIN_ROOT}`.
- Test papers (fixtures): LoRA 2106.09685, DDPM 2006.11239, Grokking 2201.02177.
