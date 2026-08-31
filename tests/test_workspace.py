import pytest

from pipeline import workspace


def test_create_run_makes_layout(tmp_path):
    run_dir = workspace.create_run(tmp_path / "runs", "2106.09685")
    assert run_dir == tmp_path / "runs" / "2106.09685"
    assert (run_dir / "source").is_dir()
    assert (run_dir / "figures").is_dir()


def test_manifest_roundtrip(tmp_path):
    run_dir = workspace.create_run(tmp_path / "runs", "x")
    manifest = workspace.new_manifest("2106.09685", "latex")
    workspace.write_manifest(run_dir, manifest)
    loaded = workspace.read_manifest(run_dir)
    assert loaded == manifest
    assert loaded["paper_id"] == "2106.09685"
    assert loaded["source_kind"] == "latex"
    assert loaded["stages"]["ingest"]["status"] == "pending"
    assert loaded["stages"]["code"] == {
        "status": "pending",
        "tier_target": None,
        "tier_reached": None,
    }


def test_mark_stage_updates_fields(tmp_path):
    run_dir = workspace.create_run(tmp_path / "runs", "x")
    workspace.write_manifest(run_dir, workspace.new_manifest("x", "latex"))
    workspace.mark_stage(run_dir, "ir", status="done", validated=True)
    loaded = workspace.read_manifest(run_dir)
    assert loaded["stages"]["ir"] == {"status": "done", "validated": True}
    assert loaded["stages"]["ingest"]["status"] == "pending"  # untouched


def test_mark_stage_rejects_unknown_stage(tmp_path):
    run_dir = workspace.create_run(tmp_path / "runs", "x")
    workspace.write_manifest(run_dir, workspace.new_manifest("x", "latex"))
    with pytest.raises(KeyError, match="unknown stage"):
        workspace.mark_stage(run_dir, "nope", status="done")


def test_mark_cli_parses_yaml_scalars(tmp_path):
    run_dir = workspace.create_run(tmp_path / "runs", "x")
    workspace.write_manifest(run_dir, workspace.new_manifest("x", "latex"))
    rc = workspace.main(["mark", str(run_dir), "code", "status=done", "tier_target=T1"])
    assert rc == 0
    loaded = workspace.read_manifest(run_dir)
    assert loaded["stages"]["code"]["status"] == "done"
    assert loaded["stages"]["code"]["tier_target"] == "T1"
    assert workspace.main(["mark", str(run_dir), "code", "malformed"]) == 2
