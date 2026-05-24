from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from vibecomfy.cli import build_parser
from vibecomfy.commands import COMMANDS, CommandSpec, load_command
from vibecomfy.commands.doctor import _doctor_warnings
from vibecomfy.commands.fetch import _cmd_fetch
from vibecomfy.commands.nodes import _cmd_nodes_ensure, _cmd_nodes_install, _cmd_nodes_install_plan, _cmd_nodes_list, _cmd_nodes_restore
import vibecomfy.node_packs_install as node_packs_install
import vibecomfy.commands.validate as validate_cmd
from vibecomfy.commands._workflow_path import resolve_workflow_path
from vibecomfy.commands.workflows import _cmd_workflows_list
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def _run_cli(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


def _top_level_commands(parser: argparse.ArgumentParser) -> list[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return list(action.choices)
    raise AssertionError("parser has no subparsers")


def _subcommands(parser: argparse.ArgumentParser, command: str) -> list[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            child = action.choices[command]
            for child_action in child._actions:
                if isinstance(child_action, argparse._SubParsersAction):
                    return list(child_action.choices)
    raise AssertionError(f"{command} parser has no subparsers")


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


def _write_raw_model_workflow(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "VAELoader",
                        "properties": {
                            "models": [
                                {
                                    "name": "raw-vae.safetensors",
                                    "url": "https://example.test/raw-vae.safetensors?download=true",
                                }
                            ]
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_object_info_cache(tmp_path: Path, *, required_text: bool = True) -> Path:
    cache = tmp_path / "object_info.fixture.json"
    text_group = "required" if required_text else "optional"
    cache.write_text(
        json.dumps(
            {
                "FixtureNode": {
                    "pack": "fixture-pack",
                    "input": {
                        text_group: {"text": ["STRING", {"default": ""}]},
                        "optional": {
                            "steps": ["INT", {"default": 1, "min": 1, "max": 8}],
                            "mode": [["fast", "slow"], {"default": "fast"}],
                        },
                    },
                    "output": ["IMAGE"],
                    "output_name": ["image"],
                }
            }
        ),
        encoding="utf-8",
    )
    return cache


def _write_validation_scratchpad(tmp_path: Path, *, value: object = True, name: str = "validation_scratch.py") -> Path:
    scratchpad = tmp_path / name
    scratchpad.write_text(
        f"""
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def build():
    workflow = VibeWorkflow(id="validation-scratch", source=WorkflowSource(id="validation-scratch"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="FixtureNode", inputs={{"steps": {value!r}}})
    return workflow
""",
        encoding="utf-8",
    )
    return scratchpad


def _write_build_error_scratchpad(tmp_path: Path) -> Path:
    scratchpad = tmp_path / "build_error_scratch.py"
    scratchpad.write_text(
        """
def build():
    raise RuntimeError("build exploded")
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
        "convert",
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
        "port",
    ]


def test_build_parser_registers_all_known_commands() -> None:
    parser = build_parser()

    assert _top_level_commands(parser) == [spec.name for spec in COMMANDS]


def test_runtime_cli_exposes_current_subcommands_without_eval_node(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    assert _subcommands(parser, "runtime") == ["doctor", "smoke"]

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["runtime", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "{doctor,smoke}" in help_text
    assert "doctor" in help_text
    assert "smoke" in help_text
    assert "eval-node" not in help_text


def test_runtime_cli_rejects_eval_node_when_eval_modules_absent() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["runtime", "eval-node"])

    assert exc_info.value.code == 2


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

    assert validate_cmd._cmd_validate(argparse.Namespace(path=str(scratchpad), json=False, no_schema=True)) == 0
    assert capsys.readouterr().out == "ok\n"


def test_validate_rejects_removed_backend_argument(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["validate", "workflow.py", "--backend", "api"])

    assert exc_info.value.code == 2
    assert "--backend" in capsys.readouterr().err


def test_validate_json_success_failure_and_build_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text(
        json.dumps([{"class_type": "FixtureNode", "inputs": {"steps": "INT"}}]),
        encoding="utf-8",
    )
    valid_scratchpad = _write_validation_scratchpad(tmp_path, value=4, name="valid_validation_scratch.py")
    invalid_scratchpad = _write_validation_scratchpad(tmp_path, value=True, name="invalid_validation_scratch.py")
    build_error_scratchpad = _write_build_error_scratchpad(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert _run_cli(["validate", str(valid_scratchpad), "--json"]) == 0
    success_payload = json.loads(capsys.readouterr().out)
    assert success_payload == {
        "issues": [],
        "ok": True,
        "status": "ok",
        "workflow_id": "validation-scratch",
    }

    assert _run_cli(["validate", str(invalid_scratchpad), "--json"]) == 1
    failure_captured = capsys.readouterr()
    failure_payload = json.loads(failure_captured.out)
    assert failure_captured.err == ""
    assert failure_payload["ok"] is False
    assert failure_payload["status"] == "error"
    assert failure_payload["workflow_id"] == "validation-scratch"
    assert [issue["code"] for issue in failure_payload["issues"]] == ["value_type_mismatch"]

    assert _run_cli(["validate", str(build_error_scratchpad), "--json"]) == 1
    exception_captured = capsys.readouterr()
    exception_payload = json.loads(exception_captured.out)
    assert exception_captured.err == ""
    assert exception_payload["ok"] is False
    assert exception_payload["status"] == "error"
    assert exception_payload["path"] == str(build_error_scratchpad)
    assert exception_payload["errors"] == [
        {"code": "workflow_load_error", "message": "build exploded", "type": "RuntimeError"}
    ]


def test_nodes_spec_explicit_json_flag_matches_json_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text(
        json.dumps(
            [
                {
                    "class_type": "FixtureNode",
                    "pack": "fixture-pack",
                    "inputs": {"steps": "INT"},
                    "outputs": ["IMAGE"],
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert _run_cli(["nodes", "spec", "FixtureNode"]) == 0
    default_payload = json.loads(capsys.readouterr().out)
    assert _run_cli(["nodes", "spec", "FixtureNode", "--json"]) == 0
    explicit_payload = json.loads(capsys.readouterr().out)

    assert explicit_payload == default_payload
    assert explicit_payload["class_type"] == "FixtureNode"
    assert explicit_payload["pack"] == "fixture-pack"
    assert explicit_payload["inputs"]["steps"]["type"] == "INT"
    assert explicit_payload["outputs"] == [{"name": None, "type": "IMAGE"}]


def test_port_validate_call_requires_class_type(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    assert "port" in _top_level_commands(parser)

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["port", "validate-call", "--kwargs", "{}"])

    assert exc_info.value.code == 2
    assert "class_type" in capsys.readouterr().err


def test_port_validate_call_reports_malformed_kwargs_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache = _write_object_info_cache(tmp_path)

    assert _run_cli(
        ["port", "validate-call", "FixtureNode", "--kwargs", "{bad-json", "--object-info-cache", str(cache), "--json"]
    ) == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "status": "error",
        "errors": [{"code": "invalid_kwargs_json", "message": "--kwargs must be valid JSON."}],
    }


@pytest.mark.parametrize("kwargs_json", ["[]", "1", "null", '"text"'])
def test_port_validate_call_rejects_non_object_kwargs_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    kwargs_json: str,
) -> None:
    cache = _write_object_info_cache(tmp_path)

    assert _run_cli(
        ["port", "validate-call", "FixtureNode", "--kwargs", kwargs_json, "--object-info-cache", str(cache), "--json"]
    ) == 2

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "status": "error",
        "errors": [{"code": "kwargs_not_object", "message": "--kwargs JSON must decode to an object."}],
    }


def test_port_validate_call_json_payload_for_valid_node_call(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache = _write_object_info_cache(tmp_path)

    assert _run_cli(
        [
            "port",
            "validate-call",
            "FixtureNode",
            "--kwargs",
            json.dumps({"text": "hello", "steps": "4", "mode": "fast"}),
            "--object-info-cache",
            str(cache),
            "--json",
        ]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["class_type"] == "FixtureNode"
    assert payload["ok"] is True
    assert payload["issues"] == []
    assert payload["status"] == "ok"
    assert payload["provider"] == {"kind": "object_info_file", "path": str(cache)}


def test_port_validate_call_json_payload_for_invalid_node_call(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache = _write_object_info_cache(tmp_path)

    assert _run_cli(
        [
            "port",
            "validate-call",
            "FixtureNode",
            "--kwargs",
            json.dumps({"steps": 99, "mode": "wrong", "extra": True}),
            "--object-info-cache",
            str(cache),
            "--json",
        ]
    ) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["class_type"] == "FixtureNode"
    assert payload["ok"] is False
    assert payload["status"] == "error"
    assert payload["provider"] == {"kind": "object_info_file", "path": str(cache)}
    assert [issue["code"] for issue in payload["issues"]] == [
        "missing_required_input",
        "unknown_input",
        "value_not_in_enum",
        "value_out_of_range",
    ]


def test_port_validate_call_object_info_cache_controls_schema_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache = _write_object_info_cache(tmp_path, required_text=False)
    (tmp_path / "node_index.json").write_text(
        json.dumps([{"class_type": "FixtureNode", "inputs": {"required": {"text": "STRING"}}}]),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert _run_cli(
        [
            "port",
            "validate-call",
            "FixtureNode",
            "--kwargs",
            json.dumps({"steps": 2, "mode": "slow"}),
            "--object-info-cache",
            str(cache),
            "--json",
        ]
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["issues"] == []
    assert payload["provider"] == {"kind": "object_info_file", "path": str(cache)}


def test_port_check_text_mode_uses_canonical_workflow_validation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache = _write_object_info_cache(tmp_path)
    scratchpad = _write_validation_scratchpad(tmp_path, value=4)

    assert _run_cli(["port", "check", str(scratchpad), "--object-info-cache", str(cache)]) == 1

    captured = capsys.readouterr()
    assert "[missing_required_input]" in captured.out
    assert "FixtureNode" in captured.out
    assert captured.err == ""


def test_port_check_json_mode_uses_canonical_workflow_validation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache = _write_object_info_cache(tmp_path)
    scratchpad = _write_validation_scratchpad(tmp_path, value=True)

    assert _run_cli(["port", "check", str(scratchpad), "--object-info-cache", str(cache), "--json"]) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["workflow_id"] == "validation-scratch"
    assert payload["ok"] is False
    assert payload["status"] == "error"
    assert payload["provider"] == {"kind": "object_info_file", "path": str(cache)}
    assert [issue["code"] for issue in payload["issues"]] == ["missing_required_input", "value_type_mismatch"]


def test_validate_doctor_and_inspect_share_canonical_status_behavior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text(
        json.dumps([{"class_type": "FixtureNode", "inputs": {"steps": "INT"}}]),
        encoding="utf-8",
    )
    scratchpad = _write_validation_scratchpad(tmp_path, value=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("vibecomfy.commands.doctor._read_doctor_lockfile", lambda: [])

    assert _run_cli(["validate", str(scratchpad)]) == 1
    assert "[value_type_mismatch]" in capsys.readouterr().err

    assert _run_cli(["doctor", str(scratchpad), "--json"]) == 1
    doctor_payload = json.loads(capsys.readouterr().out)
    assert doctor_payload["status"] == "error"
    assert doctor_payload["layer"] == "VibeWorkflow validation"
    assert any("[value_type_mismatch]" in error for error in doctor_payload["errors"])

    assert _run_cli(["inspect", str(scratchpad), "--json"]) == 0
    inspect_payload = json.loads(capsys.readouterr().out)
    assert inspect_payload["status"] == "unsupported"
    assert "issues" not in inspect_payload
    assert "errors" not in inspect_payload

    assert _run_cli(["inspect", str(scratchpad)]) == 0
    captured = capsys.readouterr()
    assert "status: unsupported" in captured.out
    assert "value_type_mismatch" not in captured.out
    assert "value_type_mismatch" not in captured.err


def test_validate_doctor_and_inspect_preserve_valid_output_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text(
        json.dumps([{"class_type": "FixtureNode", "inputs": {"steps": "INT"}}]),
        encoding="utf-8",
    )
    scratchpad = _write_validation_scratchpad(tmp_path, value=4)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VIBECOMFY_COMFY_CONFIGURATION", raising=False)
    monkeypatch.setattr("vibecomfy.commands.doctor._read_doctor_lockfile", lambda: [])

    assert _run_cli(["validate", str(scratchpad)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "ok\n"
    assert captured.err == ""

    assert _run_cli(["doctor", str(scratchpad), "--json"]) == 0
    doctor_payload = json.loads(capsys.readouterr().out)
    assert doctor_payload["status"] == "ok"
    assert "errors" not in doctor_payload

    assert _run_cli(["inspect", str(scratchpad), "--json"]) == 0
    inspect_payload = json.loads(capsys.readouterr().out)
    assert inspect_payload["status"] == "runnable"
    assert "issues" not in inspect_payload


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


def test_fetch_cli_dry_run_extracts_model_assets_from_raw_json_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workflow = _write_raw_model_workflow(tmp_path / "raw_workflow.json")
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path / "models"))

    assert _cmd_fetch(argparse.Namespace(workflow=str(workflow), force=False, dry_run=True)) == 0

    captured = capsys.readouterr()
    assert "would fetch raw-vae.safetensors" in captured.out
    assert str(tmp_path / "models" / "vae" / "raw-vae.safetensors") in captured.out


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


def test_nodes_install_plan_json_uses_shared_payload_shape(
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

    assert _run_cli(["nodes", "install-plan", str(scratchpad), "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "path": str(scratchpad),
        "packs": [
            {
                "name": "ComfyUI-Qwen3-TTS",
                "repo": "https://github.com/DarioFT/ComfyUI-Qwen3-TTS.git",
                "pip_packages": ["qwen-tts", "modelscope", "soundfile", "librosa", "accelerate"],
                "classes": ["Qwen3CustomVoice"],
            }
        ],
        "unresolved_class_types": [],
    }


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
