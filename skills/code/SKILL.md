---
name: code
description: Implement an ingested paper's method as working, tier-verified code in the run workspace. Use whenever the user asks to implement, reproduce, code up, or train the method of a paper that ditto has ingested, or asks how faithfully an implementation matches a paper.
---

# ditto:code — IR → tier-verified implementation

Produces `runs/<slug>/impl/`: a small package implementing the method, tests,
two configs, and tier evidence in `impl/logs/`. Honesty is the deliverable:
every gap between the paper and the code is either an IR status already, a
recorded deviation, or a bug — never a silent choice.

**Precondition:** manifest shows `ir: {status: done, validated: true}`.
Resume semantics: if `code` is already `done` at the target tier, report and
stop; if partially done, continue from the recorded state.

**References** (read before implementing):
- `references/tiers.md` — what each tier means and the exact evidence files
- `references/implementation-patterns.md` — IR→module mapping discipline
- `references/pytorch-patterns.md` — shape assertions, seeding, smallest-first

## Workflow

### 0. Official repo check

Read `paper.official_repo` from `ir.yaml`. If a URL exists, record in the
implementation plan (step 2): the URL and a one-paragraph diff-validation
plan — which modules/values will be compared against the reference when
end-to-end validation runs. Do not fetch the repo now unless the user asks;
the IR is the source of truth for this stage.

### 1. Declare the target tier

Default T1 (T0 when the session is compute- or time-boxed; T2+ only when the
user asks). Declare it before writing code:

```bash
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python -m pipeline.workspace mark "<runs>/<slug>" code status=in-progress tier_target=T1
```

### 2. Implementation plan

Map the IR to modules before coding: for each `method.components` and each
equation with `implements` set, name the module/class/function that realizes
it. The plan lives as a comment block at the top of the package's
`__init__.py` (small) or `impl/PLAN.md` (large). Every `training.*` value
lands in `config_paper.yaml` with its IR src as a comment; everything the
config needs that the IR tags `assumed`/`unknown` (including supplemental
sub-field entries) is resolved explicitly and recorded (step 4).

### 3. Implement — smallest-first

Build the minimum that can pass the target tier, in dependency order (core
op → layer → model → training loop). Two configs always:

- `config_paper.yaml` — faithful to the IR; values the paper doesn't give
  are filled from the recorded assumption resolutions, marked as such.
- `config_small.yaml` — same code paths, tiny dims/steps; runs in minutes
  on CPU.

Follow `references/pytorch-patterns.md`: deterministic seeding, explicit
shape assertions at module boundaries, no silent broadcasting.

### 4. Deviations — recorded at the moment they happen

Whenever the code departs from what the IR states — a different
tokenization, an added epsilon, an unstated-but-necessary choice, a
simplification — append to `implementation_notes.deviations` in `ir.yaml`
**before writing the next line of code**:

```yaml
- {what: "...", why: "...", ir_field: "training.objective"}
```

Resolving an IR `assumed`/`unknown` (e.g. picking σ for LoRA's A init) is a
deviation entry too — `why` cites the basis. Then re-validate:

```bash
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python -m pipeline.ir_validate "<runs>/<slug>"
```

### 5. Tier evidence

Run the tier checks per `references/tiers.md` and save the evidence files to
`impl/logs/` — a tier without its evidence file was not reached. Tests live
in `impl/tests/` and run with:

```bash
cd "<runs>/<slug>/impl" && uv run pytest tests/ -q
```

### 6. Mark the manifest

Only after the evidence exists:

```bash
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python -m pipeline.workspace mark "<runs>/<slug>" code status=done tier_reached=T0
```

`tier_reached` never exceeds what `impl/logs/` proves. If the target was not
reached, record the tier that *was*, keep status honest, and tell the user
what blocked the rest.

## Done means

`impl/` package + passing tests + both configs + evidence files matching
`tier_reached`; every assumption resolution and departure present in
`implementation_notes.deviations`; manifest consistent. Report: tier
target vs reached, deviation count with one-line list, and the exact
commands to re-run the evidence.
