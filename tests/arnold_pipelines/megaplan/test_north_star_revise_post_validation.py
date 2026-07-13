"""Post-validation and closeout-blocking tests for North Star revise.

Proves:
* Revise accepts addressed actions with concrete ``plan_refs``.
* Revise rejects prose-only blocking resolutions (no concrete ``plan_refs``).
* Revise rejects structurally mismatched blocking resolutions (wrong ``action_type``).
* Revise rejects omitted blocking actions (missing ``action_id`` link).
* Fail-closed: absent/malformed ``north_star_actions_addressed[]`` → all unresolved.
* ``_raise_north_star_revise_unresolved`` produces the expected ``CliError``.
"""

from __future__ import annotations

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
from arnold_pipelines.megaplan.orchestration.critique_runtime import (
    _revise_north_star_unresolved_actions,
    _raise_north_star_revise_unresolved,
)
from arnold_pipelines.megaplan.types import CliError

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

# Pick a stable dangerous category (must be one of the 6).
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
    """Return a minimal PlanState-like dict for error-raising helpers."""
    state: dict[str, Any] = {
        "iteration": 2,
        "current_state": "gated",
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


# --------------------------------------------------------------------------- #
# Tests: revise accepts addressed actions with concrete refs
# --------------------------------------------------------------------------- #


class TestReviseAcceptsAddressedWithConcreteRefs:
    """Prove that well-formed addressed records resolve carried blocking actions."""

    def test_single_action_single_concrete_ref_resolved(self) -> None:
        """One blocking action, one addressed record with a concrete plan_ref."""
        carried = [_blocking_action(id="ns-1")]
        addressed = [_addressed_record(action_id="ns-1", plan_refs=["plan_v2.md"])]
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=carried, addressed=addressed
        )
        assert unresolved == []

    def test_multiple_actions_all_resolved(self) -> None:
        """Multiple blocking actions, each with a matching addressed record."""
        carried = [
            _blocking_action(id="ns-1", action_type="change_plan"),
            _blocking_action(id="ns-2", action_type="add_gate"),
            _blocking_action(id="ns-3", action_type="add_checker"),
        ]
        addressed = [
            _addressed_record(
                action_id="ns-1", plan_refs=["plan.md"], action_type="change_plan"
            ),
            _addressed_record(
                action_id="ns-2", plan_refs=["gates.md"], action_type="add_gate"
            ),
            _addressed_record(
                action_id="ns-3", plan_refs=["checkers.md"], action_type="add_checker"
            ),
        ]
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=carried, addressed=addressed
        )
        assert unresolved == []

    def test_multiple_plan_refs_accepted(self) -> None:
        """A record with multiple concrete plan_refs counts as resolved."""
        carried = [_blocking_action(id="ns-multi")]
        addressed = [
            _addressed_record(
                action_id="ns-multi",
                plan_refs=["plan_v2.md", "gates.json", "scenarios/s1.md"],
                action_type="change_plan",
            )
        ]
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=carried, addressed=addressed
        )
        assert unresolved == []

    def test_extra_addressed_records_not_required(self) -> None:
        """Extra addressed records for non-blocking actions are fine."""
        carried = [_blocking_action(id="ns-b")]
        addressed = [
            _addressed_record(action_id="ns-b", plan_refs=["p.md"]),
            _addressed_record(action_id="ns-adv", plan_refs=["other.md"]),
        ]
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=carried, addressed=addressed
        )
        assert unresolved == []


# --------------------------------------------------------------------------- #
# Tests: revise rejects prose-only blocking resolutions
# --------------------------------------------------------------------------- #


class TestReviseRejectsProseOnly:
    """Prove that addressed records without concrete plan_refs do NOT resolve."""

    def test_addressed_with_empty_plan_refs_marks_unresolved(self) -> None:
        """Empty plan_refs list => prose_only."""
        carried = [_blocking_action(id="ns-empty-refs")]
        addressed = [
            _addressed_record(
                action_id="ns-empty-refs",
                plan_refs=[],
            )
        ]
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=carried, addressed=addressed
        )
        assert len(unresolved) == 1
        assert unresolved[0]["id"] == "ns-empty-refs"
        assert unresolved[0]["reason"] == "prose_only"

    def test_addressed_with_only_blank_plan_refs_marks_unresolved(self) -> None:
        """Blank string plan_refs => prose_only."""
        carried = [_blocking_action(id="ns-blank-refs")]
        addressed = [
            _addressed_record(
                action_id="ns-blank-refs",
                plan_refs=["", "   "],
            )
        ]
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=carried, addressed=addressed
        )
        assert len(unresolved) == 1
        assert unresolved[0]["reason"] == "prose_only"

    def test_addressed_with_no_plan_refs_key_marks_unresolved(self) -> None:
        """No plan_refs key at all => prose_only."""
        carried = [_blocking_action(id="ns-no-key")]
        rec = _addressed_record(action_id="ns-no-key")
        rec.pop("plan_refs", None)
        addressed = [rec]
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=carried, addressed=addressed
        )
        assert len(unresolved) == 1
        assert unresolved[0]["reason"] == "prose_only"

    def test_addressed_with_where_but_no_plan_refs_still_unresolved(self) -> None:
        """A 'where' string is prose, not a concrete plan_ref."""
        carried = [_blocking_action(id="ns-where-only")]
        rec = _addressed_record(action_id="ns-where-only")
        rec.pop("plan_refs", None)
        rec["where"] = "I changed line 42 of plan_v2.md"
        addressed = [rec]
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=carried, addressed=addressed
        )
        assert len(unresolved) == 1
        assert unresolved[0]["reason"] == "prose_only"

    def test_prose_only_with_multiple_blocking_actions(self) -> None:
        """Each blocking action without concrete refs is individually reported."""
        carried = [
            _blocking_action(id="ns-1", action_type="change_plan"),
            _blocking_action(id="ns-2", action_type="add_gate"),
        ]
        addressed = [
            _addressed_record(action_id="ns-1", plan_refs=["ok.md"]),
            _addressed_record(action_id="ns-2", plan_refs=[]),
        ]
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=carried, addressed=addressed
        )
        assert len(unresolved) == 1
        assert unresolved[0]["id"] == "ns-2"
        assert unresolved[0]["reason"] == "prose_only"


# --------------------------------------------------------------------------- #
# Tests: revise rejects mismatched action_type
# --------------------------------------------------------------------------- #


class TestReviseRejectsActionTypeMismatch:
    """Prove that addressed records must echo the carried action_type exactly."""

    def test_mismatched_action_type_marks_unresolved(self) -> None:
        """Carried is change_plan, addressed is add_gate => unresolved."""
        carried = [_blocking_action(id="ns-mismatch", action_type="change_plan")]
        addressed = [
            _addressed_record(
                action_id="ns-mismatch",
                plan_refs=["plan_v2.md"],
                action_type="add_gate",
            )
        ]
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=carried, addressed=addressed
        )
        assert len(unresolved) == 1
        assert unresolved[0]["id"] == "ns-mismatch"
        assert unresolved[0]["reason"] == "action_type_mismatch"
        assert unresolved[0]["action_type"] == "change_plan"
        assert unresolved[0]["addressed_action_type"] == "add_gate"

    def test_addressed_missing_action_type_marks_unresolved(self) -> None:
        """Addressed record without action_type key (None != carried type)."""
        carried = [_blocking_action(id="ns-no-type", action_type="add_scenario")]
        rec = _addressed_record(
            action_id="ns-no-type", plan_refs=["scenario.md"]
        )
        rec.pop("action_type", None)
        addressed = [rec]
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=carried, addressed=addressed
        )
        assert len(unresolved) == 1
        assert unresolved[0]["reason"] == "action_type_mismatch"

    def test_various_mismatch_types(self) -> None:
        """Each action_type mismatch is caught regardless of concrete refs."""
        for carried_type in ["change_plan", "add_gate", "add_scenario", "add_checker", "dead_delete"]:
            for addressed_type in ["change_plan", "add_gate", "add_scenario", "add_checker", "dead_delete"]:
                if carried_type == addressed_type:
                    continue
                carried = [_blocking_action(id=f"ns-{carried_type}", action_type=carried_type)]
                addressed = [
                    _addressed_record(
                        action_id=f"ns-{carried_type}",
                        plan_refs=["plan.md"],
                        action_type=addressed_type,
                    )
                ]
                unresolved = _revise_north_star_unresolved_actions(
                    carried_blocking=carried, addressed=addressed
                )
                assert len(unresolved) == 1, (
                    f"Expected unresolved for carried={carried_type} "
                    f"vs addressed={addressed_type}"
                )
                assert unresolved[0]["reason"] == "action_type_mismatch"


# --------------------------------------------------------------------------- #
# Tests: revise rejects omitted blocking actions
# --------------------------------------------------------------------------- #


class TestReviseRejectsOmittedActions:
    """Prove that blocking actions without an addressed record are unresolved."""

    def test_blocking_action_with_no_addressed_record_omitted(self) -> None:
        """Carried blocking action not referenced in addressed at all."""
        carried = [_blocking_action(id="ns-orphan")]
        addressed = [
            _addressed_record(action_id="ns-other", plan_refs=["plan.md"])
        ]
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=carried, addressed=addressed
        )
        assert len(unresolved) == 1
        assert unresolved[0]["id"] == "ns-orphan"
        assert unresolved[0]["reason"] == "omitted"

    def test_multiple_blocking_some_omitted_some_resolved(self) -> None:
        """Mix of resolved and omitted — only omitted are reported."""
        carried = [
            _blocking_action(id="ns-resolved", action_type="add_gate"),
            _blocking_action(id="ns-orphan", action_type="change_plan"),
            _blocking_action(id="ns-orphan-2", action_type="add_checker"),
        ]
        addressed = [
            _addressed_record(
                action_id="ns-resolved", plan_refs=["gates.json"], action_type="add_gate"
            ),
        ]
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=carried, addressed=addressed
        )
        assert len(unresolved) == 2
        unresolved_ids = {u["id"] for u in unresolved}
        assert unresolved_ids == {"ns-orphan", "ns-orphan-2"}
        for u in unresolved:
            assert u["reason"] == "omitted"

    def test_empty_addressed_list_all_omitted(self) -> None:
        """Empty addressed list => all blocking actions omitted."""
        carried = [
            _blocking_action(id="ns-1"),
            _blocking_action(id="ns-2"),
        ]
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=carried, addressed=[]
        )
        assert len(unresolved) == 2
        assert all(u["reason"] == "omitted" for u in unresolved)


# --------------------------------------------------------------------------- #
# Tests: fail-closed — absent/malformed addressed metadata
# --------------------------------------------------------------------------- #


class TestReviseFailClosedAddressedMetadata:
    """Prove that absent or malformed addressed metadata → all unresolved."""

    def test_addressed_none_all_unresolved(self) -> None:
        """addressed=None (metadata absent or unreadable) → every blocker unresolved."""
        carried = [
            _blocking_action(id="ns-1"),
            _blocking_action(id="ns-2"),
            _blocking_action(id="ns-3"),
        ]
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=carried, addressed=None
        )
        assert len(unresolved) == 3
        assert all(u["reason"] == "addressed_metadata_malformed" for u in unresolved)

    def test_addressed_none_no_carried_blockers_no_unresolved(self) -> None:
        """No carried blockers + addressed=None → empty unresolved list."""
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=[], addressed=None
        )
        assert unresolved == []

    def test_addressed_none_preserves_action_ids(self) -> None:
        """addressed=None reports every blocker with its id and action_type."""
        carried = [
            _blocking_action(id="ns-a", action_type="add_gate"),
            _blocking_action(id="ns-b", action_type="add_scenario"),
        ]
        unresolved = _revise_north_star_unresolved_actions(
            carried_blocking=carried, addressed=None
        )
        ids = {u["id"] for u in unresolved}
        types = {u["action_type"] for u in unresolved}
        assert ids == {"ns-a", "ns-b"}
        assert types == {"add_gate", "add_scenario"}


# --------------------------------------------------------------------------- #
# Tests: _raise_north_star_revise_unresolved raises CliError
# --------------------------------------------------------------------------- #


class TestRaiseNorthStarReviseUnresolved:
    """Prove that _raise_north_star_revise_unresolved produces the expected CliError."""

    def test_raises_cli_error_with_correct_code(self) -> None:
        """The function raises CliError with code 'north_star_revise_unresolved_blocking'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            (plan_dir / "plan_v1.md").write_text("# Plan v1")
            (plan_dir / "plan_v2.md").write_text("# Plan v2")
            unresolved = [
                {"id": "ns-1", "action_type": "change_plan", "reason": "omitted"}
            ]
            with pytest.raises(CliError) as exc_info:
                _raise_north_star_revise_unresolved(
                    plan_dir,
                    state,
                    iteration=2,
                    unresolved=unresolved,
                )
            assert exc_info.value.code == "north_star_revise_unresolved_blocking"
            assert "omitted" in str(exc_info.value)

    def test_raises_cli_error_with_multiple_unresolved(self) -> None:
        """Multiple unresolved actions all appear in the error message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            (plan_dir / "plan_v1.md").write_text("# Plan v1")
            (plan_dir / "plan_v2.md").write_text("# Plan v2")
            unresolved = [
                {"id": "ns-a", "action_type": "change_plan", "reason": "omitted"},
                {"id": "ns-b", "action_type": "add_gate", "reason": "prose_only"},
                {"id": "ns-c", "action_type": "add_checker", "reason": "action_type_mismatch"},
            ]
            with pytest.raises(CliError) as exc_info:
                _raise_north_star_revise_unresolved(
                    plan_dir,
                    state,
                    iteration=3,
                    unresolved=unresolved,
                )
            error_text = str(exc_info.value)
            assert "3 carried blocking" in error_text
            assert "ns-a" in error_text
            assert "ns-b" in error_text
            assert "ns-c" in error_text
            assert "omitted=1" in error_text or "omitted" in error_text
            assert "prose_only=1" in error_text or "prose_only" in error_text
            assert "action_type_mismatch=1" in error_text or "action_type_mismatch" in error_text

    def test_raises_cli_error_with_malformed_reason(self) -> None:
        """When addressed metadata is malformed, the message includes the reason."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            (plan_dir / "plan_v1.md").write_text("# Plan v1")
            (plan_dir / "plan_v2.md").write_text("# Plan v2")
            unresolved = [
                {"id": "ns-1", "action_type": "change_plan", "reason": "omitted"}
            ]
            with pytest.raises(CliError) as exc_info:
                _raise_north_star_revise_unresolved(
                    plan_dir,
                    state,
                    iteration=2,
                    unresolved=unresolved,
                    malformed_reason="north_star_actions_addressed[] malformed: bad shape",
                )
            assert "north_star_actions_addressed[] malformed" in str(exc_info.value)

    def test_function_always_raises(self) -> None:
        """The function always raises CliError (only called when unresolved non-empty)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            state = _min_state()
            (plan_dir / "plan_v1.md").write_text("# Plan v1")
            (plan_dir / "plan_v2.md").write_text("# Plan v2")
            with pytest.raises(CliError):
                _raise_north_star_revise_unresolved(
                    plan_dir,
                    state,
                    iteration=2,
                    unresolved=[],
                )
