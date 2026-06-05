"""Frozen primitive types for the megaplan `_pipeline` package.

This module defines the small, frozen dataclass + Protocol surface that the
Sprint-1 standalone pipeline executor and demo build on. Sprint 2 will port
existing handlers onto these primitives; the shapes declared here are
**frozen at end of Sprint 1** and must not be changed without a revision
note in ``.megaplan/briefs/megaplan-decomposition.md``.

Contract notes (load-bearing for executor authors and Step authors):

(a) ``'halt'`` is the reserved terminal ``NextEdge`` label / ``Edge.target``
    value. Step authors MUST NOT use ``'halt'`` as a non-terminal edge
    label. The executor treats either ``result.next == 'halt'`` or an edge
    whose ``target == 'halt'`` as the terminal sentinel.

(b) ``'subloop'`` and ``'override'`` are reserved ``Step.kind`` Literal
    values for forward compatibility. The Sprint-1 executor MUST NOT branch
    on them; they exist so Sprint 2 (and beyond) can introduce a tiebreaker
    subloop kind and an escape-edge override kind without changing the
    frozen Protocol.

(c) ``PipelineVerdict``, ``StepResult``, and ``StepContext`` instances are
    conceptually immutable. Callers MUST NOT mutate ``payload``,
    ``state_patch``, ``inputs``, or ``outputs`` after construction. Because
    ``@dataclass(frozen=True)`` does not deeply freeze ``Mapping`` fields,
    the executor applies ``state_patch`` via ``state.update(dict(result.state_patch))``
    — a defensive copy that prevents cross-call aliasing if a Step returns
    a shared default dict.

(d) Deviation note: the brief at ``.megaplan/briefs/megaplan-decomposition.md:124-128``
    originally sketched ``stages: dict[str, Stage]`` and
    ``overlays: list[Overlay]``. This module widens to
    ``Mapping[str, Stage | ParallelStage]`` and ``tuple[Overlay, ...]`` so
    that (1) ``Pipeline`` itself can be ``@dataclass(frozen=True)`` (frozen
    dataclasses do not accept ``list`` defaults without a default_factory),
    and (2) a ``ParallelStage`` can be addressed by name like a ``Stage``
    without requiring callers to unwrap an intermediate type. The full
    revision note lives in ``.megaplan/briefs/megaplan-decomposition.md`` under the
    ``## Revision notes`` heading (added in Sprint 1 T5).

(e) Decision/override dispatch (M3b): ``PipelineVerdict.recommendation`` is a
    plain ``str | None`` (no longer a typed gate recommendation literal).
    The shared Arnold routing resolver (:func:`arnold.pipeline.routing.resolve_edge`)
    dispatches edges by ``kind`` and ``label``: ``kind='decision'`` +
    ``label=<key>`` for recommendations, ``kind='override'`` +
    ``label='override <action>'`` for overrides, and ``kind='normal'`` +
    ``label==result.next`` for normal labels. The ``PipelineVerdict.override``
    field is also ``str | None``, consumed by the Arnold resolver's override
    dispatch tier. Decision/override vocabularies live on ``Stage`` and
    ``ParallelStage`` as ``decision_vocabulary`` / ``override_vocabulary``
    frozensets (M3b T2).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    Mapping,
    Protocol,
    TypeAlias,
    runtime_checkable,
)

from arnold.pipelines.megaplan._pipeline.envelope import EMPTY_ENVELOPE, RunEnvelope

if TYPE_CHECKING:  # pragma: no cover - typing-only aliases
    BudgetRef = Any
    Profile = Any


NextEdge = str

# M3b: GateRecommendation and OverrideAction typed Literals are removed.
# recommendations and overrides are now plain str | None on PipelineVerdict.
# Edge dispatch uses kind='decision' (was kind='gate') with label=<key>.
EdgeKind = Literal["normal", "decision", "override"]


@dataclass(frozen=True)
class Edge:
    """A labelled transition from one stage to another.

    Dispatch depends on ``kind`` (M3b: ``kind='gate'`` is renamed to
    ``kind='decision'``; the shared Arnold routing resolver dispatches
    by ``kind`` + ``label``):

    * ``kind == "normal"`` (default): the executor matches when
      ``Edge.label == StepResult.next``.
    * ``kind == "decision"``: the executor matches when
      ``Edge.label == StepResult.verdict.recommendation``.
    * ``kind == "override"``: the executor matches when
      ``Edge.label == "override <action>"`` and
      ``StepResult.verdict.override == "<action>"``.

    ``target`` is the name of the next stage in ``Pipeline.stages``. The
    reserved target ``'halt'`` terminates the pipeline.
    """

    label: str
    target: str
    kind: EdgeKind = "normal"
    recommendation: str | None = None


@dataclass(frozen=True)
class PipelineVerdict:
    """Structured output of a judge-kind Step.

    ``score`` is a float in ``[0.0, 1.0]`` by convention but is not
    enforced here. ``flags`` and ``notes`` are free-form. ``payload`` is a
    Mapping for arbitrary structured detail; see the immutability note in
    the module docstring.

    ``recommendation`` is a freeform string consumed by the Arnold routing
    resolver's ``kind='decision'`` edge dispatch (M3b). When set, the
    resolver matches the enclosing stage's decision edges by
    ``Edge.label == verdict.recommendation``. ``override`` is consumed
    by the resolver's ``kind='override'`` edge dispatch
    (``Edge.label == f"override {verdict.override}"``).
    """

    score: float
    flags: tuple[str, ...] = ()
    notes: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    recommendation: str | None = None
    override: str | None = None


@dataclass(frozen=True)
class StepContext:
    """Context handed to ``Step.run`` at dispatch time.

    ``state`` is typed ``Any`` in Sprint 1: the live megaplan ``PlanState``
    is a ``TypedDict`` at ``megaplan/types.py:146``, and tightening the
    annotation belongs to Sprint 2 once the port is in flight.
    """

    plan_dir: Path
    state: Any
    profile: Any
    mode: str
    inputs: Mapping[str, Path] = field(default_factory=dict)
    budget: Any = None
    envelope: RunEnvelope = field(default_factory=lambda: EMPTY_ENVELOPE)


@dataclass(frozen=True)
class StepResult:
    """What a ``Step.run`` invocation returns.

    ``outputs`` maps a label to a filesystem path. The executor verifies
    existence only; layout under ``ctx.plan_dir`` is unconstrained beyond
    that. ``next`` is matched against the enclosing stage's edges (with
    ``'halt'`` reserved). ``state_patch`` is applied to working state via
    a defensive ``dict(...)`` copy.
    """

    outputs: Mapping[str, Path] = field(default_factory=dict)
    verdict: "PipelineVerdict | None" = None
    next: NextEdge = "halt"
    state_patch: Mapping[str, Any] = field(default_factory=dict)
    envelope: RunEnvelope = field(default_factory=lambda: EMPTY_ENVELOPE)


@runtime_checkable
class Step(Protocol):
    """Structural Protocol for pipeline steps.

    Implementations must expose ``name``, ``kind``, ``prompt_key``, and
    ``slot`` as attributes, plus a ``run(ctx)`` method returning a
    ``StepResult``. ``@runtime_checkable`` enables ``isinstance(obj, Step)``
    sanity checks; a missing attribute surfaces at instantiation/check
    time rather than as a silent miss.

    ``produces`` and ``consumes`` are INSTANCE-level typed-port
    declarations (no ``ClassVar``) read by the binder only when
    :func:`megaplan._pipeline.flags.typed_ports_on` returns true.
    Implementations may inherit defaults from :class:`StepMixin`.
    """

    name: str
    kind: Literal["produce", "judge", "decide", "subloop", "override"]
    prompt_key: str | None
    slot: str | None
    produces: tuple["Port", ...]
    consumes: tuple["PortRef", ...]

    def run(self, ctx: StepContext) -> StepResult: ...


@dataclass
class StepMixin:
    """Default typed-port declarations for ``@dataclass`` Step classes.

    Provides empty ``produces``/``consumes`` tuples via
    ``field(default_factory=tuple)`` so dataclass Step subclasses satisfy
    the :class:`Step` Protocol's instance-level attribute contract without
    boilerplate. Non-dataclass Step implementations can subclass
    :class:`StepMixinProperty` instead (returns ``()`` via ``@property``).
    """

    produces: tuple["Port", ...] = field(default_factory=tuple)
    consumes: tuple["PortRef", ...] = field(default_factory=tuple)


class StepMixinProperty:
    """Property-based default typed-port declarations for non-dataclass Steps."""

    @property
    def produces(self) -> tuple["Port", ...]:  # pragma: no cover - trivial
        return ()

    @property
    def consumes(self) -> tuple["PortRef", ...]:  # pragma: no cover - trivial
        return ()


@dataclass(frozen=True)
class Stage:
    """A single-Step stage with labelled outgoing edges.

    ``produces`` / ``consumes`` (M2 / T1b) optionally override the wrapped
    Step's typed-port declarations. When empty, the binder falls back to
    the Step's own ``produces`` / ``consumes`` tuples. Read by the binder
    only when :func:`megaplan._pipeline.flags.typed_ports_on` is true.

    ``decision_vocabulary`` / ``override_vocabulary`` (M3b T2) declare
    the allowed decision keys and override actions for this stage.
    When non-empty, the Arnold routing resolver validates incoming
    signals against these sets.
    """

    name: str
    step: Step
    edges: tuple[Edge, ...] = ()
    produces: tuple["Port", ...] = field(default_factory=tuple)
    consumes: tuple["PortRef", ...] = field(default_factory=tuple)
    loop_condition: Callable[[Any], bool] | None = None
    decision_vocabulary: frozenset[str] = field(default_factory=frozenset)
    override_vocabulary: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class ParallelStage:
    """A fan-out stage whose Steps run concurrently and barrier-join.

    The executor submits each step to a ``ThreadPoolExecutor`` and passes
    the ordered list of ``StepResult`` values to ``join`` along with the
    shared ``StepContext``. ``join`` returns a single ``StepResult`` whose
    ``next`` label dispatches like a regular Stage. The empty-steps case
    is guarded in the executor via ``max(1, max_workers or len(steps))``.

    **Thread-safety contract**: every Step in ``steps`` MUST be hermetic
    with respect to shared mutable state. Steps that read or write the
    plan's ``state.json`` (e.g. :class:`InProcessHandlerStep`) are NOT
    safe for parallel fan-out — concurrent handler invocations would race
    through the same plan directory. The executor enforces this at
    submission time: a ``ParallelStage`` containing an
    ``InProcessHandlerStep`` is rejected with a ``ValueError`` before any
    handler executes. Hermetic steps such as ``PanelReviewerStep`` (which
    writes to a per-reviewer output directory and does not touch shared
    state) satisfy the contract.
    """

    name: str
    steps: tuple[Step, ...]
    join: Callable[[list[StepResult], StepContext], StepResult]
    edges: tuple[Edge, ...] = ()
    max_workers: int | None = None
    produces: tuple["Port", ...] = field(default_factory=tuple)
    consumes: tuple["PortRef", ...] = field(default_factory=tuple)
    decision_vocabulary: frozenset[str] = field(default_factory=frozenset)
    override_vocabulary: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Overlay:
    """A named transformation from one Pipeline to another.

    Overlays let profiles add/remove/wrap stages without mutating the base
    ``Pipeline``. Sprint 1 defines only the shape; application is Sprint 2.
    """

    name: str
    apply: Callable[["Pipeline"], "Pipeline"]


@dataclass(frozen=True)
class Pipeline:
    """A named graph of stages with an entry point and optional overlays."""

    stages: Mapping[str, "Stage | ParallelStage"]
    entry: str
    overlays: tuple[Overlay, ...] = ()
    binding_map: dict | None = None
    resource_bundles: tuple[Any, ...] = field(default_factory=tuple)

    @classmethod
    def builder(
        cls,
        name: str,
        description: str = "",
        *,
        default_profile: str | None = None,
        supported_modes: tuple[str, ...] = (),
        pipeline_dir: Path | None = None,
        worker: "Callable[..., str] | None" = None,
        prompt_registry: "Callable[[str], str] | None" = None,
        pipeline_version: int = 1,
    ) -> "Any":
        """Return a :class:`PipelineBuilder` for fluent construction.

        Pipeline-level metadata (``description`` / ``default_profile`` /
        ``supported_modes``) is held on the returned builder rather than
        the frozen :class:`Pipeline` dataclass — the dataclass has only
        ``stages / entry / overlays`` (T1.j audit). The
        :class:`PipelineRegistry` surfaces the metadata via
        ``PipelineRegistry.metadata`` (T9). Imported lazily to avoid an
        import cycle (``builder`` depends on this module)."""
        from arnold.pipelines.megaplan._pipeline.builder import PipelineBuilder

        return PipelineBuilder(
            name=name,
            description=description,
            default_profile=default_profile,
            supported_modes=tuple(supported_modes),
            pipeline_dir=pipeline_dir,
            worker=worker,
            prompt_registry=prompt_registry,
            pipeline_version=pipeline_version,
        )

    def run_phase(
        self,
        phase: str,
        *,
        plan: str,
        cwd: Path | None = None,
        plan_dir: Path | None = None,
        argv: list[str] | tuple[str, ...] | None = None,
        progress_env: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        """Run one planning phase in-process and return a CLI-like tuple.

        The auto-driver used to shell out for each phase and then inspect the
        phase_result.json written by the handler. This keeps that contract but
        dispatches the selected stage directly, so only one phase runs.
        """

        import argparse
        import contextlib
        import dataclasses
        import io

        from arnold.pipelines.megaplan._core import find_plan_dir
        from arnold.pipelines.megaplan._core.io import json_dump
        from arnold.pipelines.megaplan.types import CliError

        root = Path(cwd or Path.cwd())
        resolved_plan_dir = Path(plan_dir) if plan_dir is not None else find_plan_dir(root, plan)
        if resolved_plan_dir is None:
            return 1, "", f"Plan {plan!r} does not exist"

        stdout = io.StringIO()
        stderr = io.StringIO()

        try:
            if phase == "feedback" and phase not in self.stages:
                from arnold.pipelines.megaplan.cli.feedback import handle_feedback

                args = _phase_namespace(
                    phase,
                    plan=plan,
                    argv=argv,
                    progress_env=progress_env,
                )
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    response = handle_feedback(root, args)
                return 0, stdout.getvalue() or json_dump(response), stderr.getvalue()

            if phase not in self.stages:
                return 1, "", f"phase {phase!r} is not in pipeline; available: {sorted(self.stages)}"

            node = self.stages[phase]
            if not isinstance(node, Stage):
                return 1, "", f"phase {phase!r} is not a single-stage phase"

            state = _read_phase_state(resolved_plan_dir)
            overrides = _phase_arg_overrides(phase, argv=argv)
            step = node.step
            if overrides and hasattr(step, "arg_overrides"):
                current = getattr(step, "arg_overrides", {}) or {}
                step = dataclasses.replace(step, arg_overrides={**dict(current), **overrides})
            ctx = StepContext(
                plan_dir=resolved_plan_dir,
                state=state,
                profile={
                    "root": root,
                    "project_dir": (state.get("config") or {}).get("project_dir", str(root)),
                },
                mode=(state.get("config") or {}).get("mode", "code"),
                inputs={"_pipeline": "megaplan", "_progress_env": progress_env or {}},
            )
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = step.run(ctx)
            payload = {
                "success": True,
                "step": phase,
                "next": result.next,
                "outputs": {key: str(value) for key, value in result.outputs.items()},
            }
            return 0, stdout.getvalue() or json_dump(payload), stderr.getvalue()
        except CliError as error:
            payload: dict[str, Any] = {
                "success": False,
                "error": error.code,
                "message": error.message,
            }
            if error.extra:
                payload["details"] = dict(error.extra)
            return error.exit_code, stdout.getvalue(), stderr.getvalue() + json_dump(payload)
        except Exception as error:  # noqa: BLE001 - preserve CLI-like failure surface.
            return 1, stdout.getvalue(), stderr.getvalue() + f"{type(error).__name__}: {error}"


def _read_phase_state(plan_dir: Path) -> dict[str, Any]:
    path = Path(plan_dir) / "state.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _phase_arg_overrides(
    phase: str,
    *,
    argv: list[str] | tuple[str, ...] | None,
) -> dict[str, Any]:
    args = list(argv or [phase])
    if args and args[0] == phase:
        args = args[1:]
    if phase == "feedback" and args and args[0] == "workflow":
        args = args[1:]
    overrides: dict[str, Any] = {}
    phase_models: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token == "--fresh":
            overrides["fresh"] = True
        elif token == "--persist":
            overrides["persist"] = True
        elif token == "--ephemeral":
            overrides["ephemeral"] = True
        elif token == "--confirm-destructive":
            overrides["confirm_destructive"] = True
        elif token == "--user-approved":
            overrides["user_approved"] = True
        elif token == "--retry-blocked-tasks":
            overrides["retry_blocked_tasks"] = True
        elif token == "--confirm-self-review":
            overrides["confirm_self_review"] = True
        elif token in {"--batch", "--profile", "--agent", "--work-dir"} and index + 1 < len(args):
            key = token[2:].replace("-", "_")
            value: Any = args[index + 1]
            if key == "batch":
                try:
                    value = int(value)
                except ValueError:
                    pass
            overrides[key] = value
            index += 1
        elif token == "--phase-model" and index + 1 < len(args):
            phase_models.append(args[index + 1])
            index += 1
        elif token == "--plan" and index + 1 < len(args):
            index += 1
        index += 1
    if phase_models:
        overrides["phase_model"] = phase_models
        overrides["_live_phase_model_steps"] = {
            item.split("=", 1)[0] for item in phase_models if "=" in item
        }
    return overrides


def _phase_namespace(
    phase: str,
    *,
    plan: str,
    argv: list[str] | tuple[str, ...] | None,
    progress_env: dict[str, str] | None,
) -> Any:
    import argparse

    from arnold.pipelines.megaplan.orchestration.progress import ProgressEmitter

    overrides = _phase_arg_overrides(phase, argv=argv)
    operation = "edit"
    raw = list(argv or [phase])
    if phase == "feedback" and len(raw) > 1:
        operation = raw[1]
    defaults: dict[str, Any] = {
        "plan": plan,
        "operation": operation,
        "force": False,
        "actor": None,
        "all": False,
        "emit_json": False,
        "agent": None,
        "hermes": None,
        "phase_model": [],
        "profile": None,
        "fresh": False,
        "persist": False,
        "ephemeral": False,
        "work_dir": None,
        "confirm_destructive": False,
        "user_approved": False,
        "retry_blocked_tasks": False,
        "batch": None,
        "confirm_self_review": False,
        "progress_emitter": ProgressEmitter.from_env(progress_env),
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ── Typed Port / Content-Type / Reduce primitives ───────────────────────
# M3a bridge: these concrete neutral types now live in arnold.pipeline.types.
# Re-exported here so legacy megaplan._pipeline.types consumers continue
# to compile.  Delete these re-exports in M7 when old paths are removed.


from arnold.pipeline.types import (  # noqa: E402  # M3a compatibility bridge; delete in M7
    CONTENT_TYPES,
    ContentTypeRegistry,
    Port,
    PortRef,
    ReduceResult,
    RoutingKey,
    SelectionResult,
    _canonical_json_dumps,
    register_schema,
)

# ── Reduce TypeAlias (stays in megaplan — depends on megaplan StepContext/StepResult) ──

Reduce: TypeAlias = Callable[[list[StepResult], StepContext], ReduceResult]


# ── State delta (CAS) primitives (M2 / T2b) ────────────────────────────


class StateDeltaConflict(Exception):
    """Raised by :func:`apply_delta` when the delta's ``version`` does not
    match the current version recorded in ``state['_state_meta']['versions']``.

    Carries the offending ``key``, the ``expected`` version that the delta
    claimed, and the ``actual`` version observed in state at apply time.
    """

    def __init__(self, key: str, expected: int, actual: int) -> None:
        super().__init__(
            f"state delta for key {key!r} expected version {expected}, "
            f"found {actual}"
        )
        self.key = key
        self.expected = expected
        self.actual = actual


@dataclass(frozen=True)
class StateDelta:
    """Compare-and-swap state mutation.

    ``op`` is one of:

    * ``'replace'`` — last-writer-wins assignment of ``value`` at ``key``.
    * ``'accumulate'`` — append ``value`` to an existing list at ``key``
      (creating ``[]`` if missing); retains all prior entries.
    * ``'deep_merge'`` — recursively merge ``value`` (a mapping) into the
      mapping at ``key``; non-mapping leaves are overwritten.

    ``version`` is the version the writer last observed for ``key``.
    :func:`apply_delta` raises :class:`StateDeltaConflict` when the
    actual version in ``state['_state_meta']['versions']`` differs.
    """

    op: Literal["replace", "accumulate", "deep_merge"]
    key: str
    value: Any
    version: int


def _deep_merge(base: Any, overlay: Any) -> Any:
    if isinstance(base, dict) and isinstance(overlay, Mapping):
        out = dict(base)
        for k, v in overlay.items():
            out[k] = _deep_merge(out.get(k), v) if k in out else v
        return out
    return overlay


def apply_delta(
    state: Mapping[str, Any], delta: StateDelta
) -> tuple[dict[str, Any], int]:
    """Apply *delta* to *state* under CAS semantics.

    Returns ``(new_state, new_version)``. Raises
    :class:`StateDeltaConflict` when ``delta.version`` does not match the
    version recorded at ``state['_state_meta']['versions'][delta.key]``
    (absent ⇒ ``0``).
    """
    new_state: dict[str, Any] = dict(state)
    meta = dict(new_state.get("_state_meta", {}))
    versions = dict(meta.get("versions", {}))
    actual = int(versions.get(delta.key, 0))
    if actual != delta.version:
        raise StateDeltaConflict(delta.key, delta.version, actual)

    if delta.op == "replace":
        new_state[delta.key] = delta.value
    elif delta.op == "accumulate":
        existing = list(new_state.get(delta.key, []))
        existing.append(delta.value)
        new_state[delta.key] = existing
    elif delta.op == "deep_merge":
        existing = new_state.get(delta.key, {})
        new_state[delta.key] = _deep_merge(existing, delta.value)
    else:  # pragma: no cover - exhaustive Literal
        raise ValueError(f"unknown StateDelta op: {delta.op!r}")

    new_version = actual + 1
    versions[delta.key] = new_version
    meta["versions"] = versions
    new_state["_state_meta"] = meta
    return new_state, new_version
