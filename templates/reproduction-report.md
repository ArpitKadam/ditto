# reproduction-report template

Structure for `runs/<slug>/report.md` — the payoff artifact of a ditto run.
Section order is fixed. The report is written for someone deciding whether to
trust, extend, or fund this reproduction; it must be readable cold, without
the workspace.

**The one rule that governs every section: no number without a source.**
A claimed number cites its IR `src` (which points into the paper); an achieved
number cites the `impl/logs/` file it was read from. A number that cannot be
traced does not appear.

**The second rule: never fake a comparison.** Below T3, most headline claims
were not tested. The claims table says so per row — `not attempted` is an
honest, expected value, not a failure to hide. A T1/T2 result is evidence
about *learning* and *direction*, not about the paper's numbers.

```markdown
# Reproduction report — <Title> (arXiv <id>)

> ditto:report, generated <date> from `runs/<slug>` workspace state.
> Tier target **<T?>** → reached **<T?>** (manifest). Sources: `ir.yaml`,
> `impl/logs/`, `manifest.yaml`.

## Verdict

<3–6 sentences, honest and specific: what this reproduction demonstrates,
what it does not, and the single biggest caveat. Written last, from the
evidence below — the verdict may not claim anything the evidence sections
don't show.>

## Tier scorecard

| tier | meaning | status | evidence |
|------|---------|--------|----------|
| T0 | code runs | reached / not attempted | `impl/logs/t0_smoke.txt` |
| T1 | learns at all | ... | `impl/logs/t1_overfit.csv` — initial → final vs pass bar |
| T2 | trend reproduces | ... | `impl/logs/t2_trend/summary.md` — arm values, direction |
| T3 | numbers reproduce | not attempted | — |

<One line per *failed* attempt too: `*_failed_*` logs are negative evidence
and must be reported, not skipped.>

## Claimed vs. achieved

<Every row of `evaluation.headline_results`. Never drop a claim because it
was not tested — the untested rows are the point.>

| # | paper claim (abridged) | claim src | tested? | achieved | evidence |
|---|------------------------|-----------|---------|----------|----------|
| 1 | <claim> | <ir src, e.g. tab1> | not attempted (needs T3) / directional analogue (T2) / T1 only | <number or —> | <log path or —> |

<Prose under the table for any row needing nuance — e.g. what a "directional
analogue" actually compared, and how it differs from the paper's own setup.>

## Assumptions and unknowns

<From IR statuses — what a reproducer had to guess. Two tables.>

**Assumed** (`implementation_notes.assumptions`):

| field | assumed value (abridged) | basis |
|-------|--------------------------|-------|

**Unknown** (`implementation_notes.unknowns`) — and how each was resolved:

| field | why it matters | resolved as (from deviations) |
|-------|----------------|-------------------------------|

## Deviations log

<`implementation_notes.deviations`, in order, one row each: what / why
(abridged but not distorted) / ir_field. This is the complete diff between
the paper's recipe and what actually ran.>

## Unknowns that mattered

<The subset of assumptions/unknowns/deviations that could plausibly change
results — with one line each on *how* they could. Distinguish from benign
scope cuts (e.g. tier-scoped omissions). If none: say so and why.>

## Compute

<Device(s), wall times, and scale — all from evidence-file headers, never
from memory. Contrast with the paper's stated hardware
(`training.hardware`) in one line.>

## Path to T3

<What it would take to match the paper's headline numbers: which config
(`config_paper.yaml`), which datasets/checkpoints to obtain, estimated
compute (paper's own numbers where stated), which currently-unimplemented
pieces (from deviations "not implemented" entries) must be built, and which
assumptions become risks at that scale. Concrete enough that a reader can
answer "what would T3 take" from this section alone.>

## Reviewer gates

<One line per fresh-context review that gated this run (`impl/logs/review_*.md`,
`viz/review.md`): verdict and any finding left open.>
```

## Self-check before finishing

- [ ] Every number in the report traces to a named IR `src` or an
      `impl/logs/` / `viz/` file path.
- [ ] Every `evaluation.headline_results` row appears in the claims table,
      including all untested ones.
- [ ] No row juxtaposes a paper number with a non-comparable local number as
      if they were comparable.
- [ ] Every `*_failed_*` log in `impl/logs/` is mentioned in the scorecard.
- [ ] Every deviation from `implementation_notes.deviations` appears in the
      deviations log.
- [ ] The verdict claims nothing the evidence sections don't show.
- [ ] "Path to T3" answers "what would it take" concretely.
