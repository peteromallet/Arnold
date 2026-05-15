from __future__ import annotations

import argparse
from dataclasses import asdict

from vibecomfy.contracts import build_contract
from vibecomfy.commands._output import emit
from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.ingest.normalize import detect_workflow_shape
from vibecomfy.patches.registry import find_applicable
from vibecomfy.schema import get_schema_provider


def _cmd_inspect(args: argparse.Namespace) -> int:
    workflow = load_workflow_any(args.workflow)
    raw = workflow.compile("api")
    shape = detect_workflow_shape(raw)
    schema_provider = get_schema_provider("auto")
    report = workflow.validate(schema_provider=schema_provider)
    applicable_patches = [
        {"name": patch.name, "rationale": patch.rationale(workflow)}
        for patch in find_applicable(workflow)
    ]
    contract = build_contract(workflow).to_dict()
    payload = {
        "id": workflow.id,
        "shape": shape,
        "nodes": len(workflow.nodes),
        "edges": len(workflow.edges),
        "inputs": sorted(workflow.inputs),
        "outputs": [asdict(output) for output in workflow.outputs],
        "models": workflow.requirements.models,
        "custom_nodes": workflow.requirements.custom_nodes,
        "status": "runnable" if report.ok else "unsupported",
        "applicable_patches": applicable_patches,
        "contract": contract,
        "contract_shape": contract["contract_shape"],
        "public_inputs": contract["public_inputs"],
        "public_outputs": contract["public_outputs"],
        "graph_contract": contract["graph_contract"],
        "readiness_level": contract["readiness_level"],
        "model_assets": contract["model_assets"],
    }
    return emit(payload, json=args.json, text_renderer=_render_inspect)


def _render_inspect(payload: dict) -> str:
    return "\n".join(
        [
            f"id: {payload['id']}",
            f"shape: {payload['shape']}",
            f"nodes: {payload['nodes']}",
            f"edges: {payload['edges']}",
            f"inputs: {', '.join(payload['inputs']) or '-'}",
            f"outputs: {', '.join(output['output_type'] for output in payload['outputs']) or '-'}",
            f"public inputs: {len(payload['public_inputs'])}",
            f"public outputs: {len(payload['public_outputs'])}",
            f"models: {payload['models']}",
            f"custom nodes: {payload['custom_nodes']}",
            f"readiness: {payload['readiness_level']}",
            f"status: {payload['status']}",
        ]
    )


def register(subparsers) -> None:
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("workflow")
    inspect.add_argument("--json", action="store_true")
    inspect.set_defaults(func=_cmd_inspect)
