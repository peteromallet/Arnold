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
        fingerprint = values["semantic_dispatch_fingerprint"]
        if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
            raise ValueError("worker execution context fingerprint is not canonical")
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
    production_intent: bool = True

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
    # These fields are intentionally explicit.  A completed return value does
    # not prove that a worker was accepted; the launcher must carry the
    # identity observed at the real process boundary into the adapter.
    worker_identity: Mapping[str, Any] | None = None
    started_at: str | None = None
    finished_at: str | None = None


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


def _extract_native_models(value: Any) -> set[str]:
    """Extract exact model slugs from the installed native backend catalog."""
    models = value.get("models") if isinstance(value, Mapping) else value
    if not isinstance(models, list):
        return set()
    result: set[str] = set()
    for item in models:
        if isinstance(item, str):
            result.add(item)
        elif isinstance(item, Mapping):
            slug = item.get("slug") or item.get("id") or item.get("model")
            if isinstance(slug, str) and slug.strip():
                result.add(slug.strip())
    return result


def _default_native_liveness(agent: str, model: str, *, runner: Callable[..., Any] | None = None) -> Mapping[str, Any]:
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
    # Executable presence is only a locator, not proof that this route can
    # construct the requested model.  Use the backend's installed, machine-
    # generated catalog.  ``debug models`` is a catalog read, not a generation
    # request, and unlike ``exec --model X --help`` it cannot report success for
    # an arbitrary opaque model string.
    run = runner or subprocess.run
    try:
        probe = run(
            [resolved, "debug", "models"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CliError("route_liveness_unavailable", f"native model probe failed: {exc}") from exc
    if probe.returncode != 0:
        raise CliError(
            "route_liveness_unavailable",
            f"native backend model catalog failed for {model!r}",
            extra={"backend": binary, "stderr": (probe.stderr or "")[-1000:]},
        )
    try:
        catalog = json.loads(getattr(probe, "stdout", ""))
    except (TypeError, json.JSONDecodeError) as exc:
        raise CliError("route_liveness_invalid", "native backend model catalog was not valid JSON") from exc
    models = _extract_native_models(catalog)
    if model not in models:
        raise CliError(
            "route_liveness_missing",
            f"native backend model {model!r} is not an exact installed catalog member",
            extra={"backend": binary, "models": sorted(models)},
        )
    proof = {"binary": identity, "model": model, "catalog": sorted(models), "probe": "debug models"}
    return {"kind": "native_backend", "identity": _digest(proof), "digest": _digest(proof), "backend": binary, "provider": agent, "model": model, "observed_at": _now(), "authoritative": True}


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


def _validate_authoritative_runtime_bindings(request: WorkerAdmissionRequest) -> AdmissionRefusal | None:
    """Compare production identity claims with machine-owned observations.

    Transport fields are useful for correlation, but a caller must not be able
    to invent a source revision or point a dispatch at a different seed.  Test
    and embedded callers may use a small runtime vector; strict comparison is
    enabled whenever the vector carries real provenance or the production
    seed/manifest selectors are present.
    """
    vector = request.runtime_vector if isinstance(request.runtime_vector, Mapping) else {}
    if request.production_intent:
        if not isinstance(request.runtime_vector, Mapping):
            return _refusal(request, "runtime_binding_missing", "production runtime vector must be a mapping")
        try:
            from arnold_pipelines.megaplan.cloud.runtime_provenance import runtime_provenance
            observed = runtime_provenance()
        except Exception as exc:
            return _refusal(request, "source_runtime_unavailable", f"authoritative runtime provenance unavailable: {exc}")
        if not vector.get("source_revision") or str(vector.get("source_revision")) != str(observed.get("source_revision") or ""):
            return _refusal(request, "source_runtime_invalid", "source revision is not the executing revision")
        if request.source_revision != observed.get("source_revision"):
            return _refusal(request, "source_runtime_invalid", "request source revision is not authoritative")
        interpreter = str(Path(os.sys.executable).resolve())
        if request.dependency_interpreter_identity != interpreter:
            return _refusal(request, "runtime_binding_invalid", "dependency interpreter is not the executing interpreter")
    seed_selector = os.environ.get("MEGAPLAN_RUNTIME_LAUNCH_SEED")
    if request.production_intent and not seed_selector:
        return _refusal(request, "runtime_binding_missing", "production launch seed selector is missing")
    if seed_selector:
        path = Path(seed_selector)
        if not path.is_file():
            return _refusal(request, "runtime_binding_invalid", "configured launch seed is unreadable")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if request.seed_identity != actual:
            return _refusal(request, "runtime_binding_invalid", "seed identity does not match configured launch seed")
    manifest_selector = os.environ.get("ARNOLD_RUNTIME_MANIFEST")
    if request.production_intent and not manifest_selector:
        return _refusal(request, "runtime_binding_missing", "production runtime manifest selector is missing")
    if manifest_selector:
        path = Path(manifest_selector)
        if not path.is_file():
            return _refusal(request, "runtime_binding_invalid", "configured runtime manifest is unreadable")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if request.manifest_identity != actual:
            return _refusal(request, "runtime_binding_invalid", "manifest identity does not match configured runtime manifest")
    if request.production_intent and (not request.seed_identity or not request.manifest_identity):
        return _refusal(request, "runtime_binding_missing", "production seed and manifest identities are required")
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
    authoritative = _validate_authoritative_runtime_bindings(request)
    if authoritative:
        return authoritative
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
            # A caller hook may provide an early diagnostic, but it cannot
            # mint native admission.  The canonical probe below always runs
            # against the installed executable and the exact selected model.
            if request.route_liveness_resolver is not None:
                observed = request.route_liveness_resolver(provider, model, normalized_spec)
                if not isinstance(observed, Mapping) or not observed.get("identity") or not observed.get("digest"):
                    return _refusal(request, "route_liveness_invalid", "route resolver did not return positive proof")
            liveness = _default_native_liveness(agent, model)
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
        return WorkerAdmissionReceipt(receipt_id, request.plan_id, request.phase, request.dispatch_family_id, request.logical_dispatch_id, request.parent_logical_dispatch_id, request.authorizing_event_id, request.physical_door_id, request.admission_attempt, normalized_spec, provider, model, family, str(liveness.get("kind")), str(liveness.get("identity")), str(liveness.get("digest")), float(request.timeout_budget_s), request.source_revision, request.runtime_vector, request.manifest_identity, request.seed_identity, request.dependency_interpreter_identity, fingerprint, request.projection_key, int(payload.get("expected_projection_version", 0)), reservation_event_id, request.changed_precondition_event_id, payload.get("event_id") if payload.get("event_type") == "provider_route_child_reserved" else None, _now(), context, request.production_intent)
    except (CliError, ValueError, OSError) as exc:
        return _refusal(request, getattr(exc, "code", "admission_rejected"), str(exc))


def _worker_identity(value: Any, *, require_verified: bool = False) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(key in value for key in ("host", "pid", "boot_id")):
        raise ValueError("accepted outcome requires launcher-provided worker identity")
    if (
        not isinstance(value.get("host"), str) or not value.get("host")
        or not isinstance(value.get("boot_id"), str) or not value.get("boot_id")
        or isinstance(value.get("pid"), bool) or not isinstance(value.get("pid"), int)
        or value.get("pid") <= 0
    ):
        raise ValueError("accepted outcome worker identity is malformed")
    if require_verified:
        if value.get("verified") is not True:
            raise ValueError("production worker identity is not verified")
        if not isinstance(value.get("process_start_identity"), str) or not value.get("process_start_identity"):
            raise ValueError("production worker identity lacks process start identity")
        if value.get("host") != os.uname().nodename:
            raise ValueError("production worker identity host does not match this machine")
        # A live PID must still be the process that was attested.  Completed
        # managed workers are allowed to disappear; their durable manifest's
        # process_start_identity remains the authoritative terminal proof.
        try:
            os.kill(value["pid"], 0)
            observed_start = ""
            proc_stat = Path(f"/proc/{value['pid']}/stat")
            if proc_stat.is_file():
                try:
                    observed_start = proc_stat.read_text(encoding="utf-8").split()[21]
                except (OSError, IndexError):
                    observed_start = ""
            if not observed_start:
                try:
                    observed = subprocess.run(
                        ["ps", "-p", str(value["pid"]), "-o", "lstart="],
                        check=False, capture_output=True, text=True, timeout=2,
                    )
                    observed_start = observed.stdout.strip() if observed.returncode == 0 else ""
                except (OSError, subprocess.SubprocessError):
                    observed_start = ""
            if observed_start and observed_start != value["process_start_identity"]:
                raise ValueError("production worker process start identity mismatch")
        except ProcessLookupError:
            pass
        except PermissionError:
            raise ValueError("production worker identity cannot be inspected")
    return dict(value)


def _normalize_outcome(value: Any, receipt: WorkerAdmissionReceipt, started: str, finished: str) -> DispatchOutcome:
    if isinstance(value, DispatchOutcome):
        # A closure is invoked only after the adapter has persisted ``entered``.
        # It therefore cannot truthfully return ``no_launch``: that state must
        # be produced by the pre-launch scheduler or by explicit reconciliation
        # of a persisted not_started marker.  Treating it as a successful
        # closure would serialize an accepted marker and a no-launch result for
        # the same reservation.
        if value.kind in {"no_launch", "unresolved_launch"}:
            raise ValueError("final launch closure returned a scheduling outcome after entry")
        normalized = replace(value, plan_id=receipt.plan_id, phase=receipt.phase, dispatch_family_id=receipt.dispatch_family_id, logical_dispatch_id=receipt.logical_dispatch_id, admission_receipt_id=receipt.admission_receipt_id, semantic_dispatch_fingerprint=receipt.semantic_dispatch_fingerprint, selected_spec=receipt.normalized_spec, launch_state="accepted", started_at=value.started_at or started, finished_at=value.finished_at or finished, worker_identity=_worker_identity(value.worker_identity, require_verified=receipt.production_intent))
        # Re-run the strict constructor after transport normalization.  This
        # keeps success/provider/disposition payloads lossless while rejecting
        # a closure that smuggles incompatible fields under a different kind.
        return DispatchOutcome.from_dict(normalized.to_dict())
    launch_metadata: LaunchResult | None = None
    if isinstance(value, LaunchResult):
        if not value.accepted:
            raise RuntimeError("launch operation did not positively establish no-acceptance")
        launch_metadata = value
        value = value.value
    if isinstance(value, Mapping) and "kind" in value:
        data = dict(value)
        data.update({"schema_version": 1, "plan_id": receipt.plan_id, "phase": receipt.phase, "dispatch_family_id": receipt.dispatch_family_id, "logical_dispatch_id": receipt.logical_dispatch_id, "admission_receipt_id": receipt.admission_receipt_id, "semantic_dispatch_fingerprint": receipt.semantic_dispatch_fingerprint, "selected_spec": receipt.normalized_spec, "launch_state": "accepted", "started_at": data.get("started_at") or (launch_metadata.started_at if launch_metadata else None) or started, "finished_at": data.get("finished_at") or (launch_metadata.finished_at if launch_metadata else None) or finished, "worker_identity": _worker_identity(data.get("worker_identity") or (launch_metadata.worker_identity if launch_metadata else None), require_verified=receipt.production_intent)})
        return DispatchOutcome.from_dict(data)
    # The native doors historically return the compatibility tuple
    # ``(WorkerResult, agent, mode, refreshed)``.  Preserve the worker payload
    # as an explicit success payload rather than collapsing it to ``str`` or
    # dropping it while building the canonical terminal event.
    if isinstance(value, tuple) and len(value) == 4:
        worker, agent, mode, refreshed = value
        payload = getattr(worker, "payload", worker)
        return DispatchOutcome(kind="success", launch_state="accepted", plan_id=receipt.plan_id, phase=receipt.phase, dispatch_family_id=receipt.dispatch_family_id, logical_dispatch_id=receipt.logical_dispatch_id, admission_receipt_id=receipt.admission_receipt_id, semantic_dispatch_fingerprint=receipt.semantic_dispatch_fingerprint, selected_spec=receipt.normalized_spec, worker_identity=_worker_identity(getattr(worker, "worker_identity", None) or (launch_metadata.worker_identity if launch_metadata else None), require_verified=receipt.production_intent), started_at=(launch_metadata.started_at if launch_metadata else None) or started, finished_at=(launch_metadata.finished_at if launch_metadata else None) or finished, success_payload={"worker_payload": payload, "agent": agent, "mode": mode, "refreshed": refreshed})
    if isinstance(value, Mapping) and all(key in value for key in ("host", "pid", "boot_id")):
        return DispatchOutcome(kind="success", launch_state="accepted", plan_id=receipt.plan_id, phase=receipt.phase, dispatch_family_id=receipt.dispatch_family_id, logical_dispatch_id=receipt.logical_dispatch_id, admission_receipt_id=receipt.admission_receipt_id, semantic_dispatch_fingerprint=receipt.semantic_dispatch_fingerprint, selected_spec=receipt.normalized_spec, worker_identity=_worker_identity(value, require_verified=receipt.production_intent), started_at=started, finished_at=finished, success_payload=dict(value))
    # Integers (managed-command return codes), None, booleans, and arbitrary
    # objects are not typed worker outcomes.  Requiring a LaunchResult or a
    # canonical DispatchOutcome prevents a successful return code from being
    # serialized as an accepted worker launch.
    if not launch_metadata:
        raise ValueError("final launch must return a typed outcome with worker identity")
    if isinstance(value, (int, float, bool, str, bytes, type(None))):
        raise ValueError("primitive launch results are not typed worker outcomes")
    return DispatchOutcome(kind="success", launch_state="accepted", plan_id=receipt.plan_id, phase=receipt.phase, dispatch_family_id=receipt.dispatch_family_id, logical_dispatch_id=receipt.logical_dispatch_id, admission_receipt_id=receipt.admission_receipt_id, semantic_dispatch_fingerprint=receipt.semantic_dispatch_fingerprint, selected_spec=receipt.normalized_spec, worker_identity=_worker_identity(getattr(value, "worker_identity", None) or launch_metadata.worker_identity, require_verified=receipt.production_intent), started_at=launch_metadata.started_at or started, finished_at=launch_metadata.finished_at or finished, success_payload=getattr(value, "payload", value))


def build_authorized_linked_child_request(
    parent: WorkerAdmissionRequest | Mapping[str, Any],
    *,
    selected_spec: str,
    logical_dispatch_id: str,
    authorizing_event_id: str,
    physical_door_id: str | None = None,
    dispatch_family_id: str | None = None,
    ledger: IncidentLedger | None = None,
    **changes: Any,
) -> WorkerAdmissionRequest:
    if isinstance(parent, Mapping) and parent.get("kind") in {"no_launch", "unresolved_launch"}:
        raise ValueError("linked child cannot be created from no-launch or unresolved parent")
    if isinstance(parent, Mapping):
        parent_kind = parent.get("kind")
        if parent_kind is not None and parent_kind not in {
            "success", "ordinary_terminal_failure", "provider_exhausted", "worker_disposition",
        }:
            raise ValueError("linked child requires a canonical terminal parent")
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
    if parent.production_intent and ledger is None:
        raise ValueError("production linked child requires the authoritative ledger")
    if ledger is not None:
        # The marker is only a transport hint.  When the authoritative ledger
        # is available, reread both sides of the authorization and bind the
        # child to the exact parent context before returning a request.
        records = [record.get("payload", {}) for record in ledger.read_nbf_events()]
        terminal = next(
            (record for record in records
             if record.get("event_type") == "worker_terminal_outcome"
             and record.get("terminal_outcome_id") == parent_terminal),
            None,
        )
        if terminal is None or terminal.get("outcome_kind") not in {
            "success", "ordinary_terminal_failure", "provider_exhausted", "worker_disposition",
        }:
            raise ValueError("linked child parent marker is not a canonical terminal")
        for name, expected in (
            ("plan_id", parent.plan_id),
            ("phase", parent.phase),
            ("dispatch_family_id", parent.dispatch_family_id),
            ("logical_dispatch_id", parent.logical_dispatch_id),
            ("physical_door_id", parent.physical_door_id),
        ):
            if terminal.get(name) != expected:
                raise ValueError(f"linked child parent context mismatch: {name}")
        authorizer = next(
            (record for record in records if record.get("event_id") == authorizing_event_id),
            None,
        )
        if authorizer is None or authorizer.get("event_type") not in {
            "changed_precondition", "provider_recovery_verified", "authorization_granted",
        }:
            raise ValueError("linked child authorizer is not a persisted canonical event")
        bound_parent = (
            authorizer.get("parent_terminal_event_id")
            or authorizer.get("terminal_outcome_event_id")
            or authorizer.get("parent_event_id")
        )
        if not bound_parent or bound_parent != parent_terminal:
            raise ValueError("linked child authorizer is bound to a different parent")
        # The authorizer must carry the complete canonical context; a bare
        # event ID is not authority for a provider/fallback child.
        for name, expected in (
            ("plan_id", parent.plan_id),
            ("phase", parent.phase),
            ("parent_logical_dispatch_id", parent.logical_dispatch_id),
            ("parent_dispatch_family_id", parent.dispatch_family_id),
            ("parent_physical_door_id", parent.physical_door_id),
        ):
            if authorizer.get(name) != expected:
                raise ValueError(f"linked child authorizer context mismatch: {name}")
        if terminal.get("admission_receipt_id") is None or terminal.get("semantic_dispatch_fingerprint") is None:
            raise ValueError("linked child parent lacks canonical receipt/fingerprint context")
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
    if len(ids) != len(set(ids)):
        raise ValueError("no-launch reconciliation evidence IDs must be unique")
    # Inspect the complete reservation history, not merely the IDs supplied by
    # the caller.  A caller must not hide an entered/accepted marker by citing
    # only the earlier not_started event; doing so would release a reservation
    # that may already have created a worker.
    history = ledger.read_nbf_events()
    reservation_events = [
        record.get("payload", {}) for record in history
        if record.get("payload", {}).get("reservation_event_id") == receipt.reservation_event_id
        or record.get("payload", {}).get("event_id") == receipt.reservation_event_id
    ]
    states = {
        item.get("launch_state_identity")
        for item in reservation_events
        if item.get("event_type") == "controlled_adapter_state"
    }
    if states & {"entered", "accepted", "closed", "ambiguous"}:
        raise ValueError("no-launch reconciliation conflicts with persisted launch evidence")
    cited = {
        item.get("event_id")
        for item in reservation_events
        if item.get("event_type") == "controlled_adapter_state"
        and item.get("admission_receipt_id") == receipt.admission_receipt_id
        and item.get("physical_door_id") == receipt.physical_door_id
        and item.get("launch_state_identity") == "not_started"
    }
    if not set(ids).issubset(cited):
        raise ValueError("no-launch reconciliation requires bound not_started adapter evidence")
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


def dispatch_with_admission(request: WorkerAdmissionRequest | Mapping[str, Any], launch: Callable[[WorkerExecutionContextRef], Any], *, gate: Callable[[WorkerAdmissionRequest | Mapping[str, Any]], Any] | None = None, ledger: IncidentLedger | None = None, clock: Callable[[], float] = time.monotonic, sleeper: Callable[[float], None] = time.sleep, deadline_s: float | None = None, return_worker: bool = False) -> Any:
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
        # Admission is a trust boundary.  Keep the legacy ``gate`` keyword
        # source-compatible for callers/tests, but never let a caller replace
        # the production authority with a predicate that can mint a receipt or
        # skip source/runtime/liveness checks.  Test seams belong on the typed
        # request (resolver/readers), which the canonical authority consumes.
        decision = require_production_worker_dispatch_runtime(current)
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
        active_ledger = ledger or current.ledger or IncidentLedger(current.ledger_root)
        # A scheduler may establish positive no-launch evidence before the
        # final closure is entered.  Resolve that reservation through the same
        # canonical reconciliation door; callers cannot simply return a marker
        # that bypasses the ledger.
        pre_entry_evidence = getattr(launch, "no_launch_evidence", None)
        if pre_entry_evidence is not None:
            evidence_ids = tuple(str(item) for item in pre_entry_evidence if str(item))
            return reconcile_no_launch(decision, evidence_event_ids=evidence_ids, ledger=active_ledger)
        try:
            started = _now()
            value = controlled.run(launch)
            finished = _now()
            outcome = _normalize_outcome(value, decision, controlled.accepted_started_at or started, controlled.accepted_finished_at or finished)
            if outcome.kind in {"no_launch", "unresolved_launch"}:
                # _normalize_outcome rejects this after entry.  Retain the
                # defensive branch for future outcome kinds and fail closed.
                return DispatchOutcome(kind="unresolved_launch", launch_state="ambiguous", plan_id=decision.plan_id, phase=decision.phase, dispatch_family_id=decision.dispatch_family_id, logical_dispatch_id=decision.logical_dispatch_id, admission_receipt_id=None, semantic_dispatch_fingerprint=None, selected_spec=decision.normalized_spec, reconciliation_event_id=None)
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
            if controlled.state == "not_started":
                evidence_ids = tuple(
                    record.get("payload", {}).get("event_id")
                    for record in active_ledger.read_nbf_events()
                    if record.get("payload", {}).get("event_type") == "controlled_adapter_state"
                    and record.get("payload", {}).get("reservation_event_id") == decision.reservation_event_id
                    and record.get("payload", {}).get("launch_state_identity") == "not_started"
                )
                if evidence_ids:
                    return reconcile_no_launch(decision, evidence_event_ids=evidence_ids, ledger=active_ledger)
            return DispatchOutcome(kind="unresolved_launch", launch_state="ambiguous", plan_id=decision.plan_id, phase=decision.phase, dispatch_family_id=decision.dispatch_family_id, logical_dispatch_id=decision.logical_dispatch_id, admission_receipt_id=None, semantic_dispatch_fingerprint=None, selected_spec=decision.normalized_spec, reconciliation_event_id=None)
__all__ = ["AdmissionRefusal", "LaunchResult", "WorkerAdmissionReceipt", "WorkerAdmissionRequest", "WorkerExecutionContextRef", "build_authorized_linked_child_request", "dispatch_with_admission", "reconcile_no_launch", "require_production_worker_dispatch_runtime", "resolve_omp_live_membership"]
