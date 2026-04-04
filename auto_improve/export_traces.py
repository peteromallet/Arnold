"""Export per-task execution traces for the SWE-bench dashboard.

Reads phase files from each scored task's run directory and produces
truncated trace JSON files suitable for lazy-loading in the dashboard.

Usage:
    python -m auto_improve.export_traces 021
    python -m auto_improve.export_traces 021 --push
"""

import json
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path("results/auto-improve")
REPO_PATH = Path("/tmp/swe-bench-challenge")

# Truncation limits (chars)
TOOL_OUTPUT_LIMIT = 200
USER_CONTENT_LIMIT = 500
MAX_ASSISTANT_CONTENT = 2000


def _truncate(text: str, limit: int) -> str:
    if not text or len(text) <= limit:
        return text or ""
    return text[:limit] + f"... ({len(text)} chars total)"


def _summarize_messages(messages: list[dict]) -> str:
    """Generate a one-line summary of what happened in a phase conversation."""
    tool_calls: dict[str, int] = {}
    file_reads = 0
    searches = 0
    edits = 0

    for m in messages:
        if m.get("role") == "assistant":
            for tc in m.get("tool_calls", []):
                name = tc.get("function", {}).get("name", "unknown")
                tool_calls[name] = tool_calls.get(name, 0) + 1
                if "read" in name.lower():
                    file_reads += 1
                elif "search" in name.lower() or "find" in name.lower() or "grep" in name.lower():
                    searches += 1
                elif "write" in name.lower() or "edit" in name.lower() or "patch" in name.lower():
                    edits += 1

    parts = []
    if file_reads:
        parts.append(f"Read {file_reads} file{'s' if file_reads != 1 else ''}")
    if searches:
        parts.append(f"searched {searches} time{'s' if searches != 1 else ''}")
    if edits:
        parts.append(f"edited {edits} file{'s' if edits != 1 else ''}")

    # Add any remaining tool calls not covered above
    other = {k: v for k, v in tool_calls.items()
             if not any(w in k.lower() for w in ("read", "search", "find", "grep", "write", "edit", "patch"))}
    for name, count in sorted(other.items(), key=lambda x: -x[1])[:3]:
        parts.append(f"{name} x{count}")

    total_assistant = sum(1 for m in messages if m.get("role") == "assistant")
    total_tool = sum(1 for m in messages if m.get("role") == "tool")

    if not parts:
        parts.append(f"{total_assistant} assistant message{'s' if total_assistant != 1 else ''}")

    return ", ".join(parts)


def _process_message(msg: dict) -> dict:
    """Process a single message for export, truncating as needed."""
    role = msg.get("role", "unknown")
    result: dict = {"role": role}

    content = msg.get("content", "")
    if isinstance(content, list):
        # Multi-part content (e.g. images) — stringify
        content = json.dumps(content)

    if role == "tool":
        result["content"] = _truncate(str(content), TOOL_OUTPUT_LIMIT)
        if msg.get("tool_call_id"):
            result["tool_call_id"] = msg["tool_call_id"]
    elif role == "user":
        result["content"] = _truncate(str(content), USER_CONTENT_LIMIT)
    elif role == "assistant":
        result["content"] = _truncate(str(content), MAX_ASSISTANT_CONTENT)
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            result["tool_calls"] = []
            for tc in tool_calls:
                func = tc.get("function", {})
                args_str = func.get("arguments", "")
                # Keep tool names and args in full (args are usually small)
                if len(str(args_str)) > 500:
                    args_str = _truncate(str(args_str), 500)
                result["tool_calls"].append({
                    "name": func.get("name", "unknown"),
                    "arguments": args_str,
                })
    else:
        result["content"] = _truncate(str(content), USER_CONTENT_LIMIT)

    return result


def export_traces(iteration: str) -> int:
    """Export trace files for all scored tasks. Returns count of exported traces."""
    iter_name = iteration if iteration.startswith("iteration-") else f"iteration-{iteration}"
    iter_dir = BASE_DIR / iter_name

    scores_path = iter_dir / "_watch_scores.json"
    if not scores_path.exists():
        print(f"No scores file at {scores_path}")
        return 0

    scores = json.loads(scores_path.read_text())
    scored_tasks = {
        tid: t for tid, t in scores.get("tasks", {}).items()
        if t.get("resolved") is not None
    }

    traces_dir = REPO_PATH / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)

    exported = 0

    for tid, task_score in sorted(scored_tasks.items()):
        status = "pass" if task_score.get("resolved") else "fail"

        # Find the run directory with phases (same logic as dashboard_web)
        run_dir = None
        for worker_dir in sorted(iter_dir.glob("worker-*")):
            task_dir = worker_dir / tid
            if not task_dir.exists():
                continue
            for rd in sorted(task_dir.iterdir()):
                if (rd / "phases").exists():
                    run_dir = rd

        if not run_dir:
            print(f"  {tid}: no phases directory found, skipping")
            continue

        phases_dir = run_dir / "phases"
        patch_path = run_dir / "git" / "diff.patch"

        # Read patch
        patch_content = ""
        if patch_path.exists():
            patch_content = patch_path.read_text(errors="replace")
        # Also check _swebench_predictions
        if not patch_content:
            pred_path = iter_dir / "_swebench_predictions" / f"{tid}.jsonl"
            if pred_path.exists():
                try:
                    pred = json.loads(pred_path.read_text().strip().split("\n")[-1])
                    patch_content = pred.get("model_patch", "")
                except Exception:
                    pass

        # Process phases
        phases = []
        total_time_s = 0

        for pf in sorted(phases_dir.glob("*.json")):
            try:
                phase_data = json.loads(pf.read_text())
            except Exception:
                continue

            phase_name = phase_data.get("phase", pf.stem)
            model = phase_data.get("model", "")
            duration_ms = phase_data.get("duration_ms", 0)
            duration_s = round(duration_ms / 1000)
            total_time_s += duration_s

            trace_messages = phase_data.get("trace_messages", [])
            processed_messages = [_process_message(m) for m in trace_messages]
            summary = _summarize_messages(trace_messages)

            phases.append({
                "name": phase_name,
                "file": pf.name,
                "model": model,
                "duration_s": duration_s,
                "messages": processed_messages,
                "message_count": len(trace_messages),
                "summary": summary,
            })

        trace = {
            "task_id": tid,
            "status": status,
            "patch": patch_content,
            "total_time_s": total_time_s,
            "phases": phases,
        }

        out_path = traces_dir / f"{tid}.json"
        out_path.write_text(json.dumps(trace, indent=2))
        size_kb = out_path.stat().st_size / 1024
        exported += 1
        print(f"  {tid}: {len(phases)} phases, {size_kb:.0f}KB")

    print(f"\nExported {exported} traces to {traces_dir}")
    return exported


def main():
    args = sys.argv[1:]
    push = "--push" in args
    args = [a for a in args if not a.startswith("--")]

    iteration = args[0] if args else "021"

    count = export_traces(iteration)

    if push and count > 0:
        subprocess.run(["git", "add", "traces/"], cwd=REPO_PATH, check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_PATH)
        if result.returncode != 0:
            subprocess.run(
                ["git", "commit", "-m", f"add execution traces for {count} tasks"],
                cwd=REPO_PATH, check=True,
            )
            subprocess.run(["git", "push", "origin", "main"], cwd=REPO_PATH, check=True)
            print("Pushed traces to GitHub Pages")
        else:
            print("No trace changes to push")


if __name__ == "__main__":
    main()
