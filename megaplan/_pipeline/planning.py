"""Compile the existing planning state machine into a :class:`Pipeline` value.

Sprint 2 deliverable. Hoists the implicit pipeline-shape currently spread
across ``megaplan/_core/workflow.py`` (the ``WORKFLOW`` dict +
``_ROBUSTNESS_OVERRIDES``) into a single declarative ``Pipeline``. The
existing dict stays as the runtime source of truth; this module
**derives** a ``Pipeline`` from it so:

1. The Sprint-1 primitives are proven sufficient to express the real
   planning flow, not just demos.
2. Sprint 3 can delete ``WORKFLOW`` once every consumer reads the
   ``Pipeline`` instead. That deletion is out of scope here — it requires
   coordinating ``auto.py``, every handler, ``_RESUME_ACTIVE_STATES``, and
   the test suite.

The compiled ``Pipeline`` uses the existing **state names** as stage
names (one stage per ``WORKFLOW`` key) because that is what
``resume_cursor.phase`` already references in ``state.json``.
Robustness, ``--with-prep``, and ``--with-feedback`` are exposed as
:class:`Overlay` instances that transform the base ``Pipeline``.

Per the brief's "leaks" table:

- Gate branches are labelled by gate condition (``gate_iterate``,
  ``gate_tiebreaker``, …) — the compiled :class:`Edge` ``label`` field
  matches that condition string verbatim.
- The handler-driven review→rework loop is **not** an Edge in WORKFLOW
  today (it is mutation inside ``handle_review``); the compiled Pipeline
  therefore does not represent it. Sprint 3 will add an explicit
  ``review_needs_rework`` edge.
- Tiebreaker today is a pair of states (``tiebreaker_pending`` /
  ``tiebreaker_ready``); the compiled Pipeline keeps those as ordinary
  stages, not yet as a :class:`Step` of ``kind='subloop'``. Sprint 3 will
  fold them into a true subloop.
- ``override`` transitions are encoded as regular edges with the literal
  ``next_step`` (``override force-proceed`` etc.) as the edge label; the
  Sprint-3 executor will rewrite these as :class:`Edge`-typed escape
  edges.

Each compiled stage uses a :class:`_RuntimeStep` placeholder that returns
a ``NotImplementedError``. Sprint 3 ports the real handlers into
:class:`Step` instances. Today the value of this module is that the
Pipeline **shape** is derivable end-to-end and that ``Overlay`` is
exercised against the real ``with_prep`` / ``with_feedback`` /
robustness overlays — not just toy demos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from megaplan._core.workflow import (
    _workflow_for_robustness,
    _with_prep_from_state,
    _with_feedback_from_state,
)
from megaplan._core.workflow_data import (
    WORKFLOW,
    Transition,
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


_GATE_RECS: dict[str, str] = {
    "gate_proceed": "proceed",
    "gate_iterate": "iterate",
    "gate_tiebreaker": "tiebreaker",
    "gate_escalate": "escalate",
}


def _edges_from_transitions(transitions: list[Transition]) -> tuple[Edge, ...]:
    """Map ``Transition`` list to a tuple of :class:`Edge`.

    Sprint 4 Chunk A: gate-condition transitions become typed
    ``Edge(kind="gate", recommendation=...)`` so the executor dispatches
    by ``Verdict.recommendation`` instead of label-string compare. The
    legacy ``"gate_<condition>:<next_step>"`` packing is gone.

    Per-stage collision guard: if more than one transition in the same
    stage shares the same gate condition (today: the three
    ``gate_escalate`` transitions on ``STATE_CRITIQUED``), they fall back
    to ``kind="normal"`` edges with the bare ``next_step`` as the label
    so they remain individually addressable.
    """

    import collections

    gate_counts: collections.Counter[str] = collections.Counter()
    for transition in transitions:
        if transition.condition in _GATE_RECS:
            gate_counts[transition.condition] += 1

    edges: list[Edge] = []
    for transition in transitions:
        condition = transition.condition
        next_step = transition.next_step
        next_state = transition.next_state

        if condition == "always":
            edges.append(Edge(label=next_step, target=next_state))
            continue

        if condition in _GATE_RECS and gate_counts[condition] == 1:
            rec = _GATE_RECS[condition]
            edges.append(
                Edge(
                    label=rec,
                    target=next_state,
                    kind="gate",
                    recommendation=rec,  # type: ignore[arg-type]
                )
            )
            continue

        if condition in _GATE_RECS and gate_counts[condition] > 1:
            # Collision (e.g. gate_escalate fan-out on STATE_CRITIQUED) —
            # fall back to addressable normal edges with the bare next_step.
            edges.append(Edge(label=next_step, target=next_state))
            continue

        # Unknown / legacy gate condition (gate_unset, gate_proceed_blocked):
        # preserve the old packed label so existing dispatch keeps working.
        edges.append(
            Edge(label=f"{condition}:{next_step}", target=next_state)
        )
    return tuple(edges)


def _compile_workflow_dict(
    workflow: Mapping[str, list[Transition]],
) -> dict[str, Stage]:
    stages: dict[str, Stage] = {}
    for state_name, transitions in workflow.items():
        stages[state_name] = Stage(
            name=state_name,
            step=_step_for(state_name),
            edges=_edges_from_transitions(transitions),
        )
    return stages


def compile_planning_pipeline() -> Pipeline:
    """Return the base planning :class:`Pipeline` derived from ``WORKFLOW``.

    The entry is ``'initialized'`` — matching the live state-machine
    semantics. Overlays for robustness / with_prep / with_feedback are
    available via :func:`robustness_overlay`, :func:`with_prep_overlay`,
    and :func:`with_feedback_overlay`.
    """

    stages = _compile_workflow_dict(WORKFLOW)
    return Pipeline(stages=stages, entry="initialized")


def robustness_overlay(
    level: str,
    *,
    creative: bool = False,
    with_prep: bool = False,
    with_feedback: bool = False,
) -> Overlay:
    """Return an :class:`Overlay` that rewrites stages per a robustness level.

    Delegates to the existing ``_workflow_for_robustness`` so the
    compiled Pipeline stays in lock-step with whatever the runtime
    state-machine consults today. Sprint 3 inverts this: ``WORKFLOW`` is
    deleted and the Pipeline becomes the source of truth.

    The ``creative`` flag flips the workflow into creative-mode shape
    (e.g. the planning state's exit edge differs in some robustness
    levels). Pass ``creative=True`` for ``mode in {"creative", "joke"}``.
    """

    def _apply(pipeline: Pipeline) -> Pipeline:
        effective = _workflow_for_robustness(
            level,
            creative=creative,
            with_prep=with_prep,
            with_feedback=with_feedback,
        )
        new_stages: dict[str, Stage | Any] = dict(pipeline.stages)
        for state_name, transitions in effective.items():
            new_stages[state_name] = Stage(
                name=state_name,
                step=_step_for(state_name),
                edges=_edges_from_transitions(transitions),
            )
        return Pipeline(
            stages=new_stages,
            entry=pipeline.entry,
            overlays=pipeline.overlays,
        )

    return Overlay(name=f"robustness:{level}", apply=_apply)


def mode_overlay(mode: str) -> Overlay:
    """Overlay that routes the planning Pipeline into a per-mode shape.

    ``mode`` is one of ``"code"``, ``"doc"``, ``"metaplan"``,
    ``"joke"``, ``"creative"``. The doc/joke/creative paths use the
    same state machine as code but resolve different prompt-mode
    variants (``critique_joke.py``, ``execute_doc.py``, etc.) at
    dispatch time. The overlay names the mode so downstream slot
    resolution can pick the matching prompt; it does not rewrite the
    graph for ``code``/``doc``/``metaplan``. For ``joke``/``creative``
    the overlay is a no-op at this layer because robustness_overlay
    already applied ``creative=is_creative_mode(state)`` when it was
    composed with ``compile_pipeline_for``.
    """

    def _apply(pipeline: Pipeline) -> Pipeline:
        return pipeline  # mode is carried in StepContext.mode; no graph rewrite

    return Overlay(name=f"mode:{mode}", apply=_apply)


def with_prep_overlay(state_payload: Mapping[str, Any]) -> Overlay:
    """Overlay that re-instates the default initialized→prep edge.

    Wraps ``_with_prep_from_state`` semantics: when ``state_payload``
    encodes ``--with-prep``, the initialized stage's edge target is
    forced to ``'prepped'`` regardless of robustness-level overrides.
    """

    def _apply(pipeline: Pipeline) -> Pipeline:
        if not _with_prep_from_state(dict(state_payload)):
            return pipeline
        new_stages = dict(pipeline.stages)
        new_stages["initialized"] = Stage(
            name="initialized",
            step=_step_for("initialized"),
            edges=(Edge("prep", "prepped"),),
        )
        return Pipeline(
            stages=new_stages,
            entry=pipeline.entry,
            overlays=pipeline.overlays,
        )

    return Overlay(name="with_prep", apply=_apply)


def with_feedback_overlay(state_payload: Mapping[str, Any]) -> Overlay:
    """Overlay that splices a ``feedback`` stage between review and done.

    Mirrors ``_with_feedback_from_state`` semantics. When the flag is on,
    the executed → review edge target switches to ``'reviewed'``, a new
    ``reviewed`` stage points at ``feedback``, and ``feedback`` points at
    ``done``. The base ``WORKFLOW`` already has ``STATE_REVIEWED``
    defined in the state-machine constants — this overlay just wires the
    edges.
    """

    def _apply(pipeline: Pipeline) -> Pipeline:
        if not _with_feedback_from_state(dict(state_payload)):
            return pipeline
        new_stages = dict(pipeline.stages)
        # executed --review--> reviewed
        new_stages["executed"] = Stage(
            name="executed",
            step=_step_for("executed"),
            edges=(Edge("review", "reviewed"),),
        )
        new_stages["reviewed"] = Stage(
            name="reviewed",
            step=_step_for("reviewed"),
            edges=(Edge("feedback", "done"),),
        )
        return Pipeline(
            stages=new_stages,
            entry=pipeline.entry,
            overlays=pipeline.overlays,
        )

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
