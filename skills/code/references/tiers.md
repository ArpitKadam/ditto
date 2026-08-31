# Verification tiers — meaning and exact evidence formats

Contract 4 expanded. A tier is *reached* when its evidence file exists in
`impl/logs/` and was produced by the current code. Evidence is regenerable:
every file names the command that produced it on its first line (as a
comment/header). `tier_reached` in the manifest never exceeds the evidence.

## T0 — code runs

**Meaning:** imports clean; forward pass on dummy data; shape assertions pass.

**Evidence:** `impl/logs/t0_smoke.txt` containing:

```
# produced by: uv run pytest tests/ -q  (cwd: runs/<slug>/impl)
<full pytest output — all tests passing>
# forward pass: input <shape> -> output <shape>; params total=<n> trainable=<n>
<per-module boundary shapes for one dummy forward>
```

The shape section is printed by a `tests/test_shapes.py` that asserts, not
inspects: wrong shape = test failure, not a log line.

## T1 — learns at all

**Meaning:** overfit a single small batch to ~zero loss — proves gradients
flow through every trainable path and the objective is minimizable.

**Evidence:** `impl/logs/t1_overfit.csv` (`step,loss` rows, header comment
naming the command + config) and `impl/logs/t1_overfit.png` (loss curve,
log-scale y). Pass bar: final loss < 1% of initial, or below an explicit
absolute threshold recorded in the CSV header with justification.

## T2 — trend reproduces

**Meaning:** scaled-down training on `config_small.yaml`; the method beats
the paper's natural baseline directionally on at least one metric the paper
uses.

**Evidence:** `impl/logs/t2_trend/` — one CSV per arm (method, baseline),
a `summary.md` table (metric, method value, baseline value, direction
matches paper: yes/no), and the exact configs used.

## T3 — numbers reproduce (opt-in only)

**Meaning:** matches the paper's headline results within a stated tolerance
on `config_paper.yaml`.

**Evidence:** `impl/logs/t3_repro/` — `comparison.md` table: every
`evaluation.headline_results` row → claimed vs achieved vs tolerance vs
verdict, plus training logs. Tolerances declared *before* the run, in the
table, with rationale.

## Rules

- Evidence produced on `config_small.yaml` proves T1/T2 only; T3 requires
  `config_paper.yaml`.
- A failed tier attempt keeps its logs (renamed `*_failed_<n>`) — negative
  evidence is evidence; the report skill reads it.
- Random seeds recorded in every evidence header.
