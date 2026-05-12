from __future__ import annotations

from pathlib import Path

import pytest

import megaplan
import megaplan.handlers
import megaplan.workers
from megaplan._core import load_plan
from megaplan.workers import WorkerResult, _build_mock_payload
from tests.conftest import PlanFixture, _make_plan_fixture_with_robustness, load_state


def test_tiny_critique_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """At tiny robustness, calling critique manually errors — the phase is skipped
    in the workflow, so plan -> finalize is the canonical path."""
    from megaplan.types import CliError

    fixture = _make_plan_fixture_with_robustness(tmp_path, monkeypatch, robustness="tiny")
    megaplan.handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))

    with pytest.raises(CliError, match="tiny robustness skips critique"):
        megaplan.handle_critique(fixture.root, fixture.make_args(plan=fixture.plan_name))


def test_light_critique_routes_to_revise(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_fixture = _make_plan_fixture_with_robustness(tmp_path, monkeypatch, robustness="light")
    make_args = plan_fixture.make_args

    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)

    assert response["next_step"] == "revise"
    assert state["last_gate"]["recommendation"] == "ITERATE"


def test_handle_critique_rejects_invalid_check_payload(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    worker = WorkerResult(
        payload=_build_mock_payload(
            "critique",
            load_state(plan_fixture.plan_dir),
            plan_fixture.plan_dir,
            checks=[],
        ),
        raw_output="invalid critique payload",
        duration_ms=1,
        cost_usd=0.0,
        session_id="critique-invalid",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )
    monkeypatch.setattr(
        megaplan.handlers,
        "validate_critique_checks",
        lambda payload, **kwargs: ["correctness"],
    )

    with pytest.raises(megaplan.CliError, match="Critique output failed check validation"):
        megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    state = load_state(plan_fixture.plan_dir)
    assert state["history"][-1]["result"] == "error"
    assert state.get("active_step") is None
    assert not (plan_fixture.plan_dir / "critique_v1.json").exists()


def test_handle_critique_accepts_validated_checks(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        megaplan.handlers.critique,
        "validate_critique_checks",
        lambda payload, **kwargs: [],
    )

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    assert response["success"] is True
    assert (plan_fixture.plan_dir / "critique_v1.json").exists()


def test_parallel_critique_sets_and_clears_active_step(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        megaplan.handlers.critique,
        "validate_critique_checks",
        lambda payload, **kwargs: [],
    )
    monkeypatch.setattr(
        megaplan.handlers,
        "resolve_agent_mode",
        lambda step, args: ("hermes", "persistent", False, "fireworks:accounts/fireworks/models/kimi-k2p6"),
    )

    observed: dict[str, str] = {}

    def fake_parallel(state, plan_dir, *, root, model, checks, max_concurrent=None):
        persisted = load_state(plan_dir)
        observed.update(persisted["active_step"])
        return WorkerResult(
            payload={
                "checks": [
                    {
                        "id": check["id"],
                        "summary": "ok",
                        "findings": [],
                    }
                    for check in checks
                ],
                "flags": [],
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
            },
            raw_output="parallel",
            duration_ms=1,
            cost_usd=0.0,
            session_id=None,
        )

    monkeypatch.setattr(megaplan.handlers.critique, "run_parallel_critique", fake_parallel)

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)

    assert response["success"] is True
    assert observed["step"] == "critique"
    assert observed["agent"] == "hermes"
    assert observed["model"] == "fireworks:accounts/fireworks/models/kimi-k2p6"
    assert "active_step" not in state


def test_critique_prompt_contains_robustness_instruction(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    _, state = load_plan(plan_fixture.root, plan_fixture.plan_name)
    from megaplan.prompts import create_claude_prompt

    prompt = create_claude_prompt("critique", state, plan_fixture.plan_dir)
    assert "Robustness level" in prompt
    assert "standard" in prompt
