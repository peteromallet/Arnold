#!/usr/bin/env python3
"""Run a matrix of vibecomfy-executor scenarios and report outcomes.

Usage (from the VibeComfy repo root):
    PYTHONPATH=/path/to/arnold python run_matrix.py

Each scenario gets its own plan dir under /tmp. The script prints a markdown
summary with the routed plan, whether research/implement/reply succeeded, and
any obvious errors.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
VIBECOMFY_ROOT = Path.cwd()
PYTHONPATH = str(REPO_ROOT)

MATRIX: list[dict[str, Any]] = [
    {
        "name": "respond-only",
        "query": "Hello what can you do",
    },
    {
        "name": "research-only-text",
        "query": "What are the best KSampler settings for photorealistic images and summarize them",
    },
    {
        "name": "implement-only-text",
        "query": "Write a Python function that adds two numbers",
    },
    {
        "name": "simple-graph-edit-flat",
        "query": "Set the KSampler seed to 12345 and the steps to 30",
        "graph": "tests/fixtures/agent_edit/flat.json",
    },
    {
        "name": "complex-graph-edit-flat",
        "query": "Add an ImageScaleBy node after VAEDecode with scale 2.0 and wire it to SaveImage then set the SaveImage prefix to upscaled",
        "graph": "tests/fixtures/agent_edit/flat.json",
    },
    {
        "name": "research-plus-implement-wan",
        "query": "Research the best WAN t2v settings for 512x512 49 frames and apply them to the workflow",
        "graph": "ready_templates/sources/official/video/wan_t2v.json",
    },
    {
        "name": "research-graph-flat",
        "query": "Explain the purpose of each node in this workflow",
        "graph": "tests/fixtures/agent_edit/flat.json",
    },
    {
        "name": "complex-graph-edit-wan",
        "query": "Add a SaveImage node after the CreateVideo node and wire it so I can preview the video frames",
        "graph": "ready_templates/sources/official/video/wan_t2v.json",
    },
    {
        "name": "complex-graph-edit-qwen",
        "query": "Set the ImageScaleToTotalPixels upscale method to nearest-exact and megapixels to 3.0 and add a PreviewImage node after it",
        "graph": "ready_templates/sources/official/edit/qwen_image_edit.json",
    },
    {
        "name": "research-plus-implement-flat",
        "query": "Research the best settings for photorealistic SD1.5 and apply them to this workflow",
        "graph": "tests/fixtures/agent_edit/flat.json",
    },
    {
        "name": "respond-graph-wan",
        "query": "Describe this workflow",
        "graph": "ready_templates/sources/official/video/wan_t2v.json",
    },
    {
        "name": "lora-add-flat",
        "query": "Add a LoraLoader node and connect its output to the model input of the KSampler",
        "graph": "tests/fixtures/agent_edit/flat.json",
    },
    {
        "name": "subgraph-wan-i2v",
        "query": "Set the total number of frames to 49",
        "graph": "tests/fixtures/agent_edit/subgraphed_wan_i2v.json",
    },
]


def run_scenario(idx: int, scenario: dict[str, Any]) -> dict[str, Any]:
    plan_dir = Path(f"/tmp/qo-matrix-{idx:02d}-{scenario['name']}")
    plan_dir.mkdir(parents=True, exist_ok=True)

    inputs = f"query={scenario['query']}"
    if "graph" in scenario:
        inputs += f",graph={scenario['graph']}"

    cmd = [
        sys.executable,
        "-m",
        "arnold",
        "run",
        "vibecomfy-executor",
        "--inputs",
        inputs,
        "--plan-dir",
        str(plan_dir),
        "--profile",
        "@vibecomfy-executor:default",
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = PYTHONPATH

    proc = subprocess.run(
        cmd,
        cwd=VIBECOMFY_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )

    state: dict[str, Any] = {}
    state_path = plan_dir / "state.json"
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    plan = state.get("plan", {})
    reply = state.get("reply", "")
    implementation = state.get("implementation", "")
    research_summary = state.get("research_summary", "")
    tool_calls = state.get("research_tool_calls", [])
    edit_changes = state.get("edit_changes", [])

    return {
        "name": scenario["name"],
        "plan_dir": str(plan_dir),
        "returncode": proc.returncode,
        "plan": plan,
        "research": bool(plan.get("research")),
        "implement": bool(plan.get("implement")),
        "reply": bool(plan.get("reply")),
        "tool_calls": len(tool_calls) if isinstance(tool_calls, list) else 0,
        "research_len": len(research_summary),
        "implement_len": len(implementation),
        "edit_changes": len(edit_changes) if isinstance(edit_changes, list) else 0,
        "reply_len": len(reply),
        "reply_preview": reply[:200].replace("\n", " ") if reply else "",
        "error": _extract_error(proc.stdout + proc.stderr) if proc.returncode != 0 else None,
    }


def _extract_error(output: str) -> str:
    lines = output.strip().splitlines()
    for line in reversed(lines):
        if "error" in line.lower() or "traceback" in line.lower():
            return line[:200]
    return output[-200:]


def main() -> int:
    results: list[dict[str, Any]] = []
    for idx, scenario in enumerate(MATRIX, 1):
        print(f"[{idx}/{len(MATRIX)}] {scenario['name']} ...", file=sys.stderr, flush=True)
        result = run_scenario(idx, scenario)
        results.append(result)

    # Print markdown summary
    print("# vibecomfy-executor test matrix results\n")
    print("| # | Scenario | Plan | TC | RS | IS | EC | RE | Status | Reply preview |")
    print("|---|----------|------|----|----|----|----|----|--------|---------------|")
    for r in results:
        plan_str = f"R={int(r['research'])},I={int(r['implement'])},r={int(r['reply'])}"
        status = "OK" if r["returncode"] == 0 and r["reply_len"] > 0 else "FAIL"
        if r["error"]:
            status = "ERROR"
        print(
            f"| {MATRIX.index(next(s for s in MATRIX if s['name'] == r['name'])) + 1} "
            f"| {r['name']} "
            f"| {plan_str} "
            f"| {r['tool_calls']} "
            f"| {r['research_len']} "
            f"| {r['implement_len']} "
            f"| {r['edit_changes']} "
            f"| {r['reply_len']} "
            f"| {status} "
            f"| {r['reply_preview']} |"
        )

    # Write full JSON for inspection
    summary_path = Path("/tmp/qo-matrix-summary.json")
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nFull results: {summary_path}", file=sys.stderr)
    return 0 if all(r["returncode"] == 0 and r["reply_len"] > 0 for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
