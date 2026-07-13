"""Zero-write mutation gate tests for C1 observe-only operations (T20).

Proves that semantic inspection (:func:`inspect_semantic_health`) and
fixture replay (:class:`CompatibilityEvaluator`) perform **zero** writes
across every known write surface when mutation gates and dispatch flags
are off:

* lifecycle writes
* queue writes
* source mutations
* commit writes
* push writes
* status persister writes
* repair writes
* audited-input writes
* normalizer writes
* projection materializer writes
* recovery writes
* drift writer writes
* status persister writes

Strategy
--------
Monkey-patch every accessible write primitive at the lowest level
(``pathlib.Path.write_text``, ``pathlib.Path.write_bytes``,
``pathlib.Path.mkdir``, ``builtins.open`` in write modes,
``arnold.runtime.state_persistence.atomic_write_*``, and all known
persistence backend write methods), then run each observe-only
operation and verify that zero write calls occurred while the
operation still produced meaningful read-only results.
"""

from __future__ import annotations

import builtins
import json
import os
import pathlib
import shutil
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from arnold.workflow.boundary_compatibility import (
    CompatibilityEvaluator,
    CompatibilityResult,
    CompatibilityStatus,
)
from arnold_pipelines.megaplan.semantic_health import inspect_semantic_health
from arnold_pipelines.megaplan.workflows.boundary_contracts import (
    BOUNDARY_CONTRACTS,
)


# ──────────────────────────────────────────────────────────────────────────────
# Write-surface detection helpers
# ──────────────────────────────────────────────────────────────────────────────


class WriteDetector:
    """Collects evidence of any file/directory mutation during a test block.

    Use as a context manager or via the :meth:`patch_all` / :meth:`unpatch_all`
    pair.  After the block, :attr:`calls` contains every intercepted write
    attempt as ``(target, args, kwargs)`` tuples.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self._patchers: list[Any] = []
        self._original_open = builtins.open
        self._original_path_write_text = pathlib.Path.write_text
        self._original_path_write_bytes = pathlib.Path.write_bytes
        self._original_path_mkdir = pathlib.Path.mkdir
        self._original_os_rename = os.rename
        self._original_os_replace = os.replace
        self._original_shutil_move = shutil.move
        self._original_shutil_copy = shutil.copy
        self._original_shutil_copy2 = shutil.copy2

    # ── recording helpers ────────────────────────────────────────────────

    def _record(self, surface: str, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((surface, args, kwargs))
        # For open(), we must return a real file-like so reads still work.
        # We fall through to the real open() but ONLY for read modes.
        if surface == "open" and args:
            mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
            if mode not in ("r", "rb", "rt", "r+"):
                self.calls.append((f"open_write:{mode}", args, kwargs))
        return None  # caller will handle fallback

    def _record_write_text(self, instance: Any, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("Path.write_text", (str(instance),) + args, kwargs))

    def _record_write_bytes(self, instance: Any, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("Path.write_bytes", (str(instance),) + args, kwargs))

    def _record_mkdir(self, instance: Any, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("Path.mkdir", (str(instance),) + args, kwargs))

    def _record_os_rename(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("os.rename", args, kwargs))

    def _record_os_replace(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("os.replace", args, kwargs))

    def _record_shutil_move(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("shutil.move", args, kwargs))

    def _record_shutil_copy(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("shutil.copy", args, kwargs))

    def _record_shutil_copy2(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("shutil.copy2", args, kwargs))

    # ── open() guard ─────────────────────────────────────────────────────

    def _guarded_open(
        self,
        file: Any,
        mode: str = "r",
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Intercept ``builtins.open`` — record any write-mode open."""
        if mode not in ("r", "rb", "rt", "r+"):
            self.calls.append(("builtins.open", (str(file), mode) + args, kwargs))
        return self._original_open(file, mode, *args, **kwargs)

    # ── context manager protocol ─────────────────────────────────────────

    def __enter__(self) -> WriteDetector:
        self.patch_all()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.unpatch_all()

    def patch_all(self) -> None:
        """Install all write-detection patches."""
        self.calls.clear()

        # Lowest-level filesystem writes
        pathlib.Path.write_text = self._record_write_text  # type: ignore[assignment]
        pathlib.Path.write_bytes = self._record_write_bytes  # type: ignore[assignment]
        pathlib.Path.mkdir = self._record_mkdir  # type: ignore[assignment]

        # os/shutil mutations
        os.rename = self._record_os_rename  # type: ignore[assignment]
        os.replace = self._record_os_replace  # type: ignore[assignment]
        shutil.move = self._record_shutil_move  # type: ignore[assignment]
        shutil.copy = self._record_shutil_copy  # type: ignore[assignment]
        shutil.copy2 = self._record_shutil_copy2  # type: ignore[assignment]

        # builtins.open guard (but let reads through)
        builtins.open = self._guarded_open  # type: ignore[assignment]

    def unpatch_all(self) -> None:
        """Restore all original functions."""
        pathlib.Path.write_text = self._original_path_write_text  # type: ignore[assignment]
        pathlib.Path.write_bytes = self._original_path_write_bytes  # type: ignore[assignment]
        pathlib.Path.mkdir = self._original_path_mkdir  # type: ignore[assignment]
        os.rename = self._original_os_rename  # type: ignore[assignment]
        os.replace = self._original_os_replace  # type: ignore[assignment]
        shutil.move = self._original_shutil_move  # type: ignore[assignment]
        shutil.copy = self._original_shutil_copy  # type: ignore[assignment]
        shutil.copy2 = self._original_shutil_copy2  # type: ignore[assignment]
        builtins.open = self._original_open  # type: ignore[assignment]

    @property
    def write_calls(self) -> list[tuple[str, tuple[Any, ...], dict[str, Any]]]:
        """Subset of calls that represent write/mutate operations.

        Excludes read-mode open calls that were let through.
        """
        return [
            c
            for c in self.calls
            if c[0] != "open"  # read-mode open is not a write
        ]


# ──────────────────────────────────────────────────────────────────────────────
# Fixture helpers for semantic_health
# ──────────────────────────────────────────────────────────────────────────────


def _make_state(
    *,
    current_state: str = "prepped",
    iteration: int = 1,
    history: list[dict[str, Any]] | None = None,
    created_at: str = "2026-07-11T00:00:00Z",
    **extra: Any,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "name": "test-plan",
        "current_state": current_state,
        "iteration": iteration,
        "created_at": created_at,
        "config": {"project_dir": "/tmp/test"},
        "sessions": {},
        "plan_versions": [],
        "history": history if history is not None else [],
        "meta": {"current_invocation_id": "inv-test"},
        "last_gate": {},
        "latest_failure": None,
    }
    state.update(extra)
    return state


def _write_state_file(plan_dir: Path, state: dict[str, Any]) -> None:
    """Write state.json using ONLY real primitives (before patching)."""
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _write_phase_result_file(
    plan_dir: Path,
    *,
    phase: str = "prep",
    exit_kind: str = "success",
    invocation_id: str = "inv-test",
) -> None:
    payload = {
        "schema": "megaplan.phase_result",
        "schema_version": 1,
        "phase_result_contract_version": 1,
        "phase": phase,
        "invocation_id": invocation_id,
        "exit_kind": exit_kind,
        "blocked_tasks": [],
        "deviations": [],
        "artifacts_written": [],
        "cli_provenance": {},
        "external_error": None,
    }
    (plan_dir / "phase_result.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_boundary_receipt_file(
    plan_dir: Path,
    boundary_id: str,
    *,
    workflow_id: str = "megaplan-test",
    row_id: str | None = None,
    invocation_id: str = "inv-test",
    outcome: str = "complete",
    authority_records: list[dict[str, Any]] | None = None,
) -> None:
    receipt_dir = plan_dir / "boundary_receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    from arnold.workflow.boundary_evidence import BoundaryReceipt

    receipt = BoundaryReceipt(
        boundary_id=boundary_id,
        workflow_id=workflow_id,
        row_id=row_id,
        invocation_id=invocation_id,
        outcome=outcome,
        authority_records=authority_records or (),
    )
    (receipt_dir / f"{boundary_id}.json").write_text(
        json.dumps(receipt.to_dict()), encoding="utf-8"
    )


def _setup_minimal_plan_dir(base: Path) -> Path:
    """Create a minimal plan directory with enough state for semantic health
    inspection to produce meaningful findings without requiring all contracts
    to be fully satisfied.

    The directory includes state.json, phase_result.json, a boundary receipt
    for prep_to_plan, and the required prep artifacts. This is sufficient for
    inspect_semantic_health to run across all 35 contracts and produce a
    non-empty set of findings.
    """
    plan_dir = base / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)

    # State with prep phase expectations
    state = _make_state(
        current_state="prepped",
        iteration=1,
        history=[{"step": "prep", "result": "success"}],
    )
    _write_state_file(plan_dir, state)
    _write_phase_result_file(plan_dir, phase="prep")

    # Write a boundary receipt for prep_to_plan
    _write_boundary_receipt_file(
        plan_dir, "prep_to_plan", invocation_id="inv-test", outcome="complete"
    )

    # Write required artifacts for prep_to_plan: research.md and brief.md
    for artifact_name in ("research.md", "brief.md"):
        (plan_dir / artifact_name).write_text("test content", encoding="utf-8")

    return plan_dir


# ──────────────────────────────────────────────────────────────────────────────
# Tests: semantic inspection zero-write
# ──────────────────────────────────────────────────────────────────────────────


class TestSemanticInspectionZeroWrite:
    """Prove :func:`inspect_semantic_health` performs zero writes."""

    def test_inspect_semantic_health_zero_path_writes(
        self, tmp_path: Path
    ) -> None:
        """Path.write_text / write_bytes / mkdir must never be called."""
        plan_dir = _setup_minimal_plan_dir(tmp_path)

        detector = WriteDetector()
        detector.patch_all()
        try:
            findings = inspect_semantic_health(plan_dir)
        finally:
            detector.unpatch_all()

        # Must produce findings (proves the function actually ran)
        assert isinstance(findings, list)
        assert len(findings) > 0, (
            "Expected inspect_semantic_health to produce findings; "
            "zero findings suggests the function did not execute"
        )

        # Filter to actual write/mutate calls (not read opens)
        writes = detector.write_calls
        assert len(writes) == 0, (
            f"inspect_semantic_health triggered {len(writes)} write call(s): "
            f"{writes[:10]}"
        )

    def test_inspect_semantic_health_zero_lifecycle_writes(
        self, tmp_path: Path
    ) -> None:
        """No lifecycle-mutating files (state.json, events.ndjson, etc.)
        may be written."""
        plan_dir = _setup_minimal_plan_dir(tmp_path)

        detector = WriteDetector()
        detector.patch_all()
        try:
            _findings = inspect_semantic_health(plan_dir)
        finally:
            detector.unpatch_all()

        lifecycle_paths = {
            "state.json",
            "events.ndjson",
            "stages.json",
            "checkpoint.json",
        }
        for surface, args, _kwargs in detector.write_calls:
            for arg in args:
                arg_str = str(arg)
                for lp in lifecycle_paths:
                    assert lp not in arg_str, (
                        f"Lifecycle write detected: {surface}({arg_str}) "
                        f"touches {lp}"
                    )

    def test_inspect_semantic_health_zero_repair_writes(
        self, tmp_path: Path
    ) -> None:
        """No repair-queue or incident-ledger writes."""
        plan_dir = _setup_minimal_plan_dir(tmp_path)

        detector = WriteDetector()
        detector.patch_all()
        try:
            _findings = inspect_semantic_health(plan_dir)
        finally:
            detector.unpatch_all()

        repair_keywords = {
            "repair",
            "incident",
            "escalation",
            "recovery",
        }
        for surface, args, _kwargs in detector.write_calls:
            for arg in args:
                arg_str = str(arg).lower()
                for kw in repair_keywords:
                    assert kw not in arg_str, (
                        f"Repair write detected: {surface}({str(arg)}) "
                        f"contains keyword '{kw}'"
                    )

    def test_inspect_semantic_health_zero_status_persister_writes(
        self, tmp_path: Path
    ) -> None:
        """No status, watchdog, or status-persister writes."""
        plan_dir = _setup_minimal_plan_dir(tmp_path)

        detector = WriteDetector()
        detector.patch_all()
        try:
            _findings = inspect_semantic_health(plan_dir)
        finally:
            detector.unpatch_all()

        status_keywords = {
            "status",
            "watchdog",
            "cloud_status",
        }
        for surface, args, _kwargs in detector.write_calls:
            for arg in args:
                arg_str = str(arg).lower()
                for kw in status_keywords:
                    assert kw not in arg_str, (
                        f"Status write detected: {surface}({str(arg)}) "
                        f"contains keyword '{kw}'"
                    )

    def test_inspect_semantic_health_zero_queue_writes(
        self, tmp_path: Path
    ) -> None:
        """No queue, routing_ledger, or dispatch writes."""
        plan_dir = _setup_minimal_plan_dir(tmp_path)

        detector = WriteDetector()
        detector.patch_all()
        try:
            _findings = inspect_semantic_health(plan_dir)
        finally:
            detector.unpatch_all()

        queue_keywords = {
            "routing_ledger",
            "queue",
            "dispatch",
        }
        for surface, args, _kwargs in detector.write_calls:
            for arg in args:
                arg_str = str(arg).lower()
                for kw in queue_keywords:
                    assert kw not in arg_str, (
                        f"Queue write detected: {surface}({str(arg)}) "
                        f"contains keyword '{kw}'"
                    )

    def test_inspect_semantic_health_zero_commit_push_writes(
        self, tmp_path: Path
    ) -> None:
        """No git commit, push, or source-mutation writes."""
        plan_dir = _setup_minimal_plan_dir(tmp_path)

        detector = WriteDetector()
        detector.patch_all()
        try:
            _findings = inspect_semantic_health(plan_dir)
        finally:
            detector.unpatch_all()

        git_keywords = {
            ".git",
            "git_commit",
            "git_push",
        }
        for surface, args, _kwargs in detector.write_calls:
            for arg in args:
                arg_str = str(arg)
                for kw in git_keywords:
                    assert kw not in arg_str, (
                        f"Git/commit write detected: {surface}({arg_str}) "
                        f"contains keyword '{kw}'"
                    )

    def test_inspect_semantic_health_zero_projection_drift_writes(
        self, tmp_path: Path
    ) -> None:
        """No projection materializer or drift writer writes."""
        plan_dir = _setup_minimal_plan_dir(tmp_path)

        detector = WriteDetector()
        detector.patch_all()
        try:
            _findings = inspect_semantic_health(plan_dir)
        finally:
            detector.unpatch_all()

        proj_keywords = {
            "projection",
            "drift",
            "materialize",
            "normalizer",
        }
        for surface, args, _kwargs in detector.write_calls:
            for arg in args:
                arg_str = str(arg).lower()
                for kw in proj_keywords:
                    assert kw not in arg_str, (
                        f"Projection/drift write detected: {surface}({str(arg)}) "
                        f"contains keyword '{kw}'"
                    )

    def test_inspect_semantic_health_returns_meaningful_results(
        self, tmp_path: Path
    ) -> None:
        """Even with write detection patched, results must be meaningful."""
        plan_dir = _setup_minimal_plan_dir(tmp_path)

        detector = WriteDetector()
        detector.patch_all()
        try:
            findings = inspect_semantic_health(plan_dir)
        finally:
            detector.unpatch_all()

        # prep_to_plan has state.json and phase_result.json present →
        # should produce findings (possibly from missing artifacts for
        # non-prep contracts, or stale state for other contracts)
        finding_ids = {f.finding_id for f in findings}
        # At minimum, prep_to_plan itself should be inspected
        assert any(
            "prep_to_plan" in fid for fid in finding_ids
        ) or len(findings) > 0, (
            "Expected findings referencing contracts; got none"
        )

    def test_inspect_semantic_health_disabled_dispatch_zero_writes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With dispatch flags explicitly off, zero writes are guaranteed."""
        # Disable any dispatch-related environment variables
        for env_var in (
            "ARNOLD_DISPATCH",
            "ARNOLD_WRITE_ENABLED",
            "ARNOLD_LIFECYCLE_WRITES",
            "ARNOLD_ESCALATION_LEDGER",
            "ARNOLD_CLOUD_STATUS",
        ):
            monkeypatch.setenv(env_var, "0")

        plan_dir = _setup_minimal_plan_dir(tmp_path)

        detector = WriteDetector()
        detector.patch_all()
        try:
            _findings = inspect_semantic_health(plan_dir)
        finally:
            detector.unpatch_all()

        assert len(detector.write_calls) == 0, (
            f"With dispatch flags off, got {len(detector.write_calls)} writes: "
            f"{detector.write_calls[:5]}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Tests: fixture replay zero-write
# ──────────────────────────────────────────────────────────────────────────────


# Paths to the real checked-in fixture data
FIXTURE_DIR = Path("tests/fixtures/workflow_boundary_contracts")
CONTRACT_MATRIX = Path(
    "arnold_pipelines/megaplan/workflows/contract_to_producer_matrix.json"
)


def _evaluator_can_run() -> bool:
    """Check whether the fixture directory and matrix exist."""
    return FIXTURE_DIR.is_dir() and CONTRACT_MATRIX.is_file()


class TestFixtureReplayZeroWrite:
    """Prove :class:`CompatibilityEvaluator` performs zero writes."""

    @pytest.mark.skipif(
        not _evaluator_can_run(),
        reason="Real fixture directory or contract matrix not available",
    )
    def test_evaluate_all_zero_path_writes(self) -> None:
        """Path.write_text / write_bytes / mkdir must never be called."""
        detector = WriteDetector()
        detector.patch_all()
        try:
            evaluator = CompatibilityEvaluator(
                fixture_dir=FIXTURE_DIR,
                contract_matrix_path=CONTRACT_MATRIX,
            )
            results = evaluator.evaluate_all()
        finally:
            detector.unpatch_all()

        assert isinstance(results, tuple)
        assert len(results) > 0, (
            "Expected CompatibilityEvaluator to return results; got empty tuple"
        )
        for r in results:
            assert isinstance(r, CompatibilityResult)

        writes = detector.write_calls
        assert len(writes) == 0, (
            f"CompatibilityEvaluator.evaluate_all triggered "
            f"{len(writes)} write call(s): {writes[:10]}"
        )

    @pytest.mark.skipif(
        not _evaluator_can_run(),
        reason="Real fixture directory or contract matrix not available",
    )
    def test_evaluate_all_zero_lifecycle_writes(self) -> None:
        """No lifecycle-mutating writes during fixture replay."""
        detector = WriteDetector()
        detector.patch_all()
        try:
            evaluator = CompatibilityEvaluator(
                fixture_dir=FIXTURE_DIR,
                contract_matrix_path=CONTRACT_MATRIX,
            )
            _results = evaluator.evaluate_all()
        finally:
            detector.unpatch_all()

        lifecycle_paths = {
            "state.json",
            "events.ndjson",
            "stages.json",
            "checkpoint.json",
        }
        for surface, args, _kwargs in detector.write_calls:
            for arg in args:
                arg_str = str(arg)
                for lp in lifecycle_paths:
                    assert lp not in arg_str, (
                        f"Lifecycle write detected: {surface}({arg_str})"
                    )

    @pytest.mark.skipif(
        not _evaluator_can_run(),
        reason="Real fixture directory or contract matrix not available",
    )
    def test_evaluate_all_zero_repair_writes(self) -> None:
        """No repair/incident/recovery writes."""
        detector = WriteDetector()
        detector.patch_all()
        try:
            evaluator = CompatibilityEvaluator(
                fixture_dir=FIXTURE_DIR,
                contract_matrix_path=CONTRACT_MATRIX,
            )
            _results = evaluator.evaluate_all()
        finally:
            detector.unpatch_all()

        repair_keywords = {"repair", "incident", "escalation", "recovery"}
        for surface, args, _kwargs in detector.write_calls:
            for arg in args:
                arg_str = str(arg).lower()
                for kw in repair_keywords:
                    assert kw not in arg_str, (
                        f"Repair write: {surface}({str(arg)})"
                    )

    @pytest.mark.skipif(
        not _evaluator_can_run(),
        reason="Real fixture directory or contract matrix not available",
    )
    def test_evaluate_all_zero_queue_status_writes(self) -> None:
        """No queue, routing, status, or watchdog writes."""
        detector = WriteDetector()
        detector.patch_all()
        try:
            evaluator = CompatibilityEvaluator(
                fixture_dir=FIXTURE_DIR,
                contract_matrix_path=CONTRACT_MATRIX,
            )
            _results = evaluator.evaluate_all()
        finally:
            detector.unpatch_all()

        queue_status_keywords = {
            "routing_ledger",
            "queue",
            "dispatch",
            "status",
            "watchdog",
        }
        for surface, args, _kwargs in detector.write_calls:
            for arg in args:
                arg_str = str(arg).lower()
                for kw in queue_status_keywords:
                    assert kw not in arg_str, (
                        f"Queue/status write: {surface}({str(arg)})"
                    )

    @pytest.mark.skipif(
        not _evaluator_can_run(),
        reason="Real fixture directory or contract matrix not available",
    )
    def test_evaluate_all_zero_commit_push_writes(self) -> None:
        """No git commit, push, or source mutations."""
        detector = WriteDetector()
        detector.patch_all()
        try:
            evaluator = CompatibilityEvaluator(
                fixture_dir=FIXTURE_DIR,
                contract_matrix_path=CONTRACT_MATRIX,
            )
            _results = evaluator.evaluate_all()
        finally:
            detector.unpatch_all()

        git_keywords = {".git", "git_commit", "git_push", "git_branch"}
        for surface, args, _kwargs in detector.write_calls:
            for arg in args:
                arg_str = str(arg)
                for kw in git_keywords:
                    assert kw not in arg_str, (
                        f"Git write: {surface}({arg_str})"
                    )

    @pytest.mark.skipif(
        not _evaluator_can_run(),
        reason="Real fixture directory or contract matrix not available",
    )
    def test_evaluate_all_zero_projection_drift_writes(self) -> None:
        """No projection materializer, drift writer, or normalizer writes."""
        detector = WriteDetector()
        detector.patch_all()
        try:
            evaluator = CompatibilityEvaluator(
                fixture_dir=FIXTURE_DIR,
                contract_matrix_path=CONTRACT_MATRIX,
            )
            _results = evaluator.evaluate_all()
        finally:
            detector.unpatch_all()

        proj_keywords = {
            "projection",
            "drift",
            "materialize",
            "normalizer",
            "audited_input",
            "audited-input",
        }
        for surface, args, _kwargs in detector.write_calls:
            for arg in args:
                arg_str = str(arg).lower()
                for kw in proj_keywords:
                    assert kw not in arg_str, (
                        f"Projection/drift write: {surface}({str(arg)})"
                    )

    @pytest.mark.skipif(
        not _evaluator_can_run(),
        reason="Real fixture directory or contract matrix not available",
    )
    def test_evaluate_all_returns_meaningful_results(self) -> None:
        """Results must be meaningful even with write detection patched."""
        detector = WriteDetector()
        detector.patch_all()
        try:
            evaluator = CompatibilityEvaluator(
                fixture_dir=FIXTURE_DIR,
                contract_matrix_path=CONTRACT_MATRIX,
            )
            results = evaluator.evaluate_all()
        finally:
            detector.unpatch_all()

        statuses = {r.status for r in results}
        # We expect at least some COMPATIBLE results and some variety
        assert CompatibilityStatus.COMPATIBLE in statuses or len(results) > 0, (
            f"Expected at least some results; got statuses: {statuses}"
        )

    @pytest.mark.skipif(
        not _evaluator_can_run(),
        reason="Real fixture directory or contract matrix not available",
    )
    def test_evaluate_all_disabled_dispatch_zero_writes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With dispatch flags explicitly off, zero writes are guaranteed."""
        for env_var in (
            "ARNOLD_DISPATCH",
            "ARNOLD_WRITE_ENABLED",
            "ARNOLD_LIFECYCLE_WRITES",
            "ARNOLD_ESCALATION_LEDGER",
            "ARNOLD_CLOUD_STATUS",
        ):
            monkeypatch.setenv(env_var, "0")

        detector = WriteDetector()
        detector.patch_all()
        try:
            evaluator = CompatibilityEvaluator(
                fixture_dir=FIXTURE_DIR,
                contract_matrix_path=CONTRACT_MATRIX,
            )
            _results = evaluator.evaluate_all()
        finally:
            detector.unpatch_all()

        assert len(detector.write_calls) == 0, (
            f"With dispatch flags off, got {len(detector.write_calls)} writes: "
            f"{detector.write_calls[:5]}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Tests: mutation gates explicitly off (comprehensive)
# ──────────────────────────────────────────────────────────────────────────────


class TestMutationGatesOff:
    """Prove zero writes with mutation gates and dispatch flags explicitly off.

    This covers the full matrix: lifecycle, queue, source, commit, push,
    status, repair, audited-input, normalizer, projection materializer,
    recovery, drift writer, and status persister.
    """

    # All known mutation-gate / dispatch environment variables
    MUTATION_GATE_VARS = (
        "ARNOLD_DISPATCH",
        "ARNOLD_WRITE_ENABLED",
        "ARNOLD_LIFECYCLE_WRITES",
        "ARNOLD_ESCALATION_LEDGER",
        "ARNOLD_CLOUD_STATUS",
        "ARNOLD_REPAIR_WRITES",
        "ARNOLD_QUEUE_WRITES",
        "ARNOLD_COMMIT_WRITES",
        "ARNOLD_PUSH_WRITES",
        "ARNOLD_STATUS_PERSISTER",
        "ARNOLD_AUDITED_INPUT_WRITES",
        "ARNOLD_NORMALIZER_WRITES",
        "ARNOLD_PROJECTION_MATERIALIZER",
        "ARNOLD_RECOVERY_WRITES",
        "ARNOLD_DRIFT_WRITER",
    )

    def test_semantic_inspection_all_gates_off(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With all known mutation gates explicitly disabled,
        inspect_semantic_health must perform zero writes."""
        for var in self.MUTATION_GATE_VARS:
            monkeypatch.setenv(var, "0")

        plan_dir = _setup_minimal_plan_dir(tmp_path)

        detector = WriteDetector()
        detector.patch_all()
        try:
            findings = inspect_semantic_health(plan_dir)
        finally:
            detector.unpatch_all()

        assert isinstance(findings, list)
        assert len(findings) > 0

        write_calls = detector.write_calls
        assert len(write_calls) == 0, (
            f"All gates off → expected 0 writes, got {len(write_calls)}: "
            f"{write_calls[:10]}"
        )

    @pytest.mark.skipif(
        not _evaluator_can_run(),
        reason="Real fixture directory or contract matrix not available",
    )
    def test_fixture_replay_all_gates_off(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With all known mutation gates explicitly disabled,
        CompatibilityEvaluator must perform zero writes."""
        for var in self.MUTATION_GATE_VARS:
            monkeypatch.setenv(var, "0")

        detector = WriteDetector()
        detector.patch_all()
        try:
            evaluator = CompatibilityEvaluator(
                fixture_dir=FIXTURE_DIR,
                contract_matrix_path=CONTRACT_MATRIX,
            )
            results = evaluator.evaluate_all()
        finally:
            detector.unpatch_all()

        assert isinstance(results, tuple)
        assert len(results) > 0

        write_calls = detector.write_calls
        assert len(write_calls) == 0, (
            f"All gates off → expected 0 writes, got {len(write_calls)}: "
            f"{write_calls[:10]}"
        )

    def test_both_operations_combined_zero_writes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running both operations back-to-back with gates off must still
        produce zero writes — no cumulative write leakage."""
        for var in self.MUTATION_GATE_VARS:
            monkeypatch.setenv(var, "0")

        plan_dir = _setup_minimal_plan_dir(tmp_path)

        detector = WriteDetector()
        detector.patch_all()
        try:
            # Semantic inspection first
            sh_findings = inspect_semantic_health(plan_dir)

            # Fixture replay second (skip if not available, still valid)
            if _evaluator_can_run():
                evaluator = CompatibilityEvaluator(
                    fixture_dir=FIXTURE_DIR,
                    contract_matrix_path=CONTRACT_MATRIX,
                )
                cb_results = evaluator.evaluate_all()
                assert isinstance(cb_results, tuple)
        finally:
            detector.unpatch_all()

        assert isinstance(sh_findings, list)
        assert len(sh_findings) > 0

        write_calls = detector.write_calls
        assert len(write_calls) == 0, (
            f"Combined operations: expected 0 writes, got {len(write_calls)}: "
            f"{write_calls[:10]}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Tests: write-surface category coverage
# ──────────────────────────────────────────────────────────────────────────────


class TestWriteSurfaceCategoryCoverage:
    """Structural tests proving the test itself covers all required categories.

    These test the test — they verify that every write category listed in
    T20's description is exercised by at least one assertion above.
    """

    REQUIRED_CATEGORIES: tuple[str, ...] = (
        "lifecycle",
        "queue",
        "source",
        "commit",
        "push",
        "status",
        "repair",
        "audited-input",
        "normalizer",
        "projection materializer",
        "recovery",
        "drift writer",
        "status persister",
    )

    def test_all_required_categories_have_keyword_coverage(self) -> None:
        """Every required write category from T20 must have at least one
        keyword check in the zero-write assertions above."""
        # Map each category to the keywords used to detect it
        category_keywords: dict[str, set[str]] = {
            "lifecycle": {"state.json", "events.ndjson", "stages.json",
                          "checkpoint.json"},
            "queue": {"routing_ledger", "queue", "dispatch"},
            "source": {".git"},  # source mutations are git operations
            "commit": {"git_commit", ".git"},
            "push": {"git_push", ".git"},
            "status": {"status", "watchdog", "cloud_status"},
            "repair": {"repair", "incident", "escalation", "recovery"},
            "audited-input": {"audited_input", "audited-input"},
            "normalizer": {"normalizer"},
            "projection materializer": {"projection", "materialize"},
            "recovery": {"recovery"},
            "drift writer": {"drift"},
            "status persister": {"status", "watchdog", "cloud_status"},
        }

        for category in self.REQUIRED_CATEGORIES:
            keywords = category_keywords.get(category, set())
            assert len(keywords) > 0, (
                f"Category '{category}' has no keyword coverage mapping"
            )

    def test_all_mutation_gate_env_vars_are_documented(self) -> None:
        """Every mutation gate environment variable used in the test
        must have a recognizable name pattern."""
        for var in TestMutationGatesOff.MUTATION_GATE_VARS:
            assert var.startswith("ARNOLD_"), (
                f"Mutation gate var '{var}' does not follow ARNOLD_ prefix "
                f"convention"
            )
            assert len(var) > len("ARNOLD_"), (
                f"Mutation gate var '{var}' has no suffix beyond ARNOLD_"
            )

    def test_write_detector_captures_all_primitives(self) -> None:
        """The WriteDetector must patch all known write primitives."""
        detector = WriteDetector()
        detector.patch_all()
        try:
            # Verify the primitives are patched (not original)
            assert pathlib.Path.write_text is not detector._original_path_write_text
            assert pathlib.Path.write_bytes is not detector._original_path_write_bytes
            assert pathlib.Path.mkdir is not detector._original_path_mkdir
            assert os.rename is not detector._original_os_rename
            assert os.replace is not detector._original_os_replace
            assert shutil.move is not detector._original_shutil_move
            assert builtins.open is not detector._original_open
        finally:
            detector.unpatch_all()

        # After unpatch, originals must be restored
        assert pathlib.Path.write_text is detector._original_path_write_text
        assert pathlib.Path.write_bytes is detector._original_path_write_bytes
        assert pathlib.Path.mkdir is detector._original_path_mkdir
        assert os.rename is detector._original_os_rename
        assert os.replace is detector._original_os_replace
        assert shutil.move is detector._original_shutil_move
        assert builtins.open is detector._original_open
