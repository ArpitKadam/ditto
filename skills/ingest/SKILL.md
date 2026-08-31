---
name: ingest
description: Ingest a research paper into a ditto run workspace and build its validated Paper IR. Use whenever the user wants to reproduce, implement, explain, or analyze a research paper, shares an arXiv link or ID, or provides a paper PDF — this is the mandatory first stage before ditto:explain, ditto:code, ditto:visualize, or ditto:report.
---

# ditto:ingest — paper → validated Paper IR

Turns any paper input (arXiv ID/URL, local PDF/tex, PDF URL) into a run
workspace: `runs/<slug>/` with `source/`, `paper.md`, `figures/`, a filled
`ir.yaml`, and an updated `manifest.yaml`. All state lives on the filesystem —
never in conversation memory.

**Resumable by contract.** Before every step, read `runs/<slug>/manifest.yaml`
and the workspace state; skip anything already done. Re-invoking ingest on an
existing run continues where it stopped.

All commands run from the user's project directory. `<runs>` below is the
absolute path to `<project>/runs`.

## Workflow

### 1. Fetch

Skip if `runs/<slug>/source/` already has content.

```bash
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python -m pipeline.fetch "<input>" --runs-dir "<runs>"
```

Prints the run directory. On failure it exits 2 with an explicit reason —
relay it to the user; do not improvise a workaround.

### 2. Extract

Skip if `runs/<slug>/paper.md` exists.

```bash
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python -m pipeline.extract "<runs>/<slug>"
```

Produces `paper.md` (LaTeX preserved verbatim), `figures/` with
`figures.yaml`, and `pages/` for PDF sources.

### 3. Scaffold the IR

Skip if `runs/<slug>/ir.yaml` exists (never `--force` an IR that may contain
filled work — ask the user first).

```bash
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python -m pipeline.ir_build "<runs>/<slug>"
```

The skeleton arrives pre-filled with paper metadata, the official-repo
candidate, and the figure inventory. Every leaf starts `status: unknown`.

### 4. Fill the IR — the judgment step

Read `paper.md` and fill `ir.yaml`. Rules:

- **The IR is an index, not a summary.** Every claim carries
  `{value, status, src}`: `stated` (explicit in the paper — quote-level
  fidelity), `inferred` (derivable from the paper), `assumed` (your guess —
  record the basis), `unknown` (the paper doesn't say). Never upgrade a
  status to look better; `assumed` and `unknown` are first-class answers.
- **`src` must point where a reader can check:** section (`§3.2`), equation
  (`eq4`), table (`tab9`), figure (`fig1`), or page. If you cannot name a
  src, the status is not `stated`.
- **Viewing the architecture diagram is mandatory when one exists.** Check
  the `figures:` inventory; open the architecture figure with the Read tool
  and set `architecture.diagram` to its path. If figures are vector PDFs the
  Read tool renders them — do not skip because of the format.
- **Equations:** copy LaTeX verbatim from `paper.md` into
  `mathematics.equations` with `id`, `meaning` (plain language), and
  `implements` (which component realizes it).
- **Training recipe:** fill every `training.*` field. The loss goes in
  `training.objective` exactly — the formula or its equation id, not a vibe.
  A hyperparameter the paper omits is `unknown` or `assumed`-with-basis,
  never silently invented.
- **Sub-details a `stated` field leaves unspecified** (an init σ, Adam
  β/ε, a GPU count) do not demote the field — they get **supplemental
  entries** in `implementation_notes.unknowns`/`assumptions` whose path
  extends the leaf (e.g. `training.init.sigma_A`); `--derive` preserves
  them and the validator checks their prefix.
- **Official repo:** if `paper.official_repo.url` is set, record it; do not
  fetch the repo during ingest.
- **Dependencies:** cited works the method leans on for setup/recipe go in
  `paper.dependencies` with what they are needed for.

After filling, resync the assumptions/unknowns mirror:

```bash
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python -m pipeline.ir_build "<runs>/<slug>" --derive
```

### 5. Validate

```bash
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python -m pipeline.ir_validate "<runs>/<slug>"
```

Exit 0 or fix every finding and re-run. Findings are mechanical (missing
src, broken mirror, unbalanced LaTeX) — fix the IR, not the validator.

### 6. Audit — fresh-context fabrication check

Spawn the `ir-auditor` agent (registered by this plugin; if unavailable,
spawn a general read-only subagent and paste it the instructions from
`${CLAUDE_PLUGIN_ROOT}/agents/ir-auditor.md`). Give it only the run
directory path. It samples 10 `stated`/`inferred` claims, resolves each
`src` against `paper.md`/`source/`, and returns a verdict table.

Save its report verbatim to `runs/<slug>/ir_audit.md`. **Zero tolerance:**
any UNSUPPORTED or CONTRADICTED verdict means the IR is fixed and re-audited
before ingest is declared done.

### 7. Mark the manifest

```bash
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python -m pipeline.workspace mark "<runs>/<slug>" ingest status=done
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python -m pipeline.workspace mark "<runs>/<slug>" ir status=done validated=true
```

## Done means

`source/`, `paper.md`, `figures/`, validated `ir.yaml`, clean `ir_audit.md`,
manifest showing `ingest: done` and `ir: {done, validated: true}`. Report to
the user: paper title, source kind, equation/figure counts, official repo,
and the counts of `stated / inferred / assumed / unknown` fields.
