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

(f) Arnold-resolved edge dispatch (M3b): the executor delegates to
    :func:`arnold.pipeline.routing.resolve_edge` for override, decision,
    and normal edge dispatch. The Megaplan executor retains its own
    lifecycle (loop_condition, governor, state merge, policy stall,
    and escalate-policy fallback) while using the shared Arnold resolver
    for edge matching. ``kind='decision'`` edges (formerly ``kind='gate'``)
    match via ``label == verdict.recommendation``; ``kind='override'``
    edges match via ``label == 'override <action>'``. The escalate-policy
    fallback is applied when the resolver raises ``RoutingError`` for an
    ``escalate`` decision with no matching edge.
"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import json
import os
from pathlib import Path
from typing import Any, Mapping

from arnold.pipelines.megaplan._core.state import write_plan_state
from arnold.pipelines.megaplan.types import CliError
from arnold.pipelines.megaplan._pipeline.envelope import EMPTY_ENVELOPE, EnvelopeDroppedError, RunEnvelope
from arnold.pipelines.megaplan._pipeline.types import (
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


def _assert_envelope_present(envelope: "RunEnvelope | None", context: str) -> None:
    """Raise ``EnvelopeDroppedError`` when *envelope* is None and strict mode is on.

    No-op when ``conveyance_strict_on()`` is ``False``.
    """
    from arnold.pipelines.megaplan._pipeline.flags import conveyance_strict_on

    if conveyance_strict_on() and envelope is None:
        raise EnvelopeDroppedError(
            f"Envelope dropped at {context!r}: envelope is None under conveyance_strict_on()"
        )


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


def _record_error(
    artifact_root: Path,
    stage_name: str,
    exc: BaseException,
    *,
    envelope: "RunEnvelope | None" = None,
) -> None:
    _assert_envelope_present(envelope, f"_record_error:{stage_name}")
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
    from arnold.pipelines.megaplan.stages.inprocess_step import InProcessHandlerStep

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
    from arnold.pipelines.megaplan.stages.inprocess_step import InProcessHandlerStep

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

    joined = node.join(results, ctx)
    # M4 T3 — fold the reduced envelope's shard spend into the active
    # Governor accumulator (if installed).  No-op when no Governor is
    # attached or when the envelope lacks lease_id / fencing_token, which
    # preserves byte-identical behaviour on the single-process fallback
    # path where no shared capacity ledger is configured.
    try:
        from arnold.pipelines.megaplan.runtime.governor import current_governor as _cur_gov
        _gov_p = _cur_gov()
        if _gov_p is not None:
            _gov_p.fold_shard_spend(joined.envelope)
    except Exception:
        # fold is observational; never mask the upstream join result.
        # BudgetExceeded must still propagate, however — re-raise it.
        from arnold.pipelines.megaplan.runtime.governor import BudgetExceeded as _BE
        import sys as _sys
        _exc = _sys.exc_info()[1]
        if isinstance(_exc, _BE):
            raise
    return joined


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
    and escalate-policy fallback. Edge dispatch is delegated to the shared
    Arnold resolver (:func:`arnold.pipeline.routing.resolve_edge`) for both
    paths — the policy path inherits the override edge ladder from the bare
    path so verdict.override is honored consistently.
    """

    artifact_root = Path(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)

    if isinstance(ctx.state, Mapping):
        state: dict[str, Any] = dict(ctx.state)
    else:
        state = {}

    executor_owned_keys: set[str] = set()
    envelope: RunEnvelope = ctx.envelope if ctx.envelope is not None else EMPTY_ENVELOPE

    # M4 T2: under MEGAPLAN_UNIFIED_DISPATCH=1, install a tree-scoped Governor
    # for the duration of this pipeline run.  Strangler-pattern: bare path is
    # unchanged when the flag is off.
    from arnold.pipelines.megaplan._pipeline.flags import unified_dispatch_on as _udo
    if _udo():
        from arnold.pipelines.megaplan.runtime import install_runtime_governor as _install_gov
        _install_gov(envelope)
    cursor = pipeline.entry
    iterations = 0
    loop_iters: dict[str, int] = {}
    while True:
        if policy is not None and iterations >= policy.max_iterations:
            return {"state": state, "final_stage": cursor, "halt_reason": "max_iterations", "envelope": envelope}
        iterations += 1
        node = pipeline.stages[cursor]

        # Refresh ctx.state and ctx.envelope with the executor's working
        # state/envelope so each iteration sees the latest patches and
        # accumulated taint/cost/lineage. ctx is frozen; build a new
        # instance via dataclasses.replace.
        ctx = dataclasses.replace(ctx, state=state, envelope=envelope)

        # Flag-ON (M2 / T11b): runtime port-binding. Resolve each Stage's
        # consumes against Pipeline.binding_map and populate ctx.inputs
        # with concrete upstream artifact paths. On miss raise
        # PortBindError so the legacy v1.md fallback never silently fires.
        from arnold.pipelines.megaplan._pipeline.flags import typed_ports_on as _tpo
        if _tpo() and getattr(pipeline, "binding_map", None) is not None:
            from arnold.pipelines.megaplan._pipeline.contracts import PortBindError

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

        # Per-step Activation lifecycle: PENDING → READY → RUNNING → DONE/FAILED
        # Emission is gated on activation_emit_on(); creation is always cheap.
        from arnold.pipelines.megaplan._pipeline.flags import activation_emit_on as _aeo
        from arnold.pipelines.megaplan._core.activation import (
            Activation as _Activation,
            LifecycleState as _LS,
            ReadinessRule as _RR,
            compute_activation_id as _compute_act_id,
        )
        from arnold.pipelines.megaplan.observability.events import emit as _emit_event, EventKind as _EK

        _node_consumes: tuple
        if isinstance(node, Stage):
            _node_consumes = tuple(getattr(node, "consumes", ()) or ()) or tuple(
                getattr(node.step, "consumes", ()) or ()
            )
        else:
            _node_consumes = tuple(getattr(node, "consumes", ()) or ())
        _port_names: frozenset = frozenset(
            getattr(_c, "port_name", None) or getattr(_c, "name", str(_c))
            for _c in _node_consumes
        )
        _act_profile = str(ctx.state.get("profile", "")) if isinstance(ctx.state, dict) else ""
        _act_id = _compute_act_id(node.name, list(_port_names), _act_profile)
        _activation = _Activation(
            id=_act_id,
            node=node.name,
            input_ports=_port_names,
            profile=_act_profile,
            readiness_rule=_RR.UPSTREAM_DONE,
            lifecycle=_LS.PENDING,
        )
        _emit_on = _aeo()

        def _act_transition(act: "_Activation", to: "_LS") -> "_Activation":
            if _emit_on:
                _emit_event(
                    _EK.ACTIVATION_TRANSITIONED,
                    ctx.plan_dir,
                    payload={
                        "activation_id": act.id,
                        "node": act.node,
                        "from": act.lifecycle.value,
                        "to": to.value,
                    },
                )
            return dataclasses.replace(act, lifecycle=to)

        _activation = _act_transition(_activation, _LS.READY)
        _activation = _act_transition(_activation, _LS.RUNNING)

        try:
            # Governor charge at FIRING: BudgetExceeded propagates through the
            # except block below (FAILED transition + escalate ladder re-raise).
            from arnold.pipelines.megaplan.runtime.governor import current_governor as _current_gov
            _gov = _current_gov()
            if _gov is not None:
                _gov.charge(envelope)

            if isinstance(node, ParallelStage):
                result = _run_parallel_stage(node, ctx)
            else:
                assert isinstance(node, Stage)
                result = node.step.run(ctx)
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            _act_transition(_activation, _LS.FAILED)
            _record_error(artifact_root, node.name, exc, envelope=envelope)
            raise

        _activation = _act_transition(_activation, _LS.SUCCEEDED)

        _verify_outputs(node.name, result.outputs)

        patch = dict(result.state_patch)
        if _tpo():
            from arnold.pipelines.megaplan._pipeline.types import StateDelta, apply_delta

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

        # Envelope join: accumulate cross-cutting metadata from each step.
        _assert_envelope_present(result.envelope, f"step_result:{node.name}")
        envelope = envelope.join(result.envelope)
        # M4 T3 — fold the joined shard spend into the active Governor.
        # No-op without lease_id / fencing_token (single-process fallback is
        # byte-identical with the pre-M4 behaviour).
        from arnold.pipelines.megaplan.runtime.governor import current_governor as _cur_gov_seq
        _gov_s = _cur_gov_seq()
        if _gov_s is not None:
            _gov_s.fold_shard_spend(envelope)

        _assert_envelope_present(envelope, "_merge_state_to_disk")
        # T24: gated behind UNIFIED_EVALUAND — wrap the state-merge +
        # receipt write in a Store.transaction so state.json + receipt
        # row + DB roll back together on mid-stage crash (UU#8).
        from arnold.pipelines.megaplan._pipeline.flags import unified_evaluand_on
        if unified_evaluand_on():
            from arnold.pipelines.megaplan.observability.evaluand import _evaluand_transaction_boundary
            with _evaluand_transaction_boundary(envelope):
                _merge_state_to_disk(artifact_root, state, executor_owned_keys=executor_owned_keys)
        else:
            _merge_state_to_disk(artifact_root, state, executor_owned_keys=executor_owned_keys)

        if policy is not None:
            _assert_envelope_present(envelope, "stall_cost_observer")
            policy.stall.observe(state)
            if policy.stall.is_stalled():
                return {"state": state, "final_stage": node.name, "halt_reason": "stalled", "envelope": envelope}
            if policy.cost.should_abort(state):
                return {"state": state, "final_stage": node.name, "halt_reason": "cost_cap", "envelope": envelope}

        if result.next == "halt":
            if state.get("_pipeline_paused"):
                return {"state": state, "final_stage": node.name, "halt_reason": "awaiting_user", "envelope": envelope}
            return {"state": state, "final_stage": node.name, "envelope": envelope}

        # Stage.loop_condition (M2 / T9b): per-iteration evaluation of a
        # caller-supplied predicate. True ⇒ exit the loop.
        cond = getattr(node, "loop_condition", None)
        if cond is not None:
            _assert_envelope_present(envelope, "subloop_edge_dispatch")
            from arnold.pipelines.megaplan._pipeline.pattern_stops import LoopState

            loop_iters[node.name] = loop_iters.get(node.name, 0) + 1
            last_fanout = state.get("last_fanout_results")
            ls = LoopState(
                state=state,
                last_fanout_results=last_fanout,
                iteration=loop_iters[node.name],
            )
            if cond(ls):
                return {"state": state, "final_stage": node.name, "halt_reason": "loop_condition", "envelope": envelope}

        # M3b: delegate edge dispatch to the shared Arnold routing resolver.
        # The resolver handles halt (returns None for result.next == 'halt'),
        # override (kind='override' + label='override <action>'), decision
        # (kind='decision' + label=<key>), and normal label match.
        from arnold.pipeline.routing import resolve_edge, RoutingError

        edge = None
        try:
            edge = resolve_edge(
                stage=node,
                result=result,
                verdict=result.verdict,
                edges=node.edges,
            )
        except RoutingError:
            # Megaplan-specific escalate-policy fallback.
            # When the resolver finds no matching edge for an 'escalate'
            # decision, the policy may force-proceed instead.
            rec = result.verdict.recommendation if result.verdict else None
            if policy is not None and rec == "escalate":
                _assert_envelope_present(envelope, "escalate_path")
                resolution = policy.escalate.resolve(node.name)
                if resolution == "force_proceed":
                    edge = next(
                        (
                            e
                            for e in node.edges
                            if e.kind == "decision" and e.label == "proceed"
                        ),
                        None,
                    )
            if edge is None:
                raise

        if edge is None:
            # halt — resolve_edge returns None for result.next == "halt"
            return {"state": state, "final_stage": node.name, "envelope": envelope}
        if edge.target == "halt":
            return {"state": state, "final_stage": node.name, "envelope": envelope}
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

    from arnold.pipelines.megaplan._pipeline.runtime import RuntimePolicy as _Policy

    if not isinstance(policy, _Policy):
        raise TypeError(
            f"run_pipeline_with_policy requires a RuntimePolicy, got {type(policy)!r}"
        )
    return run_pipeline(pipeline, ctx, artifact_root=artifact_root, policy=policy)
