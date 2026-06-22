"""Arnold workflow CLI.

Subcommands operate on a single builder target:

    arnold workflow check --module package.module:build_pipeline
    arnold workflow manifest --module package.module:build_pipeline
    arnold workflow dot --module package.module:build_pipeline
    arnold workflow dry-run --module package.module:build_pipeline
    arnold workflow run --module package.module:build_pipeline
    arnold workflow resume --module package.module:build_pipeline
    arnold workflow describe --module package.module:build_pipeline
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

import arnold.workflow as workflow
from arnold.execution import ExecutionRegistries, run
from arnold.execution.backend import SkeletalBackend
from arnold.execution.observability import ExecutionLogger
from arnold.execution.state_store import FileStateStore
from arnold.execution.result import ExecutionResult
from arnold.manifest.refs import NodeRef, manifest_coordinate
from arnold.workflow import (
    Pipeline,
    compile_pipeline,
    dry_run,
    inspect_manifest,
    to_dot,
    to_yaml,
)


def _load_builder(target: str) -> Callable[[], Pipeline]:
    if ":" not in target:
        raise ValueError(
            "builder target must be '--module package.module:builder_name'"
        )
    module_path, builder_name = target.rsplit(":", 1)
    try:
        module = importlib.import_module(module_path)
    except Exception as exc:
        raise ValueError(f"cannot import module {module_path!r}: {exc}") from exc
    try:
        builder = getattr(module, builder_name)
    except AttributeError as exc:
        raise ValueError(
            f"module {module_path!r} has no attribute {builder_name!r}"
        ) from exc
    if not callable(builder):
        raise ValueError(f"builder {target!r} is not callable")
    return builder


def _compile_from_target(target: str) -> workflow.WorkflowManifest:
    builder = _load_builder(target)
    pipeline = builder()
    if not isinstance(pipeline, Pipeline):
        raise ValueError(
            f"builder {target!r} returned {type(pipeline).__name__}, expected Pipeline"
        )
    return compile_pipeline(pipeline)


def _output(data: Any, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(data, sort_keys=True, indent=2)
    return to_yaml(data)


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


def _cmd_check(args: argparse.Namespace) -> int:
    try:
        manifest = _compile_from_target(args.module)
    except Exception as exc:
        print(f"check failed: {exc}", file=sys.stderr)
        return 1
    print(f"ok: {manifest.id} ({manifest.manifest_hash})")
    return 0


def _cmd_manifest(args: argparse.Namespace) -> int:
    try:
        manifest = _compile_from_target(args.module)
    except Exception as exc:
        print(f"manifest failed: {exc}", file=sys.stderr)
        return 1
    print(_output(manifest.to_dict(include_hashes=True), args.format))
    return 0


def _cmd_dot(args: argparse.Namespace) -> int:
    try:
        manifest = _compile_from_target(args.module)
    except Exception as exc:
        print(f"dot failed: {exc}", file=sys.stderr)
        return 1
    print(to_dot(manifest))
    return 0


def _cmd_dry_run(args: argparse.Namespace) -> int:
    try:
        manifest = _compile_from_target(args.module)
    except Exception as exc:
        print(f"dry-run failed: {exc}", file=sys.stderr)
        return 1
    print(_output(dry_run(manifest), args.format))
    return 0


def _parse_budget(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    return json.loads(raw)


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        manifest = _compile_from_target(args.module)
    except Exception as exc:
        print(f"run failed: {exc}", file=sys.stderr)
        return 1

    artifact_root = Path(args.artifact_root or f"./runs/{manifest.id}")
    backend = None
    if args.backend == "fake":
        backend = SkeletalBackend()

    state_store = None
    if args.state_store_dir:
        state_store = FileStateStore(args.state_store_dir)

    registries = ExecutionRegistries()
    budget = _parse_budget(args.budget)
    if budget is not None:
        from arnold.kernel import GovernorBudget

        registries.budget = GovernorBudget(
            cost_limit=budget.get("max_cost"),
            seconds_limit=budget.get("max_seconds"),
            token_limit=budget.get("token_budget"),
        )

    logger = ExecutionLogger()
    result = run(
        manifest,
        artifact_root=artifact_root,
        backend=backend,
        state_store=state_store,
        registries=registries,
        logger=logger,
    )
    _print_result(result)
    return 0 if result.state.value == "completed" else 1


def _cmd_resume(args: argparse.Namespace) -> int:
    try:
        manifest = _compile_from_target(args.module)
    except Exception as exc:
        print(f"resume failed: {exc}", file=sys.stderr)
        return 1

    resume_cursor = None
    if args.cursor:
        # cursor is the manifest coordinate key; resume from the manifest start.
        resume_cursor = manifest_coordinate(
            manifest.id, manifest.manifest_hash or ""
        ).cursor()
    elif args.node:
        resume_cursor = manifest_coordinate(
            manifest.id, manifest.manifest_hash or ""
        ).cursor(node=NodeRef(args.node))

    artifact_root = Path(args.artifact_root or f"./runs/{manifest.id}")
    backend = None
    if args.backend == "fake":
        backend = SkeletalBackend()

    state_store = None
    if args.state_store_dir:
        state_store = FileStateStore(args.state_store_dir)

    logger = ExecutionLogger()
    result = run(
        manifest,
        artifact_root=artifact_root,
        backend=backend,
        state_store=state_store,
        resume_cursor=resume_cursor,
        logger=logger,
    )
    _print_result(result)
    return 0 if result.state.value == "completed" else 1


def _cmd_describe(args: argparse.Namespace) -> int:
    try:
        manifest = _compile_from_target(args.module)
    except Exception as exc:
        print(f"describe failed: {exc}", file=sys.stderr)
        return 1
    view = inspect_manifest(manifest)
    view["builder_target"] = args.module
    print(_output(view, args.format))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="arnold workflow",
        description="Compile, inspect, and run explicit-node Arnold workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, help_text in [
        ("check", "Validate a pipeline builder target."),
        ("manifest", "Emit the compiled workflow manifest."),
        ("dot", "Emit a DOT graph of the compiled manifest."),
        ("dry-run", "Print a dry-run report without executing."),
        ("run", "Run a compiled workflow manifest."),
        ("resume", "Resume a workflow from a checkpoint or cursor."),
        ("describe", "Manifest-backed describe (replaces arnold pipelines describe)."),
    ]:
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument(
            "--module",
            required=True,
            help="Builder target: package.module:build_pipeline",
        )
        sub.add_argument(
            "--format",
            choices=["yaml", "json"],
            default="yaml",
            help="Output format for manifest/dry-run/describe.",
        )
        if name in {"run", "resume"}:
            sub.add_argument(
                "--artifact-root",
                help="Directory for the journal and artifacts.",
            )
            sub.add_argument(
                "--state-store-dir",
                help="Directory for JSON checkpoints.",
            )
            sub.add_argument(
                "--backend",
                choices=["local", "fake"],
                default="local",
                help="Execution backend (default: local).",
            )
        if name == "run":
            sub.add_argument(
                "--budget",
                help='JSON budget object, e.g. {"max_cost": 10.0}.',
            )
        if name == "resume":
            sub.add_argument(
                "--cursor",
                action="store_true",
                help="Resume from the manifest coordinate cursor.",
            )
            sub.add_argument(
                "--node",
                help="Resume from a specific node id.",
            )

    dispatch = {
        "check": _cmd_check,
        "manifest": _cmd_manifest,
        "dot": _cmd_dot,
        "dry-run": _cmd_dry_run,
        "run": _cmd_run,
        "resume": _cmd_resume,
        "describe": _cmd_describe,
    }

    args = parser.parse_args(argv)
    return dispatch[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
