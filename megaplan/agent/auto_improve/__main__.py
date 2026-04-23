"""Auto-improve CLI — central entry point.

Usage:
    python -m auto_improve              # show this help
    python -m auto_improve <command>    # run a command

Commands:
    loop            Start an iteration (run tasks with workers)
    scale           Scale an iteration to more tasks + ensure workers/scorer running
    kill            Kill iterations, workers, or scorers
    score           Score predictions via Modal (watch mode or one-shot)
    dashboard       Live status overview for an iteration
    healthcheck     Deep health diagnosis across iterations
    check_scores    Compare pass rates across iterations
    review          Add/list manual reviews for scoring results
    add_tasks       Add replacement tasks to a running iteration
    compare         Compare per-task results between two iterations

Each command has its own --help. Example:
    python -m auto_improve.loop --help
    python -m auto_improve.score --watch --iterations 021 022
    python -m auto_improve.kill --all

Process docs:
    auto_improve/README.md              — full setup and process
    auto_improve/CRON_RUNBOOK.md        — hourly check-in checklist
    auto_improve/SCORING_REVIEW_GUIDE.md — how to review and reconcile scores
"""

import sys

COMMANDS = {
    "loop":         "Start an iteration (run tasks with workers)",
    "scale":        "Scale iteration to more tasks + ensure workers/scorer",
    "kill":         "Kill iterations, workers, or scorers",
    "score":        "Score predictions via Modal",
    "dashboard":    "Live status overview for an iteration",
    "healthcheck":  "Deep health diagnosis across iterations",
    "check_scores": "Compare pass rates across iterations",
    "review":       "Add/list manual reviews for scoring results",
    "add_tasks":    "Add replacement tasks to a running iteration",
    "compare":      "Compare per-task results between two iterations",
}


def main():
    print("Auto-Improve CLI")
    print("=" * 50)
    print()
    print("Commands:")
    for cmd, desc in COMMANDS.items():
        print(f"  python -m auto_improve.{cmd:<14s} {desc}")
    print()
    print("Add --help to any command for usage details.")
    print()
    print("Docs:")
    print("  auto_improve/README.md               Setup & process")
    print("  auto_improve/CRON_RUNBOOK.md          Hourly checklist")
    print("  auto_improve/SCORING_REVIEW_GUIDE.md  Review & reconcile")


if __name__ == "__main__":
    main()
