from __future__ import annotations

from pathlib import Path

import pytest

import megaplan
from megaplan._core import load_plan
from megaplan.types import CliError
from tests.test_handle_review_robustness import PlanFixture, _advance_to_executed, _make_plan_fixture


def _artifact_names(plan_dir: Path) -> set[str]:
    return {path.name for path in plan_dir.iterdir() if path.is_file()}


def _advance_tiny_to_executed(fixture: PlanFixture) -> dict[str, object]:
    args = fixture.make_args(plan=fixture.plan_name)
    megaplan.handle_plan(fixture.root, args)
    megaplan.handle_finalize(fixture.root, args)
    execute = megaplan.handle_execute(
        fixture.root,
        fixture.make_args(plan=fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    _plan_dir, final_state = load_plan(fixture.root, fixture.plan_name)
    return {"state": final_state, "execute": execute}


def test_tiny_robustness_skips_critique_and_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tiny_fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="tiny")

    _plan_dir, tiny_initial_state = load_plan(tiny_fixture.root, tiny_fixture.plan_name)
    # From INITIALIZED at tiny, next valid step is plan (not prep).
    assert "plan" in megaplan.infer_next_steps(tiny_initial_state)

    # Drive the plan through to DONE.
    result = _advance_tiny_to_executed(tiny_fixture)

    # After plan, the only valid next step is finalize (critique is bypassed).
    # We can't easily snapshot mid-flight here, but we can assert the terminal
    # artifact set: no critique_v*.json files were produced.
    tiny_artifacts = _artifact_names(tiny_fixture.plan_dir)
    assert not any(name.startswith("critique_v") for name in tiny_artifacts), (
        f"tiny should not produce critique artifacts, got: {sorted(tiny_artifacts)}"
    )
    assert "review.json" not in tiny_artifacts
    assert "plan_v1.md" in tiny_artifacts
    assert "finalize.json" in tiny_artifacts
    assert "state.json" in tiny_artifacts

    # Final state is DONE; no review fired.
    assert result["execute"]["state"] == megaplan.STATE_DONE
    assert result["state"]["current_state"] == megaplan.STATE_DONE
    assert "review" not in megaplan.infer_next_steps(
        {"current_state": megaplan.STATE_EXECUTED, "last_gate": {}, "config": {"robustness": "tiny"}}
    )


def test_tiny_robustness_rejects_manual_critique(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling `megaplan critique` at tiny should error — the phase is skipped."""
    fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="tiny")
    megaplan.handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))

    with pytest.raises(CliError, match="bare robustness skips critique"):
        megaplan.handle_critique(fixture.root, fixture.make_args(plan=fixture.plan_name))


def test_tiny_parity_with_light_terminates_in_done(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both tiny and light end in STATE_DONE after execute (no review phase)."""
    tiny_fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="tiny")
    light_fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="light")
    standard_fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="standard")

    _advance_tiny_to_executed(tiny_fixture)
    _advance_to_executed(light_fixture)
    _advance_to_executed(standard_fixture)

    _plan_dir, tiny_final = load_plan(tiny_fixture.root, tiny_fixture.plan_name)
    _plan_dir, light_final = load_plan(light_fixture.root, light_fixture.plan_name)
    _plan_dir, standard_final = load_plan(standard_fixture.root, standard_fixture.plan_name)

    assert tiny_final["current_state"] == megaplan.STATE_DONE
    assert light_final["current_state"] == megaplan.STATE_DONE
    # standard halts at EXECUTED awaiting review (review fires separately).
    assert standard_final["current_state"] == megaplan.STATE_EXECUTED
