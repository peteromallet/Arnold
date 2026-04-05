"""Check for failed tasks where our patch matches the golden patch.

Usage:
    python -m auto_improve.check_false_negatives
"""

import json
from pathlib import Path


def check_false_negatives(iteration: str = "021") -> list[dict]:
    """Find failed tasks with patches identical to golden."""
    from datasets import load_dataset

    scores_path = Path(f"results/auto-improve/iteration-{iteration}/_watch_scores.json")
    preds_dir = Path(f"results/auto-improve/iteration-{iteration}/_swebench_predictions")

    if not scores_path.exists():
        return []

    scores = json.loads(scores_path.read_text())
    ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
    golden = {inst["instance_id"]: inst["patch"] for inst in ds}

    def extract_changes(patch: str) -> set[str]:
        return {
            line[1:].strip()
            for line in patch.split("\n")
            if (line.startswith("+") or line.startswith("-"))
            and not line.startswith("+++")
            and not line.startswith("---")
            and line[1:].strip()
        }

    candidates = []
    for tid, t in scores["tasks"].items():
        if t.get("resolved") is not False:
            continue
        # Skip already reviewed
        review = t.get("review", {})
        if isinstance(review, dict) and review.get("reviewed_by") == "human":
            continue

        pred_file = preds_dir / f"{tid}.jsonl"
        if not pred_file.exists():
            continue

        try:
            pred = json.loads(pred_file.read_text())
            our_patch = pred.get("model_patch", pred.get("patch", ""))
            gold = golden.get(tid, "")
            if not our_patch or not gold:
                continue

            our_changes = extract_changes(our_patch)
            gold_changes = extract_changes(gold)
            if not our_changes or not gold_changes:
                continue

            intersection = our_changes & gold_changes
            union = our_changes | gold_changes
            similarity = len(intersection) / len(union) if union else 0

            if similarity >= 0.9:
                candidates.append({
                    "task_id": tid,
                    "similarity": round(similarity, 2),
                    "identical": similarity == 1.0,
                    "our_changes": len(our_changes),
                    "gold_changes": len(gold_changes),
                })
        except Exception:
            pass

    return sorted(candidates, key=lambda x: -x["similarity"])


if __name__ == "__main__":
    candidates = check_false_negatives()
    if candidates:
        print(f"Found {len(candidates)} potential false negatives:")
        for c in candidates:
            tag = "IDENTICAL" if c["identical"] else f"{c['similarity']:.0%} similar"
            print(f"  {c['task_id']}: {tag}")
    else:
        print("No potential false negatives found.")
