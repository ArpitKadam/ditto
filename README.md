# ditto

A Claude Code plugin that turns a research paper into an explained, implemented, visualized, and reported reproduction.

Give it an arXiv ID, an arXiv URL, or a local PDF. It fetches the paper at the highest-fidelity source available (LaTeX e-print → HTML → PDF), distills it into a machine-checkable **Paper IR** where every field carries a confidence status and a source pointer, then walks the reproduction through explanation, tier-verified implementation, visualization, and an honest final report. All state lives on the filesystem — any skill can pick up a half-finished run in a fresh session.

## Skills

| Skill | What it does |
|-------|--------------|
| `ditto:ingest` | Fetch + normalize the paper, build and validate `ir.yaml`, audit it for fabricated provenance |
| `ditto:explain` | Human-readable walkthrough of the method, equations rendered with meaning, unknowns surfaced honestly |
| `ditto:code` | Implement the method in PyTorch, verified against explicit reproduction tiers (T0–T3) |
| `ditto:visualize` | Architecture, training-curve, and (when warranted) attention visualizations |
| `ditto:report` | Reproduction report: claimed vs. achieved, assumptions, deviations, verdict — no number without a source |

Three fresh-context reviewer agents ship with the plugin and are spawned automatically at quality gates: `ditto:ir-auditor`, `ditto:implementation-reviewer`, `ditto:viz-reviewer`.

## Requirements

- [Claude Code](https://claude.com/claude-code) 2.x
- [uv](https://docs.astral.sh/uv/) (manages the Python environment; Python 3.11.5+ is resolved automatically)

## Install

**From the marketplace (persistent):**

```
/plugin marketplace add ArpitKadam/ditto
/plugin install ditto@ditto
```

**From a local checkout (this session only):**

```bash
claude --plugin-dir /path/to/ditto
```

Core Python dependencies (PyMuPDF, PyYAML, matplotlib, transformers) sync automatically the first time a skill runs a pipeline command — no manual step.

### PyTorch (required for `ditto:code`, optional otherwise)

Torch is deliberately not a locked dependency — the right build depends on your hardware. Install it into the plugin's environment from the plugin root directory (for a marketplace install, find it with `claude plugin list`):

```bash
# NVIDIA GPU (CUDA 13.2):
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu132

# CPU only:
uv pip install torch torchvision
```

`ditto:ingest`, `ditto:explain`, and `ditto:report` work without torch.

### First-run downloads

Expect network activity on first use: the paper source from arXiv, Hugging Face model weights when an implementation fine-tunes a pretrained model (e.g. GPT-2, ~500 MB), and torchvision datasets (MNIST/CIFAR) for image papers.

## Quickstart

In any project directory:

```
> Reproduce arXiv 2106.09685
```

`ditto:ingest` fires first and builds the validated IR. Then ask for what you want next — "explain it", "implement it to T1", "visualize the training run", "write the reproduction report" — each skill reads the workspace and continues. Everything lands in `runs/<paper-id>/` under your project:

```
runs/<paper-id>/
├── source/        # fetched LaTeX / HTML / PDF
├── figures/       # extracted figure assets
├── paper.md       # normalized text, math preserved verbatim
├── ir.yaml        # the Paper IR — every field {value, status, src}
├── manifest.yaml  # stage tracker; makes runs resumable
├── impl/          # implementation, configs, tier evidence in impl/logs/
├── viz/           # visualizations
├── explain.md     # the walkthrough
└── report.md      # the reproduction report
```

## Reproduction tiers

`ditto:code` declares a target tier up front and claims nothing without evidence on disk:

| Tier | Meaning | Evidence |
|------|---------|----------|
| T0 | Code runs | clean imports, forward pass, shape assertions |
| T1 | Learns at all | single-batch overfit to ~zero loss, logged curve |
| T2 | Trend reproduces | scaled-down run beats baseline directionally |
| T3 | Numbers reproduce | matches headline results within declared tolerance |

Default target is T1 (T2 where compute permits); T3 is opt-in.

## Honesty model

The pipeline is built around not lying about papers:

- Every IR field is `stated`, `inferred`, `assumed`, or `unknown` — with a source pointer a reader can check. A fresh-context auditor samples claims against the source before ingest completes.
- Every deviation from the paper is logged the moment it happens, not reconstructed later.
- The final report contains no number without a source, and claims the paper's results are reproduced only at T3 — below that, "not attempted" is the recorded answer.

## Development

```bash
git clone https://github.com/ArpitKadam/ditto
cd ditto
uv run pytest -q          # offline suite
uv run pytest -q -m network   # live arXiv tests
claude plugin validate .
```

Deterministic work lives in `pipeline/` (fetch, extract, IR build/validate, workspace manifest); skills stay thin and call it via `uv run`.

## License

Apache-2.0
