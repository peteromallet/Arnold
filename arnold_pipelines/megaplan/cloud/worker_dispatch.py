"""Canonical production worker admission and controlled dispatch.

This module is deliberately small: admission owns pre-launch invariants, the
ledger owns durable reservation/terminal state, and ``dispatch_with_admission``
owns the only retry/wait loop.  Door adapters pass an immutable request and a
closure; they never perform a second preflight.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.incident.schema import ReservationReconciled, semantic_dispatch_fingerprint
from arnold_pipelines.megaplan.orchestration.phase_result import (
    DispatchOutcome,
    SchedulingCondition,
)
from arnold_pipelines.megaplan.types import CliError, parse_agent_spec

SCHEMA_VERSION = 1
RECEIPT_DERIVATION_VERSION = "1"
DEFAULT_TIMEOUT_BUDGET_S = 3600.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()).hexdigest()


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _refusal(
    request: Any,
    code: str,
    reason: str,
    **evidence: Any,
) -> AdmissionRefusal:
    """Build a lossless typed refusal from a possibly malformed request.

    Admission is a trust boundary.  Invalid caller data must become a typed
    refusal rather than leaking ``AttributeError``/``TypeError`` from the
    dataclass or parser.  Keep the identity fields best-effort so the caller
    can correlate a refusal even when one of them is the field that failed.
    """
    mapping = _as_mapping(request)
    def text(name: str) -> str:
        value = getattr(request, name, mapping.get(name, ""))
        return value.strip() if isinstance(value, str) else str(value or "")

    return AdmissionRefusal(
        code=str(code or "admission_rejected"),
        reason=str(reason),
        plan_id=text("plan_id") or "unknown",
        phase=text("phase") or "unknown",
        logical_dispatch_id=text("logical_dispatch_id") or "unknown",
        admission_attempt=(
            int(getattr(request, "admission_attempt", mapping.get("admission_attempt", 1)))
            if str(getattr(request, "admission_attempt", mapping.get("admission_attempt", 1))).isdigit()
            else 1
        ),
        evidence=evidence,
    )


@dataclass(frozen=True)
class WorkerExecutionContextRef:
    ledger_root: str
    plan_id: str
    phase: str
    dispatch_family_id: str
    logical_dispatch_id: str
    admission_receipt_id: str
    semantic_dispatch_fingerprint: str
    selected_spec: str
    physical_door_id: str

    def to_dict(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}
    def to_environment(self, *, variable: str = "ARNOLD_WORKER_EXECUTION_CONTEXT") -> dict[str, str]:
        return {variable: json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))}

    @classmethod
    def from_environment(cls, environment: Mapping[str, Any], *, variable: str = "ARNOLD_WORKER_EXECUTION_CONTEXT") -> "WorkerExecutionContextRef":
        raw = environment.get(variable)
        if not isinstance(raw, str) or not raw:
            raise ValueError("worker execution context is missing from environment")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("worker execution context environment value is invalid JSON") from exc
        if not isinstance(payload, Mapping):
            raise ValueError("worker execution context environment value must be an object")
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WorkerExecutionContextRef":
        expected = set(cls.__dataclass_fields__)
        unknown = set(payload) - expected
        missing = expected - set(payload)
        if unknown or missing:
            raise ValueError(f"invalid worker execution context (unknown={sorted(unknown)}, missing={sorted(missing)})")
        values = {name: payload[name] for name in expected}
        if any(not isinstance(value, str) or not value for value in values.values()):
            raise ValueError("worker execution context fields must be non-empty strings")
        return cls(**values)


@dataclass(frozen=True)
class WorkerAdmissionRequest:
    plan_id: str
    phase: str
    dispatch_family_id: str
    logical_dispatch_id: str
    physical_door_id: str
    configured_spec: str
    selected_spec: str
    source_revision: str
    runtime_vector: Any
    manifest_identity: str
    seed_identity: str
    dependency_interpreter_identity: str
    prompt_or_phase_input_identity: str
    configured_fallback_chain_identity: str
    authorized_route_identity: str
    projection_key: str
    expected_projection_version: int | None = None
    timeout_budget_s: float = DEFAULT_TIMEOUT_BUDGET_S
    parent_logical_dispatch_id: str | None = None
    authorizing_event_id: str | None = None
    admission_attempt: int = 1
    production_intent: bool = True
    ledger_root: Path | None = None
    changed_precondition_event_id: str | None = None
    route_liveness_resolver: Callable[[str, str, str], Mapping[str, Any]] | None = field(default=None, compare=False, repr=False)
    source_runtime_validator: Callable[["WorkerAdmissionRequest"], Any] | None = field(default=None, compare=False, repr=False)
    memory_headroom_reader: Callable[[str], Mapping[str, Any] | None] | None = field(default=None, compare=False, repr=False)
    cooldown_reader: Callable[[Path | None, str, str], float] | None = field(default=None, compare=False, repr=False)
    ledger: IncidentLedger | None = field(default=None, compare=False, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Return the transport form, excluding process-local callback hooks."""
        local_only = {
            "route_liveness_resolver", "source_runtime_validator",
            "memory_headroom_reader", "cooldown_reader", "ledger",
        }
        result: dict[str, Any] = {}
        for name in self.__dataclass_fields__:
            if name in local_only:
                continue
            value = getattr(self, name)
            result[name] = str(value) if isinstance(value, Path) else value
        return result

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WorkerAdmissionRequest":
        data = dict(payload)
        if data.get("ledger_root") is not None:
            data["ledger_root"] = Path(str(data["ledger_root"]))
        return cls(**data)


@dataclass(frozen=True)
class WorkerAdmissionReceipt:
    admission_receipt_id: str
    plan_id: str
    phase: str
    dispatch_family_id: str
    logical_dispatch_id: str
    parent_logical_dispatch_id: str | None
    authorizing_event_id: str | None
    physical_door_id: str
    admission_attempt: int
    normalized_spec: str
    provider: str
    model: str
    family: str
    route_liveness_kind: str
    route_liveness_identity: str
    route_liveness_digest: str
    timeout_budget_s: float
    source_revision: str
    runtime_vector: Any
    manifest_identity: str
    seed_identity: str
    dependency_interpreter_identity: str
    semantic_dispatch_fingerprint: str
    projection_key: str
    projection_version: int
    reservation_event_id: str
    accepted_changed_precondition_event_id: str | None
    route_transition_event_id: str | None
    admitted_at: str
    execution_context: WorkerExecutionContextRef

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "execution_context"}
        result["execution_context"] = self.execution_context.to_dict()
        return result

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WorkerAdmissionReceipt":
        data = dict(payload)
        data["execution_context"] = WorkerExecutionContextRef.from_dict(data.pop("execution_context"))
        return cls(**data)


@dataclass(frozen=True)
class AdmissionRefusal:
    code: str
    reason: str
    plan_id: str
    phase: str
    logical_dispatch_id: str
    admission_attempt: int
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "kind": "admission_refusal", **{name: getattr(self, name) for name in self.__dataclass_fields__}}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AdmissionRefusal":
        data = dict(payload)
        if data.pop("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION or data.pop("kind", "admission_refusal") != "admission_refusal":
            raise ValueError("invalid admission refusal schema")
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown AdmissionRefusal fields: {sorted(unknown)}")
        return cls(**data)


@dataclass(frozen=True)
class LaunchResult:
    """Optional adapter result for closures that are not already outcomes."""
    accepted: bool
    value: Any = None


def _family(provider: str, model: str, selected_spec: str) -> str:
    lowered = f"{provider}/{model}/{selected_spec}".lower()
    if "deepseek" in lowered:
        return "deepseek"
    if "kimi" in lowered:
        return "kimi"
    if "glm" in lowered:
        return "glm"
    if "gpt" in lowered or provider in {"openai", "openai-codex"}:
        return "gpt"
    if "claude" in lowered or provider == "anthropic":
        return "claude"
    if "grok" in lowered or provider in {"xai", "grok"}:
        return "grok"
    return provider or "unknown"


def _extract_omp_models(value: Any) -> set[str]:
    models = value.get("models") if isinstance(value, Mapping) else value
    if isinstance(models, Mapping):
        models = list(models.values())
    if not isinstance(models, list):
        return set()
    result: set[str] = set()
    for item in models:
        if isinstance(item, str):
            result.add(item.removeprefix("omp:"))
            continue
        if not isinstance(item, Mapping):
            continue
        provider = item.get("provider") or item.get("provider_id") or item.get("vendor")
        model = item.get("model") or item.get("model_id") or item.get("id")
        if isinstance(provider, str) and isinstance(model, str):
            normalized_model = model.removeprefix("omp:")
            result.add(normalized_model if normalized_model.startswith(f"{provider}/") else f"{provider}/{normalized_model}")
        elif isinstance(model, str) and "/" in model:
            result.add(model.removeprefix("omp:"))
    return result


def resolve_omp_live_membership(provider: str, model: str, *, timeout_s: float = 10.0, runner: Callable[..., Any] | None = None) -> Mapping[str, Any]:
    """Require exact membership in the machine-readable OMP model surface."""
    run = runner or subprocess.run
    try:
        completed = run(["omp", "models", "--json"], capture_output=True, text=True, timeout=timeout_s, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise CliError("route_liveness_unavailable", f"omp models --json failed: {exc}") from exc
    if getattr(completed, "returncode", 1) != 0:
        raise CliError("route_liveness_unavailable", "omp models --json returned non-zero", extra={"stderr": getattr(completed, "stderr", "")})
    try:
        payload = json.loads(getattr(completed, "stdout", ""))
    except (TypeError, json.JSONDecodeError) as exc:
        raise CliError("route_liveness_invalid", "omp models --json returned invalid JSON") from exc
    normalized = f"{provider}/{model}"
    members = _extract_omp_models(payload)
    if normalized not in members:
        raise CliError("route_liveness_missing", f"OMP route {normalized!r} is not an exact live member", extra={"members": sorted(members)})
    digest = _digest(sorted(members))
    return {"kind": "omp_membership", "identity": normalized, "digest": digest, "provider": provider, "model": model, "observed_at": _now()}


def _default_native_liveness(agent: str, model: str) -> Mapping[str, Any]:
    binary = "claude" if agent in {"claude", "shannon"} else "codex" if agent == "codex" else agent
    path = shutil.which(binary)
    if not path:
        raise CliError("route_liveness_missing", f"native backend {binary!r} is not available")
    resolved = str(Path(path).resolve())
    try:
        stat = Path(resolved).stat()
        identity = f"{binary}:{resolved}:{stat.st_dev}:{stat.st_ino}:{stat.st_mtime_ns}:{stat.st_size}"
    except OSError as exc:
        raise CliError("route_liveness_unreadable", f"native backend proof is unreadable: {exc}") from exc
    return {"kind": "native_backend", "identity": identity, "digest": _digest(identity), "backend": binary, "provider": agent, "model": model, "observed_at": _now()}


def _validate_basic(request: WorkerAdmissionRequest) -> AdmissionRefusal | None:
    for name in (
        "plan_id", "phase", "dispatch_family_id", "logical_dispatch_id",
        "physical_door_id", "configured_spec", "selected_spec",
        "source_revision", "manifest_identity", "seed_identity",
        "dependency_interpreter_identity", "prompt_or_phase_input_identity",
        "authorized_route_identity",
        "projection_key",
    ):
        if not isinstance(getattr(request, name), str) or not getattr(request, name).strip():
            return _refusal(request, "invalid_request", f"{name} is required")
    if request.runtime_vector is None or request.runtime_vector == "" or request.runtime_vector == {}:
        return _refusal(request, "runtime_binding_missing", "runtime vector is required")
    try:
        configured = parse_agent_spec(request.configured_spec)
        selected = parse_agent_spec(request.selected_spec)
    except (CliError, ValueError) as exc:
        return _refusal(request, "invalid_spec", str(exc))
    if configured.agent != selected.agent and not request.configured_fallback_chain_identity:
        return _refusal(request, "invalid_spec", "configured and selected routes disagree")
    if isinstance(request.admission_attempt, bool) or request.admission_attempt < 1:
        return _refusal(request, "invalid_request", "admission_attempt must be positive")
    if isinstance(request.timeout_budget_s, bool) or not isinstance(request.timeout_budget_s, (int, float)) or request.timeout_budget_s <= 0:
        return _refusal(request, "invalid_timeout", "timeout budget must be finite and positive")
    if request.timeout_budget_s != request.timeout_budget_s or request.timeout_budget_s == float("inf"):
        return _refusal(request, "invalid_timeout", "timeout budget must be finite")
    return None


def require_production_worker_dispatch_runtime(request: WorkerAdmissionRequest | Mapping[str, Any] | None = None, **legacy_kwargs: Any) -> Any:
    """Admit one production logical dispatch, or preserve the old seed API.

    The no-argument/legacy form is intentionally retained for Batch-1 callers.
    Passing a ``WorkerAdmissionRequest`` selects the canonical typed admission
    path and returns ``WorkerAdmissionReceipt | SchedulingCondition | AdmissionRefusal``.
    """
    if request is None:
        from arnold_pipelines.megaplan.cloud.runtime_attestation import _legacy_require_production_worker_dispatch_runtime
        return _legacy_require_production_worker_dispatch_runtime(**legacy_kwargs)
    if not isinstance(request, WorkerAdmissionRequest):
        try:
            request = WorkerAdmissionRequest.from_dict(request)
        except (TypeError, ValueError) as exc:
            return _refusal(request, "invalid_request", f"invalid admission request: {exc}")
    basic = _validate_basic(request)
    if basic:
        return basic
    try:
        parsed = parse_agent_spec(request.selected_spec)
        agent = parsed.agent
        model = parsed.model or request.selected_spec
        if agent == "omp":
            from arnold_pipelines.megaplan.workers.omp import validate_omp_catalog_model
            provider, model_id = model.split("/", 1) if "/" in model else ("", "")
            if not provider or not model_id:
                return _refusal(request, "invalid_spec", "OMP selected spec lacks provider/model")
            normalized_model = validate_omp_catalog_model(provider, model_id)
            normalized_spec = f"omp:{normalized_model}"
            family = _family(provider, model_id, normalized_spec)
            liveness = (request.route_liveness_resolver or (lambda p, m, _s: resolve_omp_live_membership(p, m, timeout_s=min(10.0, float(request.timeout_budget_s)))))(provider, model_id, normalized_spec)
        else:
            normalized_spec = request.selected_spec.strip()
            provider = agent
            model = model
            family = _family(provider, model, normalized_spec)
            liveness = (request.route_liveness_resolver or (lambda p, m, _s: _default_native_liveness(agent, m)))(provider, model, normalized_spec)
        if request.authorized_route_identity not in {request.selected_spec.strip(), normalized_spec}:
            return _refusal(request, "route_authorization_invalid", "authorized route does not match selected route")
        if not isinstance(liveness, Mapping) or not liveness.get("identity") or not liveness.get("digest"):
            return _refusal(request, "route_liveness_invalid", "route resolver did not return positive proof")
        expected_kind = "omp_membership" if agent == "omp" else "native_backend"
        if liveness.get("kind") != expected_kind:
            return _refusal(request, "route_liveness_invalid", f"route proof kind must be {expected_kind}")
        if request.source_runtime_validator is not None:
            result = request.source_runtime_validator(request)
            if result is False or (isinstance(result, Mapping) and result.get("ok") is False):
                return _refusal(request, "source_runtime_invalid", "source/runtime validator rejected dispatch", result=result)
        for name in ("source_revision", "manifest_identity", "seed_identity", "dependency_interpreter_identity"):
            if not str(getattr(request, name)).strip():
                return _refusal(request, "runtime_binding_missing", f"{name} is required")
        cooldown_reader = request.cooldown_reader
        if cooldown_reader is None:
            from arnold_pipelines.megaplan.runtime.memory_headroom import memory_cooldown_wait_secs
            cooldown_reader = lambda root, phase, spec: memory_cooldown_wait_secs(root, phase, spec=spec)
        wait = float(cooldown_reader(request.ledger_root, request.phase, normalized_spec) or 0.0)
        if wait > 0:
            return SchedulingCondition(condition_id=_digest(("memory_cooldown", request.plan_id, request.phase, request.logical_dispatch_id, request.admission_attempt)), reason="memory_cooldown", plan_id=request.plan_id, phase=request.phase, spec=normalized_spec, dispatch_family_id=request.dispatch_family_id, logical_dispatch_id=request.logical_dispatch_id, admission_attempt=request.admission_attempt, retry_after_s=wait, observed_at=_now(), evidence={"reason": "same_phase_spec_cgroup_oom_cooldown", "retry_after_s": wait})
        memory_reader = request.memory_headroom_reader
        if memory_reader is None:
            from arnold_pipelines.megaplan.runtime.memory_headroom import classify_memory_headroom, read_cgroup_memory_snapshot
            memory_reader = lambda spec: classify_memory_headroom(spec, read_cgroup_memory_snapshot())
        memory = memory_reader(normalized_spec)
        if request.production_intent and (not isinstance(memory, Mapping) or memory.get("ok") is not True):
            return _refusal(request, "insufficient_memory_headroom", "positive memory headroom proof is required", memory=dict(memory or {}))
        fingerprint = semantic_dispatch_fingerprint(phase=request.phase, selected_spec=normalized_spec, model_family=family, prompt_or_phase_input_identity=request.prompt_or_phase_input_identity, source_revision=request.source_revision, runtime_vector=request.runtime_vector, manifest_identity=request.manifest_identity, seed_identity=request.seed_identity, dependency_interpreter_identity=request.dependency_interpreter_identity, timeout_policy_identity=_digest(request.timeout_budget_s), configured_fallback_chain_identity=request.configured_fallback_chain_identity, authorized_route_identity=request.authorized_route_identity)
        ledger = request.ledger or IncidentLedger(request.ledger_root)
        execution_context_identity = _digest({"plan_id": request.plan_id, "phase": request.phase, "logical_dispatch_id": request.logical_dispatch_id, "physical_door_id": request.physical_door_id, "semantic_dispatch_fingerprint": fingerprint})
        reserved = ledger.reserve(plan_id=request.plan_id, phase=request.phase, projection_key=request.projection_key, semantic_dispatch_fingerprint=fingerprint, logical_dispatch_id=request.logical_dispatch_id, dispatch_family_id=request.dispatch_family_id, physical_door_id=request.physical_door_id, expected_projection_version=request.expected_projection_version, changed_precondition_event_id=request.changed_precondition_event_id, selected_spec=normalized_spec, primary_spec=normalized_spec, configured_fallback_chain_identity=request.configured_fallback_chain_identity, execution_context_identity=execution_context_identity, actor="worker-admission")
        payload = reserved.get("payload", reserved) if isinstance(reserved, Mapping) else {}
        reservation_event_id = str(payload.get("event_id") or payload.get("reservation_event_id") or "")
        receipt_id = str(payload.get("admission_receipt_id") or ledger.derive_receipt(payload))
        context = WorkerExecutionContextRef(str(request.ledger_root or Path.cwd()), request.plan_id, request.phase, request.dispatch_family_id, request.logical_dispatch_id, receipt_id, fingerprint, normalized_spec, request.physical_door_id)
        return WorkerAdmissionReceipt(receipt_id, request.plan_id, request.phase, request.dispatch_family_id, request.logical_dispatch_id, request.parent_logical_dispatch_id, request.authorizing_event_id, request.physical_door_id, request.admission_attempt, normalized_spec, provider, model, family, str(liveness.get("kind")), str(liveness.get("identity")), str(liveness.get("digest")), float(request.timeout_budget_s), request.source_revision, request.runtime_vector, request.manifest_identity, request.seed_identity, request.dependency_interpreter_identity, fingerprint, request.projection_key, int(payload.get("expected_projection_version", 0)), reservation_event_id, request.changed_precondition_event_id, payload.get("event_id") if payload.get("event_type") == "provider_route_child_reserved" else None, _now(), context)
    except (CliError, ValueError, OSError) as exc:
        return _refusal(request, getattr(exc, "code", "admission_rejected"), str(exc))


def _worker_identity(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping) and all(key in value for key in ("host", "pid", "boot_id")):
        return value
    return {"host": socket.gethostname(), "pid": os.getpid(), "boot_id": "dispatch-process"}


def _normalize_outcome(value: Any, receipt: WorkerAdmissionReceipt, started: str, finished: str) -> DispatchOutcome:
    if isinstance(value, DispatchOutcome):
        if value.kind in {"no_launch", "unresolved_launch"}:
            return value
        return replace(value, plan_id=receipt.plan_id, phase=receipt.phase, dispatch_family_id=receipt.dispatch_family_id, logical_dispatch_id=receipt.logical_dispatch_id, admission_receipt_id=receipt.admission_receipt_id, semantic_dispatch_fingerprint=receipt.semantic_dispatch_fingerprint, selected_spec=receipt.normalized_spec, launch_state="accepted", started_at=value.started_at or started, finished_at=value.finished_at or finished, worker_identity=_worker_identity(value.worker_identity))
    if isinstance(value, LaunchResult):
        if not value.accepted:
            raise RuntimeError("launch operation did not positively establish no-acceptance")
        value = value.value
    if isinstance(value, Mapping) and "kind" in value:
        data = dict(value)
        data.update({"schema_version": 1, "plan_id": receipt.plan_id, "phase": receipt.phase, "dispatch_family_id": receipt.dispatch_family_id, "logical_dispatch_id": receipt.logical_dispatch_id, "admission_receipt_id": receipt.admission_receipt_id, "semantic_dispatch_fingerprint": receipt.semantic_dispatch_fingerprint, "selected_spec": receipt.normalized_spec, "launch_state": "accepted", "started_at": data.get("started_at") or started, "finished_at": data.get("finished_at") or finished, "worker_identity": _worker_identity(data.get("worker_identity"))})
        return DispatchOutcome.from_dict(data)
    return DispatchOutcome(kind="success", launch_state="accepted", plan_id=receipt.plan_id, phase=receipt.phase, dispatch_family_id=receipt.dispatch_family_id, logical_dispatch_id=receipt.logical_dispatch_id, admission_receipt_id=receipt.admission_receipt_id, semantic_dispatch_fingerprint=receipt.semantic_dispatch_fingerprint, selected_spec=receipt.normalized_spec, worker_identity=_worker_identity(getattr(value, "worker_identity", None)), started_at=started, finished_at=finished, success_payload=getattr(value, "payload", value))


def build_authorized_linked_child_request(
    parent: WorkerAdmissionRequest | Mapping[str, Any],
    *,
    selected_spec: str,
    logical_dispatch_id: str,
    authorizing_event_id: str,
    physical_door_id: str | None = None,
    dispatch_family_id: str | None = None,
    **changes: Any,
) -> WorkerAdmissionRequest:
    if isinstance(parent, Mapping) and parent.get("kind") in {"no_launch", "unresolved_launch"}:
        raise ValueError("linked child cannot be created from no-launch or unresolved parent")
    parent_terminal_from_outcome = parent.get("terminal_outcome_event_id") if isinstance(parent, Mapping) else None
    if not isinstance(parent, WorkerAdmissionRequest):
        parent_payload = dict(parent)
        # The terminal-parent marker is authorization context, not part of the
        # admission request wire schema.  Accept it on a request mapping while
        # keeping ``WorkerAdmissionRequest.from_dict`` strict.
        parent_payload.pop("terminal_outcome_event_id", None)
        parent = WorkerAdmissionRequest.from_dict(parent_payload)
    parent_terminal = changes.pop("parent_terminal_event_id", None) or parent_terminal_from_outcome
    if not parent_terminal:
        raise ValueError("linked child requires a canonical terminal parent event")
    if logical_dispatch_id == parent.logical_dispatch_id:
        raise ValueError("linked child must use a fresh logical dispatch id")
    if not authorizing_event_id:
        raise ValueError("linked child requires durable authorizing event")
    return replace(
        parent,
        logical_dispatch_id=logical_dispatch_id,
        parent_logical_dispatch_id=parent.logical_dispatch_id,
        authorizing_event_id=authorizing_event_id,
        physical_door_id=physical_door_id or parent.physical_door_id,
        dispatch_family_id=dispatch_family_id or parent.dispatch_family_id,
        selected_spec=selected_spec,
        configured_spec=changes.pop("configured_spec", selected_spec),
        changed_precondition_event_id=changes.pop("changed_precondition_event_id", None),
        admission_attempt=1,
        **changes,
    )


def reconcile_no_launch(
    receipt: WorkerAdmissionReceipt,
    *,
    evidence_event_ids: tuple[str, ...] | list[str],
    ledger: IncidentLedger,
    evidence_kind: str = "controlled_adapter",
    observed_at: str | None = None,
) -> DispatchOutcome:
    """Release a reservation only from positive persisted no-launch proof."""
    ids = tuple(str(item) for item in evidence_event_ids if str(item))
    if not ids:
        raise ValueError("no-launch reconciliation requires positive evidence IDs")
    when = observed_at or _now()
    reconciliation_id = _digest((receipt.reservation_event_id, "released_no_launch", ids))
    reconciliation = ReservationReconciled(
        reconciliation_id=reconciliation_id,
        plan_id=receipt.plan_id,
        phase=receipt.phase,
        projection_key=receipt.projection_key,
        logical_dispatch_id=receipt.logical_dispatch_id,
        admission_receipt_id=receipt.admission_receipt_id,
        reservation_event_id=receipt.reservation_event_id,
        semantic_dispatch_fingerprint=receipt.semantic_dispatch_fingerprint,
        resolution="released_no_launch",
        evidence_kind=evidence_kind,
        evidence_event_ids=ids,
        launch_state_identity="not_started",
        observed_at=when,
        recorded_at=when,
        actor="dispatch-with-admission",
    )
    event = ledger.reconcile_reservation(reconciliation)
    return DispatchOutcome(
        kind="no_launch",
        launch_state="not_started",
        plan_id=receipt.plan_id,
        phase=receipt.phase,
        dispatch_family_id=receipt.dispatch_family_id,
        logical_dispatch_id=receipt.logical_dispatch_id,
        admission_receipt_id=None,
        semantic_dispatch_fingerprint=None,
        selected_spec=receipt.normalized_spec,
        reconciliation_event_id=str((event.get("payload", event)).get("reconciliation_id") or reconciliation_id),
    )


def dispatch_with_admission(request: WorkerAdmissionRequest | Mapping[str, Any], launch: Callable[[WorkerExecutionContextRef], Any], *, gate: Callable[[WorkerAdmissionRequest | Mapping[str, Any]], Any] = require_production_worker_dispatch_runtime, ledger: IncidentLedger | None = None, clock: Callable[[], float] = time.monotonic, sleeper: Callable[[float], None] = time.sleep, deadline_s: float | None = None, return_worker: bool = False) -> Any:
    """Run one logical dispatch through admission and one controlled closure."""
    if not isinstance(request, WorkerAdmissionRequest):
        request = WorkerAdmissionRequest.from_dict(request)
    if ledger is not None:
        request = replace(request, ledger=ledger)
    started_clock = clock()
    deadline = started_clock + float(deadline_s if deadline_s is not None else request.timeout_budget_s)
    waited_s = 0.0
    attempt = request.admission_attempt
    while True:
        current = replace(request, admission_attempt=attempt)
        decision = gate(current)
        if isinstance(decision, SchedulingCondition):
            # Test and embedded runtimes may inject a sleeper that records a
            # wait without advancing the supplied clock.  Count the requested
            # wait as elapsed as well, otherwise a cooldown can spin forever.
            elapsed = max(clock() - started_clock, waited_s)
            remaining = deadline - started_clock - elapsed
            if remaining <= 0:
                return decision
            wait = min(float(decision.retry_after_s), remaining)
            if wait <= 0:
                attempt += 1
                continue
            sleeper(wait)
            waited_s += wait
            attempt += 1
            continue
        if isinstance(decision, AdmissionRefusal):
            return decision
        if not isinstance(decision, WorkerAdmissionReceipt):
            raise TypeError("admission gate returned an unsupported decision")
        from arnold_pipelines.megaplan.cloud.controlled_final_launch import ControlledFinalLaunch
        controlled = ControlledFinalLaunch(decision, ledger=ledger or current.ledger)
        try:
            started = _now()
            value = controlled.run(launch)
            finished = _now()
            outcome = _normalize_outcome(value, decision, controlled.accepted_started_at or started, controlled.accepted_finished_at or finished)
            if outcome.kind in {"no_launch", "unresolved_launch"}:
                return outcome
            active_ledger = ledger or current.ledger or IncidentLedger(current.ledger_root)
            execution_context_identity = _digest({"plan_id": decision.plan_id, "phase": decision.phase, "logical_dispatch_id": decision.logical_dispatch_id, "physical_door_id": decision.physical_door_id, "semantic_dispatch_fingerprint": decision.semantic_dispatch_fingerprint})
            terminal = active_ledger.append_terminal_outcome(outcome=outcome, reservation_event_id=decision.reservation_event_id, projection_key=decision.projection_key, physical_door_id=decision.physical_door_id, execution_context_identity=execution_context_identity, primary_spec=decision.normalized_spec, configured_fallback_chain_identity=current.configured_fallback_chain_identity)
            terminal_outcome = replace(outcome, terminal_outcome_event_id=str((terminal.get("payload", terminal)).get("terminal_outcome_id")))
            try:
                controlled.close()
            except Exception:
                # Terminal projection is canonical and already committed.  A
                # post-terminal bookkeeping marker must not erase that fact or
                # turn a successful worker result into an unresolved launch.
                pass
            return value if return_worker else terminal_outcome
        except Exception:
            # ControlledFinalLaunch only normalizes a pre-entry exception. All
            # post-entry uncertainty is held and never blindly redispatched.
            return DispatchOutcome(kind="unresolved_launch", launch_state="ambiguous", plan_id=decision.plan_id, phase=decision.phase, dispatch_family_id=decision.dispatch_family_id, logical_dispatch_id=decision.logical_dispatch_id, admission_receipt_id=None, semantic_dispatch_fingerprint=None, selected_spec=decision.normalized_spec, reconciliation_event_id=None)
__all__ = ["AdmissionRefusal", "LaunchResult", "WorkerAdmissionReceipt", "WorkerAdmissionRequest", "WorkerExecutionContextRef", "build_authorized_linked_child_request", "dispatch_with_admission", "reconcile_no_launch", "require_production_worker_dispatch_runtime", "resolve_omp_live_membership"]
