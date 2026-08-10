"""Native runtime decorators for ``@phase``, ``@pipeline``, and ``@decision``.

These are lightweight markers that register phase functions, pipeline
generators, and decision callables with the native runtime.  They compose
with the native runner's dict-based context and state propagation.

Ownership:
    Decorated ``.pypeline`` modules and named native subworkflows own the
    source-visible product topology.  Boundary contract annotations on
    phases declare durable effects only — they do not define or own
    workflow topology.
"""

from __future__ import annotations

import builtins
import inspect
from typing import Any, Callable


# ── Decorators ──────────────────────────────────────────────────────────


def phase(
    name: str | None = None,
    *,
    id: str | None = None,
    description: str | None = None,
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    produces: tuple = (),
    consumes: tuple = (),
    # ── Side-effect metadata (M1) ──
    operation: str | None = None,
    target: str | None = None,
    idempotency_key: str | None = None,
    effect_class: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a function as a native pipeline phase.

    Supports both ``@phase`` and ``@phase(...)`` usage.

    Parameters
    ----------
    name:
        Phase name (defaults to the function name).
    id:
        Stable semantic identity for this phase.  When ``None`` (default)
        the compiler derives identity from the canonical callable name.
        An explicit value is the durability contract — stable across
        compilation, projection, trace emission, and replay.
    description:
        Optional human-readable description.
    inputs:
        Declared input schema metadata (``dict[str, Any]``).  Must be
        serializable and comparable without executing the callable body.
        When ``None`` (default) the compiler treats inputs as untyped.
    outputs:
        Declared output schema metadata (``dict[str, Any]``).  Same
        serializability contract.  When ``None`` outputs are untyped.
    produces:
        Typed ports this phase produces.
    consumes:
        Typed ports this phase consumes.
    operation:
        For side-effecting phases: canonical operation type from the effect
        taxonomy (e.g. ``'file_write'``, ``'git_commit'``).  ``None`` for
        pure phases.  Must be one of the recognised operation literals.
    target:
        For side-effecting phases: stable target identifier for the operation
        (e.g. a relpath, branch name).  ``None`` when no target is declared
        or the phase is pure.
    idempotency_key:
        For side-effecting phases: explicit idempotency key for the effect
        ledger.  When ``None`` and *operation* is set, the compiler derives a
        stable key from ``(step_path, operation, target)``.  Ignored for pure
        phases.
    effect_class:
        For side-effecting phases: effect class from the taxonomy
        (e.g. ``'filesystem_mutation'``).  ``None`` for pure phases.

    Returns
    -------
    Callable
        The decorated function with ``__phase_name__``, ``__phase_description__``,
        ``__phase_produces__``, ``__phase_consumes__``, ``__step_id__``,
        ``__step_inputs__``, ``__step_outputs__``, ``__phase__``, and
        side-effect attributes (``__phase_operation__``, ``__phase_target__``,
        ``__phase_idempotency_key__``, ``__phase_effect_class__``) attached.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn.__phase__ = True  # type: ignore[attr-defined]
        fn.__phase_name__ = name if isinstance(name, str) else fn.__name__  # type: ignore[attr-defined]
        fn.__phase_description__ = description  # type: ignore[attr-defined]
        fn.__phase_produces__ = produces  # type: ignore[attr-defined]
        fn.__phase_consumes__ = consumes  # type: ignore[attr-defined]
        fn.__step_id__ = id  # type: ignore[attr-defined]
        fn.__step_inputs__ = inputs  # type: ignore[attr-defined]
        fn.__step_outputs__ = outputs  # type: ignore[attr-defined]
        # Side-effect metadata (M1)
        fn.__phase_operation__ = operation  # type: ignore[attr-defined]
        fn.__phase_target__ = target  # type: ignore[attr-defined]
        fn.__phase_idempotency_key__ = idempotency_key  # type: ignore[attr-defined]
        fn.__phase_effect_class__ = effect_class  # type: ignore[attr-defined]
        return fn

    if callable(name):
        return decorator(name)
    return decorator


def step(
    name: str | None = None,
    *,
    id: str | None = None,
    description: str | None = None,
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    produces: tuple = (),
    consumes: tuple = (),
    # ── Side-effect metadata (M1) ──
    operation: str | None = None,
    target: str | None = None,
    idempotency_key: str | None = None,
    effect_class: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a function as a step (preferred authoring alias for ``@phase``).

    Identical to :func:`phase` — all parameters and dunder attributes are the
    same.  ``@step`` is the public authoring name; ``@phase`` remains as a
    compatibility alias.

    Parameters
    ----------
    name:
        Step name (defaults to the function name).
    id:
        Stable semantic identity (defaults to ``None`` — compiler-derived).
    description:
        Optional human-readable description.
    inputs:
        Declared input schema metadata (``dict[str, Any] | None``).
    outputs:
        Declared output schema metadata (``dict[str, Any] | None``).
    produces:
        Typed ports this step produces.
    consumes:
        Typed ports this step consumes.
    operation:
        For side-effecting steps: canonical operation type from the effect
        taxonomy (e.g. ``'file_write'``, ``'git_commit'``).
    target:
        For side-effecting steps: stable target identifier for the operation.
    idempotency_key:
        For side-effecting steps: explicit idempotency key for the effect
        ledger.
    effect_class:
        For side-effecting steps: effect class from the taxonomy
        (e.g. ``'filesystem_mutation'``).

    Returns
    -------
    Callable
        The decorated function with the same dunder attributes as ``@phase``,
        including ``__step_id__``, ``__step_inputs__``, and ``__step_outputs__``.
    """
    return phase(
        name=name,
        id=id,
        description=description,
        inputs=inputs,
        outputs=outputs,
        produces=produces,
        consumes=consumes,
        operation=operation,
        target=target,
        idempotency_key=idempotency_key,
        effect_class=effect_class,
    )


def pipeline(
    name: str | None = None,
    *,
    id: str | None = None,
    description: str | None = None,
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a generator function as a native pipeline.

    Supports both ``@pipeline`` and ``@pipeline(...)`` usage.

    Parameters
    ----------
    name:
        Pipeline name (defaults to the function name).
    id:
        Stable workflow identity.  When ``None`` (default) the compiler
        derives identity from the canonical callable name.  An explicit
        value is the durability contract.
    description:
        Optional human-readable description.
    inputs:
        Declared workflow input schema metadata (``dict[str, Any]``).
        Must be serializable and comparable without executing the body.
        When ``None`` (default) inputs are untyped.
    outputs:
        Declared workflow output schema metadata (``dict[str, Any]``).
        Same serializability contract.  When ``None`` outputs are untyped.

    Returns
    -------
    Callable
        The decorated function with ``__pipeline__``, ``__pipeline_name__``,
        ``__pipeline_description__``, ``__workflow_id__``,
        ``__workflow_inputs__``, and ``__workflow_outputs__`` attributes
        attached.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn.__pipeline__ = True  # type: ignore[attr-defined]
        fn.__pipeline_name__ = name if isinstance(name, str) else fn.__name__  # type: ignore[attr-defined]
        fn.__pipeline_description__ = description  # type: ignore[attr-defined]
        fn.__workflow_id__ = id  # type: ignore[attr-defined]
        fn.__workflow_inputs__ = inputs  # type: ignore[attr-defined]
        fn.__workflow_outputs__ = outputs  # type: ignore[attr-defined]
        return fn

    if callable(name):
        return decorator(name)
    return decorator


def workflow(
    name: str | None = None,
    *,
    id: str | None = None,
    description: str | None = None,
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a function as a workflow (preferred authoring alias for ``@pipeline``).

    Identical to :func:`pipeline` — all parameters and dunder attributes are the
    same.  ``@workflow`` is the public authoring name; ``@pipeline`` remains as a
    compatibility alias.

    Parameters
    ----------
    name:
        Workflow name (defaults to the function name).
    id:
        Stable workflow identity (defaults to ``None`` — compiler-derived).
    description:
        Optional human-readable description.
    inputs:
        Declared workflow input schema metadata (``dict[str, Any] | None``).
    outputs:
        Declared workflow output schema metadata (``dict[str, Any] | None``).

    Returns
    -------
    Callable
        The decorated function with the same dunder attributes as ``@pipeline``,
        including ``__workflow_id__``, ``__workflow_inputs__``, and
        ``__workflow_outputs__``.
    """
    return pipeline(
        name=name,
        id=id,
        description=description,
        inputs=inputs,
        outputs=outputs,
    )


def decision(
    name: str | None = None,
    *,
    description: str | None = None,
    vocabulary: frozenset[str] = frozenset(),
    human_gate: bool = False,
    artifact_stage: str = "",
    choices: tuple[str, ...] = (),
    resume_input_schema: dict[str, Any] | None = None,
    override_routes: dict[str, str | None] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a function as a native decision point.

    Supports both ``@decision`` and ``@decision(...)`` usage.

    Parameters
    ----------
    name:
        Decision name (defaults to the function name).
    description:
        Optional human-readable description.
    vocabulary:
        Set of valid return labels (e.g. ``frozenset({'pass', 'fail'})``).
    human_gate:
        When ``True``, this decision is a human-gate suspension point.
        Default ``False`` — ordinary decisions are unaffected.
    artifact_stage:
        For human-gate decisions: the name of the stage whose artifact
        the user inspects.  Empty string for ordinary decisions.
    choices:
        For human-gate decisions: ordered human-action labels
        (e.g. ``('continue', 'stop')``).  Empty tuple for ordinary decisions.
    resume_input_schema:
        For human-gate decisions: optional JSON Schema dict for resume
        input validation.  ``None`` (the default) means no validation.
    override_routes:
        For human-gate decisions: optional per-choice route overrides
        (e.g. ``{'continue': 'panel_review', 'stop': 'halt'}``).
        ``None`` (the default) means no overrides.

    Returns
    -------
    Callable
        The decorated function with ``__decision__``, ``__decision_name__``,
        ``__decision_description__``, ``__decision_vocabulary__``, and
        (when ``human_gate=True``) ``__decision_human_gate__``,
        ``__decision_artifact_stage__``, ``__decision_choices__``,
        ``__decision_resume_input_schema__``, and
        ``__decision_override_routes__`` attributes attached.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn.__decision__ = True  # type: ignore[attr-defined]
        fn.__decision_name__ = name if isinstance(name, str) else fn.__name__  # type: ignore[attr-defined]
        fn.__decision_description__ = description  # type: ignore[attr-defined]
        fn.__decision_vocabulary__ = vocabulary  # type: ignore[attr-defined]
        # Human-gate metadata (attached unconditionally so introspection
        # helpers can always read them — ordinary decisions get defaults).
        fn.__decision_human_gate__ = human_gate  # type: ignore[attr-defined]
        fn.__decision_artifact_stage__ = artifact_stage  # type: ignore[attr-defined]
        fn.__decision_choices__ = choices  # type: ignore[attr-defined]
        fn.__decision_resume_input_schema__ = resume_input_schema  # type: ignore[attr-defined]
        fn.__decision_override_routes__ = override_routes  # type: ignore[attr-defined]
        # Source-location and routing-body marker (attached unconditionally
        # so the validator can produce line-specific diagnostics).
        fn.__decision_source_file__ = inspect.getsourcefile(fn)  # type: ignore[attr-defined]
        try:
            _, start_lineno = inspect.getsourcelines(fn)
            fn.__decision_first_lineno__ = start_lineno  # type: ignore[attr-defined]
        except (OSError, TypeError):
            fn.__decision_first_lineno__ = None  # type: ignore[attr-defined]
        fn.__decision_routing_body__ = True  # type: ignore[attr-defined]
        return fn

    if callable(name):
        return decorator(name)
    return decorator


class _ParallelBranchList(list):
    """A list subclass that can carry parallel-block metadata.

    Built-in ``list`` instances do not accept arbitrary attributes, so
    this subclass exists solely to let :func:`parallel` attach the
    compiler-introspection metadata it needs while still behaving like a
    normal list.
    """

    __parallel_branches__: tuple[Callable[..., Any], ...] = ()
    __parallel_reducer__: Callable[..., Any] | None = None
    __parallel_name__: str | None = None
    __parallel_id__: str | None = None


def parallel(
    branches: tuple[Callable[..., Any], ...] | list[Callable[..., Any]],
    *,
    reducer: Callable[..., Any] | None = None,
    name: str | None = None,
    id: str | None = None,
) -> _ParallelBranchList:
    """Declare a parallel fan-out block for use in native pipelines.

    Used inside a ``@pipeline``-decorated function with ``for`` syntax::

        for branch in parallel([branch_a, branch_b], reducer=my_reducer):
            state = yield branch(ctx)

    Parameters
    ----------
    branches:
        A list or tuple of ``@phase``-decorated callables.  Must be a
        **literal** list/tuple — dynamic or non-literal branch sets are
        rejected at compile time.
    reducer:
        Optional callable invoked after all branches complete.  Receives
        a list of branch results (one per branch, in declaration order)
        and must return a dict to merge into working state.
    name:
        Optional human-readable name for the parallel block (defaults to
        a generated name like ``parallel_0``).
    id:
        Optional stable call-site identity for this parallel block.
        When set, this becomes the ``call_site_path`` in the compiled
        instruction rather than an auto-generated name.

    Returns
    -------
    _ParallelBranchList
        The branch list (returned as a list-like object for iteration by
        the compiler), with metadata attached for compile-time validation.
    """
    if not isinstance(branches, (tuple, list)):
        raise TypeError(
            f"parallel() expects a list or tuple of branches, got {type(branches).__name__}"
        )
    if len(branches) == 0:
        raise ValueError("parallel() requires at least one branch")
    seen: set[int] = set()
    for i, b in enumerate(branches):
        if not callable(b):
            raise TypeError(
                f"parallel() branch {i} is not callable: {b!r}"
            )
        if not is_phase(b):
            raise TypeError(
                f"parallel() branch {i} ({getattr(b, '__name__', b)!r}) is not a @phase-decorated function"
            )
        bid = builtins.id(b)
        if bid in seen:
            raise ValueError(
                f"parallel() contains duplicate branch: {getattr(b, '__name__', b)!r}"
            )
        seen.add(bid)
    # Attach metadata for compiler introspection
    result = _ParallelBranchList(branches)
    result.__parallel_branches__ = tuple(branches)
    result.__parallel_reducer__ = reducer
    result.__parallel_name__ = name
    result.__parallel_id__ = id
    return result


# ── Dynamic parallel_map helper ────────────────────────────────────────


class _ParallelMapDeclaration:
    """Carries ``parallel_map`` metadata for compiler introspection.

    This is a lightweight marker object — not a list-like — because
    ``parallel_map`` declares a runtime-list fan-out rather than a
    compile-time-literal branch set.  The compiler inspects the
    attributes to build a :class:`~arnold.pipeline.native.ir.ParallelMapInstruction`.
    """

    __parallel_map_items__: str = ""
    __parallel_map_step__: Callable[..., Any] | None = None
    __parallel_map_reducer__: Callable[..., Any] | None = None
    __parallel_map_path_template__: str = ""
    __parallel_map_name__: str | None = None
    __parallel_map_id__: str | None = None


def parallel_map(
    *,
    items: str,
    step: Callable[..., Any],
    reducer: Callable[..., Any] | None = None,
    path_template: str = "",
    name: str | None = None,
    id: str | None = None,
) -> _ParallelMapDeclaration:
    """Declare a dynamic runtime-list fan-out for use in native pipelines.

    Used inside a ``@pipeline``- or ``@workflow``-decorated function to
    declare that a mapper callable should be applied to each item of a
    collection resolved at runtime::

        @workflow(id="batch_review")
        def batch_review(checks: list[Check]):
            parallel_map(
                items="checks",
                step=critique_lens,
                reducer=merge_findings,
                path_template="critique/{item_id}",
            )

    This is a **distinct** construct from :func:`parallel`: ``parallel``
    declares statically-bounded branches known at compile time, while
    ``parallel_map`` declares a dynamic fan-out whose cardinality is
    resolved at execution time.

    Parameters
    ----------
    items:
        Reference to the runtime collection — a parameter name or state
        key that resolves to an iterable at execution time.
    step:
        The ``@phase``- or ``@workflow``-decorated callable applied to
        each item.
    reducer:
        Optional callable invoked after all items complete.  Receives
        a list of per-item results (one per item, in iteration order)
        and must return a dict to merge into working state.
    path_template:
        Optional template for per-item call-site paths
        (e.g. ``'critique/{item_id}'``).  Variables in braces are
        resolved from item attributes at execution time.
    name:
        Optional human-readable name for the parallel_map block
        (defaults to a generated name like ``parallel_map_0``).
    id:
        Optional stable call-site identity for this parallel_map block.
        When set, this becomes the ``call_site_path`` in the compiled
        instruction rather than an auto-generated name.

    Returns
    -------
    _ParallelMapDeclaration
        A metadata-carrying object for compiler introspection.
    """
    if not isinstance(items, str) or not items:
        raise TypeError(
            f"parallel_map() 'items' must be a non-empty str, got {items!r}"
        )
    if not callable(step):
        raise TypeError(
            f"parallel_map() 'step' must be callable, got {type(step).__name__}"
        )
    result = _ParallelMapDeclaration()
    result.__parallel_map_items__ = items
    result.__parallel_map_step__ = step
    result.__parallel_map_reducer__ = reducer
    result.__parallel_map_path_template__ = path_template
    result.__parallel_map_name__ = name
    result.__parallel_map_id__ = id
    return result


# ── Native panel helper ────────────────────────────────────────────────


def native_panel(
    name: str,
    reviewers: tuple[tuple[str, Callable[..., Any]], ...],
) -> _ParallelBranchList:
    """Build a fixed-cardinality native panel using :func:`parallel`.

    Each *reviewer* is a ``(reviewer_id, @phase_callable)`` pair.
    The built-in reducer collates per-reviewer outputs into
    ``{reviewer_id}.{label}`` keys so that downstream stages can
    resolve ``<panel>.*`` references in reviewer-list order.

    Parameters
    ----------
    name:
        Human-readable name for the parallel block (forwarded to
        :func:`parallel`).
    reviewers:
        Tuple of ``(reviewer_id: str, phase_callable)`` pairs.  Reviewer
        ids must be non-empty strings and the callables must be
        ``@phase``-decorated.

    Returns
    -------
    _ParallelBranchList
        A list-like object suitable for ``for branch in ...`` inside a
        ``@pipeline``-decorated function.  The attached reducer prefixes
        every key in each reviewer's output dict with ``reviewer_id.``
        before merging into pipeline state.

    Raises
    ------
    ValueError
        If *reviewers* is empty or contains duplicate reviewer ids.
    TypeError
        If any element of *reviewers* is not a ``(str, callable)`` pair.

    Notes
    -----
    This helper is semantically equivalent to a fixed-cardinality parallel
    panel with ``merge="none"``.  There is no second panel engine — the
    implementation is a thin wrapper around :func:`parallel` with a
    collation reducer.
    """
    if not reviewers:
        raise ValueError("native_panel() requires at least one reviewer")

    reviewer_ids: list[str] = []
    branches: list[Callable[..., Any]] = []
    seen_ids: set[str] = set()

    for i, pair in enumerate(reviewers):
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise TypeError(
                f"native_panel() reviewer {i} must be a (str, callable) pair, "
                f"got {type(pair).__name__}"
            )
        rid, func = pair
        if not isinstance(rid, str) or not rid:
            raise TypeError(
                f"native_panel() reviewer {i} id must be a non-empty str, "
                f"got {rid!r}"
            )
        if rid in seen_ids:
            raise ValueError(
                f"native_panel() duplicate reviewer id: {rid!r}"
            )
        seen_ids.add(rid)
        reviewer_ids.append(rid)
        branches.append(func)

    # Build the collation reducer that prefixes outputs with reviewer_id.
    # The reducer receives a list of branch results in declaration order.
    def _panel_reducer(results: list[dict]) -> dict:
        outputs: dict[str, object] = {}
        for rid, result in zip(reviewer_ids, results):
            if isinstance(result, dict):
                for label, value in result.items():
                    outputs[f"{rid}.{label}"] = value
        return outputs

    return parallel(tuple(branches), reducer=_panel_reducer, name=name)

# ── Introspection helpers ───────────────────────────────────────────────


def is_phase(fn: Any) -> bool:
    """Return ``True`` if *fn* is a ``@phase``-decorated callable."""
    return bool(getattr(fn, "__phase__", False))


def get_phase_meta(fn: Any) -> dict[str, Any] | None:
    """Return phase metadata dict for *fn*, or ``None``.

    Includes ``id``, ``inputs``, and ``outputs`` keys (may be ``None``)
    in addition to the existing ``name``, ``description``, ``produces``,
    and ``consumes`` keys.

    When side-effect metadata is attached (M1), ``operation``, ``target``,
    ``idempotency_key``, and ``effect_class`` keys are also included.
    """
    if not is_phase(fn):
        return None
    return {
        "name": getattr(fn, "__phase_name__", fn.__name__),
        "description": getattr(fn, "__phase_description__", None),
        "produces": getattr(fn, "__phase_produces__", ()),
        "consumes": getattr(fn, "__phase_consumes__", ()),
        "id": getattr(fn, "__step_id__", None),
        "inputs": getattr(fn, "__step_inputs__", None),
        "outputs": getattr(fn, "__step_outputs__", None),
        # Side-effect metadata (M1)
        "operation": getattr(fn, "__phase_operation__", None),
        "target": getattr(fn, "__phase_target__", None),
        "idempotency_key": getattr(fn, "__phase_idempotency_key__", None),
        "effect_class": getattr(fn, "__phase_effect_class__", None),
    }


def is_pipeline(fn: Any) -> bool:
    """Return ``True`` if *fn* is a ``@pipeline``-decorated callable."""
    return bool(getattr(fn, "__pipeline__", False))


def get_pipeline_meta(fn: Any) -> dict[str, Any] | None:
    """Return pipeline metadata dict for *fn*, or ``None``.

    Includes ``id``, ``inputs``, and ``outputs`` keys (may be ``None``)
    in addition to the existing ``name``, ``description``, ``phases``,
    and ``decisions`` keys.
    """
    if not is_pipeline(fn):
        return None
    return {
        "name": getattr(fn, "__pipeline_name__", fn.__name__),
        "description": getattr(fn, "__pipeline_description__", None) or "",
        "phases": [],
        "decisions": [],
        "id": getattr(fn, "__workflow_id__", None),
        "inputs": getattr(fn, "__workflow_inputs__", None),
        "outputs": getattr(fn, "__workflow_outputs__", None),
    }


def is_decision(fn: Any) -> bool:
    """Return ``True`` if *fn* is a ``@decision``-decorated callable."""
    return bool(getattr(fn, "__decision__", False))


def get_decision_meta(fn: Any) -> dict[str, Any] | None:
    """Return decision metadata dict for *fn*, or ``None``.

    For ordinary decisions the human-gate keys are present at their
    defaults (``human_gate=False``, ``artifact_stage=""``, etc.).
    For human-gate decisions the keys carry the declared metadata.

    Also includes source-location metadata (``source_file``,
    ``first_lineno``) and a ``routing_body`` marker so the validator
    can produce line-specific diagnostics.
    """
    if not is_decision(fn):
        return None
    vocab = getattr(fn, "__decision_vocabulary__", frozenset())
    return {
        "name": getattr(fn, "__decision_name__", fn.__name__),
        "description": getattr(fn, "__decision_description__", None),
        "vocabulary": frozenset(vocab),
        # Human-gate metadata — always present, ordinary decisions get defaults
        "human_gate": bool(getattr(fn, "__decision_human_gate__", False)),
        "artifact_stage": str(getattr(fn, "__decision_artifact_stage__", "")),
        "choices": tuple(getattr(fn, "__decision_choices__", ())),
        "resume_input_schema": getattr(fn, "__decision_resume_input_schema__", None),
        "override_routes": getattr(fn, "__decision_override_routes__", None),
        # Source-location metadata for validator diagnostics
        "source_file": getattr(fn, "__decision_source_file__", None),
        "first_lineno": getattr(fn, "__decision_first_lineno__", None),
        "routing_body": bool(getattr(fn, "__decision_routing_body__", False)),
    }


# ── Step / workflow aliased introspection helpers ──────────────────────


def is_step(fn: Any) -> bool:
    """Return ``True`` if *fn* is a ``@step``- or ``@phase``-decorated callable."""
    return is_phase(fn)


def get_step_meta(fn: Any) -> dict[str, Any] | None:
    """Return step metadata dict (including ``id``, ``inputs``, ``outputs``).

    Identical to :func:`get_phase_meta`.
    """
    return get_phase_meta(fn)


def is_workflow(fn: Any) -> bool:
    """Return ``True`` if *fn* is a ``@workflow``- or ``@pipeline``-decorated callable."""
    return is_pipeline(fn)


def get_workflow_meta(fn: Any) -> dict[str, Any] | None:
    """Return workflow metadata dict (including ``id``, ``inputs``, ``outputs``).

    Identical to :func:`get_pipeline_meta`.
    """
    return get_pipeline_meta(fn)
