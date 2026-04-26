from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from vibecomfy.commands._workflow_path import resolve_workflow_path
from vibecomfy.ingest.loader import load_template
from vibecomfy.model_assets import extract_from_raw_workflow
from vibecomfy.registry import load_workflow_reference
from vibecomfy.schema import get_schema_provider
from vibecomfy.workflow import VibeEdge, VibeWorkflow
from vibecomfy.node_packs import resolve_node_packs, unresolved_class_types


def _cmd_doctor(args: argparse.Namespace) -> int:
    schema_provider = get_schema_provider("auto")
    try:
        workflow = load_workflow_reference(args.path, schema_provider=schema_provider, allow_scratchpad=True)
    except Exception as exc:
        print("Layer: Python scratchpad import/build")
        print(f"Error: {type(exc).__name__}: {exc}")
        print("Next: fix the Python file until build() returns a VibeWorkflow.")
        return 1
    report = workflow.validate(schema_provider=schema_provider)
    if not report.ok:
        print("Layer: VibeWorkflow validation")
        for issue in report.issues:
            print(f"- {issue.code}: {issue.message}")
        missing_classes = {
            str(issue.detail.get("class_type"))
            for issue in report.issues
            if issue.code == "unknown_class_type" and issue.detail.get("class_type")
        }
        if missing_classes:
            packs = resolve_node_packs(missing_classes)
            if packs:
                print("Suggested custom node packs:")
                for pack in packs:
                    packages = f" (pip: {', '.join(pack.pip_packages)})" if pack.pip_packages else ""
                    print(f"- {pack.name}: {pack.repo}{packages}")
            unresolved = unresolved_class_types(missing_classes)
            if unresolved:
                print("Unmapped node classes:")
                for class_type in unresolved:
                    print(f"- {class_type}")
        return 1
    missing_models = _missing_model_warnings(workflow, args.path)
    if missing_models:
        print("Missing models:")
        for warning in missing_models:
            print(f"- {warning}")
        return 1
    warnings = _doctor_warnings(workflow)
    if warnings:
        print("Local checks passed with runtime warnings:")
        for warning in warnings:
            print(f"- {warning}")
        return 0
    print("No local issues found. Runtime/model/node failures require `vibecomfy run` logs.")
    return 0


def _doctor_warnings(workflow: VibeWorkflow) -> list[str]:
    warnings: list[str] = []
    warnings.extend(_embedded_configuration_warnings())
    warnings.extend(_video_audio_warnings(workflow))
    return warnings


def _missing_model_warnings(workflow: VibeWorkflow, path: str) -> list[str]:
    import vibecomfy.fetch as fetch_assets

    warnings: list[str] = []
    for entry in _model_asset_entries(workflow, path):
        if fetch_assets.is_present(entry):
            continue
        warnings.append(
            f"missing model {entry['name']}: expected {fetch_assets.local_path(entry)} — fetch from {entry['url']}"
        )
    return warnings


def _model_asset_entries(workflow: VibeWorkflow, workflow_ref: str) -> list[dict]:
    entries = workflow.metadata.get("model_assets", [])
    if entries:
        return [entry for entry in entries if isinstance(entry, dict)]
    path = _json_path_for_reference(workflow_ref)
    if path is None:
        return []
    return extract_from_raw_workflow(load_template(path))


def _json_path_for_reference(workflow_ref: str) -> str | None:
    path = Path(workflow_ref)
    if path.suffix.lower() == ".json" and path.is_file():
        return str(path)
    try:
        resolved = Path(resolve_workflow_path(workflow_ref))
    except FileNotFoundError:
        return None
    if resolved.suffix.lower() == ".json" and resolved.is_file():
        return str(resolved)
    return None


def _embedded_configuration_warnings() -> list[str]:
    raw = os.environ.get("VIBECOMFY_COMFY_CONFIGURATION")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [f"VIBECOMFY_COMFY_CONFIGURATION is not valid JSON: {exc}"]
    if not isinstance(parsed, dict):
        return ["VIBECOMFY_COMFY_CONFIGURATION must be a JSON object."]
    try:
        from vibecomfy.runtime.run import _embedded_configuration
        from vibecomfy.workflow import WorkflowSource

        probe = VibeWorkflow(id="doctor", source=WorkflowSource(id="doctor"))
        config = _embedded_configuration(probe)
    except Exception as exc:
        return [f"embedded configuration could not be constructed: {type(exc).__name__}: {exc}"]
    if config is not None and not hasattr(config, "cwd"):
        return ["embedded configuration is not a Comfy Configuration object; embedded runtime will fail before queueing."]
    return []


def _video_audio_warnings(workflow: VibeWorkflow) -> list[str]:
    warnings: list[str] = []
    edges_by_target = {(edge.to_node, edge.to_input): edge for edge in workflow.edges}
    for node_id, node in sorted(workflow.nodes.items()):
        if node.class_type != "CreateVideo":
            continue
        audio_edge = edges_by_target.get((node_id, "audio"))
        if audio_edge is None and _literal_input(node.inputs, "audio") is None:
            continue
        source = _audio_source(workflow, audio_edge, node.inputs.get("audio"))
        warnings.append(
            "CreateVideo node "
            f"{node_id} has optional audio input connected"
            f"{f' from {source}' if source else ''}; for smoke tests, remove this edge if SaveVideo fails with AAC NaN/Inf."
        )
    return warnings


def _literal_input(inputs: dict[str, Any], name: str) -> Any:
    value = inputs.get(name)
    if isinstance(value, list) and len(value) == 2:
        return None
    return value


def _audio_source(workflow: VibeWorkflow, edge: VibeEdge | None, literal: Any) -> str | None:
    if edge is not None:
        node = workflow.nodes.get(edge.from_node)
        if node is None:
            return edge.from_node
        return f"{edge.from_node}:{node.class_type}"
    if isinstance(literal, list) and len(literal) == 2:
        node = workflow.nodes.get(str(literal[0]))
        if node is None:
            return str(literal[0])
        return f"{literal[0]}:{node.class_type}"
    return None


def register(subparsers) -> None:
    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("path")
    doctor.set_defaults(func=_cmd_doctor)
