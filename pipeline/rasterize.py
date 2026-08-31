"""Rasterize a vector figure (PDF/EPS) to PNG so Markdown documents can embed it.

On-demand companion to extract.py: figures are copied with their original
extension at extract time; a skill that must *embed* one (explain, report)
renders a PNG next to the original with this module. Existing PNGs are
returned as-is.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf


class RasterizeError(Exception):
    """Explicit, user-facing rasterization failure."""


def rasterize(figure: Path | str, dpi: int = 150) -> Path:
    """figN.pdf -> figN.png next to it (first page). Idempotent; PNGs pass through."""
    figure = Path(figure)
    if not figure.is_file():
        raise RasterizeError(f"no such figure: {figure}")
    if figure.suffix.lower() == ".png":
        return figure
    out = figure.with_suffix(".png")
    if out.is_file():
        return out
    try:
        with pymupdf.open(figure) as doc:
            doc[0].get_pixmap(dpi=dpi).save(out)
    except Exception as e:  # pymupdf raises various types for unsupported input
        raise RasterizeError(f"cannot rasterize {figure}: {e}") from e
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Render a vector figure to PNG for embedding.")
    parser.add_argument("figure", help="path to figures/figN.pdf (or .eps)")
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args(argv)
    try:
        print(rasterize(args.figure, dpi=args.dpi))
    except RasterizeError as e:
        print(f"rasterize failed: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
