"""Shared plotting style for ditto viz scripts.

Palette validated with the dataviz six-checks script (CVD worst adjacent pair
dE 18.3 PASS, lightness band PASS). The amber (#E69F00) fails 3:1 contrast on
white, so any status it encodes is ALWAYS also printed as text — color never
carries identity alone.
"""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

# IR confidence statuses — fixed entity colors, never reassigned.
STATUS_COLORS = {
    "stated": "#0072B2",
    "inferred": "#009E73",
    "assumed": "#E69F00",
    "unknown": "#D55E00",
}

# Fixed categorical order for multi-arm training curves (assigned by sorted
# filename, never cycled past 4 — fold extra arms into separate figures).
ARM_COLORS = ["#0072B2", "#009E73", "#E69F00", "#D55E00"]

SERIES = "#0072B2"  # primary measured series
BASELINE = "#5A5A5A"  # reference / baseline lines
GRID = "#D9D9D9"
INK = "#1A1A1A"
MUTED = "#6B6B6B"


def apply_style():
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": GRID,
            "axes.labelcolor": INK,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "axes.axisbelow": True,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "legend.frameon": False,
        }
    )


def save(fig, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_path}")
