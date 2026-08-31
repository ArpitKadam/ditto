# TASK.md — ditto

> Project-specific task backlog. Operating contract lives in `CLAUDE.md` — read it first.
> Execution is **gated**: one task at a time, stop at Phase F, wait for "Go for Task n".
> Plugin name `ditto` is used throughout; renaming is a find-replace, decide before Task 1 commits.

---

## Project

**ditto** is a Claude Code plugin that turns a research paper into an explained, implemented, visualized, and reported reproduction. Five skills share one intermediate representation:

- `ditto:ingest` — fetch + normalize a paper into a canonical run workspace, build `ir.yaml`
- `ditto:explain` — human-readable walkthrough generated from the IR
- `ditto:code` — implement the method, verified against explicit reproduction tiers
- `ditto:visualize` — architecture / training / attention visualizations
- `ditto:report` — reproduction report: claimed vs. achieved, assumptions, deviations

All inter-skill state lives on the filesystem (run workspace + manifest), never in conversation memory. Any skill invoked in a fresh session reads the manifest and picks up.

---

## Locked decisions

These were settled during project brainstorming. **Seed `DECISIONS.md` with them in Task 1** (one dated entry each, alternatives noted). Do not re-litigate without new evidence.

1. **Source priority: arXiv e-print LaTeX → arXiv HTML → PDF hybrid.** `arxiv.org/e-print/{id}` tarball is the primary source (lossless equations, pseudocode, tables, figure assets). `arxiv.org/html/{id}` is the fallback (clean markup + image assets). PDF is last resort only (token-hungry, lossy): PyMuPDF text extraction + rendered page images at ~150 dpi.
2. **Shared Paper IR** (`ir.yaml`) with per-field `{value, status, src}` — status ∈ `stated | inferred | assumed | unknown`, `src` is a section/equation/page/figure pointer. The IR is an **index, not a replacement**: downstream skills zoom back into `source/` via `src` pointers when ambiguous.
3. **Filesystem is the state.** Canonical run workspace layout + `manifest.yaml` (schemas below) are the contract between skills.
4. **Verification tiers T0–T3** for `ditto:code`; target tier declared up front; two configs always produced (`config_paper.yaml` faithful, `config_small.yaml` runs in minutes).
5. **Official repo check is step zero of `ditto:code`.** If a reference implementation exists, the IR links it and validation diffs against it.
6. **Packaging: Claude Code plugin** (skills + reviewer subagents + shared `pipeline/` package). Skills stay thin; deterministic work lives in `pipeline/`, referenced via `${CLAUDE_PLUGIN_ROOT}`.
7. **Stack:** Python managed with `uv`. Core deps: `arxiv` (or plain HTTP to export API), `PyMuPDF`, `PyYAML`, `pytest`; `latexpand` (or a small Python flattener) for multi-file LaTeX; `torch`, `einops`, `torchinfo` for the code skill; `matplotlib`, `graphviz`/`torchview` for visualize. No further deps without justification (`CLAUDE.md` §8.6).

---

## Target repository layout

```
ditto/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   ├── ingest/
│   │   └── SKILL.md
│   ├── explain/
│   │   ├── SKILL.md
│   │   └── references/          # paper-analysis.md, explanation-template.md
│   ├── code/
│   │   ├── SKILL.md
│   │   └── references/          # implementation-patterns.md, pytorch-patterns.md, tiers.md
│   ├── visualize/
│   │   ├── SKILL.md
│   │   ├── references/          # visualization-guide.md, plotting-patterns.md
│   │   └── scripts/             # attention_viz.py, architecture_viz.py, training_viz.py
│   └── report/
│       ├── SKILL.md
│       └── references/          # report-template.md
├── agents/
│   ├── ir-auditor.md            # fresh-context: checks ir.yaml against source/
│   ├── implementation-reviewer.md  # fresh-context: checks impl/ against ir.yaml equations
│   └── viz-reviewer.md
├── pipeline/                    # plain Python package; skills invoke, never reimplement
│   ├── __init__.py
│   ├── fetch.py                 # resolve input → download source (e-print / html / pdf / local)
│   ├── extract.py               # source → paper.md + figures/ (+ pages/ for pdf)
│   ├── ir_build.py              # scaffold ir.yaml skeleton for Claude to fill
│   ├── ir_validate.py           # schema check + provenance lint + status coverage
│   └── workspace.py             # run dir creation, manifest read/write
├── templates/
│   ├── ir-skeleton.yaml
│   ├── manifest-skeleton.yaml
│   └── reproduction-report.md
├── tests/
│   └── ...                      # pytest, fixtures = the three test papers
└── runs/                        # gitignored; per-paper workspaces
```

---

## Contract 1 — Run workspace layout

Created by `ditto:ingest`. Every skill treats this as read/write ground truth.

```
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

## Contract 2 — IR schema v0

Draft. Refined against real papers in Task 5 — schema changes after Task 5 require a `DECISIONS.md` entry. Field convention everywhere: `{value, status, src}`.

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

## Contract 4 — Verification tiers (`ditto:code`)

| Tier | Meaning | Evidence required |
|------|---------|-------------------|
| T0 | Code runs | imports clean; forward pass on dummy data; shape assertions pass |
| T1 | Learns at all | overfit a single batch to ~zero loss; loss curve saved to `impl/logs/` |
| T2 | Trend reproduces | scaled-down training; method beats baseline directionally on `config_small` |
| T3 | Numbers reproduce | matches paper's headline results within stated tolerance |

Default target: **T1**, T2 where compute permits. T3 is opt-in only.

---

## Task backlog

Status values: `pending | in-progress | done`. Update in place as work progresses.

### Phase 0 — Foundation

**Task 1 — Repo scaffold, decisions, test-paper selection** · Status: done
- **Goal:** Working skeleton + evaluation ground truth chosen.
- **Do:** Scaffold the target layout (empty modules, `plugin.json`, `uv` project, pytest wired). Seed `DECISIONS.md` with the seven locked decisions. Create `ARCHITECTURE.md` from the contracts above. Select the three test papers with the user — candidates: **LoRA** (2106.09685: clean, official repo, T2 cheap), **DDPM** (2006.11239: math-heavy, T1/T2 feasible on MNIST-scale), plus one deliberately underspecified paper of the user's choice. Record picks in `DECISIONS.md`.
- **Accept:** `uv run pytest` passes (even if trivially); three papers recorded with rationale; plugin skeleton loads in Claude Code without errors.
- **Verify:** `claude` session lists the plugin; `uv run pytest -q`.

### Phase 1 — Ingestion pipeline (no skills yet; 60% of project value)

**Task 2 — `pipeline/fetch.py` + `workspace.py`** · Status: done
- **Goal:** Any input → populated `source/` + manifest.
- **Do:** Accept arXiv ID, arXiv URL (abs/pdf/html), local PDF/tex/txt path, generic PDF URL. Resolution order per locked decision 1: try e-print tarball (untar, flatten multi-file LaTeX to one `.tex`), else HTML (save page + image assets), else PDF. Create the run workspace, write `manifest.yaml` with `source_kind`. Check for an official repo (arXiv abstract links / README mention) and record in a fetch metadata file for the IR.
- **Accept:** All three test papers fetch via e-print with figures present in the tarball assets; a local-PDF fixture also produces a valid workspace; garbage input fails with an explicit error, not a stack trace.
- **Verify:** pytest cases per input type (network tests marked, cassette/fixture-based where possible); manual run on all three papers.

**Task 3 — `pipeline/extract.py`** · Status: done
- **Goal:** `source/` → `paper.md` + `figures/`.
- **Do:** LaTeX path: strip preamble/comments, preserve math environments verbatim, resolve `\includegraphics` → copy assets to `figures/` with stable names, keep captions. HTML path: readable text + math (MathML/LaTeX annotations) + download figure assets. PDF path (last resort): PyMuPDF text + embedded-image extraction + full-page renders to `pages/` at ~150 dpi.
- **Accept:** For each test paper: every numbered equation present in `paper.md` as valid LaTeX; every architecture figure present in `figures/`; tables survive with structure (LaTeX/HTML source, not OCR soup).
- **Verify:** pytest fixture assertions (equation count, figure count per paper); human spot-check of one figure and one equation per paper.

**Task 4 — IR build + validate** · Status: done
- **Goal:** `ir.yaml` scaffold, filled by Claude, mechanically validated.
- **Do:** `ir_build.py` writes the skeleton (Contract 2) pre-filled with paper metadata + figure inventory. `ir_validate.py` enforces: schema shape; every leaf field carries `status`; every `stated`/`inferred` field carries a non-empty `src`; `implementation_notes.assumptions/unknowns` exactly mirror the fields tagged `assumed`/`unknown`; equations have parseable LaTeX. Exit non-zero with a findings list on violation.
- **Accept:** Validator catches seeded violations (test cases for each rule); a hand-filled partial IR for one paper validates clean.
- **Verify:** pytest on validator rules; run against a deliberately broken IR.

**Task 5 — `ditto:ingest` skill + IR quality gate** · Status: done
- **Goal:** The first real skill; IR proven sufficient on all three papers.
- **Do:** Write `skills/ingest/SKILL.md`: workflow = fetch → extract → fill IR from `paper.md` + figures (viewing the architecture diagram is mandatory when present) → validate → update manifest. Spawn `ir-auditor` subagent (write `agents/ir-auditor.md`): fresh context, checks 10 sampled IR claims against `source/` via their `src` pointers, flags fabrications. Then run ingest end-to-end on all three test papers.
- **Accept — the IR quality gate:** From `ir.yaml` alone (source hidden), answer for each paper: exact loss function, full optimizer recipe with per-field confidence status, layer-by-layer architecture. Auditor finds zero fabricated `src` pointers. Any failure → fix schema or extraction, append `DECISIONS.md`, re-run. **Schema freezes after this task.**
- **Verify:** Three validated `ir.yaml` files in `runs/`; auditor reports saved; gate questions answered in `EXPLANATION.md` entry.

### Phase 2 — Explain

**Task 6 — `ditto:explain`** · Status: done
- **Goal:** IR → `explain.md` walkthrough; doubles as IR validation.
- **Do:** SKILL.md + `references/explanation-template.md`: problem → intuition → method walkthrough keyed to equations (rendered with meaning, not just restated) → architecture (embed diagram) → training recipe with confidence statuses surfaced honestly → what's unknown. Zoom into `source/` via `src` pointers where the IR is thin — and if that happens, the IR was deficient: log it.
- **Accept:** Explanations for all three papers; a reader can state the method's core mechanism and every assumption without opening the paper; no claims absent from IR + source.
- **Verify:** User reads one explanation cold and confirms; discrepancy log empty or actioned.

### Phase 3 — Code

**Task 7 — `ditto:code` skill** · Status: done
- **Goal:** IR → working implementation in `impl/`, tier-verified.
- **Do:** SKILL.md workflow: (0) official repo check — if exists, note diff-validation plan; (1) declare `tier_target` in manifest; (2) implementation plan mapping IR components/equations → modules; (3) implement smallest-first (ponytail ladder applies), `config_paper.yaml` + `config_small.yaml`; (4) every deviation from IR appended to `implementation_notes.deviations` **as it happens**; (5) tier evidence saved to `impl/logs/`. References: `implementation-patterns.md`, `pytorch-patterns.md`, `tiers.md` (Contract 4 expanded with exact evidence formats).
- **Accept:** Skill dry-runs on test paper 1 (LoRA) reaching T0 within the session.
- **Verify:** `uv run pytest` inside `impl/`; shape-assertion tests pass.

**Task 8 — `implementation-reviewer` subagent** · Status: done
- **Goal:** Fresh-context bias check.
- **Do:** `agents/implementation-reviewer.md`: input = `ir.yaml` + `impl/` diff, no implementer context. Checks each equation against its implementing code, config values against IR statuses (an `assumed` value silently hardcoded as fact = finding), unlogged deviations. One severity-tagged line per finding. Wire into `ditto:code` as a mandatory step before tier claims.
- **Accept:** Reviewer run on Task 7's output produces a findings list; seeded bug (wrong sign in loss) is caught in a test run.
- **Verify:** Seeded-bug test documented in `EXPLANATION.md`.

**Task 9 — End-to-end reproduction, papers 1–3** · Status: pending
- **Goal:** Prove the pipeline on real targets.
- **Do:** Full `ingest → code` runs: LoRA to **T2** (small model, e.g. distilgpt2-scale, adapter beats frozen baseline directionally), DDPM to **T1** (single-batch overfit, MNIST-scale samples as bonus), paper 3 to **T1**. Where compute in the session is insufficient, produce the runnable script + config and have the user execute; results fed back.
- **Accept:** `tier_reached` recorded honestly in each manifest with evidence in `impl/logs/`; deviations lists non-empty only where real; reviewer findings addressed.
- **Verify:** Loss curves / eval outputs in logs; manifests consistent.

### Phase 4 — Visualize and report

**Task 10 — `ditto:visualize`** · Status: pending
- **Goal:** `viz/` outputs from IR + `impl/`.
- **Do:** SKILL.md + scripts: `architecture_viz.py` (graph from IR layers, torchview/graphviz), `training_viz.py` (curves from `impl/logs/`), `attention_viz.py` (only when the method warrants it — skill must decide from IR, not run unconditionally). Reference: `plotting-patterns.md` (readable defaults, no chartjunk). `viz-reviewer` agent optional-lightweight: checks plots against the numbers they claim to show.
- **Accept:** Architecture + training visualizations for papers 1–2; each plot regenerable from a script, not a one-off.
- **Verify:** Scripts re-run clean from workspace state alone.

**Task 11 — `ditto:report`** · Status: pending
- **Goal:** The payoff artifact.
- **Do:** SKILL.md + `templates/reproduction-report.md`: claimed vs. achieved table (from `evaluation.headline_results` × `impl/logs/`), tier target vs. reached, full assumptions table (from IR statuses), deviations log, unknowns that mattered, compute used, honest verdict. No number without a source (IR `src` or log path).
- **Accept:** Reports for papers 1–2; every number traceable; verdict matches evidence.
- **Verify:** User reads LoRA report and can answer "what would it take to reach T3" from it.

### Phase 5 — Package and evaluate

**Task 12 — Plugin packaging + install test** · Status: pending
- **Goal:** Installable, namespaced, documented.
- **Do:** Finalize `plugin.json` (name, version, skill/agent registration); README with quickstart; verify `${CLAUDE_PLUGIN_ROOT}` paths resolve; install into a clean Claude Code environment and run `ditto:ingest` on a fresh arXiv ID.
- **Accept:** Cold install → successful ingest of an unseen paper with zero path errors.
- **Verify:** Clean-environment run logged.

**Task 13 — Trigger evals + description optimization** · Status: pending
- **Goal:** Skills fire when they should.
- **Do:** Use the `skill-creator` tooling: build a trigger eval set (~15 queries per skill: direct asks, indirect phrasings like "can you implement this arXiv paper", and negatives that must NOT trigger, e.g. "summarize this news article PDF"). Run the description-optimization loop; adopt best descriptions; make them appropriately pushy ("use whenever the user mentions reproducing, implementing, or reading a research paper, shares an arXiv link…").
- **Accept:** Trigger rate on held-out queries materially improved or confirmed high; negatives don't fire.
- **Verify:** Eval report saved to `tests/`.

---

## Dependency graph

```
1 → 2 → 3 → 4 → 5 → 6
                 5 → 7 → 8 → 9 → 10 → 11 → 12 → 13
```

Tasks 6 and 7 are parallelizable after 5 if batch mode is ever authorized; default remains gated.

## Out of scope (v1)

Recursive ingestion of dependency papers (IR records them; fetching them is v2). Non-arXiv paywalled sources. T3 reproductions. Multi-paper comparative reports.