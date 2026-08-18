"""No-new-failures delta lifecycle for narrow_recheck (occurrence a07166d38fbc).

Contract under test (proposal from the codex consult, 2026-08-18T20:42Z):

- A pre-dispatch narrow_recheck that demands exit 0 on full-file selectors
  under a planner probe budget is a deterministic gate for suites whose
  selectors exceed the probe budget or carry environment-dependent failures.
  The pre-dispatch run becomes a COMPLETE pre-execution envelope capture:
  exit 0 -> known-empty envelope; exit 1 with a fully parsed failure set ->
  captured envelope (verdict deferred); timeout/signal/exit 2-5/collection
  errors/malformed output -> fail closed (never an empty envelope).
- The pass/fail verdict moves to a post-adoption delta recheck that compares
  the merged state against the envelope: unchanged failure set passes even
  with raw exit 1; any novel failure blocks and never carries authority.
- Resume is artifact-based: a durable envelope is reused (no re-capture, no
  redo); a durable POST_DELTA_PASSED artifact skips the rerun; a real delta
  failure never skips.
- The comparison ceiling is the authoritative full-suite budget
  (post_execute_suite), never the planner probe value; legacy embedded
  ``timeout <N>s pytest`` commands are recompiled from validated structured
  selectors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.execute.batch import (
    POST_DELTA_FAILED,
    POST_DELTA_PASSED,
    PRE_ENVELOPE_CAPTURED,
    _narrow_recheck_delta_policy,
    _post_delta_artifact_path,
    _pre_envelope_artifact_path,
    _recompile_legacy_narrow_recheck_command,
    _rerun_deferred_selector_validation_jobs,
    _run_batch_validation_jobs,
    _validation_comparison_ceiling,
)
from arnold_pipelines.megaplan.orchestration.suite_runner import SuiteRunResult

SEL_A = "tests/cloud/test_progress_auditor.py"
SEL_B = "tests/cloud/test_wrapper_authority_bypass_gating.py"
LEGACY_COMMAND = (
    f"timeout 120s pytest {SEL_A} {SEL_B} --tb=short -q"
)


def _make_state(project_dir: Path) -> dict:
    return {
        "name": "test-plan",
        "iteration": 1,
        "current_state": "executing",
        "config": {
            "mode": "code",
            "project_dir": str(project_dir),
        },
        "meta": {},
        "history": [],
        "sessions": {},
    }


def _narrow_ready_fixture(tmp_path: Path) -> tuple[Path, Path, dict]:
    """A finalized narrow_recheck job (legacy embedded-timeout shape) with
    existing selectors + an authoritative post_execute_suite ceiling."""
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    for sel in (SEL_A, SEL_B):
        path = project_dir / sel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def test_ok(): pass\n", encoding="utf-8")
    finalize_data: dict = {
        "task_contract_version": 2,
        "tasks": [
            {
                "id": "T1",
                "status": "pending",
                "write_set": {"paths": [SEL_A, SEL_B], "complete": True},
            }
        ],
        "validation_jobs": [
            {
                "id": "VJ12",
                "kind": "narrow_recheck",
                "command": LEGACY_COMMAND,
                "selectors": [SEL_A, SEL_B],
                "max_seconds": 120,
                "timeout_seconds": 120,
                "task_id": "T1",
                "mutates": False,
                "writes_files": False,
                "expected_exit_codes": [0],
            },
            {
                "id": "VJ1",
                "kind": "post_execute_suite",
                "command": f"timeout 3600s pytest tests --tb=short -q",
                "selectors": ["tests"],
                "max_seconds": 3600,
                "task_id": "",
                "mutates": False,
                "writes_files": False,
                "expected_exit_codes": [0],
            },
        ],
    }
    return plan_dir, project_dir, finalize_data


def _result(
    *,
    exit_code: int,
    failures: list[str],
    status: str = "failed",
    collected_ids: list[str] | None = None,
    collected: int = 0,
    collections_parse_ok: bool = True,
    collection_errors: list[str] | None = None,
    timeout_reason: str | None = None,
    code_hash: str = "sha256:tree",
    command: str = "pytest ...",
) -> SuiteRunResult:
    return SuiteRunResult(
        run_id="run-vj12",
        phase="narrow_recheck",
        command=command,
        duration=0.1,
        collected=collected if collected else len(collected_ids or []),
        collected_ids=list(collected_ids or failures),
        failures=list(failures),
        passes=[],
        status=status,
        exit_code=exit_code,
        raw_log_path=Path("/tmp/raw.log"),
        code_hash=code_hash,
        collections_parse_ok=collections_parse_ok,
        collection_errors=collection_errors,
        timeout_reason=timeout_reason,
    )


def _tree_code_hash(project_dir: Path) -> str:
    """Real source-tree digest via suite_runner's canonical computation.

    The resume-reuse predicate compares a stored envelope's ``code_hash``
    against the CURRENT tree, so the fake run result must carry the real
    digest of the fixture tree (not a placeholder).
    """
    from arnold_pipelines.megaplan.orchestration.suite_runner import (
        _compute_code_hash,
    )

    return _compute_code_hash(project_dir)


# ---------------------------------------------------------------------------
# Unit: legacy recompile + ceiling derivation
# ---------------------------------------------------------------------------


def test_recompile_legacy_command_removes_embedded_timeout() -> None:
    rebuilt = _recompile_legacy_narrow_recheck_command(
        LEGACY_COMMAND, [SEL_A, SEL_B]
    )
    assert rebuilt == f"pytest {SEL_A} {SEL_B} --tb=short -q"
    assert "timeout" not in rebuilt


def test_recompile_legacy_command_drift_fails_closed() -> None:
    # Command selectors drift from the structured selectors -> refuse.
    assert (
        _recompile_legacy_narrow_recheck_command(
            f"timeout 120s pytest tests/other.py --tb=short -q",
            [SEL_A, SEL_B],
        )
        is None
    )


def test_recompile_legacy_command_non_legacy_shape() -> None:
    assert (
        _recompile_legacy_narrow_recheck_command(
            f"pytest {SEL_A} --tb=short -q", [SEL_A]
        )
        is None
    )


def test_comparison_ceiling_prefers_post_execute_suite(
    tmp_path: Path,
) -> None:
    _, _, finalize_data = _narrow_ready_fixture(tmp_path)
    assert _validation_comparison_ceiling(finalize_data) == 3600


def test_comparison_ceiling_none_without_budgets() -> None:
    assert _validation_comparison_ceiling({"validation_jobs": []}) is None


def test_delta_policy_derived_from_legacy_shape() -> None:
    job = {
        "kind": "narrow_recheck",
        "command": LEGACY_COMMAND,
        "selectors": [SEL_A, SEL_B],
    }
    assert _narrow_recheck_delta_policy(job, job.get("command")) is True


def test_delta_policy_explicit_acceptance_mode() -> None:
    job = {
        "kind": "narrow_recheck",
        "command": f"pytest {SEL_A} --tb=short -q",
        "selectors": [SEL_A],
        "acceptance_mode": "no_new_failures_delta",
    }
    assert _narrow_recheck_delta_policy(job, job.get("command")) is True


def test_delta_policy_plain_job_stays_strict() -> None:
    job = {
        "kind": "narrow_recheck",
        "command": f"pytest {SEL_A} --tb=short -q",
        "selectors": [SEL_A],
    }
    assert _narrow_recheck_delta_policy(job, job.get("command")) is False


# ---------------------------------------------------------------------------
# Pre-dispatch envelope capture
# ---------------------------------------------------------------------------


def test_pre_dispatch_exit_one_captures_envelope_and_dispatches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import patch

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    fake = _result(
        exit_code=1,
        failures=["tests/cloud/test_progress_auditor.py::test_a"],
        collected_ids=[
            "tests/cloud/test_progress_auditor.py::test_a",
            "tests/cloud/test_progress_auditor.py::test_b",
        ],
        collected=2,
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ) as mock_run:
        with patch(
            "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
            return_value={"event_id": "ev"},
        ):
            with patch(
                "arnold_pipelines.megaplan.observability.work_ledger.emit_unavailable_reason",
            ):
                evidence = _run_batch_validation_jobs(
                    plan_dir=plan_dir,
                    project_dir=project_dir,
                    finalize_data=finalize_data,
                    batch_task_ids=["T1"],
                    state=state,
                    admission=True,
                )
    mock_run.assert_called_once()
    envelope = evidence[0]
    assert envelope["status"] == PRE_ENVELOPE_CAPTURED
    assert envelope["admission"] == "pre_dispatch_delta_envelope"
    assert envelope["failures"] == [
        "tests/cloud/test_progress_auditor.py::test_a"
    ]
    assert envelope["comparison_ceiling"] == 3600
    # Durable envelope artifact for resume reuse.
    artifact = _pre_envelope_artifact_path(plan_dir / "verification", "VJ12")
    assert artifact.exists()
    stored = artifact.read_text(encoding="utf-8")
    assert PRE_ENVELOPE_CAPTURED in stored


def test_pre_dispatch_exit_zero_persists_known_empty_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import patch

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    fake = _result(
        exit_code=0,
        failures=[],
        collected_ids=["tests/cloud/test_progress_auditor.py::test_a"],
        collected=1,
        status="passed",
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ):
        with patch(
            "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
            return_value={"event_id": "ev"},
        ):
            evidence = _run_batch_validation_jobs(
                plan_dir=plan_dir,
                project_dir=project_dir,
                finalize_data=finalize_data,
                batch_task_ids=["T1"],
                state=state,
                admission=True,
            )
    assert evidence[0]["admission"] == "pre_dispatch_delta_envelope"
    artifact = _pre_envelope_artifact_path(plan_dir / "verification", "VJ12")
    assert artifact.exists()


def test_pre_dispatch_timeout_never_becomes_empty_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.types import CliError
    from unittest.mock import patch

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    fake = _result(
        exit_code=124,
        failures=[],
        collected=0,
        status="runner_error",
        timeout_reason="deadline",
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ):
        with patch(
            "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
            return_value={"event_id": "ev"},
        ):
            with pytest.raises(CliError) as exc_info:
                _run_batch_validation_jobs(
                    plan_dir=plan_dir,
                    project_dir=project_dir,
                    finalize_data=finalize_data,
                    batch_task_ids=["T1"],
                    state=state,
                    admission=True,
                )
    assert exc_info.value.code == "validation_job_failed"
    # No envelope artifact may exist for an incomplete run.
    artifact = _pre_envelope_artifact_path(plan_dir / "verification", "VJ12")
    assert not artifact.exists()


def test_pre_dispatch_collection_error_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.types import CliError
    from unittest.mock import patch

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    fake = _result(
        exit_code=2,
        failures=[],
        collected=0,
        status="failed",
        collection_errors=["tests/cloud/test_progress_auditor.py: cannot collect"],
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ):
        with patch(
            "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
            return_value={"event_id": "ev"},
        ):
            with pytest.raises(CliError) as exc_info:
                _run_batch_validation_jobs(
                    plan_dir=plan_dir,
                    project_dir=project_dir,
                    finalize_data=finalize_data,
                    batch_task_ids=["T1"],
                    state=state,
                    admission=True,
                )
    assert exc_info.value.code == "validation_job_failed"


def test_pre_dispatch_exit_one_without_failure_data_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.types import CliError
    from unittest.mock import patch

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    fake = _result(
        exit_code=1,
        failures=[],
        collected=0,
        status="failed",
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ):
        with patch(
            "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
            return_value={"event_id": "ev"},
        ):
            with pytest.raises(CliError) as exc_info:
                _run_batch_validation_jobs(
                    plan_dir=plan_dir,
                    project_dir=project_dir,
                    finalize_data=finalize_data,
                    batch_task_ids=["T1"],
                    state=state,
                    admission=True,
                )
    assert exc_info.value.code == "validation_job_failed"


def test_resume_reuses_durable_pre_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import patch

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    # First pass captures the envelope.
    fake = _result(
        exit_code=1,
        failures=["tests/cloud/test_progress_auditor.py::test_a"],
        collected_ids=["tests/cloud/test_progress_auditor.py::test_a"],
        collected=1,
        code_hash=_tree_code_hash(project_dir),
        command=_recompile_legacy_narrow_recheck_command(
            LEGACY_COMMAND, [SEL_A, SEL_B]
        ),
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ) as mock_run:
        with patch(
            "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
            return_value={"event_id": "ev"},
        ):
            _run_batch_validation_jobs(
                plan_dir=plan_dir,
                project_dir=project_dir,
                finalize_data=finalize_data,
                batch_task_ids=["T1"],
                state=state,
                admission=True,
            )
    mock_run.assert_called_once()
    # Resume: the durable envelope is reused — the suite must NOT re-run.
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ) as mock_run2:
        evidence = _run_batch_validation_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            batch_task_ids=["T1"],
            state=state,
            admission=True,
        )
    mock_run2.assert_not_called()
    assert evidence[0]["status"] == PRE_ENVELOPE_CAPTURED


def test_resume_envelope_requires_matching_selectors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import patch

    from arnold_pipelines.megaplan.types import CliError

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    # A stale envelope artifact with DIFFERENT selectors must never be reused
    # AND must never be re-captured onto the current tree: a completed
    # envelope whose selectors/command/source digest no longer match fails
    # closed (drift), so the post-adoption delta can never self-compare.
    stale = {
        "job_id": "VJ12",
        "status": PRE_ENVELOPE_CAPTURED,
        "selectors": ["tests/other.py"],
        "failures": [],
        "evidence_hash": "sha256:stale",
    }
    artifact = _pre_envelope_artifact_path(plan_dir / "verification", "VJ12")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        __import__("json").dumps(stale), encoding="utf-8"
    )
    fake = _result(
        exit_code=1,
        failures=["tests/cloud/test_progress_auditor.py::test_a"],
        collected_ids=["tests/cloud/test_progress_auditor.py::test_a"],
        collected=1,
        code_hash=_tree_code_hash(project_dir),
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ) as mock_run:
        with patch(
            "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
            return_value={"event_id": "ev"},
        ):
            with pytest.raises(CliError) as exc_info:
                _run_batch_validation_jobs(
                    plan_dir=plan_dir,
                    project_dir=project_dir,
                    finalize_data=finalize_data,
                    batch_task_ids=["T1"],
                    state=state,
                    admission=True,
                )
    # Fail closed BEFORE any run: the stale envelope is neither reused nor
    # overwritten by a re-capture.
    mock_run.assert_not_called()
    assert exc_info.value.code == "validation_job_failed"
    assert exc_info.value.extra.get("reason") == "pre_envelope_digest_drift"


# ---------------------------------------------------------------------------
# Post-adoption delta verdict
# ---------------------------------------------------------------------------


def _accepted_task_payload() -> dict:
    """Mirror of the m8a helper: an authority-accepted T1 result envelope."""
    from arnold_pipelines.megaplan.authority.batch_scope import RESULT_ENVELOPES_KEY
    from arnold_pipelines.megaplan.authority.binding import (
        DispatchIdentity,
        TASK_RESULT_CAPABILITY,
    )
    from arnold_pipelines.megaplan.execute.batch import _task_result_envelope

    entry: dict = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "created the task output",
        "files_changed": [SEL_A, SEL_B],
        "commands_run": ["pytest"],
    }
    identity = DispatchIdentity.create(
        dispatch_id="dispatch-vj12",
        run_id="run-vj12",
        run_revision="revision-vj12",
        coordinator_attempt_id="coordinator-vj12",
        fence_token=1,
        subject_ids=("T1",),
        capabilities=(TASK_RESULT_CAPABILITY,),
        prerequisite_digest="prereq-vj12",
        worker_id="worker-vj12",
    )
    envelope = _task_result_envelope(
        identity=identity,
        entry=entry,
        ordinal=1,
        source="test",
    )
    assert envelope is not None
    entry["authority_validation"] = {
        "outcome": "accepted",
        "envelope_digest": envelope.digest(),
    }
    return {
        "task_updates": [entry],
        RESULT_ENVELOPES_KEY: [envelope.to_dict()],
    }


def test_post_delta_same_failure_set_passes_and_persists_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import patch

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    failures = [
        "tests/cloud/test_progress_auditor.py::test_a",
        "tests/cloud/test_progress_auditor.py::test_b",
    ]
    collected_ids = list(failures) + [
        "tests/cloud/test_progress_auditor.py::test_ok"
    ]
    envelope = {
        "job_id": "VJ12",
        "status": PRE_ENVELOPE_CAPTURED,
        "admission": "pre_dispatch_delta_envelope",
        "failures": list(failures),
        "collected_ids": list(collected_ids),
        "selectors": [SEL_A, SEL_B],
    }
    # In production the merge path updates the finalized task before the
    # post-merge recheck.  Mirror that post-merge state here.
    finalize_data["tasks"][0]["status"] = "done"
    # Post-merge rerun: same failure set -> delta clean.
    fake = _result(
        exit_code=1,
        failures=list(failures),
        collected_ids=list(collected_ids),
        collected=len(collected_ids),
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ) as mock_run:
        rerun = _rerun_deferred_selector_validation_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            batch_task_ids=["T1"],
            pre_dispatch_results=[envelope],
            payload=_accepted_task_payload(),
            state=state,
        )
    mock_run.assert_called_once()
    assert rerun[0]["status"] == POST_DELTA_PASSED
    assert rerun[0]["admission"] == "post_dispatch_delta"
    assert rerun[0]["newly_failing"] == []
    # Durable post-delta artifact -> resume does not redo.
    assert _post_delta_artifact_path(plan_dir / "verification", "VJ12").exists()


def test_post_delta_new_failure_blocks_without_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.types import CliError
    from unittest.mock import patch

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    baseline_failures = [
        "tests/cloud/test_progress_auditor.py::test_a",
    ]
    envelope = {
        "job_id": "VJ12",
        "status": PRE_ENVELOPE_CAPTURED,
        "admission": "pre_dispatch_delta_envelope",
        "failures": list(baseline_failures),
        "collected_ids": list(baseline_failures),
        "selectors": [SEL_A, SEL_B],
    }
    finalize_data["tasks"][0]["status"] = "done"
    # Post-merge rerun: the task introduced a NEW failure.
    fake = _result(
        exit_code=1,
        failures=list(baseline_failures)
        + ["tests/cloud/test_progress_auditor.py::test_new_regression"],
        collected_ids=list(baseline_failures)
        + ["tests/cloud/test_progress_auditor.py::test_new_regression"],
        collected=2,
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ):
        with pytest.raises(CliError) as exc_info:
            _rerun_deferred_selector_validation_jobs(
                plan_dir=plan_dir,
                project_dir=project_dir,
                finalize_data=finalize_data,
                batch_task_ids=["T1"],
                pre_dispatch_results=[envelope],
                payload=_accepted_task_payload(),
                state=state,
            )
    assert exc_info.value.code == "deferred_validation_result_missing"
    assert exc_info.value.extra.get("reason") == "post_delta_new_failures"
    assert (
        "test_new_regression"
        in " ".join(exc_info.value.extra.get("newly_failing", []))
    )
    # The failed delta is persisted but NEVER reused as a pass.
    failed_artifact = _post_delta_artifact_path(
        plan_dir / "verification", "VJ12"
    )
    assert failed_artifact.exists()
    assert POST_DELTA_PASSED not in failed_artifact.read_text(encoding="utf-8")


def test_post_delta_timeout_blocks_without_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.types import CliError
    from unittest.mock import patch

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    envelope = {
        "job_id": "VJ12",
        "status": PRE_ENVELOPE_CAPTURED,
        "admission": "pre_dispatch_delta_envelope",
        "failures": ["tests/cloud/test_progress_auditor.py::test_a"],
        "collected_ids": ["tests/cloud/test_progress_auditor.py::test_a"],
        "selectors": [SEL_A, SEL_B],
    }
    finalize_data["tasks"][0]["status"] = "done"
    fake = _result(
        exit_code=124,
        failures=[],
        collected=0,
        status="runner_error",
        timeout_reason="deadline",
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ):
        with pytest.raises(CliError) as exc_info:
            _rerun_deferred_selector_validation_jobs(
                plan_dir=plan_dir,
                project_dir=project_dir,
                finalize_data=finalize_data,
                batch_task_ids=["T1"],
                pre_dispatch_results=[envelope],
                payload=_accepted_task_payload(),
                state=state,
            )
    assert exc_info.value.code == "validation_job_failed"


def test_resume_after_delta_pass_does_not_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import patch

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    failures = ["tests/cloud/test_progress_auditor.py::test_a"]
    envelope = {
        "job_id": "VJ12",
        "status": PRE_ENVELOPE_CAPTURED,
        "admission": "pre_dispatch_delta_envelope",
        "failures": list(failures),
        "collected_ids": list(failures),
        "selectors": [SEL_A, SEL_B],
        "evidence_hash": "sha256:env",
    }
    finalize_data["tasks"][0]["status"] = "done"
    # Simulate the durable POST_DELTA_PASSED artifact from a prior attempt.
    # It must carry the same selectors, the current source digest, and the
    # exact pre-envelope evidence hash it was computed against — otherwise
    # the pass is stale and must be recomputed, never blindly skipped.
    passed = {
        "job_id": "VJ12",
        "status": POST_DELTA_PASSED,
        "admission": "post_dispatch_delta",
        "newly_failing": [],
        "selectors": [SEL_A, SEL_B],
        "code_hash": _tree_code_hash(project_dir),
        "baseline_envelope_hash": "sha256:env",
        "evidence_hash": "sha256:passed",
    }
    artifact = _post_delta_artifact_path(plan_dir / "verification", "VJ12")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(__import__("json").dumps(passed), encoding="utf-8")
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
    ) as mock_run:
        rerun = _rerun_deferred_selector_validation_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            batch_task_ids=["T1"],
            pre_dispatch_results=[envelope],
            payload=_accepted_task_payload(),
            state=state,
        )
    mock_run.assert_not_called()
    assert rerun[0]["status"] == POST_DELTA_PASSED


def test_post_delta_rerun_uses_full_suite_comparison_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gap-1 regression: the post-adoption rerun deadline is the authoritative
    full-suite ceiling (3600), never the planner probe budget (120)."""
    import time as _time

    from unittest.mock import patch

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    failures = ["tests/cloud/test_progress_auditor.py::test_a"]
    envelope = {
        "job_id": "VJ12",
        "status": PRE_ENVELOPE_CAPTURED,
        "admission": "pre_dispatch_delta_envelope",
        "failures": list(failures),
        "collected_ids": list(failures),
        "selectors": [SEL_A, SEL_B],
        "comparison_ceiling": 3600,
    }
    finalize_data["tasks"][0]["status"] = "done"
    fake = _result(
        exit_code=1,
        failures=list(failures),
        collected_ids=list(failures),
        collected=1,
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ) as mock_run:
        rerun = _rerun_deferred_selector_validation_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            batch_task_ids=["T1"],
            pre_dispatch_results=[envelope],
            payload=_accepted_task_payload(),
            state=state,
        )
    mock_run.assert_called_once()
    kwargs = mock_run.call_args.kwargs
    deadline = kwargs.get("deadline_seconds")
    assert deadline is not None
    # ~3600s out, comfortably beyond the 120s probe budget (the selectors take
    # ~254s; a 120s deadline would deterministically exit 124).
    assert deadline - _time.monotonic() > 300
    assert rerun[0]["status"] == POST_DELTA_PASSED


def test_resume_after_delta_failure_does_not_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A durable POST_DELTA_FAILED artifact is never reused: the candidate must
    be reworked and the check re-run against the current pre-envelope."""
    from unittest.mock import patch

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    failures = ["tests/cloud/test_progress_auditor.py::test_a"]
    envelope = {
        "job_id": "VJ12",
        "status": PRE_ENVELOPE_CAPTURED,
        "admission": "pre_dispatch_delta_envelope",
        "failures": list(failures),
        "collected_ids": list(failures),
        "selectors": [SEL_A, SEL_B],
        "evidence_hash": "sha256:env",
    }
    finalize_data["tasks"][0]["status"] = "done"
    failed = {
        "job_id": "VJ12",
        "status": POST_DELTA_FAILED,
        "admission": "post_dispatch_delta",
        "newly_failing": ["tests/cloud/test_progress_auditor.py::test_new"],
        "selectors": [SEL_A, SEL_B],
        "code_hash": _tree_code_hash(project_dir),
        "baseline_envelope_hash": "sha256:env",
        "evidence_hash": "sha256:failed",
    }
    artifact = _post_delta_artifact_path(plan_dir / "verification", "VJ12")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(__import__("json").dumps(failed), encoding="utf-8")
    # The reworked candidate now matches the baseline failure set -> recheck
    # runs again and passes; the failed artifact is never treated as a skip.
    fake = _result(
        exit_code=1,
        failures=list(failures),
        collected_ids=list(failures),
        collected=1,
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ) as mock_run:
        rerun = _rerun_deferred_selector_validation_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            batch_task_ids=["T1"],
            pre_dispatch_results=[envelope],
            payload=_accepted_task_payload(),
            state=state,
        )
    mock_run.assert_called_once()
    assert rerun[0]["status"] == POST_DELTA_PASSED


def test_stale_post_delta_pass_is_recomputed_not_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A POST_DELTA_PASSED artifact computed against a DIFFERENT pre-envelope
    (or a different tree) is stale: the rerun recomputes the verdict instead
    of blindly skipping."""
    from unittest.mock import patch

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    failures = ["tests/cloud/test_progress_auditor.py::test_a"]
    envelope = {
        "job_id": "VJ12",
        "status": PRE_ENVELOPE_CAPTURED,
        "admission": "pre_dispatch_delta_envelope",
        "failures": list(failures),
        "collected_ids": list(failures),
        "selectors": [SEL_A, SEL_B],
        "evidence_hash": "sha256:env-current",
    }
    finalize_data["tasks"][0]["status"] = "done"
    passed_stale = {
        "job_id": "VJ12",
        "status": POST_DELTA_PASSED,
        "admission": "post_dispatch_delta",
        "newly_failing": [],
        "selectors": [SEL_A, SEL_B],
        "code_hash": _tree_code_hash(project_dir),
        "baseline_envelope_hash": "sha256:env-stale",
        "evidence_hash": "sha256:passed-stale",
    }
    artifact = _post_delta_artifact_path(plan_dir / "verification", "VJ12")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(__import__("json").dumps(passed_stale), encoding="utf-8")
    fake = _result(
        exit_code=1,
        failures=list(failures),
        collected_ids=list(failures),
        collected=1,
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ) as mock_run:
        rerun = _rerun_deferred_selector_validation_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            batch_task_ids=["T1"],
            pre_dispatch_results=[envelope],
            payload=_accepted_task_payload(),
            state=state,
        )
    # Stale pass -> recompute against the current envelope -> fresh pass.
    mock_run.assert_called_once()
    assert rerun[0]["status"] == POST_DELTA_PASSED
    assert rerun[0]["baseline_envelope_hash"] == "sha256:env-current"


def test_post_delta_reruns_suite_even_when_durable_pre_envelope_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Production-shaped regression (codex ship-verdict item): after a durable
    pre-envelope is captured in the plan's verification dir, the post-adoption
    rerun MUST execute a SECOND suite invocation and produce POST_DELTA_PASSED
    (or block) — it must never consume the stored envelope and skip the
    comparison, and must never overwrite the pre-envelope."""
    from unittest.mock import patch

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    failures = ["tests/cloud/test_progress_auditor.py::test_a"]
    collected_ids = list(failures) + [
        "tests/cloud/test_progress_auditor.py::test_ok"
    ]
    recompiled = _recompile_legacy_narrow_recheck_command(
        LEGACY_COMMAND, [SEL_A, SEL_B]
    )
    # Pass 1 (pre-dispatch): capture the durable pre-envelope artifact.
    fake1 = _result(
        exit_code=1,
        failures=list(failures),
        collected_ids=list(collected_ids),
        collected=len(collected_ids),
        code_hash=_tree_code_hash(project_dir),
        command=recompiled,
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake1,
    ), patch(
        "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
        return_value={"event_id": "ev"},
    ):
        _run_batch_validation_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            batch_task_ids=["T1"],
            state=state,
            admission=True,
        )
    env_artifact = _pre_envelope_artifact_path(plan_dir / "verification", "VJ12")
    assert env_artifact.exists()
    stored_env = __import__("json").loads(env_artifact.read_text(encoding="utf-8"))
    assert stored_env["status"] == PRE_ENVELOPE_CAPTURED
    assert stored_env.get("worktree_digest") is not None
    # Pass 2 (post-adoption): same plan dir, durable artifact present.  The
    # suite MUST run again (the enveloped loop never reuses pre-dispatch
    # state) and the verdict must be a fresh POST_DELTA_PASSED tied to the
    # envelope's evidence hash.
    finalize_data["tasks"][0]["status"] = "done"
    envelope_record = dict(stored_env)
    fake2 = _result(
        exit_code=1,
        failures=list(failures),
        collected_ids=list(collected_ids),
        collected=len(collected_ids),
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake2,
    ) as mock_run:
        rerun = _rerun_deferred_selector_validation_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            batch_task_ids=["T1"],
            pre_dispatch_results=[envelope_record],
            payload=_accepted_task_payload(),
            state=state,
        )
    mock_run.assert_called_once()
    assert rerun[0]["status"] == POST_DELTA_PASSED
    assert rerun[0]["baseline_envelope_hash"] == envelope_record["evidence_hash"]
    # The pre-envelope artifact must NOT have been overwritten by the
    # post-task run (it is still the pre-dispatch envelope).
    after = __import__("json").loads(env_artifact.read_text(encoding="utf-8"))
    assert after["status"] == PRE_ENVELOPE_CAPTURED
    assert after.get("admission") == "pre_dispatch_delta_envelope"