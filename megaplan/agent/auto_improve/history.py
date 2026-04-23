"""Cross-iteration task performance history."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from auto_improve.utils import ITERATIONS_ROOT


def main() -> int:
    iterations = sorted(
        int(d.name)
        for d in ITERATIONS_ROOT.iterdir()
        if d.is_dir() and d.name.isdigit() and (d / "scores.json").exists()
    )
    if not iterations:
        print("No scored iterations found.", file=sys.stderr)
        return 1

    # Load all scores
    all_scores: dict[int, dict[str, bool | None]] = {}
    all_tasks: set[str] = set()
    for iteration in iterations:
        scores_path = ITERATIONS_ROOT / f"{iteration:03d}" / "scores.json"
        data = json.loads(scores_path.read_text())
        tasks = data.get("tasks", {})
        task_results = {}
        for tid, info in tasks.items():
            if isinstance(info, dict):
                task_results[tid] = info.get("resolved")
            elif isinstance(info, bool):
                task_results[tid] = info
        all_scores[iteration] = task_results
        all_tasks.update(task_results.keys())

    # Build table
    sorted_tasks = sorted(all_tasks)
    iter_labels = [f"{i:03d}" for i in iterations]

    # Header
    task_width = max(len(t) for t in sorted_tasks)
    col_width = max(5, max(len(l) for l in iter_labels))
    header = f"{'task'.ljust(task_width)} | " + " | ".join(l.rjust(col_width) for l in iter_labels)
    separator = "-" * len(header)

    print(separator)
    print(header)
    print(separator)

    for task in sorted_tasks:
        cells = []
        prev = None
        for iteration in iterations:
            result = all_scores[iteration].get(task)
            if result is True:
                symbol = "PASS"
            elif result is False:
                symbol = "FAIL"
            elif result is None:
                symbol = "ERR"
            else:
                symbol = "  - "

            # Mark changes
            if prev is not None and result is not None and prev != result:
                if result is True:
                    symbol = " +1 "  # improved
                elif result is False and prev is True:
                    symbol = " -1 "  # regressed

            cells.append(symbol.center(col_width))
            prev = result

        print(f"{task.ljust(task_width)} | " + " | ".join(cells))

    print(separator)

    # Summary row
    summary_cells = []
    for iteration in iterations:
        results = all_scores[iteration]
        passed = sum(1 for v in results.values() if v is True)
        total = sum(1 for v in results.values() if v is not None)
        rate = f"{passed}/{total}" if total else "0/0"
        summary_cells.append(rate.center(col_width))

    print(f"{'TOTAL'.ljust(task_width)} | " + " | ".join(summary_cells))
    print(separator)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
