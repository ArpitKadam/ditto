"""Re-render tier-evidence CSVs from impl/logs/ as presentation curves.

Usage: python training_viz.py <run_dir> [--out-dir PATH]

Plots ONLY numbers present in the CSVs; the provenance line is quoted from the
CSV's own `# produced by:` header. Regenerable from workspace state alone.

Inputs discovered:
  impl/logs/t1_overfit.csv      -> viz/training_t1.png  (log-y overfit curve + pass bar)
  impl/logs/t2_trend/*.csv      -> viz/training_t2.png  (per-arm curves; 1-row CSV = baseline hline)
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _style import ARM_COLORS, BASELINE, INK, MUTED, apply_style, save

import matplotlib.pyplot as plt


def parse_csv(path: Path):
    comments, rows, header = [], [], None
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:  # some evidence writers emitted cp1252 dashes
        text = path.read_text(encoding="cp1252")
    for line in text.splitlines():
        if line.startswith("#"):
            comments.append(line.lstrip("# ").rstrip())
        elif line.strip():
            if header is None:
                header = [c.strip() for c in next(csv.reader([line]))]
            else:
                vals = next(csv.reader([line]))
                rows.append({k: float(v) for k, v in zip(header, vals)})
    return comments, header or [], rows


def _comment(comments, prefix):
    for c in comments:
        if c.startswith(prefix):
            return c[len(prefix):].strip()
    return ""


def _ycol(header):
    for c in ("val_loss", "loss"):
        if c in header:
            return c
    return header[-1]


def plot_t1(csv_path: Path, out_path: Path, paper_id: str):
    comments, header, rows = parse_csv(csv_path)
    ycol = _ycol(header)
    steps = [r["step"] for r in rows]
    ys = [r[ycol] for r in rows]
    initial, final = ys[0], ys[-1]
    bar = 0.01 * initial

    # sibling t1_*.csv files are supporting arms (tiers.md: the gate is
    # t1_overfit.csv alone) — plot them too so no on-disk evidence is invisible
    extras = [
        p for p in sorted(csv_path.parent.glob("t1_*.csv"))
        if p != csv_path and "_failed" not in p.stem
    ]

    apply_style()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(steps, ys, color=ARM_COLORS[0], linewidth=1.8,
            label=f"{csv_path.stem} (gate)" if extras else None)
    all_ys = list(ys)
    sources = [csv_path]
    for i, p in enumerate(extras, start=1):
        _, eheader, erows = parse_csv(p)
        eycol = _ycol(eheader)
        ax.plot([r["step"] for r in erows], [r[eycol] for r in erows],
                color=ARM_COLORS[i % len(ARM_COLORS)], linewidth=1.4,
                label=f"{p.stem} (supporting)")
        all_ys += [r[eycol] for r in erows]
        sources.append(p)
    ax.axhline(bar, color=BASELINE, linewidth=1.2, linestyle="--")
    ax.text(steps[-1], bar,
            f"  pass bar {bar:.4g} (1% of initial{', gate arm' if extras else ''})",
            fontsize=7.5, color=MUTED, va="bottom", ha="right")
    ax.annotate(f"final {final:.4g}", (steps[-1], final),
                textcoords="offset points", xytext=(-4, 8),
                fontsize=8, color=INK, ha="right")
    if max(all_ys) / max(min(all_ys), 1e-12) > 50:
        ax.set_yscale("log")
        ax.set_ylabel(f"{ycol} (log scale)")
    else:
        ax.set_ylabel(ycol)
    ax.set_xlabel("step")
    ax.set_title(f"T1 single-batch overfit — {paper_id}")
    if extras:
        ax.legend(loc="best", fontsize=8)
    prov = _comment(comments, "produced by:")
    if prov:
        names = ", ".join(p.name for p in sources)
        fig.text(0.01, -0.04,
                 f"source: impl/logs/{names} · {prov}",
                 fontsize=6.5, color=MUTED)
    save(fig, out_path)
    return out_path


def plot_t2(trend_dir: Path, out_path: Path, paper_id: str):
    files = sorted(trend_dir.glob("*.csv"))
    if not files:
        raise SystemExit(f"no CSVs in {trend_dir}")

    apply_style()
    fig, ax = plt.subplots(figsize=(7, 4))
    curve_i, metric, prov = 0, "", ""
    for f in files:
        comments, header, rows = parse_csv(f)
        ycol = _ycol(header)
        label = _comment(comments, "arm:").split(" — ")[0] or f.stem
        metric = metric or _comment(comments, "metric:")
        prov = prov or _comment(comments, "produced by:")
        if len(rows) == 1:  # untrained baseline: one value, drawn as reference line
            y = rows[0][ycol]
            ax.axhline(y, color=BASELINE, linewidth=1.2, linestyle="--")
            ax.text(0.02, y, f"{label}  {y:.4g}", transform=ax.get_yaxis_transform(),
                    fontsize=8, color=MUTED, va="bottom")
        else:
            color = ARM_COLORS[curve_i % len(ARM_COLORS)]
            curve_i += 1
            steps = [r["step"] for r in rows]
            ys = [r[ycol] for r in rows]
            ax.plot(steps, ys, color=color, linewidth=1.8, label=label,
                    marker="o", markersize=4)
            ax.annotate(f"{ys[-1]:.4g}", (steps[-1], ys[-1]),
                        textcoords="offset points", xytext=(4, -4),
                        fontsize=8, color=INK)
    ax.set_xlabel("step")
    ax.set_ylabel(metric.split(" = ")[0] if metric else "val_loss")
    ax.set_title(f"T2 trend — {paper_id}")
    if curve_i:
        ax.legend(loc="best", fontsize=8)
    if prov:
        fig.text(0.01, -0.04, f"source: {trend_dir.as_posix().split('runs/')[-1]}/*.csv · {prov}",
                 fontsize=6.5, color=MUTED)
    save(fig, out_path)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args(argv)
    out_dir = args.out_dir or args.run_dir / "viz"
    logs = args.run_dir / "impl" / "logs"
    paper_id = args.run_dir.name

    made = []
    if (logs / "t1_overfit.csv").exists():
        made.append(plot_t1(logs / "t1_overfit.csv", out_dir / "training_t1.png", paper_id))
    if (logs / "t2_trend").is_dir():
        made.append(plot_t2(logs / "t2_trend", out_dir / "training_t2.png", paper_id))
    if not made:
        raise SystemExit(f"no training logs found under {logs}")


if __name__ == "__main__":
    main()
