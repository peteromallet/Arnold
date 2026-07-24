"""Neutral batch carriers for Arnold runtime batch execution.

Provides frozen, policy-free dataclasses for batch units, unit results,
aggregated run results, runtime settings, outcome classification, and
hook Protocol types.  No Megaplan imports or vocabulary.

Settled design choices (SD1–SD4):
* ``deadline_epoch_s`` is the canonical numeric deadline; envelope
  ``deadline`` string is metadata only.
* ``cancellation_requested`` is the canonical bool stop signal; envelope
  ``cancellation`` string is opaque metadata.
* ``deadline_epoch_s < 0`` is a resolver validation error; an
  already-expired positive deadline is a neutral ``deadline_expired``
  runtime outcome.
* ``idle_timeout_s`` and ``heartbeat_interval_s`` are declared fields
  but unsupported mechanics in M3d.

Boundary discipline
-------------------
No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, Sequence

__all__ = [
    "BATCH_OUTCOME_KINDS",
    "BatchOutcomeKind",
    "BatchUnit",
    "BatchUnitResult",
    "BatchRunResult",
    "BatchRuntimeSettings",
    "RunUnitHook",
    "ParseResultHook",
    "ParseSideResultHook",
    "OnUnitErrorHook",
    "scatter_gather_threaded",
    "scatter_gather_processes",
]

# ---------------------------------------------------------------------------
# Outcome constants
# ---------------------------------------------------------------------------

BATCH_OUTCOME_KINDS: frozenset[str] = frozenset(
    {
        "completed",
        "wall_timeout",
        "deadline_expired",
        "cancelled",
        "idle_unsupported",
        "heartbeat_unsupported",
        "error",
    }
)
"""Prescribed ``kind`` literal set for :class:`BatchOutcomeKind`.

``"completed"``            — all units finished within constraints.
``"wall_timeout"``         — wall-clock timeout expired.
``"deadline_expired"``     — deadline_epoch_s has passed.
``"cancelled"``            — cancellation_requested was True.
``"idle_unsupported"``     — idle_timeout_s set but unsupported in M3d.
``"heartbeat_unsupported"``— heartbeat_interval_s set but unsupported in M3d.
``"error"``                — unexpected runtime error.
"""


class BatchOutcomeKind:
    """Namespace for batch outcome kind constants.

    Each attribute mirrors a member of :data:`BATCH_OUTCOME_KINDS`.
    Use attribute access (e.g. ``BatchOutcomeKind.COMPLETED``) for
    readability; the frozenset for membership tests.
    """

    COMPLETED: str = "completed"
    WALL_TIMEOUT: str = "wall_timeout"
    DEADLINE_EXPIRED: str = "deadline_expired"
    CANCELLED: str = "cancelled"
    IDLE_UNSUPPORTED: str = "idle_unsupported"
    HEARTBEAT_UNSUPPORTED: str = "heartbeat_unsupported"
    ERROR: str = "error"


# ---------------------------------------------------------------------------
# Batch carriers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BatchUnit:
    """One unit of work submitted to a batch runner.

    ``unit_id`` is an opaque caller-assigned identifier (e.g. index or
    hash).  ``payload`` is fully opaque to Arnold — no prompt, mode, or
    phase fields are interpreted.
    ``metadata`` carries optional caller-supplied annotations (also
    opaque).
    """

    unit_id: str
    payload: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BatchUnitResult:
    """Result of executing a single :class:`BatchUnit`.

    ``unit_id`` matches the originating unit so callers can correlate.
    ``result`` is the parsed result (if any).  ``side_result`` is the
    parsed side-task result (if any).  ``error`` is a string description
    when the unit failed (empty string on success).  ``cost_usd`` and
    ``tokens`` aggregate resource usage for this unit.
    """

    unit_id: str
    result: Any = None
    side_result: Any = None
    error: str = ""
    cost_usd: float = 0.0
    tokens: int = 0


@dataclass(frozen=True)
class BatchRunResult:
    """Aggregated result of a batch run.

    ``outcome_kind`` is a member of :data:`BATCH_OUTCOME_KINDS`.
    ``ordered_results`` preserves submission order (index 0 maps to the
    first submitted unit).  ``side_results`` is a flat list of parsed
    side-task results from all units.  ``total_cost_usd`` and
    ``total_tokens`` aggregate across all units (including side tasks).
    ``errors`` collects unit-level error strings whose outcome was not
    fatal to the batch.
    """

    outcome_kind: str
    ordered_results: tuple[BatchUnitResult, ...] = ()
    side_results: tuple[Any, ...] = ()
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class BatchRuntimeSettings:
    """Neutral runtime settings consumed by batch runners.

    All fields are pre-resolved scalars — the batch runner never calls
    ``get_effective()`` or imports Megaplan config.

    ``deadline_epoch_s`` is the canonical numeric deadline (float |
    None).  ``cancellation_requested`` is the canonical boolean stop
    signal.  ``idle_timeout_s`` and ``heartbeat_interval_s`` are
    declared but unsupported in M3d.
    """

    max_workers: int = 1
    wall_timeout_s: float | None = None
    deadline_epoch_s: float | None = None
    cancellation_requested: bool = False
    idle_timeout_s: float | None = None
    heartbeat_interval_s: float | None = None
    poll_cadence_s: float | None = None
    cost_cap_usd: float | None = None


# ---------------------------------------------------------------------------
# Hook Protocol types
# ---------------------------------------------------------------------------


class RunUnitHook(Protocol):
    """Callable that executes a single :class:`BatchUnit`.

    Receives the unit and runtime settings; returns a raw result (opaque
    to Arnold) or raises.
    """

    def __call__(
        self, unit: BatchUnit, settings: BatchRuntimeSettings
    ) -> Any:  # pragma: no cover
        ...


class ParseResultHook(Protocol):
    """Callable that parses a raw unit result into a caller-owned value.

    The raw result comes from :class:`RunUnitHook`; the parsed value is
    stored in :attr:`BatchUnitResult.result`.
    """

    def __call__(
        self, raw_result: Any, unit: BatchUnit, settings: BatchRuntimeSettings
    ) -> Any:  # pragma: no cover
        ...


class ParseSideResultHook(Protocol):
    """Callable that parses a raw side-task result into a caller-owned value.

    Used when a unit produces both a primary and a side result (e.g. a
    check alongside a generation).  The parsed value is stored in
    :attr:`BatchUnitResult.side_result`.
    """

    def __call__(
        self, raw_side: Any, unit: BatchUnit, settings: BatchRuntimeSettings
    ) -> Any:  # pragma: no cover
        ...


class OnUnitErrorHook(Protocol):
    """Callable invoked when a unit fails.

    Receives the unit, the exception, and settings.  Must be tolerant —
    exceptions must not propagate past the batch runner.  Returns a
    :class:`BatchUnitResult` (typically with ``error`` set).
    """

    def __call__(
        self,
        unit: BatchUnit,
        exception: BaseException,
        settings: BatchRuntimeSettings,
    ) -> BatchUnitResult:  # pragma: no cover
        ...


# ---------------------------------------------------------------------------
# Neutral thread-pool scatter / gather
# ---------------------------------------------------------------------------


def scatter_gather_threaded(
    units: Sequence[BatchUnit],
    settings: BatchRuntimeSettings,
    *,
    run_unit: RunUnitHook,
    parse_result: ParseResultHook | None = None,
    on_unit_error: OnUnitErrorHook | None = None,
    max_workers: int = 1,
) -> BatchRunResult:
    """Execute *units* concurrently via :class:`~concurrent.futures.ThreadPoolExecutor`.

    This is the neutral Arnold batch runner for thread-pool execution.
    It consumes pre-resolved :class:`BatchRuntimeSettings` (no
    ``get_effective()`` call) and delegates all unit-level semantics to
    the supplied hook callables.

    Parameters
    ----------
    units:
        Ordered sequence of :class:`BatchUnit` items to execute.
    settings:
        Pre-resolved runtime settings consumed by every hook.
    run_unit:
        Callable that executes a single unit → raw result (or raises).
    parse_result:
        Optional callable that transforms a raw result into the value
        stored in ``BatchUnitResult.result``.  When ``None``, the raw
        result is stored as-is.
    on_unit_error:
        Optional callable invoked when *run_unit* raises.  Must return a
        :class:`BatchUnitResult` and must not raise.  When ``None``, a
        built-in fault-tolerant default is used that captures the
        exception string as ``error``.
    max_workers:
        Pre-resolved worker count for the thread pool.  Must be ≥ 1.

    Returns
    -------
    BatchRunResult
        Aggregated result with ``ordered_results`` in submission order,
        aggregated ``total_cost_usd`` and ``total_tokens``, and a flat
        ``errors`` tuple of non-empty unit error strings.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Default handlers that never raise.
    _parse: ParseResultHook = parse_result or (lambda raw, unit, s: raw)

    def _default_on_error(
        unit: BatchUnit, exc: BaseException, _settings: BatchRuntimeSettings,
    ) -> BatchUnitResult:
        return BatchUnitResult(
            unit_id=unit.unit_id,
            error=str(exc),
        )

    _on_error: OnUnitErrorHook = on_unit_error or _default_on_error

    # Collect results in submission order.
    n = len(units)
    indexed: dict[int, BatchUnitResult] = {}

    workers = max(1, max_workers)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_index: dict = {}
        for idx, unit in enumerate(units):
            future = pool.submit(_execute_one_unit, unit, settings, run_unit, _parse, _on_error)
            future_to_index[future] = idx

        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                indexed[idx] = future.result()
            except Exception:
                # future.result() should never raise because on_unit_error
                # catches all exceptions, but be defensive.
                indexed[idx] = BatchUnitResult(
                    unit_id=units[idx].unit_id,
                    error="unhandled future exception",
                )

    ordered: list[BatchUnitResult] = [indexed[i] for i in range(n)]

    total_cost = sum(r.cost_usd for r in ordered)
    total_tokens = sum(r.tokens for r in ordered)
    errors = tuple(r.error for r in ordered if r.error)

    # Determine outcome kind from settings
    outcome_kind = BatchOutcomeKind.COMPLETED
    if settings.cancellation_requested:
        outcome_kind = BatchOutcomeKind.CANCELLED
    elif settings.deadline_epoch_s is not None:
        import time
        if time.time() > settings.deadline_epoch_s:
            outcome_kind = BatchOutcomeKind.DEADLINE_EXPIRED

    return BatchRunResult(
        outcome_kind=outcome_kind,
        ordered_results=tuple(ordered),
        side_results=(),
        total_cost_usd=total_cost,
        total_tokens=total_tokens,
        errors=errors,
    )


def _execute_one_unit(
    unit: BatchUnit,
    settings: BatchRuntimeSettings,
    run_unit: RunUnitHook,
    parse_result: ParseResultHook,
    on_unit_error: OnUnitErrorHook,
) -> BatchUnitResult:
    """Execute one unit with error tolerance, returning a BatchUnitResult."""
    try:
        raw = run_unit(unit, settings)
        parsed = parse_result(raw, unit, settings)
        return BatchUnitResult(
            unit_id=unit.unit_id,
            result=parsed,
        )
    except BaseException as exc:
        return on_unit_error(unit, exc, settings)


# ---------------------------------------------------------------------------
# Neutral process-pool scatter / gather
# ---------------------------------------------------------------------------


def scatter_gather_processes(
    units: Sequence[BatchUnit],
    settings: BatchRuntimeSettings,
    *,
    run_unit: RunUnitHook,
    parse_result: ParseResultHook | None = None,
    on_unit_error: OnUnitErrorHook | None = None,
    max_workers: int = 1,
    wall_timeout_s: float | None = None,
    hard_kill_grace_seconds: float = 5.0,
) -> BatchRunResult:
    """Execute *units* in isolated child processes via :func:`multiprocessing.Process`.

    This is the neutral Arnold batch runner for process-isolated execution.
    It consumes pre-resolved :class:`BatchRuntimeSettings` (no
    ``get_effective()`` call) and delegates all unit-level semantics to the
    supplied hook callables.

    Pre-launch checks
    -----------------
    * If ``settings.cancellation_requested`` is ``True``, returns
      ``cancelled`` immediately without spawning any child.
    * If ``settings.deadline_epoch_s`` is set and already expired, returns
      ``deadline_expired`` immediately without spawning any child.
    * If ``settings.idle_timeout_s`` or ``settings.heartbeat_interval_s``
      are not ``None``, the outcome is annotated but the mechanics are
      **not enforced** (unsupported in M3d).

    Wall-timeout supervision
    ------------------------
    When *wall_timeout_s* is set, each child gets its own deadline.  A
    child exceeding the deadline is sent ``SIGTERM``; if still alive after
    *hard_kill_grace_seconds* it receives ``SIGKILL``.  The timed-out unit
    produces a sentinel result via *on_unit_error* and siblings continue
    unaffected.

    Parameters
    ----------
    units:
        Ordered sequence of :class:`BatchUnit` items to execute.
    settings:
        Pre-resolved runtime settings consumed by every hook and checked
        for cancellation / deadline expiry before launch.
    run_unit:
        Callable that executes a single unit → raw result (or raises).
        **Must be picklable** — defined at module top-level.
    parse_result:
        Optional callable that transforms a raw result into the value
        stored in ``BatchUnitResult.result``.  When ``None``, the raw
        result is stored as-is.  Runs in the *parent* process.
    on_unit_error:
        Optional callable invoked when *run_unit* raises or a child times
        out.  Must return a :class:`BatchUnitResult` and must not raise.
        When ``None``, a built-in fault-tolerant default is used.
    max_workers:
        Pre-resolved worker count (max concurrent children).  Must be ≥ 1.
    wall_timeout_s:
        Per-child wall-clock timeout in seconds.  ``None`` means no limit.
    hard_kill_grace_seconds:
        Seconds to wait after ``SIGTERM`` before sending ``SIGKILL``.

    Returns
    -------
    BatchRunResult
        Aggregated result with ``ordered_results`` in submission order,
        aggregated ``total_cost_usd`` and ``total_tokens``, and a flat
        ``errors`` tuple.
    """
    import multiprocessing as mp
    import queue
    import time as _time

    # ------------------------------------------------------------------
    # Pre-flight: idle / heartbeat unsupported annotation
    # ------------------------------------------------------------------
    if settings.idle_timeout_s is not None:
        return BatchRunResult(
            outcome_kind=BatchOutcomeKind.IDLE_UNSUPPORTED,
            errors=("idle_timeout_s is set but unsupported in M3d",),
        )
    if settings.heartbeat_interval_s is not None:
        return BatchRunResult(
            outcome_kind=BatchOutcomeKind.HEARTBEAT_UNSUPPORTED,
            errors=("heartbeat_interval_s is set but unsupported in M3d",),
        )

    # ------------------------------------------------------------------
    # Pre-flight: cancellation
    # ------------------------------------------------------------------
    if settings.cancellation_requested:
        return BatchRunResult(
            outcome_kind=BatchOutcomeKind.CANCELLED,
            errors=("cancellation requested before launch",),
        )

    # ------------------------------------------------------------------
    # Pre-flight: deadline expired
    # ------------------------------------------------------------------
    if settings.deadline_epoch_s is not None and _time.time() > settings.deadline_epoch_s:
        return BatchRunResult(
            outcome_kind=BatchOutcomeKind.DEADLINE_EXPIRED,
            errors=("deadline already expired before launch",),
        )

    # ------------------------------------------------------------------
    # Empty input
    # ------------------------------------------------------------------
    if not units:
        return BatchRunResult(
            outcome_kind=BatchOutcomeKind.COMPLETED,
            ordered_results=(),
        )

    # ------------------------------------------------------------------
    # Default handlers
    # ------------------------------------------------------------------
    _parse: ParseResultHook = parse_result or (lambda raw, unit, s: raw)

    def _default_on_error(
        unit: BatchUnit, exc: BaseException, _settings: BatchRuntimeSettings,
    ) -> BatchUnitResult:
        return BatchUnitResult(
            unit_id=unit.unit_id,
            error=str(exc),
        )

    _on_error: OnUnitErrorHook = on_unit_error or _default_on_error

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    n = len(units)
    workers = max(1, max_workers)
    concurrency = min(workers, n)

    if wall_timeout_s is not None and wall_timeout_s <= 0:
        raise ValueError("wall_timeout_s must be positive")
    if hard_kill_grace_seconds < 0:
        raise ValueError("hard_kill_grace_seconds must be non-negative")

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    results: list[BatchUnitResult | None] = [None] * n
    ctx = mp.get_context("spawn")
    pending = list(enumerate(units))
    active: dict[int, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Helpers (defined in parent — picklable via top-level _run_child)
    # ------------------------------------------------------------------

    def _launch_next() -> None:
        if not pending:
            return
        index, unit = pending.pop(0)
        out_queue: Any = ctx.Queue()
        proc = ctx.Process(
            target=_run_process_child,
            args=(run_unit, index, unit, settings, out_queue),
        )
        proc.start()
        active[index] = {
            "process": proc,
            "queue": out_queue,
            "started_at": _time.monotonic(),
            "terminating_since": None,
        }

    def _record(idx: int, ur: BatchUnitResult) -> None:
        results[idx] = ur

    def _sentinel(idx: int, exc: BaseException) -> None:
        ur = _on_error(units[idx], exc, settings)
        _record(idx, ur)

    def _cleanup_active() -> None:
        for item in active.values():
            p = item["process"]
            if p.is_alive():
                p.terminate()
        for item in active.values():
            p = item["process"]
            p.join(hard_kill_grace_seconds)
            if p.is_alive():
                p.kill()
                p.join()

    # ------------------------------------------------------------------
    # Launch initial batch
    # ------------------------------------------------------------------
    for _ in range(concurrency):
        _launch_next()

    # ------------------------------------------------------------------
    # Supervision loop
    # ------------------------------------------------------------------
    try:
        while active:
            now = _time.monotonic()
            completed: list[int] = []

            for idx, item in list(active.items()):
                proc = item["process"]
                out_q = item["queue"]

                # Check for result from child
                try:
                    message = out_q.get_nowait()
                except queue.Empty:
                    message = None

                if message is not None:
                    proc.join()
                    if message.get("ok"):
                        raw_result = message["result"]
                        try:
                            parsed = _parse(raw_result, units[idx], settings)
                            _record(idx, BatchUnitResult(
                                unit_id=units[idx].unit_id,
                                result=parsed,
                            ))
                        except BaseException as exc:
                            _sentinel(idx, exc)
                    else:
                        exc_msg = str(message.get("error", "child process failed"))
                        _sentinel(idx, RuntimeError(exc_msg))
                    completed.append(idx)
                    continue

                # Wall-timeout check
                if (
                    wall_timeout_s is not None
                    and item["terminating_since"] is None
                    and now - item["started_at"] >= wall_timeout_s
                ):
                    item["terminating_since"] = now
                    if proc.is_alive():
                        proc.terminate()

                terminating_since = item["terminating_since"]
                if terminating_since is not None:
                    if proc.is_alive() and now - terminating_since >= hard_kill_grace_seconds:
                        proc.kill()
                    proc.join(0)
                    if not proc.is_alive():
                        _sentinel(
                            idx,
                            TimeoutError(
                                f"process unit {idx} timed out after {wall_timeout_s:.3f}s"
                            ),
                        )
                        completed.append(idx)
                    continue

                # Process exited without result
                if not proc.is_alive():
                    proc.join()
                    _sentinel(
                        idx,
                        RuntimeError(f"process unit {idx} exited without a result"),
                    )
                    completed.append(idx)

            for idx in completed:
                active.pop(idx, None)
                _launch_next()

            if active:
                _time.sleep(0.01)

    except Exception:
        _cleanup_active()
        raise

    # ------------------------------------------------------------------
    # Assemble result
    # ------------------------------------------------------------------
    ordered: list[BatchUnitResult] = []
    errors: list[str] = []
    for i in range(n):
        ur = results[i]
        if ur is None:
            ur = BatchUnitResult(
                unit_id=units[i].unit_id,
                error="process fan-out did not return a result",
            )
        ordered.append(ur)
        if ur.error:
            errors.append(ur.error)

    total_cost = sum(r.cost_usd for r in ordered)
    total_tokens = sum(r.tokens for r in ordered)

    # Determine outcome kind
    outcome_kind = BatchOutcomeKind.COMPLETED
    if errors and all(r.error for r in ordered):
        outcome_kind = BatchOutcomeKind.ERROR

    return BatchRunResult(
        outcome_kind=outcome_kind,
        ordered_results=tuple(ordered),
        side_results=(),
        total_cost_usd=total_cost,
        total_tokens=total_tokens,
        errors=tuple(errors),
    )


def _run_process_child(
    run_unit: RunUnitHook,
    index: int,
    unit: BatchUnit,
    settings: BatchRuntimeSettings,
    out_queue: Any,
) -> None:
    """Top-level target for child processes — must be picklable."""
    try:
        raw = run_unit(unit, settings)
        out_queue.put({
            "ok": True,
            "result": raw,
        })
    except BaseException as exc:
        out_queue.put({
            "ok": False,
            "error": str(exc) or exc.__class__.__name__,
        })
