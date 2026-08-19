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
    _current_worktree_digest,
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


def test_post_delta_policy_blocked_row_is_parked_not_raised(
    tmp_path: Path,
) -> None:
    """A post-merge policy-blocked row in the delta-envelope path is parked.

    Twin of ``test_post_policy_blocked_task_cannot_release_deferred_selector``
    for the enveloped branch (batch.py ``_rerun_deferred_selector_validation_jobs``
    delta loop): a task blocked by the merge admission gate must NOT release the
    deferred selector, and the refusal is parked as a typed
    ``post_merge_policy_blocked`` / ``validation_blocked`` disposition instead of
    raising a terminal CliError — the execute coordinator can publish its
    aggregate state and a fresh compliant attempt can rerun the task.
    """
    from arnold_pipelines.megaplan.execute.batch import (
        _POST_MERGE_POLICY_BLOCKED,
        _rerun_deferred_selector_validation_jobs,
    )

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    envelope = {
        "job_id": "VJ12",
        "status": PRE_ENVELOPE_CAPTURED,
        "admission": "pre_dispatch_delta_envelope",
        "failures": [],
        "collected_ids": ["tests/cloud/test_progress_auditor.py::test_ok"],
        "selectors": [SEL_A, SEL_B],
    }
    # Post-merge policy block: the merge admission gate (e.g. test-budget
    # gate) blocked the row; an accepted envelope must not override it.
    finalize_data["tasks"][0]["status"] = "blocked"
    results = _rerun_deferred_selector_validation_jobs(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        pre_dispatch_results=[envelope],
        payload=_accepted_task_payload(),
        state=state,
    )
    # The refusal is parked as a typed validation_blocked disposition.
    assert len(results) == 1
    parked = results[0]
    assert parked["status"] == _POST_MERGE_POLICY_BLOCKED
    assert parked["disposition"] == "validation_blocked"
    assert parked["reason"] == "task_result_blocked_by_post_merge_policy"
    assert parked["task_status"] == "blocked"
    # No pass artifact is minted and the row stays blocked.
    assert not _post_delta_artifact_path(
        plan_dir / "verification", "VJ12"
    ).exists()
    assert finalize_data["tasks"][0]["status"] == "blocked"


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


def test_worktree_digest_is_content_sensitive_for_already_dirty_files(
    tmp_path: Path,
) -> None:
    """A re-edit of an ALREADY-dirty file must change the worktree digest.

    Codex ship-verdict item (20260818T2226Z): ``git status --porcelain``
    records path/status only, so re-editing a file that is already dirty
    leaves the porcelain line unchanged and a stale pre-envelope or
    POST_DELTA_PASSED could be reused after the content actually changed.
    The digest must include actual file content (diff + untracked hashes).
    """
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    subprocess_run = __import__("subprocess").run
    for argv in (
        ["git", "init", "-q", str(project_dir)],
        ["git", "-C", str(project_dir), "config", "user.email", "t@t"],
        ["git", "-C", str(project_dir), "config", "user.name", "t"],
    ):
        subprocess_run(argv, check=True, capture_output=True)
    sel = project_dir / "tests" / "cloud" / "test_progress_auditor.py"
    sel.parent.mkdir(parents=True)
    sel.write_text("def test_ok(): pass\n", encoding="utf-8")
    subprocess_run(
        ["git", "-C", str(project_dir), "add", "."],
        check=True,
        capture_output=True,
    )
    subprocess_run(
        ["git", "-C", str(project_dir), "commit", "-qm", "base"],
        check=True,
        capture_output=True,
    )
    # Dirty edit #1: digest D1.
    sel.write_text("def test_ok(): return 1\n", encoding="utf-8")
    d1 = _current_worktree_digest(project_dir)
    assert d1 is not None
    # Re-edit the SAME already-dirty path with different content: the
    # porcelain status line is identical (" M tests/..."), so a
    # path/status-only digest would NOT change.  Content-sensitive must.
    sel.write_text("def test_ok(): return 2\n", encoding="utf-8")
    d2 = _current_worktree_digest(project_dir)
    assert d2 is not None
    assert d1 != d2, (
        "worktree digest must change when an already-dirty file's content "
        "changes (path/status-only digests are launderable)"
    )
    # Untracked file addition also changes the digest.
    untracked = project_dir / "new_file.py"
    untracked.write_text("x = 1\n", encoding="utf-8")
    d3 = _current_worktree_digest(project_dir)
    assert d3 is not None and d3 != d2
    # Restoring the dirty file to HEAD content yields a different digest
    # again (tree state changed back), and a second identical run is
    # deterministic.
    sel.write_text("def test_ok(): pass\n", encoding="utf-8")
    untracked.unlink()
    d4 = _current_worktree_digest(project_dir)
    assert d4 is not None and d4 != d2 and d4 != d3
    assert _current_worktree_digest(project_dir) == d4

# ---------------------------------------------------------------------------
# Quiet-run envelope completeness (occurrence a07166d38fbc, second wave)
# ---------------------------------------------------------------------------
# The harness recompiles legacy narrow-recheck commands to
# ``pytest <selectors> --tb=short -q``.  Under ``-q`` pytest does not print
# the "collected N items" line, so suite_runner's parser leaves ``collected
# == 0`` while ``collected_ids`` (from the ``-rA`` report) and
# ``collections_parse_ok`` are complete.  The envelope predicate must accept
# the complete run via ``collected_ids``; otherwise the pre-dispatch gate
# fails a complete exit-1 run instead of capturing the envelope and deferring
# to the post-adoption delta.


def test_envelope_complete_accepts_quiet_run_without_collected_count() -> None:
    """Production -q shape: collected=0 but collected_ids complete and
    collections_parse_ok -> envelope complete (verdict deferrable)."""
    from arnold_pipelines.megaplan.execute.batch import (
        _narrow_recheck_envelope_complete,
    )

    quiet_shape = SuiteRunResult(
        run_id="run-vj12-q",
        phase="narrow_recheck",
        command=f"pytest {SEL_A} {SEL_B} --tb=short -q",
        duration=0.1,
        # Production parser leaves ``collected`` at 0 under -q even though
        # the -rA report enumerates every node id.
        collected=0,
        collected_ids=[
            "tests/cloud/test_progress_auditor.py::test_a",
            "tests/cloud/test_progress_auditor.py::test_b",
        ],
        failures=["tests/cloud/test_progress_auditor.py::test_a"],
        passes=["tests/cloud/test_progress_auditor.py::test_b"],
        status="failed",
        exit_code=1,
        raw_log_path=Path("/tmp/raw-q.log"),
        code_hash="sha256:tree",
        collections_parse_ok=True,
        collection_errors=[],
        timeout_reason=None,
    )
    assert _narrow_recheck_envelope_complete(quiet_shape) is True


def test_envelope_complete_still_fails_closed_without_collection_proof() -> None:
    """collected=0 AND collected_ids empty (collection unknown) stays
    fail-closed: never an empty envelope."""
    from arnold_pipelines.megaplan.execute.batch import (
        _narrow_recheck_envelope_complete,
    )

    unknown = SuiteRunResult(
        run_id="run-vj12-unknown",
        phase="narrow_recheck",
        command=f"pytest {SEL_A} --tb=short -q",
        duration=0.1,
        collected=0,
        collected_ids=[],
        failures=["tests/cloud/test_progress_auditor.py::test_a"],
        passes=[],
        status="failed",
        exit_code=1,
        raw_log_path=Path("/tmp/raw-unknown.log"),
        code_hash="sha256:tree",
        collections_parse_ok=False,
        collection_errors=[],
        timeout_reason=None,
    )
    assert _narrow_recheck_envelope_complete(unknown) is False


def test_pre_dispatch_quiet_run_captures_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end pre-dispatch: a COMPLETE exit-1 run whose ``collected`` is 0
    (quiet pytest shape) but whose collected_ids/parse_ok are complete is
    captured as PRE_ENVELOPE_CAPTURED and dispatch proceeds — the verdict is
    deferred to the post-adoption delta instead of failing the admission gate.
    """
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import (
        _narrow_recheck_envelope_complete,
    )

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    # Production -q shape: collected=0 (no "collected N items" line) with a
    # fully parsed -rA report.
    fake = SuiteRunResult(
        run_id="run-vj12-q",
        phase="narrow_recheck",
        command=f"pytest {SEL_A} {SEL_B} --tb=short -q",
        duration=0.1,
        collected=0,
        collected_ids=[
            "tests/cloud/test_progress_auditor.py::test_a",
            "tests/cloud/test_progress_auditor.py::test_b",
        ],
        failures=["tests/cloud/test_progress_auditor.py::test_a"],
        passes=["tests/cloud/test_progress_auditor.py::test_b"],
        status="failed",
        exit_code=1,
        raw_log_path=Path("/tmp/raw-q.log"),
        code_hash="sha256:tree",
        collections_parse_ok=True,
        collection_errors=[],
        timeout_reason=None,
    )
    assert _narrow_recheck_envelope_complete(fake) is True
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
    # Durable artifact exists for resume reuse / post-adoption delta.
    artifact = _pre_envelope_artifact_path(plan_dir / "verification", "VJ12")
    assert artifact.exists()
    stored = artifact.read_text(encoding="utf-8")
    assert PRE_ENVELOPE_CAPTURED in stored
    assert stored.count("test_a") >= 1


# ---------------------------------------------------------------------------
# Envelope reuse command normalization (occurrence a07166d38fbc, third wave)
# ---------------------------------------------------------------------------
# The stored envelope records the EXECUTED command (suite_runner rewrites it
# to ``<interpreter> -m pytest <selectors> ...`` and appends the standard
# reporting flags ``--tb=no --no-header -rA``), while the reuse gate holds
# the RECOMPILED command (bare ``pytest <selectors> ...``).  Raw string
# equality can therefore never match, so the second pre-dispatch invocation
# raised ``pre_envelope_digest_drift`` and the delta lifecycle could never
# resume after its first envelope capture.


def test_validation_commands_equivalent_accepts_both_shapes() -> None:
    """The executed form and the recompiled form are the same pytest
    invocation; legacy bare-pytest envelopes compare equal too."""
    from arnold_pipelines.megaplan.execute.batch import (
        _validation_commands_equivalent,
    )
    from arnold_pipelines.megaplan.orchestration.suite_runner import (
        _pytest_command,
    )

    recompiled = _recompile_legacy_narrow_recheck_command(
        LEGACY_COMMAND, [SEL_A, SEL_B]
    )
    executed = _pytest_command(recompiled)
    assert executed != recompiled  # the production representation difference
    assert _validation_commands_equivalent(executed, recompiled) is True
    # Legacy/test-shaped stored envelope (bare pytest, no appended flags).
    assert _validation_commands_equivalent(recompiled, recompiled) is True
    # A genuinely different selector set stays unequal (fail closed).
    other = _pytest_command(f"pytest tests/cloud/other.py --tb=short -q")
    assert _validation_commands_equivalent(other, recompiled) is False
    # Unparseable/empty stored command never matches a real one.
    assert _validation_commands_equivalent(None, recompiled) is False


def test_pre_dispatch_second_invocation_reuses_production_shaped_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A production-shaped durable pre-envelope (executed command with
    interpreter prefix + appended reporting flags) is REUSED on the second
    pre-dispatch invocation without re-capturing and without a
    ``pre_envelope_digest_drift`` refusal."""
    from unittest.mock import patch

    from arnold_pipelines.megaplan.orchestration.suite_runner import (
        _pytest_command,
    )

    plan_dir, project_dir, finalize_data = _narrow_ready_fixture(tmp_path)
    state = _make_state(project_dir)
    failures = ["tests/cloud/test_progress_auditor.py::test_a"]
    collected_ids = list(failures) + [
        "tests/cloud/test_progress_auditor.py::test_ok"
    ]
    recompiled = _recompile_legacy_narrow_recheck_command(
        LEGACY_COMMAND, [SEL_A, SEL_B]
    )
    # Production shape: the executed command is _pytest_command(recompiled).
    executed = _pytest_command(recompiled)
    fake1 = _result(
        exit_code=1,
        failures=list(failures),
        collected_ids=list(collected_ids),
        collected=0,  # quiet -q run: parser leaves the count at 0
        code_hash=_tree_code_hash(project_dir),
        command=executed,
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake1,
    ) as mock_run1, patch(
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
    mock_run1.assert_called_once()
    assert evidence[0]["status"] == PRE_ENVELOPE_CAPTURED
    env_artifact = _pre_envelope_artifact_path(plan_dir / "verification", "VJ12")
    assert env_artifact.exists()
    stored_env = __import__("json").loads(env_artifact.read_text(encoding="utf-8"))
    assert stored_env["command"] == executed

    # Pass 2: same plan dir + same tree.  The durable envelope must be reused
    # (NO second suite invocation, NO drift raise) and dispatch proceeds.
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
    ) as mock_run2, patch(
        "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
        return_value={"event_id": "ev"},
    ):
        evidence2 = _run_batch_validation_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            batch_task_ids=["T1"],
            state=state,
            admission=True,
        )
    mock_run2.assert_not_called()
    assert evidence2[0]["evidence_hash"] == stored_env["evidence_hash"]
    assert evidence2[0]["status"] == PRE_ENVELOPE_CAPTURED