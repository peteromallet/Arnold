"""Standalone Sprint-1 pipeline executor for the ``megaplan/_pipeline`` package.

``run_pipeline`` walks a :class:`Pipeline`'s stages, dispatches each
:class:`Step`, verifies declared outputs, applies state patches, and
follows labelled edges until a terminal sentinel is hit. The executor is
deliberately self-contained — no imports from ``megaplan._core``,
``megaplan.types``, ``megaplan.phase_result``, or ``megaplan._core.io`` —
so the new package can be exercised under bare ``pytest`` without
triggering the live-megaplan import graph.

Contract notes:

(a) ``'halt'`` is reserved both as a :class:`NextEdge` label returned by
    a Step (``result.next == 'halt'``) and as an :class:`Edge` target
    (``edge.target == 'halt'``). Either form terminates the loop. Step
    authors MUST NOT use ``'halt'`` for non-terminal transitions.

(b) ``'subloop'`` and ``'override'`` are reserved ``Step.kind`` literals
    declared in :mod:`megaplan._pipeline.types`. The Sprint-1 executor
    deliberately has **no branch** for either kind — they exist purely
    for forward compatibility and any Step declared with one of these
    kinds is dispatched identically to a ``produce``/``judge``/``decide``
    step.

(c) Verify-only artifact contract: after each Step (or
    :class:`ParallelStage` ``join``) returns, the executor iterates
    ``result.outputs`` and raises ``FileNotFoundError`` if any declared
    path is absent. The error message includes the stage name, output
    label, and path. The executor never copies, moves, or rewrites
    artifacts — Step authors own placement.

(d) Immutability convention: :class:`StepResult`, :class:`PipelineVerdict`, and
    :class:`StepContext` are conceptually immutable. State is applied
    via ``state.update(dict(result.state_patch))`` — a defensive copy so
    a Step returning a shared default dict cannot alias the executor's
    working state.

(e) Step authors may nest declared outputs at any depth under the
    stage's artifact directory (or anywhere else under ``ctx.plan_dir``).
    The executor verifies existence only, not directory layout.

(f) PipelineVerdict-first edge dispatch on ``kind="gate"`` edges: when a Step
    returns a :class:`StepResult` whose ``verdict.recommendation`` is
    set, the executor first searches ``node.edges`` for the edge whose
    ``kind == "gate"`` and ``recommendation == verdict.recommendation``.
    On miss (or when no recommendation is set), it falls back to the
    legacy ``kind == "normal"`` + ``label == result.next`` match. If
    neither path finds an edge, the executor raises ``LookupError``
    naming both the ``result.next`` label and the ``verdict.recommendation``
    so debugging starts from both fields. ``kind == "override"`` edges
    are reserved for Chunk D and are NOT consumed by the Chunk-A
    dispatcher — any such edges sit inert in ``node.edges`` until that
    branch lands. The ``result.next == "halt"`` short-circuit above the
    dispatch block is preserved unchanged.
"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import json
import os
from pathlib import Path
from typing import Any, Mapping

from megaplan._core.state import write_plan_state
from megaplan.types import CliError
from megaplan._pipeline.types import (
    ParallelStage,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)


def _atomic_write_json(dest: Path, payload: Any) -> None:
    """Write ``payload`` to ``dest`` atomically via a sibling ``.tmp`` file.

    Uses stdlib ``json`` + ``os.replace`` only — no dependency on
    ``megaplan._core.io``.
    """

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))
    os.replace(tmp, dest)


def _write_forensic_backup(source: Path) -> Path:
    """Copy ``source`` to a sibling forensic backup via atomic replace."""

    backup_path = source.with_name(f"{source.name}.corrupt-executor-backup")
    tmp = backup_path.with_suffix(backup_path.suffix + ".tmp")
    tmp.write_bytes(source.read_bytes())
    os.replace(tmp, backup_path)
    return backup_path


def _merge_state_to_disk(
    plan_dir: Path,
    executor_state: dict[str, Any],
    *,
    executor_owned_keys: set[str] | None = None,
) -> None:
    """Merge the executor's tracked state with on-disk handler-written keys.

    Two scenarios coexist:
    - Hermetic Steps (demos): only the executor writes state.json.
      The executor's tracked state is authoritative for every key.
    - Handler-backed Steps: the in-process handler writes its own
      state.json with plan_versions, history, meta, etc. The
      executor's tracked state is stale for those keys.

    Resolution: ``executor_owned_keys`` lists the keys the executor
    has explicitly mutated via state_patch since the run began. For
    those keys the executor's value wins; for all other on-disk keys
    the on-disk value wins. When no executor keys are tracked yet
    (or no on-disk state exists), the executor's full state is
    written as the cold-start.
    """
    try:
        write_plan_state(
            plan_dir,
            mode="executor-key-merge",
            state=executor_state,
            executor_owned_keys=executor_owned_keys,
        )
    except CliError as exc:
        state_path = plan_dir / "state.json"
        if exc.code == "corrupt_state_write" and state_path.exists():
            backup_path = _write_forensic_backup(state_path)
            exc.extra.setdefault("forensic_backup_path", str(backup_path))
        raise


def _verify_outputs(stage_name: str, outputs: Mapping[str, Path]) -> None:
    for label, path in outputs.items():
        if not Path(path).exists():
            raise FileNotFoundError(
                f"Stage {stage_name!r} declared output {label!r}={path} "
                f"but the file does not exist"
            )


def _record_error(artifact_root: Path, stage_name: str, exc: BaseException) -> None:
    stage_dir = artifact_root / stage_name
    stage_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(
        stage_dir / "error.json",
        {"stage": stage_name, "error": repr(exc)},
    )


def _is_safe_for_parallel(parallel_stage: ParallelStage) -> bool:
    """Return False if any step is an InProcessHandlerStep (unsafe for threads).

    InProcessHandlerStep reads and writes shared state.json on disk via
    handler functions — concurrent handler invocations would race through
    the same plan directory. PanelReviewerStep and other hermetic steps
    are safe: they call worker functions that write to per-reviewer output
    directories and do not touch shared state.
    """
    from megaplan._pipeline.stages.inprocess_step import InProcessHandlerStep

    return not any(
        isinstance(step, InProcessHandlerStep) for step in parallel_stage.steps
    )


def _run_parallel_stage(node: ParallelStage, ctx: StepContext) -> StepResult:
    """Run a ParallelStage with thread-safe context isolation.

    * Rejects the stage if any step is an :class:`InProcessHandlerStep`
      (not thread-safe — reads/writes shared state.json).
    * Each worker thread receives a shallow copy of *ctx* via
      ``dataclasses.replace(ctx, state=dict(state))`` so that per-step
      state mutations do not race through the shared Mapping.
    * Results are collected in declaration order (not completion order)
      and joined via ``node.join(results, ctx)``.
    """
    from megaplan._pipeline.stages.inprocess_step import InProcessHandlerStep

    # Guard: reject InProcessHandlerStep before any handler executes.
    for step in node.steps:
        if isinstance(step, InProcessHandlerStep):
            raise ValueError(
                f"ParallelStage {node.name!r} contains InProcessHandlerStep "
                f"{step.name!r}. InProcessHandlerStep is not thread-safe — "
                f"it reads and writes shared state.json on disk. "
                f"Use a sequential Stage instead."
            )

    workers = max(1, node.max_workers or len(node.steps))
    results: list[StepResult] = [None] * len(node.steps)  # type: ignore[list-item]

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_idx: dict[concurrent.futures.Future[StepResult], int] = {}
        for idx, step in enumerate(node.steps):
            # Per-thread shallow copy: dict(state) prevents workers
            # from racing through the shared ctx.state Mapping.
            thread_ctx = dataclasses.replace(ctx, state=dict(ctx.state))
            future_to_idx[pool.submit(step.run, thread_ctx)] = idx

        for fut in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[fut]
            results[idx] = fut.result()

    return node.join(results, ctx)


def run_pipeline(
    pipeline: Pipeline,
    ctx: StepContext,
    *,
    artifact_root: Path,
    policy: Any | None = None,
) -> dict[str, Any]:
    """Walk ``pipeline`` from its entry stage until a terminal sentinel.

    Returns ``{'state': <final state dict>, 'final_stage': <stage name>}``
    on normal termination. Raises on Step failure, missing declared
    output, or unmatched edge label.

    When ``policy`` is None (production default), behavior is identical to the
    pre-merge bare path. When a :class:`RuntimePolicy` is supplied (previously
    only reachable via :func:`run_pipeline_with_policy`), per-iteration policy
    guards engage: ``max_iterations`` cap, stall observation, cost-cap abort,
    and escalate-policy fallback. ``find_override_edge`` dispatch runs
    unconditionally for both paths — the policy path inherits the override
    edge ladder from the bare path so verdict.override is honored consistently.
    """

    artifact_root = Path(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)

    if isinstance(ctx.state, Mapping):
        state: dict[str, Any] = dict(ctx.state)
    else:
        state = {}

    executor_owned_keys: set[str] = set()
    cursor = pipeline.entry
    iterations = 0
    loop_iters: dict[str, int] = {}
    while True:
        if policy is not None and iterations >= policy.max_iterations:
            return {"state": state, "final_stage": cursor, "halt_reason": "max_iterations"}
        iterations += 1
        node = pipeline.stages[cursor]

        # Refresh ctx.state with the executor's working state so each
        # iteration of a loop sees the latest state_patches. ctx is
        # frozen; build a new instance via dataclasses.replace.
        ctx = dataclasses.replace(ctx, state=state)

        # Flag-ON (M2 / T11b): runtime port-binding. Resolve each Stage's
        # consumes against Pipeline.binding_map and populate ctx.inputs
        # with concrete upstream artifact paths. On miss raise
        # PortBindError so the legacy v1.md fallback never silently fires.
        from megaplan._pipeline.flags import typed_ports_on as _tpo
        if _tpo() and getattr(pipeline, "binding_map", None) is not None:
            from megaplan._pipeline.contracts import PortBindError

            consumes = ()
            if isinstance(node, Stage):
                consumes = tuple(node.consumes) or tuple(
                    getattr(node.step, "consumes", ()) or ()
                )
            elif isinstance(node, ParallelStage):
                consumes = tuple(node.consumes)
            if consumes:
                new_inputs = dict(ctx.inputs)
                for consume in consumes:
                    cname = getattr(consume, "port_name", None) or getattr(
                        consume, "name", ""
                    )
                    key = (node.name, cname)
                    if key not in pipeline.binding_map:
                        raise PortBindError(
                            step_id=node.name,
                            consume_name=cname,
                            detail="not present in Pipeline.binding_map",
                        )
                    upstream_id, _upstream_port_name = pipeline.binding_map[key]
                    upstream_dir = ctx.plan_dir / upstream_id
                    path = None
                    if upstream_dir.is_dir():
                        candidates: list[tuple[int, Path]] = []
                        for child in upstream_dir.iterdir():
                            if child.is_file() and child.name.startswith("v"):
                                stem = child.stem
                                if stem[1:].isdigit():
                                    candidates.append((int(stem[1:]), child))
                        if candidates:
                            candidates.sort(key=lambda x: x[0], reverse=True)
                            path = candidates[0][1]
                    if path is None:
                        raise PortBindError(
                            step_id=node.name,
                            consume_name=cname,
                            detail=(
                                f"no upstream artifact under {upstream_dir} "
                                f"for upstream stage {upstream_id!r}"
                            ),
                        )
                    new_inputs[cname] = path
                ctx = dataclasses.replace(ctx, inputs=new_inputs)

        try:
            if isinstance(node, ParallelStage):
                result = _run_parallel_stage(node, ctx)
            else:
                assert isinstance(node, Stage)
                result = node.step.run(ctx)
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            _record_error(artifact_root, node.name, exc)
            raise

        _verify_outputs(node.name, result.outputs)

        patch = dict(result.state_patch)
        if _tpo():
            from megaplan._pipeline.types import StateDelta, apply_delta

            for _k, _v in patch.items():
                _versions = state.get("_state_meta", {}).get("versions", {})
                _current = int(_versions.get(_k, 0))
                state, _ = apply_delta(
                    state, StateDelta(op="replace", key=_k, value=_v, version=_current)
                )
                executor_owned_keys.add(_k)
        else:
            state.update(patch)
            executor_owned_keys.update(patch.keys())
        _merge_state_to_disk(artifact_root, state, executor_owned_keys=executor_owned_keys)

        if policy is not None:
            policy.stall.observe(state)
            if policy.stall.is_stalled():
                return {"state": state, "final_stage": node.name, "halt_reason": "stalled"}
            if policy.cost.should_abort(state):
                return {"state": state, "final_stage": node.name, "halt_reason": "cost_cap"}

        if result.next == "halt":
            if state.get("_pipeline_paused"):
                return {"state": state, "final_stage": node.name, "halt_reason": "awaiting_user"}
            return {"state": state, "final_stage": node.name}

        # Stage.loop_condition (M2 / T9b): per-iteration evaluation of a
        # caller-supplied predicate. True ⇒ exit the loop.
        cond = getattr(node, "loop_condition", None)
        if cond is not None:
            from megaplan._pipeline.pattern_stops import LoopState

            loop_iters[node.name] = loop_iters.get(node.name, 0) + 1
            last_fanout = state.get("last_fanout_results")
            ls = LoopState(
                state=state,
                last_fanout_results=last_fanout,
                iteration=loop_iters[node.name],
            )
            if cond(ls):
                return {"state": state, "final_stage": node.name, "halt_reason": "loop_condition"}

        # PipelineVerdict-first edge dispatch:
        #  - If verdict.override is set (Chunk D), match a kind="override" edge.
        #  - Else if verdict.recommendation is set (Chunk A), match a
        #    kind="gate" edge by recommendation.
        #  - Otherwise (or on miss) fall back to kind="normal" +
        #    label == result.next dispatch.
        from megaplan._pipeline.override import find_override_edge

        edge = None
        rec = None
        if result.verdict is not None and result.verdict.override is not None:
            edge = find_override_edge(node.edges, result.verdict.override)
        if edge is None and result.verdict is not None and result.verdict.recommendation is not None:
            rec = result.verdict.recommendation
            edge = next(
                (
                    e
                    for e in node.edges
                    if e.kind == "gate" and e.recommendation == rec
                ),
                None,
            )
            # Escalate-policy resolution (policy path only).
            if policy is not None and rec == "escalate" and edge is None:
                resolution = policy.escalate.resolve(node.name)
                if resolution == "force_proceed":
                    edge = next(
                        (
                            e
                            for e in node.edges
                            if e.kind == "gate" and e.recommendation == "proceed"
                        ),
                        None,
                    )
        if edge is None:
            edge = next(
                (
                    e
                    for e in node.edges
                    if e.kind == "normal" and e.label == result.next
                ),
                None,
            )
        if edge is None:
            raise LookupError(
                f"Stage {node.name!r} produced next={result.next!r} "
                f"recommendation={rec!r} but no matching edge was found"
            )
        if edge.target == "halt":
            return {"state": state, "final_stage": node.name}
        cursor = edge.target


def run_pipeline_with_policy(
    pipeline: Pipeline,
    ctx: StepContext,
    *,
    artifact_root: Path,
    policy: Any,
) -> dict[str, Any]:
    """Thin shim — delegates to :func:`run_pipeline` with ``policy=`` set.

    Preserves the historical TypeError-on-non-RuntimePolicy contract; behavior
    is now provided by the merged superset in :func:`run_pipeline`.
    """

    from megaplan._pipeline.runtime import RuntimePolicy as _Policy

    if not isinstance(policy, _Policy):
        raise TypeError(
            f"run_pipeline_with_policy requires a RuntimePolicy, got {type(policy)!r}"
        )
    return run_pipeline(pipeline, ctx, artifact_root=artifact_root, policy=policy)


