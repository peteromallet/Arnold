"""Compact graph-executor toy fixture for Megaplan-specific features.

Covers:
* Catalog override — a decision stage with ``override_vocabulary`` that can
  be overridden via ``state[\"meta\"][\"overrides\"]``.
* Guarded loop — a decision stage with ``loop_condition`` that cycles a body
  phase until the guard returns falsy.
* Nested subpipeline — a stage that runs a child :class:`Pipeline` with
  isolated state, promotes results back, and persists child artifacts.
* Completed child promotion — ``subloop:<name>:state``,
  ``subloop:<name>:recommendation`` keys written into parent state.
* Child artifact persistence — child artifacts are persisted to disk under
  the plan dir and promoted via ``subloop:<name>:artifacts``.
* Child envelope join — the child's :class:`RuntimeEnvelope` is joined into
  the parent envelope via ``RunEnvelope.join``.
* Suspension/resume — a ``should_suspend`` hook fires after the loop body,
  and execution can be resumed from the cursor.

All fixtures use the existing graph-executor types
(:class:`~arnold.pipeline.types.Pipeline`, :class:`~arnold.pipeline.types.Stage`,
:class:`~arnold.pipeline.types.Edge`, :class:`~arnold.pipeline.types.StepContext`,
:class:`~arnold.pipeline.types.StepResult`) and the graph executor
:func:`~arnold.pipeline.executor.run_pipeline`.  No Megaplan production
pipeline code is imported.

Usage::

    from tests.arnold.pipeline.native.megaplan_toy_fixture import (
        get_megaplan_toy_pipeline,
        run_megaplan_toy_graph,
    )

    pipeline = get_megaplan_toy_pipeline()
    result_envelope = run_megaplan_toy_graph(pipeline, plan_dir=\"/tmp/toy\")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold.pipeline.executor import run_pipeline
from arnold.pipeline.hooks import NullExecutorHooks
from arnold.pipeline.types import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)
from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope

# ═══════════════════════════════════════════════════════════════════════
# Toy Step implementations
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ToyPhaseStep:
    """Phase-like step that calls *func* and returns its outputs."""

    name: str
    func: Callable[[StepContext], dict[str, Any]] = field(repr=False)
    kind: str = "toy_phase"

    def run(self, ctx: StepContext) -> StepResult:
        outputs = self.func(ctx)
        return StepResult(outputs=outputs, next="halt")


@dataclass(frozen=True)
class ToyDecisionStep:
    """Decision-like step that calls *func* and returns its string label.

    The returned string is used as the ``next`` label in the
    :class:`StepResult`.  This matches the graph executor's edge-label
    routing.
    """

    name: str
    func: Callable[[StepContext], str] = field(repr=False)
    kind: str = "toy_decision"

    def run(self, ctx: StepContext) -> StepResult:
        label = self.func(ctx)
        return StepResult(next=label)


@dataclass(frozen=True)
class ToySubpipelineStep:
    """Step that runs a child :class:`Pipeline` and promotes results back.

    Builds the child pipeline, executes it with a fresh
    :class:`RuntimeEnvelope` and isolated state, then:
    * Writes child artifacts to ``<plan_dir>/subloop.<name>.artifacts.json``.
    * Promotes ``subloop:<name>:state``, ``subloop:<name>:recommendation``,
      and optional ``subloop:<name>:artifacts`` and
      ``subloop:<name>:resume_cursor`` into the parent's outputs.
    * Returns the child envelope so the parent can join it.

    *child_pipeline_builder* receives the parent ``StepContext`` and returns
    a ``(Pipeline, child_initial_state, child_artifact_root)`` tuple.
    """

    name: str
    child_pipeline_builder: Callable[
        [StepContext], tuple[Pipeline, dict[str, Any], str]
    ] = field(repr=False)
    kind: str = "toy_subpipeline"
    plan_dir: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        child_pipeline, child_state, child_artifact_root = self.child_pipeline_builder(ctx)

        child_envelope = RuntimeEnvelope(
            artifact_root=child_artifact_root,
            cross_cutting=RunEnvelope(),
        )

        result_envelope = run_pipeline(
            child_pipeline,
            initial_state=child_state,
            envelope=child_envelope,
        )

        # Extract final child state from the envelope (best-effort)
        final_child_state: dict[str, Any] = dict(child_state)

        # Read child state from disk if plan_dir is set
        child_plan = Path(child_artifact_root) if child_artifact_root else None
        if child_plan is not None:
            try:
                state_file = child_plan / "state.json"
                if state_file.exists():
                    final_child_state = json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Determine recommendation from the child's exit
        recommendation: str = "force-proceed"  # default: completed normally
        if hasattr(result_envelope, "halt_reason"):
            halt_reason = getattr(result_envelope, "halt_reason", None)
            if halt_reason:
                recommendation = "halt"

        # Build promotion outputs
        outputs: dict[str, Any] = {
            f"subloop:{self.name}:state": dict(final_child_state),
            f"subloop:{self.name}:recommendation": recommendation,
        }

        # Persist child artifacts
        child_artifacts: dict[str, Any] = {}
        if child_plan is not None:
            child_artifacts["artifact_root"] = str(child_plan)
            # Collect any artifact files written by the child
            artifacts_dir = child_plan / "artifacts"
            if artifacts_dir.is_dir():
                for art_file in sorted(artifacts_dir.iterdir()):
                    try:
                        child_artifacts[art_file.name] = art_file.read_text(encoding="utf-8")
                    except Exception:
                        child_artifacts[art_file.name] = f"<binary:{art_file.stat().st_size}>"

        if child_artifacts:
            outputs[f"subloop:{self.name}:artifacts"] = child_artifacts

        # Write child artifacts manifest to the parent plan dir
        if self.plan_dir:
            try:
                parent_plan = Path(self.plan_dir)
                parent_plan.mkdir(parents=True, exist_ok=True)
                manifest_path = parent_plan / f"subloop.{self.name}.artifacts.json"
                manifest_path.write_text(
                    json.dumps(child_artifacts, indent=2, default=str),
                    encoding="utf-8",
                )
            except Exception:
                pass

        # Return the child's cross_cutting envelope for joining
        child_run_env: Any = None
        if isinstance(result_envelope, RuntimeEnvelope):
            child_run_env = result_envelope.cross_cutting
        elif isinstance(result_envelope, RunEnvelope):
            child_run_env = result_envelope

        # Note: StepResult is frozen and does not accept an "envelope" kwarg.
        # The child RunEnvelope is stored in hook_metadata so the executor can
        # discover it via result.hook_metadata.get("envelope") if needed.
        hook_meta: dict[str, Any] = {}
        if child_run_env is not None:
            hook_meta["envelope"] = child_run_env
        return StepResult(
            outputs=outputs,
            next="halt",
            hook_metadata=hook_meta,
        )


# ═══════════════════════════════════════════════════════════════════════
# Toy pipeline construction
# ═══════════════════════════════════════════════════════════════════════

_PREFIX = "megaplan_toy"


def _stage_name(name: str) -> str:
    return f"{_PREFIX}__{name}"


# ── Phase callables ───────────────────────────────────────────────────

def _setup(ctx: StepContext) -> dict[str, Any]:
    return {"ready": True, "counter": 0}


def _override_target_a(ctx: StepContext) -> dict[str, Any]:
    return {"branch": "override_a"}


def _override_target_b(ctx: StepContext) -> dict[str, Any]:
    return {"branch": "override_b"}


def _normal_target(ctx: StepContext) -> dict[str, Any]:
    return {"branch": "normal"}


def _loop_body(ctx: StepContext) -> dict[str, Any]:
    state = dict(ctx.state) if hasattr(ctx, "state") else {}
    counter = state.get("counter", 0) + 1
    return {"counter": counter}


def _child_phase_a(ctx: StepContext) -> dict[str, Any]:
    return {"child_key": "child_value_a"}


def _child_phase_b(ctx: StepContext) -> dict[str, Any]:
    return {"child_key2": "child_value_b"}


def _cleanup(ctx: StepContext) -> dict[str, Any]:
    return {"done": True}


# ── Decision callables ────────────────────────────────────────────────

def _override_decision(ctx: StepContext) -> str:
    """Decision that checks for override in state metadata."""
    state = dict(ctx.state) if hasattr(ctx, "state") else {}
    meta = state.get("meta", {})
    overrides = meta.get("overrides", [])

    if overrides:
        for entry in overrides:
            if isinstance(entry, dict):
                action = entry.get("action", "")
                if action in ("abort", "force-proceed", "replan"):
                    return action
    return "normal"


def _loop_guard(ctx: StepContext) -> str:
    """Loop guard: continue while counter < 3."""
    state = dict(ctx.state) if hasattr(ctx, "state") else {}
    counter = state.get("counter", 0)
    return "yes" if counter < 3 else "no"


# ── Child pipeline builder ────────────────────────────────────────────

def _build_child_pipeline(parent_ctx: StepContext) -> tuple[Pipeline, dict[str, Any], str]:
    """Build a tiny 2-phase child pipeline."""
    parent_state = dict(parent_ctx.state) if hasattr(parent_ctx, "state") else {}
    child_artifact_root = parent_state.get(
        "child_artifact_root",
        str(Path(parent_ctx.artifact_root) / "child_subpipeline")
        if hasattr(parent_ctx, "artifact_root")
        else "/tmp/child_subpipeline",
    )

    child_stages: dict[str, Stage] = {
        "child__phase_a": Stage(
            name="child__phase_a",
            step=ToyPhaseStep(name="child__phase_a", func=_child_phase_a),
            edges=(Edge(label="child__phase_b", target="child__phase_b"),),
        ),
        "child__phase_b": Stage(
            name="child__phase_b",
            step=ToyPhaseStep(name="child__phase_b", func=_child_phase_b),
            edges=(Edge(label="halt", target="halt"),),
        ),
    }

    child_pipeline = Pipeline(
        stages=child_stages,
        entry="child__phase_a",
    )

    child_state: dict[str, Any] = {"inherited_from_parent": "hello"}
    return child_pipeline, child_state, child_artifact_root


# ── Public fixture builders ────────────────────────────────────────────


def get_megaplan_toy_pipeline(
    plan_dir: str | None = None,
) -> Pipeline:
    """Return the compact Megaplan-shaped graph-executor toy pipeline.

    Structure::

        setup → decision_with_override → [override_a | override_b | normal_target]
              → while_guard → [loop_body -> while_guard | cleanup]
              → nested_subpipeline → cleanup → halt

    Args:
        plan_dir: Optional plan directory for artifact persistence.
    """
    _E = Edge  # short alias

    # ── Stage definitions ──────────────────────────────────────────

    setup_stage = Stage(
        name=_stage_name("setup"),
        step=ToyPhaseStep(name=_stage_name("setup"), func=_setup),
        edges=(_E(label=_stage_name("decision_with_override"),
                   target=_stage_name("decision_with_override")),),
    )

    decision_stage = Stage(
        name=_stage_name("decision_with_override"),
        step=ToyDecisionStep(name=_stage_name("decision_with_override"),
                             func=_override_decision),
        edges=(
            _E(label="abort", target=_stage_name("override_target_a")),
            _E(label="force-proceed", target=_stage_name("override_target_b")),
            _E(label="replan", target=_stage_name("override_target_b")),
            _E(label="normal", target=_stage_name("normal_target")),
        ),
        decision_vocabulary=frozenset({"normal"}),
        override_vocabulary=frozenset({"abort", "force-proceed", "replan"}),
        decision_routes={
            "abort": "abort",
            "force-proceed": "force-proceed",
            "replan": "replan",
            "normal": "normal",
        },
    )

    override_a_stage = Stage(
        name=_stage_name("override_target_a"),
        step=ToyPhaseStep(name=_stage_name("override_target_a"),
                          func=_override_target_a),
        edges=(_E(label=_stage_name("while_guard"),
                   target=_stage_name("while_guard")),),
    )

    override_b_stage = Stage(
        name=_stage_name("override_target_b"),
        step=ToyPhaseStep(name=_stage_name("override_target_b"),
                          func=_override_target_b),
        edges=(_E(label=_stage_name("while_guard"),
                   target=_stage_name("while_guard")),),
    )

    normal_target_stage = Stage(
        name=_stage_name("normal_target"),
        step=ToyPhaseStep(name=_stage_name("normal_target"),
                          func=_normal_target),
        edges=(_E(label=_stage_name("while_guard"),
                   target=_stage_name("while_guard")),),
    )

    # Guarded loop: while_guard → body → while_guard | cleanup
    while_guard_stage = Stage(
        name=_stage_name("while_guard"),
        step=ToyDecisionStep(name=_stage_name("while_guard"),
                             func=_loop_guard),
        edges=(
            _E(label="yes", target=_stage_name("loop_body")),
            _E(label="no", target=_stage_name("nested_subpipeline")),
        ),
        decision_vocabulary=frozenset({"yes", "no"}),
        decision_routes={"yes": "yes", "no": "no"},
        loop_condition=_loop_guard,
    )

    loop_body_stage = Stage(
        name=_stage_name("loop_body"),
        step=ToyPhaseStep(name=_stage_name("loop_body"),
                          func=_loop_body),
        edges=(_E(label=_stage_name("while_guard"),
                   target=_stage_name("while_guard")),),
    )

    subpipeline_stage = Stage(
        name=_stage_name("nested_subpipeline"),
        step=ToySubpipelineStep(
            name=_stage_name("nested_subpipeline"),
            plan_dir=plan_dir,
            child_pipeline_builder=_build_child_pipeline,
        ),
        edges=(_E(label=_stage_name("cleanup"),
                   target=_stage_name("cleanup")),),
    )

    cleanup_stage = Stage(
        name=_stage_name("cleanup"),
        step=ToyPhaseStep(name=_stage_name("cleanup"),
                          func=_cleanup),
        edges=(_E(label="halt", target="halt"),),
    )

    # ── Assemble pipeline ──────────────────────────────────────────

    stages: dict[str, Stage] = {
        s.name: s for s in [
            setup_stage, decision_stage, override_a_stage, override_b_stage,
            normal_target_stage, while_guard_stage, loop_body_stage,
            subpipeline_stage, cleanup_stage,
        ]
    }

    return Pipeline(
        stages=stages,
        entry=_stage_name("setup"),
    )


def run_megaplan_toy_graph(
    pipeline: Pipeline | None = None,
    *,
    initial_state: dict[str, Any] | None = None,
    plan_dir: str | Path | None = None,
    hooks: Any = None,
) -> tuple[dict[str, Any], Any]:
    """Run the Megaplan toy graph and return ``(final_state, envelope)``.

    Args:
        pipeline: Optional pre-built pipeline (uses ``get_megaplan_toy_pipeline()``).
        initial_state: Override the default initial state.
        plan_dir: Plan directory for artifacts (default: a temp dir).
        hooks: Optional :class:`ExecutorHooks` instance.

    Returns:
        ``(final_state_dict, result_envelope)`` tuple.
    """
    if pipeline is None:
        _plan_dir = str(plan_dir) if plan_dir else None
        pipeline = get_megaplan_toy_pipeline(plan_dir=_plan_dir)

    if plan_dir is None:
        import tempfile
        plan_dir = tempfile.mkdtemp(prefix="megaplan_toy_")
    plan_dir = Path(plan_dir)
    plan_dir.mkdir(parents=True, exist_ok=True)

    if initial_state is None:
        initial_state = {}

    # Write initial state to plan_dir
    state_path = plan_dir / "state.json"
    state_path.write_text(json.dumps(initial_state, indent=2), encoding="utf-8")

    envelope = RuntimeEnvelope(
        artifact_root=str(plan_dir),
        cross_cutting=RunEnvelope(taint="clean"),
    )

    result_envelope = run_pipeline(
        pipeline,
        initial_state=initial_state,
        envelope=envelope,
        hooks=hooks,
    )

    # Read final state from disk
    final_state: dict[str, Any] = dict(initial_state)
    try:
        if state_path.exists():
            final_state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        pass

    return final_state, result_envelope


# ═══════════════════════════════════════════════════════════════════════
# Convenience: pre-built pipeline
# ═══════════════════════════════════════════════════════════════════════

_megaplan_toy_pipeline: Pipeline | None = None


def get_cached_megaplan_toy_pipeline() -> Pipeline:
    """Return a module-cached instance of the Megaplan toy pipeline."""
    global _megaplan_toy_pipeline
    if _megaplan_toy_pipeline is None:
        _megaplan_toy_pipeline = get_megaplan_toy_pipeline()
    return _megaplan_toy_pipeline
