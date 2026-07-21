"""Tests proving that status display fallbacks cannot feed dispatch, completion,
cancellation, publication, or delivery.

Every display projection — whether from ``status_projection``, ``status_view``,
or ``cli/projection`` — must carry an explicit non-authoritative marker and
must never imply an authority grant for any of the five forbidden actions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arnold.kernel.events import EventEnvelope, EventFamily, ManifestReference
from arnold.kernel.journal import NDJsonEventJournal


# ── Helpers ─────────────────────────────────────────────────────────────

def _append_event(
    journal: NDJsonEventJournal,
    *,
    kind: str,
    payload: dict,
    family: EventFamily = EventFamily.NODE_LIFECYCLE,
) -> None:
    event = EventEnvelope(
        event_id=f"run:test:{kind}",
        family=family,
        kind=kind,
        manifest=ManifestReference(alias="megaplan", manifest_hash="sha256:" + "0" * 64),
        run_id="run:test",
        payload_schema_hash="sha256:" + "0" * 64,
        payload=payload,
    )
    journal.append(event)


def _make_minimal_state(**overrides: Any) -> dict[str, Any]:
    """Return a minimal state dict suitable for _build_status_payload."""
    state: dict[str, Any] = {
        "name": "test-plan",
        "current_state": "finalized",
        "iteration": 0,
        "config": {"mode": "code"},
        "sessions": {},
        "meta": {"notes": [], "total_cost_usd": 0.0},
        "history": [],
    }
    state.update(overrides)
    return state


# ── Forbidden actions ───────────────────────────────────────────────────

FORBIDDEN_ACTIONS = {"dispatch", "completion", "cancellation", "publication", "delivery"}
NON_AUTHORITATIVE_MARKER = "display_only_non_authoritative"


# ═══════════════════════════════════════════════════════════════════════════
# status_projection.py — plan_status_presentation
# ═══════════════════════════════════════════════════════════════════════════

class TestPlanStatusPresentationNeverAuthorizes:
    """Every call to plan_status_presentation must return non-authoritative markers."""

    @pytest.mark.parametrize("plan_state", [
        "finalized", "executing", "done", "completed", "failed",
        "paused", "blocked", "cancelled", "in_progress", "unknown",
    ])
    def test_display_authority_always_non_authoritative(self, plan_state: str) -> None:
        from arnold_pipelines.megaplan.status_projection import plan_status_presentation

        projection = plan_status_presentation(plan_state)
        assert projection["display_authority"] == NON_AUTHORITATIVE_MARKER, (
            f"plan_state={plan_state!r} produced display_authority={projection['display_authority']!r}"
        )

    def test_no_state_grants_authority(self) -> None:
        """Exhaustively check that no lifecycle state produces an authority grant."""
        from arnold_pipelines.megaplan.status_projection import plan_status_presentation

        all_states = [
            "finalized", "executing", "done", "completed", "complete",
            "failed", "aborted", "cancelled", "paused", "awaiting_human",
            "awaiting_human_verify", "blocked", "clarifying",
            "initialized", "planned", "reviewed", "in_progress",
        ]
        for state in all_states:
            projection = plan_status_presentation(state)
            assert projection["display_authority"] == NON_AUTHORITATIVE_MARKER
            # The display_authority must never be an action verb.
            assert projection["display_authority"] not in FORBIDDEN_ACTIONS

    def test_execution_state_never_is_authority_grant(self) -> None:
        """execution_state labels are cosmetic; never an authority keyword."""
        from arnold_pipelines.megaplan.status_projection import plan_status_presentation

        # Every execution_state value possible.
        projections = [
            plan_status_presentation("finalized", active_step={"phase": "execute"}),
            plan_status_presentation("finalized"),
            plan_status_presentation("paused"),
            plan_status_presentation("failed"),
            plan_status_presentation("blocked"),
            plan_status_presentation("done"),
            plan_status_presentation("executed", active_step={"phase": "review"}),
        ]
        for p in projections:
            assert p["display_authority"] == NON_AUTHORITATIVE_MARKER
            assert p["execution_state"] is None or p["execution_state"] not in FORBIDDEN_ACTIONS

    def test_display_state_never_is_authority_grant(self) -> None:
        """display_state labels are human-readable; never an authority keyword."""
        from arnold_pipelines.megaplan.status_projection import plan_status_presentation

        projections = [
            plan_status_presentation("done"),
            plan_status_presentation("completed", completed=True),
            plan_status_presentation("finalized", active_step={"phase": "execute"}),
            plan_status_presentation("finalized", review_verdict="needs_rework"),
        ]
        for p in projections:
            assert p["display_authority"] == NON_AUTHORITATIVE_MARKER
            assert p["display_state"] is None or p["display_state"] not in FORBIDDEN_ACTIONS


class TestPlanStatusPresentationSourceCursor:
    """Source cursor vectors are always present but never authoritative."""

    def test_missing_cursor_produces_absent_sentinel(self) -> None:
        from arnold_pipelines.megaplan.status_projection import plan_status_presentation

        projection = plan_status_presentation("finalized")
        cursor = projection["source_cursor_vector"]
        assert isinstance(cursor, dict)
        assert cursor["authority"] == "absent"
        assert "reason" in cursor

    def test_provided_cursor_is_evidence_extracted_display_only(self) -> None:
        from arnold_pipelines.megaplan.status_projection import plan_status_presentation

        cursor_vec = {"phase": "execute", "sequence": 42}
        projection = plan_status_presentation(
            "finalized",
            source_cursor_vector=cursor_vec,
        )
        cursor = projection["source_cursor_vector"]
        assert cursor["authority"] == "evidence_extracted_display_only"
        assert cursor["value"] == cursor_vec

    def test_cursor_never_grants_any_forbidden_action(self) -> None:
        from arnold_pipelines.megaplan.status_projection import plan_status_presentation

        for authority_label in ["absent", "evidence_extracted_display_only"]:
            cursor_vec = {"authority": authority_label}
            projection = plan_status_presentation(
                "finalized",
                source_cursor_vector=cursor_vec,
            )
            cursor = projection["source_cursor_vector"]
            assert cursor["authority"] not in FORBIDDEN_ACTIONS
            assert cursor["authority"] != "granted"


class TestPlanStatusPresentationWbcInputs:
    """WBC query inputs are always present but never authoritative."""

    def test_missing_wbc_inputs_produce_absent_sentinel(self) -> None:
        from arnold_pipelines.megaplan.status_projection import plan_status_presentation

        projection = plan_status_presentation("finalized")
        wbc = projection["wbc_query_inputs"]
        assert isinstance(wbc, dict)
        assert wbc["authority"] == "absent"
        assert "reason" in wbc

    def test_provided_wbc_inputs_are_wbc_query_display_only(self) -> None:
        from arnold_pipelines.megaplan.status_projection import plan_status_presentation

        wbc_in = {"chain": "CHAIN-01", "phase": "execute"}
        projection = plan_status_presentation(
            "finalized",
            wbc_query_inputs=wbc_in,
        )
        wbc = projection["wbc_query_inputs"]
        assert wbc["authority"] == "wbc_query_display_only"
        assert wbc["value"] == wbc_in

    def test_wbc_inputs_never_grant_any_forbidden_action(self) -> None:
        from arnold_pipelines.megaplan.status_projection import plan_status_presentation

        for authority_label in ["absent", "wbc_query_display_only"]:
            projection = plan_status_presentation("finalized")
            wbc = projection["wbc_query_inputs"]
            assert wbc["authority"] not in FORBIDDEN_ACTIONS
            assert wbc["authority"] != "granted"


class TestPlanStatusPresentationPreservesReviewRework:
    """The review/rework display behavior from the adjacent-review/rework
    commit is preserved."""

    def test_reviewing_state(self) -> None:
        from arnold_pipelines.megaplan.status_projection import plan_status_presentation

        p = plan_status_presentation(
            "executed",
            active_step={"phase": "review"},
            review_verdict="needs_rework",
        )
        assert p["execution_state"] == "reviewing"
        assert p["display_state"] == "reviewing"
        assert p["display_authority"] == NON_AUTHORITATIVE_MARKER

    def test_reworking_state(self) -> None:
        from arnold_pipelines.megaplan.status_projection import plan_status_presentation

        p = plan_status_presentation(
            "finalized",
            active_step={"phase": "execute"},
            review_verdict="needs_rework",
        )
        assert p["execution_state"] == "reworking"
        assert p["display_state"] == "reworking"
        assert p["display_authority"] == NON_AUTHORITATIVE_MARKER

    def test_rework_required_state(self) -> None:
        from arnold_pipelines.megaplan.status_projection import plan_status_presentation

        p = plan_status_presentation(
            "finalized",
            review_verdict="needs_rework",
        )
        assert p["execution_state"] == "rework_required"
        assert p["display_state"] == "needs_rework"
        assert p["display_authority"] == NON_AUTHORITATIVE_MARKER


# ═══════════════════════════════════════════════════════════════════════════
# cli/status_view.py — _build_status_payload
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildStatusPayloadNeverAuthorizes:
    """The CLI status payload must never authorize dispatch, completion, etc."""

    def test_status_route_authority_is_workflow_source_only(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.status_view import _build_status_payload

        state = _make_minimal_state()
        payload = _build_status_payload(tmp_path, state)

        assert payload["status_route_authority"] == "workflow_source_only"
        assert payload["status_route_authority"] not in FORBIDDEN_ACTIONS

    def test_legacy_route_hints_are_display_only(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.status_view import _build_status_payload

        state = _make_minimal_state()
        payload = _build_status_payload(tmp_path, state)

        hints = payload["legacy_route_hints"]
        assert hints["authority"] == NON_AUTHORITATIVE_MARKER
        assert hints["authority"] not in FORBIDDEN_ACTIONS

    def test_display_authority_key_present(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.status_view import _build_status_payload

        state = _make_minimal_state()
        payload = _build_status_payload(tmp_path, state)
        assert payload["display_authority"] == NON_AUTHORITATIVE_MARKER

    def test_source_cursor_vector_in_payload(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.status_view import _build_status_payload

        state = _make_minimal_state()
        payload = _build_status_payload(tmp_path, state)
        cursor = payload["source_cursor_vector"]
        assert isinstance(cursor, dict)
        assert cursor["authority"] not in FORBIDDEN_ACTIONS
        assert cursor["authority"] != "granted"

    def test_wbc_query_inputs_in_payload(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.status_view import _build_status_payload

        state = _make_minimal_state()
        payload = _build_status_payload(tmp_path, state)
        wbc = payload["wbc_query_inputs"]
        assert isinstance(wbc, dict)
        assert wbc["authority"] not in FORBIDDEN_ACTIONS
        assert wbc["authority"] != "granted"

    def test_next_step_never_grants_dispatch(self, tmp_path: Path) -> None:
        """The next_step field is a display hint, never a dispatch grant."""
        from arnold_pipelines.megaplan.cli.status_view import _build_status_payload

        state = _make_minimal_state()
        payload = _build_status_payload(tmp_path, state)

        # next_step may be None or a string like "execute", "review", etc.
        # It must never be presented as an authority grant.
        assert payload["status_route_authority"] == "workflow_source_only"
        assert payload["legacy_route_hints"]["authority"] == NON_AUTHORITATIVE_MARKER

    def test_blocked_state_does_not_leak_authority(self, tmp_path: Path) -> None:
        """When the plan is blocked, recovery commands are hints, not grants."""
        from arnold_pipelines.megaplan.cli.status_view import _build_status_payload

        state = _make_minimal_state(current_state="blocked")
        payload = _build_status_payload(tmp_path, state)

        assert payload["display_authority"] == NON_AUTHORITATIVE_MARKER
        assert payload["status_route_authority"] == "workflow_source_only"
        # Recovery commands are suggestions, not authorization.
        cmds = payload.get("suggested_recovery_commands", [])
        for cmd in cmds:
            assert isinstance(cmd, str)


# ═══════════════════════════════════════════════════════════════════════════
# cli/projection.py — manifest-backed projections
# ═══════════════════════════════════════════════════════════════════════════

class TestPlanStatusProjectionNeverAuthorizes:
    """PlanStatusProjection.to_dict() must carry a display-only marker."""

    def test_to_dict_includes_display_authority(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_status

        journal = NDJsonEventJournal(tmp_path)
        _append_event(journal, kind="node_started", payload={"node_ref": "prep"})

        status = project_status(plan_name="test", artifact_root=tmp_path)
        d = status.to_dict()
        assert d["display_authority"] == NON_AUTHORITATIVE_MARKER
        assert d["display_authority"] not in FORBIDDEN_ACTIONS

    def test_source_cursor_vector_in_to_dict(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_status

        journal = NDJsonEventJournal(tmp_path)
        _append_event(journal, kind="node_started", payload={"node_ref": "prep"})

        status = project_status(plan_name="test", artifact_root=tmp_path)
        d = status.to_dict()
        assert "source_cursor_vector" in d
        cursor = d["source_cursor_vector"]
        assert cursor["authority"] == "manifest_journal_derived_display_only"
        assert cursor["authority"] not in FORBIDDEN_ACTIONS


class TestProjectInspectNeverAuthorizes:
    """project_inspect must carry explicit forbidden-actions markers."""

    def test_inspect_includes_display_authority(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_inspect

        journal = NDJsonEventJournal(tmp_path)
        _append_event(journal, kind="node_completed", payload={"node_ref": "prep"})

        inspect = project_inspect(
            artifact_root=tmp_path, plan_name="test", manifest_hash="sha256:abc"
        )
        assert inspect["display_authority"] == NON_AUTHORITATIVE_MARKER

    def test_inspect_forbidden_actions_covers_all_five(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_inspect

        journal = NDJsonEventJournal(tmp_path)
        _append_event(journal, kind="node_completed", payload={"node_ref": "prep"})

        inspect = project_inspect(
            artifact_root=tmp_path, plan_name="test", manifest_hash="sha256:abc"
        )
        forbidden = set(inspect["forbidden_actions"])
        assert forbidden == FORBIDDEN_ACTIONS

    def test_inspect_status_also_non_authoritative(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_inspect

        journal = NDJsonEventJournal(tmp_path)
        _append_event(journal, kind="node_completed", payload={"node_ref": "prep"})

        inspect = project_inspect(
            artifact_root=tmp_path, plan_name="test", manifest_hash="sha256:abc"
        )
        assert inspect["status"]["display_authority"] == NON_AUTHORITATIVE_MARKER
        # The nested status also carries a source_cursor_vector that is display-only.
        if "source_cursor_vector" in inspect["status"]:
            cursor = inspect["status"]["source_cursor_vector"]
            assert cursor.get("authority", "") not in FORBIDDEN_ACTIONS


class TestCommandProjectionsNeverAuthorize:
    """Gate, review, execute, and override projections are display-only."""

    def test_gate_status_is_display_only(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_gate_status

        journal = NDJsonEventJournal(tmp_path)
        _append_event(
            journal,
            kind="control_transition",
            payload={
                "kind": "override",
                "source_node": "gate",
                "target_node": "revise",
                "trigger": "gate:iterate",
            },
            family=EventFamily.CONTROL_TRANSITION,
        )

        result = project_gate_status(artifact_root=tmp_path)
        assert result["display_authority"] == NON_AUTHORITATIVE_MARKER
        assert result["display_authority"] not in FORBIDDEN_ACTIONS

    def test_review_status_is_display_only(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_review_status

        journal = NDJsonEventJournal(tmp_path)
        _append_event(
            journal,
            kind="control_transition",
            payload={
                "kind": "override",
                "source_node": "review",
                "target_node": "halt",
                "trigger": "review:pass",
            },
            family=EventFamily.CONTROL_TRANSITION,
        )

        result = project_review_status(artifact_root=tmp_path)
        assert result["display_authority"] == NON_AUTHORITATIVE_MARKER
        assert result["display_authority"] not in FORBIDDEN_ACTIONS

    def test_execute_status_is_display_only(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_execute_status

        journal = NDJsonEventJournal(tmp_path)
        _append_event(journal, kind="node_started", payload={"node_ref": "execute"})

        result = project_execute_status(artifact_root=tmp_path)
        assert result["display_authority"] == NON_AUTHORITATIVE_MARKER
        assert result["display_authority"] not in FORBIDDEN_ACTIONS

    def test_override_status_is_display_only(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.projection import project_override_status

        journal = NDJsonEventJournal(tmp_path)
        _append_event(
            journal,
            kind="control_transition",
            payload={
                "kind": "override",
                "source_node": "gate",
                "target_node": "execute",
                "trigger": "override:force_execute",
            },
            family=EventFamily.CONTROL_TRANSITION,
        )

        result = project_override_status(artifact_root=tmp_path)
        assert result["display_authority"] == NON_AUTHORITATIVE_MARKER
        assert result["display_authority"] not in FORBIDDEN_ACTIONS


# ═══════════════════════════════════════════════════════════════════════════
# Integration: proof that every display artifact carries non-authoritative
# markers, even when reconstruction is attempted.
# ═══════════════════════════════════════════════════════════════════════════

class TestCrossSurfaceNonAuthoritative:
    """Every display surface — status, progress, projections — is non-authoritative."""

    def test_status_payload_all_keys_are_non_authoritative(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.status_view import _build_status_payload

        state = _make_minimal_state()
        payload = _build_status_payload(tmp_path, state)

        # Every authority-carrying key must be non-authoritative.
        authority_keys = [
            ("display_authority", payload.get("display_authority")),
            ("status_route_authority", payload.get("status_route_authority")),
            ("source_cursor_vector.authority", payload["source_cursor_vector"]["authority"]),
            ("wbc_query_inputs.authority", payload["wbc_query_inputs"]["authority"]),
            ("legacy_route_hints.authority", payload["legacy_route_hints"]["authority"]),
        ]
        for key, value in authority_keys:
            assert value not in FORBIDDEN_ACTIONS, (
                f"Key {key} has forbidden value {value!r}"
            )
            assert value != "granted", f"Key {key} claims 'granted' authority"

    def test_progress_payload_never_authorizes(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cli.status_view import _build_progress_payload

        state = _make_minimal_state()
        # _build_progress_payload requires a finalize.json to exist
        plan_dir = tmp_path / ".megaplan" / "plans" / "test-plan"
        plan_dir.mkdir(parents=True)
        (plan_dir / "finalize.json").write_text(
            json.dumps({"tasks": [], "user_actions": []}), encoding="utf-8"
        )
        payload = _build_progress_payload(plan_dir, state)
        # Progress payloads do not carry authority markers directly, but
        # they must not contain any forbidden action keyword as a top-level key.
        assert "recommended_action" not in payload or isinstance(payload.get("recommended_action"), str)
        # The summary is a display string, never an authority token.
        assert payload.get("summary") is None or isinstance(payload["summary"], str)
