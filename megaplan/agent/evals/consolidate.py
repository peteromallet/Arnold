"""Consolidate SWE-bench run results into a clean, shareable format.

Run after a parallel eval completes to produce:
  results/{run_name}/consolidated/
    ├── summary.json          # Full scorecard: task, status, cost, duration, patch_lines
    ├── predictions.jsonl     # All patches in one file (SWE-bench submission format)
    ├── scores.json           # SWE-bench eval results per task
    ├── tasks/
    │   └── {instance_id}/
    │       ├── patch.diff    # The generated patch
    │       ├── audit.json    # Phase costs, durations, models used
    │       ├── traces/       # Symlinked to full LLM traces
    │       └── score.json    # SWE-bench eval result
    └── README.md             # Run metadata, model config, pass rate
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def consolidate(results_root: str | Path, *, logs_root: str | Path | None = None) -> Path:
    root = Path(results_root).expanduser().resolve()
    score_logs_root = (
        Path(logs_root).expanduser().resolve()
        if logs_root is not None
        else Path("logs/run_evaluation").expanduser().resolve()
    )
    out = root / "consolidated"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    tasks_dir = out / "tasks"
    tasks_dir.mkdir()

    # Load manifest
    manifest_path = root / "_task_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"tasks": {}}

    # Load run config
    config_path = root / "_run_config.json"
    run_config = json.loads(config_path.read_text()) if config_path.exists() else {}

    # Collect all predictions
    all_predictions = []
    pred_dir = root / "_swebench_predictions"
    if pred_dir.exists():
        for f in sorted(pred_dir.glob("*.jsonl")):
            for line in f.read_text().splitlines():
                if line.strip():
                    try:
                        all_predictions.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    # Collect SWE-bench scores
    scores: dict[str, dict] = {}
    for report in score_logs_root.rglob("report.json"):
        try:
            for iid, res in json.load(open(report)).items():
                if iid not in scores:
                    scores[iid] = res
        except (json.JSONDecodeError, OSError):
            pass

    # Collect audit data per task
    entries = []
    for worker_dir in sorted(root.glob("worker-*")):
        for task_dir in sorted(worker_dir.iterdir()):
            if not task_dir.is_dir():
                continue
            iid = task_dir.name
            # Find the latest timestamp dir
            ts_dirs = sorted(task_dir.iterdir())
            if not ts_dirs:
                continue
            audit_dir = ts_dirs[-1]

            # Read summary
            summary_path = audit_dir / "summary.json"
            summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}

            # Read phase costs
            phase_costs = []
            for pf in sorted((audit_dir / "phases").glob("*.json")) if (audit_dir / "phases").exists() else []:
                try:
                    pd = json.load(open(pf))
                    phase_costs.append({
                        "phase": pd.get("phase", pf.stem),
                        "cost_usd": pd.get("cost_usd", 0),
                        "duration_ms": pd.get("duration_ms", 0),
                        "model": pd.get("model", ""),
                    })
                except:
                    pass

            total_cost = sum(p["cost_usd"] for p in phase_costs)
            total_duration = sum(p["duration_ms"] for p in phase_costs) / 1000

            # Find patch
            pred = next((p for p in all_predictions if p.get("instance_id") == iid), None)
            patch = pred.get("model_patch", "") if pred else ""
            patch_lines = patch.count("\n") + 1 if patch else 0

            # Find score
            score = scores.get(iid)
            resolved = score.get("resolved", False) if score else None

            # Manifest status
            manifest_entry = manifest.get("tasks", {}).get(iid, {})

            entry = {
                "instance_id": iid,
                "status": "resolved" if resolved else "failed" if resolved is False else summary.get("final_status", manifest_entry.get("status", "unknown")),
                "resolved": resolved,
                "cost_usd": total_cost,
                "duration_seconds": total_duration,
                "patch_lines": patch_lines,
                "phases": len(phase_costs),
                "worker": worker_dir.name,
                "audit_dir": str(audit_dir.relative_to(root)),
            }
            entries.append(entry)

            # Write per-task consolidated output
            task_out = tasks_dir / iid
            task_out.mkdir(parents=True, exist_ok=True)

            if patch:
                (task_out / "patch.diff").write_text(patch, encoding="utf-8")

            audit_summary = {
                "instance_id": iid,
                "resolved": resolved,
                "cost_usd": total_cost,
                "duration_seconds": total_duration,
                "patch_lines": patch_lines,
                "phases": phase_costs,
            }
            (task_out / "audit.json").write_text(json.dumps(audit_summary, indent=2), encoding="utf-8")

            if score:
                (task_out / "score.json").write_text(json.dumps(score, indent=2), encoding="utf-8")

            # Symlink traces if they exist
            traces_src = audit_dir / "traces"
            if traces_src.exists():
                traces_dst = task_out / "traces"
                if not traces_dst.exists():
                    traces_dst.symlink_to(traces_src)

    # Sort entries
    entries.sort(key=lambda e: e["instance_id"])

    # Compute stats
    scored = [e for e in entries if e["resolved"] is not None]
    passed = sum(1 for e in scored if e["resolved"])
    failed = sum(1 for e in scored if not e["resolved"])
    total_cost = sum(e["cost_usd"] for e in entries)
    total_tasks = len(manifest.get("tasks", {}))

    summary = {
        "run_name": root.name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": run_config,
        "total_tasks": total_tasks,
        "tasks_attempted": len(entries),
        "predictions_generated": len(all_predictions),
        "scored": len(scored),
        "resolved": passed,
        "failed": failed,
        "pass_rate": round(passed / len(scored), 4) if scored else None,
        "total_cost_usd": round(total_cost, 2),
        "avg_cost_per_task": round(total_cost / len(entries), 3) if entries else 0,
        "avg_duration_seconds": round(sum(e["duration_seconds"] for e in entries) / len(entries), 1) if entries else 0,
        "tasks": entries,
    }

    # Write outputs
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Combined predictions JSONL
    with open(out / "predictions.jsonl", "w") as f:
        for pred in all_predictions:
            f.write(json.dumps(pred) + "\n")

    # Scores
    (out / "scores.json").write_text(json.dumps(scores, indent=2), encoding="utf-8")

    # README
    readme = f"""# SWE-bench Eval Run: {root.name}

## Results
- **Pass rate: {passed}/{len(scored)} ({round(100*passed/len(scored))}%)** (scored)
- Tasks attempted: {len(entries)}/{total_tasks}
- Predictions generated: {len(all_predictions)}
- Total cost: ${total_cost:.2f}

## Config
- Models: {json.dumps(run_config.get('models', {}), indent=2)}
- Robustness: {run_config.get('robustness', 'unknown')}
- Dataset: {run_config.get('swebench_dataset', 'unknown')}

## Files
- `summary.json` — Full scorecard with per-task results
- `predictions.jsonl` — All patches (SWE-bench submission format)
- `scores.json` — SWE-bench evaluation results
- `tasks/<instance_id>/` — Per-task patch, audit, traces, score

## Reproduction
```bash
python -m evals.run_evals --config <config> --workers 10
```
""" if scored else "# Run in progress\n"

    (out / "README.md").write_text(readme, encoding="utf-8")

    print(f"Consolidated {len(entries)} tasks to {out}")
    print(f"Pass rate: {passed}/{len(scored)} ({round(100*passed/len(scored))}%)" if scored else "No scores yet")
    return out


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "results/swebench-verified-qwen-glm"
    consolidate(path)
