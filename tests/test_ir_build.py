import pytest
import yaml

from pipeline import ir_build, ir_validate, workspace


def _make_run(tmp_path, with_meta=True, with_figures_yaml=True):
    run = workspace.create_run(tmp_path / "runs", "synthetic")
    workspace.write_manifest(run, workspace.new_manifest("2101.00001", "latex"))
    if with_meta:
        (run / "fetch_meta.yaml").write_text(
            yaml.safe_dump(
                {
                    "arxiv_id": "2101.00001",
                    "title": "A Synthetic Paper",
                    "authors": ["Ada Lovelace", "Alan Turing"],
                    "year": 2021,
                    "official_repo_candidates": ["https://github.com/example/repo"],
                }
            ),
            encoding="utf-8",
        )
    if with_figures_yaml:
        (run / "figures" / "figures.yaml").write_text(
            yaml.safe_dump(
                [
                    {"id": "fig1", "file": "figures/fig1.pdf", "original": "a.pdf", "caption": "Arch."},
                    {"id": "fig2", "file": "figures/fig2.png", "original": "b.png", "caption": ""},
                ]
            ),
            encoding="utf-8",
        )
    return run


def _read_ir(run):
    return yaml.safe_load((run / "ir.yaml").read_text(encoding="utf-8"))


def test_build_prefills_metadata_and_figures(tmp_path):
    run = _make_run(tmp_path)
    ir_build.build_ir(run)
    ir = _read_ir(run)
    assert ir["paper"]["id"] == "2101.00001"
    assert ir["paper"]["title"] == "A Synthetic Paper"
    assert ir["paper"]["authors"] == ["Ada Lovelace", "Alan Turing"]
    assert ir["paper"]["year"] == 2021
    assert ir["paper"]["source_kind"] == "latex"
    assert ir["paper"]["official_repo"] == {
        "url": "https://github.com/example/repo",
        "status": "stated",
    }
    assert ir["figures"] == [
        {"id": "fig1", "file": "figures/fig1.pdf", "caption": "Arch."},
        {"id": "fig2", "file": "figures/fig2.png", "caption": ""},
    ]


def test_build_skeleton_validates_clean(tmp_path):
    run = _make_run(tmp_path)
    ir_build.build_ir(run)
    assert ir_validate.validate_run(run) == []


def test_build_all_leaves_unknown_and_mirrored(tmp_path):
    run = _make_run(tmp_path)
    ir_build.build_ir(run)
    ir = _read_ir(run)
    fields = ir_build.status_fields(ir)
    assert len(fields) == 13  # 2 problem + 1 method + 10 training; no layers yet
    assert all(n["status"] == "unknown" for n in fields.values())
    assert sorted(ir["implementation_notes"]["unknowns"]) == sorted(fields)
    assert ir["implementation_notes"]["assumptions"] == []


def test_build_without_meta_or_figures_yaml(tmp_path):
    run = _make_run(tmp_path, with_meta=False, with_figures_yaml=False)
    (run / "figures" / "fig1.png").write_bytes(b"x")
    (run / "figures" / "fig2.png").write_bytes(b"x")
    ir_build.build_ir(run)
    ir = _read_ir(run)
    assert ir["paper"]["id"] == "2101.00001"  # from manifest
    assert ir["paper"]["title"] is None
    assert ir["paper"]["official_repo"] == {"url": None, "status": "unknown"}
    assert ir["figures"] == [
        {"id": "fig1", "file": "figures/fig1.png", "caption": ""},
        {"id": "fig2", "file": "figures/fig2.png", "caption": ""},
    ]
    assert ir_validate.validate_ir(ir, run_dir=run) == []


def test_build_refuses_overwrite_without_force(tmp_path):
    run = _make_run(tmp_path)
    ir_build.build_ir(run)
    with pytest.raises(ir_build.IRBuildError, match="--force"):
        ir_build.build_ir(run)
    ir_build.build_ir(run, force=True)  # explicit force succeeds


def test_derive_resyncs_mirror_and_keeps_basis(tmp_path):
    run = _make_run(tmp_path)
    ir_build.build_ir(run)
    ir = _read_ir(run)
    ir["training"]["lr"] = {"value": "2e-4", "status": "assumed", "src": ""}
    ir["training"]["optimizer"] = {"value": "AdamW", "status": "stated", "src": "§5"}
    # stale mirror on purpose; then a prior basis that must survive the resync
    ir["implementation_notes"]["assumptions"] = [
        {"field": "training.lr", "value": "old", "basis": "typical for this model size"}
    ]
    ir_build.write_ir(run, ir)
    ir_build.derive(run)
    ir = _read_ir(run)
    assert ir["implementation_notes"]["assumptions"] == [
        {"field": "training.lr", "value": "2e-4", "basis": "typical for this model size"}
    ]
    assert "training.lr" not in ir["implementation_notes"]["unknowns"]
    assert "training.optimizer" not in ir["implementation_notes"]["unknowns"]
    assert "training.dataset" in ir["implementation_notes"]["unknowns"]
    assert ir_validate.validate_run(run) == []


def test_header_comment_survives_write(tmp_path):
    run = _make_run(tmp_path)
    ir_build.build_ir(run)
    text = (run / "ir.yaml").read_text(encoding="utf-8")
    assert text.startswith("# Paper IR")
    ir_build.derive(run)
    assert (run / "ir.yaml").read_text(encoding="utf-8").startswith("# Paper IR")


def test_build_missing_run_dir_fails_explicitly(tmp_path):
    with pytest.raises(ir_build.IRBuildError, match="not a run directory"):
        ir_build.build_ir(tmp_path / "nope")
