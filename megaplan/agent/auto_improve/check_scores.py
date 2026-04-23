"""Quick score checker for active iterations."""

import json
import sys
from pathlib import Path

from evals.watch_scoring import classify_task, load_scores_data


def check_iteration(iter_dir: Path) -> dict:
    scores_path = iter_dir / "_watch_scores.json"
    preds_dir = iter_dir / "_swebench_predictions"
    config_path = iter_dir / "_run_config.json"

    preds = len([p for p in preds_dir.glob("*.jsonl") if p.stem != "all_predictions"]) if preds_dir.exists() else 0

    robustness = "?"
    if config_path.exists():
        config = json.loads(config_path.read_text())
        robustness = config.get("robustness", "?")

    if not scores_path.exists():
        return {"iter": iter_dir.name, "robustness": robustness, "preds": preds, "passed": 0, "failed": 0, "pending": 0, "skipped": 0, "tasks": {}}

    data = load_scores_data(scores_path)
    tasks = data.get("tasks", {})

    passed = failed = pending = skipped = excluded = 0
    task_results = {}
    for tid, t in sorted(tasks.items()):
        review = t.get("review", {}) if isinstance(t, dict) else {}
        is_excluded = isinstance(review, dict) and review.get("excluded_from_pass_rate", False)
        review_cat = review.get("category", "") if isinstance(review, dict) else ""
        state = classify_task(t)

        if state == "pass":
            passed += 1
            task_results[tid] = "PASS"
        elif state == "fail":
            if is_excluded:
                excluded += 1
                task_results[tid] = f"FAIL [EXCLUDED: {review_cat}]"
            else:
                failed += 1
                label = f"FAIL [{review_cat}]" if review_cat else "FAIL"
                task_results[tid] = label
        elif state == "exhausted":
            if is_excluded:
                excluded += 1
                task_results[tid] = f"SKIP [EXCLUDED: {review_cat}]"
            else:
                skipped += 1
                label = f"SKIP [{review_cat}]" if review_cat else "SKIP"
                task_results[tid] = label
        else:
            pending += 1
            task_results[tid] = f"pending({t.get('attempts', 0)})"

    return {
        "iter": iter_dir.name,
        "robustness": robustness,
        "preds": preds,
        "passed": passed,
        "failed": failed,
        "pending": pending,
        "skipped": skipped,
        "excluded": excluded,
        "tasks": task_results,
    }


def main():
    base = Path("results/auto-improve")
    iters = sys.argv[1:] if len(sys.argv) > 1 else []

    if not iters:
        # Auto-detect active iterations (have a manifest)
        for d in sorted(base.iterdir()):
            if d.is_dir() and (d / "_task_manifest.json").exists():
                iters.append(d.name)

    for iter_name in iters:
        iter_dir = base / iter_name
        if not iter_dir.exists():
            continue
        r = check_iteration(iter_dir)
        scored = r["passed"] + r["failed"]
        pct = r["passed"] * 100 // scored if scored else 0
        line = f"  {r['passed']}/{scored} ({pct}%)"
        if r.get("excluded", 0):
            adj_scored = scored + r["excluded"]
            adj_pct = (r["passed"] + r["excluded"]) * 100 // adj_scored if adj_scored else 0
            line += f" | adjusted: {r['passed'] + r['excluded']}/{adj_scored} ({adj_pct}%)"
        line += f" | {r['preds']} preds | {r['pending']} pending"
        if r["skipped"]:
            line += f" | {r['skipped']} UNRESOLVED SKIP(s) ⚠️"
        print(f"=== {r['iter']} ({r['robustness']}) ===")
        print(line)
        for tid, status in r["tasks"].items():
            print(f"    {tid}: {status}")
        if r["skipped"]:
            print(f"  ⚠️  {r['skipped']} task(s) need review: python -m auto_improve.review --iteration {iter_name} --list")
        print()


if __name__ == "__main__":
    main()
