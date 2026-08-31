"""Render attention heatmaps from impl/logs/attention/*.npz dumps.

Usage: python attention_viz.py <run_dir> [--out-dir PATH]

The viz layer cannot generically instantiate arbitrary impl models, so the
convention is: the impl dumps attention tensors, this script renders them.

Dump convention (one .npz per case):
  - each 2D array (rows = query positions, cols = key positions) becomes one
    heatmap panel, titled by its array name (e.g. layer0_head1, or just attn)
  - optional array `tokens` (strings) labels both axes when lengths match

Output: viz/attention_<npz-stem>.png per dump file.
"""

import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from _style import MUTED, apply_style, save

import matplotlib.pyplot as plt


def render_npz(npz_path: Path, out_path: Path):
    data = np.load(npz_path, allow_pickle=False)
    tokens = data["tokens"] if "tokens" in data.files else None
    panels = [(k, data[k]) for k in data.files if k != "tokens" and data[k].ndim == 2]
    if not panels:
        raise SystemExit(f"no 2D attention arrays in {npz_path}")

    apply_style()
    ncols = min(4, len(panels))
    nrows = math.ceil(len(panels) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.2 * ncols, 3.0 * nrows),
                             squeeze=False)
    vmax = max(float(a.max()) for _, a in panels)
    im = None
    for i, (name, arr) in enumerate(panels):
        ax = axes[i // ncols][i % ncols]
        im = ax.imshow(arr, cmap="Blues", vmin=0.0, vmax=vmax, origin="upper")
        ax.set_title(name, fontsize=9)
        ax.grid(False)
        if tokens is not None and len(tokens) == arr.shape[0] == arr.shape[1]:
            ax.set_xticks(range(len(tokens)))
            ax.set_xticklabels([str(t) for t in tokens], rotation=90, fontsize=6)
            ax.set_yticks(range(len(tokens)))
            ax.set_yticklabels([str(t) for t in tokens], fontsize=6)
        else:
            ax.set_xlabel("key position", fontsize=7)
            ax.set_ylabel("query position", fontsize=7)
    for j in range(len(panels), nrows * ncols):
        axes[j // ncols][j % ncols].set_axis_off()
    fig.colorbar(im, ax=axes, shrink=0.8, label="attention weight")
    fig.text(0.01, -0.02, f"source: {npz_path.name} (impl/logs/attention/)",
             fontsize=6.5, color=MUTED)
    save(fig, out_path)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args(argv)
    out_dir = args.out_dir or args.run_dir / "viz"
    dump_dir = args.run_dir / "impl" / "logs" / "attention"
    dumps = sorted(dump_dir.glob("*.npz")) if dump_dir.is_dir() else []
    if not dumps:
        raise SystemExit(
            f"no attention dumps under {dump_dir} — the impl must save .npz dumps "
            "there first (see module docstring for the convention)"
        )
    for npz in dumps:
        render_npz(npz, out_dir / f"attention_{npz.stem}.png")


if __name__ == "__main__":
    main()
