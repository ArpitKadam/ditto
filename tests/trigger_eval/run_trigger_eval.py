"""Trigger eval harness: does each query fire the right ditto skill?

For every query in the eval set, launches a headless `claude -p` session with
the plugin loaded (--plugin-dir), user/global settings dropped, MCP disabled,
and every execution tool disallowed except the Skill tool. The first
`Skill` tool_use in the stream-json output is the verdict; the process is
killed the moment it appears, so a probe costs one routing decision, not a
full skill run.

Not a pytest module on purpose: each probe is a real model call. Run manually:

    uv run python tests/trigger_eval/run_trigger_eval.py --set tests/trigger_eval/queries.yaml --label baseline
    uv run python tests/trigger_eval/run_trigger_eval.py --set tests/trigger_eval/holdout.yaml --label holdout

Results land in tests/trigger_eval/results/<label>.json plus a printed
summary. Exit code 1 if any negative fires or any positive misses.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

DISALLOWED_TOOLS = [
    "Bash", "PowerShell", "Write", "Edit", "Read", "Glob", "Grep",
    "Task", "WebFetch", "WebSearch", "TodoWrite", "NotebookEdit",
]

SKILL_CALL_RE = re.compile(r'"name":"Skill".*?"skill":"([^"]+)"')

# Give up on a probe if the model produced this many assistant messages
# without invoking any skill — it is answering directly, verdict "none".
MAX_ASSISTANT_MESSAGES = 8
PROBE_TIMEOUT_S = 150


def resolve_claude() -> list[str]:
    """Return the argv prefix that launches the claude CLI on this machine."""
    exe = shutil.which("claude.exe") or shutil.which("claude")
    if exe is None:
        sys.exit("claude CLI not found on PATH")
    if exe.lower().endswith(".exe"):
        return [exe]
    if exe.lower().endswith(".cmd"):
        return ["cmd", "/c", exe]
    if exe.lower().endswith(".ps1"):
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", exe]
    return [exe]


def run_probe(claude_argv: list[str], query: str, plugin_dir: str, model: str,
              probe_cwd: str) -> dict:
    """One headless session; returns {'triggered': skill-or-none, 'error': ...}."""
    cmd = claude_argv + [
        "-p", query,
        "--plugin-dir", plugin_dir,
        "--model", model,
        "--output-format", "stream-json",
        "--verbose",
        "--setting-sources", "",
        "--strict-mcp-config",
        "--disallowedTools", *DISALLOWED_TOOLS,
    ]
    start = time.monotonic()
    proc = subprocess.Popen(
        cmd, cwd=probe_cwd,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
    )
    triggered = "none"
    assistant_msgs = 0
    # Watchdog: line iteration below blocks on a silent child; hard-kill on timeout.
    timer = threading.Timer(PROBE_TIMEOUT_S, proc.kill)
    timer.start()
    try:
        for line in proc.stdout:
            m = SKILL_CALL_RE.search(line)
            if m:
                triggered = m.group(1)
                break
            if '"type":"assistant"' in line:
                assistant_msgs += 1
                if assistant_msgs >= MAX_ASSISTANT_MESSAGES:
                    break
            if '"type":"result"' in line:
                break
    finally:
        timer.cancel()
        proc.kill()
        proc.wait()
    elapsed = time.monotonic() - start
    if elapsed >= PROBE_TIMEOUT_S:
        return {"triggered": "error", "error": f"timeout after {PROBE_TIMEOUT_S}s"}
    return {"triggered": triggered, "seconds": round(elapsed, 1)}


def normalize(skill: str) -> str:
    """'ditto:ingest' -> 'ingest'; non-ditto skills stay verbatim."""
    return skill.split(":", 1)[1] if skill.startswith("ditto:") else skill


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", dest="query_set", default="tests/trigger_eval/queries.yaml")
    ap.add_argument("--label", default="run")
    ap.add_argument("--only", help="comma-separated query ids to (re)run")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--plugin-dir", default=str(REPO_ROOT))
    args = ap.parse_args()

    queries = yaml.safe_load(Path(args.query_set).read_text(encoding="utf-8"))["queries"]
    if args.only:
        wanted = set(args.only.split(","))
        queries = [q for q in queries if q["id"] in wanted]

    claude_argv = resolve_claude()
    probe_cwd = tempfile.mkdtemp(prefix="ditto-trigger-probe-")
    results = {}

    def work(q):
        return q["id"], run_probe(claude_argv, q["query"], args.plugin_dir,
                                  args.model, probe_cwd)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(work, q) for q in queries]
        for fut in as_completed(futures):
            qid, res = fut.result()
            results[qid] = res
            print(f"  {qid}: {res['triggered']}", flush=True)

    # Score
    rows, misses, false_fires, errors = [], [], [], []
    for q in queries:
        res = results[q["id"]]
        got = normalize(res["triggered"])
        expect = q["expect"]
        if got == "error":
            ok = False
            errors.append(q["id"])
        elif expect == ["none"]:
            ok = not got.startswith("ditto") and got not in {
                "ingest", "explain", "code", "visualize", "report"}
            if not ok:
                false_fires.append((q["id"], got))
        else:
            ok = got in expect
            if not ok:
                misses.append((q["id"], q["query"], expect, got))
        rows.append({"id": q["id"], "kind": q["kind"], "query": q["query"],
                     "expect": expect, "got": got, "ok": ok})

    positives = [r for r in rows if r["expect"] != ["none"]]
    negatives = [r for r in rows if r["expect"] == ["none"]]
    pos_ok = sum(r["ok"] for r in positives)
    neg_ok = sum(r["ok"] for r in negatives)

    summary = {
        "label": args.label,
        "set": args.query_set,
        "model": args.model,
        "positives": f"{pos_ok}/{len(positives)}",
        "negatives_clean": f"{neg_ok}/{len(negatives)}",
        "misses": [{"id": m[0], "expect": m[2], "got": m[3]} for m in misses],
        "false_fires": [{"id": f[0], "got": f[1]} for f in false_fires],
        "errors": errors,
        "rows": rows,
    }
    out_dir = REPO_ROOT / "tests" / "trigger_eval" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.label}.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\n{args.label}: positives {pos_ok}/{len(positives)}, "
          f"negatives clean {neg_ok}/{len(negatives)}")
    for m in misses:
        print(f"  MISS {m[0]}: expected {m[2]}, got {m[3]}")
    for f in false_fires:
        print(f"  FALSE-FIRE {f[0]}: got {f[1]}")
    for e in errors:
        print(f"  ERROR {e}")
    print(f"results -> {out_path}")

    shutil.rmtree(probe_cwd, ignore_errors=True)
    return 0 if (pos_ok == len(positives) and neg_ok == len(negatives) and not errors) else 1


if __name__ == "__main__":
    sys.exit(main())
