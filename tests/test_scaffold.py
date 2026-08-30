import json
from pathlib import Path

import pipeline.extract
import pipeline.fetch
import pipeline.ir_build
import pipeline.ir_validate
import pipeline.workspace  # noqa: F401  (import success is the assertion)

ROOT = Path(__file__).resolve().parents[1]


def test_plugin_manifest_valid():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["name"] == "ditto"
    assert manifest["version"]
    assert manifest["description"]
