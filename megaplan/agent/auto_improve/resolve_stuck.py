"""Find tasks stuck in retry loops and force-resolve them.

Tasks requeued 3+ times without producing a scored result get compared
to golden. If patch matches: resolve PASS. If no patch or different: resolve FAIL.

Usage:
    python -m auto_improve.resolve_stuck              # dry run
    python -m auto_improve.resolve_stuck --apply      # apply resolutions
"""

import json
import sys
from pathlib import Path

MAX_REQUEUES = 3


def resolve_stuck(iteration: str = "021", apply: bool = False) -> list[dict]:
    from datasets import load_dataset

    manifest_path = Path(f"results/auto-improve/iteration-{iteration}/_task_manifest.json")
    scores_path = Path(f"results/auto-improve/iteration-{iteration}/_watch_scores.json")
    preds_dir = Path(f"results/auto-improve/iteration-{iteration}/_swebench_predictions")

    m = json.loads(manifest_path.read_text())
    s = json.loads(scores_path.read_text())
    preds = {p.stem for p in preds_dir.glob("*.jsonl")}

    ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
    golden = {inst["instance_id"]: inst["patch"] for inst in ds}

    def extract_changes(patch: str) -> set[str]:
        return {
            line[1:].strip()
            for line in patch.split("\n")
            if (line.startswith("+") or line.startswith("-"))
            and not line.startswith("+++") and not line.startswith("---")
            and line[1:].strip()
        }

    results = []
    for tid, task in m["tasks"].items():
        # Count requeues from history
        hist = task.get("history", [])
        requeues = sum(1 for h in hist if h.get("event") == "requeued")
        if requeues < MAX_REQUEUES:
            continue

        # Already scored?
        if tid in s["tasks"] and s["tasks"][tid].get("resolved") is not None:
            continue

        # Check if we have a prediction
        has_pred = tid in preds
        gold = golden.get(tid, "")

        if has_pred and gold:
            pred = json.loads((preds_dir / f"{tid}.jsonl").read_text())
            our_patch = pred.get("model_patch", pred.get("patch", ""))
            our_changes = extract_changes(our_patch)
            gold_changes = extract_changes(gold)
            intersection = our_changes & gold_changes
            union = our_changes | gold_changes
            sim = len(intersection) / len(union) if union else 0

            if sim >= 0.9:
                resolution = "pass"
                reason = f"Patch {sim:.0%} similar to golden after {requeues} requeues"
            else:
                resolution = "fail"
                reason = f"Patch {sim:.0%} similar to golden after {requeues} requeues — not a match"
        elif has_pred:
            resolution = "fail"
            reason = f"Has prediction but no golden to compare after {requeues} requeues"
        else:
            resolution = "fail"
            reason = f"No patch produced after {requeues} requeues"

        results.append({
            "task_id": tid,
            "resolution": resolution,
            "reason": reason,
            "requeues": requeues,
            "status": task.get("status"),
        })

        if apply:
            # Stop further requeuing
            task["status"] = "done"
            task["worker_id"] = None
            hist.append({"event": "force_resolved", "reason": reason})

            # Set score
            if tid not in s["tasks"]:
                s["tasks"][tid] = {}
            s["tasks"][tid]["resolved"] = resolution == "pass"
            s["tasks"][tid]["review"] = {
                "reviewed_by": "auto_resolve_stuck",
                "category": "retry_exhausted",
                "explanation": reason,
            }

    if apply and results:
        json.dump(m, open(manifest_path, "w"), indent=2)
        json.dump(s, open(scores_path, "w"), indent=2)

    return results


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    results = resolve_stuck(apply=apply)
    if results:
        print(f"{'Applied' if apply else 'Would resolve'} {len(results)} stuck tasks:")
        for r in results:
            print(f"  {r['task_id']}: {r['resolution']} ({r['reason']})")
    else:
        print("No stuck tasks to resolve.")
