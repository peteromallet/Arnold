"""Fixture tests for ``build_introspect_payload`` (megaplan introspect).

Tests against hand-crafted events.ndjson fixtures for all liveness states,
blocked-state recoverable_via, rubric_doc drift, and the four killer fields.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from megaplan.observability.events import EventKind
from megaplan.observability.introspect import (
    _compute_block_details,
    _compute_liveness,
    _compute_rubric_drift,
    _get_profiles_list,
    _parse_decision_skill_profiles,
    build_introspect_payload,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_epoch() -> float:
    return datetime.now(timezone.utc).timestamp()


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _make_plan_dir(tmp_path: Path, plan_name: str = "test-plan") -> Path:
    """Create a plan directory under tmp_path/.megaplan/plans/<name>."""
    plan_dir = tmp_path / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)
    return plan_dir


def _write_events(plan_dir: Path, events: list[dict]) -> Path:
    """Write a list of event dicts to events.ndjson, one JSON line each."""
    ndjson = plan_dir / "events.ndjson"
    lines = [json.dumps(ev) for ev in events]
    ndjson.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ndjson


def _write_state(plan_dir: Path, state: dict) -> None:
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _event(
    kind: str,
    ts_epoch: float,
    seq: int = 0,
    phase: str | None = None,
    payload: dict | None = None,
    ts_rel_init_s: float = 0.0,
) -> dict:
    return {
        "seq": seq,
        "ts_utc": _iso(ts_epoch),
        "ts_rel_init_s": ts_rel_init_s,
        "kind": kind,
        "phase": phase,
        "payload": payload or {},
    }


# ---------------------------------------------------------------------------
# Liveness: progressing (recent events < 60s, or in-flight LLM)
# ---------------------------------------------------------------------------


class TestLivenessProgressing:
    def test_recent_event_under_60s(self, tmp_path: Path) -> None:
        """Progressing: most recent event is < 60s ago."""
        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)
        events = [
            _event(EventKind.INIT, now_ts - 30, seq=0),
        ]
        _write_events(plan_dir, events)

        liveness, reason = _compute_liveness(events, plan_dir, None, now_ts)
        assert liveness == "progressing"
        assert "last event" in reason

    def test_in_flight_llm_makes_progressing(self, tmp_path: Path) -> None:
        """Progressing: in-flight LLM call, even if last event is old."""
        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)
        events = [
            _event(EventKind.INIT, now_ts - 600, seq=0),
            _event(
                EventKind.LLM_CALL_START,
                now_ts - 400,
                seq=1,
                payload={"request_id": "req-1", "provider": "fireworks", "model": "test"},
            ),
        ]
        _write_events(plan_dir, events)

        liveness, reason = _compute_liveness(events, plan_dir, None, now_ts)
        assert liveness == "progressing"
        assert "in-flight LLM" in reason

    def test_in_flight_llm_old_start_still_in_flight(self, tmp_path: Path) -> None:
        """In-flight LLM start within 2 hours counts; >2 hours is stale."""
        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)

        # Start 1.5 hours ago (5400s) — still within 2h window
        events = [
            _event(EventKind.INIT, now_ts - 4000, seq=0),
            _event(
                EventKind.LLM_CALL_START,
                now_ts - 5400,
                seq=1,
                payload={"request_id": "req-old", "provider": "fireworks", "model": "test"},
            ),
        ]
        _write_events(plan_dir, events)

        liveness, reason = _compute_liveness(events, plan_dir, None, now_ts)
        assert liveness == "progressing", f"Expected progressing, got {liveness}: {reason}"
        assert "in-flight LLM" in reason

    def test_stale_llm_start_over_2h_not_in_flight(self, tmp_path: Path) -> None:
        """LLM start >2 hours old is stale, does not count as in-flight."""
        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)
        events = [
            _event(EventKind.INIT, now_ts - 8000, seq=0),
            _event(
                EventKind.LLM_CALL_START,
                now_ts - 8000,
                seq=1,
                payload={"request_id": "req-stale", "provider": "fireworks", "model": "test"},
            ),
        ]
        _write_events(plan_dir, events)

        liveness, reason = _compute_liveness(events, plan_dir, None, now_ts)
        # >2h old start, last event 8000s ago, no in-flight → stalled
        assert liveness == "stalled", f"Expected stalled for stale LLM start, got {liveness}: {reason}"


# ---------------------------------------------------------------------------
# Liveness: quiet (last event 60–300s, no in-flight LLM)
# ---------------------------------------------------------------------------


class TestLivenessQuiet:
    def test_last_event_120s_ago_no_inflight(self, tmp_path: Path) -> None:
        """Quiet: last event 120s ago, no in-flight LLM call."""
        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)
        events = [
            _event(EventKind.INIT, now_ts - 120, seq=0),
        ]
        _write_events(plan_dir, events)

        liveness, reason = _compute_liveness(events, plan_dir, None, now_ts)
        assert liveness == "quiet"
        assert "60-300s" in reason

    def test_last_event_200s_ago_no_inflight(self, tmp_path: Path) -> None:
        """Quiet: last event 200s ago, no in-flight LLM call."""
        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)
        events = [
            _event(EventKind.INIT, now_ts - 200, seq=0),
            _event(EventKind.PHASE_START, now_ts - 200, seq=1, phase="critique"),
        ]
        _write_events(plan_dir, events)

        liveness, reason = _compute_liveness(events, plan_dir, None, now_ts)
        assert liveness == "quiet"
        assert "60-300s" in reason

    def test_no_events_yet_is_quiet(self, tmp_path: Path) -> None:
        """No events recorded yet → quiet."""
        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)
        events: list[dict] = []

        liveness, reason = _compute_liveness(events, plan_dir, None, now_ts)
        assert liveness == "quiet"
        assert "no events" in reason.lower()


# ---------------------------------------------------------------------------
# Liveness: stalled (last event > 300s, no in-flight LLM)
# ---------------------------------------------------------------------------


class TestLivenessStalled:
    def test_last_event_400s_ago_no_inflight(self, tmp_path: Path) -> None:
        """Stalled: last event >300s ago, no in-flight LLM call."""
        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)
        events = [
            _event(EventKind.INIT, now_ts - 400, seq=0),
            _event(EventKind.PHASE_START, now_ts - 400, seq=1, phase="critique"),
        ]
        _write_events(plan_dir, events)

        liveness, reason = _compute_liveness(events, plan_dir, None, now_ts)
        assert liveness == "stalled"
        assert ">300s" in reason
        assert "no in-flight LLM" in reason

    def test_last_event_1000s_ago_no_inflight(self, tmp_path: Path) -> None:
        """Stalled: very old last event, no in-flight LLM call."""
        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)
        events = [
            _event(EventKind.INIT, now_ts - 1000, seq=0),
        ]
        _write_events(plan_dir, events)

        liveness, reason = _compute_liveness(events, plan_dir, None, now_ts)
        assert liveness == "stalled"

    def test_not_stalled_when_in_flight_llm_exists(self, tmp_path: Path) -> None:
        """NOT stalled when unmatched llm_call_start exists (regardless of age <2h)."""
        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)
        events = [
            _event(EventKind.INIT, now_ts - 500, seq=0),
            _event(
                EventKind.LLM_CALL_START,
                now_ts - 450,
                seq=1,
                payload={"request_id": "req-inflight", "provider": "openrouter", "model": "claude"},
            ),
        ]
        _write_events(plan_dir, events)

        liveness, reason = _compute_liveness(events, plan_dir, None, now_ts)
        # Last event is init at 500s ago (>300s) but in-flight LLM exists → progressing, not stalled
        assert liveness == "progressing", f"Expected progressing (in-flight LLM), got {liveness}: {reason}"
        assert "in-flight LLM" in reason

    def test_not_stalled_when_matched_llm_exists(self, tmp_path: Path) -> None:
        """When llm_call_start has matching llm_call_end, it's not in-flight."""
        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)
        events = [
            _event(EventKind.INIT, now_ts - 500, seq=0),
            _event(
                EventKind.LLM_CALL_START,
                now_ts - 480,
                seq=1,
                payload={"request_id": "req-done", "provider": "openrouter", "model": "claude"},
            ),
            _event(
                EventKind.LLM_CALL_END,
                now_ts - 460,
                seq=2,
                payload={"request_id": "req-done", "tokens_in": 100, "tokens_out": 200},
            ),
        ]
        _write_events(plan_dir, events)

        liveness, reason = _compute_liveness(events, plan_dir, None, now_ts)
        # Last event is 460s ago, NO in-flight LLM (matched) → stalled
        assert liveness == "stalled", f"Expected stalled (matched LLM), got {liveness}: {reason}"
        assert "no in-flight LLM" in reason


# ---------------------------------------------------------------------------
# Liveness: timeout-imminent (phase_age > 0.8 × phase_timeout)
# ---------------------------------------------------------------------------


class TestLivenessTimeoutImminent:
    def test_phase_age_exceeds_80pct(self, tmp_path: Path) -> None:
        """Timeout-imminent: phase_age > 0.8 * phase_timeout (2880s)."""
        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)

        started_at = _iso(now_ts - 3000)  # 3000s ago > 2880s
        state = {
            "current_state": "critiquing",
            "active_step": {
                "step": "critique",
                "agent": "claude",
                "model": "sonnet-4",
                "started_at": started_at,
                "attempt": 1,
            },
        }
        _write_state(plan_dir, state)

        events = [
            _event(EventKind.INIT, now_ts - 3000, seq=0),
            _event(EventKind.PHASE_START, now_ts - 3000, seq=1, phase="critique"),
        ]
        _write_events(plan_dir, events)

        liveness, reason = _compute_liveness(events, plan_dir, state, now_ts)
        assert liveness == "timeout-imminent", f"Expected timeout-imminent, got {liveness}: {reason}"
        assert "0.8" in reason or "timeout" in reason.lower()

    def test_phase_age_below_80pct_not_imminent(self, tmp_path: Path) -> None:
        """Not timeout-imminent: phase_age < 0.8 * phase_timeout."""
        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)

        started_at = _iso(now_ts - 1000)  # 1000s < 2880s
        state = {
            "current_state": "critiquing",
            "active_step": {
                "step": "critique",
                "started_at": started_at,
                "attempt": 1,
            },
        }
        _write_state(plan_dir, state)

        events = [
            _event(EventKind.INIT, now_ts - 1000, seq=0),
            _event(EventKind.PHASE_START, now_ts - 1000, seq=1, phase="critique"),
        ]
        _write_events(plan_dir, events)

        liveness, reason = _compute_liveness(events, plan_dir, state, now_ts)
        assert liveness != "timeout-imminent", f"Should not be timeout-imminent at 1000s"

    def test_timeout_imminent_takes_priority_over_progressing(self, tmp_path: Path) -> None:
        """Timeout-imminent takes priority even if recent events exist."""
        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)

        started_at = _iso(now_ts - 3000)  # > 2880s
        state = {
            "current_state": "critiquing",
            "active_step": {
                "step": "critique",
                "started_at": started_at,
                "attempt": 1,
            },
        }
        _write_state(plan_dir, state)

        # Most recent event is only 10s ago — would normally be progressing
        events = [
            _event(EventKind.INIT, now_ts - 3000, seq=0),
            _event(EventKind.PHASE_START, now_ts - 3000, seq=1, phase="critique"),
            _event(EventKind.LLM_TOKEN_HEARTBEAT, now_ts - 10, seq=2),
        ]
        _write_events(plan_dir, events)

        liveness, reason = _compute_liveness(events, plan_dir, state, now_ts)
        assert liveness == "timeout-imminent", f"Expected timeout-imminent priority, got {liveness}: {reason}"


# ---------------------------------------------------------------------------
# Block details: recoverable_via populated and non-empty
# ---------------------------------------------------------------------------


class TestBlockDetails:
    def test_blocked_state_with_recoverable_via(self, tmp_path: Path) -> None:
        """Blocked state (gated) has recoverable_via populated."""
        plan_dir = _make_plan_dir(tmp_path)
        state = {
            "current_state": "gated",
            "active_step": {"step": "gate"},
            "robustness": "full",
            "creative": False,
            "profile_name": "solo",
        }
        _write_state(plan_dir, state)

        block = _compute_block_details(plan_dir, state)
        assert block["is_blocked"] is True
        assert block["current_state"] == "gated"
        assert block["recoverable_via"] is not None
        assert isinstance(block["recoverable_via"], list)
        assert len(block["recoverable_via"]) > 0, (
            f"Expected non-empty recoverable_via for state 'gated', got {block['recoverable_via']}"
        )

    def test_blocked_state_with_outstanding_flags(self, tmp_path: Path) -> None:
        """Blocked state due to outstanding flags has recoverable_via."""
        plan_dir = _make_plan_dir(tmp_path)
        state = {
            "current_state": "critiqued",
            "robustness": "full",
            "creative": False,
            "profile_name": "solo",
        }
        _write_state(plan_dir, state)

        # Write gate signals with unresolved flags
        gate_data = {"unresolved_flags": [{"id": "F1", "message": "test flag"}]}
        (plan_dir / "gate_signals_v1.json").write_text(json.dumps(gate_data), encoding="utf-8")

        block = _compute_block_details(plan_dir, state)
        assert block["is_blocked"] is True
        assert block["recoverable_via"] is not None
        assert isinstance(block["recoverable_via"], list)

    def test_non_blocked_state_recoverable_via_none(self, tmp_path: Path) -> None:
        """Non-blocked state: recoverable_via is None."""
        plan_dir = _make_plan_dir(tmp_path)
        state = {
            "current_state": "planning",
            "robustness": "full",
            "creative": False,
            "profile_name": "solo",
        }
        _write_state(plan_dir, state)

        block = _compute_block_details(plan_dir, state)
        assert block["is_blocked"] is False
        assert block["recoverable_via"] is None

    def test_no_state_recoverable_via_none(self, tmp_path: Path) -> None:
        """No state.json → recoverable_via is None, not blocked."""
        plan_dir = _make_plan_dir(tmp_path)
        block = _compute_block_details(plan_dir, None)
        assert block["is_blocked"] is False
        assert block["recoverable_via"] is None
        assert block["current_state"] is None


# ---------------------------------------------------------------------------
# Rubric doc drift
# ---------------------------------------------------------------------------


class TestRubricDrift:
    @patch("megaplan.observability.introspect._get_profiles_list")
    @patch("megaplan.observability.introspect._parse_decision_skill_profiles")
    def test_drift_when_profile_missing(
        self, mock_parse: MagicMock, mock_profiles: MagicMock
    ) -> None:
        """rubric_doc.drift detects missing profile in binary."""
        mock_parse.return_value = ["solo", "directed", "partnered", "premium", "apex", "thoughtful"]
        mock_profiles.return_value = ["solo", "directed", "partnered", "premium", "apex"]

        result = _compute_rubric_drift()
        assert result["drifted"] is True
        assert "thoughtful" in result["missing_in_binary"]
        assert result["referenced_profiles"] is not None
        assert result["available_profiles"] is not None

    @patch("megaplan.observability.introspect._get_profiles_list")
    @patch("megaplan.observability.introspect._parse_decision_skill_profiles")
    def test_no_drift_when_all_match(
        self, mock_parse: MagicMock, mock_profiles: MagicMock
    ) -> None:
        """No drift when all referenced profiles exist."""
        mock_parse.return_value = ["solo", "directed", "partnered", "premium", "apex"]
        mock_profiles.return_value = ["solo", "directed", "partnered", "premium", "apex", "all-claude"]

        result = _compute_rubric_drift()
        assert result["drifted"] is False
        assert result["missing_in_binary"] is None
        # extra profiles available but not referenced
        assert "all-claude" in result["extra_in_skill_not_referenced"]

    @patch("megaplan.observability.introspect._get_profiles_list")
    @patch("megaplan.observability.introspect._parse_decision_skill_profiles")
    def test_empty_profiles_no_drift(
        self, mock_parse: MagicMock, mock_profiles: MagicMock
    ) -> None:
        """Empty profiles on both sides → no drift."""
        mock_parse.return_value = []
        mock_profiles.return_value = []

        result = _compute_rubric_drift()
        assert result["drifted"] is False
        assert result["missing_in_binary"] is None


# ---------------------------------------------------------------------------
# Four killer fields populated in every output
# ---------------------------------------------------------------------------


class TestKillerFieldsPopulated:
    def test_all_four_killer_fields_in_payload(self, tmp_path: Path) -> None:
        """now_utc, rubric_doc.drift, active_phase.liveness, block_details.recoverable_via
        are all present in the output of build_introspect_payload."""
        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)

        # Create minimal events
        events = [
            _event(EventKind.INIT, now_ts - 10, seq=0),
        ]
        _write_events(plan_dir, events)

        # Create state (non-blocked, progressing)
        state = {
            "current_state": "planning",
            "active_step": {
                "step": "plan",
                "started_at": _iso(now_ts - 10),
                "attempt": 1,
            },
        }
        _write_state(plan_dir, state)

        # Mock external dependencies to avoid real shell calls
        with patch(
            "megaplan.observability.introspect._git_info",
            return_value={"branch": "main", "dirty": False, "head": "abc123def456"},
        ), patch(
            "megaplan.observability.introspect._editable_install_location",
            return_value="/fake/install/path",
        ), patch(
            "megaplan.observability.introspect._get_profiles_list",
            return_value=["solo", "directed", "partnered", "premium", "apex"],
        ), patch(
            "megaplan.observability.introspect._parse_decision_skill_profiles",
            return_value=["solo", "directed", "partnered", "premium", "apex"],
        ), patch(
            "megaplan.observability.introspect._process_tree",
            return_value=[],
        ):
            payload = build_introspect_payload(plan_dir)

        # Killer field 1: now_utc
        assert "now_utc" in payload, "Killer field 'now_utc' missing"
        assert payload["now_utc"] is not None

        # Killer field 2: rubric_doc.drift
        assert "rubric_doc" in payload, "Killer field 'rubric_doc' missing"
        assert "drifted" in payload["rubric_doc"], "rubric_doc.drift missing"
        assert payload["rubric_doc"]["drifted"] is not None

        # Killer field 3: active_phase.liveness
        assert "active_phase" in payload, "Killer field 'active_phase' missing"
        assert "liveness" in payload["active_phase"], "active_phase.liveness missing"
        assert payload["active_phase"]["liveness"] in (
            "progressing", "quiet", "stalled", "timeout-imminent"
        ), f"Unexpected liveness: {payload['active_phase']['liveness']}"

        # Killer field 4: block_details.recoverable_via
        assert "block_details" in payload, "Killer field 'block_details' missing"
        assert "recoverable_via" in payload["block_details"], (
            "block_details.recoverable_via missing"
        )
        # For non-blocked state, recoverable_via is None — that's still "populated"

    def test_killer_fields_in_blocked_payload(self, tmp_path: Path) -> None:
        """All four killer fields populated even when plan is blocked."""
        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)

        events = [
            _event(EventKind.INIT, now_ts - 500, seq=0),
            _event(EventKind.PHASE_START, now_ts - 500, seq=1, phase="critique"),
        ]
        _write_events(plan_dir, events)

        state = {
            "current_state": "gated",
            "active_step": {
                "step": "gate",
                "started_at": _iso(now_ts - 500),
                "attempt": 1,
            },
            "robustness": "full",
            "creative": False,
            "profile_name": "solo",
        }
        _write_state(plan_dir, state)

        with patch(
            "megaplan.observability.introspect._git_info",
            return_value={"branch": "main", "dirty": False, "head": "abc123def456"},
        ), patch(
            "megaplan.observability.introspect._editable_install_location",
            return_value=None,
        ), patch(
            "megaplan.observability.introspect._get_profiles_list",
            return_value=["solo", "directed", "partnered", "premium", "apex"],
        ), patch(
            "megaplan.observability.introspect._parse_decision_skill_profiles",
            return_value=["solo", "directed", "partnered", "premium", "apex"],
        ), patch(
            "megaplan.observability.introspect._process_tree",
            return_value=[],
        ):
            payload = build_introspect_payload(plan_dir)

        assert "now_utc" in payload and payload["now_utc"] is not None
        assert "rubric_doc" in payload and "drifted" in payload["rubric_doc"]
        assert "active_phase" in payload and "liveness" in payload["active_phase"]
        assert payload["active_phase"]["liveness"] == "stalled"
        assert "block_details" in payload and "recoverable_via" in payload["block_details"]
        # For gated state, recoverable_via should be non-empty
        assert payload["block_details"]["recoverable_via"] is not None
        assert len(payload["block_details"]["recoverable_via"]) > 0


# ---------------------------------------------------------------------------
# Full introspect payload smoke tests
# ---------------------------------------------------------------------------


class TestBuildIntrospectPayload:
    @patch("megaplan.observability.introspect._git_info")
    @patch("megaplan.observability.introspect._editable_install_location")
    @patch("megaplan.observability.introspect._get_profiles_list")
    @patch("megaplan.observability.introspect._parse_decision_skill_profiles")
    @patch("megaplan.observability.introspect._process_tree")
    def test_payload_keys_present(
        self,
        mock_proc: MagicMock,
        mock_parse: MagicMock,
        mock_profiles: MagicMock,
        mock_editable: MagicMock,
        mock_git: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Full payload includes all expected top-level keys."""
        mock_git.return_value = {"branch": "main", "dirty": False, "head": "abc123"}
        mock_editable.return_value = "/fake/path"
        mock_profiles.return_value = ["solo", "directed", "partnered", "premium", "apex"]
        mock_parse.return_value = ["solo", "directed", "partnered", "premium", "apex"]
        mock_proc.return_value = []

        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)

        events = [
            _event(EventKind.INIT, now_ts - 10, seq=0),
        ]
        _write_events(plan_dir, events)

        state = {
            "current_state": "planning",
            "active_step": {"step": "plan", "started_at": _iso(now_ts - 10), "attempt": 1},
        }
        _write_state(plan_dir, state)

        payload = build_introspect_payload(plan_dir)

        expected_keys = [
            "now_utc", "plan", "plan_dir", "binary_git", "rubric_doc",
            "active_phase", "block_details", "event_stats", "in_flight_llm",
            "cost", "outstanding_flags", "outstanding_flags_count",
        ]
        for key in expected_keys:
            assert key in payload, f"Missing key in payload: {key}"

    @patch("megaplan.observability.introspect._git_info")
    @patch("megaplan.observability.introspect._editable_install_location")
    @patch("megaplan.observability.introspect._get_profiles_list")
    @patch("megaplan.observability.introspect._parse_decision_skill_profiles")
    @patch("megaplan.observability.introspect._process_tree")
    def test_in_flight_llm_detected(
        self,
        mock_proc: MagicMock,
        mock_parse: MagicMock,
        mock_profiles: MagicMock,
        mock_editable: MagicMock,
        mock_git: MagicMock,
        tmp_path: Path,
    ) -> None:
        """in_flight_llm is populated when unmatched llm_call_start exists."""
        mock_git.return_value = {"branch": "main", "dirty": False, "head": "abc123"}
        mock_editable.return_value = "/fake/path"
        mock_profiles.return_value = ["solo", "directed", "partnered", "premium", "apex"]
        mock_parse.return_value = ["solo", "directed", "partnered", "premium", "apex"]
        mock_proc.return_value = []

        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)

        events = [
            _event(EventKind.INIT, now_ts - 100, seq=0),
            _event(
                EventKind.LLM_CALL_START,
                now_ts - 50,
                seq=1,
                payload={"request_id": "req-abc", "provider": "fireworks", "model": "deepseek-v4"},
            ),
        ]
        _write_events(plan_dir, events)

        state = {
            "current_state": "critiquing",
            "active_step": {"step": "critique", "started_at": _iso(now_ts - 100), "attempt": 1},
        }
        _write_state(plan_dir, state)

        payload = build_introspect_payload(plan_dir)

        assert payload["in_flight_llm"] is not None
        assert payload["in_flight_llm"]["kind"] == EventKind.LLM_CALL_START
        assert payload["in_flight_llm"]["payload"]["request_id"] == "req-abc"

    @patch("megaplan.observability.introspect._git_info")
    @patch("megaplan.observability.introspect._editable_install_location")
    @patch("megaplan.observability.introspect._get_profiles_list")
    @patch("megaplan.observability.introspect._parse_decision_skill_profiles")
    @patch("megaplan.observability.introspect._process_tree")
    def test_in_flight_llm_none_when_all_ended(
        self,
        mock_proc: MagicMock,
        mock_parse: MagicMock,
        mock_profiles: MagicMock,
        mock_editable: MagicMock,
        mock_git: MagicMock,
        tmp_path: Path,
    ) -> None:
        """in_flight_llm is None when all LLM calls have matching ends."""
        mock_git.return_value = {"branch": "main", "dirty": False, "head": "abc123"}
        mock_editable.return_value = "/fake/path"
        mock_profiles.return_value = ["solo"]
        mock_parse.return_value = ["solo"]
        mock_proc.return_value = []

        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)

        events = [
            _event(EventKind.INIT, now_ts - 200, seq=0),
            _event(
                EventKind.LLM_CALL_START,
                now_ts - 150,
                seq=1,
                payload={"request_id": "req-done", "provider": "openrouter", "model": "claude"},
            ),
            _event(
                EventKind.LLM_CALL_END,
                now_ts - 100,
                seq=2,
                payload={"request_id": "req-done", "tokens_in": 500, "tokens_out": 2000},
            ),
        ]
        _write_events(plan_dir, events)

        payload = build_introspect_payload(plan_dir)

        assert payload["in_flight_llm"] is None

    @patch("megaplan.observability.introspect._git_info")
    @patch("megaplan.observability.introspect._editable_install_location")
    @patch("megaplan.observability.introspect._get_profiles_list")
    @patch("megaplan.observability.introspect._parse_decision_skill_profiles")
    @patch("megaplan.observability.introspect._process_tree")
    def test_cost_accumulation(
        self,
        mock_proc: MagicMock,
        mock_parse: MagicMock,
        mock_profiles: MagicMock,
        mock_editable: MagicMock,
        mock_git: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Cost is summed from cost_recorded events."""
        mock_git.return_value = {"branch": "main", "dirty": False, "head": "abc123"}
        mock_editable.return_value = "/fake/path"
        mock_profiles.return_value = ["solo"]
        mock_parse.return_value = ["solo"]
        mock_proc.return_value = []

        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)

        events = [
            _event(EventKind.INIT, now_ts - 50, seq=0),
            _event(
                EventKind.COST_RECORDED,
                now_ts - 40,
                seq=1,
                payload={"cost_usd": 0.05, "request_id": "r1", "provider": "openrouter"},
            ),
            _event(
                EventKind.COST_RECORDED,
                now_ts - 30,
                seq=2,
                payload={"cost_usd": 0.12, "request_id": "r2", "provider": "fireworks"},
            ),
        ]
        _write_events(plan_dir, events)

        payload = build_introspect_payload(plan_dir)
        assert payload["cost"]["total_usd"] == pytest.approx(0.17)  # 0.05 + 0.12

    @patch("megaplan.observability.introspect._git_info")
    @patch("megaplan.observability.introspect._editable_install_location")
    @patch("megaplan.observability.introspect._get_profiles_list")
    @patch("megaplan.observability.introspect._parse_decision_skill_profiles")
    @patch("megaplan.observability.introspect._process_tree")
    def test_outstanding_flags_count(
        self,
        mock_proc: MagicMock,
        mock_parse: MagicMock,
        mock_profiles: MagicMock,
        mock_editable: MagicMock,
        mock_git: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Outstanding flags count reflects gate_signals files."""
        mock_git.return_value = {"branch": "main", "dirty": False, "head": "abc123"}
        mock_editable.return_value = "/fake/path"
        mock_profiles.return_value = ["solo"]
        mock_parse.return_value = ["solo"]
        mock_proc.return_value = []

        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)

        events = [
            _event(EventKind.INIT, now_ts - 10, seq=0),
        ]
        _write_events(plan_dir, events)

        # Write gate signals with 3 unresolved flags
        gate_data = {
            "unresolved_flags": [
                {"id": "F1", "message": "flag 1"},
                {"id": "F2", "message": "flag 2"},
                {"id": "F3", "message": "flag 3"},
            ]
        }
        (plan_dir / "gate_signals_v1.json").write_text(json.dumps(gate_data), encoding="utf-8")

        payload = build_introspect_payload(plan_dir)
        assert payload["outstanding_flags_count"] == 3
        assert payload["outstanding_flags"] is not None
        assert len(payload["outstanding_flags"]) == 3

    @patch("megaplan.observability.introspect._git_info")
    @patch("megaplan.observability.introspect._editable_install_location")
    @patch("megaplan.observability.introspect._get_profiles_list")
    @patch("megaplan.observability.introspect._parse_decision_skill_profiles")
    @patch("megaplan.observability.introspect._process_tree")
    def test_event_stats(
        self,
        mock_proc: MagicMock,
        mock_parse: MagicMock,
        mock_profiles: MagicMock,
        mock_editable: MagicMock,
        mock_git: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Event stats reflect the journal contents."""
        mock_git.return_value = {"branch": "main", "dirty": False, "head": "abc123"}
        mock_editable.return_value = "/fake/path"
        mock_profiles.return_value = ["solo"]
        mock_parse.return_value = ["solo"]
        mock_proc.return_value = []

        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)

        events = [
            _event(EventKind.INIT, now_ts - 100, seq=0),
            _event(EventKind.PHASE_START, now_ts - 90, seq=1, phase="plan"),
            _event(EventKind.PHASE_END, now_ts - 50, seq=2, phase="plan"),
        ]
        _write_events(plan_dir, events)

        payload = build_introspect_payload(plan_dir)
        assert payload["event_stats"]["total"] == 3
        assert payload["event_stats"]["first_ts"] is not None
        assert payload["event_stats"]["last_ts"] is not None
        assert EventKind.INIT in payload["event_stats"]["kinds_seen"]
        assert EventKind.PHASE_START in payload["event_stats"]["kinds_seen"]
        assert EventKind.PHASE_END in payload["event_stats"]["kinds_seen"]


class TestEvidenceBlock:
    """Tests for the evidence block in build_introspect_payload."""

    @patch("megaplan.observability.introspect._git_info")
    @patch("megaplan.observability.introspect._editable_install_location")
    @patch("megaplan.observability.introspect._get_profiles_list")
    @patch("megaplan.observability.introspect._parse_decision_skill_profiles")
    @patch("megaplan.observability.introspect._process_tree")
    def test_evidence_block_present_with_all_keys(
        self,
        mock_proc: MagicMock,
        mock_parse: MagicMock,
        mock_profiles: MagicMock,
        mock_editable: MagicMock,
        mock_git: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Evidence block contains window, changed_file_count, divergence_count,
        repeated_divergence_fingerprint, and carry_forward_declared."""
        mock_git.return_value = {"branch": "main", "dirty": False, "head": "abc123"}
        mock_editable.return_value = "/fake/path"
        mock_profiles.return_value = ["solo"]
        mock_parse.return_value = ["solo"]
        mock_proc.return_value = []

        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)

        events = [
            _event(EventKind.INIT, now_ts - 10, seq=0),
        ]
        _write_events(plan_dir, events)

        state = {
            "current_state": "planning",
            "meta": {
                "chain_policy": {
                    "milestone_base_sha": "base000",
                    "repeated_divergence_fingerprint": "fp123",
                }
            },
        }
        _write_state(plan_dir, state)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="file1.py\nfile2.py\n", stderr="")
            payload = build_introspect_payload(plan_dir)

        assert "evidence" in payload, "evidence block missing from payload"
        ev = payload["evidence"]
        assert "window" in ev
        assert ev["window"]["base_sha"] == "base000"
        assert ev["window"]["head_sha"] == "abc123"
        assert ev["window"]["source"] == "declared"
        assert ev["changed_file_count"] == 2
        assert ev["divergence_count"] is None  # fingerprint is a string, not dict
        assert ev["repeated_divergence_fingerprint"] == "fp123"
        assert ev["carry_forward_declared"] is False

    @patch("megaplan.observability.introspect._git_info")
    @patch("megaplan.observability.introspect._editable_install_location")
    @patch("megaplan.observability.introspect._get_profiles_list")
    @patch("megaplan.observability.introspect._parse_decision_skill_profiles")
    @patch("megaplan.observability.introspect._process_tree")
    def test_evidence_window_heuristic_when_base_absent(
        self,
        mock_proc: MagicMock,
        mock_parse: MagicMock,
        mock_profiles: MagicMock,
        mock_editable: MagicMock,
        mock_git: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When milestone_base_sha is absent, source is heuristic_merge_base
        and changed_file_count stays None."""
        mock_git.return_value = {"branch": "main", "dirty": False, "head": "abc123"}
        mock_editable.return_value = "/fake/path"
        mock_profiles.return_value = ["solo"]
        mock_parse.return_value = ["solo"]
        mock_proc.return_value = []

        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)

        events = [
            _event(EventKind.INIT, now_ts - 10, seq=0),
        ]
        _write_events(plan_dir, events)

        # No chain_policy at all
        _write_state(plan_dir, {"current_state": "planning"})

        payload = build_introspect_payload(plan_dir)

        ev = payload["evidence"]
        assert ev["window"]["base_sha"] is None
        assert ev["window"]["head_sha"] == "abc123"
        assert ev["window"]["source"] == "heuristic_merge_base"
        assert ev["changed_file_count"] is None
        assert ev["repeated_divergence_fingerprint"] is None
        assert ev["carry_forward_declared"] is False

    @patch("megaplan.observability.introspect._git_info")
    @patch("megaplan.observability.introspect._editable_install_location")
    @patch("megaplan.observability.introspect._get_profiles_list")
    @patch("megaplan.observability.introspect._parse_decision_skill_profiles")
    @patch("megaplan.observability.introspect._process_tree")
    def test_evidence_carry_forward_declared_when_manifest_present(
        self,
        mock_proc: MagicMock,
        mock_parse: MagicMock,
        mock_profiles: MagicMock,
        mock_editable: MagicMock,
        mock_git: MagicMock,
        tmp_path: Path,
    ) -> None:
        """carry_forward_declared is True when carry_forward_manifest has a milestone_label."""
        mock_git.return_value = {"branch": "main", "dirty": False, "head": "abc123"}
        mock_editable.return_value = "/fake/path"
        mock_profiles.return_value = ["solo"]
        mock_parse.return_value = ["solo"]
        mock_proc.return_value = []

        now_ts = _now_epoch()
        plan_dir = _make_plan_dir(tmp_path)

        events = [
            _event(EventKind.INIT, now_ts - 10, seq=0),
        ]
        _write_events(plan_dir, events)

        state = {
            "current_state": "executing",
            "meta": {
                "chain_policy": {
                    "carry_forward_manifest": {
                        "milestone_label": "M1",
                        "base_sha": "base111",
                        "head_sha_at_start": "head222",
                        "inherited_file_count": 3,
                    }
                }
            },
        }
        _write_state(plan_dir, state)

        payload = build_introspect_payload(plan_dir)

        ev = payload["evidence"]
        assert ev["carry_forward_declared"] is True
        assert ev["window"]["source"] == "heuristic_merge_base"
