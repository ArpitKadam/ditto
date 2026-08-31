"""Viz scripts run clean on synthetic workspace state and produce PNGs."""

import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

SCRIPTS = Path(__file__).parent.parent / "skills" / "visualize" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import architecture_viz
import attention_viz
import training_viz


@pytest.fixture
def run_dir(tmp_path):
    ir = {
        "paper": {"id": "0000.00000", "title": "Synthetic Paper"},
        "architecture": {
            "inputs": ["x: a vector — §1"],
            "layers": [
                {"name": "encoder", "spec": "a $stated$ layer " * 30,
                 "status": "stated", "src": "§2"},
                {"name": "mystery", "spec": "", "status": "unknown", "src": ""},
            ],
            "diagram": None,
        },
    }
    (tmp_path / "ir.yaml").write_text(yaml.safe_dump(ir), encoding="utf-8")
    return tmp_path


def test_architecture_viz(run_dir):
    out = run_dir / "viz" / "architecture.png"
    architecture_viz.render(run_dir, out)
    assert out.stat().st_size > 1000


def test_training_viz_t1_and_t2(run_dir):
    logs = run_dir / "impl" / "logs"
    logs.mkdir(parents=True)
    (logs / "t1_overfit.csv").write_text(
        "# produced by: synthetic\nstep,loss\n0,4.0\n1,0.4\n2,0.004\n",
        encoding="utf-8",
    )
    trend = logs / "t2_trend"
    trend.mkdir()
    (trend / "frozen.csv").write_text(
        "# arm: frozen baseline — no training\n# metric: val loss = NLL\n"
        "# produced by: synthetic\nstep,val_loss\n0,3.6\n",
        encoding="utf-8",
    )
    (trend / "method.csv").write_text(
        "# arm: method r=4 — trained\nstep,train_loss,val_loss\n"
        "100,3.0,2.2\n200,2.5,1.9\n",
        encoding="utf-8",
    )
    training_viz.main([str(run_dir)])
    assert (run_dir / "viz" / "training_t1.png").stat().st_size > 1000
    assert (run_dir / "viz" / "training_t2.png").stat().st_size > 1000


def test_training_viz_no_logs_exits(run_dir):
    with pytest.raises(SystemExit):
        training_viz.main([str(run_dir)])


def test_attention_viz(run_dir):
    dump = run_dir / "impl" / "logs" / "attention"
    dump.mkdir(parents=True)
    rng = np.random.default_rng(0)
    a = rng.random((4, 4))
    a /= a.sum(axis=1, keepdims=True)
    np.savez(dump / "case0.npz",
             layer0_head0=a, layer0_head1=a.T,
             tokens=np.array(["a", "b", "c", "d"]))
    attention_viz.main([str(run_dir)])
    assert (run_dir / "viz" / "attention_case0.png").stat().st_size > 1000


def test_attention_viz_no_dumps_exits(run_dir):
    with pytest.raises(SystemExit):
        attention_viz.main([str(run_dir)])
