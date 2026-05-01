from __future__ import annotations

import inspect
from pathlib import Path

from megaplan._core import atomic_write_json, read_json
from megaplan.handlers.review import _resolve_review_outcome
from megaplan.types import STATE_DONE, STATE_FINALIZED


def _write_finalize(plan_dir: Path, *, requested: bool) -> None:
    atomic_write_json(
        plan_dir / "finalize.json",
        {
            "tasks": [
                {
                    "id": "T1",
                    "stop_signal": {
                        "requested": requested,
                        "defense": "The next pass would damage the live edge.",
                    },
                }
            ]
        },
    )


def test_resolve_review_outcome_first_positional_is_plan_dir() -> None:
    first = next(iter(inspect.signature(_resolve_review_outcome).parameters.values()))
    assert first.name == "plan_dir"


def test_creative_stop_signal_short_circuits_needs_rework(tmp_path: Path) -> None:
    _write_finalize(tmp_path, requested=True)
    atomic_write_json(
        tmp_path / "directors_notes.json",
        {"form": "poem", "primary_criterion": "", "passes": [{"iteration": 1}]},
    )
    state = {"config": {"mode": "creative", "form": "poem"}, "history": [], "meta": {}}

    result = _resolve_review_outcome(tmp_path, "needs_rework", 1, 1, 0, 0, [], "standard", state, [])

    assert result == ("success", STATE_DONE, None)
    assert "damage the live edge" in state["meta"]["notes"][0]["note"]
    assert read_json(tmp_path / "directors_notes.json")["passes"][-1]["stop_requested"] is True


def test_creative_without_stop_signal_requests_rework(tmp_path: Path) -> None:
    _write_finalize(tmp_path, requested=False)
    state = {"config": {"mode": "creative", "form": "poem"}, "history": [], "meta": {}}

    result = _resolve_review_outcome(tmp_path, "needs_rework", 1, 1, 0, 0, [], "standard", state, [])

    assert result == ("needs_rework", STATE_FINALIZED, "execute")


def test_code_mode_stop_signal_does_not_short_circuit(tmp_path: Path) -> None:
    _write_finalize(tmp_path, requested=True)
    state = {"config": {"mode": "code"}, "history": [], "meta": {}}

    result = _resolve_review_outcome(tmp_path, "needs_rework", 1, 1, 0, 0, [], "standard", state, [])

    assert result == ("needs_rework", STATE_FINALIZED, "execute")
