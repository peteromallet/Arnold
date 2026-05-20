from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from vibecomfy.cli import build_parser
from vibecomfy.commands import COMMANDS, CommandSpec, load_command
from vibecomfy.commands._workflow_path import resolve_workflow_path
from vibecomfy.commands.copy_to_recipe import _cmd_copy_to_recipe
from vibecomfy.commands.inspect import _cmd_inspect

from tests._cli_helpers import _top_level_commands


def test_cli_command_registry_is_explicit_and_ordered() -> None:
    assert [spec.name for spec in COMMANDS] == [
        "sources",
        "workflows",
        "nodes",
        "analyze",
        "search",
        "inspect",
        "port",
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
        "schemas",
        "agentic",
        "copy-to-recipe",
    ]


def test_build_parser_registers_all_known_commands() -> None:
    parser = build_parser()

    assert _top_level_commands(parser) == [spec.name for spec in COMMANDS]


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


# ── copy-to-recipe ──────────────────────────────────────────────────────


def test_copy_to_recipe_resolves_and_writes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out_file = tmp_path / "test_copy.py"
    code = _cmd_copy_to_recipe(
        argparse.Namespace(
            id="video/wan_i2v",
            out=str(out_file),
            strip_markers=False,
            with_runner=False,
        )
    )
    captured = capsys.readouterr()
    assert code == 0
    assert out_file.is_file()
    assert "Copied" in captured.out
    text = out_file.read_text(encoding="utf-8")
    assert "def build()" in text
    assert "vibecomfy" in text.lower()


def test_copy_to_recipe_strip_markers(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out_file = tmp_path / "test_copy_stripped.py"
    code = _cmd_copy_to_recipe(
        argparse.Namespace(
            id="video/wan_i2v",
            out=str(out_file),
            strip_markers=True,
            with_runner=False,
        )
    )
    captured = capsys.readouterr()
    assert code == 0
    text = out_file.read_text(encoding="utf-8")
    # Markers should be stripped
    assert "vibecomfy: generated" not in text.lower()
    assert "vibecomfy: manual" not in text.lower()
    assert "def build()" in text


def test_copy_to_recipe_with_runner(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out_file = tmp_path / "test_copy_runner.py"
    code = _cmd_copy_to_recipe(
        argparse.Namespace(
            id="video/wan_i2v",
            out=str(out_file),
            strip_markers=False,
            with_runner=True,
        )
    )
    captured = capsys.readouterr()
    assert code == 0
    text = out_file.read_text(encoding="utf-8")
    assert "if __name__ == '__main__':" in text
    assert "build()" in text
    assert "runner" in captured.out.lower()


def test_copy_to_recipe_unknown_id_returns_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_copy_to_recipe(
        argparse.Namespace(
            id="nonexistent/template_id_xyz",
            out="/tmp/nonexistent_out.py",
            strip_markers=False,
            with_runner=False,
        )
    )
    captured = capsys.readouterr()
    assert code == 1
    assert captured.err or captured.out


# ── inspect --field ─────────────────────────────────────────────────────


def test_inspect_field_json_returns_tracefield(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_inspect(
        argparse.Namespace(workflow="video/wan_i2v", json=True, field="prompt")
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "field" in payload
    assert payload["field"] == "prompt"
    assert "resolution_chain" in payload
    assert "aliases" in payload
    assert "bound_node" in payload


def test_inspect_field_unknown_field_returns_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_inspect(
        argparse.Namespace(workflow="video/wan_i2v", json=True, field="nonexistent_field_xyz")
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert "error" in payload


def test_inspect_field_text_renders_chain(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_inspect(
        argparse.Namespace(workflow="video/wan_i2v", json=False, field="prompt")
    )
    text = capsys.readouterr().out
    assert code == 0
    assert "field:" in text
    assert "resolution chain" in text
    assert "bound to:" in text
