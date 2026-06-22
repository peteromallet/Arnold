"""CLI for running compiled workflow manifests.

Example::

    python -m arnold.cli.execution run-manifest \
        --manifest manifest.json \
        --state-store-dir ./runs \
        --budget '{"max_cost": 10.0}'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from arnold.execution import run
from arnold.execution.observability import ExecutionLogger, build_progress_report
from arnold.execution.result import ExecutionResult
from arnold.execution.state_store import FileStateStore
from arnold.kernel import GovernorBudget
from arnold.kernel.journal import read_event_journal
from arnold.manifest import WorkflowManifest


def _load_manifest(path: Path) -> WorkflowManifest:
    return WorkflowManifest.from_json(path.read_text(encoding="utf-8"))


def _parse_budget(raw: str | None) -> GovernorBudget | None:
    if not raw:
        return None
    payload = json.loads(raw)
    return GovernorBudget(
        cost_limit=payload.get("max_cost"),
        seconds_limit=payload.get("max_seconds"),
        token_limit=payload.get("token_budget"),
    )


def _print_result(result: ExecutionResult) -> None:
    payload = {
        "state": result.state.value,
        "manifest_id": result.manifest_id,
        "manifest_hash": result.manifest_hash,
        "artifact_root": str(result.artifact_root),
        "outputs": dict(result.outputs),
        "diagnostics": [
            {"code": d.code, "message": d.message, "node_id": d.node_id}
            for d in result.diagnostics
        ],
        "resume_cursor": result.resume_cursor.key if result.resume_cursor else None,
        "is_terminal": result.is_terminal,
    }
    print(json.dumps(payload, sort_keys=True, indent=2))


def _cmd_run_manifest(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    manifest = _load_manifest(manifest_path)

    state_store = None
    if args.state_store_dir:
        state_store = FileStateStore(args.state_store_dir)

    budget = _parse_budget(args.budget)
    registries = None
    if budget is not None:
        from arnold.execution import ExecutionRegistries

        registries = ExecutionRegistries()

    logger = ExecutionLogger()

    result = run(
        manifest,
        artifact_root=args.artifact_root or str(Path(args.state_store_dir or ".") / "artifacts"),
        registries=registries,
        state_store=state_store,
        logger=logger,
    )

    if args.progress:
        events = read_event_journal(result.artifact_root)
        report = build_progress_report(events)
        print(json.dumps({
            "state": result.state.value,
            "progress": {
                "total_nodes": report.total_nodes,
                "completed": report.completed,
                "failed": report.failed,
                "pending": report.pending,
                "suspended": report.suspended,
                "consumed_cost": report.consumed_cost,
                "remaining_cost": report.remaining_cost,
                "health_status": report.health_status,
            },
        }, sort_keys=True, indent=2))
    else:
        _print_result(result)

    return 0 if result.state.value == "completed" else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="arnold execution",
        description="Run compiled Arnold workflow manifests.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run-manifest",
        help="Run a compiled manifest from a JSON file.",
    )
    run_parser.add_argument("--manifest", required=True, help="Path to the compiled manifest JSON file.")
    run_parser.add_argument("--run-id", help="Optional run identity.")
    run_parser.add_argument("--artifact-root", help="Directory for the journal and artifacts.")
    run_parser.add_argument("--state-store-dir", help="Directory for JSON checkpoints.")
    run_parser.add_argument("--backend", default="local", help="Backend selector (default: local).")
    run_parser.add_argument("--budget", help='JSON budget object, e.g. {"max_cost": 10.0}.')
    run_parser.add_argument("--progress", action="store_true", help="Print progress report instead of result.")
    run_parser.set_defaults(func=_cmd_run_manifest)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
