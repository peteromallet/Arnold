"""Tests for the ``megaplan run`` CLI subcommand."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


_MEGAPLAN = Path(__file__).resolve().parent.parent / ".venv-decomp" / "bin" / "megaplan"


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


def test_parse_inputs_helper() -> None:
    from megaplan._pipeline.run_cli import _parse_inputs
    parsed = _parse_inputs("doc=/tmp/x.md,extra=/tmp/y.json")
    assert parsed == {"doc": Path("/tmp/x.md"), "extra": Path("/tmp/y.json")}
    assert _parse_inputs("") == {}
    assert _parse_inputs(None) == {}
    with pytest.raises(ValueError, match="must be key=value"):
        _parse_inputs("no-equals")
