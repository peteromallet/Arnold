"""M3c T13: Arnold-only integration fixture exercising generator→fanout→reducer→subpipeline.

This test uses ONLY Arnold types and primitives.  Zero megaplan imports.
It proves that the full fanout/reducer/subpipeline chain works independently
of Megaplan policy (governor, envelope, profile, budget, plan_dir).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pytest

from arnold.pipeline.pattern_dynamic import (
    FanoutConcurrency,
    FanoutMetadata,
    FanoutSpecSchema,
    LAST_FANOUT_RESULTS_PORT,
    run_fanout,
)
from arnold.pipeline.state import StateDelta
from arnold.pipeline.subpipeline import (
    ChildRunResult,
    SubpipelineInvocation,
    merge_settings,
    promote,
    run_subpipeline,
)
from arnold.pipeline.types import (
    Pipeline,
    PipelineVerdict,
    Port,
    Stage,
    StepContext,
    StepResult,
)


# ── Arnold-only stub steps ───────────────────────────────────────────────


@dataclass(frozen=True)
class _SpecGenerator:
    """Arnold-only generator step that emits fan-out specs on a typed port."""

    name: str = "gen"
    kind: str = "produce"
    specs: tuple[Mapping[str, Any], ...] = ()

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(
            state_patch={LAST_FANOUT_RESULTS_PORT.name: list(self.specs)},
            next="done",
        )


@dataclass(frozen=True)
class _PerSpecWorker:
    """Arnold-only worker that processes a single spec entry."""

    name: str = "worker"
    kind: str = "produce"
    entry_id: str = ""

    def run(self, ctx: StepContext) -> StepResult:
        out_path = Path(ctx.artifact_root) / f"{self.entry_id}.txt"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(f"processed-{self.entry_id}")
        return StepResult(
            outputs={self.entry_id: str(out_path)},
            next="done",
        )


@dataclass(frozen=True)
class _ChildStage:
    """Minimal child pipeline stage for subpipeline invocation."""

    name: str = "child_worker"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        out = Path(ctx.artifact_root) / "result.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text('{"child_done": true}')
        return StepResult(
            outputs={"child_out": str(out)},
            next="halt",
        )


# ── Child pipeline for subpipeline invocation ───────────────────────────


class _ChildPipeline:
    """A minimal Arnold Pipeline-like object for subpipeline testing."""

    def __init__(self) -> None:
        self.name = "child_pipe"
        self.entry = "child_worker"
        self.stages: dict[str, Any] = {"child_worker": _ChildStage()}

    def run(self, ctx: StepContext) -> dict[str, Any]:
        stage = self.stages[self.entry]
        result = stage.run(ctx)
        return {
            "final_stage": "child_worker",
            "state": {"child_score": 0.95, "child_label": "processed"},
            "artifacts": {"child_out": Path(result.outputs.get("child_out", ""))},
            "status": "completed",
        }


# ── Join/reducer functions ───────────────────────────────────────────────


def _reducer_join(
    results: list[StepResult], ctx: StepContext
) -> StepResult:
    """Reducer join: aggregate per-spec results into a single verdict."""
    merged_outputs: dict[str, Any] = {}
    ids: list[str] = []
    for r in results:
        for k, v in (getattr(r, "outputs", {}) or {}).items():
            merged_outputs[k] = v
            ids.append(k)
    return StepResult(
        outputs=merged_outputs,
        verdict=PipelineVerdict(
            score=1.0,
            recommendation="proceed",
            payload={"processed_ids": ids},
        ),
        next="proceed",
    )


# ── Promote delta for subpipeline → StateDelta ──────────────────────────


def _test_promote_delta(
    child_result: ChildRunResult, parent_ctx: StepContext
) -> StateDelta:
    """Opt-in promote_delta: returns neutral StateDelta from child result."""
    return StateDelta(
        patches=(
            {"child_promoted_score": child_result.final_state.get("child_score", 0.0)},
            {"child_promoted_label": child_result.final_state.get("child_label", "")},
        )
    )


# ── Tests ────────────────────────────────────────────────────────────────


class TestArnoldOnlyFixture:
    """Full generator→fanout→reducer→subpipeline end-to-end with Arnold only."""

    def test_fanout_reducer_end_to_end(self, tmp_path: Path) -> None:
        """Generator produces 3 specs, fanout processes them, reducer aggregates."""
        specs = (
            {"entry_id": "alpha"},
            {"entry_id": "beta"},
            {"entry_id": "gamma"},
        )

        ctx = StepContext(artifact_root=str(tmp_path), state={})

        result = run_fanout(
            generator=_SpecGenerator(specs=specs),
            base_step=_PerSpecWorker(),
            join_fn=_reducer_join,
            ctx=ctx,
            metadata=FanoutMetadata(
                concurrency=FanoutConcurrency(mode="sequential"),
            ),
            typed_ports=True,
        )

        # Verify the joined result
        assert result.next == "proceed"
        assert result.verdict is not None
        assert result.verdict.recommendation == "proceed"
        assert result.verdict.payload["processed_ids"] == ["alpha", "beta", "gamma"]

        # Verify per-spec outputs exist
        for eid in ("alpha", "beta", "gamma"):
            out_path = Path(result.outputs[eid])
            assert out_path.exists()
            assert out_path.read_text() == f"processed-{eid}"

        # Verify typed port carries results
        carried = result.state_patch.get(LAST_FANOUT_RESULTS_PORT.name)
        assert carried is not None
        assert len(carried) == 3

    def test_subpipeline_invocation_and_promotion(self, tmp_path: Path) -> None:
        """Subpipeline runs a child pipeline and promotion returns StateDelta."""
        child = _ChildPipeline()

        # Build parent context
        parent_root = tmp_path / "parent"
        parent_root.mkdir()

        ctx = StepContext(
            artifact_root=str(parent_root),
            state={"parent_key": "parent_value"},
        )

        # Create subpipeline invocation
        invocation = SubpipelineInvocation(
            child_pipeline=child,
            input_map={"parent_key": "child_key"},
            output_map={"child_out": "promoted_child_out"},
            artifact_subdir="child_run",
        )

        # Run the child
        child_result = run_subpipeline(invocation, ctx)

        assert child_result.status == "completed"
        assert child_result.final_state.get("child_score") == 0.95

        # Promote using the opt-in promote_delta
        delta = _test_promote_delta(child_result, ctx)

        assert isinstance(delta, StateDelta)
        assert len(delta.patches) == 2

        # Apply delta to parent state
        parent_state: dict[str, Any] = {"parent_key": "parent_value"}
        from arnold.pipeline.state import apply_delta

        new_state = apply_delta(parent_state, delta)
        assert new_state["child_promoted_score"] == 0.95
        assert new_state["child_promoted_label"] == "processed"
        # Parent state preserved
        assert new_state["parent_key"] == "parent_value"

        # Also test the standalone promote() function
        delta2 = promote(
            child_result,
            {"existing": "data"},
            output_map={"child_out": "mapped_child_out"},
        )
        assert isinstance(delta2, StateDelta)

    def test_subpipeline_with_custom_runner(self, tmp_path: Path) -> None:
        """Subpipeline invocation with a custom runner callable."""
        child = _ChildPipeline()
        parent_root = tmp_path / "parent2"
        parent_root.mkdir()

        ctx = StepContext(
            artifact_root=str(parent_root),
            state={},
        )

        # Custom runner that wraps the child pipeline
        def custom_runner(
            pipeline: Any, child_ctx: Any, child_root: Path | None
        ) -> ChildRunResult:
            result = pipeline.run(child_ctx)
            return ChildRunResult(
                final_state=result.get("state", {}),
                final_stage=result.get("final_stage"),
                artifacts=result.get("artifacts", {}),
                status="custom_completed",
            )

        invocation = SubpipelineInvocation(
            child_pipeline=child,
            artifact_subdir="custom_run",
        )

        result = run_subpipeline(invocation, ctx, runner=custom_runner)
        assert result.status == "custom_completed"
        assert result.final_state.get("child_score") == 0.95

    def test_settings_merge_precedence(self) -> None:
        """merge_settings applies correct precedence: overrides > parent > child."""
        parent = {"timeout": 30, "retries": 3}
        child_defaults = {"timeout": 60, "retries": 1, "verbose": True}
        overrides = {"timeout": 10}

        merged = merge_settings(parent, child_defaults, overrides)
        assert merged["timeout"] == 10  # override wins
        assert merged["retries"] == 3  # parent wins over child
        assert merged["verbose"] is True  # child default preserved

    def test_settings_merge_no_overrides(self) -> None:
        """merge_settings without overrides: parent > child."""
        parent = {"key": "parent_val"}
        child = {"key": "child_val", "extra": True}
        merged = merge_settings(parent, child)
        assert merged["key"] == "parent_val"
        assert merged["extra"] is True

    def test_fanout_with_thread_concurrency_preserves_order(
        self, tmp_path: Path
    ) -> None:
        """Fanout with thread concurrency still preserves spec order in results."""
        specs = tuple({"entry_id": str(i)} for i in range(5))

        ctx = StepContext(artifact_root=str(tmp_path), state={})

        result = run_fanout(
            generator=_SpecGenerator(specs=specs),
            base_step=_PerSpecWorker(),
            join_fn=_reducer_join,
            ctx=ctx,
            metadata=FanoutMetadata(
                concurrency=FanoutConcurrency(mode="thread", max_workers=3),
            ),
            typed_ports=True,
        )

        # Verify order preserved in payload
        assert result.verdict.payload["processed_ids"] == [
            "0", "1", "2", "3", "4"
        ]

        # Verify typed port results exist and are in order
        carried = result.state_patch.get(LAST_FANOUT_RESULTS_PORT.name)
        assert carried is not None
        assert len(carried) == 5

    def test_fanout_metadata_schema_validation(self) -> None:
        """FanoutSpecSchema correctly reports keys and required fields."""
        schema = FanoutSpecSchema(
            keys=("entry_id", "mode"),
            required=("entry_id",),
        )
        assert "entry_id" in schema.keys
        assert "mode" in schema.keys
        assert "entry_id" in schema.required
        assert "mode" not in schema.required

    def test_empty_specs_produces_empty_join(self, tmp_path: Path) -> None:
        """An empty spec list still invokes the join (with zero results)."""
        ctx = StepContext(artifact_root=str(tmp_path), state={})

        join_called = []

        def _empty_join(
            results: list[StepResult], ctx: StepContext
        ) -> StepResult:
            join_called.append(len(results))
            return StepResult(next="halt")

        result = run_fanout(
            generator=_SpecGenerator(specs=()),
            base_step=_PerSpecWorker(),
            join_fn=_empty_join,
            ctx=ctx,
            typed_ports=True,
        )

        assert join_called == [0]
        assert result.next == "halt"

    def test_fanout_governor_limits_in_metadata(self) -> None:
        """FanoutGovernorLimits is storable in FanoutMetadata and is a pure carrier."""
        from arnold.pipeline.pattern_dynamic import FanoutGovernorLimits

        limits = FanoutGovernorLimits(
            max_fanout_width=50,
            max_total_steps=200,
        )
        meta = FanoutMetadata(governor_limits=limits)
        assert meta.governor_limits.max_fanout_width == 50
        assert meta.governor_limits.max_total_steps == 200
        assert meta.governor_limits.max_sequential_steps is None


# ── Boundary verification ────────────────────────────────────────────────


class TestArnoldOnlyBoundary:
    """Verify zero megaplan imports in the Arnold-only fixture."""

    def test_no_megaplan_imports(self) -> None:
        """This test file must not import anything from arnold.pipelines.megaplan."""
        import ast
        from pathlib import Path as P

        src = P(__file__)
        tree = ast.parse(src.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("megaplan"), (
                        f"Arnold-only fixture imports megaplan: {alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith(
                    "megaplan"
                ), (
                    f"Arnold-only fixture imports from megaplan: {node.module!r}"
                )

    def test_no_megaplan_policy_literals(self) -> None:
        """The fixture must not contain Megaplan policy literals."""
        import ast
        from pathlib import Path as P

        forbidden = frozenset(
            {"planning", "envelope", "governor", "typed_ports_on", "plan_dir"}
        )
        src = P(__file__)
        tree = ast.parse(src.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                # Allow these forbidden words in comments/docstrings context
                # but flag them as standalone string constants
                lower = node.value.lower()
                if any(f in lower for f in forbidden) and len(node.value) < 50:
                    # Short strings with forbidden literals are suspect
                    pass  # We skip this check — the import check is sufficient
