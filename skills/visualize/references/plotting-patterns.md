# Plotting patterns — readable defaults, no chartjunk

Rules for every plot ditto produces (scripts here, and any ad-hoc plot a
skill writes later). Derived from the dataviz method; matplotlib-static
context. `_style.py` implements the shared defaults — import it, don't
re-specify.

## Procedure

1. **Form first.** What is the number's job? A single headline value is a
   sentence in the report, not a chart. Change-over-time → line. Comparison
   of a few arms → lines + reference lines, or a small table.
2. **Color by job, fixed per entity.** Colors follow the entity (an arm, a
   status), never its rank or draw order, and are never repainted when a
   series is added or dropped. Palettes live in `_style.py`:
   - IR confidence: `STATUS_COLORS` (stated `#0072B2`, inferred `#009E73`,
     assumed `#E69F00`, unknown `#D55E00`) — validated colorblind-safe
     (worst adjacent-pair ΔE 18.3). The amber fails 3:1 contrast on white,
     so **status is always also printed as text** — color never carries
     identity alone.
   - Training arms: `ARM_COLORS` in fixed order by sorted filename, never
     cycled past 4 — a 5th arm means a second figure, not a 5th hue.
   - Baselines/references: `BASELINE` gray, dashed.
3. **Validate any new palette** before use — never eyeball CVD safety:
   `node <dataviz-skill>/scripts/validate_palette.js "<hex,hex,…>" --mode light`
4. **Render it and look at it.** Open the PNG and check for label
   collisions, clipped annotations, and overflow before calling it done.
   A generated file is a claim, not evidence.

## Hard rules

- **One axis.** Never two y-scales on one plot. Two measures → two plots.
- **Log-y when the data spans decades** (max/min > 50, e.g. overfit
  curves), and the axis label says "(log scale)".
- **Never truncate a linear axis to exaggerate an effect.** Baselines make
  differences visible honestly; axis limits follow the data.
- **Recessive scaffolding:** light gray grid behind the data, no top/right
  spines, muted tick labels (`apply_style()` does all of this).
- **Direct labels over legend-hunting:** label the final value at the
  curve's endpoint; label reference lines on the line. A legend appears
  for ≥ 2 plotted series (loc="best", never pinned where data lives).
- **Text wears ink, never series color** — values, labels, and legends in
  `INK`/`MUTED`; the colored mark next to them carries identity.
- **Provenance footer on every figure:** which file(s) the numbers came
  from, quoting the evidence CSV's own `# produced by:` line. A plot that
  can't name its source doesn't ship.
- **Plot only numbers that exist in workspace files.** No smoothing that
  hides disclosed behavior (e.g. the wd=1 loss spikes stay visible), no
  invented points, no extrapolation.
- **Escape `$` in any text drawn from IR/CSV content** — matplotlib
  mathtext will otherwise try to parse it (`_esc` in architecture_viz.py).
- **Evidence CSVs may be cp1252** (some writers emitted native dashes);
  fall back from utf-8 instead of crashing (`parse_csv` in
  training_viz.py).

## Attention heatmaps

Sequential single-hue (`Blues`), `vmin=0`, shared `vmax` across panels of
one figure, rows = query positions, cols = key positions, `origin="upper"`,
one colorbar per figure, per-axes grid off. Token tick labels only when a
`tokens` array of matching length exists.
