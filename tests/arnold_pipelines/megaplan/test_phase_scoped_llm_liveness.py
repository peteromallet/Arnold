"""Regression coverage for phase-scoped LLM liveness."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from arnold_pipelines.megaplan.observability.introspect import _compute_liveness, _process_tree
from arnold_pipelines.megaplan.observability.liveness import unmatched_llm_starts
from arnold_pipelines.megaplan.watchdog.signals import compute_signal_bundle


def _event(
    kind: str,
    at: datetime,
    *,
    phase: str,
    model: str,
    request_id: str | None = None,
) -> dict:
    return {
        "kind": kind,
        "ts_utc": at.isoformat(),
        "phase": phase,
        "payload": {"model": model, "request_id": request_id},
    }


def _review_state(started: datetime) -> dict:
    return {
        "active_step": {
            "phase": "review",
            "model": "gpt-5.4",
            "started_at": started.isoformat(),
        }
    }


def test_cross_phase_in_flight_llm_cannot_mask_stalled_active_phase(tmp_path: Path) -> None:
    """A lost execute/DeepSeek end must not keep review/Codex progressing."""
    now = datetime.now(timezone.utc)
    stale = now - timedelta(seconds=360)
    state = _review_state(now - timedelta(seconds=500))
    events = [_event("llm_call_start", stale, phase="execute", model="deepseek-v4")]

    liveness, reason = _compute_liveness(events, tmp_path, state, now.timestamp())

    assert liveness == "stalled"
    assert "no in-flight LLM" in reason

    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(__import__("json").dumps(state), encoding="utf-8")
    (plan_dir / "events.ndjson").write_text(
        __import__("json").dumps(events[0]) + "\n", encoding="utf-8"
    )
    signals = compute_signal_bundle(plan_dir, state)

    assert signals.liveness == "stalled"
    assert signals.has_in_flight_llm is False


def test_matching_active_phase_and_model_in_flight_llm_is_progressing(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    state = _review_state(now - timedelta(seconds=360))
    events = [_event("llm_call_start", now - timedelta(seconds=180), phase="review", model="gpt-5.4")]

    liveness, reason = _compute_liveness(events, tmp_path, state, now.timestamp())

    assert liveness == "progressing"
    assert "in-flight LLM call" in reason


def test_same_phase_wrong_model_in_flight_llm_cannot_mask_stall(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    state = _review_state(now - timedelta(seconds=500))
    events = [_event("llm_call_start", now - timedelta(seconds=360), phase="review", model="deepseek-v4")]

    liveness, _ = _compute_liveness(events, tmp_path, state, now.timestamp())

    assert liveness == "stalled"


def test_matched_call_transaction_is_not_left_in_flight() -> None:
    now = datetime.now(timezone.utc)
    start = _event("llm_call_start", now - timedelta(seconds=120), phase="gate", model="deepseek-v4")
    end = _event("llm_call_end", now - timedelta(seconds=60), phase="gate", model="deepseek-v4")
    start["payload"]["call_transaction_id"] = "call-7"
    end["payload"]["call_transaction_id"] = "call-7"
    assert unmatched_llm_starts([start, end]) == []


def test_legacy_requestless_start_is_closed_by_same_phase_end() -> None:
    now = datetime.now(timezone.utc)
    start = _event("llm_call_start", now - timedelta(seconds=120), phase="gate", model="deepseek-v4")
    end = _event(
        "llm_call_end",
        now - timedelta(seconds=60),
        phase="gate",
        model="deepseek-v4",
        request_id="known-only-at-end",
    )
    assert unmatched_llm_starts([start, end]) == []


def test_introspection_process_discovery_excludes_self_and_unrelated_prompt(monkeypatch) -> None:
    class Proc:
        def __init__(self, pid, cmdline):
            self.info = {"pid": pid, "ppid": 1, "cmdline": cmdline, "create_time": 1.0}

    class Psutil:
        @staticmethod
        def process_iter(_fields):
            return [
                Proc(1, ["python", "-m", "arnold_pipelines.megaplan", "introspect", "--plan", "demo"]),
                Proc(2, ["codex", "exec", "please inspect megaplan plan demo"]),
                Proc(3, ["python", "-m", "arnold_pipelines.megaplan", "revise", "--plan", "demo"]),
            ]

    monkeypatch.setitem(__import__("sys").modules, "psutil", Psutil)
    assert [item["pid"] for item in _process_tree("demo")] == [3]


def test_requestless_start_is_closed_by_later_same_phase_end() -> None:
    now = datetime.now(timezone.utc)
    events = [
        _event("llm_call_start", now - timedelta(seconds=180), phase="execute", model="gpt-5.6-sol"),
        _event(
            "llm_call_end",
            now - timedelta(seconds=60),
            phase="execute",
            model="gpt-5.4",
            request_id="provider-id-known-only-at-end",
        ),
    ]

    assert unmatched_llm_starts(events) == []


def test_sequential_requestless_calls_leave_only_latest_start_in_flight() -> None:
    now = datetime.now(timezone.utc)
    first_start = _event(
        "llm_call_start", now - timedelta(seconds=240), phase="execute", model="gpt-5.6-sol"
    )
    latest_start = _event(
        "llm_call_start", now - timedelta(seconds=30), phase="execute", model="gpt-5.6-sol"
    )
    events = [
        first_start,
        _event(
            "llm_call_end",
            now - timedelta(seconds=120),
            phase="execute",
            model="gpt-5.4",
            request_id="provider-id-known-only-at-end",
        ),
        latest_start,
    ]

    assert unmatched_llm_starts(events) == [latest_start]
