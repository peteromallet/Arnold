"""A dead tmux server mid-turn must be a RETRYABLE worker_stall, not internal_error.

Root cause (m7-agent-runtime-extraction, 2026-06-09): the vendored Shannon
launcher drives Claude in tmux; when the tmux server dies during the
``waitForPrompt`` startup poll it prints
``tmux capture-pane -pt <id> -S -40 failed with 1: no server running`` and the
only surviving stdout is Claude's ``{"type":"system","subtype":"init",...}``
line. ``_parse_shannon_output`` then found no result envelope, the init line was
misparsed as the "result", and the phase surfaced a NON-retryable
``internal_error`` that looped forever (while the edits had already landed on
disk). The guard classifies the dead-tmux signature as a retryable
``worker_stall`` so the next attempt sheds the session and spawns fresh — which
is what a healthy run gets organically.
"""
from __future__ import annotations

import pytest

from arnold.pipelines.megaplan.runtime.process import TmuxSession
from arnold.pipelines.megaplan.types import CliError
from arnold.pipelines.megaplan.workers.shannon import (
    _matched_tmux_died_marker,
    _raw_contains_success_result,
    _raw_indicates_tmux_died,
    _readiness_session_recovered,
)

# The exact line the vendored launcher emitted for the m7 failure.
M7_DEAD_TMUX_RAW = (
    '{"type":"system","subtype":"init","slash_commands":["babysit","loop"],'
    '"plugins":[],"uuid":"11d4be90-5260-4b42-b518-9f2942600f2a"}\n'
    "tmux capture-pane -pt 4c44d884689a -S -40 failed with 1: "
    "no server running on /private/tmp/tmux-501/default"
)

SUCCESS_RAW = '{"type":"result","subtype":"success","result":"{\\"ok\\":true}"}'


def test_m7_dead_tmux_signature_is_detected() -> None:
    assert _raw_indicates_tmux_died(M7_DEAD_TMUX_RAW) is True
    # ...and it carries no success envelope, so the guard fires.
    assert _raw_contains_success_result(M7_DEAD_TMUX_RAW) is False


def test_other_tmux_death_markers_detected() -> None:
    for marker in (
        "no current client",
        "no current target",
        "can't find session",
        "session not found",
        "lost server",
    ):
        raw = f"tmux capture-pane failed: {marker}"
        assert _raw_indicates_tmux_died(raw) is True, marker


# ---------------------------------------------------------------------------
# Defect 1: the LIVE readiness-probe failure was exactly this line. It must be
# recognised as a dead-session signature (the prior _TMUX_DIED_MARKERS set
# lacked "no current target", so it fell through to a non-retryable worker_error
# that looped at iter 7).
# ---------------------------------------------------------------------------

LIVE_READINESS_DEAD_RAW = (
    "tmux -L mp-9352a98c0ce0 capture-pane -pt 9352a98c0ce0 -S -40 "
    "failed with 1: no current target"
)


def test_live_no_current_target_is_a_tmux_death_signature() -> None:
    assert _raw_indicates_tmux_died(LIVE_READINESS_DEAD_RAW) is True
    assert _raw_contains_success_result(LIVE_READINESS_DEAD_RAW) is False


def test_matched_marker_reports_the_concrete_marker() -> None:
    assert _matched_tmux_died_marker(LIVE_READINESS_DEAD_RAW) == "no current target"
    assert _matched_tmux_died_marker(M7_DEAD_TMUX_RAW) == "no server running"
    assert _matched_tmux_died_marker("nothing relevant here") == ""


def test_clean_success_not_flagged_as_tmux_death() -> None:
    assert _raw_indicates_tmux_died(SUCCESS_RAW) is False
    assert _raw_contains_success_result(SUCCESS_RAW) is True


def test_empty_and_unrelated_not_flagged() -> None:
    assert _raw_indicates_tmux_died("") is False
    # A mention of tmux without a death marker must not trip it.
    assert _raw_indicates_tmux_died("I ran `tmux ls` and the session was fine") is False
    # A death-marker phrase without any tmux/capture-pane context must not trip it
    # (avoids flagging unrelated agent prose).
    assert _raw_indicates_tmux_died("the database had no server running at boot") is False


# ---------------------------------------------------------------------------
# Defect 1: bounded startup-race re-poll. A dead capture is re-checked a few
# times before we conclude the turn really died; a session that comes back with
# painted output is treated as recovered (no needless retry).
# ---------------------------------------------------------------------------


def test_recover_returns_true_when_session_comes_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import arnold.pipelines.megaplan.workers.shannon as _mod

    session = TmuxSession("recover-test")
    monkeypatch.setattr(session, "exists", lambda: True)
    monkeypatch.setattr(_mod, "_tmux_capture_pane", lambda _n: "❯ Welcome to Claude")
    # No real sleeping in the test.
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_DEAD_RECHECK_INTERVAL_S", "0")
    assert _readiness_session_recovered(session) is True


def test_recover_returns_false_when_session_stays_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import arnold.pipelines.megaplan.workers.shannon as _mod

    session = TmuxSession("dead-test")
    monkeypatch.setattr(session, "exists", lambda: False)
    monkeypatch.setattr(_mod, "_tmux_capture_pane", lambda _n: None)
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_DEAD_RECHECK_ATTEMPTS", "2")
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_DEAD_RECHECK_INTERVAL_S", "0")
    assert _readiness_session_recovered(session) is False


def test_recover_false_when_session_alive_but_pane_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alive but blank pane is NOT recovered — claude never painted output."""
    import arnold.pipelines.megaplan.workers.shannon as _mod

    session = TmuxSession("blank-test")
    monkeypatch.setattr(session, "exists", lambda: True)
    monkeypatch.setattr(_mod, "_tmux_capture_pane", lambda _n: "   \n")
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_DEAD_RECHECK_ATTEMPTS", "2")
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_DEAD_RECHECK_INTERVAL_S", "0")
    assert _readiness_session_recovered(session) is False


# ---------------------------------------------------------------------------
# Defect 1: end-to-end retryability. THE bug — a worker_error for "no current
# target" classified to external_error=None (=> internal_error, loops). The fix
# raises worker_stall, which classifies to a retryable worker_stream_stall layer.
# ---------------------------------------------------------------------------


def test_dead_turn_worker_stall_is_retryable_external_error() -> None:
    from arnold.pipelines.megaplan.auto import _is_retryable_external_error
    from arnold.pipelines.megaplan.orchestration.phase_result import ExternalError
    from arnold.pipelines.megaplan.orchestration.phase_result_classify import (
        classify_external_error_payload,
    )

    err = CliError(
        "worker_stall",
        "Shannon readiness probe: the claude tmux session died during startup "
        "(tmux reported a dead session/window: no current target).",
        extra={"error_layer": "worker_stream_stall", "session_id": "x"},
    )
    payload = classify_external_error_payload(err)
    assert payload is not None
    assert payload["error_layer"] == "worker_stream_stall"
    ext = ExternalError.from_dict(payload)
    assert _is_retryable_external_error("finalize", ext) is True


def test_old_worker_error_for_no_current_target_was_not_retryable() -> None:
    """Regression witness: the OLD code raised worker_error here and it
    classified to None (=> internal_error, looped)."""
    from arnold.pipelines.megaplan.orchestration.phase_result_classify import (
        classify_external_error_payload,
    )

    old = CliError(
        "worker_error",
        "Shannon readiness probe failed with exit code 1",
        extra={"raw_output": LIVE_READINESS_DEAD_RAW},
    )
    assert classify_external_error_payload(old) is None
