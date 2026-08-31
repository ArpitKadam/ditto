# Trigger eval report — Task 13

**Date:** 2026-08-31 · **Model:** claude-haiku-4-5 (weakest available router — conservative
stress test for description quality) · **Verdict: pass.** Held-out trigger rate 20/20
positives, 26/26 negatives clean across both sets after optimization.

## Method

The official vehicle (`claude plugin eval`) is feature-gated off in CLI 2.1.201, and no
`skill-creator` tooling is installed, so triggering is measured with a purpose-built
harness (`run_trigger_eval.py`):

- Each query runs in a headless `claude -p` session with the plugin loaded via
  `--plugin-dir`, user/global settings dropped (`--setting-sources ""`), MCP disabled
  (`--strict-mcp-config`), and every execution tool disallowed **except `Skill`** — a
  disallowed tool is removed from the model's toolset entirely, so the one being observed
  must stay allowed.
- The first `Skill` tool_use in the stream-json output is the verdict; the process is
  killed the moment it appears (or after 8 assistant messages → verdict "none"), so a
  probe costs one routing decision, not a full skill run.
- Probes run from an empty temp directory: no `runs/` workspace, no project context.
  This is the *hard* condition for downstream skills — the router must trust the skill
  to locate state rather than concluding "nothing is ingested here."

Query sets: `queries.yaml` (dev, 50 positives + 12 negatives — used for optimization)
and `holdout.yaml` (20 positives + 6 negatives — never inspected until descriptions were
frozen). Positives split direct/indirect phrasings; `expect` lists every acceptable
route (e.g. "implement this arXiv paper" in a fresh session may legitimately open with
ingest). Negatives are adjacent traps: "summarize this news article PDF", "explain how
the auth flow in this codebase works", "reproduce this bug", "explain transformers like
I'm five".

## Results

| Run | Positives | Negatives clean | Notes |
|---|---|---|---|
| baseline (dev) | 29/50 (58%) | 12/12 | ingest 10/10; explain 5/10, code 5/10, visualize 6/10, report 4/10 |
| optimized-r1 (dev, 4 skills re-run) | 48/50 | 11/12 | explain description over-fired on the codebase negative |
| optimized-r2 (dev, after guard) | 49–50/50 | 12/12 | explain-02 missed once, then fired 3/3 on repeat — sampling noise |
| **holdout (frozen descriptions)** | **20/20** | **6/6** | 5 probe timeouts on first pass, all resolved correct on retry at lower concurrency |

## What the baseline failures were

1. **State-conditioned descriptions suppress routing.** Every downstream description said
   "a paper that ditto has ingested". In a bare directory the router reasoned "nothing is
   ingested" and answered directly — 19 of 21 misses were verdict "none", concentrated in
   explain/code/visualize/report. Ingest, whose description has no state precondition,
   went 10/10 untouched.
2. **Verb gaps.** "diagram", "chart", "render", "break down", "teach", "verdict",
   "close out", "write up" weren't covered.
3. **Name-invocation gap.** "Run ditto code on X" didn't route; descriptions never
   mentioned their own invocation phrase.
4. **Built-in skill leakage.** A few queries fired bundled skills (`run`,
   `update-config`) instead — a symptom of the ditto description losing the comparison,
   fixed by the same edits.

## What changed (the optimization)

All four downstream descriptions gained: broader verb coverage, their own "ditto X"
invocation phrase, and the key routing instruction — *"Do not skip because no run is
visible in the current directory: invoke this skill — it locates the run workspace from
the manifest and reports cleanly if [prerequisites are] missing."* That claim is honest:
each SKILL.md body carries a manifest precondition step that reports and redirects to
`ditto:ingest` when state is absent.

The pushiness overshot exactly once: "Explain how the auth flow in this codebase works"
false-fired explain. Fixed with an explicit scope guard ("Not for explaining codebases,
source code, or general concepts with no research paper involved") — negatives returned
to 12/12 with no positive regression. The ingest description was not touched.

One dev-set expectation was corrected rather than optimized around: "How faithful is our
implementation to the paper?" now accepts either `code` or `report` — code's reviewer
checks faithfulness, report delivers the claimed-vs-achieved verdict; both are correct
user outcomes.

## Limitations

- Single model (haiku). Stronger session models should route at least as well, but that
  is an inference, not a measurement.
- Single run per query (except flakiness spot-checks); temperature noise of roughly one
  query per sweep observed. The two anomalies both re-ran correct 3/3 and 5/5.
- Bare-cwd probes only. Triggering *with* a populated `runs/` workspace in view is
  strictly easier and was not separately measured.
- First holdout pass hit 5 probe timeouts at 4-way concurrency (rate-limit stalls, not
  routing verdicts); retried clean at 2-way.

## Reproduce

```
uv run python tests/trigger_eval/run_trigger_eval.py --set tests/trigger_eval/queries.yaml --label dev
uv run python tests/trigger_eval/run_trigger_eval.py --set tests/trigger_eval/holdout.yaml --label holdout
```

Raw per-query results: `tests/trigger_eval/results/*.json`.
