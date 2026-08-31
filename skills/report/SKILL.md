---
name: report
description: Write the reproduction report for an ingested-and-implemented paper — claimed vs. achieved, tier evidence, assumptions, deviations, honest verdict — into runs/<slug>/report.md. Use whenever the user asks for a reproduction report, a summary of how a reproduction went, or "did we reproduce this paper".
---

# ditto:report — workspace state → report.md

The payoff artifact: everything the run learned, in one document a reader can
trust cold. Template and rules in
`${CLAUDE_PLUGIN_ROOT}/templates/reproduction-report.md` — read it first,
follow its section order exactly. The two governing rules: **no number
without a source** (IR `src` or a log path) and **never fake a comparison**
(claims untested at the reached tier are written `not attempted`, not
paired with non-comparable local numbers).

**Preconditions:** `manifest.yaml` shows `ir: {status: done, validated: true}`
and `code: {status: done}` with a recorded `tier_reached`. Visualize is
optional — reference `viz/` figures only if they exist. If
`report: {status: done}` and `report.md` exists, report that and stop
(resume semantics).

## Workflow

1. **Read the evidence, all of it.** `manifest.yaml` (tiers), `ir.yaml`
   (`evaluation.headline_results`, `implementation_notes`,
   `training.hardware`), and every file in `impl/logs/` — including
   `t2_trend/summary.md`, `review_*.md`, and any `*_failed_*` logs
   (negative evidence is evidence; tiers.md says the report reads it).
   Numbers come from evidence-file headers and rows, never from memory of
   the session that produced them.

2. **Draft `runs/<slug>/report.md`** from the template. Section-specific
   sourcing:
   - *Tier scorecard*: initial/final/pass-bar numbers quoted from the
     evidence CSV headers verbatim.
   - *Claimed vs. achieved*: one row per `evaluation.headline_results`
     entry, `claim src` copied from the IR. `tested?` is honest per row.
   - *Assumptions / unknowns / deviations*: transcribed from
     `implementation_notes` — abridge, never distort; every deviation
     appears.
   - *Path to T3*: built from `config_paper.yaml`, the paper's stated
     compute (`training.hardware`, `training.epochs_or_steps`), and the
     "not implemented" deviation entries.

3. **Trace pass.** Walk the finished draft number by number: re-open each
   cited source and confirm the number appears there. Run the template's
   self-check list. Fix before proceeding — a report with one untraceable
   number has lost its authority for all of them.

4. **Mark the stage:**

```bash
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python -m pipeline.workspace mark "<runs>/<slug>" report status=done
```

## Done means

`report.md` exists, passes the template self-check, every number traces, and
the manifest shows `report: done`. Report to the user: the verdict verbatim,
plus anything the trace pass had to fix.
