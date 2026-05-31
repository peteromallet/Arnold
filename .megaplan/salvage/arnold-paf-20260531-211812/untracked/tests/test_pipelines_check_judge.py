"""T9 — pipelines check reports NODE_REGISTRY without importing judge_piece."""
from __future__ import annotations

import subprocess
import sys
import types

import pytest


def _run_check(*extra_args: str) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        [sys.executable, "-m", "megaplan", "pipelines", "check", *extra_args],
        capture_output=True,
        text=True,
    )


def test_pipelines_check_resolves_judge_default_nodespec():
    """pipelines check (no name) prints judge.default's NodeSpec from NODE_REGISTRY."""
    result = _run_check()

    assert result.returncode == 0, f"exit non-zero: {result.stderr}"
    output = result.stdout
    assert "judge.default" in output
    assert "arnold_api_version=1" in output
    assert "judge_version=" in output
    # Port names from the NodeSpec
    assert "judged-artifact" in output
    assert "evaluand-record" in output


def test_judge_piece_not_in_sys_modules_before_and_after_check():
    """judge_piece must NOT be imported as a side-effect of pipelines check."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "before = 'megaplan._pipeline.judge_piece' not in sys.modules; "
                "from megaplan.cli import _handle_pipelines; "
                "import argparse; "
                "ns = argparse.Namespace(pipelines_action='check', pipeline_name=None); "
                "import pathlib, io; "
                "_handle_pipelines(pathlib.Path('.'), ns); "
                "after = 'megaplan._pipeline.judge_piece' not in sys.modules; "
                "import sys as _sys; print(before, after, file=_sys.stderr)"
            ),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    # result printed on stderr to avoid mixing with NODE_REGISTRY stdout
    parts = result.stderr.strip().split()[-2:]
    assert parts == ["True", "True"], (
        f"judge_piece import leaked: before={parts[0]} after={parts[1]}\nfull stderr: {result.stderr}"
    )


def test_identity_in_sys_modules_after_check():
    """megaplan._pipeline.identity must be in sys.modules after pipelines check runs."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "from megaplan.cli import _handle_pipelines; "
                "import argparse, pathlib; "
                "ns = argparse.Namespace(pipelines_action='check', pipeline_name=None); "
                "_handle_pipelines(pathlib.Path('.'), ns); "
                "import sys as _sys; print('megaplan._pipeline.identity' in sys.modules, file=_sys.stderr)"
            ),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "True" in result.stderr


def test_pipelines_check_exits_zero():
    """pipelines check with no name must exit 0."""
    result = _run_check()
    assert result.returncode == 0, f"stderr: {result.stderr}"
