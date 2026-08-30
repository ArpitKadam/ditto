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
