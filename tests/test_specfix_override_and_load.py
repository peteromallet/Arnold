"""Specfix: override set-vendor, and load-time validation of persisted
phase_model routing pins.

Companion to the parse_agent_spec semantic-validation regression tests in
tests/test_types_schemas.py — these cover the operator-facing surfaces that
remove the hand-edit vector (set-vendor) and surface an already-corrupt plan
loudly (load-time validation).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import megaplan
from megaplan._core import load_plan
from megaplan._core.state import load_plan_from_dir
from megaplan.types import CliError
from tests.conftest import PlanFixture


def _init_plan(plan_fixture: PlanFixture) -> tuple[Path, dict]:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    return load_plan(plan_fixture.root, plan_fixture.plan_name)


def test_override_set_vendor_swaps_premium_vendor_cleanly(
    plan_fixture: PlanFixture,
) -> None:
    """set-vendor re-points a phase from claude -> codex via the clean swap
    logic (no hand-edited spec string)."""
    plan_dir, state = _init_plan(plan_fixture)
    # Seed a persisted claude pin for critique.
    state["config"]["phase_model"] = ["critique=claude:low"]
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    args = plan_fixture.make_args(
        plan=plan_fixture.plan_name,
        override_action="set-vendor",
        phase="critique",
        vendor="codex",
    )
    response = megaplan.handle_override(plan_fixture.root, args)

    assert response["success"] is True
    assert response["new_spec"] == "codex:low", response
    # Persisted state reflects the swap.
    _, reloaded = load_plan(plan_fixture.root, plan_fixture.plan_name)
    pins = {pm.split("=", 1)[0]: pm.split("=", 1)[1] for pm in reloaded["config"]["phase_model"]}
    assert pins["critique"] == "codex:low"


def test_override_set_vendor_rejects_bad_vendor(plan_fixture: PlanFixture) -> None:
    _init_plan(plan_fixture)
    args = plan_fixture.make_args(
        plan=plan_fixture.plan_name,
        override_action="set-vendor",
        phase="critique",
        vendor="nonsense",
    )
    with pytest.raises(CliError):
        megaplan.handle_override(plan_fixture.root, args)


def test_override_set_vendor_requires_phase_and_vendor(plan_fixture: PlanFixture) -> None:
    _init_plan(plan_fixture)
    with pytest.raises(CliError, match="requires --phase"):
        megaplan.handle_override(
            plan_fixture.root,
            plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="set-vendor", vendor="codex"),
        )
    with pytest.raises(CliError, match="requires --vendor"):
        megaplan.handle_override(
            plan_fixture.root,
            plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="set-vendor", phase="critique"),
        )


def test_load_plan_rejects_corrupt_persisted_phase_model(
    plan_fixture: PlanFixture,
) -> None:
    """An already-persisted malformed routing pin (the original bug:
    ``critique=codex:claude:sonnet``) must surface loudly on the next load,
    not mis-dispatch silently."""
    plan_dir, state = _init_plan(plan_fixture)
    state["config"]["phase_model"] = ["critique=codex:claude:sonnet"]
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(CliError) as exc:
        load_plan_from_dir(plan_dir)
    assert exc.value.code == "corrupt_phase_model"
    assert "critique" in str(exc.value)
    assert "codex:claude:sonnet" in str(exc.value)


def test_load_plan_accepts_clean_persisted_phase_model(
    plan_fixture: PlanFixture,
) -> None:
    plan_dir, state = _init_plan(plan_fixture)
    state["config"]["phase_model"] = ["critique=codex:high", "plan=claude:claude-opus-4-7"]
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    # Must not raise.
    _, reloaded = load_plan_from_dir(plan_dir)
    assert reloaded["config"]["phase_model"][0] == "critique=codex:high"
