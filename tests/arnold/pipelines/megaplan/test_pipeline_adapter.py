"""Tests for Megaplan → canonical pipeline adapter (Step 4 / T5 / SC5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)
from arnold.pipelines.megaplan._pipeline.adapter import (
    from_canonical_step_context,
    to_canonical_pipeline,
    to_canonical_step_context,
)
from arnold.pipelines.megaplan._pipeline.envelope import EMPTY_ENVELOPE, RunEnvelope
from arnold.pipelines.megaplan._pipeline.types import (
    Edge as MegaplanEdge,
    ParallelStage as MegaplanParallelStage,
    Pipeline as MegaplanPipeline,
    Stage as MegaplanStage,
    StepContext as MegaplanStepContext,
    Step as MegaplanStep,
)


# ---------------------------------------------------------------------------
# Minimal Megaplan Step for tests
# ---------------------------------------------------------------------------


class _FakeMegaplanStep:
    """A minimal step satisfying the Megaplan Step Protocol."""

    def __init__(self, name: str, kind: str = "produce") -> None:
        self.name = name
        self.kind = kind
        self.prompt_key = None
        self.slot = None
        self.produces: tuple[Any, ...] = ()
        self.consumes: tuple[Any, ...] = ()

    def run(self, ctx: MegaplanStepContext) -> Any:
        return type(
            "FakeStepResult",
            (),
            {
                "outputs": {},
                "verdict": None,
                "next": "halt",
                "state_patch": {},
                "contract_result": None,
                "envelope": ctx.envelope,
            },
        )()


def _simple_join(results: list[Any], ctx: Any) -> StepResult:
    return StepResult(next="halt", outputs={"count": len(results)})


# ---------------------------------------------------------------------------
# Pipeline conversion tests
# ---------------------------------------------------------------------------


class TestToCanonicalPipeline:
    """Structural equivalence tests for to_canonical_pipeline."""

    def test_minimal_two_stage_pipeline(self) -> None:
        """A minimal two-stage Megaplan pipeline maps correctly."""
        step_a = _FakeMegaplanStep("a")
        step_b = _FakeMegaplanStep("b")
        mp = MegaplanPipeline(
            stages={
                "a": MegaplanStage(
                    name="a",
                    step=step_a,
                    edges=(MegaplanEdge(label="next", target="b"),),
                ),
                "b": MegaplanStage(name="b", step=step_b, edges=()),
            },
            entry="a",
        )

        cp = to_canonical_pipeline(mp)

        assert isinstance(cp, Pipeline)
        assert cp.entry == "a"
        assert len(cp.stages) == 2
        assert "a" in cp.stages
        assert "b" in cp.stages

        stage_a = cp.stages["a"]
        assert isinstance(stage_a, Stage)
        assert stage_a.name == "a"
        assert stage_a.step is step_a  # same reference
        assert len(stage_a.edges) == 1
        assert stage_a.edges[0].label == "next"
        assert stage_a.edges[0].target == "b"

    def test_parallel_stage_conversion(self) -> None:
        """ParallelStage maps field-for-field."""
        step1 = _FakeMegaplanStep("p1")
        step2 = _FakeMegaplanStep("p2")
        mp = MegaplanPipeline(
            stages={
                "fan": MegaplanParallelStage(
                    name="fan",
                    steps=(step1, step2),
                    join=_simple_join,
                    edges=(MegaplanEdge(label="next", target="halt"),),
                    max_workers=4,
                ),
            },
            entry="fan",
        )

        cp = to_canonical_pipeline(mp)

        stage = cp.stages["fan"]
        assert isinstance(stage, ParallelStage)
        assert stage.name == "fan"
        assert len(stage.steps) == 2
        assert stage.steps[0] is step1
        assert stage.steps[1] is step2
        assert stage.max_workers == 4

    def test_overlays_dropped(self) -> None:
        """Overlays are stripped — they're a Megaplan concern."""
        step_a = _FakeMegaplanStep("a")
        mp = MegaplanPipeline(
            stages={"a": MegaplanStage(name="a", step=step_a)},
            entry="a",
            overlays=(
                type("Overlay", (), {"name": "o1", "apply": lambda p: p})(),
            ),
        )

        cp = to_canonical_pipeline(mp)
        # Canonical Pipeline has no overlays attribute
        assert not hasattr(cp, "overlays")

    def test_binding_map_carried_through(self) -> None:
        """binding_map passes through unchanged."""
        step_a = _FakeMegaplanStep("a")
        bm = {"key": "value"}
        mp = MegaplanPipeline(
            stages={"a": MegaplanStage(name="a", step=step_a)},
            entry="a",
            binding_map=bm,
        )

        cp = to_canonical_pipeline(mp)
        assert cp.binding_map is bm

    def test_resource_bundles_carried_through(self) -> None:
        """resource_bundles passes through unchanged."""
        step_a = _FakeMegaplanStep("a")
        rb = (object(),)
        mp = MegaplanPipeline(
            stages={"a": MegaplanStage(name="a", step=step_a)},
            entry="a",
            resource_bundles=rb,
        )

        cp = to_canonical_pipeline(mp)
        assert cp.resource_bundles is rb

    def test_edge_kinds_preserved(self) -> None:
        """Decision and override edge kinds survive conversion."""
        step_a = _FakeMegaplanStep("a")
        mp = MegaplanPipeline(
            stages={
                "a": MegaplanStage(
                    name="a",
                    step=step_a,
                    edges=(
                        MegaplanEdge(label="proceed", target="b", kind="decision"),
                        MegaplanEdge(label="override abort", target="halt", kind="override"),
                    ),
                ),
            },
            entry="a",
        )

        cp = to_canonical_pipeline(mp)
        edges = cp.stages["a"].edges
        assert edges[0].kind == "decision"
        assert edges[0].label == "proceed"
        assert edges[1].kind == "override"
        assert edges[1].label == "override abort"

    def test_vocabularies_preserved(self) -> None:
        """Decision/override vocabularies are carried through."""
        step_a = _FakeMegaplanStep("a")
        mp = MegaplanPipeline(
            stages={
                "a": MegaplanStage(
                    name="a",
                    step=step_a,
                    decision_vocabulary=frozenset({"proceed", "iterate"}),
                    override_vocabulary=frozenset({"force_proceed", "abort"}),
                ),
            },
            entry="a",
        )

        cp = to_canonical_pipeline(mp)
        stage = cp.stages["a"]
        assert stage.decision_vocabulary == frozenset({"proceed", "iterate"})
        assert stage.override_vocabulary == frozenset({"force_proceed", "abort"})


# ---------------------------------------------------------------------------
# StepContext conversion tests
# ---------------------------------------------------------------------------


class TestStepContextConversion:
    """Round-trip and hook_extensions tests for context conversion."""

    def test_round_trip_preserves_fields(self) -> None:
        """Megaplan ctx → canonical → Megaplan ctx round-trips faithfully."""
        plan_dir = Path("/tmp/test-plan")
        envelope = RunEnvelope(taint="clean", cost=1.5)
        profile = {"mode": "code"}
        budget = {"limit": 100}

        mp_ctx = MegaplanStepContext(
            plan_dir=plan_dir,
            state={"key": "val"},
            profile=profile,
            mode="default",
            inputs={"in": Path("/tmp/input")},
            budget=budget,
            envelope=envelope,
        )

        canon = to_canonical_step_context(mp_ctx)
        assert canon.artifact_root == str(plan_dir)
        assert canon.state == {"key": "val"}
        assert canon.mode == "default"
        assert canon.hook_extensions["plan_dir"] is plan_dir
        assert canon.hook_extensions["profile"] is profile
        assert canon.hook_extensions["budget"] is budget
        assert canon.hook_extensions["envelope"] is envelope

        # Round-trip back
        restored = from_canonical_step_context(canon)
        assert restored.plan_dir == plan_dir
        assert restored.state == {"key": "val"}
        assert restored.profile is profile
        assert restored.budget is budget
        assert restored.envelope is envelope
        assert restored.mode == "default"

    def test_hook_extensions_packed_correctly(self) -> None:
        """to_canonical_step_context stores Megaplan fields in hook_extensions."""
        plan_dir = Path("/tmp/plan")
        envelope = RunEnvelope()
        mp_ctx = MegaplanStepContext(
            plan_dir=plan_dir,
            state={},
            profile="test-profile",
            mode="code",
            budget=None,
            envelope=envelope,
        )

        canon = to_canonical_step_context(mp_ctx)
        assert canon.hook_extensions == {
            "plan_dir": plan_dir,
            "profile": "test-profile",
            "budget": None,
            "envelope": envelope,
        }

    def test_empty_inputs_survive_round_trip(self) -> None:
        """Empty inputs dict round-trips."""
        mp_ctx = MegaplanStepContext(
            plan_dir=Path("/tmp"),
            state={},
            profile=None,
            mode="default",
            budget=None,
            envelope=EMPTY_ENVELOPE,
        )

        canon = to_canonical_step_context(mp_ctx)
        restored = from_canonical_step_context(canon)
        assert dict(restored.inputs) == {}

    def test_string_plan_dir_coerced_to_path(self) -> None:
        """from_canonical_step_context coerces str plan_dir to Path."""
        canon = StepContext(
            artifact_root="/tmp/plan",
            state={},
            hook_extensions={
                "plan_dir": "/tmp/plan",
                "profile": None,
                "budget": None,
                "envelope": EMPTY_ENVELOPE,
            },
        )

        restored = from_canonical_step_context(canon)
        assert isinstance(restored.plan_dir, Path)
        assert str(restored.plan_dir) == "/tmp/plan"


class TestFromCanonicalStepContextKeyError:
    """SC5: from_canonical_step_context raises KeyError on missing keys."""

    def test_all_keys_present_no_error(self) -> None:
        """No error when all four keys are present."""
        ctx = StepContext(
            artifact_root="/tmp",
            state={},
            hook_extensions={
                "plan_dir": Path("/tmp"),
                "profile": None,
                "budget": None,
                "envelope": EMPTY_ENVELOPE,
            },
        )
        # Should not raise
        from_canonical_step_context(ctx)

    def test_missing_plan_dir_raises_keyerror(self) -> None:
        """KeyError when plan_dir is missing."""
        ctx = StepContext(
            artifact_root="/tmp",
            state={},
            hook_extensions={
                "profile": None,
                "budget": None,
                "envelope": EMPTY_ENVELOPE,
            },
        )
        with pytest.raises(KeyError, match="plan_dir"):
            from_canonical_step_context(ctx)

    def test_missing_profile_raises_keyerror(self) -> None:
        """KeyError when profile is missing."""
        ctx = StepContext(
            artifact_root="/tmp",
            state={},
            hook_extensions={
                "plan_dir": Path("/tmp"),
                "budget": None,
                "envelope": EMPTY_ENVELOPE,
            },
        )
        with pytest.raises(KeyError, match="profile"):
            from_canonical_step_context(ctx)

    def test_missing_budget_raises_keyerror(self) -> None:
        """KeyError when budget is missing."""
        ctx = StepContext(
            artifact_root="/tmp",
            state={},
            hook_extensions={
                "plan_dir": Path("/tmp"),
                "profile": None,
                "envelope": EMPTY_ENVELOPE,
            },
        )
        with pytest.raises(KeyError, match="budget"):
            from_canonical_step_context(ctx)

    def test_missing_envelope_raises_keyerror(self) -> None:
        """KeyError when envelope is missing."""
        ctx = StepContext(
            artifact_root="/tmp",
            state={},
            hook_extensions={
                "plan_dir": Path("/tmp"),
                "profile": None,
                "budget": None,
            },
        )
        with pytest.raises(KeyError, match="envelope"):
            from_canonical_step_context(ctx)

    def test_missing_multiple_keys_reports_all(self) -> None:
        """KeyError message lists all missing keys."""
        ctx = StepContext(
            artifact_root="/tmp",
            state={},
            hook_extensions={},
        )
        with pytest.raises(KeyError) as exc_info:
            from_canonical_step_context(ctx)
        msg = str(exc_info.value)
        assert "plan_dir" in msg
        assert "profile" in msg
        assert "budget" in msg
        assert "envelope" in msg

    def test_empty_hook_extensions_raises_keyerror(self) -> None:
        """KeyError when hook_extensions is empty dict."""
        ctx = StepContext(artifact_root="/tmp", state={})
        with pytest.raises(KeyError):
            from_canonical_step_context(ctx)
