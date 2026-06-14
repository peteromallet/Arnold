"""M4 T11 — tests for arnold.runtime.oracle (OracleResult + run).

Verifies:
1. OracleResult fields (exit, stdout, stderr) are typed and preserved.
2. run() executes subprocess commands and returns OracleResult.
3. The shim in orchestration/oracle.py preserves `is`-identity with
   the canonical runtime module.
4. OracleResult is importable from arnold.runtime and is the same class.
"""

from __future__ import annotations

import inspect

import pytest

from arnold.runtime import oracle
from arnold.runtime.oracle import OracleResult, run


def test_oracle_result_fields_typed():
    """OracleResult has the three typed fields."""
    result = OracleResult(exit=0, stdout="out", stderr="err")
    assert result.exit == 0
    assert isinstance(result.exit, int)
    assert result.stdout == "out"
    assert isinstance(result.stdout, str)
    assert result.stderr == "err"
    assert isinstance(result.stderr, str)


def test_oracle_result_is_frozen():
    """OracleResult is immutable."""
    result = OracleResult(exit=0, stdout="", stderr="")
    with pytest.raises(Exception):
        result.exit = 1  # type: ignore[misc]


def test_run_true_returns_exit_zero():
    """run(['true']) returns exit 0."""
    res = run(["true"])
    assert isinstance(res, OracleResult)
    assert res.exit == 0
    assert isinstance(res.stdout, str)
    assert isinstance(res.stderr, str)


def test_run_false_returns_nonzero_exit():
    """run(['false']) returns nonzero exit."""
    res = run(["false"])
    assert isinstance(res, OracleResult)
    assert res.exit != 0


def test_run_captures_stdout_and_stderr():
    """run captures stdout and stderr separately."""
    res = run(["sh", "-c", "echo hello-stdout; echo hello-stderr 1>&2"])
    assert res.exit == 0
    assert "hello-stdout" in res.stdout
    assert "hello-stderr" in res.stderr


def test_run_accepts_string_command_via_shell():
    """run accepts a string command (shell=True)."""
    res = run("echo shell-mode")
    assert res.exit == 0
    assert "shell-mode" in res.stdout


def test_run_timeout_raises():
    """run with a tight timeout on sleep raises TimeoutExpired."""
    with pytest.raises(Exception):
        run(["sleep", "10"], timeout=0.1)


def test_oracle_result_still_importable_from_runtime_package():
    """OracleResult is importable from arnold.runtime."""
    from arnold.runtime import OracleResult as PkgResult
    assert PkgResult is OracleResult


def test_shim_preserves_is_identity():
    """The orchestration/oracle.py shim re-exports the identical class."""
    from arnold.pipelines.megaplan.orchestration.oracle import (
        OracleResult as ShimResult,
        run as shim_run,
    )
    assert ShimResult is OracleResult
    assert shim_run is run


def test_oracle_run_is_callable_with_expected_signature():
    """run has the expected parameter names."""
    sig = inspect.signature(run)
    params = list(sig.parameters)
    assert "cmd" in params


def test_run_exit_is_int():
    """run always returns an int exit code."""
    res = run(["echo", "hello"])
    assert isinstance(res.exit, int)
    assert res.exit == 0
