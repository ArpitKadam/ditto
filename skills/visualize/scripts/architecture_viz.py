"""Render ir.yaml architecture.layers as a confidence-coded flow diagram.

Usage: python architecture_viz.py <run_dir> [--out PATH]

Reads only ir.yaml — the diagram shows what the IR actually knows: each layer
box is colored by its confidence status (stated/inferred/assumed/unknown) and
prints that status as text. Regenerable from workspace state alone.
"""

import argparse
import sys
import textwrap
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from _style import BASELINE, INK, MUTED, STATUS_COLORS, apply_style, save

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

WRAP = 96
MAX_SPEC_LINES = 4

# vertical layout constants (inches)
NAME_H = 0.22
LINE_H = 0.17
PAD_TOP = 0.12
PAD_BOT = 0.10
GAP = 0.32
FIG_W = 8.5
BOX_X, BOX_W = 0.4, 7.7


def _esc(s):
    """Guard against matplotlib mathtext parsing on stray $."""
    return str(s).replace("$", r"\$")


def _wrap(spec):
    lines = textwrap.wrap(" ".join(str(spec).split()), WRAP) or ["(unspecified)"]
    if not lines[0].strip():
        lines = ["(unspecified)"]
    if len(lines) > MAX_SPEC_LINES:
        lines = lines[:MAX_SPEC_LINES]
        lines[-1] = lines[-1][: WRAP - 2].rstrip() + " …"
    return lines


def _box_entries(ir):
    arch = ir.get("architecture") or {}
    entries = []
    inputs = arch.get("inputs") or []
    if inputs:
        spec = " | ".join(str(i).split(" — ")[0] for i in inputs)
        entries.append({"name": "inputs", "spec": spec, "status": None, "src": ""})
    for layer in arch.get("layers") or []:
        entries.append(
            {
                "name": layer.get("name", "?"),
                "spec": layer.get("spec", ""),
                "status": layer.get("status", "unknown"),
                "src": str(layer.get("src") or "").strip(),
            }
        )
    return entries


def render(run_dir: Path, out_path: Path) -> Path:
    ir = yaml.safe_load((run_dir / "ir.yaml").read_text(encoding="utf-8"))
    entries = _box_entries(ir)
    if not any(e["status"] for e in entries):
        raise SystemExit(f"no architecture.layers in {run_dir / 'ir.yaml'}")

    for e in entries:
        e["lines"] = _wrap(e["spec"])
        e["h"] = PAD_TOP + NAME_H + LINE_H * len(e["lines"]) + PAD_BOT

    title = (ir.get("paper") or {}).get("title") or run_dir.name
    paper_id = (ir.get("paper") or {}).get("id") or run_dir.name
    diagram = (ir.get("architecture") or {}).get("diagram")

    head_h, foot_h = 0.55, 0.75
    total_h = head_h + sum(e["h"] for e in entries) + GAP * (len(entries) - 1) + foot_h

    apply_style()
    fig = plt.figure(figsize=(FIG_W, total_h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, FIG_W)
    ax.set_ylim(total_h, 0)  # y grows downward
    ax.set_axis_off()

    ax.text(BOX_X, 0.28, _esc(f"{title} ({paper_id}) — architecture"),
            fontsize=11, fontweight="bold", color=INK, va="center")

    y = head_h
    prev_bottom = None
    statuses_present = []
    for e in entries:
        color = STATUS_COLORS.get(e["status"], BASELINE) if e["status"] else BASELINE
        if e["status"] and e["status"] not in statuses_present:
            statuses_present.append(e["status"])
        ax.add_patch(
            FancyBboxPatch(
                (BOX_X, y), BOX_W, e["h"],
                boxstyle="round,pad=0.03",
                facecolor=color, alpha=1.0, edgecolor=color, linewidth=1.4,
                mutation_aspect=1.0, fill=False,
            )
        )
        ax.add_patch(
            FancyBboxPatch(
                (BOX_X, y), BOX_W, e["h"],
                boxstyle="round,pad=0.03",
                facecolor=color, alpha=0.08, edgecolor="none",
            )
        )
        ax.text(BOX_X + 0.15, y + PAD_TOP + 0.02, _esc(e["name"]),
                fontsize=8.5, fontweight="bold", color=INK, va="top")
        if e["status"]:
            src = e["src"] if len(e["src"]) <= 48 else e["src"][:47] + "…"
            chip = e["status"].upper() + (f" · {src}" if src else "")
            ax.text(BOX_X + BOX_W - 0.15, y + PAD_TOP + 0.02, _esc(chip),
                    fontsize=7, color=MUTED, va="top", ha="right")
        for i, line in enumerate(e["lines"]):
            ax.text(BOX_X + 0.15, y + PAD_TOP + NAME_H + i * LINE_H, _esc(line),
                    fontsize=8, color=INK, va="top")
        if prev_bottom is not None:
            ax.add_patch(
                FancyArrowPatch(
                    (FIG_W / 2, prev_bottom + 0.05), (FIG_W / 2, y - 0.05),
                    arrowstyle="-|>", mutation_scale=11, color=MUTED, linewidth=1.2,
                )
            )
        prev_bottom = y + e["h"]
        y = prev_bottom + GAP

    legend_y = total_h - foot_h + 0.22
    x = BOX_X
    ax.text(x, legend_y, "IR confidence:", fontsize=7.5, color=MUTED, va="center")
    x += 0.95
    for status in ["stated", "inferred", "assumed", "unknown"]:
        if status not in statuses_present:
            continue
        ax.add_patch(plt.Rectangle((x, legend_y - 0.05), 0.1, 0.1,
                                   facecolor=STATUS_COLORS[status], edgecolor="none"))
        ax.text(x + 0.16, legend_y, status, fontsize=7.5, color=INK, va="center")
        x += 0.16 + 0.09 * len(status) + 0.25
    foot = "generated from ir.yaml architecture.layers — full specs there"
    if diagram:
        foot += f" · paper's own diagram: {diagram}"
    ax.text(BOX_X, legend_y + 0.28, _esc(foot), fontsize=7, color=MUTED, va="center")

    save(fig, out_path)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    out = args.out or args.run_dir / "viz" / "architecture.png"
    render(args.run_dir, out)


if __name__ == "__main__":
    main()
