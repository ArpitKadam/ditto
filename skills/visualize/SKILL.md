---
name: visualize
description: Generate architecture, training, and (when warranted) attention visualizations into a run's viz/ directory from the Paper IR and impl/logs evidence. Use whenever the user asks to visualize, plot, or diagram an ingested paper's architecture or training results, or after ditto:code completes.
---

# ditto:visualize — IR + impl/logs → viz/

Produces `runs/<slug>/viz/`: an IR-confidence-coded architecture diagram and
presentation-grade training curves, each regenerable by re-running its script
against workspace state alone. Scripts live in
`${CLAUDE_PLUGIN_ROOT}/skills/visualize/scripts/`; style and honesty rules in
`references/plotting-patterns.md` (read it before writing any ad-hoc plot).

**Preconditions:** `manifest.yaml` shows `ir: {status: done, validated: true}`
(architecture viz needs only the IR). Training/attention viz additionally need
`code: done` with evidence in `impl/logs/`. If `visualize: done` and `viz/`
exists, report that and stop (resume semantics).

## Workflow

1. Read `manifest.yaml` and `ir.yaml` (at least `architecture` and
   `method.components`).

2. **Architecture diagram** (always):

```bash
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python skills/visualize/scripts/architecture_viz.py "<runs>/<slug>"
```

   Renders `architecture.layers` as a flow diagram color-coded by IR
   confidence (stated/inferred/assumed/unknown, status printed in each box).
   This is deliberate: in a reproduction tool the diagram's job is to show
   *claim confidence*, not just topology.

3. **Training curves** (when `impl/logs/` has evidence):

```bash
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python skills/visualize/scripts/training_viz.py "<runs>/<slug>"
```

   Discovers `t1_overfit.csv` → `viz/training_t1.png` (log-y curve + pass
   bar) and `t2_trend/*.csv` → `viz/training_t2.png` (per-arm curves;
   single-row CSVs drawn as baseline reference lines). Plots only numbers
   present in the CSVs; provenance quoted from their headers.

4. **Attention decision — from the IR, never unconditional.** Warranted only
   if the method operates on or modifies attention (check
   `method.components` / `architecture.layers` for attention-touching
   entries) AND a dump exists at `impl/logs/attention/*.npz` (convention in
   the script docstring: 2D arrays per panel, optional `tokens` labels — the
   impl dumps, the script renders). If warranted but no dump/checkpoint
   exists, record why it was skipped in the completion report instead of
   fabricating one. When both hold:

```bash
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python skills/visualize/scripts/attention_viz.py "<runs>/<slug>"
```

5. **Look at every PNG** with the Read tool. A written file is a claim, not
   evidence — check for label collisions, clipped annotations, wrong
   numbers. Fix and regenerate before proceeding.

6. **viz-reviewer gate.** Spawn the `viz-reviewer` agent
   (`agents/viz-reviewer.md`) on the run directory — fresh context, checks
   plots against the numbers/statuses they claim. Save its report to
   `viz/review.md`. Fix HIGH/MED findings and re-run it before marking the
   stage.

7. Mark the stage:

```bash
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python -m pipeline.workspace mark "<runs>/<slug>" visualize status=done
```

## Done means

`viz/` holds the architecture diagram, training plots for every evidence CSV
present, `review.md` with a PASS verdict, and the manifest shows
`visualize: done`. Report to the user: which plots were produced, which were
skipped and why (e.g. attention not warranted / no dump), and any reviewer
findings left open.
