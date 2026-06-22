"""Retained Arnold operator commands.

These commands project runtime state from manifests, event journals, artifacts,
and control transitions. They do not import legacy Megaplan authoring modules.

    arnold status --artifact-root ./runs/my-flow
    arnold trace --artifact-root ./runs/my-flow
    arnold inspect --artifact-root ./runs/my-flow
    arnold override --artifact-root ./runs/my-flow --transition resume --node n1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from arnold.execution.observability import build_progress_report
from arnold.kernel.journal import read_event_journal
from arnold.execution.result import ExecutionResult
from arnold.manifest import WorkflowManifest
from arnold.workflow import inspect_manifest, to_yaml


def _load_manifest_from_artifact_root(root: Path) -> WorkflowManifest:
    candidates = [
        root / "manifest.json",
        root / "workflow-manifest.json",
        root / "manifest.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            if candidate.suffix == ".yaml":
                import yaml

                payload = yaml.safe_load(candidate.read_text(encoding="utf-8"))
                return WorkflowManifest.from_json(json.dumps(payload))
            return WorkflowManifest.from_json(candidate.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"no manifest.json found under {root}")


def _cmd_status(args: argparse.Namespace) -> int:
    root = Path(args.artifact_root)
    events = read_event_journal(root)
    report = build_progress_report(events)
    payload = {
        "artifact_root": str(root),
        "total_nodes": report.total_nodes,
        "completed": report.completed,
        "failed": report.failed,
        "pending": report.pending,
        "suspended": report.suspended,
        "consumed_cost": report.consumed_cost,
        "remaining_cost": report.remaining_cost,
        "health_status": report.health_status,
    }
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0


def _cmd_trace(args: argparse.Namespace) -> int:
    root = Path(args.artifact_root)
    events = read_event_journal(root)
    for event in events:
        print(json.dumps(event, sort_keys=True, default=str))
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    root = Path(args.artifact_root)
    manifest = _load_manifest_from_artifact_root(root)
    view = inspect_manifest(manifest)
    view["artifact_root"] = str(root)
    print(to_yaml(view))
    return 0


def _cmd_override(args: argparse.Namespace) -> int:
    root = Path(args.artifact_root)
    manifest = _load_manifest_from_artifact_root(root)
    transition = args.transition
    node = args.node
    payload: dict[str, Any] = {
        "artifact_root": str(root),
        "manifest_id": manifest.id,
        "manifest_hash": manifest.manifest_hash,
        "transition": transition,
        "node": node,
        "projected": bool(args.node),
    }
    # Validate that the requested transition maps to a declared control slot.
    control_ids = {
        slot.transition_id
        for node in manifest.nodes
        if node.policy
        for slot in node.policy.control_transitions
    }
    if manifest.policy:
        control_ids.update(slot.transition_id for slot in manifest.policy.control_transitions)
    if transition in control_ids:
        payload["validated"] = True
    else:
        payload["validated"] = False
        payload["note"] = "transition not declared in manifest"
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="arnold",
        description="Retained Arnold operator commands.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser(
        "status", help="Print progress/status from an artifact root."
    )
    status_parser.add_argument("--artifact-root", required=True)

    trace_parser = subparsers.add_parser(
        "trace", help="Print the event journal from an artifact root."
    )
    trace_parser.add_argument("--artifact-root", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect", help="Inspect the manifest and control transitions."
    )
    inspect_parser.add_argument("--artifact-root", required=True)

    override_parser = subparsers.add_parser(
        "override", help="Project a control-transition override."
    )
    override_parser.add_argument("--artifact-root", required=True)
    override_parser.add_argument(
        "--transition", required=True, help="Control transition id."
    )
    override_parser.add_argument("--node", help="Target node id.")

    args = parser.parse_args(argv)
    dispatch = {
        "status": _cmd_status,
        "trace": _cmd_trace,
        "inspect": _cmd_inspect,
        "override": _cmd_override,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
