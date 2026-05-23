"""Tests for the ``megaplan run`` CLI subcommand + YAML pipeline CLI paths."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest


_MEGAPLAN = Path(__file__).resolve().parent.parent / ".venv-decomp" / "bin" / "megaplan"


# ── Existing subprocess tests (require decomp venv) ───────────────────

@pytest.mark.skipif(not _MEGAPLAN.exists(), reason="decomp venv not available")
def test_run_list_shows_builtin_pipelines() -> None:
    proc = subprocess.run(
        [str(_MEGAPLAN), "run", "--list"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "doc-critique" in proc.stdout
    assert "judges" in proc.stdout
    assert "planning" in proc.stdout


@pytest.mark.skipif(not _MEGAPLAN.exists(), reason="decomp venv not available")
def test_run_describe_returns_description() -> None:
    proc = subprocess.run(
        [str(_MEGAPLAN), "run", "doc-critique", "--describe"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "critique" in proc.stdout.lower()


@pytest.mark.skipif(not _MEGAPLAN.exists(), reason="decomp venv not available")
def test_run_doc_critique_end_to_end(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.md"
    fixture.write_text(
        "This is the doc the critique loop reads.\n"
        "Three critique passes apply deterministic rubric edits.\n"
    )
    plan_dir = tmp_path / "out"

    proc = subprocess.run(
        [
            str(_MEGAPLAN), "run", "doc-critique",
            "--inputs", f"doc={fixture}",
            "--plan-dir", str(plan_dir),
            "--state", '{"critique_iter": 0}',
        ],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["pipeline"] == "doc-critique"
    assert payload["final_stage"] == "critique"
    assert payload["state"]["critique_iter"] == 3

    # Exact artifact set landed.
    assert (plan_dir / "critique_versions" / "critique_v1.json").exists()
    assert (plan_dir / "critique_versions" / "critique_v2.json").exists()
    assert (plan_dir / "critique_versions" / "critique_v3.json").exists()
    assert (plan_dir / "doc_versions" / "doc_v1.md").exists()
    assert (plan_dir / "doc_versions" / "doc_v2.md").exists()


@pytest.mark.skipif(not _MEGAPLAN.exists(), reason="decomp venv not available")
def test_run_unknown_pipeline_returns_error() -> None:
    proc = subprocess.run(
        [str(_MEGAPLAN), "run", "does-not-exist",
         "--plan-dir", "/tmp/discard"],
        capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "no pipeline named" in (proc.stdout + proc.stderr).lower()


@pytest.mark.skipif(not _MEGAPLAN.exists(), reason="decomp venv not available")
def test_run_list_includes_epic_blitz() -> None:
    """``megaplan run --list`` includes epic-blitz."""
    proc = subprocess.run(
        [str(_MEGAPLAN), "run", "--list"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "epic-blitz" in proc.stdout


@pytest.mark.skipif(not _MEGAPLAN.exists(), reason="decomp venv not available")
def test_run_describe_epic_blitz_prints_metadata() -> None:
    """``megaplan run epic-blitz --describe`` prints metadata + SKILL.md."""
    proc = subprocess.run(
        [str(_MEGAPLAN), "run", "epic-blitz", "--describe"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Three-round" in proc.stdout
    assert "epic-blitz" in proc.stdout


# ── Registry-backed CLI tests (Python-level, no subprocess) ───────────


def test_registered_pipelines_includes_writing_panel_strict() -> None:
    """The registry surfaces writing-panel-strict alongside the built-ins."""
    from megaplan._pipeline.registry import registered_pipelines
    names = registered_pipelines()
    assert "writing-panel-strict" in names
    assert "planning" in names


def test_registered_pipelines_includes_epic_blitz() -> None:
    """The registry surfaces epic-blitz alongside the built-ins."""
    from megaplan._pipeline.registry import registered_pipelines
    names = registered_pipelines()
    assert "epic-blitz" in names


def test_describe_pipeline_writing_panel_strict(capsys) -> None:
    """_describe_pipeline for writing-panel-strict prints metadata."""
    from megaplan._pipeline.run_cli import _describe_pipeline
    rc = _describe_pipeline("writing-panel-strict")
    assert rc == 0
    captured = capsys.readouterr()
    assert "writing-panel-strict" in captured.out
    assert "adversarial" in captured.out.lower() or "Adversarial" in captured.out


def test_describe_pipeline_unknown(capsys) -> None:
    """_describe_pipeline for unknown name prints error and returns 2."""
    from megaplan._pipeline.run_cli import _describe_pipeline
    rc = _describe_pipeline("nonexistent-pipeline-xyz")
    assert rc == 2
    captured = capsys.readouterr()
    assert "unknown" in captured.err.lower() or "Unknown" in captured.err


def test_describe_pipeline_epic_blitz(capsys) -> None:
    """_describe_pipeline for epic-blitz prints metadata + SKILL.md."""
    from megaplan._pipeline.run_cli import _describe_pipeline
    rc = _describe_pipeline("epic-blitz")
    assert rc == 0
    captured = capsys.readouterr()
    assert "epic-blitz" in captured.out
    assert "Three-round" in captured.out


def test_handle_list_pipelines() -> None:
    """handle_list with list_target='pipelines' returns pipeline listing."""
    from megaplan.cli import handle_list
    args = argparse.Namespace(
        list_target="pipelines",
        verbose=False,
        filter_status=None,
        no_tree=False,
        include_done=False,
        summary=False,
        all=False,
    )
    result = handle_list(Path.cwd(), args)
    assert result["success"] is True
    assert result["step"] == "list"
    assert len(result["pipelines"]) >= 2  # at minimum writing-panel-strict + planning
    names = [p["name"] for p in result["pipelines"]]
    assert "writing-panel-strict" in names
    assert "planning" in names
    assert "epic-blitz" in names


def test_handle_list_pipelines_verbose() -> None:
    """handle_list with list_target='pipelines' and verbose includes extra fields."""
    from megaplan.cli import handle_list
    args = argparse.Namespace(
        list_target="pipelines",
        verbose=True,
        filter_status=None,
        no_tree=False,
        include_done=False,
        summary=False,
        all=False,
    )
    result = handle_list(Path.cwd(), args)
    assert result["success"] is True
    # writing-panel-strict's registered metadata carries default_profile + modes;
    # locate it and assert the verbose-mode metadata surface.
    wps = next(
        (p for p in result["pipelines"] if p["name"] == "writing-panel-strict"),
        None,
    )
    assert wps is not None
    assert "default_profile" in wps
    assert "modes" in wps
    # The kind='yaml'|'python' distinction was dropped in 0.22.0.
    assert all("kind" not in entry for entry in result["pipelines"])


def test_handle_describe_writing_panel_strict(capsys) -> None:
    """handle_describe for writing-panel-strict prints metadata + SKILL.md."""
    from megaplan.cli import handle_describe
    args = argparse.Namespace(pipeline_name="writing-panel-strict")
    result = handle_describe(args)
    captured = capsys.readouterr()
    assert result["success"] is True
    assert result["step"] == "describe"
    assert result["pipeline"] == "writing-panel-strict"
    assert "writing-panel-strict" in captured.out
    assert "Adversarial review" in captured.out or "adversarial" in captured.out.lower()


def test_handle_describe_unknown_pipeline() -> None:
    """handle_describe for unknown pipeline returns error."""
    from megaplan.cli import handle_describe
    args = argparse.Namespace(pipeline_name="nonexistent-pipeline-xyz")
    result = handle_describe(args)
    assert result["success"] is False
    assert result["step"] == "describe"


def test_handle_describe_epic_blitz(capsys) -> None:
    """handle_describe for epic-blitz prints metadata + SKILL.md."""
    from megaplan.cli import handle_describe
    args = argparse.Namespace(pipeline_name="epic-blitz")
    result = handle_describe(args)
    captured = capsys.readouterr()
    assert result["success"] is True
    assert result["step"] == "describe"
    assert result["pipeline"] == "epic-blitz"
    assert "epic-blitz" in captured.out
    assert "Three-round" in captured.out


def test_cli_run_list_dispatches(monkeypatch) -> None:
    """cli_run with --list prints the registered pipeline names."""
    from megaplan._pipeline.run_cli import cli_run

    args = argparse.Namespace(
        list_pipelines=True,
        pipeline_name=None,
        describe=False,
    )
    # Should exit 0 after listing
    result = cli_run(args)
    assert result == 0


def test_cli_run_describe_dispatches(monkeypatch) -> None:
    """cli_run with --describe for a YAML pipeline prints description."""
    from megaplan._pipeline.run_cli import cli_run

    args = argparse.Namespace(
        list_pipelines=False,
        pipeline_name="writing-panel-strict",
        describe=True,
    )
    result = cli_run(args)
    assert result == 0


def test_cli_run_unknown_pipeline_returns_2() -> None:
    """cli_run with unknown pipeline name returns 2."""
    from megaplan._pipeline.run_cli import cli_run

    args = argparse.Namespace(
        list_pipelines=False,
        pipeline_name="does-not-exist-xyz",
        describe=False,
    )
    result = cli_run(args)
    assert result == 2


def test_cli_run_list_includes_epic_blitz(capsys) -> None:
    """cli_run --list output includes epic-blitz."""
    from megaplan._pipeline.run_cli import cli_run

    args = argparse.Namespace(
        list_pipelines=True,
        pipeline_name=None,
        describe=False,
    )
    result = cli_run(args)
    assert result == 0
    captured = capsys.readouterr()
    assert "epic-blitz" in captured.out


def test_cli_run_describe_epic_blitz(capsys) -> None:
    """cli_run --describe for epic-blitz prints metadata + SKILL.md."""
    from megaplan._pipeline.run_cli import cli_run

    args = argparse.Namespace(
        list_pipelines=False,
        pipeline_name="epic-blitz",
        describe=True,
    )
    result = cli_run(args)
    assert result == 0
    captured = capsys.readouterr()
    assert "epic-blitz" in captured.out
    assert "Three-round" in captured.out


# ── Credential preflight CLI path tests ────────────────────────────────


def test_preflight_or_raise_exits_7_non_tty_cli(monkeypatch, capsys) -> None:
    """Non-TTY credential failure exits 7 with structured stderr message."""
    from megaplan._pipeline.preflight import preflight_or_raise

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

    profile = {"synth": "claude", "revise": "codex"}

    with pytest.raises(SystemExit) as exc_info:
        preflight_or_raise(profile, pipeline_name="test-pipe", profile_name="test-prof")

    assert exc_info.value.code == 7
    captured = capsys.readouterr()
    assert "test-pipe" in captured.err
    assert "ANTHROPIC_API_KEY" in captured.err
    assert "OPENAI_API_KEY" in captured.err


def test_render_credential_failure_non_tty_structure() -> None:
    """Non-TTY credential message has env var hints, no interactive options."""
    from megaplan._pipeline.preflight import render_credential_failure

    missing = [
        {"slot": "critique", "spec": "codex", "agent": "codex",
         "env_var": "OPENAI_API_KEY"},
    ]
    msg = render_credential_failure(
        missing, pipeline_name="pipe", profile_name="prof", is_tty=False,
    )

    assert "pipe" in msg
    assert "prof" in msg
    assert "OPENAI_API_KEY" in msg
    # Non-TTY: no interactive options
    assert "[1]" not in msg
    assert "[2]" not in msg
    assert "Set the required environment variables" in msg


# ── Existing helper tests ─────────────────────────────────────────────


def test_parse_inputs_helper() -> None:
    from megaplan._pipeline.run_cli import _parse_inputs
    parsed = _parse_inputs("doc=/tmp/x.md,extra=/tmp/y.json")
    assert parsed == {"doc": Path("/tmp/x.md"), "extra": Path("/tmp/y.json")}
    assert _parse_inputs("") == {}
    assert _parse_inputs(None) == {}
    with pytest.raises(ValueError, match="must be key=value"):
        _parse_inputs("no-equals")
