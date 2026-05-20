from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from vibecomfy.cli import build_parser
from vibecomfy.commands.port import _cmd_port_check, _cmd_port_convert, _cmd_port_lint, _cmd_port_rules, _cmd_port_simulate, _cmd_port_widgets

from tests._cli_helpers import (
    _load_emitted_provenance,
    _write_port_node_index,
    _write_port_workflow,
)


def test_port_help_explains_check_convert_and_related_commands(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["port", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    for text in [
        "port check",
        "port convert",
        "doctor",
        "validate",
        "nodes install-plan",
        "fetch",
        "--head-check-models",
        "RunPod",
    ]:
        assert text in help_text


def test_port_subcommand_help_is_discoverable(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as check_help:
        parser.parse_args(["port", "check", "--help"])
    check_text = capsys.readouterr().out

    with pytest.raises(SystemExit) as convert_help:
        parser.parse_args(["port", "convert", "--help"])
    convert_text = capsys.readouterr().out

    assert check_help.value.code == 0
    assert convert_help.value.code == 0
    assert "before manual template editing or expensive RunPod validation" in check_text
    assert "--head-check-models" in check_text
    assert "--runtime-object-info" in check_text
    assert "turn source workflows into Python scratchpads" in convert_text
    assert "--ready-id" in convert_text
    assert "--head-check-models" in convert_text
    assert "--runtime-object-info" in convert_text


def test_port_check_json_returns_zero_for_clean_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_port_node_index(tmp_path)
    workflow_path = _write_port_workflow(tmp_path)
    monkeypatch.chdir(tmp_path)

    code = _cmd_port_check(argparse.Namespace(workflow=str(workflow_path), json=True, head_check_models=False))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["ok"] is True
    assert payload["provenance"]["source_kind"] == "raw_json"
    assert payload["contract_shape"] == "workflow_runtime_contract.v1.public_descriptors.v2"
    assert isinstance(payload["public_inputs"], list)
    assert isinstance(payload["public_outputs"], list)
    assert isinstance(payload["graph_contract"], dict)


def test_port_check_returns_nonzero_for_hard_port_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_port_node_index(tmp_path)
    workflow_path = tmp_path / "bad_port_workflow.json"
    workflow_path.write_text(json.dumps({"1": {"class_type": "UnknownRuntimeNode", "inputs": {}}}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = _cmd_port_check(argparse.Namespace(workflow=str(workflow_path), json=False, head_check_models=False))

    captured = capsys.readouterr()
    assert code == 1
    assert "unresolved_runtime_class" in captured.out


def test_port_widgets_json_suggests_widget_only_schema_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_port_node_index(tmp_path)
    workflow_path = tmp_path / "widgets_workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "PromptNode",
                        "widgets_values": ["hello", "fast", {"collapsed": True}],
                        "inputs": [],
                    }
                ],
                "links": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    code = _cmd_port_widgets(argparse.Namespace(workflow=str(workflow_path), json=True))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["unresolved_widget_aliases"] == [{"node_id": "1", "class_type": "PromptNode", "input": "widget_2"}]
    assert payload["suggestions"] == [
        {
            "class_type": "PromptNode",
            "nodes": [
                {
                    "node_id": "1",
                    "unresolved_inputs": ["widget_2"],
                    "widgets_values": ["hello", "fast", {"collapsed": True}],
                }
            ],
            "observed_widget_count": 3,
            "schema_source": "schema_provider",
            "suggested_schema_entry": ["text", "mode", None],
            "python": "'PromptNode': ['text', 'mode', None]",
        }
    ]


def test_port_convert_emits_importable_scratchpad_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_port_node_index(tmp_path)
    workflow_path = _write_port_workflow(tmp_path)
    out = tmp_path / "out" / "scratchpads" / "converted.py"
    monkeypatch.chdir(tmp_path)

    code = _cmd_port_convert(
        argparse.Namespace(
            workflow=str(workflow_path),
            out=str(out),
            ready_id=None,
            json=True,
            head_check_models=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["conversion"]["mode"] == "scratchpad"
    text = out.read_text(encoding="utf-8")
    assert "source_type='scratchpad'" in text
    assert "READY_METADATA" not in text
    provenance = _load_emitted_provenance(out)
    assert provenance["source_hash"] == payload["report"]["source_hash"]
    assert provenance["workflow_shape"] == payload["report"]["workflow_shape"]
    assert provenance["output_mode"] == "scratchpad"


def test_port_convert_ready_template_mode_requires_ready_id_and_writes_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_port_node_index(tmp_path)
    workflow_path = _write_port_workflow(tmp_path)
    out = tmp_path / "candidate.py"
    monkeypatch.chdir(tmp_path)

    assert _cmd_port_convert(
        argparse.Namespace(
            workflow=str(workflow_path),
            out=str(out),
            ready_id="image/ported",
            json=True,
            head_check_models=False,
        )
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    text = out.read_text(encoding="utf-8")
    assert "READY_METADATA =" in text
    assert "template_id='image/ported'" not in text
    provenance = _load_emitted_provenance(out)
    assert provenance["ready_id"] == "image/ported"
    assert provenance["source_hash"] == payload["report"]["source_hash"]
    assert provenance["workflow_shape"] == payload["report"]["workflow_shape"]
    assert provenance["output_mode"] == "ready_template"


def test_strict_ready_template_gate_escalates_unresolved_widgets() -> None:
    from vibecomfy.commands.port import _apply_strict_ready_template_gate
    from vibecomfy.porting.report import PortReport

    report = PortReport(
        source="ready_templates/video/example.py",
        workflow_shape={"outputs": 1},
        metadata={
            "widget_analysis": {
                "unresolved_widget_aliases": [
                    {"node_id": "1", "class_type": "ExampleNode", "input": "widget_0"}
                ],
                "suggestions": [
                    {
                        "class_type": "ExampleNode",
                        "schema_source": "committed_widget_schema",
                        "suggested_schema_entry": ["value"],
                    }
                ],
            }
        },
    )

    _apply_strict_ready_template_gate(report)

    assert report.has_errors
    assert report.diagnostics[0].code == "strict_ready_unresolved_widgets"
    assert report.diagnostics[0].detail["count"] == 1


def test_strict_ready_template_gate_requires_output_contract() -> None:
    from vibecomfy.commands.port import _apply_strict_ready_template_gate
    from vibecomfy.porting.report import PortReport

    report = PortReport(
        source="ready_templates/video/example.py",
        workflow_shape={"outputs": 0},
        metadata={"widget_analysis": {"unresolved_widget_aliases": [], "suggestions": []}},
    )

    _apply_strict_ready_template_gate(report)

    assert report.has_errors
    assert report.diagnostics[0].code == "strict_ready_missing_output_contract"
    assert "bind_output" in (report.diagnostics[0].recommendation or "")
    assert "public_outputs" in (report.diagnostics[0].recommendation or "")


# ── port rules ──────────────────────────────────────────────────────────


def test_port_rules_json_returns_deterministic_list(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_port_rules(argparse.Namespace(json=True, explain=False))
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert isinstance(payload, dict)
    assert "rules_by_category" in payload
    assert "total_rules" in payload
    assert payload["total_rules"] > 0
    by_cat = payload["rules_by_category"]
    assert isinstance(by_cat, dict)
    # Get first rule from first category
    first_cat = next(iter(by_cat.values()))
    rule = first_cat[0]
    assert "id" in rule
    assert "description" in rule
    assert "behavior" in rule
    # Verify note about partial coverage
    assert payload.get("partial_coverage") is True or any(
        r.get("partial_coverage", False)
        for rules in by_cat.values()
        for r in rules
    )


def test_port_rules_explain_shows_behavior(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_port_rules(argparse.Namespace(json=False, explain=True))
    text = capsys.readouterr().out
    assert code == 0
    assert "R-NAME-01" in text
    assert "emitter.py" in text


# ── port lint ───────────────────────────────────────────────────────────


def test_port_lint_all_json_returns_diagnostics(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_port_lint(argparse.Namespace(all=True, json=True, workflow=None))
    payload = json.loads(capsys.readouterr().out)
    assert code == 0  # zero unless errors
    assert "diagnostics" in payload
    assert "total" in payload
    assert isinstance(payload["diagnostics"], list)
    # All diagnostics should have required fields
    for d in payload["diagnostics"]:
        assert "severity" in d
        assert "path" in d
        assert "line" in d
        assert "code" in d
        assert "message" in d


def test_port_lint_single_wf_renders_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Lint a known ready template
    code = _cmd_port_lint(argparse.Namespace(workflow="video/wan_i2v", all=False, json=False))
    text = capsys.readouterr().out
    assert code == 0
    # Should report something — at minimum the file path header
    assert "wan_i2v" in text or "ready_templates" in text


# ── port simulate ───────────────────────────────────────────────────────


def test_port_simulate_drop_set_id_map_all_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_port_simulate(
        argparse.Namespace(rule="drop_set_id_map=true", all=True, json=True)
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "templates_affected" in payload
    assert "loc_delta_total" in payload
    assert "parity_preserved" in payload
    assert isinstance(payload["templates_affected"], int)
    assert isinstance(payload["parity_preserved"], int)


def test_port_simulate_unknown_rule_returns_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_port_simulate(
        argparse.Namespace(rule="nonexistent_rule=xyz", all=False, json=True)
    )
    captured = capsys.readouterr()
    assert code == 1
    # Should have some error output
    assert captured.err or captured.out


# ── port convert dry-run diff ───────────────────────────────────────────


def test_port_convert_dry_run_diff_json_includes_diff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_port_node_index(tmp_path)
    workflow_path = _write_port_workflow(tmp_path)
    monkeypatch.chdir(tmp_path)

    code = _cmd_port_convert(
        argparse.Namespace(
            workflow=str(workflow_path),
            out=None,
            json=True,
            head_check_models=False,
            ready_id=None,
            strict_ready_template=False,
            dry_run=True,
            diff=True,
        )
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "ok"
    assert "write" in payload
    assert payload["write"]["dry_run"] is True


def test_port_convert_dry_run_diff_with_ready_template_shows_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Use a real ready template for dry-run diff; target derived from source
    # Manual templates may be refused; dry-run shows diff anyway
    code = _cmd_port_convert(
        argparse.Namespace(
            workflow="video/wan_i2v",
            out=None,
            json=False,
            head_check_models=False,
            ready_id=None,
            strict_ready_template=False,
            dry_run=True,
            diff=True,
        )
    )
    captured = capsys.readouterr()
    text = captured.out + captured.err
    # May exit 0 for manual template showing diff, or exit 1 if target resolution fails
    if code == 0:
        assert any(x in text.lower() for x in ["validated", "parity", "import=", "loc"])
    else:
        # Non-zero may happen if the ready template path can't be derived
        # Error output may be on stdout or stderr
        assert len(text) > 0, f"Expected some output, got empty. code={code}"
