"""Deprecated re-export bridge for megaplan._pipeline.types.

Neutral carriers (Port, PortRef, ContentTypeRegistry, ReduceResult,
SelectionResult, ContentRoutingKey, RoutingKey, RoutingKeyKind,
_canonical_json_dumps, register_schema) are imported from
:mod:`arnold.pipeline.types`.

Policy symbols (GateRecommendation, OverrideAction, EdgeKind, NextEdge,
Overlay, StepMixin, StepMixinProperty, StateDelta) and Megaplan-specific
variants of the core DAG types (Edge, PipelineVerdict, StepContext,
StepResult, Step, Stage, ParallelStage, Pipeline with ``run_phase``
and ``builder``) are kept local in this module for backward compatibility.

Import from :mod:`arnold.pipeline.types` for neutral carriers — import
from here only if you depend on the Megaplan opinionated shapes.
"""

from __future__ import annotations

import hashlib
import json
import warnings
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

warnings.warn(
    "megaplan._pipeline.types is deprecated; "
    "import neutral carriers from arnold.pipeline.types instead.",
    DeprecationWarning,
    stacklevel=2,
)

# ── Neutral carriers imported from arnold ──────────────────────────────

from arnold.pipeline.types import (  # noqa: E402
    ContentRoutingKey,
    ContentTypeRegistry,
    Port,
    PortRef,
    ReduceResult,
    RoutingKey,
    RoutingKeyKind,
    SelectionResult,
    _canonical_json_dumps,
    register_schema,
)

# ── Megaplan policy literals (kept local per SD10) ─────────────────────

GateRecommendation = Literal["proceed", "iterate", "tiebreaker", "escalate"]
OverrideAction = Literal["force_proceed", "abort", "replan", "add_note"]
EdgeKind = Literal["normal", "gate", "override"]
NextEdge = str

# ── Megaplan envelope import ───────────────────────────────────────────

from megaplan._pipeline.envelope import EMPTY_ENVELOPE, RunEnvelope  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - typing-only aliases
    BudgetRef = Any
    Profile = Any


# ── Core DAG types (Megaplan variants with extra fields) ───────────────


@dataclass(frozen=True)
class Edge:
    """A labelled transition from one stage to another.

    Dispatch depends on ``kind``:

    * ``kind == "normal"`` (default): the executor matches when
      ``Edge.label == StepResult.next``. ``label`` is the sole match key.
    * ``kind == "gate"``: the executor matches when
      ``Edge.recommendation == StepResult.verdict.recommendation``.
      ``label`` is NOT consulted for dispatch and is held only for
      debug-readable rendering (planning emits the recommendation name as
      the label, e.g. ``"iterate"``).
    * ``kind == "override"``: reserved for Chunk D; not dispatched by the
      Chunk-A executor.

    ``target`` is the name of the next stage in ``Pipeline.stages``. The
    reserved target ``'halt'`` terminates the pipeline.
    """

    label: str
    target: str
    kind: EdgeKind = "normal"
    recommendation: GateRecommendation | None = None


@dataclass(frozen=True)
class PipelineVerdict:
    """Structured output of a judge-kind Step.

    ``score`` is a float in ``[0.0, 1.0]`` by convention but is not
    enforced here. ``flags`` and ``notes`` are free-form. ``payload`` is a
    Mapping for arbitrary structured detail; see the immutability note in
    the module docstring.

    ``recommendation`` is the typed gate signal consumed by the executor's
    ``kind == "gate"`` edge dispatch (Sprint 4 Chunk A). When set, the
    executor matches the enclosing stage's gate edges by
    ``Edge.recommendation == verdict.recommendation`` in preference to the
    legacy ``Edge.label == result.next`` path. ``override`` is added now
    for forward compatibility with Chunk D's override-edge dispatch; the
    Chunk-A executor does not consume it.
    """

    score: float
    flags: tuple[str, ...] = ()
    notes: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    recommendation: GateRecommendation | None = None
    override: OverrideAction | None = None


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
    """

    name: str
    step: Step
    edges: tuple[Edge, ...] = ()
    produces: tuple["Port", ...] = field(default_factory=tuple)
    consumes: tuple["PortRef", ...] = field(default_factory=tuple)
    loop_condition: Callable[[Any], bool] | None = None


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
        from megaplan._pipeline.builder import PipelineBuilder

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

        from megaplan._core import find_plan_dir
        from megaplan._core.io import json_dump
        from megaplan.types import CliError

        root = Path(cwd or Path.cwd())
        resolved_plan_dir = Path(plan_dir) if plan_dir is not None else find_plan_dir(root, plan)
        if resolved_plan_dir is None:
            return 1, "", f"Plan {plan!r} does not exist"

        stdout = io.StringIO()
        stderr = io.StringIO()

        try:
            if phase == "feedback" and phase not in self.stages:
                from megaplan.cli.feedback import handle_feedback

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

    from megaplan.orchestration.progress import ProgressEmitter

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


# ── Content type registry (module-level builtins) ──────────────────────

_BUILTIN_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "text/markdown",
        "image/png",
        "application/x-git-diff",
        "application/x-verdict+json",
        "application/x-routing-key+json",
        "application/x-fanout-results+json",
        "application/x-evaluand-record+json",
    }
)

CONTENT_TYPES = ContentTypeRegistry()
for _ct in sorted(_BUILTIN_CONTENT_TYPES):
    CONTENT_TYPES.register(_ct, {"content_type": _ct})


# ── Reduce TypeAlias ───────────────────────────────────────────────────

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
