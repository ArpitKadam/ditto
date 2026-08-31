# explain.md template

Structure for `runs/<slug>/explain.md`. Section order is fixed; depth scales
with the paper. Write for a competent ML practitioner who has NOT read the
paper. Every paper-specific fact traces to the IR (and through it, the paper);
statuses are surfaced inline where confidence is less than `stated`.

```markdown
# <Title> — explained

> <one-line what-this-paper-does>, from arXiv <id> (<year>).
> Generated from the ditto Paper IR; confidence tags: **[inferred]**,
> **[assumed: basis]**, **[unknown]** — untagged facts are stated in the paper.

## The problem

<problem.statement + motivation, 1–3 paragraphs. Why existing approaches
fall short, with the paper's own numbers where the IR has them.>

## The idea in one paragraph

<The core mechanism, intuition-first — the paragraph a reader should be able
to repeat back. Built from method.summary.>

## The method, step by step

<Walkthrough keyed to mathematics.equations, in logical (not necessarily
paper) order. For each equation:>

$$<expanded, self-contained LaTeX>$$

<what each symbol is, what the equation *does* for the method, and which
component (method.components / architecture.layers) implements it. Meaning,
not restatement: "this says the update lives in a rank-r subspace", not "this
is the equation for Delta W".>

## Architecture

![architecture](figures/figN.png)   <!-- when architecture.diagram is set -->

<architecture.inputs, then layers in order. A table works when layers are
homogeneous; prose when they are not. Tag every non-stated layer:
"bottleneck block **[assumed: standard U-Net convention — paper is silent]**".>

## Training recipe

| field | value | confidence | src |
|-------|-------|------------|-----|
<all ten training.* fields, values possibly abbreviated but never distorted;
confidence column shows the status; assumed rows include their basis.>

<Prose notes under the table for anything multi-setting ("primary setting
shown; RoBERTa/GPT-3 variants in ir.yaml") or subtle (EMA, label smoothing,
where dropout applies).>

## What the paper claims

<evaluation.headline_results as a short list with their srcs — the numbers a
reproduction will be measured against.>

## What you'd have to guess to reproduce this

<implementation_notes.assumptions: each with value + basis.
implementation_notes.unknowns: each with one line on why it matters.
This section is the honest core — it must let the reader list every
assumption without opening the paper.>

## IR gaps found while explaining

<Empty ("None — the IR supported this explanation fully.") or a list:
{what was missing, where the explanation had to look instead, what the IR
should have contained}.>
```

## Self-check before finishing

- [ ] A reader could state the core mechanism from "The idea in one
      paragraph" alone.
- [ ] Every equation is `$$`-wrapped, self-contained (no author macros, no
      `\label`), and paired with meaning.
- [ ] Diagram embedded as PNG when `architecture.diagram` is set.
- [ ] All ten training fields present with confidence column.
- [ ] Every `assumed`/`unknown` from the IR appears in "What you'd have to
      guess".
- [ ] No paper-specific claim that is absent from ir.yaml + source.
- [ ] IR-gaps section present (even when empty).
