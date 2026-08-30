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
│   ├── fetch.py                 # resolve input → download source (e-print / html / pdf / local)
│   ├── extract.py               # source → paper.md + figures/ (+ pages/ for pdf)
│   ├── ir_build.py              # scaffold ir.yaml skeleton for Claude to fill
│   ├── ir_validate.py           # schema check + provenance lint + status coverage
│   └── workspace.py             # run dir creation, manifest read/write
├── tests/                       # pytest; fixtures = the three test papers
├── pyproject.toml               # uv-managed, package = false
└── runs/                        # gitignored; per-paper workspaces
```

Pending (created by the task that first fills them): `skills/{ingest,explain,code,visualize,report}/`, `agents/{ir-auditor,implementation-reviewer,viz-reviewer}.md`, `templates/`.

Pipeline modules are docstring-only stubs; Tasks 2–4 implement them.

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

implementation_notes:
  assumptions: []   # auto-derived: every field with status assumed → {field, value, basis}
  unknowns: []      # auto-derived: every field with status unknown
  deviations: []    # appended by ditto:code as they happen
```

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
