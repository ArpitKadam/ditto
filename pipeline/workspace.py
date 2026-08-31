"""Run workspace creation and manifest.yaml read/write."""

from datetime import datetime, timezone
from pathlib import Path

import yaml


def create_run(runs_dir: Path | str, slug: str) -> Path:
    """Create runs/<slug>/ with the source/ and figures/ subdirs; idempotent."""
    run_dir = Path(runs_dir) / slug
    (run_dir / "source").mkdir(parents=True, exist_ok=True)
    (run_dir / "figures").mkdir(exist_ok=True)
    return run_dir


def new_manifest(paper_id: str, source_kind: str) -> dict:
    """Fresh manifest per Contract 3 (see ARCHITECTURE.md)."""
    return {
        "paper_id": paper_id,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_kind": source_kind,
        "stages": {
            "ingest": {"status": "pending"},
            "ir": {"status": "pending", "validated": False},
            "explain": {"status": "pending"},
            "code": {"status": "pending", "tier_target": None, "tier_reached": None},
            "visualize": {"status": "pending"},
            "report": {"status": "pending"},
        },
    }


def write_manifest(run_dir: Path | str, manifest: dict) -> None:
    (Path(run_dir) / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def read_manifest(run_dir: Path | str) -> dict:
    return yaml.safe_load(
        (Path(run_dir) / "manifest.yaml").read_text(encoding="utf-8")
    )


def mark_stage(run_dir: Path | str, stage: str, **fields) -> dict:
    """Update one stage's fields in manifest.yaml (e.g. status='done', validated=True)."""
    manifest = read_manifest(run_dir)
    stages = manifest.setdefault("stages", {})
    if stage not in stages:
        raise KeyError(f"unknown stage {stage!r}; expected one of {sorted(stages)}")
    stages[stage].update(fields)
    write_manifest(run_dir, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Run-workspace manifest operations.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    mark = sub.add_parser("mark", help="update a stage: mark <run_dir> <stage> key=value ...")
    mark.add_argument("run_dir")
    mark.add_argument("stage")
    mark.add_argument("fields", nargs="+", help="key=value; values parsed as YAML scalars")
    args = parser.parse_args(argv)
    fields = {}
    for item in args.fields:
        key, sep, value = item.partition("=")
        if not sep or not key:
            print(f"workspace mark failed: expected key=value, got {item!r}", file=sys.stderr)
            return 2
        fields[key] = yaml.safe_load(value)
    try:
        mark_stage(args.run_dir, args.stage, **fields)
    except (KeyError, FileNotFoundError) as e:
        print(f"workspace mark failed: {e}", file=sys.stderr)
        return 2
    print(f"{args.stage}: {fields}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
