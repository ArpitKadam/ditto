import yaml

from pipeline import ir_build, ir_validate, workspace


def _clean_ir(tmp_path):
    """A validating IR built from a synthetic workspace."""
    run = workspace.create_run(tmp_path / "runs", "synthetic")
    workspace.write_manifest(run, workspace.new_manifest("2101.00001", "latex"))
    ir_build.build_ir(run)
    ir = yaml.safe_load((run / "ir.yaml").read_text(encoding="utf-8"))
    return run, ir


def _findings(ir, run=None):
    return ir_validate.validate_ir(ir, run_dir=run)


# --- latex balance helper ---------------------------------------------------


def test_latex_balanced_accepts_real_latex():
    assert ir_validate.latex_balanced(r"W_0 + \Delta W = W_0 + BA")
    assert ir_validate.latex_balanced(r"\frac{1}{2}\|x\|^2")
    assert ir_validate.latex_balanced(r"\begin{aligned}a &= b\\c &= d\end{aligned}")
    assert ir_validate.latex_balanced(r"a \{ b")  # escaped brace is literal


def test_latex_balanced_rejects_mangled():
    assert not ir_validate.latex_balanced(r"\frac{1}{2")           # truncated
    assert not ir_validate.latex_balanced(r"a}b")                  # close before open
    assert not ir_validate.latex_balanced(r"\begin{align}x=y")     # unclosed env
    assert not ir_validate.latex_balanced(r"\begin{align}x\end{aligned}")  # mismatch


# --- seeded violations, one per validator rule ------------------------------


def test_clean_ir_validates(tmp_path):
    run, ir = _clean_ir(tmp_path)
    assert _findings(ir, run) == []


def test_missing_top_level_section(tmp_path):
    _, ir = _clean_ir(tmp_path)
    del ir["training"]
    assert any(f.startswith("training: missing") for f in _findings(ir))


def test_unknown_top_level_section_flagged(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["trainnig"] = {}  # typo'd section
    assert any("trainnig: unknown top-level section" in f for f in _findings(ir))


def test_leaf_missing_status(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["training"]["lr"] = {"value": "1e-3", "src": "§5"}
    fs = _findings(ir)
    assert any("training.lr" in f and "status" in f for f in fs)


def test_leaf_invalid_status_value(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["problem"]["statement"]["status"] = "guessed"
    assert any("problem.statement" in f and "'guessed'" in f for f in _findings(ir))


def test_stated_requires_src(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["training"]["objective"] = {"value": "MSE", "status": "stated", "src": ""}
    ir["implementation_notes"]["unknowns"].remove("training.objective")
    assert any("training.objective" in f and "src" in f for f in _findings(ir))


def test_inferred_requires_src(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["method"]["summary"] = {"value": "low-rank update", "status": "inferred", "src": "   "}
    ir["implementation_notes"]["unknowns"].remove("method.summary")
    assert any("method.summary" in f and "src" in f for f in _findings(ir))


def test_mirror_missing_unknown(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["implementation_notes"]["unknowns"].remove("training.lr")
    assert any("missing 'training.lr'" in f for f in _findings(ir))


def test_mirror_stale_unknown(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["training"]["lr"] = {"value": "2e-4", "status": "stated", "src": "§5"}
    assert any("stale entry 'training.lr'" in f for f in _findings(ir))


def test_mirror_missing_assumption(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["training"]["init"] = {"value": "gaussian", "status": "assumed", "src": ""}
    ir["implementation_notes"]["unknowns"].remove("training.init")
    assert any(
        "assumptions: missing 'training.init'" in f for f in _findings(ir)
    )


def test_layers_participate_in_status_checks_and_mirror(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["architecture"]["layers"] = [
        {"name": "embed", "spec": "d=128", "status": "stated", "src": "§3"},
        {"name": "mystery", "spec": "", "status": "unknown", "src": ""},
    ]
    fs = _findings(ir)
    assert any("unknowns: missing 'architecture.layers[1]'" in f for f in fs)
    ir["implementation_notes"]["unknowns"].append("architecture.layers[1]")
    assert _findings(ir) == []


def test_equation_unbalanced_latex(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["mathematics"]["equations"] = [
        {"id": "eq1", "latex": r"\frac{1}{2", "meaning": "half", "implements": "", "src": "§3"}
    ]
    assert any("equations[0]" in f and "unbalanced" in f for f in _findings(ir))


def test_equation_missing_src_and_id(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["mathematics"]["equations"] = [
        {"id": "", "latex": "a=b", "meaning": "", "implements": "", "src": ""}
    ]
    fs = _findings(ir)
    assert any("equations[0]: id" in f for f in fs)
    assert any("equations[0]: src" in f for f in fs)


def test_headline_result_requires_src(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["evaluation"]["headline_results"] = [{"metric": "acc", "value": 0.9, "src": ""}]
    assert any("headline_results[0]" in f for f in _findings(ir))


def test_component_requires_name_and_src(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["method"]["components"] = [{"name": "", "role": "adapter", "src": ""}]
    fs = _findings(ir)
    assert any("components[0]: name" in f for f in fs)
    assert any("components[0]: src" in f for f in fs)


def test_diagram_must_exist_when_run_dir_given(tmp_path):
    run, ir = _clean_ir(tmp_path)
    ir["architecture"]["diagram"] = "figures/fig9.png"
    assert any("diagram" in f and "does not exist" in f for f in _findings(ir, run))
    (run / "figures" / "fig9.png").write_bytes(b"x")
    assert _findings(ir, run) == []


def test_bad_source_kind(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["paper"]["source_kind"] = "docx"
    assert any("paper.source_kind" in f for f in _findings(ir))


def test_non_mapping_ir():
    assert ir_validate.validate_ir(["not", "a", "mapping"]) == ["ir.yaml: not a YAML mapping"]


def test_multiple_seeded_violations_all_reported(tmp_path):
    _, ir = _clean_ir(tmp_path)
    del ir["experiments"]
    ir["problem"]["statement"]["status"] = "bogus"
    ir["mathematics"]["equations"] = [
        {"id": "eq1", "latex": "{", "meaning": "", "implements": "", "src": "§1"}
    ]
    assert len(_findings(ir)) >= 3


# --- supplemental sub-field entries (Task 6 mirror widening) ----------------


def test_supplemental_unknown_accepted(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["implementation_notes"]["unknowns"].append("training.init.sigma_A")
    assert _findings(ir) == []


def test_supplemental_assumption_accepted(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["implementation_notes"]["assumptions"].append(
        {"field": "training.optimizer.adam_betas", "value": "(0.9, 0.999)", "basis": "PyTorch default"}
    )
    assert _findings(ir) == []


def test_supplemental_with_bogus_prefix_rejected(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["implementation_notes"]["unknowns"].append("nonexistent.leaf.detail")
    assert any("neither a tracked leaf nor a sub-detail" in f for f in _findings(ir))


def test_supplemental_does_not_satisfy_missing_auto_entry(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["implementation_notes"]["unknowns"].remove("training.init")
    ir["implementation_notes"]["unknowns"].append("training.init.sigma")  # sub-detail is not the leaf
    assert any("missing 'training.init'" in f for f in _findings(ir))


def test_derive_preserves_supplemental_entries(tmp_path):
    _, ir = _clean_ir(tmp_path)
    ir["implementation_notes"]["unknowns"].append("training.init.sigma_A")
    ir["implementation_notes"]["assumptions"].append(
        {"field": "training.optimizer.adam_betas", "value": "(0.9, 0.999)", "basis": "PyTorch default"}
    )
    ir_build.derive_notes(ir)
    assert "training.init.sigma_A" in ir["implementation_notes"]["unknowns"]
    assert {"field": "training.optimizer.adam_betas", "value": "(0.9, 0.999)", "basis": "PyTorch default"} in ir[
        "implementation_notes"
    ]["assumptions"]
    assert _findings(ir) == []


# --- a hand-filled partial IR must validate clean ---------------------------


def test_hand_filled_partial_ir_validates(tmp_path):
    run, ir = _clean_ir(tmp_path)
    ir["problem"]["statement"] = {
        "value": "Full fine-tuning of large LMs is prohibitively expensive.",
        "status": "stated",
        "src": "§1",
    }
    ir["method"]["summary"] = {
        "value": "Freeze W0; learn a low-rank update BA per weight matrix.",
        "status": "stated",
        "src": "§4.1",
    }
    ir["method"]["components"] = [
        {"name": "LoRA adapter", "role": "trainable low-rank branch", "src": "§4.1"}
    ]
    ir["mathematics"]["equations"] = [
        {
            "id": "eq3",
            "latex": r"W_0 + \Delta W = W_0 + BA",
            "meaning": "adapted weight is frozen base plus low-rank product",
            "implements": "LoRA adapter forward",
            "src": "§4.1 eq3",
        }
    ]
    ir["training"]["optimizer"] = {"value": "AdamW", "status": "stated", "src": "§5 tab9"}
    ir["training"]["lr"] = {"value": "2e-4", "status": "assumed", "src": ""}
    # rest of training stays unknown — a partial fill is valid
    ir_build.derive_notes(ir)
    assert ir_validate.validate_ir(ir, run_dir=run) == []
    # and the mirror reflects exactly the partial state
    assert "problem.statement" not in ir["implementation_notes"]["unknowns"]
    assert ir["implementation_notes"]["assumptions"][0]["field"] == "training.lr"
