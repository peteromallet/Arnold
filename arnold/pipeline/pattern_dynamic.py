"""Neutral fanout metadata and core runner for dynamic pipeline fan-out.

Provides data carriers and a core execution function that:

1. Runs a generator step to produce fan-out specs.
2. Specialises a base step per spec via ``dataclasses.replace``.
3. Runs per-spec steps (sequentially or via ``ThreadPoolExecutor``).
4. Preserves result order.
5. Invokes a join function on the ordered results.
6. Emits the typed output port ``last_fanout_results``.

All types are neutral dataclasses with zero megaplan imports.
"""

from __future__ import annotations

import dataclasses
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence, cast

from arnold.pipeline.types import Port

# ── Typed Port emitted by the fan-out join ──────────────────────────────────

LAST_FANOUT_RESULTS_PORT: Port = Port(
    name="last_fanout_results",
    content_type="application/x-fanout-results+json",
)

# ── Fanout data carriers ───────────────────────────────────────────────────


@dataclass(frozen=True)
class FanoutSpecSchema:
    """Declares the shape of a single fan-out specification.

    ``keys`` names the top-level keys that a spec dictionary must contain.
    ``required`` is the subset of keys that must be non-None.
    """

    keys: tuple[str, ...] = ()
    required: tuple[str, ...] = ()


@dataclass(frozen=True)
class FanoutSpecialization:
    """Describes how a base step is specialised per spec.

    ``spec_keys`` names the spec-dictionary keys that are eligible for
    ``dataclasses.replace`` on the base step.  When empty, every key in
    the spec that matches a dataclass field is used.
    """

    spec_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class FanoutConcurrency:
    """Controls concurrent execution of fan-out steps.

    ``mode`` is ``"sequential"`` (default) or ``"thread"``.
    ``max_workers`` caps the ``ThreadPoolExecutor`` size (``None`` means
    unbounded).  Ignored when ``mode != "thread"``.
    """

    mode: str = "sequential"
    max_workers: int | None = None


@dataclass(frozen=True)
class FanoutGovernorLimits:
    """Data carrier for budget/envelope limits on fan-out width.

    Purely a data holder — the caller (Megaplan shim, executor, etc.)
    reads these values and enforces policy.  Arnold never enforces
    governor policy on its own.
    """

    max_fanout_width: int | None = None
    max_total_steps: int | None = None
    max_sequential_steps: int | None = None


@dataclass(frozen=True)
class FanoutJoinContract:
    """Describes the join function signature and expectations.

    ``arity`` is the expected number of inputs ("many" means variable).
    ``result_kind`` describes the join output shape
    (e.g. "reduce", "select", "merge").
    """

    arity: str = "many"
    result_kind: str = "reduce"


@dataclass(frozen=True)
class FanoutMetadata:
    """Complete metadata bundle for a dynamic fan-out invocation.

    Carries schema, specialisation, concurrency, governor limits, and
    join contract.  All fields are optional so callers can supply only
    what they need.
    """

    schema: FanoutSpecSchema = field(default_factory=FanoutSpecSchema)
    specialization: FanoutSpecialization = field(default_factory=FanoutSpecialization)
    concurrency: FanoutConcurrency = field(default_factory=FanoutConcurrency)
    governor_limits: FanoutGovernorLimits = field(
        default_factory=FanoutGovernorLimits
    )
    join_contract: FanoutJoinContract = field(default_factory=FanoutJoinContract)


# ── Internal helpers ───────────────────────────────────────────────────────


def _specialize_step(base: Any, spec: Any) -> Any:
    """Return a per-spec specialised copy of *base* via ``dataclasses.replace``.

    Duck-types the base: if it is a dataclass instance, replaces fields
    whose names appear in *spec*.  Otherwise returns *base* unchanged.
    """
    if not isinstance(spec, Mapping):
        return base
    if dataclasses.is_dataclass(base) and not isinstance(base, type):
        valid = {f.name for f in dataclasses.fields(base)}
        kwargs = {key: value for key, value in spec.items() if key in valid}
        if kwargs:
            try:
                return dataclasses.replace(base, **kwargs)
            except TypeError:
                return base
    return base


def _extract_specs_from_result(
    result: Any,
    *,
    typed_ports: bool = True,
) -> list[Any]:
    """Pull a list of fan-out specs from a generator's result.

    *result* is duck-typed as having ``state_patch`` and ``outputs``
    attributes (like ``StepResult``).

    When ``typed_ports`` is ``True`` (default), reads the typed Port
    channel ``last_fanout_results``.  When ``False``, falls back to
    the untyped ``specs`` channel.
    """
    state_patch = getattr(result, "state_patch", {}) or {}
    outputs = getattr(result, "outputs", {}) or {}

    if typed_ports:
        port_name = LAST_FANOUT_RESULTS_PORT.name
        if isinstance(state_patch, Mapping):
            value = state_patch.get(port_name)
            if isinstance(value, list):
                return list(value)
        if isinstance(outputs, Mapping):
            out_path = outputs.get(port_name)
            if out_path is not None:
                return _read_specs_from_path(Path(out_path))
        raise LookupError(
            f"dynamic_fanout: generator emitted no typed Port "
            f"{port_name!r} (neither in state_patch nor outputs)"
        )

    # untyped fallback
    if isinstance(state_patch, Mapping):
        value = state_patch.get("specs")
        if isinstance(value, list):
            return list(value)
    if isinstance(outputs, Mapping):
        out_path = outputs.get("specs")
        if out_path is not None:
            return _read_specs_from_path(Path(out_path))
    raise LookupError(
        "dynamic_fanout: generator emitted no 'specs' (neither in "
        "state_patch nor outputs)"
    )


def _read_specs_from_path(path: Path) -> list[Any]:
    """Read a JSON list of specs from *path*."""
    loaded = json.loads(Path(path).read_text())
    if not isinstance(loaded, list):
        raise ValueError(
            f"spec artifact {str(path)!r} must be a JSON list, "
            f"got {type(loaded).__name__}"
        )
    return loaded


# ── Core fanout runner ─────────────────────────────────────────────────────


def run_fanout(
    generator: Any,
    base_step: Any,
    join_fn: Callable[[list[Any], Any], Any],
    ctx: Any,
    *,
    metadata: FanoutMetadata | None = None,
    typed_ports: bool = True,
) -> Any:
    """Neutral dynamic fan-out core.

    1. Runs *generator* with *ctx* to produce a result.
    2. Extracts fan-out specs from the generator result.
    3. Specialises *base_step* per spec via ``dataclasses.replace``.
    4. Runs per-spec steps (sequentially or via ``ThreadPoolExecutor``).
    5. Invokes *join_fn*(ordered_results, ctx).
    6. When ``typed_ports=True``, emits ``LAST_FANOUT_RESULTS_PORT``
       on the joined result's ``state_patch``.

    Parameters
    ----------
    generator:
        A step-like object with a ``run(ctx)`` method that returns a
        result carrying specs.
    base_step:
        A step-like dataclass instance that will be specialised per spec.
    join_fn:
        ``Callable[[list[StepResult], StepContext], StepResult]`` —
        invoked with the ordered list of per-spec results and the context.
    ctx:
        The ``StepContext`` to pass to every step invocation.
    metadata:
        Optional :class:`FanoutMetadata` bundle; concurrency settings
        are read from ``metadata.concurrency``.
    typed_ports:
        When ``True`` (default), specs are read from the typed port
        channel and the joined result emits ``LAST_FANOUT_RESULTS_PORT``.
        When ``False``, the untyped ``specs`` channel is used instead.

    Returns
    -------
    The result of ``join_fn(results, ctx)``, with ``last_fanout_results``
    stitched into ``state_patch`` when ``typed_ports=True``.

    Raises
    ------
    LookupError:
        When the generator result contains no extractable specs.
    """
    if metadata is None:
        metadata = FanoutMetadata()

    # 1. Run generator
    gen_result = generator.run(ctx)

    # 2. Extract specs
    specs = _extract_specs_from_result(gen_result, typed_ports=typed_ports)

    # 3. Specialise base step per spec
    steps = [_specialize_step(base_step, spec) for spec in specs]

    # 4. Run per-spec steps
    concurrency = metadata.concurrency
    if concurrency.mode == "thread" and len(steps) > 1:
        results = _run_concurrent(steps, ctx, concurrency.max_workers)
    else:
        results = [step.run(ctx) for step in steps]

    # 5. Invoke join
    joined = join_fn(results, ctx)

    # 6. Emit typed output port
    if typed_ports:
        patch = (
            dict(joined.state_patch)
            if isinstance(getattr(joined, "state_patch", None), Mapping)
            else {}
        )
        patch[LAST_FANOUT_RESULTS_PORT.name] = list(results)
        patch.pop("specs", None)
        joined = dataclasses.replace(joined, state_patch=patch)

    return joined


def _run_concurrent(
    steps: list[Any],
    ctx: Any,
    max_workers: int | None,
) -> list[Any]:
    """Run *steps* concurrently via ``ThreadPoolExecutor``, preserving order.

    Each step receives a *copy* of *ctx* to avoid shared mutable state
    across threads.
    """
    indexed: dict[int, Any] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_step_run_copy, step, ctx, idx): idx
            for idx, step in enumerate(steps)
        }
        for future in as_completed(futures):
            idx = futures[future]
            indexed[idx] = future.result()

    return [indexed[i] for i in range(len(steps))]


def _step_run_copy(step: Any, ctx: Any, idx: int) -> Any:
    """Run *step* with a dataclass-replaced copy of *ctx*.

    The copy ensures thread isolation for mutable fields like ``state``.
    If *ctx* is a dataclass, ``dataclasses.replace(ctx)`` is used.
    Otherwise the original *ctx* is passed (caller is responsible for
    thread safety).
    """
    if dataclasses.is_dataclass(ctx) and not isinstance(ctx, type):
        ctx_copy = dataclasses.replace(ctx)
    else:
        ctx_copy = ctx
    return step.run(ctx_copy)
