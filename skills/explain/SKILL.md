---
name: explain
description: Generate a human-readable walkthrough (explain.md) of an ingested research paper from its Paper IR. Use whenever the user asks to explain, summarize, walk through, or understand a paper that ditto has ingested, or after ditto:ingest completes and the user wants the paper explained.
---

# ditto:explain — IR → explain.md walkthrough

Produces `runs/<slug>/explain.md`: a walkthrough a reader can follow cold —
stating the method's core mechanism and every assumption without opening the
paper. Doubles as IR validation: writing a good explanation exposes a thin IR.

**Precondition:** `manifest.yaml` shows `ir: {status: done, validated: true}`.
If not, run `ditto:ingest` first. If `explain: done` and `explain.md` exists,
report that and stop (resume semantics).

## Source discipline

- **IR-first.** Every claim in `explain.md` comes from `ir.yaml`. When the IR
  is too thin to explain something, follow its `src` pointer into `paper.md` /
  `source/` — and record that zoom-in as an IR gap (see below). No claims from
  memory or general knowledge of the paper; general ML background (what a
  U-Net is, what cross-entropy is) is allowed for *intuition*, never for
  paper-specific facts.
- **Confidence is content.** `stated / inferred / assumed / unknown` statuses
  appear in the walkthrough. Never present an `assumed` value as fact; never
  omit an `unknown` that an implementer would need.

## Math rendering — self-contained LaTeX only

`explain.md` must render in a plain Markdown preview:

- Wrap display equations in `$$…$$`, inline math in `$…$`.
- **Expand author-defined macros.** IR equation LaTeX is verbatim from the
  paper and may use preamble shorthands (`\bmu`, `\defeq`, `\Eb{...}{...}`,
  `\cZ`, …). Look up their `\newcommand` definitions in the `source/` preamble
  and substitute until only standard LaTeX remains (`\boldsymbol{\mu}`,
  `\triangleq`, `\mathbb{E}[...]`, `\mathcal{Z}`). Drop `\label{}`. Do NOT
  edit `ir.yaml` — the IR stays verbatim; expansion happens only here.
- Every equation gets prose meaning next to it — rendered *and* explained,
  never just restated.

## Diagram embedding

If `architecture.diagram` is set and points at a vector file (`.pdf`/`.eps`),
rasterize it first, then embed the PNG with a relative path:

```bash
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python -m pipeline.rasterize "<runs>/<slug>/figures/figN.pdf"
```

```markdown
![architecture](figures/figN.png)
```

## Workflow

1. Read `ir.yaml` in full. Read `manifest.yaml`.
2. Write `runs/<slug>/explain.md` following
   `${CLAUDE_PLUGIN_ROOT}/skills/explain/references/explanation-template.md`.
3. While writing, keep an **IR gaps** list: every time the IR alone could not
   support the explanation and you zoomed into `source/` via a `src` pointer,
   record `{what was missing, where you had to look, what the IR should have
   contained}`. The finished document ends with this list (or states it is
   empty). A non-empty list means the IR was deficient — surface it to the
   user; schema-level fixes need a decision entry.
4. Self-check against the template's checklist (bottom of the template).
5. Mark the stage:

```bash
uv run --directory "${CLAUDE_PLUGIN_ROOT}" python -m pipeline.workspace mark "<runs>/<slug>" explain status=done
```

## Done means

`explain.md` exists, renders (math + diagram) in a Markdown preview, ends
with the IR-gaps section, and the manifest shows `explain: done`. Report to
the user: one-paragraph method summary, the count of assumptions/unknowns
surfaced, and the IR-gap count.
