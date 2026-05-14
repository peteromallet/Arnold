from __future__ import annotations

import argparse

from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.commands._output import emit
from vibecomfy.contracts import build_contract, doctor_contract


def _cmd_contract_inspect(args: argparse.Namespace) -> int:
    workflow = load_workflow_any(args.workflow)
    contract = build_contract(workflow)
    payload = contract.to_dict()
    return emit(payload, json=args.json, text_renderer=_render_contract_inspect)


def _render_contract_inspect(payload: dict) -> str:
    lines = [
        f"version: {payload['version']}",
        f"workflow_id: {payload['workflow_id']}",
        f"readiness_level: {payload['readiness_level']}",
        f"model_assets: {len(payload['model_assets'])} entries",
        f"custom_nodes: {', '.join(payload['custom_nodes']) or '-'}",
        f"inputs: {', '.join(payload['inputs']) or '-'}",
        f"outputs: {len(payload['outputs'])} entries",
        f"runtime_nodes: {len(payload['runtime_nodes'])} entries",
        f"runtime_class_types: {len(payload['runtime_class_types'])} entries",
        f"runtime_packages: {len(payload['runtime_packages'])} entries",
    ]
    return "\n".join(lines)


def _cmd_contract_doctor(args: argparse.Namespace) -> int:
    workflow = load_workflow_any(args.workflow)
    contract = build_contract(workflow)
    report = doctor_contract(workflow, contract)
    payload = {
        "status": report.status,
        "contract": report.contract,
        "diagnostics": [
            {
                "code": d.code,
                "severity": d.severity,
                "message": d.message,
                "node_id": d.node_id,
                "class_type": d.class_type,
                "detail": d.detail,
                "recommendation": d.recommendation,
            }
            for d in report.diagnostics
        ],
    }
    exit_code = emit(payload, json=args.json, text_renderer=_render_contract_doctor)
    if report.status == "error":
        return 1
    return exit_code


def _render_contract_doctor(payload: dict) -> str:
    lines = [f"status: {payload['status']}"]
    if payload["diagnostics"]:
        lines.append("diagnostics:")
        for d in payload["diagnostics"]:
            lines.append(
                f"  [{d['severity'].upper()}] {d['code']}: {d['message']}"
            )
    return "\n".join(lines)


def register(subparsers) -> None:
    contract = subparsers.add_parser("contract")
    contract_subs = contract.add_subparsers(dest="contract_command")

    # contract inspect
    inspect = contract_subs.add_parser("inspect")
    inspect.add_argument("workflow")
    inspect.add_argument("--json", action="store_true")
    inspect.set_defaults(func=_cmd_contract_inspect)

    # contract doctor
    doctor = contract_subs.add_parser("doctor")
    doctor.add_argument("workflow")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=_cmd_contract_doctor)
