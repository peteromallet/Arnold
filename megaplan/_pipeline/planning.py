"""Compile the canonical planning :class:`Pipeline`.

Sprint 5 Chunk A: the runnable, phase-name-keyed shape is now the only
canonical compile target. The legacy state-name-keyed shape (built from
the ``WORKFLOW`` dict via ``_compile_workflow_dict``) and its byte-for-
byte inversion helper ``workflow_dict_from_pipeline`` have been retired
— they only ever existed to pass the inversion parity test.

The canonical :class:`Pipeline` keys stages by phase name
(``prep / plan / critique / gate / revise / finalize / execute / review
/ tiebreaker``) and routes the gate Step's recommendation edges directly
off the ``gate`` stage. The three overlays (``with_prep_overlay``,
``with_feedback_overlay``, ``robustness_overlay``) are retained as
identity transforms on the phase-name graph; the prep step is now
unconditionally present, and robustness / feedback customisation moves
to Step-level configuration in subsequent sprints.

``WORKFLOW`` remains in :mod:`megaplan._core.workflow_data` solely as
bootstrap data for ``_workflow_for_robustness`` and the legacy
state-machine driver behind ``MEGAPLAN_PIPELINE_AUTO=0``. This module
no longer imports it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from megaplan._core.workflow import (
    _with_prep_from_state,
    _with_feedback_from_state,
)
from megaplan._pipeline.patterns import (
    critique_revise_gate_loop,
    phase_zero_gate,
)
from megaplan._pipeline.types import (
    Edge,
    Overlay,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)


@dataclass(frozen=True)
class _RuntimeStep:
    """Placeholder Step for stages whose handler has not yet been ported.

    Sprint 3 replaces these with real handler-backed steps. Until then
    invoking the executor against a compiled planning Pipeline raises
    ``NotImplementedError`` with the stage name. The structural shape is
    fully derivable, which is what the abstraction proof requires.
    """

    name: str
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None

    def run(self, ctx: StepContext) -> StepResult:  # pragma: no cover - shim
        raise NotImplementedError(
            f"Stage {self.name!r} is a compiled WORKFLOW placeholder; "
            "Sprint 3 ports the underlying handler into a real Step."
        )


_HANDLER_STEPS: dict[str, Any] | None = None


def _step_for(state_name: str) -> Any:
    # State names like 'initialized', 'planned', 'critiqued', etc. become
    # stage names. Sprint 3: bind to real handler-backed Steps when the
    # state name has a matching handler (prep / plan / critique / gate /
    # finalize / execute / review / tiebreaker_*); fall back to the
    # _RuntimeStep placeholder for terminal/non-handler states
    # (initialized, gated → finalize-edge, done, aborted,
    # awaiting_human_verify).
    global _HANDLER_STEPS
    if _HANDLER_STEPS is None:
        from megaplan._pipeline.stages.handler_step import build_planning_steps

        _HANDLER_STEPS = build_planning_steps()
    handler = _HANDLER_STEPS.get(state_name)
    if handler is not None:
        return handler
    return _RuntimeStep(name=state_name)


def compile_planning_pipeline() -> Pipeline:
    """Return the canonical, runnable planning :class:`Pipeline`.

    Sprint 5 Chunk A: this is the only canonical compile target. Stage
    keys are phase names (``prep / plan / critique / gate / revise /
    finalize / execute / review / tiebreaker``); the gate Step's
    recommendation edges sit directly on the ``gate`` stage so the
    executor's typed-verdict dispatch resolves cleanly.

    Stage layout::

        prep → plan → critique → gate
                                  ├─ proceed → finalize → execute → review → halt
                                  ├─ iterate → revise → critique  (loop)
                                  ├─ tiebreaker → tiebreaker → critique
                                  └─ escalate → (override edges)
    """

    from megaplan._pipeline.stages.prep import PrepStep
    from megaplan._pipeline.stages.plan import PlanStep
    from megaplan._pipeline.stages.critique import CritiqueStep
    from megaplan._pipeline.stages.gate import GateStep
    from megaplan._pipeline.stages.revise import ReviseStep
    from megaplan._pipeline.stages.finalize import FinalizeStep
    from megaplan._pipeline.stages.execute import ExecuteStep
    from megaplan._pipeline.stages.review import ReviewStep
    from megaplan._pipeline.stages.tiebreaker import TiebreakerStep

    # Phase 0: prep gate via patterns.phase_zero_gate.
    prep_stage = phase_zero_gate(
        PrepStep(),
        name="prep",
        on_pass="plan",
        on_fail="halt",
    )

    # critique → gate → revise cycle assembled via the pattern library.
    # gate_extra_edges carry the four non-recommendation fallback/override
    # edges that the legacy gate stage required; critique_fallback_edges
    # carry the two label-fallback edges the existing CritiqueStep emits.
    cycle = critique_revise_gate_loop(
        CritiqueStep(),
        GateStep(),
        ReviseStep(),
        on_proceed="finalize",
        on_iterate="revise",
        on_tiebreaker="tiebreaker",
        on_escalate="finalize",
        critique_fallback_edges=(
            Edge(label="gate_unset:gate", target="gate"),
            Edge(label="gate", target="gate"),
        ),
        gate_extra_edges=(
            Edge(label="revise", target="revise"),
            Edge(label="gate", target="finalize"),
            Edge(label="override force-proceed", target="finalize"),
            Edge(label="override abort", target="halt"),
        ),
        revise_target="critique",
    )

    stages: dict[str, Stage] = {
        "prep": prep_stage,
        "plan": Stage(
            name="plan", step=PlanStep(),
            edges=(Edge(label="critique", target="critique"),),
        ),
        "critique": cycle["critique"],
        "gate": cycle["gate"],
        "revise": cycle["revise"],
        "finalize": Stage(
            name="finalize", step=FinalizeStep(),
            edges=(Edge(label="execute", target="execute"),),
        ),
        "execute": Stage(
            name="execute", step=ExecuteStep(),
            edges=(Edge(label="review", target="review"),),
        ),
        "review": Stage(
            name="review", step=ReviewStep(),
            edges=(Edge(label="review", target="halt"),
                   Edge(label="halt", target="halt")),
        ),
        # T11 LOAD-BEARING: TiebreakerStep is a SubloopStep that emits a
        # Verdict with a typed recommendation. The three kind='gate' edges
        # below replace the legacy label-only edges; the legacy 'escalate
        # folds into the finalize branch' semantics are preserved via
        # escalate→finalize (anti-scope: no new pipeline branches this
        # sprint).
        "tiebreaker": Stage(
            name="tiebreaker", step=TiebreakerStep(),
            edges=(
                Edge(label="", target="critique", kind="gate", recommendation="iterate"),
                Edge(label="", target="finalize", kind="gate", recommendation="proceed"),
                Edge(label="", target="finalize", kind="gate", recommendation="escalate"),
            ),
        ),
    }
    return Pipeline(stages=stages, entry="prep")


def robustness_overlay(
    level: str,
    *,
    creative: bool = False,
    with_prep: bool = False,
    with_feedback: bool = False,
) -> Overlay:
    """Return an :class:`Overlay` that records a robustness level on the Pipeline.

    Sprint 5 Chunk A: legacy state-name keys (``initialized / prepped /
    planned / critiqued / gated / executed / reviewed / tiebreaker_*``)
    no longer exist in the canonical phase-name graph (``prep / plan /
    critique / gate / revise / finalize / execute / review /
    tiebreaker``), so this overlay no longer rewrites edges by walking
    ``_workflow_for_robustness``. Robustness customisation now flows to
    the Step layer (e.g. ``GateStep`` and ``CritiqueStep`` reading the
    robustness setting from ``StepContext`` / profile). The overlay is
    retained as an identity transform so callers — including
    :func:`compile_pipeline_for` — keep composing it for provenance,
    and a later sprint can promote it into typed Step configuration.

    ``creative``, ``with_prep``, and ``with_feedback`` are accepted for
    signature compatibility with the legacy call sites in
    :func:`compile_pipeline_for`.
    """

    del creative, with_prep, with_feedback  # accepted for signature compat

    def _apply(pipeline: Pipeline) -> Pipeline:
        return pipeline

    return Overlay(name=f"robustness:{level}", apply=_apply)


def mode_overlay(mode: str) -> Overlay:
    """Overlay that names the mode for downstream introspection.

    ``mode`` is one of ``"code"``, ``"doc"``, ``"metaplan"``,
    ``"joke"``, ``"creative"``. The mode is carried in
    ``StepContext.mode``; this overlay does not rewrite the graph and
    only annotates the resulting Pipeline.
    """

    def _apply(pipeline: Pipeline) -> Pipeline:
        return pipeline  # mode is carried in StepContext.mode; no graph rewrite

    return Overlay(name=f"mode:{mode}", apply=_apply)


def with_prep_overlay(state_payload: Mapping[str, Any]) -> Overlay:
    """Overlay for the ``--with-prep`` flag.

    Sprint 5 Chunk A: the canonical phase-name graph unconditionally
    routes through the ``prep`` stage as the entry, so this overlay no
    longer rewrites edges. It is retained as an identity transform on
    the phase-name graph (and continues to read
    ``_with_prep_from_state`` for provenance) so callers keep composing
    it; if ``--with-prep`` is ever opted-out, that customisation now
    belongs on :class:`PrepStep` itself rather than on a graph rewrite.
    """

    def _apply(pipeline: Pipeline) -> Pipeline:
        # Read the flag for provenance / future Step-level wiring but
        # do not rewrite the canonical graph — ``prep`` is the entry.
        _with_prep_from_state(dict(state_payload))
        return pipeline

    return Overlay(name="with_prep", apply=_apply)


def with_feedback_overlay(state_payload: Mapping[str, Any]) -> Overlay:
    """Overlay for the ``--with-feedback`` flag.

    Sprint 5 Chunk A: the canonical phase-name graph already chains
    ``execute → review`` and routes ``review → halt``. A real feedback
    step is a future addition (a typed Step inserted between ``review``
    and ``halt`` once the FeedbackStep primitive lands). Until then the
    overlay is an identity transform on the phase-name graph; it
    continues to read ``_with_feedback_from_state`` for provenance so
    callers can be migrated incrementally.
    """

    def _apply(pipeline: Pipeline) -> Pipeline:
        # Read the flag for provenance / future Step-level wiring but
        # do not splice extra stages onto the canonical graph yet.
        _with_feedback_from_state(dict(state_payload))
        return pipeline

    return Overlay(name="with_feedback", apply=_apply)


def compile_pipeline_for(
    *,
    robustness: str = "standard",
    state_payload: Mapping[str, Any] | None = None,
    mode: str | None = None,
) -> Pipeline:
    """Return the planning :class:`Pipeline` with all relevant overlays applied.

    ``state_payload`` typically comes from the persisted plan
    ``state.json`` and carries the ``config.with_prep`` /
    ``config.with_feedback`` / ``config.mode`` flags. Overlays compose
    left-to-right: robustness first (which already absorbs the
    creative-mode flag), then with_prep, then with_feedback, then a
    no-op mode overlay that names the mode for downstream introspection.
    """

    state_payload = dict(state_payload or {})
    with_prep = _with_prep_from_state(state_payload)
    with_feedback = _with_feedback_from_state(state_payload)
    config = state_payload.get("config", {}) if isinstance(state_payload, Mapping) else {}
    resolved_mode = mode or (config.get("mode", "code") if isinstance(config, Mapping) else "code")
    creative = resolved_mode in {"creative", "joke"}

    pipeline = compile_planning_pipeline()
    overlays = (
        robustness_overlay(
            robustness,
            creative=creative,
            with_prep=with_prep,
            with_feedback=with_feedback,
        ),
        with_prep_overlay(state_payload),
        with_feedback_overlay(state_payload),
        mode_overlay(resolved_mode),
    )
    for overlay in overlays:
        pipeline = overlay.apply(pipeline)
    return Pipeline(
        stages=pipeline.stages,
        entry=pipeline.entry,
        overlays=overlays,
    )
