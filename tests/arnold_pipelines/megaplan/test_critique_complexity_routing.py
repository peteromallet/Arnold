"""Focused tests for the critique evaluator-to-tier compatibility boundary."""

from __future__ import annotations

import argparse

import pytest

from arnold_pipelines.megaplan.handlers.critique import _apply_adaptive_critique_routing
from arnold_pipelines.megaplan.types import CliError


def _args(table: dict[int | str, str], **extra: object) -> argparse.Namespace:
    return argparse.Namespace(tier_models={"critique": table}, **extra)


def _checks(*complexities: object) -> list[dict[str, object]]:
    return [
        {"id": f"check-{index}", "question": "Probe?", "complexity": complexity}
        for index, complexity in enumerate(complexities)
    ]


@pytest.fixture
def resolved_tier_spec(monkeypatch: pytest.MonkeyPatch):
    from arnold_pipelines.megaplan.execute import batch

    def resolve(_args: argparse.Namespace, spec: str, *, phase: str = "execute"):
        assert phase == "critique"
        agent, model = spec.split(":", 1)
        return agent, "fresh", model

    monkeypatch.setattr(batch, "_resolve_tier_spec", resolve)


def test_legacy_table_projects_complexity_7_to_tier_4(
    resolved_tier_spec: None,
) -> None:
    checks = _checks(7)
    _apply_adaptive_critique_routing(
        {"config": {}}, _args({1: "codex:t1", 2: "codex:t2", 3: "codex:t3", 4: "codex:t4", 5: "codex:t5"}), checks
    )

    assert checks[0]["_routing_evaluator_complexity"] == 7
    assert checks[0]["_routing_tier"] == 4
    assert checks[0]["_routing_selected_spec"] == "codex:t4"


def test_legacy_table_projects_complexity_10_to_tier_5(
    resolved_tier_spec: None,
) -> None:
    checks = _checks(10)
    _apply_adaptive_critique_routing(
        {"config": {}}, _args({str(i): f"codex:t{i}" for i in range(1, 6)}), checks
    )

    assert checks[0]["_routing_evaluator_complexity"] == 10
    assert checks[0]["_routing_tier"] == 5
    assert checks[0]["_routing_selected_spec"] == "codex:t5"


@pytest.mark.parametrize("complexity", [7, 10])
def test_current_table_routes_exact_tier(
    resolved_tier_spec: None, complexity: int,
) -> None:
    checks = _checks(complexity)
    _apply_adaptive_critique_routing(
        {"config": {}}, _args({i: f"codex:t{i}" for i in range(1, 11)}), checks
    )

    assert checks[0]["_routing_evaluator_complexity"] == complexity
    assert checks[0]["_routing_tier"] == complexity
    assert checks[0]["_routing_selected_spec"] == f"codex:t{complexity}"


@pytest.mark.parametrize("complexity", [0, 11, None, "7", True])
def test_invalid_evaluator_complexity_fails(complexity: object) -> None:
    with pytest.raises(CliError, match="1..10"):
        _apply_adaptive_critique_routing(
            {"config": {}}, _args({1: "codex:t1"}), _checks(complexity)
        )


def test_missing_projected_tier_without_pin_still_fails() -> None:
    with pytest.raises(CliError, match="complexity 7"):
        _apply_adaptive_critique_routing(
            {"config": {}}, _args({1: "codex:t1", 2: "codex:t2", 3: "codex:t3"}), _checks(7)
        )


def test_missing_exact_tier_without_pin_still_fails() -> None:
    with pytest.raises(CliError, match="complexity 10"):
        _apply_adaptive_critique_routing(
            {"config": {}}, _args({6: "codex:t6", 7: "codex:t7"}), _checks(10)
        )


def test_global_pin_fallback_still_works(resolved_tier_spec: None) -> None:
    checks = _checks(7)
    _apply_adaptive_critique_routing(
        {"config": {"critic_model_explicit": True, "critic_model": "deepseek-v4-pro"}},
        _args({1: "codex:t1"}),
        checks,
    )

    assert checks[0]["_routing_tier"] == 4
    assert checks[0]["_routing_evaluator_complexity"] == 7
    assert checks[0]["_routing_selected_spec"] == "critic_model:deepseek-v4-pro"
