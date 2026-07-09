"""Closeout-blocking tests for North Star actions in review and finalize.

Proves:
* Review blocks the review→done transition when carried blocking North Star
  actions are unresolved in the latest revise metadata.
* Review allows the review→done transition when all blocking actions are
  concretely resolved.
* Finalize rejects when carried blocking actions are unresolved (fail-closed).
* Finalize allows when no blocking actions are carried or all are resolved.
* Absent/malformed metadata in either phase is treated as all-unresolved
  (fail-closed, SD1).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.north_star_actions import (
    SEVERITY_BLOCKING,
    SEVERITY_SOURCE_SCHEMA,
    NORTH_STAR_DANGEROUS_CATEGORIES,
    normalize_north_star_action,
)
from arnold_pipelines.megaplan.handlers.review import (
    _review_north_star_closeout_blockers,
)
from arnold_pipelines.megaplan.handlers.finalize import (
    _reject_finalize_unresolved_north_star,
)
from arnold_pipelines.megaplan.types import CliError

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_DANGEROUS_CAT = sorted(NORTH_STAR_DANGEROUS_CATEGORIES)[0]


def _blocking_action(**overrides: Any) -> dict[str, Any]:
    """Return a normalized blocking action (dangerous category, schema-authoritative)."""
    action: dict[str, Any] = {
        "id": "ns-block-001",
        "concern": "Plan is missing a rollback mechanism.",
        "category": _DANGEROUS_CAT,
        "action_type": "change_plan",
        "severity": SEVERITY_BLOCKING,
        "severity_source": SEVERITY_SOURCE_SCHEMA,
        "evidence": "Step 3 has no undo path.",
    }
    action.update(overrides)
    return normalize_north_star_action(action)


def _addressed_record(**overrides: Any) -> dict[str, Any]:
    """Return a well-formed addressed record for ns-block-001."""
    record: dict[str, Any] = {
        "action_id": "ns-block-001",
        "resolution": "addressed",
        "reason": "Added rollback step in plan_v2.md.",
        "plan_refs": ["plan_v2.md"],
        "action_type": "change_plan",
    }
    record.update(overrides)
    return record


def _min_state(**overrides: Any) -> dict[str, Any]:
    """Return a minimal PlanState-like dict for handlers."""
    state: dict[str, Any] = {
        "iteration": 2,
        "current_state": "reviewed",
        "name": "test-plan",
        "config": {"project_dir": "/tmp/test-project"},
        "meta": {},
        "history": [],
        "plan_versions": [
            {"version": 1, "file": "plan_v1.md", "hash": "abc", "timestamp": "2026-01-01"},
            {"version": 2, "file": "plan_v2.md", "hash": "def", "timestamp": "2026-01-02"},
        ],
    }
    state.update(overrides)
    return state


def _write_gate_carry(plan_dir: Path, actions: list[dict[str, Any]]) -> None:
    """Write gate_carry.json with north_star_actions."""
    carry = {"north_star_actions": actions, "iteration": 1}
    (plan_dir / "gate_carry.json").write_text(json.dumps(carry), encoding="utf-8")


def _write_revise_meta(plan_dir: Path, state: dict[str, Any], addressed: list[dict[str, Any]]) -> None:
    """Write the latest revise meta file with north_star_actions_addressed."""
    from arnold_pipelines.megaplan._core import latest_plan_meta_path
    meta_path = latest_plan_meta_path(plan_dir, state)
    meta = {
        "changes_summary": "Test changes.",
        "flags_addressed": [],
        "questions": [],
        "success_criteria": [],
        "assumptions": [],
        "delta_from_previous_percent": 10,
        "north_star_actions_addressed": addressed,
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Tests: review closeout blocking
# --------------------------------------------------------------------------- #


class TestReviewNorthStarCloseoutBlockers:
    """Prove _review_north_star_closeout_blockers correctly denies or allows
    the review→done transition based on North Star action resolution."""

    # --- No carried blockers ---

    def test_no_carried_blockers_returns_empty(self) -> None:
        """When no blocking North Star actions are carried, no denial reasons."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            _write_gate_carry(plan_dir, [])
            reasons = _review_north_star_closeout_blockers(plan_dir, state)
            assert reasons == []

    def test_only_advisory_carried_returns_empty(self) -> None:
        """Advisory actions are never blocking; no denial reasons."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            advisory = normalize_north_star_action({
                "id": "ns-adv",
                "concern": "Minor nitpick.",
                "category": "completeness",
                "action_type": "change_plan",
                "severity": "advisory",
                "severity_source": "worker",
                "evidence": "Nitpick detail.",
            })
            _write_gate_carry(plan_dir, [advisory])
            reasons = _review_north_star_closeout_blockers(plan_dir, state)
            assert reasons == []

    # --- All resolved ---

    def test_all_blocking_resolved_returns_empty(self) -> None:
        """When every carried blocking action is concretely resolved, no denial."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [_blocking_action(id="ns-b1", action_type="add_gate")]
            _write_gate_carry(plan_dir, carried)
            _write_revise_meta(plan_dir, state, [
                _addressed_record(action_id="ns-b1", plan_refs=["gates.md"], action_type="add_gate"),
            ])
            reasons = _review_north_star_closeout_blockers(plan_dir, state)
            assert reasons == []

    def test_multiple_blocking_all_resolved(self) -> None:
        """Multiple blocking actions, all resolved — no denial."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [
                _blocking_action(id="ns-1", action_type="change_plan"),
                _blocking_action(id="ns-2", action_type="add_scenario"),
            ]
            _write_gate_carry(plan_dir, carried)
            _write_revise_meta(plan_dir, state, [
                _addressed_record(action_id="ns-1", plan_refs=["plan_v2.md"], action_type="change_plan"),
                _addressed_record(action_id="ns-2", plan_refs=["scenarios/s1.md"], action_type="add_scenario"),
            ])
            reasons = _review_north_star_closeout_blockers(plan_dir, state)
            assert reasons == []

    # --- Unresolved: omitted ---

    def test_blocking_action_omitted_returns_denial_reasons(self) -> None:
        """A carried blocking action with no addressed record yields denial."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [_blocking_action(id="ns-orphan", action_type="add_checker")]
            _write_gate_carry(plan_dir, carried)
            _write_revise_meta(plan_dir, state, [
                _addressed_record(action_id="ns-other", plan_refs=["plan.md"]),
            ])
            reasons = _review_north_star_closeout_blockers(plan_dir, state)
            assert len(reasons) == 1
            reason_text = reasons[0]
            assert "ns-orphan" in reason_text
            assert "omitted" in reason_text
            assert "unresolved blocking North Star action" in reason_text

    # --- Unresolved: prose_only ---

    def test_blocking_action_prose_only_returns_denial_reasons(self) -> None:
        """An addressed record with no concrete plan_refs yields denial."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [_blocking_action(id="ns-prose", action_type="change_plan")]
            _write_gate_carry(plan_dir, carried)
            _write_revise_meta(plan_dir, state, [
                _addressed_record(
                    action_id="ns-prose",
                    plan_refs=[],  # prose-only
                ),
            ])
            reasons = _review_north_star_closeout_blockers(plan_dir, state)
            assert len(reasons) == 1
            assert "ns-prose" in reasons[0]
            assert "prose_only" in reasons[0]

    # --- Unresolved: action_type_mismatch ---

    def test_blocking_action_type_mismatch_returns_denial_reasons(self) -> None:
        """Addressed record with different action_type yields denial."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [_blocking_action(id="ns-mismatch", action_type="add_gate")]
            _write_gate_carry(plan_dir, carried)
            _write_revise_meta(plan_dir, state, [
                _addressed_record(
                    action_id="ns-mismatch",
                    plan_refs=["plan.md"],
                    action_type="change_plan",  # wrong
                ),
            ])
            reasons = _review_north_star_closeout_blockers(plan_dir, state)
            assert len(reasons) == 1
            assert "ns-mismatch" in reasons[0]
            assert "action_type_mismatch" in reasons[0]

    # --- Mixed: some resolved, some unresolved ---

    def test_mixed_resolution_only_unresolved_reported(self) -> None:
        """When some are resolved and some are not, only unresolved yield denial."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [
                _blocking_action(id="ns-ok", action_type="change_plan"),
                _blocking_action(id="ns-bad", action_type="add_gate"),
            ]
            _write_gate_carry(plan_dir, carried)
            _write_revise_meta(plan_dir, state, [
                _addressed_record(action_id="ns-ok", plan_refs=["plan_v2.md"], action_type="change_plan"),
                _addressed_record(action_id="ns-bad", plan_refs=[], action_type="add_gate"),
            ])
            reasons = _review_north_star_closeout_blockers(plan_dir, state)
            assert len(reasons) == 1
            assert "ns-bad" in reasons[0]
            assert "ns-ok" not in reasons[0]

    # --- Fail-closed: absent metadata ---

    def test_no_revise_meta_fail_closed(self) -> None:
        """When no revise meta file exists, every carried blocker is unresolved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [
                _blocking_action(id="ns-1"),
                _blocking_action(id="ns-2"),
            ]
            _write_gate_carry(plan_dir, carried)
            # No revise meta written → fail-closed
            reasons = _review_north_star_closeout_blockers(plan_dir, state)
            assert len(reasons) == 2

    def test_malformed_revise_meta_fail_closed(self) -> None:
        """When revise meta is corrupt JSON, every carried blocker is unresolved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [_blocking_action(id="ns-corrupt")]
            _write_gate_carry(plan_dir, carried)
            # Write corrupt meta
            from arnold_pipelines.megaplan._core import latest_plan_meta_path
            meta_path = latest_plan_meta_path(plan_dir, state)
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta_path.write_text("not valid json {{{", encoding="utf-8")
            reasons = _review_north_star_closeout_blockers(plan_dir, state)
            assert len(reasons) == 1

    def test_revise_meta_missing_addressed_field_fail_closed(self) -> None:
        """When revise meta exists but has no north_star_actions_addressed, fail-closed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [_blocking_action(id="ns-missing-field")]
            _write_gate_carry(plan_dir, carried)
            from arnold_pipelines.megaplan._core import latest_plan_meta_path
            meta_path = latest_plan_meta_path(plan_dir, state)
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta = {
                "changes_summary": "No addressed field.",
                "flags_addressed": [],
                "delta_from_previous_percent": 5,
            }
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            reasons = _review_north_star_closeout_blockers(plan_dir, state)
            assert len(reasons) == 1

    def test_gate_carry_fallback_to_gate_json(self) -> None:
        """When gate_carry.json is absent, falls back to gate.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [_blocking_action(id="ns-gate-fallback", action_type="change_plan")]
            gate_data = {"north_star_actions": carried}
            (plan_dir / "gate.json").write_text(json.dumps(gate_data), encoding="utf-8")
            _write_revise_meta(plan_dir, state, [
                _addressed_record(action_id="ns-gate-fallback", plan_refs=["plan_v2.md"]),
            ])
            reasons = _review_north_star_closeout_blockers(plan_dir, state)
            assert reasons == []


# --------------------------------------------------------------------------- #
# Tests: finalize closeout blocking
# --------------------------------------------------------------------------- #


class TestFinalizeRejectsUnresolved:
    """Prove _reject_finalize_unresolved_north_star blocks finalize when
    carried blocking actions are unresolved."""

    def test_all_resolved_allows_finalize(self) -> None:
        """When all blocking actions are resolved, no CliError is raised."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [_blocking_action(id="ns-ok", action_type="change_plan")]
            _write_gate_carry(plan_dir, carried)
            _write_revise_meta(plan_dir, state, [
                _addressed_record(action_id="ns-ok", plan_refs=["plan_v2.md"]),
            ])
            # Should not raise
            _reject_finalize_unresolved_north_star(plan_dir, state)

    def test_no_carried_blockers_allows_finalize(self) -> None:
        """When no blocking actions are carried, finalize proceeds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            _write_gate_carry(plan_dir, [])
            _reject_finalize_unresolved_north_star(plan_dir, state)

    def test_only_advisory_allows_finalize(self) -> None:
        """Advisory-only carried actions do not block finalize."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            advisory = normalize_north_star_action({
                "id": "ns-adv",
                "concern": "Style suggestion.",
                "category": "conventions",
                "action_type": "change_plan",
                "severity": "advisory",
                "severity_source": "worker",
                "evidence": "Style guide says otherwise.",
            })
            _write_gate_carry(plan_dir, [advisory])
            _reject_finalize_unresolved_north_star(plan_dir, state)

    def test_omitted_action_raises_cli_error(self) -> None:
        """A carried blocking action omitted from addressed raises CliError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [_blocking_action(id="ns-orphan", action_type="add_gate")]
            _write_gate_carry(plan_dir, carried)
            _write_revise_meta(plan_dir, state, [
                _addressed_record(action_id="ns-other", plan_refs=["plan.md"]),
            ])
            with pytest.raises(CliError) as exc_info:
                _reject_finalize_unresolved_north_star(plan_dir, state)
            assert exc_info.value.code == "north_star_finalize_unresolved_blocking"
            assert "ns-orphan" in str(exc_info.value)
            assert "omitted" in str(exc_info.value)

    def test_prose_only_action_raises_cli_error(self) -> None:
        """Prose-only addressed record raises CliError in finalize."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [_blocking_action(id="ns-prose", action_type="change_plan")]
            _write_gate_carry(plan_dir, carried)
            _write_revise_meta(plan_dir, state, [
                _addressed_record(action_id="ns-prose", plan_refs=[]),
            ])
            with pytest.raises(CliError) as exc_info:
                _reject_finalize_unresolved_north_star(plan_dir, state)
            assert exc_info.value.code == "north_star_finalize_unresolved_blocking"
            assert "prose_only" in str(exc_info.value)

    def test_action_type_mismatch_raises_cli_error(self) -> None:
        """Mismatched action_type in addressed raises CliError in finalize."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [_blocking_action(id="ns-mis", action_type="add_scenario")]
            _write_gate_carry(plan_dir, carried)
            _write_revise_meta(plan_dir, state, [
                _addressed_record(
                    action_id="ns-mis",
                    plan_refs=["plan.md"],
                    action_type="change_plan",
                ),
            ])
            with pytest.raises(CliError) as exc_info:
                _reject_finalize_unresolved_north_star(plan_dir, state)
            assert exc_info.value.code == "north_star_finalize_unresolved_blocking"
            assert "action_type_mismatch" in str(exc_info.value)

    def test_no_revise_meta_fail_closed_raises(self) -> None:
        """Absent revise meta → all unresolved → finalize raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [
                _blocking_action(id="ns-1"),
                _blocking_action(id="ns-2"),
            ]
            _write_gate_carry(plan_dir, carried)
            # No meta file
            with pytest.raises(CliError) as exc_info:
                _reject_finalize_unresolved_north_star(plan_dir, state)
            assert "2 carried blocking" in str(exc_info.value)

    def test_corrupt_revise_meta_fail_closed_raises(self) -> None:
        """Corrupt revise meta → all unresolved → finalize raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [_blocking_action(id="ns-corrupt")]
            _write_gate_carry(plan_dir, carried)
            from arnold_pipelines.megaplan._core import latest_plan_meta_path
            meta_path = latest_plan_meta_path(plan_dir, state)
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta_path.write_text("{{{bad json", encoding="utf-8")
            with pytest.raises(CliError):
                _reject_finalize_unresolved_north_star(plan_dir, state)

    def test_gate_carry_fallback_allows_finalize(self) -> None:
        """When gate_carry.json is absent but gate.json has resolved actions, finalize allows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [_blocking_action(id="ns-gf", action_type="change_plan")]
            (plan_dir / "gate.json").write_text(
                json.dumps({"north_star_actions": carried}), encoding="utf-8"
            )
            _write_revise_meta(plan_dir, state, [
                _addressed_record(action_id="ns-gf", plan_refs=["plan_v2.md"]),
            ])
            # Should not raise
            _reject_finalize_unresolved_north_star(plan_dir, state)

    def test_multiple_unresolved_error_message_includes_all_ids(self) -> None:
        """Multiple unresolved actions all appear in the CliError message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            carried = [
                _blocking_action(id="ns-a", action_type="change_plan"),
                _blocking_action(id="ns-b", action_type="add_gate"),
                _blocking_action(id="ns-c", action_type="add_checker"),
            ]
            _write_gate_carry(plan_dir, carried)
            _write_revise_meta(plan_dir, state, [
                _addressed_record(action_id="ns-a", plan_refs=["plan.md"]),
                # ns-b and ns-c omitted
            ])
            with pytest.raises(CliError) as exc_info:
                _reject_finalize_unresolved_north_star(plan_dir, state)
            error_text = str(exc_info.value)
            assert "ns-b" in error_text
            assert "ns-c" in error_text
            assert "ns-a" not in error_text  # resolved
            assert "2 carried blocking" in error_text
