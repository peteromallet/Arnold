"""Regression tests for evidence-gated test-budget debt acceptance (D2).

Occurrence 927ad612eda8: m5 task T28's declared narrow_tests selection is
parametrized so wide (tests/cloud/test_progress_auditor.py ~225 cases, ~217s
green run) that it can NEVER complete inside ``max_seconds=120``.  The merge
budget gate therefore blocks it forever, and execute wedges in
``blocked_by_quality`` on every resume.

Fix: after the final deferred sweep, a task whose ONLY typed violation is
``max_seconds_exceeded`` (all runs used admitted selectors + wrappers, run
count within ``max_runs``), that has ACCEPTED kernel authority, exactly one
matching narrow_recheck job with admitted selectors, and a binding-valid
CURRENT-worktree strict pass artifact, is promoted to ``done`` with a durable
``accepted_with_debt`` record + receipt.  Every other violation shape, missing
authority, stale digest, widened selector, or genuine strict failure stays
blocked — never laundered.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.execute.batch import (
    _accept_strictly_verified_test_budget_debt,
    _pre_envelope_artifact_path,
    _current_worktree_digest,
)


def _budget_debt_fixture(tmp_path: Path) -> tuple[Path, Path, dict]:
    """A finalized task blocked ONLY on cumulative max_seconds + a strict pass."""
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    selector = "tests/cloud/test_progress_auditor.py"
    sel_path = project_dir / selector
    sel_path.parent.mkdir(parents=True, exist_ok=True)
    sel_path.write_text("def test_ok(): pass\n", encoding="utf-8")
    finalize_data: dict = {
        "task_contract_version": 2,
        "tasks": [
            {
                "id": "T28",
                "status": "blocked",
                "narrow_tests": {
                    "selectors": [selector],
                    "max_seconds": 120,
                    "max_runs": 2,
                },
                "task_test_budget_exhausted": (
                    "task_test_budget_exhausted: declared test timeout total "
                    "420s exceeds max_seconds=120"
                ),
                "task_test_budget_violations": [
                    {
                        "kind": "max_seconds_exceeded",
                        "declared_total_seconds": 420,
                        "max_seconds": 120,
                    }
                ],
                "authority_validation": {"outcome": "accepted"},
            }
        ],
        "validation_jobs": [
            {
                "id": "VJ30",
                "kind": "narrow_recheck",
                "command": f"pytest {selector} --tb=short -q",
                "selectors": [selector],
                "max_seconds": 120,
                "timeout_seconds": 120,
                "task_id": "T28",
                "mutates": False,
                "writes_files": False,
                "expected_exit_codes": [0],
            }
        ],
    }
    return plan_dir, project_dir, finalize_data


def _write_strict_pass(
    plan_dir: Path, project_dir: Path, *, job_id: str = "VJ30", digest: str | None = None
) -> str:
    """Persist a binding-valid strict pass artifact for a job."""
    verification_dir = plan_dir / "verification"
    verification_dir.mkdir(parents=True, exist_ok=True)
    selector = "tests/cloud/test_progress_auditor.py"
    record = {
        "job_id": job_id,
        "status": "passed",
        "exit_code": 0,
        "selectors": [selector],
        "failures": [],
        "timeout_reason": None,
        "command": f"pytest {selector} --tb=short -q --tb=no --no-header -rA",
        "worktree_digest": digest or _current_worktree_digest(project_dir),
        "collected": 1,
        "collected_ids": [f"{selector}::test_ok"],
        "evidence_hash": "sha256:strict-pass-evidence",
    }
    artifact = verification_dir / f"validation_{job_id}_run.json"
    artifact.write_text(json.dumps(record), encoding="utf-8")
    return str(artifact)


def _accepted_payload() -> dict:
    """Minimal accepted-envelope payload mirroring _accepted_task_payload."""
    from arnold_pipelines.megaplan.authority.batch_scope import RESULT_ENVELOPES_KEY
    from arnold_pipelines.megaplan.authority.binding import (
        DispatchIdentity,
        TASK_RESULT_CAPABILITY,
    )
    from arnold_pipelines.megaplan.execute.batch import _task_result_envelope

    entry: dict = {
        "task_id": "T28",
        "status": "done",
        "executor_notes": "full declared selection ran green once",
        "files_changed": ["tests/cloud/test_progress_auditor.py"],
        "commands_run": [
            "timeout 120 python3 -m pytest tests/cloud/test_progress_auditor.py -q",
            "timeout 300 python3 -m pytest tests/cloud/test_progress_auditor.py -q",
        ],
    }
    identity = DispatchIdentity.create(
        dispatch_id="dispatch-vj30",
        run_id="run-vj30",
        run_revision="revision-vj30",
        coordinator_attempt_id="coordinator-vj30",
        fence_token=11,
        subject_ids=("T28",),
        capabilities=(TASK_RESULT_CAPABILITY,),
        prerequisite_digest="prereq-vj30",
        worker_id="worker-vj30",
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


def test_budget_debt_accepted_only_with_current_strict_pass(tmp_path: Path) -> None:
    plan_dir, project_dir, finalize_data = _budget_debt_fixture(tmp_path)
    deviations: list[str] = [
        "Task T28 blocked by admitted test budget: task_test_budget_exhausted: "
        "declared test timeout total 420s exceeds max_seconds=120. Remediation: "
        "rerun pytest using exactly `timeout <N> python3 -m pytest <selector> "
        "-q`; record results separately."
    ]
    _write_strict_pass(plan_dir, project_dir)
    accepted = _accept_strictly_verified_test_budget_debt(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        payload=_accepted_payload(),
        deviations=deviations,
    )
    assert accepted == ["T28"]
    task = finalize_data["tasks"][0]
    assert task["status"] == "done"
    assert "task_test_budget_exhausted" not in task
    assert task["task_test_budget_debt"]["disposition"] == "accepted_with_debt"
    assert task["task_test_budget_debt"]["strict_evidence_hash"] == (
        "sha256:strict-pass-evidence"
    )
    receipts = list((plan_dir / "verification").glob("task_budget_acceptance_*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["disposition"] == "accepted_with_debt"
    assert receipt["task_id"] == "T28"
    # The merge-generated blocker deviation is replaced by an advisory.
    assert not any("blocked by admitted test budget" in d for d in deviations)
    assert any("accepted after current strict validation" in d for d in deviations)


def test_budget_debt_stale_digest_does_not_accept(tmp_path: Path) -> None:
    plan_dir, project_dir, finalize_data = _budget_debt_fixture(tmp_path)
    deviations: list[str] = ["Task T28 blocked by admitted test budget: stale"]
    # A strict pass bound to a DIFFERENT tree must never accept the debt.
    _write_strict_pass(
        plan_dir, project_dir, digest="sha256:some-other-tree-digest"
    )
    accepted = _accept_strictly_verified_test_budget_debt(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        payload=_accepted_payload(),
        deviations=deviations,
    )
    assert accepted == []
    assert finalize_data["tasks"][0]["status"] == "blocked"
    assert "accepted after current strict validation" not in " ".join(deviations)


def test_budget_debt_extra_violation_kind_stays_blocked(tmp_path: Path) -> None:
    plan_dir, project_dir, finalize_data = _budget_debt_fixture(tmp_path)
    # Add a run-count violation: NOT the single non-correctness case.
    finalize_data["tasks"][0]["task_test_budget_violations"].append(
        {"kind": "max_runs_exceeded", "runs": 3, "max_runs": 2}
    )
    _write_strict_pass(plan_dir, project_dir)
    accepted = _accept_strictly_verified_test_budget_debt(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        payload=_accepted_payload(),
        deviations=[],
    )
    assert accepted == []
    assert finalize_data["tasks"][0]["status"] == "blocked"


def test_budget_debt_missing_authority_stays_blocked(tmp_path: Path) -> None:
    plan_dir, project_dir, finalize_data = _budget_debt_fixture(tmp_path)
    # No accepted envelope, no row authority, and no work evidence ->
    # stays blocked.  A skipped task must never be laundered into done.
    finalize_data["tasks"][0].pop("authority_validation", None)
    _write_strict_pass(plan_dir, project_dir)
    accepted = _accept_strictly_verified_test_budget_debt(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        payload={},
        deviations=[],
    )
    assert accepted == []
    assert finalize_data["tasks"][0]["status"] == "blocked"


def test_budget_debt_prior_dispatch_work_evidence_accepts(tmp_path: Path) -> None:
    """Occurrence 927ad612eda8 live regression 10:46Z.

    A budget-killed task can NEVER produce an accepted envelope (the worker
    is forced to return blocked by the cap), so the envelope preconditions
    are unsatisfiable for exactly the case this reconciler exists for.  The
    merged row's kernel-witnessed WORK EVIDENCE (non-empty files_changed AND
    commands_run from the dispatch that did the work) plus a binding-valid
    strict pass must carry the acceptance.
    """
    plan_dir, project_dir, finalize_data = _budget_debt_fixture(tmp_path)
    task = finalize_data["tasks"][0]
    task.pop("authority_validation", None)
    task["files_changed"] = [
        "arnold_pipelines/megaplan/resident/scheduler.py",
        "tests/cloud/test_progress_auditor.py",
    ]
    task["commands_run"] = [
        "timeout 120 python3 -m pytest tests/cloud/test_progress_auditor.py -q",
    ]
    _write_strict_pass(plan_dir, project_dir)
    accepted = _accept_strictly_verified_test_budget_debt(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        payload={},  # NO accepted envelope — work evidence must carry it
        deviations=[],
    )
    assert accepted == ["T28"]
    task = finalize_data["tasks"][0]
    assert task["status"] == "done"
    assert task["task_test_budget_debt"]["disposition"] == "accepted_with_debt"
    receipts = list((plan_dir / "verification").glob("task_budget_acceptance_*.json"))
    assert len(receipts) == 1


def test_budget_debt_skipped_task_without_work_evidence_stays_blocked(
    tmp_path: Path,
) -> None:
    """A never-executed task (no files_changed/commands_run) stays blocked."""
    plan_dir, project_dir, finalize_data = _budget_debt_fixture(tmp_path)
    task = finalize_data["tasks"][0]
    task.pop("authority_validation", None)
    # No work fields: the strict pass alone must NOT launder a skip.
    _write_strict_pass(plan_dir, project_dir)
    accepted = _accept_strictly_verified_test_budget_debt(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        payload={},
        deviations=[],
    )
    assert accepted == []
    assert finalize_data["tasks"][0]["status"] == "blocked"


def test_worktree_digest_excludes_engine_owned_ledger_files(
    tmp_path: Path,
) -> None:
    """Occurrence 927ad612eda8: watchdog ledger appends must not shift the
    worktree digest (they made validation artifacts stale within minutes and
    wedged D2 strict-binding acceptance).  Real source changes must still
    shift it."""
    import subprocess

    def _git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(project_dir), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "src.py").write_text("x=1\n", encoding="utf-8")
    ledger = project_dir / ".megaplan" / "incident-ledger"
    ledger.mkdir(parents=True)
    (ledger / "events.jsonl").write_text('{"seq":1}\n', encoding="utf-8")
    (ledger / ".events.seq").write_text("1\n", encoding="utf-8")
    _git("init", "-q")
    _git("config", "user.email", "test@example.com")
    _git("config", "user.name", "test")
    _git("add", ".")
    _git("commit", "-q", "-m", "init")
    d1 = _current_worktree_digest(project_dir)
    assert d1
    # Watchdog-style ledger append must NOT change the digest.
    with open(ledger / "events.jsonl", "a", encoding="utf-8") as fh:
        fh.write('{"seq":2}\n')
    (ledger / ".events.seq").write_text("2\n", encoding="utf-8")
    assert _current_worktree_digest(project_dir) == d1
    # A real source change MUST change the digest.
    (project_dir / "src.py").write_text("x=2\n", encoding="utf-8")
    assert _current_worktree_digest(project_dir) != d1


def test_budget_debt_selector_mismatch_stays_blocked(tmp_path: Path) -> None:
    plan_dir, project_dir, finalize_data = _budget_debt_fixture(tmp_path)
    # Job selectors differ from the admitted narrow_tests selectors.
    finalize_data["validation_jobs"][0]["selectors"] = ["tests/other.py"]
    _write_strict_pass(plan_dir, project_dir)
    accepted = _accept_strictly_verified_test_budget_debt(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        payload=_accepted_payload(),
        deviations=[],
    )
    assert accepted == []
    assert finalize_data["tasks"][0]["status"] == "blocked"


def test_envelope_budget_blocked_subtracts_accepted_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Old batch artifacts retain the violation; a valid receipt must exclude it."""
    from arnold_pipelines.megaplan.execute.batch import (
        _envelope_budget_blocked_task_ids,
    )

    plan_dir, project_dir, finalize_data = _budget_debt_fixture(tmp_path)
    # Simulate an old immutable batch artifact carrying the durable block.
    batch_dir = plan_dir / "execute_batches" / "batch_17"
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / "tasks_abc.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T28",
                        "task_test_budget_exhausted": (
                            "task_test_budget_exhausted: declared test timeout "
                            "total 420s exceeds max_seconds=120"
                        ),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert _envelope_budget_blocked_task_ids(plan_dir) == {"T28"}
    # After a valid acceptance receipt, the block is subtracted.
    verification_dir = plan_dir / "verification"
    verification_dir.mkdir(parents=True, exist_ok=True)
    (verification_dir / "task_budget_acceptance_T28_abcd.json").write_text(
        json.dumps(
            {
                "task_id": "T28",
                "disposition": "accepted_with_debt",
                "strict_evidence_hash": "sha256:strict-pass-evidence",
            }
        ),
        encoding="utf-8",
    )
    assert _envelope_budget_blocked_task_ids(plan_dir) == set()