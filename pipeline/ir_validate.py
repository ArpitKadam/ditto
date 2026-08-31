"""Validate ir.yaml: schema shape, provenance lint, status coverage, mirror.

Pure read-only check — never rewrites the IR or the manifest. CLI exits 0 on a
clean IR, 1 with one finding per line on violations, 2 on operational errors.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

from pipeline.ir_build import TRAINING_FIELDS, status_fields

STATUS_VALUES = {"stated", "inferred", "assumed", "unknown"}
SOURCE_KINDS = {"latex", "html", "pdf"}
TOP_SECTIONS = [
    "paper",
    "problem",
    "method",
    "architecture",
    "mathematics",
    "training",
    "evaluation",
    "experiments",
    "figures",
    "implementation_notes",
]
PAPER_KEYS = ["id", "title", "authors", "year", "source_kind", "official_repo", "dependencies"]
EQUATION_KEYS = ["id", "latex", "meaning", "implements", "src"]
_ENV_RE = re.compile(r"\\(begin|end)\{([^}]*)\}")


def latex_balanced(s: str) -> bool:
    """Escape-aware brace balance + matched \\begin/\\end environment pairs."""
    depth = 0
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth < 0:
                return False
        i += 1
    if depth:
        return False
    envs: list[str] = []
    for m in _ENV_RE.finditer(s):
        if m.group(1) == "begin":
            envs.append(m.group(2))
        elif not envs or envs.pop() != m.group(2):
            return False
    return not envs


def _nonempty_str(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _check_status_leaf(path: str, node: dict, findings: list[str]) -> None:
    status = node.get("status")
    if status not in STATUS_VALUES:
        findings.append(f"{path}: status must be one of {sorted(STATUS_VALUES)}, got {status!r}")
        return
    if status in ("stated", "inferred") and not _nonempty_str(node.get("src")):
        findings.append(f"{path}: status {status!r} requires a non-empty src")


def _check_mirror(ir: dict, findings: list[str]) -> None:
    notes = ir.get("implementation_notes")
    if not isinstance(notes, dict):
        findings.append("implementation_notes: missing or not a mapping")
        return
    fields = status_fields(ir)
    want_unknown = {p for p, n in fields.items() if n.get("status") == "unknown"}
    want_assumed = {p for p, n in fields.items() if n.get("status") == "assumed"}

    unknowns = notes.get("unknowns")
    if not isinstance(unknowns, list) or not all(isinstance(u, str) for u in unknowns):
        findings.append("implementation_notes.unknowns: must be a list of dotted field paths")
    else:
        have = set(unknowns)
        for p in sorted(want_unknown - have):
            findings.append(f"implementation_notes.unknowns: missing {p!r} (field is tagged unknown)")
        for p in sorted(have - want_unknown):
            findings.append(f"implementation_notes.unknowns: stale entry {p!r} (field is not tagged unknown)")

    assumptions = notes.get("assumptions")
    if not isinstance(assumptions, list) or not all(isinstance(a, dict) for a in assumptions):
        findings.append("implementation_notes.assumptions: must be a list of {field, value, basis} mappings")
    else:
        have = {a.get("field") for a in assumptions}
        for p in sorted(want_assumed - have):
            findings.append(f"implementation_notes.assumptions: missing {p!r} (field is tagged assumed)")
        for p in sorted(have - want_assumed):
            findings.append(f"implementation_notes.assumptions: stale entry {p!r} (field is not tagged assumed)")

    if not isinstance(notes.get("deviations"), list):
        findings.append("implementation_notes.deviations: must be a list")


def validate_ir(ir, run_dir: Path | None = None) -> list[str]:
    """All findings for an IR mapping; empty list means clean."""
    if not isinstance(ir, dict):
        return ["ir.yaml: not a YAML mapping"]
    findings: list[str] = []
    for sec in TOP_SECTIONS:
        if sec not in ir:
            findings.append(f"{sec}: missing top-level section")
    for key in ir:
        if key not in TOP_SECTIONS:
            findings.append(f"{key}: unknown top-level section")

    paper = ir.get("paper")
    if isinstance(paper, dict):
        for key in PAPER_KEYS:
            if key not in paper:
                findings.append(f"paper.{key}: missing")
        kind = paper.get("source_kind")
        if kind is not None and kind not in SOURCE_KINDS:
            findings.append(f"paper.source_kind: must be one of {sorted(SOURCE_KINDS)}, got {kind!r}")
        repo = paper.get("official_repo")
        if not isinstance(repo, dict) or "url" not in repo or "status" not in repo:
            findings.append("paper.official_repo: must be a {url, status} mapping")
        elif repo["status"] not in STATUS_VALUES:
            findings.append(f"paper.official_repo.status: must be one of {sorted(STATUS_VALUES)}")
    elif "paper" in ir:
        findings.append("paper: not a mapping")

    # status-carrying leaves must exist as mappings before status_fields can see them
    for sec, key in (("problem", "statement"), ("problem", "motivation"), ("method", "summary")):
        if isinstance(ir.get(sec), dict) and not isinstance(ir[sec].get(key), dict):
            findings.append(f"{sec}.{key}: missing or not a {{value, status, src}} mapping")
    if isinstance(ir.get("training"), dict):
        for f in TRAINING_FIELDS:
            if not isinstance(ir["training"].get(f), dict):
                findings.append(f"training.{f}: missing or not a {{value, status, src}} mapping")
    elif "training" in ir:
        findings.append("training: not a mapping")

    for path, node in status_fields(ir).items():
        _check_status_leaf(path, node, findings)

    for i, comp in enumerate((ir.get("method") or {}).get("components") or []):
        path = f"method.components[{i}]"
        if not isinstance(comp, dict):
            findings.append(f"{path}: not a mapping")
            continue
        if not _nonempty_str(comp.get("name")):
            findings.append(f"{path}: name must be non-empty")
        if not _nonempty_str(comp.get("src")):
            findings.append(f"{path}: src must be non-empty")

    for i, eq in enumerate((ir.get("mathematics") or {}).get("equations") or []):
        path = f"mathematics.equations[{i}]"
        if not isinstance(eq, dict):
            findings.append(f"{path}: not a mapping")
            continue
        for key in EQUATION_KEYS:
            if key not in eq:
                findings.append(f"{path}.{key}: missing")
        if not _nonempty_str(eq.get("id")):
            findings.append(f"{path}: id must be non-empty")
        if not _nonempty_str(eq.get("src")):
            findings.append(f"{path}: src must be non-empty")
        latex = eq.get("latex")
        if not _nonempty_str(latex):
            findings.append(f"{path}: latex must be non-empty")
        elif not latex_balanced(latex):
            findings.append(f"{path}: latex has unbalanced braces or \\begin/\\end pairs")

    for i, res in enumerate((ir.get("evaluation") or {}).get("headline_results") or []):
        path = f"evaluation.headline_results[{i}]"
        if not isinstance(res, dict) or not _nonempty_str(res.get("src")):
            findings.append(f"{path}: claimed result requires a non-empty src")

    arch = ir.get("architecture")
    if isinstance(arch, dict):
        diagram = arch.get("diagram")
        if diagram is not None:
            if not _nonempty_str(diagram):
                findings.append("architecture.diagram: must be null or a figures/ path")
            elif run_dir is not None and not (Path(run_dir) / diagram).is_file():
                findings.append(f"architecture.diagram: {diagram!r} does not exist in the run dir")

    _check_mirror(ir, findings)
    return findings


def validate_run(run_dir: Path | str) -> list[str]:
    run_dir = Path(run_dir)
    path = run_dir / "ir.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"no ir.yaml under {run_dir}")
    try:
        ir = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        return [f"ir.yaml: not parseable YAML ({e})"]
    return validate_ir(ir, run_dir=run_dir)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate a run's ir.yaml.")
    parser.add_argument("run_dir", help="path to runs/<slug>/")
    args = parser.parse_args(argv)
    try:
        findings = validate_run(args.run_dir)
    except FileNotFoundError as e:
        print(f"ir_validate failed: {e}", file=sys.stderr)
        return 2
    if findings:
        for f in findings:
            print(f)
        print(f"{len(findings)} finding(s)", file=sys.stderr)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
