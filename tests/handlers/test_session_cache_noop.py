from __future__ import annotations

import argparse
from pathlib import Path

import pytest

import megaplan
from megaplan._core import atomic_write_json
from megaplan.types import STATE_CRITIQUED
from megaplan.workers import WorkerResult, _build_mock_payload
from tests.conftest import PlanFixture, load_state


def _mark_for_revise(plan_fixture: PlanFixture) -> None:
    state = load_state(plan_fixture.plan_dir)
    state["current_state"] = STATE_CRITIQUED
    state["last_gate"] = {"recommendation": "ITERATE"}
    atomic_write_json(plan_fixture.plan_dir / "state.json", state)
    atomic_write_json(
        plan_fixture.plan_dir / "gate.json",
        {
            "recommendation": "ITERATE",
            "rationale": "test loop",
            "signals_assessment": "test loop",
            "warnings": [],
            "settled_decisions": [],
        },
    )


def _worker_with_plan(
    state: dict,
    plan_dir: Path,
    plan_text: str,
    session_id: str,
    *,
    cost_usd: float = 0.01,
) -> WorkerResult:
    payload = _build_mock_payload("revise", state, plan_dir)
    payload["plan"] = plan_text
    return WorkerResult(
        payload=payload,
        raw_output="{}",
        duration_ms=25,
        cost_usd=cost_usd,
        session_id=session_id,
        rendered_prompt=f"revise prompt {session_id}",
        prompt_tokens=123,
        completion_tokens=45,
        total_tokens=168,
    )


def test_revise_noop_detector_raises_cache_hit_suspected(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_gate(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    state = load_state(plan_fixture.plan_dir)
    duplicate_plan = (
        _build_mock_payload("revise", state, plan_fixture.plan_dir)["plan"].rstrip()
        + "\n\n## Stable Marker\nsame\n"
    )
    sessions = iter(["revise-session-1", "revise-session-2"])

    def fake_run_step_with_worker(
        step: str,
        state: dict,
        plan_dir: Path,
        args: argparse.Namespace,
        **kwargs: object,
    ):
        assert step == "revise"
        session_id = next(sessions)
        return _worker_with_plan(state, plan_dir, duplicate_plan, session_id), "codex", "persistent", True

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step_with_worker)

    _mark_for_revise(plan_fixture)
    megaplan.handle_revise(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    _mark_for_revise(plan_fixture)
    with pytest.raises(megaplan.CliError) as exc_info:
        megaplan.handle_revise(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    error = exc_info.value
    assert error.code == "cache_hit_suspected"
    assert error.extra["step"] == "revise"
    assert error.extra["prior_version"] == 2
    assert error.extra["prior_hash"] == error.extra["new_hash"]
    assert error.extra["session_id"] == "revise-session-2"
    assert error.extra["duration_ms"] == 25
    assert error.extra["prompt_tokens"] == 123
    assert error.extra["completion_tokens"] == 45
    assert error.extra["ticket"] == "01KRXNZZGRV17PHZRJ2Q56SPS3"


def test_revise_cost_sanity_guard_aborts(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_gate(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    def fake_run_step_with_worker(
        step: str,
        state: dict,
        plan_dir: Path,
        args: argparse.Namespace,
        **kwargs: object,
    ):
        plan_text = _build_mock_payload("revise", state, plan_dir)["plan"] + "\nexpensive\n"
        return (
            _worker_with_plan(state, plan_dir, plan_text, "expensive-session", cost_usd=5.01),
            "codex",
            "persistent",
            True,
        )

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step_with_worker)

    _mark_for_revise(plan_fixture)
    with pytest.raises(megaplan.CliError) as exc_info:
        megaplan.handle_revise(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    assert exc_info.value.code == "revise_cost_sanity_guard"
    assert exc_info.value.extra["ticket"] == "01KRXNZZGRV17PHZRJ2Q56SPS3"
