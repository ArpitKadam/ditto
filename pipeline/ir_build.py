"""Scaffold ir.yaml pre-filled with paper metadata + figure inventory.

The skeleton follows Contract 2 (see ARCHITECTURE.md). Every status-carrying
leaf starts as `unknown` and implementation_notes.unknowns is pre-derived, so
a fresh or partially filled IR validates clean by construction. `--derive`
resyncs the assumptions/unknowns mirror from statuses after Claude edits.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

TRAINING_FIELDS = [
    "dataset",
    "objective",
    "optimizer",
    "lr",
    "schedule",
    "batch_size",
    "epochs_or_steps",
    "init",
    "regularization",
    "hardware",
]

_HEADER = """\
# Paper IR — index into source/, not a replacement. Filled by ditto:ingest,
# validated by `python -m pipeline.ir_validate <run_dir>`.
# Field convention: {value, status, src}
#   status: stated (explicit in paper) | inferred (derivable) | assumed (guessed) | unknown
#   src: pointer into paper.md / source — section, equation, page, or figure ("§3.2", "eq4", "fig1")
# Validator rules:
#   - every stated/inferred field needs a non-empty src
#   - implementation_notes.assumptions/unknowns mirror fields tagged assumed/unknown
#     (resync mechanically: `python -m pipeline.ir_build <run_dir> --derive`);
#     sub-details of a stated field may be added manually as supplemental entries
#     whose path extends a tracked leaf (e.g. training.init.sigma_A) — --derive
#     preserves them
#   - equations need id, src, and balanced latex
"""


class IRBuildError(Exception):
    """Explicit, user-facing build failure."""


def _leaf() -> dict:
    return {"value": "", "status": "unknown", "src": ""}


def status_fields(ir: dict) -> dict[str, dict]:
    """Dotted path -> mapping, for every status-carrying leaf in the IR."""
    out: dict[str, dict] = {}
    for sec, key in (
        ("problem", "statement"),
        ("problem", "motivation"),
        ("method", "summary"),
    ):
        node = (ir.get(sec) or {}).get(key)
        if isinstance(node, dict):
            out[f"{sec}.{key}"] = node
    for f in TRAINING_FIELDS:
        node = (ir.get("training") or {}).get(f)
        if isinstance(node, dict):
            out[f"training.{f}"] = node
    for i, layer in enumerate((ir.get("architecture") or {}).get("layers") or []):
        if isinstance(layer, dict):
            out[f"architecture.layers[{i}]"] = layer
    return out


def derive_notes(ir: dict) -> None:
    """Regenerate implementation_notes.assumptions/unknowns from field statuses.

    Hand-written `basis` text is preserved per field, and supplemental entries
    (paths extending a tracked leaf, e.g. training.init.sigma_A) are carried
    over untouched; deviations are untouched.
    """
    notes = ir.setdefault("implementation_notes", {})
    fields = status_fields(ir)
    prior_assumptions = [
        a for a in notes.get("assumptions") or [] if isinstance(a, dict)
    ]
    prior_by_field = {a.get("field"): a for a in prior_assumptions}
    notes["assumptions"] = [
        {
            "field": path,
            "value": node.get("value") or node.get("spec") or "",
            "basis": prior_by_field.get(path, {}).get("basis", ""),
        }
        for path, node in fields.items()
        if node.get("status") == "assumed"
    ] + [a for a in prior_assumptions if a.get("field") not in fields]
    notes["unknowns"] = [
        path for path, node in fields.items() if node.get("status") == "unknown"
    ] + [
        u
        for u in notes.get("unknowns") or []
        if isinstance(u, str) and u not in fields
    ]
    notes.setdefault("deviations", [])


def _figure_inventory(run_dir: Path) -> list[dict]:
    """{id, file, caption} per figure, from figures.yaml or a glob fallback (pdf path)."""
    manifest = run_dir / "figures" / "figures.yaml"
    if manifest.is_file():
        figs = yaml.safe_load(manifest.read_text(encoding="utf-8")) or []
        return [
            {"id": f.get("id"), "file": f.get("file"), "caption": f.get("caption", "")}
            for f in figs
        ]
    numbered = []
    for p in (run_dir / "figures").glob("fig[0-9]*.*"):
        m = re.fullmatch(r"fig(\d+)", p.stem)
        if m:
            numbered.append((int(m.group(1)), p))
    return [
        {"id": f"fig{n}", "file": f"figures/{p.name}", "caption": ""}
        for n, p in sorted(numbered)
    ]


def skeleton(run_dir: Path) -> dict:
    """Contract 2 skeleton, pre-filled from manifest + fetch_meta + figure inventory."""
    meta: dict = {}
    meta_file = run_dir / "fetch_meta.yaml"
    if meta_file.is_file():
        meta = yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}
    manifest: dict = {}
    if (run_dir / "manifest.yaml").is_file():
        manifest = (
            yaml.safe_load((run_dir / "manifest.yaml").read_text(encoding="utf-8"))
            or {}
        )
    repos = meta.get("official_repo_candidates") or []
    ir = {
        "paper": {
            "id": manifest.get("paper_id") or meta.get("arxiv_id") or run_dir.name,
            "title": meta.get("title"),
            "authors": meta.get("authors") or [],
            "year": meta.get("year"),
            "source_kind": manifest.get("source_kind"),
            "official_repo": {
                "url": repos[0] if repos else None,
                "status": "stated" if repos else "unknown",
            },
            "dependencies": [],
        },
        "problem": {"statement": _leaf(), "motivation": _leaf()},
        "method": {"summary": _leaf(), "components": []},
        "architecture": {"inputs": [], "layers": [], "diagram": None},
        "mathematics": {"equations": []},
        "training": {f: _leaf() for f in TRAINING_FIELDS},
        "evaluation": {"metrics": [], "headline_results": []},
        "experiments": {"baselines": [], "ablations": []},
        "figures": _figure_inventory(run_dir),
        "implementation_notes": {"assumptions": [], "unknowns": [], "deviations": []},
    }
    derive_notes(ir)
    return ir


def write_ir(run_dir: Path | str, ir: dict) -> Path:
    path = Path(run_dir) / "ir.yaml"
    path.write_text(
        _HEADER + yaml.safe_dump(ir, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def build_ir(run_dir: Path | str, force: bool = False) -> Path:
    """Write runs/<slug>/ir.yaml skeleton. Refuses to clobber unless force."""
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise IRBuildError(f"not a run directory: {run_dir}")
    if (run_dir / "ir.yaml").exists() and not force:
        raise IRBuildError(f"{run_dir / 'ir.yaml'} exists; pass --force to overwrite")
    return write_ir(run_dir, skeleton(run_dir))


def derive(run_dir: Path | str) -> Path:
    """Resync implementation_notes in an existing ir.yaml from field statuses."""
    run_dir = Path(run_dir)
    path = run_dir / "ir.yaml"
    if not path.is_file():
        raise IRBuildError(f"no ir.yaml under {run_dir}")
    ir = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(ir, dict):
        raise IRBuildError(f"{path} is not a YAML mapping")
    derive_notes(ir)
    return write_ir(run_dir, ir)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Scaffold or resync a run's ir.yaml.")
    parser.add_argument("run_dir", help="path to runs/<slug>/")
    parser.add_argument("--force", action="store_true", help="overwrite an existing ir.yaml")
    parser.add_argument(
        "--derive",
        action="store_true",
        help="resync implementation_notes.assumptions/unknowns from statuses",
    )
    args = parser.parse_args(argv)
    try:
        path = derive(args.run_dir) if args.derive else build_ir(args.run_dir, force=args.force)
    except IRBuildError as e:
        print(f"ir_build failed: {e}", file=sys.stderr)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
