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
