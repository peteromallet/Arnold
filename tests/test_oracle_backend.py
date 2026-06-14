"""M4 T11 — typed oracle.run backend smoke + attestation-path preservation.

Asserts:

1. ``oracle.run`` returns an :class:`OracleResult` with typed
   ``exit``/``stdout``/``stderr`` for a synthetic ``true``/``false`` command pair.
2. ``validate_execution_evidence`` is still importable from
   ``megaplan.orchestration.execution_evidence`` and is purely an
   attestation/notary helper (no flow-branching) — verified by a
   structural check on its signature.
"""

from __future__ import annotations

import inspect

import pytest

from arnold.runtime import oracle
from arnold.runtime.oracle import OracleResult


def test_oracle_run_true_returns_exit_zero():
    res = oracle.run(["true"])
    assert isinstance(res, OracleResult)
    assert res.exit == 0
    assert isinstance(res.stdout, str)
    assert isinstance(res.stderr, str)


def test_oracle_run_false_returns_nonzero_exit():
    res = oracle.run(["false"])
    assert isinstance(res, OracleResult)
    assert res.exit != 0


def test_oracle_run_captures_stdout_and_stderr():
    res = oracle.run(["sh", "-c", "echo hello-stdout; echo hello-stderr 1>&2"])
    assert res.exit == 0
    assert "hello-stdout" in res.stdout
    assert "hello-stderr" in res.stderr


def test_oracle_run_accepts_string_command_via_shell():
    res = oracle.run("echo shell-mode")
    assert res.exit == 0
    assert "shell-mode" in res.stdout


def test_validate_execution_evidence_preserved_as_attestation_path():
    """Must remain a callable in execution_evidence — and not be re-routed
    through the oracle.run flow-execution seam."""
    from arnold.pipelines.megaplan.orchestration import execution_evidence

    assert hasattr(execution_evidence, "validate_execution_evidence")
    assert callable(execution_evidence.validate_execution_evidence)
    # Attestation: takes a finalize document + project dir, returns a dict.
    sig = inspect.signature(execution_evidence.validate_execution_evidence)
    params = list(sig.parameters)
    assert params[:2] == ["finalize_data", "project_dir"], params
    # Sanity: oracle.run is a SEPARATE symbol; the attestation path was not
    # silently aliased to the execution seam.
    assert execution_evidence.validate_execution_evidence is not oracle.run
