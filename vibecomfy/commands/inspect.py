from __future__ import annotations

import argparse

from vibecomfy.commands._workflow_path import resolve_workflow_path
from vibecomfy.ingest.loader import load_template
from vibecomfy.ingest.normalize import detect_workflow_shape
from vibecomfy.registry import load_workflow_reference
from vibecomfy.schema import get_schema_provider


def _cmd_inspect(args: argparse.Namespace) -> int:
    path = resolve_workflow_path(args.workflow)
    raw = load_template(path)
    shape = detect_workflow_shape(raw)
    schema_provider = get_schema_provider("auto")
    workflow = load_workflow_reference(args.workflow, schema_provider=schema_provider)
    print(f"id: {workflow.id}")
    print(f"shape: {shape}")
    print(f"nodes: {len(workflow.nodes)}")
    print(f"edges: {len(workflow.edges)}")
    print(f"inputs: {', '.join(workflow.inputs) or '-'}")
    print(f"outputs: {', '.join(output.output_type for output in workflow.outputs) or '-'}")
    print(f"models: {workflow.requirements.models}")
    print(f"custom nodes: {workflow.requirements.custom_nodes}")
    print(f"status: {'runnable' if workflow.validate(schema_provider=schema_provider).ok else 'unsupported'}")
    return 0


def register(subparsers) -> None:
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("workflow")
    inspect.set_defaults(func=_cmd_inspect)
