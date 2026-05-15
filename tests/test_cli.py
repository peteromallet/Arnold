from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import pytest

from vibecomfy.cli import build_parser
from vibecomfy.commands import COMMANDS, CommandSpec, load_command
from vibecomfy.commands.doctor import _doctor_warnings
from vibecomfy.commands.fetch import _cmd_fetch
from vibecomfy.commands.nodes import _cmd_nodes_ensure, _cmd_nodes_install, _cmd_nodes_install_plan, _cmd_nodes_list, _cmd_nodes_restore
from vibecomfy.commands.port import _cmd_port_check, _cmd_port_convert, _cmd_port_widgets
from vibecomfy.commands.contract import _cmd_contract_inspect, _cmd_contract_doctor
import vibecomfy.node_packs_install as node_packs_install
import vibecomfy.commands.validate as validate_cmd
from vibecomfy.commands._workflow_path import resolve_workflow_path
from vibecomfy.commands.workflows import _cmd_workflows_contract_validate, _cmd_workflows_enrich_targets, _cmd_workflows_lens, _cmd_workflows_list, _cmd_workflows_source_info
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def _top_level_commands(parser: argparse.ArgumentParser) -> list[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return list(action.choices)
    raise AssertionError("parser has no subparsers")


def _write_fetch_scratchpad(tmp_path: Path) -> Path:
    scratchpad = tmp_path / "fetch_scratch.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def build():
    workflow = VibeWorkflow(id="fetch-test", source=WorkflowSource(id="fetch-test"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="CheckpointLoaderSimple")
    workflow.metadata["model_assets"] = [
        {
            "name": "present.safetensors",
            "url": "https://example.test/present.safetensors",
            "subdir": "checkpoints",
        },
        {
            "name": "missing.safetensors",
            "url": "https://example.test/missing.safetensors",
            "subdir": "checkpoints",
        },
    ]
    return workflow
""",
        encoding="utf-8",
    )
    return scratchpad


def test_cli_command_registry_is_explicit_and_ordered() -> None:
    assert [spec.name for spec in COMMANDS] == [
        "sources",
        "workflows",
        "nodes",
        "analyze",
        "search",
        "inspect",
        "port",
        "convert",
        "contract",
        "validate",
        "doctor",
        "fetch",
        "models",
        "run",
        "runtime",
        "session",
        "logs",
        "runpod",
        "watchdog",
    ]


def test_build_parser_registers_all_known_commands() -> None:
    parser = build_parser()

    assert _top_level_commands(parser) == [spec.name for spec in COMMANDS]


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
    assert "turn source workflows into Python scratchpads" in convert_text
    assert "--ready-id" in convert_text
    assert "--head-check-models" in convert_text


def test_validate_no_schema_skips_schema_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scratchpad = tmp_path / "workflow.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def build():
    workflow = VibeWorkflow("validate-no-schema", WorkflowSource("validate-no-schema"))
    workflow.nodes["1"] = VibeNode("1", "UnknownRuntimeOnlyNode")
    return workflow
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        validate_cmd,
        "get_schema_provider",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("schema provider should not be built")),
    )

    assert validate_cmd._cmd_validate(argparse.Namespace(path=str(scratchpad), backend="api", no_schema=True)) == 0
    assert capsys.readouterr().out == "ok\n"


def _write_port_node_index(tmp_path: Path) -> None:
    (tmp_path / "node_index.json").write_text(
        json.dumps(
            [
                {
                    "class_type": "LoadImage",
                    "pack": "core",
                    "inputs": {"image": {"type": "STRING", "required": True}},
                    "outputs": [{"type": "IMAGE", "name": "image"}],
                },
                {
                    "class_type": "SaveImage",
                    "pack": "core",
                    "inputs": {
                        "images": {"type": "IMAGE", "required": True},
                        "filename_prefix": {"type": "STRING", "required": True},
                    },
                    "outputs": [],
                },
                {
                    "class_type": "PromptNode",
                    "pack": "core",
                    "inputs": {
                        "clip": {"type": "CLIP", "required": True},
                        "text": {"type": "STRING", "required": True},
                        "mode": {"type": "STRING", "required": False},
                    },
                    "outputs": [],
                },
            ]
        ),
        encoding="utf-8",
    )


def _write_port_workflow(tmp_path: Path) -> Path:
    workflow_path = tmp_path / "port_workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "1": {"class_type": "LoadImage", "inputs": {"image": "input.png"}},
                "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": "out/port"}},
            }
        ),
        encoding="utf-8",
    )
    return workflow_path


def _load_emitted_provenance(path: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location(f"test_emitted_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build().source.provenance


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
    assert "'ready_template': 'image/ported'" in text
    provenance = _load_emitted_provenance(out)
    assert provenance["ready_id"] == "image/ported"
    assert provenance["source_hash"] == payload["report"]["source_hash"]
    assert provenance["workflow_shape"] == payload["report"]["workflow_shape"]
    assert provenance["output_mode"] == "ready_template"


def test_fetch_cli_dry_run_lists_entries_without_downloading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scratchpad = _write_fetch_scratchpad(tmp_path)
    present = tmp_path / "models" / "checkpoints" / "present.safetensors"
    present.parent.mkdir(parents=True)
    present.write_bytes(b"present")
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path / "models"))
    calls = 0

    def download_many(_entries, *, force=False):
        nonlocal calls
        calls += 1
        raise AssertionError("download_many must not be called during dry-run")

    import vibecomfy.fetch as fetch_assets

    monkeypatch.setattr(fetch_assets, "download_many", download_many)

    assert _cmd_fetch(argparse.Namespace(workflow=str(scratchpad), force=False, dry_run=True)) == 0

    captured = capsys.readouterr()
    assert "present present.safetensors" in captured.out
    assert f"would fetch missing.safetensors -> {tmp_path / 'models' / 'checkpoints' / 'missing.safetensors'}" in captured.out
    assert calls == 0


def test_fetch_cli_invokes_download_many(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scratchpad = _write_fetch_scratchpad(tmp_path)
    calls: list[tuple[list[dict], bool]] = []

    def download_many(entries, *, force=False):
        calls.append((entries, force))
        return []

    import vibecomfy.fetch as fetch_assets

    monkeypatch.setattr(fetch_assets, "download_many", download_many)

    assert _cmd_fetch(argparse.Namespace(workflow=str(scratchpad), force=True, dry_run=False)) == 0

    assert calls == [
        (
            [
                {
                    "name": "present.safetensors",
                    "url": "https://example.test/present.safetensors",
                    "subdir": "checkpoints",
                },
                {
                    "name": "missing.safetensors",
                    "url": "https://example.test/missing.safetensors",
                    "subdir": "checkpoints",
                },
            ],
            True,
        )
    ]


def test_command_modules_expose_register() -> None:
    for spec in COMMANDS:
        assert callable(load_command(spec).register)


def test_load_command_rejects_module_without_register() -> None:
    with pytest.raises(TypeError, match="must expose register"):
        load_command(CommandSpec("argparse", "argparse"))


def test_resolve_workflow_path_accepts_existing_path(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.json"
    workflow.write_text("{}", encoding="utf-8")

    assert resolve_workflow_path(str(workflow)) == str(workflow)


def test_resolve_workflow_path_rejects_empty_or_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_workflow_path("")

    with pytest.raises(FileNotFoundError):
        resolve_workflow_path(str(tmp_path))


def test_resolve_workflow_path_accepts_index_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workflow = tmp_path / "workflow.json"
    workflow.write_text("{}", encoding="utf-8")
    (tmp_path / "workflow_index.json").write_text(
        json.dumps([{"id": "sample", "path": str(workflow)}]),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert resolve_workflow_path("sample") == str(workflow)


def test_resolve_workflow_path_raises_for_unknown_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError):
        resolve_workflow_path("missing")


def test_workflows_list_reports_malformed_index_with_recovery_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "workflow_index.json").write_text("{not-json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert _cmd_workflows_list(argparse.Namespace(ready=False, limit=10)) == 1

    captured = capsys.readouterr()
    assert "workflow_index.json could not be read" in captured.err
    assert "vibecomfy sources sync" in captured.err


def test_workflows_source_info_json_reports_pure_python_source(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _cmd_workflows_source_info(argparse.Namespace(template_id="image/z_image", json=True))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["template_id"] == "image/z_image"
    assert payload["source_mode"] == "pure_python"
    assert payload["runtime_source_of_truth"] is True


def test_workflows_source_info_accepts_policy_applied_python_fork(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _cmd_workflows_source_info(
        argparse.Namespace(
            template_id="video/ltx2_3_runexx_first_last_raw_video_guide",
            json=True,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["template_id"] == "video/ltx2_3_runexx_first_last_raw_video_guide"
    assert payload["source_mode"] == "pure_python"
    assert payload["runtime_source_of_truth"] is True


def test_workflows_enrich_targets_writes_schema_and_asset_metadata(tmp_path: Path) -> None:
    targets_path = tmp_path / "targets.json"
    output_path = tmp_path / "enriched.json"
    models_root = tmp_path / "models"
    targets_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "selector": {"backend": "vibecomfy"},
                "selection": {"case_names": ["z_image_turbo"]},
                "targets": [
                    {
                        "case_name": "z_image_turbo",
                        "task_type": "z_image_turbo",
                        "route_key": "z_image_turbo",
                        "template_id": "image/z_image",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    code = _cmd_workflows_enrich_targets(
        argparse.Namespace(
            targets_json=str(targets_path),
            output=str(output_path),
            models_root=models_root,
        )
    )

    assert code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["producer"] == "vibecomfy.workflows.enrich-targets"
    assert payload["templates"] == ["image/z_image"]
    assert payload["target_count"] == 1
    assert payload["template_count"] == 1
    target = payload["targets"][0]
    assert target["source"]["source_mode"] == "pure_python"
    assert target["schema"]["node_count"] > 0
    assert "SaveImage" in target["schema"]["class_types"]
    assets = {asset["name"]: asset for asset in target["assets"]}
    assert "z_image_bf16.safetensors" in assets
    assert assets["z_image_bf16.safetensors"]["expected_path"].startswith(str(models_root))
    assert assets["z_image_bf16.safetensors"]["present"] is False
    missing_asset_issues = [item for item in target["issues"] if item["code"] == "missing_model_asset"]
    assert missing_asset_issues
    missing_z_image = next(
        item for item in missing_asset_issues if item["detail"]["name"] == "z_image_bf16.safetensors"
    )
    assert missing_z_image["detail"]["expected_path"] == assets["z_image_bf16.safetensors"]["expected_path"]
    assert missing_asset_issues[0]["detail"]["paths_checked"]
    assert "curl -L" in (missing_asset_issues[0]["detail"]["remediation"] or "")


def test_workflows_enrich_targets_treats_orchestrators_as_non_template_info(tmp_path: Path):
    targets_path = tmp_path / "targets.json"
    output_path = tmp_path / "enriched.json"
    targets_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "selector": {"backend": "vibecomfy"},
                "selection": {"case_names": ["travel_orchestrator_wan2_1seg"]},
                "targets": [
                    {
                        "case_name": "travel_orchestrator_wan2_1seg",
                        "task_type": "travel_orchestrator",
                        "route_key": "travel_orchestrator",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    code = _cmd_workflows_enrich_targets(
        argparse.Namespace(
            targets_json=str(targets_path),
            output=str(output_path),
            models_root=str(tmp_path / "models"),
        )
    )

    assert code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["target_count"] == 1
    assert payload["template_count"] == 0
    assert payload["templates"] == []
    target = payload["targets"][0]
    assert target["enrichment_status"] == "skipped"
    assert target["issues"] == [
        {
            "group": "workflow_source",
            "code": "non_template_target",
            "severity": "info",
            "message": "Target does not execute a VibeComfy template directly.",
        }
    ]


def test_nodes_list_reports_malformed_index_with_recovery_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text("{not-json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert _cmd_nodes_list(argparse.Namespace(limit=10)) == 1

    captured = capsys.readouterr()
    assert "node_index.json could not be read" in captured.err
    assert "vibecomfy sources sync" in captured.err


def test_doctor_warns_about_optional_video_audio_edge() -> None:
    workflow = VibeWorkflow("video", WorkflowSource("video"))
    workflow.nodes["1"] = VibeNode("1", "LTXVAudioVAEDecode")
    workflow.nodes["2"] = VibeNode("2", "CreateVideo")
    workflow.edges.append(VibeEdge("1", "0", "2", "audio"))

    warnings = _doctor_warnings(workflow)

    assert any("CreateVideo node 2 has optional audio input connected from 1:LTXVAudioVAEDecode" in item for item in warnings)


def test_doctor_warns_about_kj_ltx_audio_vae_loader() -> None:
    workflow = VibeWorkflow("audio-vae", WorkflowSource("audio-vae"))
    workflow.nodes["175"] = VibeNode(
        "175",
        "VAELoaderKJ",
        inputs={"vae_name": "LTX23_audio_vae_bf16.safetensors"},
    )

    warnings = _doctor_warnings(workflow)

    assert any("Use LTXVAudioVAELoader with the file staged under checkpoints" in item for item in warnings)


def test_doctor_suggests_custom_node_pack_for_unknown_class(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text(
        json.dumps([{"class_type": "SaveImage", "pack": "core", "inputs": {}, "outputs": []}]),
        encoding="utf-8",
    )
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeWorkflow, WorkflowSource, VibeNode

def build():
    workflow = VibeWorkflow(id="x", source=WorkflowSource(id="x"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="DWPreprocessor")
    return workflow
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    from vibecomfy.commands.doctor import _cmd_doctor

    # B5 lockfile drift verification is default-on per Step 16; this test predates B5 and isolates from the seam to keep its existing assertions stable.
    monkeypatch.setattr("vibecomfy.commands.doctor._read_doctor_lockfile", lambda: [])
    assert _cmd_doctor(argparse.Namespace(path=str(scratchpad))) == 1

    captured = capsys.readouterr()
    assert "Suggested custom node packs:" in captured.out
    assert "comfyui_controlnet_aux" in captured.out
    assert "vibecomfy port check" in captured.out


def test_doctor_points_helper_diagnostics_to_port_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scratchpad = tmp_path / "helper_issue.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource

def build():
    workflow = VibeWorkflow(id="helper", source=WorkflowSource(id="helper"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="GetNode", inputs={"widget_0": "missing"})
    workflow.nodes["2"] = VibeNode(id="2", class_type="SaveImage", inputs={"filename_prefix": "out/helper"})
    workflow.edges.append(VibeEdge("1", "0", "2", "images"))
    return workflow
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    from vibecomfy.commands.doctor import _cmd_doctor

    monkeypatch.setattr("vibecomfy.commands.doctor._read_doctor_lockfile", lambda: [])
    assert _cmd_doctor(argparse.Namespace(path=str(scratchpad), json=False, lint=False, allow_drift=False)) == 1

    captured = capsys.readouterr()
    assert "Porting helper diagnostics" in captured.out
    assert f"vibecomfy port check {scratchpad} --json" in captured.out


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


def test_nodes_install_plan_suggests_pack_for_missing_class(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text(
        json.dumps([{"class_type": "PreviewAudio", "pack": "core", "inputs": {}, "outputs": []}]),
        encoding="utf-8",
    )
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeWorkflow, WorkflowSource, VibeNode

def build():
    workflow = VibeWorkflow(id="x", source=WorkflowSource(id="x"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="Qwen3CustomVoice")
    return workflow
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert _cmd_nodes_install_plan(argparse.Namespace(path=str(scratchpad), json=False)) == 0

    captured = capsys.readouterr()
    assert "ComfyUI-Qwen3-TTS" in captured.out
    assert "Qwen3CustomVoice" in captured.out


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        ("installed", 0),
        ("refreshed", 0),
        ("skipped_dirty", 1),
        ("failed", 1),
    ],
)
def test_cmd_nodes_install_translates_install_result_to_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: str,
    expected_code: int,
) -> None:
    def fake_install_pack(**kwargs):
        assert kwargs == {"name": "ExamplePack", "repo": None, "force": False}
        return node_packs_install.InstallResult(
            name="ExamplePack",
            status=status,  # type: ignore[arg-type]
            git_commit_sha="abc123" if status in {"installed", "refreshed"} else None,
            error="install issue" if status in {"skipped_dirty", "failed"} else None,
        )

    monkeypatch.setattr(node_packs_install, "install_pack", fake_install_pack)

    code = _cmd_nodes_install(argparse.Namespace(name="ExamplePack", repo=None, force=False))

    captured = capsys.readouterr()
    assert code == expected_code
    assert f"ExamplePack: {status}" in captured.out
    if expected_code:
        assert "install issue" in captured.err
    else:
        assert captured.err == ""


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        ("installed", 0),
        ("refreshed", 0),
        ("skipped_dirty", 1),
        ("failed", 1),
    ],
)
def test_cmd_nodes_restore_translates_results_to_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: str,
    expected_code: int,
) -> None:
    lockfile = tmp_path / "custom_nodes.lock"
    lockfile.write_text("ExamplePack abc123 https://example.test/example.git\n", encoding="utf-8")

    def fake_restore_pack(entry):
        assert entry.name == "ExamplePack"
        assert entry.git_commit_sha == "abc123"
        return node_packs_install.InstallResult(
            name="ExamplePack",
            status=status,  # type: ignore[arg-type]
            git_commit_sha="abc123" if status in {"installed", "refreshed"} else None,
            error="restore issue" if status in {"skipped_dirty", "failed"} else None,
        )

    monkeypatch.setattr(node_packs_install, "restore_pack", fake_restore_pack)

    code = _cmd_nodes_restore(argparse.Namespace(lockfile=str(lockfile)))

    captured = capsys.readouterr()
    assert code == expected_code
    assert f"ExamplePack: {status}" in captured.out
    if expected_code:
        assert "restore issue" in captured.err
    else:
        assert captured.err == ""


def test_cmd_nodes_ensure_dry_run_does_not_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text(
        json.dumps([{"class_type": "SaveImage", "pack": "core", "inputs": {}, "outputs": []}]),
        encoding="utf-8",
    )
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeWorkflow, WorkflowSource, VibeNode

def build():
    workflow = VibeWorkflow(id="x", source=WorkflowSource(id="x"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="Qwen3CustomVoice")
    return workflow
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    def fail_install_pack(**_kwargs):
        raise AssertionError("install_pack must not be called during dry-run")

    monkeypatch.setattr(node_packs_install, "install_pack", fail_install_pack)

    code = _cmd_nodes_ensure(argparse.Namespace(template=None, workflow=str(scratchpad), dry_run=True))

    captured = capsys.readouterr()
    assert code == 0
    assert "Suggested custom node packs:" in captured.out
    assert "ComfyUI-Qwen3-TTS" in captured.out


def test_ensure_calls_install_for_each_missing_pack(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text(
        json.dumps([{"class_type": "SaveImage", "pack": "core", "inputs": {}, "outputs": []}]),
        encoding="utf-8",
    )
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeWorkflow, WorkflowSource, VibeNode

def build():
    workflow = VibeWorkflow(id="x", source=WorkflowSource(id="x"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="Qwen3CustomVoice")
    workflow.nodes["2"] = VibeNode(id="2", class_type="VHS_LoadVideo")
    return workflow
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    installed: list[str | None] = []

    def fake_install_pack(**kwargs):
        installed.append(kwargs.get("name"))
        return node_packs_install.InstallResult(
            name=str(kwargs["name"]),
            status="refreshed",
            git_commit_sha="abc123",
            error=None,
        )

    monkeypatch.setattr(node_packs_install, "install_pack", fake_install_pack)

    code = _cmd_nodes_ensure(argparse.Namespace(template=None, workflow=str(scratchpad), dry_run=False))

    captured = capsys.readouterr()
    assert code == 0
    assert installed == ["ComfyUI-Qwen3-TTS", "ComfyUI-VideoHelperSuite"]
    assert "Nodepacks installed/refreshed." in captured.out


def test_contract_inspect_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_contract_inspect(argparse.Namespace(workflow="image/z_image", json=True))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["version"] == 1
    assert payload["workflow_id"] == "image/z_image"
    assert isinstance(payload["model_assets"], list)
    assert len(payload["model_assets"]) > 0
    assert isinstance(payload["inputs"], list)
    assert "model" in payload["inputs"]
    assert isinstance(payload["outputs"], list)
    assert isinstance(payload["runtime_nodes"], list)
    assert isinstance(payload["runtime_class_types"], list)
    assert payload["readiness_level"] == "ready"


def test_contract_doctor_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_contract_doctor(argparse.Namespace(workflow="image/z_image", json=True))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "status" in payload
    assert payload["status"] == "ok"
    assert isinstance(payload["contract"], dict)
    assert payload["contract"]["version"] == 1
    assert isinstance(payload["diagnostics"], list)
    # No error diagnostics for a clean image/z_image
    error_diags = [d for d in payload["diagnostics"] if d["severity"] == "error"]
    assert error_diags == []


# ── T7: workflows lens / contract-validate CLI tests ──────────────────────────


def test_workflows_lens_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    """JSON lens output includes node/edge counts, inputs, outputs, and per-node metadata."""
    code = _cmd_workflows_lens(
        argparse.Namespace(template_or_path="video/ltx2_3_lightricks_first_last_parity", json=True)
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["workflow_id"] == "video/ltx2_3_lightricks_first_last_parity"
    assert payload["node_count"] >= 20
    assert payload["edge_count"] >= 20
    assert "prompt" in payload["inputs"]
    assert "negative_prompt" in payload["inputs"]
    assert "first_image" in payload["inputs"]
    assert "last_image" in payload["inputs"]
    assert "seed_first" in payload["inputs"]
    assert "seed_last" in payload["inputs"]
    assert "width" in payload["inputs"]
    assert "height" in payload["inputs"]
    assert "first_strength" in payload["inputs"]
    assert "last_strength" in payload["inputs"]
    assert "frames" in payload["inputs"]
    assert "fps" in payload["inputs"]
    outputs = payload["outputs"]
    assert any(o["output_type"] == "SaveVideo" for o in outputs)
    nodes = payload["nodes"]
    assert len(nodes) == payload["node_count"]
    class_types = {n["class_type"] for n in nodes}
    assert "LTXVAddGuide" in class_types
    assert "RandomNoise" in class_types


def test_workflows_lens_human_readable(capsys: pytest.CaptureFixture[str]) -> None:
    """Human-readable lens diagnostics produce a readable graph summary."""
    code = _cmd_workflows_lens(
        argparse.Namespace(template_or_path="video/ltx2_3_lightricks_first_last_parity", json=False)
    )

    captured = capsys.readouterr().out
    assert code == 0
    assert "video/ltx2_3_lightricks_first_last_parity" in captured
    assert "LTXVAddGuide" in captured


def test_workflows_contract_validate_success_json(capsys: pytest.CaptureFixture[str]) -> None:
    """Successful LTX contract validation produces passing JSON output."""
    code = _cmd_workflows_contract_validate(
        argparse.Namespace(
            template_or_path="video/ltx2_3_lightricks_first_last_parity",
            type="ltx-first-last-two-stage",
            json=True,
            no_schema=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["passed"] is True
    assert payload["contract_name"] == "ltx-first-last-two-stage"
    assert isinstance(payload["issues"], list)
    # No errors or warnings for the clean parity template
    error_issues = [i for i in payload["issues"] if i["severity"] == "error"]
    assert error_issues == [], f"Unexpected error issues: {error_issues}"


def test_workflows_contract_validate_success_human(capsys: pytest.CaptureFixture[str]) -> None:
    """Successful LTX contract validation produces readable human output."""
    code = _cmd_workflows_contract_validate(
        argparse.Namespace(
            template_or_path="video/ltx2_3_lightricks_first_last_parity",
            type="ltx-first-last-two-stage",
            json=False,
            no_schema=False,
        )
    )

    captured = capsys.readouterr().out
    assert code == 0
    assert "ltx-first-last-two-stage" in captured
    assert "passed: True" in captured


def test_workflows_contract_validate_failure_diagnostic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A broken workflow produces a stable, readable failure diagnostic."""
    # Build a deliberately broken workflow: missing named inputs, wrong conditioning, etc.
    scratchpad = tmp_path / "broken_ltx.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def build():
    wf = VibeWorkflow("broken-ltx", WorkflowSource("broken-ltx"))
    # Only add a SaveVideo output with no conditioning pipeline
    wf.node("SaveVideo", filename_prefix="broken")
    wf.node("LoadImage", image="broken.png")
    wf.finalize_metadata()
    return wf
""",
        encoding="utf-8",
    )

    code = _cmd_workflows_contract_validate(
        argparse.Namespace(
            template_or_path=str(scratchpad),
            type="ltx-first-last-two-stage",
            json=True,
            no_schema=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["passed"] is False
    assert payload["contract_name"] == "ltx-first-last-two-stage"
    issues = payload["issues"]
    assert len(issues) > 0, "Expected failure diagnostic issues"

    # Verify readable, stable issue codes
    codes = {i["code"] for i in issues}
    assert "missing_named_inputs" in codes
    assert "missing_first_strength_guide" in codes
    assert "missing_last_strength_guide" in codes

    # Verify issues have human-readable messages
    for issue in issues:
        assert isinstance(issue["code"], str) and issue["code"]
        assert isinstance(issue["message"], str) and issue["message"]
        assert issue["severity"] in ("error", "warning")

    # Human-readable version should also show the failure
    code2 = _cmd_workflows_contract_validate(
        argparse.Namespace(
            template_or_path=str(scratchpad),
            type="ltx-first-last-two-stage",
            json=False,
            no_schema=False,
        )
    )
    captured2 = capsys.readouterr().out
    assert code2 == 1
    assert "passed: False" in captured2
    assert "missing_named_inputs" in captured2


def test_workflows_contract_validate_rejects_unknown_type(capsys: pytest.CaptureFixture[str]) -> None:
    """Unknown contract type returns exit code 1 with a clear error."""
    code = _cmd_workflows_contract_validate(
        argparse.Namespace(
            template_or_path="video/ltx2_3_lightricks_first_last_parity",
            type="unknown-contract-type",
            json=False,
            no_schema=False,
        )
    )

    captured = capsys.readouterr().out
    assert code == 1
    assert "unknown contract type" in captured
    assert "ltx-first-last-two-stage" in captured
