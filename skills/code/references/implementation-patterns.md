# Implementation patterns — IR → modules

## The mapping discipline

Code structure follows the IR, not habit:

- Each `method.components` entry → one module, class, or clearly named
  function. The component's `name` appears in the code name
  (`low_rank_decomposition` → `LoRALinear`, `zero_init_update` → its
  `reset_parameters`).
- Each equation with `implements` set → a docstring reference at the exact
  code site (`# implements eq3: h = W0 x + BA x`). Reviewers diff equation
  against code line-by-line; make that diff trivial.
- `architecture.layers` order → construction order in the model class.
- Every `training.*` value → a key in `config_paper.yaml`, with its IR src
  as an inline comment. The training loop reads the config; no hyperparameter
  literals in code.

## Resolving assumed/unknown values

The config must be runnable, so every `assumed`/`unknown` (including
supplemental sub-field entries like `training.init.sigma_A`) gets an
explicit resolution:

1. Pick a value with a defensible basis (framework default, cited-work
   convention, the IR assumption's own basis).
2. Record it as a deviation (`{what, why, ir_field}`) — the `why` is the
   basis, not "had to pick something".
3. Mark the config line: `sigma_a: 0.02  # RESOLVED unknown training.init.sigma_A — nn.init default-scale convention`.

Never resolve silently, never resolve twice differently.

## Smallest-first ordering

1. Core op as a pure function/module + its shape test.
2. Composition into the paper's architecture unit.
3. Model assembly (config-driven dims).
4. Training loop (only what the target tier needs — T0 needs none).

Stop at the target tier's needs. A T0 target does not get a trainer,
a scheduler, checkpointing, or CLI flags "for later".

## What goes where

```
impl/
├── <package>/           # named after the method (lora/, ddpm/, …)
│   ├── __init__.py      # implementation plan comment (small projects)
│   └── *.py
├── tests/
│   ├── conftest.py      # sys.path bootstrap (2 lines)
│   └── test_shapes.py   # T0: boundary shape assertions + param counts
├── config_paper.yaml    # faithful; src comments; RESOLVED markers
├── config_small.yaml    # same keys, tiny values; minutes on CPU
└── logs/                # tier evidence (see tiers.md)
```
