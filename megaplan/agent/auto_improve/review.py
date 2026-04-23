"""Review and reconcile scoring results.

Add review entries to _watch_scores.json with evidence and classification.

Usage:
    python -m auto_improve.review --iteration 021 --task django__django-14011 \
        --category partial_fix \
        --explanation "Fix covers 3/4 tests but misses samesite+secure" \
        --exclude false

    python -m auto_improve.review --iteration 021 --task sympy__sympy-20590 \
        --category golden_match \
        --explanation "Patch identical to golden" \
        --exclude true

    python -m auto_improve.review --iteration 021 --list
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path("results/auto-improve")

VALID_CATEGORIES = {
    "golden_match", "env_regression", "env_missing_dep", "harness_error",
    "scoring_infra", "partial_fix", "close_miss", "wrong_detail",
    "wrong_approach", "regression", "test_contamination", "escalated",
    "scoring_exhausted",
}

VALID_GOLDEN = {"same", "similar", "different", "not_checked"}
VALID_GAPS = {"critique_missed", "gate_bypass", "execute_no_test", "review_rubber_stamp", "none"}


def _iter_path(iteration: str) -> Path:
    name = iteration if iteration.startswith("iteration-") else f"iteration-{iteration}"
    return BASE_DIR / name


def _load_scores(iter_path: Path) -> dict:
    scores_path = iter_path / "_watch_scores.json"
    if not scores_path.exists():
        return {}
    return json.loads(scores_path.read_text())


def _save_scores(iter_path: Path, data: dict) -> None:
    scores_path = iter_path / "_watch_scores.json"
    scores_path.write_text(json.dumps(data, indent=2))


def list_reviews(iteration: str) -> int:
    iter_path = _iter_path(iteration)
    data = _load_scores(iter_path)
    tasks = data.get("tasks", {})

    reviewed = []
    unreviewed_fails = []
    unreviewed_skips = []

    for tid, entry in sorted(tasks.items()):
        resolved = entry.get("resolved")
        review = entry.get("review")

        if review and isinstance(review, dict):
            cat = review.get("category", "?")
            excl = review.get("excluded_from_pass_rate", False)
            expl = review.get("explanation", "")[:80]
            reviewed.append((tid, resolved, cat, excl, expl))
        elif resolved is False:
            unreviewed_fails.append(tid)
        elif resolved is None and entry.get("attempts", 0) >= 3:
            unreviewed_skips.append(tid)

    if reviewed:
        print(f"Reviewed ({len(reviewed)}):")
        for tid, resolved, cat, excl, expl in reviewed:
            r = "PASS" if resolved is True else "FAIL" if resolved is False else "SKIP"
            e = "EXCLUDED" if excl else "kept"
            print(f"  {tid}: {r} → {cat} ({e})")
            print(f"    {expl}")
    else:
        print("No reviews yet.")

    if unreviewed_fails:
        print(f"\nUnreviewed FAILs ({len(unreviewed_fails)}):")
        for tid in unreviewed_fails:
            print(f"  {tid}")

    if unreviewed_skips:
        print(f"\nUnreviewed SKIPs ({len(unreviewed_skips)}):")
        for tid in unreviewed_skips:
            print(f"  {tid}")

    return 0


def add_review(
    iteration: str,
    task_id: str,
    category: str,
    explanation: str,
    exclude: bool,
    resolve_as: str | None = None,
    golden: str = "not_checked",
    gap: str = "none",
) -> int:
    if category not in VALID_CATEGORIES:
        print(f"Invalid category: {category}. Valid: {', '.join(sorted(VALID_CATEGORIES))}", file=sys.stderr)
        return 1
    if golden not in VALID_GOLDEN:
        print(f"Invalid --golden: {golden}. Valid: {', '.join(sorted(VALID_GOLDEN))}", file=sys.stderr)
        return 1
    if gap not in VALID_GAPS:
        print(f"Invalid --gap: {gap}. Valid: {', '.join(sorted(VALID_GAPS))}", file=sys.stderr)
        return 1
    if resolve_as and resolve_as not in ("pass", "fail"):
        print(f"Invalid --resolve: {resolve_as}. Must be 'pass' or 'fail'.", file=sys.stderr)
        return 1

    iter_path = _iter_path(iteration)
    data = _load_scores(iter_path)
    tasks = data.get("tasks", {})

    if task_id not in tasks:
        print(f"Task {task_id} not found in {iter_path.name} scores", file=sys.stderr)
        return 1

    entry = tasks[task_id]
    old_resolved = entry.get("resolved")
    old_r = "PASS" if old_resolved is True else "FAIL" if old_resolved is False else "SKIP"

    # Resolve the task to pass/fail if requested
    if resolve_as == "pass":
        entry["resolved"] = True
    elif resolve_as == "fail":
        entry["resolved"] = False

    entry["review"] = {
        "category": category,
        "explanation": explanation,
        "excluded_from_pass_rate": exclude,
        "golden_comparison": golden,
        "pipeline_gap": gap,
        "reviewed_by": "human",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    if resolve_as:
        entry["review"]["resolved_from"] = old_r.lower()
        entry["review"]["resolved_to"] = resolve_as

    _save_scores(iter_path, data)

    new_resolved = entry.get("resolved")
    new_r = "PASS" if new_resolved is True else "FAIL" if new_resolved is False else "SKIP"
    resolution = f" → resolved {old_r}→{new_r}" if resolve_as else ""
    excl_str = "EXCLUDED" if exclude else "kept"
    print(f"Reviewed {task_id}: {category} ({excl_str}){resolution}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Review and reconcile scoring results")
    parser.add_argument("--iteration", required=True, help="Iteration (e.g., 021)")
    parser.add_argument("--list", action="store_true", help="List all reviews and unreviewed tasks")
    parser.add_argument("--task", help="Task ID to review")
    parser.add_argument("--category", help=f"Review category: {', '.join(sorted(VALID_CATEGORIES))}")
    parser.add_argument("--explanation", help="Explanation with evidence")
    parser.add_argument("--exclude", type=lambda x: x.lower() in ("true", "yes", "1"), default=False,
                       help="Exclude from pass rate (true/false)")
    parser.add_argument("--resolve", choices=["pass", "fail"],
                       help="Resolve a SKIP/null task to pass or fail (changes the resolved field)")
    parser.add_argument("--golden", default="not_checked", help=f"Golden comparison: {', '.join(sorted(VALID_GOLDEN))}")
    parser.add_argument("--gap", default="none", help=f"Pipeline gap: {', '.join(sorted(VALID_GAPS))}")
    args = parser.parse_args()

    if args.list:
        return list_reviews(args.iteration)

    if not args.task or not args.category or not args.explanation:
        print("--task, --category, and --explanation are required (or use --list)", file=sys.stderr)
        return 1

    return add_review(
        args.iteration, args.task, args.category, args.explanation,
        args.exclude, args.resolve, args.golden, args.gap,
    )


if __name__ == "__main__":
    sys.exit(main())
