# PyTorch patterns for reproduction code

## Determinism

Every entry point (test, training script) seeds first:

```python
torch.manual_seed(cfg["seed"])  # seed lives in the config, echoed in evidence headers
```

Shape tests and T0 evidence run on CPU — reproducible on a machine with no
GPU. Training (T1+) takes its device from the config
(`device: cuda` when available, falling back to CPU with a printed notice);
never hardcoded.

## Shape assertions, not shape comments

Assert at module boundaries with messages that name the symbol from the
paper:

```python
assert x.shape == (b, k), f"x expected (batch, k={self.k}), got {tuple(x.shape)}"
```

- Assert on the *symbolic* dims from the IR (`r`, `d`, `k`), not magic
  numbers — tests then exercise both configs unchanged.
- One test drives a dummy forward through every module and prints the
  boundary shapes it asserted (this printout is the T0 evidence's shape
  section).
- Parameter accounting is a shape test too: assert trainable/frozen counts
  match the IR's formulas (e.g. LoRA: trainable = 2·L·d·r).

## Frozen-parameter hygiene

When the method freezes weights (`requires_grad=False`), test it:

```python
loss.backward()
assert base.weight.grad is None          # frozen path got no gradient
assert lora.A.grad is not None           # trainable path did
```

A single backward-pass test like this catches the most common reproduction
bug class (accidentally trainable/frozen parameters) at T0 cost.

## Numerics

- `float32` unless the paper's recipe demands otherwise (an IR-recorded
  deviation if changed).
- Compare tensors with `torch.testing.assert_close`, never `==`.
- Zero-init claims are tested (`assert (B == 0).all()` after construction;
  method output equals base output at init when the paper says ΔW = 0).

## Keep the surface small

`nn.Module` subclasses with explicit `__init__(dims...)` signatures taken
from the config; no registry/factory/abstract-base machinery. One file per
concept until a file exceeds ~200 lines.
