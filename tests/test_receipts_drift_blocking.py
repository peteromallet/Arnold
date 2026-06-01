from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import megaplan
import megaplan.execute.aggregation
import megaplan.execute.batch
import megaplan.execute.core
import megaplan.workers
from megaplan._core import compute_global_batches
from megaplan.workers import WorkerResult
from tests.conftest import _make_plan_fixture_with_robustness, read_json


def _advance_to_finalized(fixture: Any) -> None:
    args = fixture.make_args(plan=fixture.plan_name)
    megaplan.handle_plan(fixture.root, args)
    megaplan.handle_critique(fixture.root, args)
    megaplan.handle_override(
        fixture.root,
        fixture.make_args(
            plan=fixture.plan_name,
            override_action="force-proceed",
            reason="test",
        ),
    )
    megaplan.handle_finalize(fixture.root, args)


def _write_drift_fixture(project_dir: Path) -> None:
    (project_dir / "a.py").write_text("print('claimed')\n", encoding="utf-8")
    (project_dir / "b.py").write_text(
        "".join(f"print({index})\n" for index in range(30)),
        encoding="utf-8",
    )


def _execute_payload(finalize_data: dict[str, Any]) -> dict[str, Any]:
    task_updates = []
    for task in finalize_data.get("tasks", []):
        task_updates.append(
            {
                "task_id": task["id"],
                "status": "done",
                "executor_notes": "Completed the requested task and verified the claimed file.",
                "files_changed": ["a.py"],
                "commands_run": ["pytest -q"],
            }
        )
    sense_check_acknowledgments = []
    for sense_check in finalize_data.get("sense_checks", []):
        sense_check_acknowledgments.append(
            {
                "sense_check_id": sense_check["id"],
                "executor_note": "Confirmed the requested task evidence.",
            }
        )
    return {
        "output": "Execution updated the claimed file only.",
        "files_changed": ["a.py"],
        "commands_run": ["pytest -q"],
        "deviations": [],
        "task_updates": task_updates,
        "sense_check_acknowledgments": sense_check_acknowledgments,
    }


def _read_execute_receipt(plan_dir: Path) -> dict[str, Any]:
    return read_json(plan_dir / "step_receipt_execute_v1.json")


def _assert_audit_line(audit_dir: Path, plan_id: str) -> None:
    lines = [
        json.loads(line)
        for line in (audit_dir / "receipts.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    matching = [
        receipt
        for receipt in lines
        if receipt.get("plan_id") == plan_id and receipt.get("phase") == "execute"
    ]
    assert matching
    assert matching[-1]["scope_drift_severity"] == "high"


# standard(=full) now ALSO surfaces unclaimed files as a recoverable blocker
# (DEFECT 3), but via the distinct ``scope_drift_unclaimed_files`` reason
# rather than the hardened-only ``scope_drift_severity=high`` reason. robust
# (=thorough) keeps the high-severity gate.
@pytest.mark.parametrize("execute_mode", ["auto", "batch"])
@pytest.mark.parametrize(
    ("robustness", "should_block"),
    [("standard", True), ("robust", True)],
)
def test_high_scope_drift_blocks_only_hardened_robustness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    robustness: str,
    should_block: bool,
    execute_mode: str,
) -> None:
    audit_dir = tmp_path / "audit"
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(audit_dir))
    fixture = _make_plan_fixture_with_robustness(
        tmp_path,
        monkeypatch,
        robustness=robustness,
    )
    _advance_to_finalized(fixture)

    finalize_data = read_json(fixture.plan_dir / "finalize.json")
    _write_drift_fixture(fixture.project_dir)

    payload = _execute_payload(finalize_data)

    def drift_worker(*args: object, **kwargs: object) -> tuple[WorkerResult, str, str, bool]:
        del args, kwargs
        return (
            WorkerResult(
                payload=payload,
                raw_output=json.dumps(payload),
                duration_ms=12,
                cost_usd=0.05,
                session_id=f"{execute_mode}-{robustness}",
            ),
            "codex",
            "persistent",
            False,
        )

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", drift_worker)
    _drift_snapshot = lambda *_: ({"a.py": "claimed-hash", "b.py": "unclaimed-hash"}, None)
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_capture_git_status_snapshot",
        _drift_snapshot,
    )
    monkeypatch.setattr(
        megaplan.execute.aggregation,
        "_capture_git_status_snapshot",
        _drift_snapshot,
    )

    args_kwargs: dict[str, Any] = {
        "plan": fixture.plan_name,
        "confirm_destructive": True,
        "user_approved": True,
    }
    if execute_mode == "batch":
        batches_total = len(compute_global_batches(finalize_data))
        args_kwargs["batch"] = batches_total

    response = megaplan.handle_execute(fixture.root, fixture.make_args(**args_kwargs))

    receipt = _read_execute_receipt(fixture.plan_dir)
    assert receipt["scope_drift_severity"] == "high"
    assert receipt["metrics"]["loc_added_outside_claimed"] == 30
    assert receipt["metrics"]["scope_drift_files_added"] == 1
    _assert_audit_line(audit_dir, fixture.plan_name)

    assert "[scope_drift=high]" in response["summary"]
    # robust(=thorough) blocks via the hardened high-severity reason; standard
    # (=full) blocks via the unclaimed-files surfacing reason (DEFECT 3).
    drift_blocker = (
        "scope_drift_severity=high"
        if robustness == "robust"
        else "scope_drift_unclaimed_files"
    )
    assert should_block
    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert drift_blocker in response["summary"]
    assert "b.py" in response["summary"]


def _drift(severity: str, files_added: list[str], loc: int):
    from megaplan.receipts.drift import ScopeDriftReport

    return ScopeDriftReport(
        files_added=files_added,
        files_missing=[],
        loc_added=loc,
        loc_removed=0,
        loc_added_outside_claimed=loc,
        severity=severity,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("robustness", "expect_blocker"),
    [
        ("bare", False),
        ("light", False),
        ("full", True),       # DEFECT 3: surface unclaimed files on full
        ("thorough", True),   # unchanged hardened gate
        ("extreme", True),    # unchanged hardened gate
    ],
)
def test_append_scope_drift_blocker_surfaces_unclaimed_files_on_full(
    robustness: str,
    expect_blocker: bool,
) -> None:
    """DEFECT 3: high-severity unclaimed files surface a recoverable blocker on
    `full` (and the hardened levels), but stay quiet on `light`/`bare`."""
    state = {"config": {"robustness": robustness}}
    blocking_reasons: list[str] = []
    megaplan.execute.aggregation._append_scope_drift_blocker(
        blocking_reasons,
        state,  # type: ignore[arg-type]
        _drift("high", ["pack.yaml"], 42),
    )
    if expect_blocker:
        assert len(blocking_reasons) == 1
        assert "pack.yaml" in blocking_reasons[0]
        if robustness == "full":
            assert "scope_drift_unclaimed_files" in blocking_reasons[0]
            assert "not claimed by any task" in blocking_reasons[0]
        else:
            assert "scope_drift_severity=high" in blocking_reasons[0]
    else:
        assert blocking_reasons == []


def test_append_scope_drift_blocker_quiet_on_full_for_low_severity() -> None:
    """Benign low-severity churn (e.g. a directory marker) stays quiet on full."""
    state = {"config": {"robustness": "full"}}
    blocking_reasons: list[str] = []
    megaplan.execute.aggregation._append_scope_drift_blocker(
        blocking_reasons,
        state,  # type: ignore[arg-type]
        _drift("low", ["newpkg/"], 0),
    )
    assert blocking_reasons == []
