"""Simple orchestrator for the auto-improve run -> score -> analyze loop."""

from __future__ import annotations

import argparse
import sys

from auto_improve.run_experiment import WORKSPACES_BASE_DIR, clean_iteration, run_iteration
from auto_improve.score_experiment import results_root_for_iteration, score_iteration
from auto_improve.utils import AUTO_IMPROVE_ROOT, ITERATIONS_ROOT, compare_scores, get_iteration_dir, load_scores, next_iteration


PROCESS_DOC = AUTO_IMPROVE_ROOT / "README.md"


def resolve_iteration(*, requested: int | None, skip_run: bool) -> int:
    if requested is not None:
        return requested

    existing_iterations = _existing_iterations()
    if skip_run:
        if not existing_iterations:
            raise FileNotFoundError("No existing iterations found. Pass --iteration or run without --skip-run.")
        return existing_iterations[-1]

    return next_iteration()


def run_loop(
    *,
    iteration: int,
    workers: int,
    skip_run: bool,
    skip_score: bool,
    skip_scoring: bool,
    clean: bool,
    force: bool,
    task_count: int | None = None,
    seed: int | None = None,
) -> dict[str, object]:
    run_result = None
    clean_result = None
    if not skip_run:
        if clean:
            clean_result = clean_iteration(iteration, dry_run=not force)
            if not force:
                return {
                    "iteration": iteration,
                    "run_result": None,
                    "score_result": None,
                    "scores": None,
                    "summary_table": "",
                    "instructions": "",
                    "clean_result": clean_result,
                    "aborted": True,
                }
        elif _iteration_has_stale_artifacts(iteration):
            clean_result = clean_iteration(iteration, dry_run=True)
            if force:
                clean_result = clean_iteration(iteration, dry_run=False)
            else:
                print(
                    "Iteration already has stale run artifacts. Re-run with --force to clean before launching.",
                    file=sys.stderr,
                )
                return {
                    "iteration": iteration,
                    "run_result": None,
                    "score_result": None,
                    "scores": None,
                    "summary_table": "",
                    "instructions": "",
                    "clean_result": clean_result,
                    "aborted": True,
                }
        run_result = run_iteration(
            iteration=iteration,
            workers=workers,
            dry_run=False,
            skip_scoring=skip_scoring,
            task_count=task_count,
            seed=seed,
        )

    score_result = None
    if not skip_score and not skip_scoring:
        score_result = score_iteration(iteration=iteration)

    if skip_scoring:
        return {
            "iteration": iteration,
            "run_result": run_result,
            "score_result": None,
            "clean_result": clean_result,
            "scores": None,
            "summary_table": "",
            "instructions": "\n".join(
                [
                    "Scoring skipped for this run.",
                    "Start the external scorer with `python -m auto_improve.score --watch` when ready.",
                ]
            ),
        }

    scores = load_scores(iteration)
    scaffold_iteration_docs(iteration, scores)
    return {
        "iteration": iteration,
        "run_result": run_result,
        "score_result": score_result,
        "clean_result": clean_result,
        "scores": scores,
        "summary_table": format_scores_table(scores),
        "instructions": analysis_instructions(iteration),
    }


def scaffold_iteration_docs(iteration: int, scores: dict[str, object]) -> None:
    """Pre-fill analysis.md and changes.md with scores data so they're never blank."""
    iteration_dir = get_iteration_dir(iteration)
    tasks = scores.get("tasks", {})
    if not isinstance(tasks, dict):
        tasks = {}

    passed = [tid for tid, t in tasks.items() if isinstance(t, dict) and t.get("resolved")]
    failed = [tid for tid, t in tasks.items() if isinstance(t, dict) and t.get("status") == "failed"]
    errors = [tid for tid, t in tasks.items() if isinstance(t, dict) and t.get("status") == "error"]

    # Comparison with prior iteration
    comparison_block = ""
    if iteration > 1:
        try:
            previous = load_scores(iteration - 1)
            diff = compare_scores(scores, previous)
            lines = []
            if diff["improvements"]:
                lines.append(f"**New passes:** {', '.join(diff['improvements'])}")
            if diff["regressions"]:
                lines.append(f"**Regressions:** {', '.join(diff['regressions'])}")
            if not diff["improvements"] and not diff["regressions"]:
                lines.append("No changes from prior iteration.")
            prev_rate = previous.get("pass_rate", 0)
            curr_rate = scores.get("pass_rate", 0)
            lines.append(f"**Pass rate:** {prev_rate:.0%} → {curr_rate:.0%}")
            comparison_block = "\n## vs Prior Iteration\n\n" + "\n".join(lines) + "\n"
        except FileNotFoundError:
            pass

    analysis_path = iteration_dir / "analysis.md"
    if not analysis_path.exists():
        analysis_path.write_text(
            f"# Iteration {iteration:03d} — Analysis\n\n"
            f"**Pass rate: {scores.get('pass_rate', 0):.0%}** "
            f"({scores.get('resolved', 0)}/{scores.get('total', 0)})\n"
            f"{comparison_block}\n"
            f"## Passed ({len(passed)})\n\n"
            + "".join(f"- {t}\n" for t in passed)
            + f"\n## Failed ({len(failed)})\n\n"
            + "".join(f"- {t} — **Phase:** ? | **Pattern:** ? | **Why:** ?\n" for t in failed)
            + f"\n## Errors ({len(errors)})\n\n"
            + ("".join(f"- {t}\n" for t in errors) if errors else "None\n")
            + "\n## Failure Patterns\n\n"
            + "<!-- Group the failures above by pattern. Which pattern caused the most failures? -->\n\n"
            + "| Pattern | Count | Tasks |\n|---------|-------|-------|\n"
            + "| ? | ? | ? |\n"
            + "\n## Hypothesis\n\n"
            + "<!-- One general change targeting the top pattern. See README.md Principles. -->\n\n"
            + "**Pattern:** \n\n**Change:** \n\n**Why it's general:** \n",
            encoding="utf-8",
        )

    changes_path = iteration_dir / "changes.md"
    if not changes_path.exists():
        changes_path.write_text(
            f"# Iteration {iteration:03d} — Changes\n\n"
            "## What changed\n\n<!-- File, line, diff summary -->\n\n"
            "## Why it's general\n\n<!-- Which pattern does this target? Why would it help any coding task, not just these 20? -->\n\n"
            "## Evidence\n\n<!-- Which failed tasks motivated this? Link to their audit.json / patch.diff -->\n",
            encoding="utf-8",
        )


def format_scores_table(scores: dict[str, object]) -> str:
    rows = [
        ("iteration", str(scores.get("iteration", ""))),
        ("total", str(scores.get("total", ""))),
        ("resolved", str(scores.get("resolved", ""))),
        ("failed", str(scores.get("failed", ""))),
        ("errors", str(scores.get("errors", ""))),
        ("pass_rate", f"{float(scores.get('pass_rate', 0.0)):.2%}"),
    ]

    label_width = max(len(label) for label, _ in rows)
    value_width = max(len(value) for _, value in rows)
    border = f"+-{'-' * label_width}-+-{'-' * value_width}-+"
    lines = [border, f"| {'metric'.ljust(label_width)} | {'value'.ljust(value_width)} |", border]
    for label, value in rows:
        lines.append(f"| {label.ljust(label_width)} | {value.ljust(value_width)} |")
    lines.append(border)
    return "\n".join(lines)


def analysis_instructions(iteration: int) -> str:
    iteration_dir = get_iteration_dir(iteration)
    return "\n".join(
        [
            "Next steps:",
            f"1. Follow the process in {PROCESS_DOC}",
            f"2. Review {iteration_dir / 'scores.json'}",
            f"3. Write {iteration_dir / 'analysis.md'} and {iteration_dir / 'changes.md'}",
            f"4. Append the generalized learning to {AUTO_IMPROVE_ROOT / 'FINDINGS.md'}",
            f"5. Create and push branch auto-improve/iteration-{iteration:03d}",
        ]
    )


def _existing_iterations() -> list[int]:
    if not ITERATIONS_ROOT.exists():
        return []
    iteration_numbers: list[int] = []
    for child in ITERATIONS_ROOT.iterdir():
        if child.is_dir() and child.name.isdigit():
            iteration_numbers.append(int(child.name))
    return sorted(iteration_numbers)


def _iteration_has_stale_artifacts(iteration: int) -> bool:
    results_root = results_root_for_iteration(iteration).resolve()
    workspace_root = (WORKSPACES_BASE_DIR / f"iteration-{iteration:03d}").resolve()
    stale_results = [
        results_root / "_task_manifest.json",
        results_root / "_watch_scores.json",
        results_root / "_swebench_predictions",
        results_root / "_scoring_logs",
        results_root / "consolidated",
    ]
    if any(path.exists() for path in stale_results):
        return True
    if workspace_root.exists() and any(workspace_root.iterdir()):
        return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the auto-improve experiment loop.")
    parser.add_argument("--iteration", type=int, help="Iteration number to use. Defaults to next iteration unless --skip-run is set.")
    parser.add_argument("--workers", type=int, default=3, help="Parallel worker count for experiment runs (default: 3).")
    parser.add_argument("--tasks", type=int, help="Randomly sample N tasks for the run without editing tasks.json.")
    parser.add_argument("--seed", type=int, help="Optional RNG seed for deterministic --tasks sampling.")
    parser.add_argument("--skip-run", action="store_true", help="Skip the experiment run step and reuse the existing iteration results.")
    parser.add_argument("--skip-score", action="store_true", help="Skip score normalization and only print the existing scores summary.")
    parser.add_argument("--skip-scoring", action="store_true", help="Run workers without scoring and skip all score artifact processing.")
    parser.add_argument("--clean", action="store_true", help="Preview stale iteration artifacts before launching. Combine with --force to delete them.")
    parser.add_argument("--force", action="store_true", help="Delete stale iteration artifacts before relaunching.")
    args = parser.parse_args(argv)

    iteration = resolve_iteration(requested=args.iteration, skip_run=args.skip_run)
    result = run_loop(
        iteration=iteration,
        workers=args.workers,
        skip_run=args.skip_run,
        skip_score=args.skip_score,
        skip_scoring=args.skip_scoring,
        clean=args.clean,
        force=args.force,
        task_count=args.tasks,
        seed=args.seed,
    )
    if result.get("aborted"):
        return 1

    print(result["summary_table"])
    print()
    print(result["instructions"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
