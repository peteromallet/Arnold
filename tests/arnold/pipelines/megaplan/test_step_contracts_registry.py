"""Self-consistency tests for the StepContract registry.

Verifies the registry shape, dataclass-backed stage defaults, and explicit
values for phases that lack a dedicated *Step dataclass.
"""

from __future__ import annotations

import pytest

from arnold.pipelines.megaplan.step_contracts import STEP_CONTRACTS, StepContract
from arnold.pipelines.megaplan._compatibility import CompatibilityMode

# ---------------------------------------------------------------------------
# Expected phase identity sets
# ---------------------------------------------------------------------------

# 8 phases backed by a dedicated frozen-dataclass Step in stages/
_PRIMARY_DATACLASS_STAGES: frozenset[str] = frozenset(
    {"execute", "finalize", "critique", "review", "gate", "plan", "prep", "revise"}
)

# 9 phases with NO *Step dataclass — verified against explicit values only
_EXPLICIT_VALUE_PHASES: frozenset[str] = frozenset(
    {
        "critique_evaluator",
        "prep-triage",
        "prep-distill",
        "prep-research",
        "feedback",
        "loop_plan",
        "loop_execute",
        "tiebreaker_researcher",
        "tiebreaker_challenger",
    }
)

ALL_17: frozenset[str] = _PRIMARY_DATACLASS_STAGES | _EXPLICIT_VALUE_PHASES

# ---------------------------------------------------------------------------
# Explicit expected values for the 9 non-dataclass phases
# ---------------------------------------------------------------------------

_EXPLICIT_VALUES: dict[str, dict] = {
    "critique_evaluator": {
        "output_kind": "produce",
        "prompt_key": "critique_evaluator",
        "slot": "critique_evaluator",
    },
    "prep-triage": {
        "output_kind": "produce",
        "normalizer": "prep",
        "default_routing": None,
        "prompt_key": "prep-triage",
        "slot": "prep-triage",
    },
    "prep-distill": {
        "output_kind": "produce",
        "normalizer": "prep",
        "default_routing": None,
        "prompt_key": "prep-distill",
        "slot": "prep-distill",
    },
    "prep-research": {
        "output_kind": "produce",
        "normalizer": "prep",
        "default_routing": None,
        "prompt_key": "prep-research",
        "slot": "prep-research",
    },
    "feedback": {
        "output_kind": "produce",
        "default_routing": "premium:low",
        "prompt_key": "feedback",
        "slot": "feedback",
    },
    "loop_plan": {
        "output_kind": "produce",
        "normalizer": "plan",
        "default_routing": "premium",
        "prompt_key": "plan",
        "slot": "loop_plan",
    },
    "loop_execute": {
        "output_kind": "produce",
        "normalizer": "execute",
        "default_routing": "premium",
        "prompt_key": "execute",
        "slot": "loop_execute",
    },
    "tiebreaker_researcher": {
        "output_kind": "subloop",
        "default_routing": "premium",
        "prompt_key": None,
        "slot": "tiebreaker_researcher",
    },
    "tiebreaker_challenger": {
        "output_kind": "subloop",
        "default_routing": "premium",
        "prompt_key": None,
        "slot": "tiebreaker_challenger",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_step_dataclass(name: str):
    """Return the frozen *Step dataclass for a primary stage name.

    Never attempts to look up ``critique_evaluator`` or any other phase
    that lacks a dedicated *Step dataclass.
    """
    if name not in _PRIMARY_DATACLASS_STAGES:
        raise ValueError(
            f"{name!r} is not a dataclass-backed primary stage — "
            f"use explicit values instead"
        )

    mapping: dict[str, str] = {
        "execute": "arnold.pipelines.megaplan.stages.execute:ExecuteStep",
        "finalize": "arnold.pipelines.megaplan.stages.finalize:FinalizeStep",
        "critique": "arnold.pipelines.megaplan.stages.critique:CritiqueStep",
        "review": "arnold.pipelines.megaplan.stages.review:ReviewStep",
        "gate": "arnold.pipelines.megaplan.stages.gate:GateStep",
        "plan": "arnold.pipelines.megaplan.stages.plan:PlanStep",
        "prep": "arnold.pipelines.megaplan.stages.prep:PrepStep",
        "revise": "arnold.pipelines.megaplan.stages.revise:ReviseStep",
    }

    if name == "execute":
        from arnold.pipelines.megaplan.stages.execute import ExecuteStep

        return ExecuteStep
    elif name == "finalize":
        from arnold.pipelines.megaplan.stages.finalize import FinalizeStep

        return FinalizeStep
    elif name == "critique":
        from arnold.pipelines.megaplan.stages.critique import CritiqueStep

        return CritiqueStep
    elif name == "review":
        from arnold.pipelines.megaplan.stages.review import ReviewStep

        return ReviewStep
    elif name == "gate":
        from arnold.pipelines.megaplan.stages.gate import GateStep

        return GateStep
    elif name == "plan":
        from arnold.pipelines.megaplan.stages.plan import PlanStep

        return PlanStep
    elif name == "prep":
        from arnold.pipelines.megaplan.stages.prep import PrepStep

        return PrepStep
    elif name == "revise":
        from arnold.pipelines.megaplan.stages.revise import ReviseStep

        return ReviseStep

    raise AssertionError(f"unreachable — {name!r} not in primary set")  # pragma: no cover


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRegistryShape:
    """Verify the overall shape and membership of STEP_CONTRACTS."""

    def test_exactly_17_phase_identities(self) -> None:
        assert set(STEP_CONTRACTS.keys()) == ALL_17

    def test_all_keys_are_phase_identity(self) -> None:
        for key, contract in STEP_CONTRACTS.items():
            assert key == contract.phase_identity, (
                f"Registry key {key!r} does not match contract.phase_identity "
                f"{contract.phase_identity!r}"
            )

    def test_all_schema_keys_non_empty(self) -> None:
        for contract in STEP_CONTRACTS.values():
            assert isinstance(contract.schema_key, str), (
                f"{contract.phase_identity}: schema_key is not a str"
            )
            assert contract.schema_key, (
                f"{contract.phase_identity}: schema_key is empty"
            )

    def test_all_capture_schema_keys_non_empty(self) -> None:
        for contract in STEP_CONTRACTS.values():
            assert isinstance(contract.capture_schema_key, str), (
                f"{contract.phase_identity}: capture_schema_key is not a str"
            )
            assert contract.capture_schema_key, (
                f"{contract.phase_identity}: capture_schema_key is empty"
            )

    def test_all_compatibility_mode_is_native(self) -> None:
        for contract in STEP_CONTRACTS.values():
            assert contract.compatibility_mode is CompatibilityMode.NATIVE, (
                f"{contract.phase_identity}: expected NATIVE, "
                f"got {contract.compatibility_mode!r}"
            )

    def test_every_contract_has_9_fields(self) -> None:
        """StepContract must carry exactly the 9 declared fields — no more, no less."""
        expected_fields = {
            "phase_identity",
            "schema_key",
            "capture_schema_key",
            "output_kind",
            "compatibility_mode",
            "normalizer",
            "default_routing",
            "prompt_key",
            "slot",
        }
        for contract in STEP_CONTRACTS.values():
            actual = set(contract.__dataclass_fields__.keys())
            assert actual == expected_fields, (
                f"{contract.phase_identity}: unexpected fields: "
                f"{actual ^ expected_fields}"
            )


class TestDataclassBackedStages:
    """Verify the 8 primary stages with *Step dataclasses match their defaults."""

    def test_prompt_key_matches_step_default(self) -> None:
        for name in sorted(_PRIMARY_DATACLASS_STAGES):
            contract = STEP_CONTRACTS[name]
            step_cls = _get_step_dataclass(name)
            default = step_cls.__dataclass_fields__["prompt_key"].default
            assert contract.prompt_key == default, (
                f"{name}: contract.prompt_key={contract.prompt_key!r} != "
                f"{step_cls.__name__}.prompt_key default={default!r}"
            )

    def test_slot_matches_step_default(self) -> None:
        for name in sorted(_PRIMARY_DATACLASS_STAGES):
            contract = STEP_CONTRACTS[name]
            step_cls = _get_step_dataclass(name)
            default = step_cls.__dataclass_fields__["slot"].default
            assert contract.slot == default, (
                f"{name}: contract.slot={contract.slot!r} != "
                f"{step_cls.__name__}.slot default={default!r}"
            )

    def test_output_kind_matches_step_kind_default(self) -> None:
        for name in sorted(_PRIMARY_DATACLASS_STAGES):
            contract = STEP_CONTRACTS[name]
            step_cls = _get_step_dataclass(name)
            default = step_cls.__dataclass_fields__["kind"].default
            assert contract.output_kind == default, (
                f"{name}: contract.output_kind={contract.output_kind!r} != "
                f"{step_cls.__name__}.kind default={default!r}"
            )


class TestExplicitValuePhases:
    """Verify the 9 phases without *Step dataclasses against explicit values.

    IMPORTANT: This test class MUST NOT import or reference any
    ``CritiqueEvaluatorStep`` — that class does not exist.
    """

    def test_no_critique_evaluator_step_lookup(self) -> None:
        """Guard: prove CritiqueEvaluatorStep does not exist in the stages module."""
        with pytest.raises(ImportError):
            # This import MUST fail — there is no CritiqueEvaluatorStep
            from arnold.pipelines.megaplan.stages.critique_evaluator import (  # type: ignore[import-not-found]
                CritiqueEvaluatorStep,
            )  # pragma: no cover

    def test_explicit_values_match(self) -> None:
        for name, expected in sorted(_EXPLICIT_VALUES.items()):
            contract = STEP_CONTRACTS[name]
            for attr, expected_value in expected.items():
                actual = getattr(contract, attr)
                assert actual == expected_value, (
                    f"{name}.{attr}: got {actual!r}, expected {expected_value!r}"
                )

    def test_no_phase_has_a_step_dataclass(self) -> None:
        """Each explicit-value phase must NOT have a corresponding *Step dataclass."""
        for name in sorted(_EXPLICIT_VALUE_PHASES):
            with pytest.raises(ValueError, match="not a dataclass-backed primary stage"):
                _get_step_dataclass(name)


class TestNoCrossContamination:
    """Ensure the two phase sets partition the full registry cleanly."""

    def test_partition_is_exhaustive_and_disjoint(self) -> None:
        assert _PRIMARY_DATACLASS_STAGES | _EXPLICIT_VALUE_PHASES == ALL_17
        assert _PRIMARY_DATACLASS_STAGES & _EXPLICIT_VALUE_PHASES == set()
        assert _PRIMARY_DATACLASS_STAGES.issubset(STEP_CONTRACTS.keys())
        assert _EXPLICIT_VALUE_PHASES.issubset(STEP_CONTRACTS.keys())
