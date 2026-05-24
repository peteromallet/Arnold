from __future__ import annotations

import json
from types import SimpleNamespace

import tools.check_strict_ready_templates as gate


def test_strict_ready_gate_report_is_repo_only_and_deterministic() -> None:
    first = gate.build_strict_ready_report()
    second = gate.build_strict_ready_report()

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["version"] == 1
    assert first["template_count"] >= first["target_count"] > 0
    assert all(target["source_scope"] == "repo" for target in first["targets"])
    assert all(target["indexed"] is True for target in first["targets"])
    assert all(target["source_scope"] != "dynamic" for target in first["targets"])
    assert first["diagnostics"] == sorted(
        first["diagnostics"],
        key=lambda item: (item["ready_id"], item["category"], item["code"], item["target"]),
    )


def test_static_drift_diagnostics_report_public_contract_mismatch(monkeypatch) -> None:
    class _Contract:
        def to_dict(self) -> dict[str, object]:
            return {
                "public_inputs": [{"name": "prompt", "node_id": "2", "field": "text"}],
                "public_outputs": [],
            }

    monkeypatch.setattr(gate, "_workflow_from_repo_template", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(gate, "build_contract", lambda _workflow: _Contract())
    diagnostics = gate._static_drift_diagnostics(
        {
            "id": "image/example",
            "path": "ready_templates/image/example.py",
            "public_inputs": [{"name": "prompt", "node_id": "1", "field": "text"}],
            "public_outputs": [],
        },
        ready_id="image/example",
        enforced=True,
    )

    assert [item["code"] for item in diagnostics] == [
        "static_contract_inputs_only_built",
        "static_contract_inputs_only_static",
    ]
    assert all(item["severity"] == "error" and item["enforced"] is True for item in diagnostics)


def test_generated_style_diagnostics_are_warnings_until_protected() -> None:
    entry = SimpleNamespace(
        marker="generated",
        counts=SimpleNamespace(
            positional_outs=1,
            widget_n_fields=0,
            uuid_class_types=0,
            n_uuid_variables=0,
            local_node_copies=0,
            missing_output_contract=True,
        ),
    )

    diagnostics = gate._style_diagnostics(
        entry,
        ready_id="image/generated",
        path="ready_templates/image/generated.py",
        enforced=False,
    )

    assert [item["code"] for item in diagnostics] == [
        "generated_template_positional_out",
        "generated_template_missing_output_contract",
    ]
    assert all(item["severity"] == "warning" and item["enforced"] is False for item in diagnostics)


def test_strict_ready_gate_main_exits_nonzero_for_enforced_errors(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        gate,
        "build_strict_ready_report",
        lambda: {
            "ok": False,
            "target_count": 1,
            "summary": {"diagnostics": 1},
            "diagnostics": [
                {
                    "ready_id": "image/example",
                    "category": "strict_ready",
                    "code": "strict_ready_missing_public_input",
                    "target": "public_inputs",
                    "severity": "error",
                    "enforced": True,
                    "message": "missing input",
                }
            ],
        },
    )

    assert gate.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
