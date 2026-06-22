"""Megaplan-specific ExecutorHooks implementation.

``MegaplanExecutorHooks`` is the single source of truth for the lifecycle,
state-merge, and governor logic that the Megaplan executor injects into the
canonical walk-loop.  When wired (Step 7b onward), the canonical
``arnold.pipeline.executor.run_pipeline`` calls these callbacks; the inline
copies in ``_pipeline/executor.py`` are then deleted.

StateDelta distinction
----------------------

Megaplan uses a **CAS-style** ``StateDelta`` (``_pipeline/types.py:604``)
with ``op``, ``key``, ``value``, ``version`` fields that raise
:class:`~arnold_pipelines.megaplan._pipeline.types.StateDeltaConflict` on
version mismatch.  The canonical ``arnold.pipeline.state.StateDelta`` is a
simpler **multi-patch** container (``patches: tuple[dict, ...]``).  This
module receives the canonical shape from the canonical executor and bridges
to Megaplan's ``apply_delta`` when ``typed_ports_on()`` is active; it falls
back to a plain ``dict.update`` otherwise.  Never conflate the two — use
explicit module-qualified imports.

Boundary discipline
-------------------

This module imports from ``arnold.pipelines.megaplan`` (intentional — it IS
the Megaplan-side hooks class) and from ``arnold.pipeline.hooks`` (to inherit
``NullExecutorHooks``).  It must NOT import from
``arnold_pipelines.megaplan._pipeline.executor`` to avoid a circular dependency.
"""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold.pipeline.hooks import ExecutorHooks, NullExecutorHooks  # noqa: F401 – re-export
from arnold.pipeline.state import StateDelta as CanonicalStateDelta
from arnold.pipeline.types import ParallelStage, Stage, StepContext, StepResult

__all__ = [
    "MegaplanExecutorHooks",
]


# ---------------------------------------------------------------------------
# Internal file-write helpers (duplicated from executor.py — SINGLE SOURCE
# once the executor delegates here; executor copies will be removed in Step 7b)
# ---------------------------------------------------------------------------


def _atomic_write_json(dest: Path, payload: Any) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))
    os.replace(tmp, dest)


def _write_forensic_backup(source: Path) -> Path:
    backup_path = source.with_name(f"{source.name}.corrupt-executor-backup")
    tmp = backup_path.with_suffix(backup_path.suffix + ".tmp")
    tmp.write_bytes(source.read_bytes())
    os.replace(tmp, backup_path)
    return backup_path


# ---------------------------------------------------------------------------
# Enforcement binding (duplicated from executor.py — SINGLE SOURCE once the
# executor delegates here; executor copies will be removed in Step 7b)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class _EnforcementBinding:
    binding_map: Mapping[Any, Any] | None
    diagnostics: Mapping[str, Any] | None = None

    @property
    def available(self) -> bool:
        return self.binding_map is not None and self.diagnostics is None


def _edge_pairs(pipeline: Any) -> tuple[tuple[str, str], ...]:
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
        from arnold_pipelines.megaplan._pipeline.step_io_policy_adapter import (
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
    pipeline: Any,
    *,
    artifact_root: Path,
) -> _EnforcementBinding:
    existing = getattr(pipeline, "binding_map", None)
    if isinstance(existing, Mapping):
        return _EnforcementBinding(binding_map=existing)

    try:
        from arnold.pipeline import contracts
        from arnold.pipeline.declaration_lowering import bind_with_lowered_declarations

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


# ---------------------------------------------------------------------------
# MegaplanExecutorHooks
# ---------------------------------------------------------------------------


class MegaplanExecutorHooks(NullExecutorHooks):
    """Megaplan lifecycle, state-merge, and governor hooks for the canonical executor.

    Part A (this file) covers:
    - Activation lifecycle: ``on_step_start`` (PENDING→READY→RUNNING),
      ``on_step_end`` (→SUCCEEDED), ``on_step_error`` (→FAILED).
    - Governor charge: ``on_step_start`` (once per node, not per parallel child).
    - State merge: ``merge_state`` bridges canonical multi-patch ``StateDelta``
      to Megaplan CAS ``apply_delta`` when ``typed_ports_on()`` is active.
    - Disk persistence: ``on_stage_complete`` calls ``write_plan_state`` in
      executor-key-merge mode.
    - Typed-port binding (T9): ``on_step_start`` resolves port bindings when
      ``typed_ports_on()`` is active, with lazy enforcement-binding init.

    Part B (T10 onward) will add suspension, policy guards,
    envelope-join, and step-IO handoff.

    Hook extensions schema
    ----------------------
    The following keys must be present in ``ctx.hook_extensions`` for the
    Megaplan-side callbacks to function:

    * ``plan_dir`` — ``Path | str`` plan directory.
    * ``envelope`` — Megaplan ``RunEnvelope`` instance.
    * ``profile`` — opaque profile object (may be ``None``).
    * ``budget`` — opaque budget object (may be ``None``).

    These are injected by
    :func:`~arnold_pipelines.megaplan._pipeline.adapter.to_canonical_step_context`.
    """

    def __init__(
        self,
        *,
        pipeline: Any = None,
        artifact_root: Path | None = None,
    ) -> None:
        super().__init__()
        # Per-node activation state (stage.name → Activation dataclass).
        # Parallel stages share the same node name across child on_step_start
        # calls; we create the activation only on the first call per name.
        self._activations: dict[str, Any] = {}
        # Nodes whose governor has already been charged this run.
        self._charged_nodes: set[str] = set()
        # Pipeline reference for typed-port binding (optional — no binding when None).
        self._pipeline: Any = pipeline
        # Artifact root for lazy enforcement binding (optional).
        self._artifact_root: Path | None = Path(artifact_root) if artifact_root is not None else None
        # Lazy enforcement binding — computed on first on_step_start.
        self._enforcement_binding: _EnforcementBinding | None = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _plan_dir(self, ctx: StepContext) -> Path | None:
        """Extract ``plan_dir`` from ``ctx.hook_extensions``; coerce to ``Path``."""
        he: Mapping[str, Any] = getattr(ctx, "hook_extensions", {}) or {}
        plan_dir = he.get("plan_dir")
        if plan_dir is None:
            return None
        return Path(plan_dir) if isinstance(plan_dir, str) else plan_dir

    def _meg_envelope(self, ctx: StepContext) -> Any | None:
        """Extract the Megaplan ``RunEnvelope`` from ``ctx.hook_extensions``."""
        he: Mapping[str, Any] = getattr(ctx, "hook_extensions", {}) or {}
        return he.get("envelope")

    def _emit_activation_event(
        self,
        activation: Any,
        to_lifecycle: Any,
        plan_dir: Path,
    ) -> Any:
        """Emit ACTIVATION_TRANSITIONED event and return updated activation."""
        from arnold_pipelines.megaplan.observability.events import (
            EventKind as _EK,
            emit as _emit_event,
        )

        _emit_event(
            _EK.ACTIVATION_TRANSITIONED,
            plan_dir,
            payload={
                "activation_id": activation.id,
                "node": activation.node,
                "from": activation.lifecycle.value,
                "to": to_lifecycle.value,
            },
        )
        return dataclasses.replace(activation, lifecycle=to_lifecycle)

    def _ensure_enforcement_binding(self) -> _EnforcementBinding | None:
        """Lazily compute the enforcement binding on first call.

        Returns the binding (may be unavailable with diagnostics set).
        Returns None when no pipeline or artifact root is available.
        """
        if self._enforcement_binding is not None:
            return self._enforcement_binding
        if self._pipeline is None or self._artifact_root is None:
            return None
        self._enforcement_binding = _prepare_enforcement_binding(
            self._pipeline,
            artifact_root=self._artifact_root,
        )
        return self._enforcement_binding

    # ------------------------------------------------------------------
    # typed-port binding helpers (T9)
    # ------------------------------------------------------------------

    @staticmethod
    def _port_name(port: Any) -> str:
        return str(getattr(port, "port_name", None) or getattr(port, "name", ""))

    @staticmethod
    def _stage_consumes(node: Stage | ParallelStage) -> tuple[Any, ...]:
        if isinstance(node, ParallelStage):
            consumes = getattr(node, "consumes", None)
            return tuple(consumes) if consumes else ()
        # Stage: try stage-level consumes, then step-level consumes.
        consumes = getattr(node, "consumes", None)
        if consumes:
            return tuple(consumes)
        step = getattr(node, "step", None)
        step_consumes = getattr(step, "consumes", None)
        return tuple(step_consumes) if step_consumes else ()

    def _apply_typed_port_binding(
        self,
        stage: Stage | ParallelStage,
        ctx: StepContext,
    ) -> StepContext:
        """Resolve typed-port bindings and populate ctx.inputs.

        Only fires when ``typed_ports_on()`` is active AND the pipeline
        has a ``binding_map``.  Raises ``PortBindError`` on missing upstream
        artifacts so the legacy v1.md fallback never silently fires.
        """
        from arnold_pipelines.megaplan._pipeline.flags import typed_ports_on as _tpo

        if not _tpo():
            return ctx

        pipeline = self._pipeline
        if pipeline is None:
            return ctx

        binding_map = getattr(pipeline, "binding_map", None)
        if not isinstance(binding_map, Mapping):
            return ctx

        # Lazy-init the enforcement binding (observational — not used for
        # typed-port resolution which reads binding_map directly).
        self._ensure_enforcement_binding()

        from arnold_pipelines.megaplan._pipeline.contracts import PortBindError

        plan_dir = self._plan_dir(ctx)
        if plan_dir is None:
            return ctx

        consumes = self._stage_consumes(stage)
        if not consumes:
            return ctx

        new_inputs = dict(ctx.inputs)
        for consume in consumes:
            cname = self._port_name(consume)
            key = (stage.name, cname)
            if key not in binding_map:
                raise PortBindError(
                    step_id=stage.name,
                    consume_name=cname,
                    detail="not present in Pipeline.binding_map",
                )
            upstream_id, _upstream_port_name = binding_map[key]
            upstream_dir = plan_dir / upstream_id
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
                    step_id=stage.name,
                    consume_name=cname,
                    detail=(
                        f"no upstream artifact under {upstream_dir} "
                        f"for upstream stage {upstream_id!r}"
                    ),
                )
            new_inputs[cname] = path
        return dataclasses.replace(ctx, inputs=new_inputs)

    # ------------------------------------------------------------------
    # Activation: on_step_start / on_step_end / on_step_error
    # ------------------------------------------------------------------

    def on_step_start(
        self,
        stage: Stage | ParallelStage,
        ctx: StepContext,
    ) -> StepContext:
        """PENDING → READY → RUNNING lifecycle + governor charge (once per node)
        + typed-port binding (T9).
        """
        from arnold_pipelines.megaplan._core.activation import (
            Activation as _Activation,
            LifecycleState as _LS,
            ReadinessRule as _RR,
            compute_activation_id as _compute_act_id,
        )
        from arnold_pipelines.megaplan._pipeline.flags import activation_emit_on as _aeo

        if stage.name not in self._activations:
            _node_consumes = tuple(getattr(stage, "consumes", ()) or ())
            _port_names: frozenset[str] = frozenset(
                getattr(c, "port_name", None) or getattr(c, "name", str(c))
                for c in _node_consumes
            )
            state = ctx.state
            _act_profile = (
                str(state.get("profile", "")) if isinstance(state, dict) else ""
            )
            _act_id = _compute_act_id(stage.name, list(_port_names), _act_profile)

            activation = _Activation(
                id=_act_id,
                node=stage.name,
                input_ports=_port_names,
                profile=_act_profile,
                readiness_rule=_RR.UPSTREAM_DONE,
                lifecycle=_LS.PENDING,
            )

            _emit_on = _aeo()
            plan_dir = self._plan_dir(ctx)

            if _emit_on and plan_dir is not None:
                activation = self._emit_activation_event(activation, _LS.READY, plan_dir)
                activation = self._emit_activation_event(activation, _LS.RUNNING, plan_dir)
            else:
                activation = dataclasses.replace(activation, lifecycle=_LS.RUNNING)

            self._activations[stage.name] = activation

        # Governor charge — once per node across all parallel children.
        if stage.name not in self._charged_nodes:
            self._charged_nodes.add(stage.name)
            envelope = self._meg_envelope(ctx)
            if envelope is not None:
                from arnold_pipelines.megaplan.runtime.governor import (
                    BudgetExceeded,
                    current_governor as _current_gov,
                )

                gov = _current_gov()
                if gov is not None:
                    gov.charge(envelope)  # BudgetExceeded propagates to caller

        # T9: Typed-port binding — resolve consumes against binding_map.
        ctx = self._apply_typed_port_binding(stage, ctx)

        return ctx

    def on_step_end(
        self,
        stage: Stage | ParallelStage,
        ctx: StepContext,
        result: StepResult,
    ) -> StepResult:
        """Transition activation to SUCCEEDED."""
        from arnold_pipelines.megaplan._core.activation import LifecycleState as _LS
        from arnold_pipelines.megaplan._pipeline.flags import activation_emit_on as _aeo

        activation = self._activations.get(stage.name)
        if activation is not None:
            _emit_on = _aeo()
            plan_dir = self._plan_dir(ctx)
            if _emit_on and plan_dir is not None:
                activation = self._emit_activation_event(activation, _LS.SUCCEEDED, plan_dir)
            else:
                activation = dataclasses.replace(activation, lifecycle=_LS.SUCCEEDED)
            self._activations[stage.name] = activation

        return result

    def on_step_error(
        self,
        stage: Stage | ParallelStage,
        ctx: StepContext,
        exc: BaseException,
    ) -> None:
        """Transition activation to FAILED and record error artifact."""
        from arnold_pipelines.megaplan._core.activation import LifecycleState as _LS
        from arnold_pipelines.megaplan._pipeline.flags import activation_emit_on as _aeo

        activation = self._activations.get(stage.name)
        if activation is not None:
            _emit_on = _aeo()
            plan_dir = self._plan_dir(ctx)
            if _emit_on and plan_dir is not None:
                activation = self._emit_activation_event(activation, _LS.FAILED, plan_dir)
            else:
                activation = dataclasses.replace(activation, lifecycle=_LS.FAILED)
            self._activations[stage.name] = activation

        # Write error artifact next to the stage's artifact directory.
        plan_dir = self._plan_dir(ctx)
        if plan_dir is not None:
            stage_dir = plan_dir / stage.name
            stage_dir.mkdir(parents=True, exist_ok=True)
            _atomic_write_json(
                stage_dir / "error.json",
                {"stage": stage.name, "error": repr(exc)},
            )

    # ------------------------------------------------------------------
    # State merge
    # ------------------------------------------------------------------

    def merge_state(
        self,
        stage: Stage | ParallelStage,
        current_state: Any,
        patch: CanonicalStateDelta,
        owned_keys: frozenset[str],
    ) -> tuple[Any, frozenset[str]]:
        """Bridge canonical multi-patch ``StateDelta`` to Megaplan CAS semantics.

        When ``typed_ports_on()`` is active, each key in each patch dict is
        applied via Megaplan's CAS ``apply_delta`` (reads the current version
        from ``state['_state_meta']['versions']`` and increments it).  When the
        flag is off, plain ``dict.update`` is used — matching the legacy
        ``_pipeline/executor.py`` non-CAS path.
        """
        from arnold_pipelines.megaplan._pipeline.flags import typed_ports_on as _tpo

        state: Any = dict(current_state) if isinstance(current_state, dict) else current_state
        new_owned: set[str] = set(owned_keys)

        # Normalise the canonical StateDelta to a flat list of patch dicts.
        if isinstance(patch, CanonicalStateDelta):
            patch_dicts: tuple[dict[str, Any], ...] = patch.patches
        elif isinstance(patch, dict):
            patch_dicts = (patch,)
        else:
            patch_dicts = ()

        if _tpo():
            # CAS path: apply each (key, value) as a versioned replace delta.
            from arnold_pipelines.megaplan._pipeline.types import (
                StateDelta as _MegaStateDelta,
                apply_delta as _mp_apply_delta,
            )

            for patch_dict in patch_dicts:
                for k, v in patch_dict.items():
                    _versions: dict[str, Any] = (
                        state.get("_state_meta", {}).get("versions", {})
                        if isinstance(state, dict)
                        else {}
                    )
                    _current_ver = int(_versions.get(k, 0))
                    state, _ = _mp_apply_delta(
                        state,
                        _MegaStateDelta(op="replace", key=k, value=v, version=_current_ver),
                    )
                    new_owned.add(k)
        else:
            # Non-CAS path: plain dict.update (matches legacy executor behaviour).
            for patch_dict in patch_dicts:
                if isinstance(state, dict):
                    state.update(patch_dict)
                    new_owned.update(patch_dict.keys())

        return state, frozenset(new_owned)

    # ------------------------------------------------------------------
    # Disk persistence
    # ------------------------------------------------------------------

    def on_stage_complete(
        self,
        stage: Stage | ParallelStage,
        ctx: StepContext,
        result: StepResult,
        state: Any,
        owned_keys: frozenset[str],
    ) -> None:
        """Persist state to disk in executor-key-merge mode.

        Merges the executor's tracked keys with on-disk handler-written keys:
        keys in ``owned_keys`` take the in-memory value; all other on-disk keys
        retain their on-disk value.
        """
        plan_dir = self._plan_dir(ctx)
        if plan_dir is None or not isinstance(state, dict):
            return

        from arnold_pipelines.megaplan._core.state import write_plan_state
        from arnold_pipelines.megaplan.types import CliError

        try:
            write_plan_state(
                plan_dir,
                mode="executor-key-merge",
                state=state,
                executor_owned_keys=set(owned_keys),
            )
        except CliError as exc:
            state_path = plan_dir / "state.json"
            if exc.code == "corrupt_state_write" and state_path.exists():
                backup_path = _write_forensic_backup(state_path)
                exc.extra.setdefault("forensic_backup_path", str(backup_path))
            raise

    # ------------------------------------------------------------------
    # is_parallel_safe (delegates to InProcessHandlerStep guard)
    # ------------------------------------------------------------------

    def is_parallel_safe(self, step: Any) -> bool:
        """Reject ``InProcessHandlerStep`` from parallel fan-out (not thread-safe)."""
        try:
            from arnold_pipelines.megaplan.stages.inprocess_step import InProcessHandlerStep

            return not isinstance(step, InProcessHandlerStep)
        except ImportError:
            return True
