"""Kind guard for the baseline-unavailable deferral (m3 T4/T6 anomaly).

Regression for the astrid-first m3 execute anomaly: T4 (kind=code, carrying
the generic "introduce no new failures vs the recorded baseline" boilerplate
in its description) was mislabeled ``skipped`` by
``_defer_baseline_unavailable_checkpoints`` with no authority/envelope
evidence, because ``_is_baseline_dependent_verification_task`` matched the
description marker alone. Implementation tasks must NEVER be deferrable by
the baseline-unavailable disposition; only verification-family tasks
(audit/proof/verification) may be.
"""

from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.execute.batch import (
    _BASELINE_VERIFICATION_MARKER,
    _defer_baseline_unavailable_checkpoints,
    _is_baseline_dependent_verification_task,
    baseline_unavailable_checkpoint_ids,
)


def _task(task_id: str, kind: str, *, description: str | None = None) -> dict:
    return {
        "id": task_id,
        "kind": kind,
        "description": (
            description
            if description is not None
            else f"Task {task_id}: {_BASELINE_VERIFICATION_MARKER}."
        ),
        "status": "pending",
        "depends_on": [],
    }


class TestKindGuard:
    """The matcher must reject implementation tasks before the marker check."""

    def test_code_task_with_marker_is_not_baseline_dependent(self) -> None:
        # T4/T6 shape from the m3 plan: kind=code, boilerplate marker present.
        assert _is_baseline_dependent_verification_task(
            _task("T4", "code")
        ) is False
        assert _is_baseline_dependent_verification_task(
            _task("T6", "code")
        ) is False

    def test_audit_task_with_marker_is_baseline_dependent(self) -> None:
        # T2_proof shape from the m3 plan: kind=audit.
        assert _is_baseline_dependent_verification_task(
            _task("T2_proof", "audit")
        ) is True

    def test_proof_and_verification_kinds_are_baseline_dependent(self) -> None:
        assert _is_baseline_dependent_verification_task(
            _task("X_proof", "proof")
        ) is True
        assert _is_baseline_dependent_verification_task(
            _task("X_verification", "verification")
        ) is True

    def test_test_kind_with_marker_is_not_baseline_dependent(self) -> None:
        assert _is_baseline_dependent_verification_task(
            _task("T16", "test")
        ) is False

    def test_marker_alone_without_verification_kind_is_never_enough(
        self,
    ) -> None:
        for kind in ("code", "test", "docs", "research", "ops"):
            assert _is_baseline_dependent_verification_task(
                _task(f"T_{kind}", kind)
            ) is False, f"kind={kind} must not be deferrable"

    def test_missing_kind_is_not_baseline_dependent(self) -> None:
        task = _task("T_no_kind", "code")
        task.pop("kind")
        assert _is_baseline_dependent_verification_task(task) is False

    def test_non_string_kind_is_not_baseline_dependent(self) -> None:
        assert _is_baseline_dependent_verification_task(
            {**_task("T_nk", "code"), "kind": None}
        ) is False

    def test_missing_description_is_not_baseline_dependent(self) -> None:
        task = _task("T_audit", "audit")
        task.pop("description")
        assert _is_baseline_dependent_verification_task(task) is False

    def test_verification_kind_without_marker_is_not_baseline_dependent(
        self,
    ) -> None:
        task = _task(
            "T_audit_other",
            "audit",
            description="Verify the implementation in T2 by running tests.",
        )
        assert _is_baseline_dependent_verification_task(task) is False


class TestDeferralIntegration:
    """The deferral path must skip only verification-kind tasks."""

    def _finalize(self, tasks: list[dict]) -> dict:
        return {
            "baseline_test_failures": None,
            "tasks": tasks,
            "sense_checks": [],
        }

    def test_checkpoint_ids_only_include_verification_kinds(self) -> None:
        tasks = [
            _task("T4", "code"),
            _task("T6", "code"),
            _task("T2_proof", "audit"),
        ]
        blocked = baseline_unavailable_checkpoint_ids(
            self._finalize(tasks), ["T4", "T6", "T2_proof"]
        )
        assert blocked == {"T2_proof"}

    def test_defer_leaves_code_tasks_pending_and_defers_only_audit(
        self,
    ) -> None:
        tasks = [
            _task("T4", "code"),
            _task("T6", "code"),
            _task("T2_proof", "audit"),
        ]
        deferred_ids, _acks = _defer_baseline_unavailable_checkpoints(
            self._finalize(tasks)
        )
        assert deferred_ids == ["T2_proof"]
        by_id = {t["id"]: t for t in tasks}
        assert by_id["T2_proof"]["status"] == "skipped"
        assert by_id["T2_proof"]["reviewer_verdict"] == (
            "deferred_baseline_unavailable"
        )
        # Implementation tasks must remain actionable pending work.
        assert by_id["T4"]["status"] == "pending"
        assert by_id["T6"]["status"] == "pending"

    def test_baseline_present_means_no_deferral_at_all(self) -> None:
        tasks = [_task("T2_proof", "audit")]
        finalize = self._finalize(tasks)
        finalize["baseline_test_failures"] = {
            "failing": [],
            "collected": 104,
        }
        deferred_ids, _acks = _defer_baseline_unavailable_checkpoints(
            finalize
        )
        assert deferred_ids == []
        assert tasks[0]["status"] == "pending"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
