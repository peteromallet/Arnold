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

.. rubric:: Migration note — ``run_pipeline`` is NOT replaced by the bridge in M1

This standalone executor module is **not deleted** in the M1 sprint. The
:func:`run_pipeline` function remains the active entry point for all
non-``demo_judges`` pipelines. See ``_BRIDGE_CALLERS.md`` in this directory
for the complete call-survey checklist.

The standalone ``run_pipeline`` stays in place because:

(a) **Dispatcher allowlist.** The bridge dispatcher
    (:func:`run_pipeline_dispatch`) routes only ``demo_judges`` to the
    bridged path via a hard-coded ``_BRIDGED_PIPELINES = {'demo_judges'}``
    allowlist. All other pipeline keys fall through to this legacy executor
    unchanged.

(b) **``run_pipeline_with_policy`` + 19+ callers remain on legacy.**
    The ``policy``-based entry point and its callers (``registry.py``,
    ``tests/test_pipeline_runtime_e2e.py``, ``tests/test_auto_pipeline_runtime.py``,
    and ~16 other test modules) stay on the standalone executor for M1.
    Bridging ``run_pipeline_with_policy`` requires porting the policy
    lifecycle (stall, cost-cap, escalate) through the hooks surface,
    which is deferred.

(c) **CLI resume remains on legacy.**
    ``megaplan/cli/__init__.py:1339`` (``_resume_human_gate``) is
    intentionally left on the legacy executor. Resume authority is
    package-local and not redesigned in M1.

(d) **``_materialize_stage_step``-dependent pipelines aren't bridge-compatible.**
    Pipelines such as ``creative`` and ``epic_blitz`` rely on
    :func:`_materialize_stage_step` (``executor.py:709-721``) which injects
    stage-level ``StepInvocation`` metadata at runtime. The bridge
    (``_BridgeStep`` in ``_bridge.py``) does not yet honor this injection,
    so these pipelines **cannot** be dispatched through the bridge in M1.

**Deletion gate:** Every entry in ``_BRIDGE_CALLERS.md`` §"Intentionally left
on legacy" must move to §"Repointed" before this module can be deleted. See
that file for the per-caller tracking.
"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import json
import os
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.declaration_lowering import bind_with_lowered_declarations
from arnold.pipeline.runtime_contract_diagnostics import diagnostic_from_binding_failure
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
from arnold.pipeline.types import Stage as _GenericStage


@dataclasses.dataclass(frozen=True)
class _EnforcementBinding:
    binding_map: Mapping[Any, Any] | None
    diagnostics: Mapping[str, Any] | None = None

    @property
    def available(self) -> bool:
        return self.binding_map is not None and self.diagnostics is None


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


def _contract_status_value(contract_result: Any | None) -> str:
    if contract_result is None:
        return "completed"
    status = getattr(contract_result, "status", None)
    return str(getattr(status, "value", status) or "completed")


def _contract_result_json(contract_result: Any | None) -> dict[str, Any] | None:
    if contract_result is None:
        return None
    to_json = getattr(contract_result, "to_json", None)
    if callable(to_json):
        return dict(to_json())
    if isinstance(contract_result, Mapping):
        return dict(contract_result)
    return {"payload": repr(contract_result)}


def _terminal_result(
    *,
    state: dict[str, Any],
    final_stage: str,
    envelope: "RunEnvelope",
    contract_result: Any | None,
    halt_reason: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "state": state,
        "final_stage": final_stage,
        "envelope": envelope,
        "status": status or _contract_status_value(contract_result),
        "contract_result": _contract_result_json(contract_result),
    }
    if halt_reason is not None:
        payload["halt_reason"] = halt_reason
    return payload


def _is_suspended_contract(contract_result: Any | None) -> bool:
    return _contract_status_value(contract_result) == "suspended"


def _jsonable_cursor(raw: Any) -> Any | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def _legacy_awaiting_user_contract(
    *,
    plan_dir: Path,
    state: Mapping[str, Any],
    stage_name: str,
) -> Any | None:
    if not state.get("_pipeline_paused"):
        return None

    from arnold.pipeline import ContractResult, ContractStatus, Suspension
    from arnold.pipelines.megaplan._pipeline.resume import check_awaiting_user

    awaiting = check_awaiting_user(plan_dir) or {}
    paused_stage = state.get("_pipeline_paused_stage")
    stage = paused_stage if isinstance(paused_stage, str) and paused_stage else stage_name
    choices = awaiting.get("choices") if isinstance(awaiting.get("choices"), list) else []
    artifact_path = awaiting.get("artifact_path")
    display_refs = ()
    if isinstance(artifact_path, str) and artifact_path:
        from arnold.pipeline import EvidenceArtifactRef

        display_refs = (
            EvidenceArtifactRef(
                uri=artifact_path,
                content_type="application/octet-stream",
                name=Path(artifact_path).name,
            ),
        )
    cursor = {
        "phase": stage,
        "retry_strategy": "awaiting_user",
        "kind": "awaiting_user",
    }
    if choices:
        cursor["choices"] = [str(choice) for choice in choices]
    return ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=Suspension(
            kind="human",
            awaitable="user",
            prompt=str(awaiting.get("message") or f"Pipeline paused at stage '{stage}'."),
            display_refs=display_refs,
            resume_input_schema={
                "type": "object",
                "properties": {
                    "choice": {
                        "type": "string",
                        "enum": [str(choice) for choice in choices],
                    }
                },
                "required": ["choice"],
                "additionalProperties": False,
            },
            resume_cursor=json.dumps(cursor, sort_keys=True),
            thread_ref=str(awaiting.get("pipeline")) if awaiting.get("pipeline") else None,
            actor="human",
        ),
        payload={
            "source": "awaiting_user.json",
            "awaiting_user": dict(awaiting),
        },
    )


def _resume_cursor_for_contract(contract_result: Any | None) -> Any | None:
    if contract_result is None:
        return None
    suspension = getattr(contract_result, "suspension", None)
    payload = getattr(contract_result, "payload", None)
    if isinstance(payload, Mapping):
        pending = payload.get("pending_suspensions")
        if isinstance(pending, list) and pending:
            children: dict[str, Any] = {}
            for item in pending:
                if not isinstance(item, Mapping):
                    continue
                child_id = item.get("child_id")
                if not isinstance(child_id, str) or not child_id:
                    continue
                children[child_id] = _jsonable_cursor(item.get("cursor"))
            if children:
                cursor: dict[str, Any] = {
                    "kind": "composite_suspension",
                    "version": 1,
                    "children": children,
                    "pending_suspensions": pending,
                }
                if suspension is not None:
                    awaitable = getattr(suspension, "awaitable", None)
                    thread_ref = getattr(suspension, "thread_ref", None)
                    actor = getattr(suspension, "actor", None)
                    if awaitable is not None:
                        cursor["shared_awaitable"] = awaitable
                    if thread_ref is not None:
                        cursor["shared_thread_ref"] = thread_ref
                    if actor is not None:
                        cursor["shared_actor"] = actor
                return cursor
    if suspension is None:
        return None
    if _contract_status_value(contract_result) not in {"suspended", "failed"}:
        return None
    return _jsonable_cursor(getattr(suspension, "resume_cursor", None))


def _persist_suspension_cursor(
    *,
    state: dict[str, Any],
    executor_owned_keys: set[str],
    contract_result: Any | None,
    artifact_root: str | Path,
    stage: str,
) -> None:
    cursor = _resume_cursor_for_contract(contract_result)
    if cursor is None:
        return
    # Ensure composite cursors carry a top-level ``phase`` so that
    # suspension-aware fan-out consumers can discover the origin stage
    # without inspecting every child payload.
    if isinstance(cursor, dict) and cursor.get("kind") == "composite_suspension" and "phase" not in cursor:
        cursor["phase"] = stage
    state["resume_cursor"] = cursor
    executor_owned_keys.add("resume_cursor")
    if isinstance(cursor, dict) and cursor.get("kind") == "composite_suspension":
        from arnold.pipeline.resume import persist_composite_resume_cursor
        # Broaden durable metadata forwarding to exactly the approved
        # allow-list: phase, pipeline, pipeline_manifest_hash,
        # pending_suspensions, and shared_* keys.  Child cursor payloads
        # are forwarded unchanged.
        persist_composite_resume_cursor(
            artifact_root,
            children=cursor.get("children", {}),
            pending_suspensions=cursor.get("pending_suspensions", []),
            phase=cursor.get("phase"),
            pipeline=cursor.get("pipeline"),
            pipeline_manifest_hash=cursor.get("pipeline_manifest_hash"),
            **{
                key: value
                for key, value in cursor.items()
                if key.startswith("shared_")
            },
        )


def _persist_terminal_suspended_contract_result(
    *,
    state: dict[str, Any],
    executor_owned_keys: set[str],
    contract_result: Any | None,
) -> None:
    if not _is_suspended_contract(contract_result):
        return
    state["contract_result"] = _contract_result_json(contract_result)
    executor_owned_keys.add("contract_result")


def _load_json_object(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        raise AssertionError("resume re-verification succeeded without an artifact path")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise AssertionError("resume re-verification payload must be a JSON object")
    return dict(data)


def _resume_reverify_suspension(contract_result: Any | None) -> Any | None:
    if contract_result is None:
        return None
    payload = getattr(contract_result, "payload", None)
    if not isinstance(payload, Mapping):
        return None
    suspension_payload = payload.get("resume_reverify_suspension")
    if not isinstance(suspension_payload, Mapping):
        return None

    from arnold.pipeline import HumanSuspension

    return HumanSuspension.from_json(suspension_payload)


def _resume_reverify_checkpoint(contract_result: Any | None) -> dict[str, Any] | None:
    if contract_result is None:
        return None
    payload = getattr(contract_result, "payload", None)
    if not isinstance(payload, Mapping):
        return None
    checkpoint = payload.get("resume_reverify_checkpoint")
    return dict(checkpoint) if isinstance(checkpoint, Mapping) else None


def _resume_reverify_invalid_result(
    *,
    result: StepResult,
    suspension: Any,
    diagnostic: Mapping[str, Any] | None,
) -> StepResult:
    from arnold.pipeline import ContractResult, ContractStatus

    return dataclasses.replace(
        result,
        outputs={},
        state_patch={},
        contract_result=ContractResult(
            status=ContractStatus.SUSPENDED,
            suspension=suspension,
            payload=(
                {"resume_reverify_diagnostic": dict(diagnostic)}
                if isinstance(diagnostic, Mapping)
                else {}
            ),
        ),
    )


def _resume_reverify_valid_result(
    *,
    result: StepResult,
    port: str,
    authoritative_payload: Mapping[str, Any],
) -> StepResult:
    from arnold.pipeline import ContractResult, ContractStatus

    existing_contract = result.contract_result
    payload = {}
    if existing_contract is not None and isinstance(getattr(existing_contract, "payload", None), Mapping):
        payload = dict(existing_contract.payload)
    payload.pop("resume_reverify_suspension", None)
    payload[port] = dict(authoritative_payload)

    if existing_contract is None:
        contract_result = ContractResult(
            status=ContractStatus.COMPLETED,
            payload=payload,
        )
    else:
        contract_result = dataclasses.replace(
            existing_contract,
            status=ContractStatus.COMPLETED,
            suspension=None,
            payload=payload,
        )
    return dataclasses.replace(result, contract_result=contract_result)


def _apply_resume_reverification(
    *,
    result: StepResult,
    stage_name: str,
    ctx: StepContext,
    artifact_root: Path,
) -> StepResult:
    """Rewrite declaration-bearing human-gate resumes before any merge surface."""

    suspension = _resume_reverify_suspension(result.contract_result)
    if suspension is None:
        return result

    from arnold.pipeline.executor import StepIOEnforcementError
    from arnold.pipeline.resume_validation import reverify_resume_produces
    from arnold.pipelines.megaplan._pipeline.schema_registry_adapter import (
        create_contract_schema_registry,
    )

    verified = reverify_resume_produces(
        suspension,
        artifact_root=artifact_root,
        schema_registry=create_contract_schema_registry(ctx.plan_dir),
        producer_stage=stage_name,
    )
    if verified.outcome == "no_op":
        return result

    if verified.outcome == "invalid":
        if (
            verified.declaration is not None
            and verified.declaration.invalid_policy == "fail"
        ):
            detail = "resume re-verification failed"
            if isinstance(verified.diagnostic, Mapping):
                detail = str(verified.diagnostic.get("detail") or detail)
            raise StepIOEnforcementError(
                detail,
                author_diagnostic=verified.diagnostic,
            )
        checkpoint = _resume_reverify_checkpoint(result.contract_result)
        if checkpoint is not None:
            _atomic_write_json(ctx.plan_dir / "awaiting_user.json", checkpoint)
        return _resume_reverify_invalid_result(
            result=result,
            suspension=suspension,
            diagnostic=verified.diagnostic,
        )

    declaration = verified.declaration
    port = str(getattr(declaration, "port", None) or stage_name)
    rewritten = _resume_reverify_valid_result(
        result=result,
        port=port,
        authoritative_payload=_load_json_object(verified.resolved_artifact_path),
    )
    awaiting_path = ctx.plan_dir / "awaiting_user.json"
    if awaiting_path.exists():
        awaiting_path.unlink()
    return rewritten


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


def _edge_pairs(pipeline: Pipeline) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for stage_name, stage in pipeline.stages.items():
        for edge in getattr(stage, "edges", ()) or ():
            target = getattr(edge, "target", "")
            if target and target != "halt":
                pairs.append((stage_name, target))
    return tuple(pairs)


def _binding_diagnostics(result: Any) -> dict[str, Any]:
    return {
        "error_kind": getattr(result, "error_kind", type(result).__name__),
        "wanted": repr(getattr(result, "wanted", "")),
        "candidates": [repr(candidate) for candidate in getattr(result, "candidates", ())],
        "suggested_moves": list(getattr(result, "suggested_moves", ())),
    }


def _emit_binding_unavailable_telemetry(
    *,
    artifact_root: Path,
    diagnostics: Mapping[str, Any],
) -> None:
    try:
        from arnold.pipeline.step_io_contract import (
            StepIOClassification,
            StepIOContractDecision,
            StepIODiagnostic,
        )
        from arnold.pipeline.step_io_telemetry import (
            TELEMETRY_FILENAME,
            emit_decision_telemetry,
        )
        from arnold.pipelines.megaplan._pipeline.step_io_policy_adapter import (
            resolve_megaplan_step_io_policy,
        )

        detail = str(diagnostics.get("error_kind", "binding unavailable"))
        decision = StepIOContractDecision(
            classification=StepIOClassification.BINDING_UNAVAILABLE,
            allow_read=True,
            allow_write=True,
            value=None,
            diagnostics=(
                StepIODiagnostic(
                    code="binding_unavailable",
                    message=detail,
                ),
            ),
            block_reason=detail,
        )
        emit_decision_telemetry(
            decision=decision,
            policy=resolve_megaplan_step_io_policy(
                configured_mode=None,
                producer_typed=True,
                consumer_typed=True,
            ),
            artifact="executor_binding",
            operation="bind",
            telemetry_path=artifact_root / TELEMETRY_FILENAME,
            seam="executor_startup",
        )
    except Exception:
        # Startup binding diagnostics are observational for legacy runs.
        return


def _prepare_enforcement_binding(
    pipeline: Pipeline,
    *,
    artifact_root: Path,
) -> _EnforcementBinding:
    existing = getattr(pipeline, "binding_map", None)
    if isinstance(existing, Mapping):
        return _EnforcementBinding(binding_map=existing)

    try:
        from arnold.pipeline import contracts

        edges = _edge_pairs(pipeline)
        result = bind_with_lowered_declarations(pipeline.stages, edges)
        if result is None:
            result = contracts.bind(
                pipeline.stages,
                edges,
                typed_ports=True,
            )
    except Exception as exc:
        diagnostics = {
            "error_kind": type(exc).__name__,
            "detail": str(exc),
        }
        _emit_binding_unavailable_telemetry(
            artifact_root=artifact_root,
            diagnostics=diagnostics,
        )
        return _EnforcementBinding(binding_map=None, diagnostics=diagnostics)

    binding_map = getattr(result, "binding_map", None)
    if isinstance(binding_map, Mapping):
        return _EnforcementBinding(binding_map=binding_map)

    diagnostics = _binding_diagnostics(result)
    _emit_binding_unavailable_telemetry(
        artifact_root=artifact_root,
        diagnostics=diagnostics,
    )
    return _EnforcementBinding(binding_map=None, diagnostics=diagnostics)


def _port_name(port: Any) -> str:
    return str(getattr(port, "port_name", None) or getattr(port, "name", ""))


def _stage_produces(stage: Any) -> tuple[Any, ...]:
    from arnold.pipeline.declaration_lowering import lower_stage_declarations

    lowered = lower_stage_declarations(stage)
    if lowered.effective_produces:
        return tuple(lowered.effective_produces)
    produces = getattr(stage, "produces", None)
    if produces:
        return tuple(produces)
    step = getattr(stage, "step", None)
    step_produces = getattr(step, "produces", None)
    return tuple(step_produces) if step_produces else ()


def _stage_consumes(stage: Any) -> tuple[Any, ...]:
    from arnold.pipeline.declaration_lowering import lower_stage_declarations

    lowered = lower_stage_declarations(stage)
    if lowered.effective_consumes:
        return tuple(lowered.effective_consumes)
    consumes = getattr(stage, "consumes", None)
    if consumes:
        return tuple(consumes)
    step = getattr(stage, "step", None)
    step_consumes = getattr(step, "consumes", None)
    return tuple(step_consumes) if step_consumes else ()


def _find_port(ports: tuple[Any, ...], port_name: str) -> Any:
    return next((port for port in ports if _port_name(port) == port_name), None)


def _step_io_handoff_value(result: StepResult) -> Any | None:
    contract_result = getattr(result, "contract_result", None)
    if contract_result is None:
        return None
    return contract_result


def _evaluate_cursor_handoff(
    *,
    pipeline: Pipeline,
    binding: _EnforcementBinding,
    producer_stage: Any,
    consumer_stage: Any,
    result: StepResult,
    ctx: StepContext,
    artifact_root: Path,
) -> None:
    value = _step_io_handoff_value(result)
    if value is None:
        return

    consumer_ports = _stage_consumes(consumer_stage)
    if not consumer_ports:
        return

    from arnold.pipeline.step_io_contract import StepIOOperation
    from arnold.pipeline.step_io_handoff import evaluate_step_io_handoff
    from arnold.pipeline.step_io_seams import SeamResolution, resolve_seam_from_binding_map
    from arnold.pipeline.step_io_telemetry import TELEMETRY_FILENAME
    from arnold.pipelines.megaplan._pipeline.schema_registry_adapter import (
        create_step_io_contract_context,
    )
    from arnold.pipelines.megaplan._pipeline.step_io_policy_adapter import (
        resolve_megaplan_step_io_policy,
    )

    for consumer_port in consumer_ports:
        consumer_port_name = _port_name(consumer_port)
        producer_port_name = ""
        producer_port = None
        binding_map = binding.binding_map
        if isinstance(binding_map, Mapping):
            bound = binding_map.get((consumer_stage.name, consumer_port_name))
            if isinstance(bound, tuple) and len(bound) == 2:
                producer_stage_name, producer_port_name = bound
                if producer_stage_name != producer_stage.name:
                    continue
                producer_port = _find_port(_stage_produces(producer_stage), producer_port_name)

        if binding.diagnostics is not None:
            reason = str(
                binding.diagnostics.get("detail")
                or binding.diagnostics.get("error_kind")
                or "binding lookup unavailable"
            )
            seam = SeamResolution(
                seam_id=None,
                producer_typed=bool(_stage_produces(producer_stage)),
                consumer_typed=True,
                both_sides_typed=bool(_stage_produces(producer_stage)),
                binding_found=False,
                reason=reason,
            )
        else:
            seam = resolve_seam_from_binding_map(
                pipeline,
                pipeline_id=getattr(pipeline, "name", "pipeline"),
                consumer_step=consumer_stage.name,
                consumer_port=consumer_port_name,
            )

        state_config = ctx.state if isinstance(ctx.state, Mapping) else None
        handoff = evaluate_step_io_handoff(
            value,
            operation=StepIOOperation.WRITE,
            context=create_step_io_contract_context(
                operation=StepIOOperation.WRITE,
                explicit_root=ctx.plan_dir,
            ),
            policy=resolve_megaplan_step_io_policy(
                plan_dir=ctx.plan_dir,
                state_config=state_config,
                binding=seam,
                producer_typed=seam.producer_typed,
                consumer_typed=seam.consumer_typed,
            ),
            pipeline=pipeline,
            pipeline_id=getattr(pipeline, "name", "pipeline"),
            consumer_step=consumer_stage.name,
            consumer_port=consumer_port_name,
            seam=seam,
            producer_port=producer_port,
            consumer_port_decl=consumer_port,
            artifact=f"{producer_stage.name}.contract_result",
            telemetry_path=artifact_root / TELEMETRY_FILENAME,
            producer_stage=producer_stage.name,
        )
        if handoff.blocks_write:
            if handoff.author_diagnostic is not None:
                raise ValueError(f"Step IO handoff blocked: {handoff.author_diagnostic.message}")
            if binding.diagnostics is not None:
                envelope = getattr(handoff.decision, "envelope", None)
                logical_type = str(getattr(envelope, "logical_type", None) or "unknown")
                schema_version = str(getattr(envelope, "schema_version", None) or "unknown")
                diagnostic = diagnostic_from_binding_failure(
                    diagnostics=binding.diagnostics,
                    producer_stage=producer_stage.name,
                    consumer_stage=consumer_stage.name,
                    logical_type=logical_type,
                    schema_version=schema_version,
                )
                raise ValueError(f"Step IO handoff blocked: {diagnostic.message}")
            reason = handoff.decision.block_reason or handoff.decision.classification.value
            raise ValueError(
                "Step IO handoff blocked "
                f"{producer_stage.name!r} -> {consumer_stage.name!r} "
                f"for port {consumer_port_name!r}: {reason}"
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


def _compose_parallel_join_contract(
    node: ParallelStage,
    results: list[StepResult],
    joined: StepResult,
) -> StepResult:
    child_contracts = [result.contract_result for result in results]
    if not any(contract is not None for contract in child_contracts):
        return joined

    from arnold.pipeline import reduce_contract_results

    child_ids = [getattr(step, "name", f"child_{index}") for index, step in enumerate(node.steps)]
    reduced = reduce_contract_results(child_contracts, child_ids=child_ids)
    explicit = joined.contract_result
    child_needs_reduction = any(
        _contract_status_value(contract) in {"suspended", "failed"}
        for contract in child_contracts
    )

    if explicit is None:
        return dataclasses.replace(joined, contract_result=reduced)
    if not child_needs_reduction:
        return joined

    payload = dict(reduced.payload)
    payload["executor_composition"] = {
        "source": "_run_parallel_stage.post_join",
        "join_contract": explicit.to_json(),
        "join_payload": dict(explicit.payload),
    }
    return dataclasses.replace(
        joined,
        contract_result=dataclasses.replace(reduced, payload=payload),
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
    joined = _compose_parallel_join_contract(node, results, joined)
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


def _is_single_stage(node: Any) -> bool:
    """Return whether *node* is a Megaplan or generic Arnold Stage."""
    return isinstance(node, (Stage, _GenericStage))


def _materialize_stage_step(node: Stage):
    """Inject stage-level invocation metadata into runtime AgentStep instances."""
    if node.invocation is None:
        return node.step

    from arnold.pipelines.megaplan._pipeline.steps.agent import AgentStep

    step = node.step
    if not isinstance(step, AgentStep):
        return step
    if step._invocation == node.invocation:
        return step
    return dataclasses.replace(step, _invocation=node.invocation, _invocation_explicit=True)


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
    _enforcement_binding = _prepare_enforcement_binding(
        pipeline,
        artifact_root=artifact_root,
    )

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
    latest_contract_result: Any | None = None
    while True:
        if policy is not None and iterations >= policy.max_iterations:
            return _terminal_result(
                state=state,
                final_stage=cursor,
                halt_reason="max_iterations",
                envelope=envelope,
                contract_result=latest_contract_result,
            )
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
            if _is_single_stage(node):
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
        if _is_single_stage(node):
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
                assert _is_single_stage(node)
                result = _materialize_stage_step(node).run(ctx)
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            _act_transition(_activation, _LS.FAILED)
            _record_error(artifact_root, node.name, exc, envelope=envelope)
            raise

        _activation = _act_transition(_activation, _LS.SUCCEEDED)

        _verify_outputs(node.name, result.outputs)
        result = _apply_resume_reverification(
            result=result,
            stage_name=node.name,
            ctx=ctx,
            artifact_root=artifact_root,
        )
        latest_contract_result = result.contract_result

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

        if latest_contract_result is None and state.get("_pipeline_paused"):
            latest_contract_result = _legacy_awaiting_user_contract(
                plan_dir=ctx.plan_dir,
                state=state,
                stage_name=node.name,
            )
        _persist_suspension_cursor(
            state=state,
            executor_owned_keys=executor_owned_keys,
            contract_result=latest_contract_result,
            artifact_root=artifact_root,
            stage=node.name,
        )
        _persist_terminal_suspended_contract_result(
            state=state,
            executor_owned_keys=executor_owned_keys,
            contract_result=latest_contract_result,
        )

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
                return _terminal_result(
                    state=state,
                    final_stage=node.name,
                    halt_reason="stalled",
                    envelope=envelope,
                    contract_result=latest_contract_result,
                )
            if policy.cost.should_abort(state):
                return _terminal_result(
                    state=state,
                    final_stage=node.name,
                    halt_reason="cost_cap",
                    envelope=envelope,
                    contract_result=latest_contract_result,
                )

        if _is_suspended_contract(latest_contract_result):
            _suspension_kind = getattr(
                getattr(latest_contract_result, "suspension", None), "kind", None
            )
            _halt_reason = "awaiting_user" if _suspension_kind == "human" else "suspended"
            return _terminal_result(
                state=state,
                final_stage=node.name,
                halt_reason=_halt_reason,
                envelope=envelope,
                contract_result=latest_contract_result,
            )

        if result.next == "halt":
            if state.get("_pipeline_paused"):
                return _terminal_result(
                    state=state,
                    final_stage=node.name,
                    halt_reason="awaiting_user",
                    envelope=envelope,
                    contract_result=latest_contract_result,
                )
            return _terminal_result(
                state=state,
                final_stage=node.name,
                envelope=envelope,
                contract_result=latest_contract_result,
            )

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
                return _terminal_result(
                    state=state,
                    final_stage=node.name,
                    halt_reason="loop_condition",
                    envelope=envelope,
                    contract_result=latest_contract_result,
                )

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
            return _terminal_result(
                state=state,
                final_stage=node.name,
                envelope=envelope,
                contract_result=latest_contract_result,
            )
        if edge.target == "halt":
            return _terminal_result(
                state=state,
                final_stage=node.name,
                envelope=envelope,
                contract_result=latest_contract_result,
            )
        _evaluate_cursor_handoff(
            pipeline=pipeline,
            binding=_enforcement_binding,
            producer_stage=node,
            consumer_stage=pipeline.stages[edge.target],
            result=result,
            ctx=ctx,
            artifact_root=artifact_root,
        )
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
