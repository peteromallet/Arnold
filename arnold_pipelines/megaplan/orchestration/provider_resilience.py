"""Small, typed provider-resilience seam used by the shared worker door.

NBF-06 deliberately keeps policy beside the existing admission/terminal
seams.  This module contains only pure identity/decision helpers and a thin
post-terminal observation adapter; the :class:`IncidentLedger` remains the
durable authority for reservations, terminals, probes, and replay.

The implementation is intentionally conservative.  A provider route is
never selected from prose or an uncommitted worker result, and no policy
decision can authorize an execute retry.  Callers which need a route child
must continue through the existing linked-child admission API.
"""

from __future__ import annotations

import hashlib
import json
import struct
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

from arnold_pipelines.megaplan.fallback_chains import (
    FallbackSpecChain,
    is_cross_family_retryable_classification,
    provider_family,
)
from arnold_pipelines.megaplan.incident.schema import ProviderFailureKey
from arnold_pipelines.megaplan.orchestration.phase_result import (
    DispatchOutcome,
    SchedulingCondition,
)


CHAIN_MAGIC = b"NBF06-CHAIN-ID-V1"
CHAIN_CODEC_VERSION = "v1"
_U64 = struct.Struct(">Q")
_SHA256_HEX_LEN = 64
_PROVIDER_FAILURE_CLASSES = frozenset({"availability", "idle_timeout"})


def _sha256_bytes(value: bytes) -> bytes:
    return hashlib.sha256(value).digest()


def _digest(value: Any) -> str:
    import json

    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    normalized = unicodedata.normalize("NFC", value)
    if "\x00" in normalized:
        raise ValueError(f"{field_name} cannot contain NUL")
    normalized.encode("utf-8")
    return normalized


def _bytes(value: Any, *, field_name: str) -> bytes:
    if isinstance(value, bytearray):
        value = bytes(value)
    if isinstance(value, str):
        value = value.encode("utf-8")
    if not isinstance(value, bytes):
        raise ValueError(f"{field_name} must be bytes or UTF-8 text")
    if b"\x00" in value:
        raise ValueError(f"{field_name} cannot contain NUL")
    try:
        value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{field_name} must be valid UTF-8") from exc
    return value


def _field(value: str) -> bytes:
    encoded = _text(value, field_name="chain field").encode("utf-8")
    return _U64.pack(len(encoded)) + encoded


def _specs(value: FallbackSpecChain | Sequence[str] | str) -> tuple[str, ...]:
    chain = value if isinstance(value, FallbackSpecChain) else FallbackSpecChain.from_value(value, path="normalized_specs")
    return tuple(_text(spec, field_name="normalized_spec") for spec in chain.specs)


def serialize_configured_fallback_chain_v1(
    *,
    domain: str,
    phase: str,
    parser_version: str,
    origin_bytes: bytes | str,
    normalized_specs: FallbackSpecChain | Sequence[str] | str,
) -> bytes:
    """Serialize the canonical framed CHAIN V1 identity bytes.

    The public codec uses keyword-only arguments so a caller cannot silently
    swap the origin and the normalized route list.  The origin bytes are
    retained verbatim (after UTF-8 validation); the digest in the frame is
    always recomputed from those bytes.
    """

    domain_text = _text(domain, field_name="domain")
    phase_text = _text(phase, field_name="phase")
    parser_text = _text(parser_version, field_name="parser_version")
    origin = _bytes(origin_bytes, field_name="origin_bytes")
    specs = _specs(normalized_specs)
    encoded = bytearray(CHAIN_MAGIC)
    encoded.extend(_field(domain_text))
    encoded.extend(_field(phase_text))
    encoded.extend(_field(parser_text))
    encoded.extend(_U64.pack(len(origin)))
    encoded.extend(origin)
    encoded.extend(_sha256_bytes(origin))
    encoded.extend(_U64.pack(len(specs)))
    for spec in specs:
        encoded.extend(_field(spec))
    return bytes(encoded)


def _read_field(raw: bytes, offset: int, *, field_name: str) -> tuple[str, int]:
    length, offset = _read_u64(raw, offset, field_name=f"{field_name}.length")
    end = offset + length
    if end > len(raw):
        raise ValueError(f"truncated {field_name}")
    value = raw[offset:end]
    if b"\x00" in value:
        raise ValueError(f"{field_name} contains NUL")
    try:
        text = unicodedata.normalize("NFC", value.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError(f"{field_name} is not valid UTF-8") from exc
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text, end


def _read_u64(raw: bytes, offset: int, *, field_name: str) -> tuple[int, int]:
    end = offset + _U64.size
    if end > len(raw):
        raise ValueError(f"truncated {field_name}")
    return _U64.unpack(raw[offset:end])[0], end


def deserialize_configured_fallback_chain_v1(raw: bytes | bytearray) -> dict[str, Any]:
    """Decode CHAIN V1 and reject legacy JSON or non-canonical bytes."""

    if isinstance(raw, bytearray):
        raw = bytes(raw)
    if not isinstance(raw, bytes) or not raw.startswith(CHAIN_MAGIC):
        raise ValueError("configured fallback chain is not CHAIN V1")
    offset = len(CHAIN_MAGIC)
    domain, offset = _read_field(raw, offset, field_name="domain")
    phase, offset = _read_field(raw, offset, field_name="phase")
    parser_version, offset = _read_field(raw, offset, field_name="parser_version")
    origin_length, offset = _read_u64(raw, offset, field_name="origin_bytes.length")
    origin_end = offset + origin_length
    if origin_end + 32 > len(raw):
        raise ValueError("truncated origin_bytes")
    origin = raw[offset:origin_end]
    try:
        unicodedata.normalize("NFC", origin.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("origin_bytes is not valid UTF-8") from exc
    offset = origin_end
    origin_digest = raw[offset:offset + 32]
    offset += 32
    if origin_digest != _sha256_bytes(origin):
        raise ValueError("origin_bytes digest mismatch")
    spec_count, offset = _read_u64(raw, offset, field_name="spec_count")
    if spec_count < 1:
        raise ValueError("configured fallback chain must contain at least one spec")
    specs: list[str] = []
    for index in range(spec_count):
        spec, offset = _read_field(raw, offset, field_name=f"normalized_specs[{index}]")
        specs.append(spec)
    if offset != len(raw):
        raise ValueError("configured fallback chain has trailing bytes")
    # Re-encode to enforce NFC/length canonicality, including the scalar
    # one-spec representation.  A decoder must not normalize a forged frame
    # into a different identity.
    canonical = serialize_configured_fallback_chain_v1(
        domain=domain,
        phase=phase,
        parser_version=parser_version,
        origin_bytes=origin,
        normalized_specs=specs,
    )
    if canonical != raw:
        raise ValueError("configured fallback chain is not canonical")
    return {
        "domain": domain,
        "phase": phase,
        "parser_version": parser_version,
        "origin_bytes": origin,
        "origin_digest": origin_digest,
        "normalized_specs": tuple(specs),
        "bytes": raw,
    }


def derive_configured_fallback_chain_identity(
    *,
    domain: str,
    phase: str,
    parser_version: str,
    origin_bytes: bytes | str,
    normalized_specs: FallbackSpecChain | Sequence[str] | str,
) -> bytes:
    """Return the raw 32-byte identity of canonical CHAIN V1 bytes."""

    return _sha256_bytes(
        serialize_configured_fallback_chain_v1(
            domain=domain,
            phase=phase,
            parser_version=parser_version,
            origin_bytes=origin_bytes,
            normalized_specs=normalized_specs,
        )
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _copy_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True)
class ProviderLedgerView:
    """Immutable provider state snapshot consumed by pure route selection."""

    projection_version: int
    active_provider_failure_key: str | None = None
    observation_streak: int = 0
    provider_streaks: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    reservations: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    terminals: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    changed_preconditions: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    provider_observations: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    provider_probe_leases: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    provider_probe_results: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    provider_probe_closures: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    provider_recovery_proofs: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    probe_status: str = "none"

    def __post_init__(self) -> None:
        if isinstance(self.projection_version, bool) or self.projection_version < 0:
            raise ValueError("provider ledger projection version must be non-negative")
        if isinstance(self.observation_streak, bool) or self.observation_streak < 0:
            raise ValueError("provider observation streak must be non-negative")
        object.__setattr__(self, "provider_streaks", _copy_mapping(self.provider_streaks))
        object.__setattr__(self, "reservations", _copy_mapping(self.reservations))
        object.__setattr__(self, "terminals", _copy_mapping(self.terminals))
        object.__setattr__(self, "changed_preconditions", _copy_mapping(self.changed_preconditions))
        object.__setattr__(self, "provider_observations", _copy_mapping(self.provider_observations))
        object.__setattr__(self, "provider_probe_leases", _copy_mapping(self.provider_probe_leases))
        object.__setattr__(self, "provider_probe_results", _copy_mapping(self.provider_probe_results))
        object.__setattr__(self, "provider_probe_closures", _copy_mapping(self.provider_probe_closures))
        object.__setattr__(self, "provider_recovery_proofs", _copy_mapping(self.provider_recovery_proofs))
        if self.probe_status not in {"none", "leased", "passed", "failed"}:
            raise ValueError("provider probe status is outside its finite state set")

    @classmethod
    def from_projection(cls, projection: Mapping[str, Any]) -> "ProviderLedgerView":
        return cls(
            projection_version=int(projection.get("projection_version", 0)),
            active_provider_failure_key=projection.get("active_provider_failure_key"),
            observation_streak=int(projection.get("observation_streak", 0)),
            provider_streaks=projection.get("provider_streaks", {}),
            reservations=projection.get("reservations", {}),
            terminals=projection.get("terminals", {}),
            changed_preconditions=projection.get("changed_preconditions", {}),
            provider_observations=projection.get("provider_observations", {}),
            provider_probe_leases=projection.get("provider_probe_leases", {}),
            provider_probe_results=projection.get("provider_probe_results", {}),
            provider_probe_closures=projection.get("provider_probe_closures", {}),
            provider_recovery_proofs=projection.get("provider_recovery_proofs", {}),
            probe_status=str(projection.get("probe_status", "none")),
        )

    @classmethod
    def from_ledger(cls, ledger: Any) -> "ProviderLedgerView":
        return cls.from_projection(ledger.projection())


@dataclass(frozen=True)
class ProviderRouteDecision:
    """Closed, side-effect-free route decision.

    ``kind`` is intentionally a finite string union.  Applying a decision is
    a separate operation and therefore cannot accidentally append an event
    while policy is reading the immutable view.
    """

    kind: str
    phase: str
    logical_dispatch_id: str
    selected_spec: str
    provider_failure_key: str | None = None
    retry_after_s: float = 0.0
    cause_event_id: str | None = None
    from_spec: str | None = None
    to_spec: str | None = None
    reason: str | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)

    KINDS = frozenset(
        {
            "noop",
            "hold",
            "probe",
            "provider_observation_wait",
            "provider_degraded",
            "pre_tool_next_target",
            "same_route_recovery_child",
            "configured_fallback_child",
            "return_primary_child",
            "refusal",
            "durability_unknown",
        }
    )

    def __post_init__(self) -> None:
        if self.kind not in self.KINDS:
            raise ValueError(f"unknown provider route decision kind: {self.kind!r}")
        for name in ("phase", "logical_dispatch_id", "selected_spec"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"provider route decision {name} is required")
        if self.retry_after_s < 0:
            raise ValueError("provider route decision retry_after_s must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "phase": self.phase,
            "logical_dispatch_id": self.logical_dispatch_id,
            "selected_spec": self.selected_spec,
            "provider_failure_key": self.provider_failure_key,
            "retry_after_s": self.retry_after_s,
            "cause_event_id": self.cause_event_id,
            "from_spec": self.from_spec,
            "to_spec": self.to_spec,
            "reason": self.reason,
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True)
class ProviderProbeRequest:
    """The immutable request handed to an out-of-lock probe executor."""

    provider_failure_key: str
    phase: str
    route_identity: str = ""
    retry_not_before_ns: int = 0
    deadline_ns: int = 0
    provider_epoch_identity: str = ""
    observation_id: str = ""
    parent_reservation_event_id: str | None = None
    parent_terminal_event_id: str | None = None
    selected_spec: str = ""
    logical_dispatch_id: str = ""
    route_liveness_identity: str | None = None
    attempt: int = 1
    previous_now_ns: int | None = None

    def __post_init__(self) -> None:
        for name in ("provider_failure_key", "phase"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"provider probe request {name} is required")
        if not isinstance(self.route_identity, str):
            raise ValueError("provider probe request route_identity must be text")
        for name in ("retry_not_before_ns", "deadline_ns"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"provider probe request {name} must be non-negative")
        if self.deadline_ns < self.retry_not_before_ns:
            raise ValueError("provider probe request deadline precedes eligibility")
        if isinstance(self.attempt, bool) or not isinstance(self.attempt, int) or self.attempt < 1:
            raise ValueError("provider probe request attempt must be positive")
        if self.previous_now_ns is not None and (
            isinstance(self.previous_now_ns, bool)
            or not isinstance(self.previous_now_ns, int)
            or self.previous_now_ns < 0
        ):
            raise ValueError("provider probe request previous_now_ns is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_failure_key": self.provider_failure_key,
            "provider_epoch_identity": self.provider_epoch_identity,
            "observation_id": self.observation_id,
            "parent_reservation_event_id": self.parent_reservation_event_id,
            "parent_terminal_event_id": self.parent_terminal_event_id,
            "phase": self.phase,
            "route_identity": self.route_identity,
            "route_liveness_identity": self.route_liveness_identity,
            "retry_not_before_ns": self.retry_not_before_ns,
            "deadline_ns": self.deadline_ns,
            "attempt": self.attempt,
            "selected_spec": self.selected_spec,
            "logical_dispatch_id": self.logical_dispatch_id,
            "previous_now_ns": self.previous_now_ns,
        }


@dataclass(frozen=True)
class ProviderProbeResult:
    """Typed executor output; ``unknown`` is conservatively a failure."""

    probe_lease_id: str
    provider_failure_key: str
    result: str = "unknown"
    evidence_digest: str = ""
    provider_epoch_identity: str = ""
    parent_reservation_event_id: str | None = None
    parent_terminal_event_id: str | None = None
    phase: str | None = None
    route_identity: str | None = None
    route_liveness_identity: str | None = None
    passed: bool | None = None

    def __post_init__(self) -> None:
        for name in ("probe_lease_id", "provider_failure_key", "evidence_digest"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"provider probe result {name} is required")
        result = self.result
        if self.passed is not None:
            if not isinstance(self.passed, bool):
                raise ValueError("provider probe result passed must be boolean")
            result = "passed" if self.passed else ("failed" if result != "unknown" else "unknown")
            object.__setattr__(self, "result", result)
        if result not in {"passed", "failed", "unknown"}:
            raise ValueError("provider probe result kind is invalid")
        if self.phase is not None and not isinstance(self.phase, str):
            raise ValueError("provider probe result phase must be text")
        if self.route_identity is not None and not isinstance(self.route_identity, str):
            raise ValueError("provider probe result route_identity must be text")

    @property
    def is_passed(self) -> bool:
        return self.result == "passed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe_lease_id": self.probe_lease_id,
            "provider_failure_key": self.provider_failure_key,
            "provider_epoch_identity": self.provider_epoch_identity,
            "parent_reservation_event_id": self.parent_reservation_event_id,
            "parent_terminal_event_id": self.parent_terminal_event_id,
            "phase": self.phase,
            "route_identity": self.route_identity,
            "route_liveness_identity": self.route_liveness_identity,
            "result": self.result,
            "passed": self.is_passed,
            "evidence_digest": self.evidence_digest,
        }


_PROBE_REQUEST_MAGIC = b"NBF06-PROBE-REQUEST-V1"
_PROBE_RESULT_MAGIC = b"NBF06-PROBE-RESULT-V1"
_PROBE_REQUEST_FIELDS = frozenset(ProviderProbeRequest("key", "phase").to_dict())
_PROBE_RESULT_FIELDS = frozenset(ProviderProbeResult("lease", "key", evidence_digest="e" ).to_dict())


def _probe_json_frame(magic: bytes, payload: Mapping[str, Any]) -> bytes:
    import json

    body = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return magic + _U64.pack(len(body)) + body


def _probe_parse_frame(raw: bytes | bytearray, magic: bytes, fields: frozenset[str]) -> dict[str, Any]:
    import json

    raw = bytes(raw) if isinstance(raw, bytearray) else raw
    if not isinstance(raw, bytes) or not raw.startswith(magic):
        raise ValueError("provider probe frame has an invalid codec magic")
    offset = len(magic)
    length, offset = _read_u64(raw, offset, field_name="probe frame length")
    if offset + length != len(raw):
        raise ValueError("provider probe frame has truncated or trailing bytes")
    try:
        payload = json.loads(raw[offset:offset + length].decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("provider probe frame is not canonical JSON") from exc
    if not isinstance(payload, dict) or set(payload) != fields:
        raise ValueError("provider probe frame has unknown or missing fields")
    canonical = _probe_json_frame(magic, payload)
    if canonical != raw:
        raise ValueError("provider probe frame is not canonical")
    return payload


def serialize_provider_probe_request(
    request: ProviderProbeRequest | Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> bytes:
    if request is None:
        request = kwargs
    elif kwargs:
        raise ValueError("provider probe request cannot mix object and keyword fields")
    if isinstance(request, ProviderProbeRequest):
        obj = request
    elif isinstance(request, Mapping):
        if set(request) != _PROBE_REQUEST_FIELDS:
            unknown = sorted(set(request) - _PROBE_REQUEST_FIELDS)
            missing = sorted(_PROBE_REQUEST_FIELDS - set(request))
            raise ValueError(f"provider probe request fields differ (unknown={unknown}, missing={missing})")
        obj = ProviderProbeRequest(**dict(request))
    else:
        raise ValueError("provider probe request must be typed or mapping")
    return _probe_json_frame(_PROBE_REQUEST_MAGIC, obj.to_dict())


def deserialize_provider_probe_request(raw: bytes | bytearray) -> ProviderProbeRequest:
    return ProviderProbeRequest(**_probe_parse_frame(raw, _PROBE_REQUEST_MAGIC, _PROBE_REQUEST_FIELDS))


def serialize_provider_probe_result(
    result: ProviderProbeResult | Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> bytes:
    if result is None:
        result = kwargs
    elif kwargs:
        raise ValueError("provider probe result cannot mix object and keyword fields")
    if isinstance(result, ProviderProbeResult):
        obj = result
    elif isinstance(result, Mapping):
        if set(result) != _PROBE_RESULT_FIELDS:
            unknown = sorted(set(result) - _PROBE_RESULT_FIELDS)
            missing = sorted(_PROBE_RESULT_FIELDS - set(result))
            raise ValueError(f"provider probe result fields differ (unknown={unknown}, missing={missing})")
        obj = ProviderProbeResult(**dict(result))
    else:
        raise ValueError("provider probe result must be typed or mapping")
    return _probe_json_frame(_PROBE_RESULT_MAGIC, obj.to_dict())


def deserialize_provider_probe_result(raw: bytes | bytearray) -> ProviderProbeResult:
    return ProviderProbeResult(**_probe_parse_frame(raw, _PROBE_RESULT_MAGIC, _PROBE_RESULT_FIELDS))


def _probe_value(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _probe_matches_context(lease: Mapping[str, Any], request: ProviderProbeRequest) -> bool:
    return (
        lease.get("provider_failure_key") == request.provider_failure_key
        and lease.get("parent_reservation_event_id") == request.parent_reservation_event_id
        and lease.get("phase") == request.phase
        and lease.get("route_identity") == request.route_identity
    )


def select_provider_probe(
    request: Mapping[str, Any] | Any,
    ledger_view: ProviderLedgerView | Mapping[str, Any],
    *,
    now_ns: int | None = None,
) -> ProviderProbeRequest | None:
    """Purely decide whether one deadline-gated probe may be leased.

    The function never appends a lease.  Its caller must pass the returned
    request through ``IncidentLedger.start_provider_probe_locked``; this is
    the only way two contenders can resolve to one durable winner.
    """
    view = ledger_view if isinstance(ledger_view, ProviderLedgerView) else ProviderLedgerView.from_projection(ledger_view)
    source = request
    outcome = _probe_value(request, "outcome")
    if isinstance(outcome, DispatchOutcome):
        source = outcome
    evidence = _probe_value(source, "provider_evidence", {})
    if not isinstance(evidence, Mapping):
        evidence = {}
    key = _probe_value(source, "provider_failure_key") or evidence.get("provider_failure_key")
    phase = _probe_value(source, "phase") or evidence.get("phase")
    selected_spec = _probe_value(source, "selected_spec") or evidence.get("selected_spec") or ""
    if isinstance(source, DispatchOutcome):
        if source.kind != "provider_exhausted":
            return None
        # A malformed terminal is a hold, never a probe authorization.
        try:
            key = derive_provider_failure_key(source).value
            evidence = validate_provider_terminal_evidence(source)
        except ValueError:
            return None
    if not isinstance(key, str) or not key or not isinstance(phase, str) or not phase:
        return None
    stream = _matching_stream(view, key)
    if stream is not None and int(stream.get("observation_streak", 0)) >= 2:
        return None
    overlay = request if isinstance(request, Mapping) else None

    def _field(name: str, default: Any = None) -> Any:
        if overlay is not None and overlay.get(name) is not None:
            return overlay.get(name)
        return _probe_value(source, name, default)

    route_identity = _field("route_identity") or _field("route_liveness_identity") or ""
    parent_reservation = _field("parent_reservation_event_id") or _field("reservation_event_id")
    parent_terminal = _field("parent_terminal_event_id") or _field("terminal_outcome_event_id")
    logical_dispatch_id = _field("logical_dispatch_id", "") or ""
    observation_id = _field("observation_id") or evidence.get("observation_id") or ""
    epoch = _field("provider_epoch_identity") or evidence.get("provider_epoch_identity") or ""
    retry = _field("retry_not_before_ns")
    if retry is None:
        retry = _field("parent_retry_not_before_ns", 0) or 0
    observed_ns = _field("terminal_observed_at_ns") or evidence.get("observed_at_ns") or 0
    if isinstance(observed_ns, int) and observed_ns > retry:
        retry = observed_ns
    deadline = _field("deadline_ns")
    if deadline is None:
        deadline = _field("probe_deadline_ns")
    if not isinstance(retry, int) or isinstance(retry, bool) or retry < 0 or not isinstance(deadline, int) or isinstance(deadline, bool) or deadline < retry:
        return None
    now = int(datetime.now(timezone.utc).timestamp() * 1_000_000_000) if now_ns is None else now_ns
    if isinstance(now, bool) or not isinstance(now, int) or now < 0:
        raise ValueError("probe selector now_ns must be non-negative")
    previous_now = _field("previous_now_ns")
    if previous_now is not None and now < previous_now:
        return None
    if now < retry:
        return None
    candidate = ProviderProbeRequest(
        provider_failure_key=key,
        provider_epoch_identity=str(epoch),
        observation_id=str(observation_id),
        parent_reservation_event_id=parent_reservation,
        parent_terminal_event_id=parent_terminal,
        phase=phase,
        route_identity=str(route_identity),
        retry_not_before_ns=retry,
        deadline_ns=deadline,
        attempt=int(_field("attempt", 1) or 1),
        selected_spec=str(_field("selected_spec") or selected_spec),
        logical_dispatch_id=logical_dispatch_id,
        route_liveness_identity=_field("route_liveness_identity"),
        previous_now_ns=previous_now,
    )
    if any(_probe_matches_context(lease, candidate) and lease.get("status") in {"leased", "passed"} for lease in view.provider_probe_leases.values()):
        return None
    return candidate


class ProbeExecutor(Protocol):
    """Executor protocol; implementations run only after the lease CAS."""

    def run(self, request: ProviderProbeRequest) -> ProviderProbeResult | Mapping[str, Any]:
        ...


def _invoke_probe_executor(executor: Any, request: ProviderProbeRequest) -> Any:
    run = getattr(executor, "run", None)
    if callable(run):
        return run(request)
    if callable(executor):
        return executor(request)
    raise ValueError("provider probe executor must be callable or expose run")


def execute_provider_probe(
    ledger: Any,
    request: ProviderProbeRequest,
    executor: ProbeExecutor | Callable[[ProviderProbeRequest], Any],
    *,
    now_ns: int | None = None,
    actor: str = "provider-resilience",
) -> Mapping[str, Any] | None:
    """Lease, execute outside the ledger lock, then fence result and close."""
    lease = ledger.start_provider_probe_locked(probe_request=request, now_ns=now_ns, actor=actor)
    if lease is None:
        return None
    # There is intentionally no ledger call around this executor invocation.
    raw_result = _invoke_probe_executor(executor, request)
    if isinstance(raw_result, ProviderProbeResult):
        result = raw_result
    elif isinstance(raw_result, Mapping):
        result = ProviderProbeResult(
            probe_lease_id=str(raw_result.get("probe_lease_id") or lease["payload"]["probe_lease_id"]),
            provider_failure_key=str(raw_result.get("provider_failure_key") or request.provider_failure_key),
            provider_epoch_identity=str(raw_result.get("provider_epoch_identity") or request.provider_epoch_identity),
            parent_reservation_event_id=raw_result.get("parent_reservation_event_id", request.parent_reservation_event_id),
            parent_terminal_event_id=raw_result.get("parent_terminal_event_id", request.parent_terminal_event_id),
            phase=raw_result.get("phase", request.phase),
            route_identity=raw_result.get("route_identity", request.route_identity),
            route_liveness_identity=raw_result.get("route_liveness_identity", request.route_liveness_identity),
            result=str(raw_result.get("result", "passed" if raw_result.get("passed") is True else "unknown")),
            passed=raw_result.get("passed"),
            evidence_digest=str(raw_result.get("evidence_digest") or _digest(raw_result)),
        )
    else:
        raise ValueError("provider probe executor returned an unsupported result")
    result_record = ledger.record_provider_probe_result_locked(result, now_ns=now_ns, actor=actor)
    closed_record = ledger.close_provider_probe_locked(
        probe_lease_id=result.probe_lease_id,
        provider_failure_key=result.provider_failure_key,
        parent_reservation_event_id=request.parent_reservation_event_id,
        phase=request.phase,
        route_identity=request.route_identity,
        now_ns=now_ns,
        close_reason="passed" if result.is_passed else ("unknown" if result.result == "unknown" else "failed"),
        actor=actor,
    )
    return {"lease": lease, "result": result_record, "closed": closed_record}


class LedgerBoundProbeExecutor:
    """Small convenience wrapper that preserves the out-of-lock boundary."""

    def __init__(self, ledger: Any, executor: ProbeExecutor | Callable[[ProviderProbeRequest], Any], *, actor: str = "provider-resilience") -> None:
        self.ledger = ledger
        self.executor = executor
        self.actor = actor

    def run(self, request: ProviderProbeRequest, *, now_ns: int | None = None) -> Mapping[str, Any] | None:
        return execute_provider_probe(self.ledger, request, self.executor, now_ns=now_ns, actor=self.actor)


def _evidence_for(outcome: DispatchOutcome) -> Mapping[str, Any]:
    evidence = outcome.provider_evidence
    if not isinstance(evidence, Mapping):
        raise ValueError("provider exhaustion requires mapping evidence")
    return evidence


def derive_provider_failure_key(outcome: DispatchOutcome) -> ProviderFailureKey:
    """Derive and verify the only accepted provider-failure identity."""

    evidence = _evidence_for(outcome)
    failure_class = evidence.get("provider_failure_class") or evidence.get("retryability_class")
    if failure_class not in _PROVIDER_FAILURE_CLASSES:
        raise ValueError("provider exhaustion class is not T8-eligible")
    epoch = evidence.get("provider_epoch_identity")
    if not isinstance(epoch, str) or not epoch:
        raise ValueError("provider epoch identity is required")
    derived = ProviderFailureKey.derive(
        phase=outcome.phase,
        selected_spec=outcome.selected_spec,
        provider_failure_class=str(failure_class),
        provider_epoch_identity=epoch,
    )
    supplied = outcome.provider_failure_key or evidence.get("provider_failure_key")
    if supplied != derived.value:
        raise ValueError("provider failure key does not match canonical evidence")
    return derived


def validate_provider_terminal_evidence(outcome: DispatchOutcome) -> Mapping[str, Any]:
    """Validate closed provider evidence at the accepted terminal boundary."""

    if outcome.kind != "provider_exhausted" or outcome.launch_state != "accepted":
        raise ValueError("provider policy accepts only an accepted provider_exhausted terminal")
    evidence = dict(_evidence_for(outcome))
    required = (
        "observation_id",
        "retryability_class",
        "exhausted_attempt_count",
        "terminal_provider_evidence_id",
        "precondition_identity",
        "provider_epoch_identity",
        "provider_failure_key",
        "observed_at",
    )
    missing = [name for name in required if not evidence.get(name)]
    if missing:
        raise ValueError(f"provider evidence missing fields: {', '.join(missing)}")
    if evidence.get("retryability_class") not in _PROVIDER_FAILURE_CLASSES:
        raise ValueError("provider evidence class cannot authorize T8 routing")
    attempts = evidence.get("exhausted_attempt_count")
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
        raise ValueError("provider evidence exhausted_attempt_count must be positive")
    # Timestamps are evidence, not identity.  Parse them to reject malformed
    # provider records while leaving the value untouched for ledger replay.
    try:
        datetime.fromisoformat(str(evidence["observed_at"]).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("provider evidence observed_at is invalid") from exc
    derive_provider_failure_key(outcome)
    if evidence.get("provider") is not None and evidence.get("provider") != outcome.provider:
        raise ValueError("provider evidence provider disagrees with terminal context")
    return MappingProxyType(evidence)


def _matching_stream(view: ProviderLedgerView, key: str) -> Mapping[str, Any] | None:
    for stream in view.provider_streaks.values():
        if isinstance(stream, Mapping) and stream.get("provider_failure_key") == key:
            return stream
    return None


def select_provider_route(
    request: Mapping[str, Any] | Any,
    ledger_view: ProviderLedgerView | Mapping[str, Any],
) -> ProviderRouteDecision:
    """Purely select the next T8 action from typed request + ledger view.

    This first slice handles the high-value shared-seam behavior: accepted
    provider exhaustion becomes one observation wait, while ordinary,
    scheduling, unresolved, and disposition outcomes are no-ops.  A target
    may be proposed only when the request explicitly carries a configured
    chain and a typed operational class; callers still need linked admission
    before a child can run.
    """

    view = ledger_view if isinstance(ledger_view, ProviderLedgerView) else ProviderLedgerView.from_projection(ledger_view)
    outcome = request if isinstance(request, DispatchOutcome) else request.get("outcome") if isinstance(request, Mapping) else getattr(request, "outcome", None)
    if not isinstance(outcome, DispatchOutcome):
        raise ValueError("provider route selection requires a typed DispatchOutcome")
    if outcome.kind != "provider_exhausted":
        return ProviderRouteDecision(
            kind="noop",
            phase=outcome.phase,
            logical_dispatch_id=outcome.logical_dispatch_id,
            selected_spec=outcome.selected_spec,
            reason="non_provider_terminal",
        )
    evidence = validate_provider_terminal_evidence(outcome)
    key = derive_provider_failure_key(outcome).value
    stream = _matching_stream(view, key)
    streak = int(stream.get("observation_streak", 0)) if stream else 0
    # The terminal projection is the worker-outcome authority.  The
    # observation event is intentionally not counted as another worker event.
    if streak <= 1:
        wait = float(evidence.get("retry_after_s") or 0.0)
        return ProviderRouteDecision(
            kind="provider_observation_wait",
            phase=outcome.phase,
            logical_dispatch_id=outcome.logical_dispatch_id,
            selected_spec=outcome.selected_spec,
            provider_failure_key=key,
            retry_after_s=max(0.0, wait),
            cause_event_id=outcome.terminal_outcome_event_id,
            reason="first_matching_provider_observation",
            evidence=evidence,
        )
    return ProviderRouteDecision(
        kind="provider_degraded",
        phase=outcome.phase,
        logical_dispatch_id=outcome.logical_dispatch_id,
        selected_spec=outcome.selected_spec,
        provider_failure_key=key,
        retry_after_s=0.0,
        cause_event_id=outcome.terminal_outcome_event_id,
        reason="two_matching_provider_observations",
        evidence=evidence,
    )


def provider_scheduling_condition(
    decision: ProviderRouteDecision,
    *,
    plan_id: str,
    dispatch_family_id: str,
    admission_attempt: int,
) -> SchedulingCondition | None:
    """Project a pure provider wait/degradation decision to transport."""

    if decision.kind not in {"provider_observation_wait", "provider_degraded"}:
        return None
    reason = decision.kind
    return SchedulingCondition(
        condition_id=_digest((reason, decision.cause_event_id, decision.provider_failure_key, decision.logical_dispatch_id)),
        reason=reason,
        plan_id=plan_id,
        phase=decision.phase,
        spec=decision.selected_spec,
        dispatch_family_id=dispatch_family_id,
        logical_dispatch_id=decision.logical_dispatch_id,
        admission_attempt=admission_attempt,
        retry_after_s=decision.retry_after_s,
        observed_at=_now(),
        cause_event_id=decision.cause_event_id,
        evidence=decision.to_dict(),
    )


def apply_provider_route_decision_locked(
    ledger: Any,
    decision: ProviderRouteDecision,
    *,
    outcome: DispatchOutcome | None = None,
    reservation_event_id: str | None = None,
    actor: str = "provider-resilience",
) -> ProviderRouteDecision:
    """Apply the minimal post-terminal observation through the ledger door.

    The ledger's append methods acquire its existing sequence lock.  No
    provider-specific store or writer is introduced here.  Replaying the same
    terminal produces the same deterministic observation identity and the
    ledger's idempotent append path returns the already committed event.
    """

    if decision.kind not in {"provider_observation_wait", "provider_degraded"}:
        return decision
    if outcome is None or outcome.kind != "provider_exhausted":
        raise ValueError("provider observation application requires its terminal outcome")
    evidence = validate_provider_terminal_evidence(outcome)
    key = derive_provider_failure_key(outcome).value
    if decision.provider_failure_key != key:
        raise ValueError("provider decision key disagrees with terminal evidence")
    terminal_id = outcome.terminal_outcome_event_id
    projection = ledger.projection()
    terminal = next(
        (
            item
            for item in projection.get("terminals", {}).values()
            if (terminal_id and item.get("terminal_outcome_id") == terminal_id)
            or (
                item.get("admission_receipt_id") == outcome.admission_receipt_id
                and item.get("phase") == outcome.phase
                and item.get("logical_dispatch_id") == outcome.logical_dispatch_id
            )
        ),
        None,
    )
    if terminal_id is None:
        terminal_id = (terminal or {}).get("terminal_outcome_id")
    if terminal_id is None:
        raise ValueError("provider observation requires its committed terminal")
    reservation_event_id = reservation_event_id or (terminal or {}).get("reservation_event_id")
    observation_id = hashlib.sha256(
        json.dumps(("provider-observation", terminal_id, key), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    append = getattr(ledger, "append_provider_observation")
    append(
        observation_id=observation_id,
        provider_failure_key=key,
        selected_spec=outcome.selected_spec,
        phase=outcome.phase,
        provider_failure_class=str(evidence["retryability_class"]),
        provider_epoch_identity=str(evidence["provider_epoch_identity"]),
        terminal_outcome_event_id=terminal_id,
        reservation_event_id=reservation_event_id,
        admission_receipt_id=outcome.admission_receipt_id,
        logical_dispatch_id=outcome.logical_dispatch_id,
        actor=actor,
    )
    return decision


__all__ = [
    "CHAIN_CODEC_VERSION",
    "CHAIN_MAGIC",
    "LedgerBoundProbeExecutor",
    "ProviderLedgerView",
    "ProviderProbeRequest",
    "ProviderProbeResult",
    "ProviderRouteDecision",
    "apply_provider_route_decision_locked",
    "derive_configured_fallback_chain_identity",
    "derive_provider_failure_key",
    "deserialize_configured_fallback_chain_v1",
    "deserialize_provider_probe_request",
    "deserialize_provider_probe_result",
    "execute_provider_probe",
    "provider_family",
    "provider_scheduling_condition",
    "select_provider_probe",
    "select_provider_route",
    "serialize_configured_fallback_chain_v1",
    "serialize_provider_probe_request",
    "serialize_provider_probe_result",
    "validate_provider_terminal_evidence",
]
