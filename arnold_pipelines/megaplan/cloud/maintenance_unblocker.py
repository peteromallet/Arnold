"""Observation-only maintenance unblocker (T3.2).

This module is deliberately a producer of *requests*, never an owner of repair
authority.  It joins two fresh, independently-read observations and emits one
occurrence-bound request/checkpoint.  A single observation, missing evidence,
identity drift, or a stale fence remains non-dispatchable.

The supported fixer recovery sequence is represented as inert typed data.  The
unblocker never runs ``recover-blocked``, ``runtime-rebind``, ``chain start``,
or any other effect.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator


SCHEMA_VERSION = "arnold-megaplan-maintenance-unblocker-v1"
CHECKPOINT_SCHEMA_VERSION = "arnold-megaplan-maintenance-unblocker-checkpoint-v1"
PERMITTED_MONOTONIC_COUNTERS = frozenset({"observation_count", "read_count", "attempt_count"})


class UnblockerOutcome(StrEnum):
    UNKNOWN = "unknown"
    DRIFT_REJECTED = "drift_rejected"
    REQUEST_EMITTED = "request_emitted"
    REPLAYED = "replayed"
    STALE_FENCE = "stale_fence"


class StableOccurrenceIdentity(BaseModel):
    """The only identity coordinates that may authorize a matching pair."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    occurrence: StrictStr
    plan_cursor: StrictStr
    runtime_manifest: StrictStr
    target_digest: StrictStr
    source_cursor: StrictStr

    @field_validator("occurrence", "plan_cursor", "runtime_manifest", "target_digest", "source_cursor")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("stable occurrence identity fields must be non-empty")
        return value


class ObservationEvidence(BaseModel):
    """One read-only observation; authority-looking telemetry is never authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["arnold-megaplan-maintenance-unblocker-v1"] = SCHEMA_VERSION
    identity: StableOccurrenceIdentity
    observed_at: datetime
    source_read_id: StrictStr
    source_read_digest: StrictStr | None = None
    evidence_ref: StrictStr | None = None
    failure_fingerprint: StrictStr
    producer_principal: StrictStr
    verifier_principal: StrictStr
    # These are telemetry only.  They are compared for drift and never establish
    # authority, even when present and plausible.
    pid: StrictInt | None = None
    tmux_session: StrictStr | None = None
    heartbeat: StrictStr | None = None
    path: StrictStr | None = None
    lease_epoch: StrictInt | None = None
    permitted_counters: dict[StrictStr, StrictInt] = Field(default_factory=dict)

    @field_validator("observed_at")
    @classmethod
    def _aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observation time must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("source_read_id", "failure_fingerprint", "producer_principal", "verifier_principal")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("observation identity/evidence fields must be non-empty")
        return value

    @field_validator("permitted_counters")
    @classmethod
    def _allowed_counters(cls, value: Mapping[str, int]) -> dict[str, int]:
        unknown = set(value) - PERMITTED_MONOTONIC_COUNTERS
        if unknown:
            raise ValueError(f"unsupported monotonic counters: {sorted(unknown)}")
        if any(int(item) < 0 for item in value.values()):
            raise ValueError("permitted counters must be non-negative")
        return {str(key): int(item) for key, item in value.items()}

    @model_validator(mode="after")
    def _evidence_is_well_formed(self) -> ObservationEvidence:
        if self.evidence_ref is not None and not self.evidence_ref.strip():
            raise ValueError("evidence_ref must be non-empty when supplied")
        return self

    @property
    def has_required_evidence(self) -> bool:
        return bool(self.evidence_ref and self.source_read_id and self.source_read_digest)


class FixerExecutableRecoveryContract(BaseModel):
    """Inert description of the explicit fixer-only recovery sequence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract: Literal["fixer_executable_recovery_v1"] = "fixer_executable_recovery_v1"
    failure_kind: Literal["deterministic_phase_failure"] = "deterministic_phase_failure"
    retry_strategy: Literal["repair_phase_contract"] = "repair_phase_contract"
    repair_scope: Literal["engine_runtime"] = "engine_runtime"
    approval_required: Literal[True] = True
    automatic: Literal[False] = False
    authority: Literal["explicit_repair_commit_bound_to_engine_runtime"] = (
        "explicit_repair_commit_bound_to_engine_runtime"
    )
    verbs: tuple[StrictStr, ...] = (
        "land_patch_on_import_root",
        "expected_head_telemetry_only",
        "runtime_rebind_with_milestone_label_m7",
        "recover_blocked_with_explicit_repair_commit",
        "chain_start_one",
    )


class OccurrenceBoundMaintenanceRequest(BaseModel):
    """Typed request/checkpoint payload; it has no approve or execute operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["arnold-megaplan-maintenance-unblocker-v1"] = SCHEMA_VERSION
    request_id: StrictStr
    occurrence: StableOccurrenceIdentity
    failure_fingerprint: StrictStr
    observation_ids: tuple[StrictStr, StrictStr]
    recovery_contract: FixerExecutableRecoveryContract = Field(
        default_factory=FixerExecutableRecoveryContract
    )
    approval_required: Literal[True] = True
    effect_authorized: Literal[False] = False
    source: Literal["observation_bound_unblocker"] = "observation_bound_unblocker"


class MaintenanceCheckpoint(BaseModel):
    """Durable, replayable inert checkpoint for one emitted request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["arnold-megaplan-maintenance-unblocker-checkpoint-v1"] = CHECKPOINT_SCHEMA_VERSION
    checkpoint_id: StrictStr
    request_id: StrictStr
    occurrence: StableOccurrenceIdentity
    fence: StrictInt
    outcome: Literal["request_emitted", "replayed"]
    request: OccurrenceBoundMaintenanceRequest

    @field_validator("checkpoint_id")
    @classmethod
    def _safe_checkpoint_id(cls, value: str) -> str:
        if not value or Path(value).name != value or value in {".", ".."}:
            raise ValueError("checkpoint_id must be a single safe path component")
        return value
    @field_validator("fence")
    @classmethod
    def _nonnegative_fence(cls, value: int) -> int:
        if value < 0:
            raise ValueError("checkpoint fence must be non-negative")
        return value


class UnblockerResult(BaseModel):
    """Result of the pure observation join or its optional checkpoint write."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["arnold-megaplan-maintenance-unblocker-v1"] = SCHEMA_VERSION
    outcome: UnblockerOutcome
    reasons: tuple[StrictStr, ...] = ()
    request: OccurrenceBoundMaintenanceRequest | None = None
    checkpoint: MaintenanceCheckpoint | None = None


class CheckpointConflict(ValueError):
    """An idempotency key was reused with different immutable content."""


class StaleCheckpointFence(ValueError):
    """A checkpoint write carried a fence older than the stored checkpoint."""


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _observation_id(observation: ObservationEvidence) -> str:
    return "observation:" + _canonical_digest(observation.model_dump(mode="json"))


def _stable_key(observation: ObservationEvidence) -> tuple[str, ...]:
    identity = observation.identity
    return (
        identity.occurrence,
        identity.plan_cursor,
        identity.runtime_manifest,
        identity.target_digest,
        identity.source_cursor,
    )


def _non_monotonic_projection(observation: ObservationEvidence) -> tuple[Any, ...]:
    """Fields whose drift invalidates a pair, excluding time/counters/read IDs."""
    return (
        observation.identity,
        observation.failure_fingerprint,
        observation.evidence_ref,
        observation.producer_principal,
        observation.verifier_principal,
        observation.pid,
        observation.tmux_session,
        observation.heartbeat,
        observation.path,
        observation.lease_epoch,
    )


def _unknown(reason: str) -> UnblockerResult:
    return UnblockerResult(outcome=UnblockerOutcome.UNKNOWN, reasons=(reason,))


def _reject(reason: str) -> UnblockerResult:
    return UnblockerResult(outcome=UnblockerOutcome.DRIFT_REJECTED, reasons=(reason,))


def evaluate_observations(
    observations: Sequence[ObservationEvidence],
    *,
    fence: int = 0,
) -> UnblockerResult:
    """Join at most two observations without writing or invoking an effect.

    One observation is explicitly ``UNKNOWN``.  Two observations must have
    equal stable identity and equal every non-monotonic field; their source
    reads must be distinct.  Only observation time and the allow-listed
    counters may advance.
    """
    if fence < 0:
        raise ValueError("fence must be non-negative")
    if not observations:
        return _unknown("no observation evidence")
    if len(observations) == 1:
        return _unknown("one observation is insufficient; second independent read is unknown")
    if len(observations) != 2:
        return _reject("exactly two observations are required")

    first, second = observations
    if not first.has_required_evidence or not second.has_required_evidence:
        return _unknown("required evidence reference/read digest is missing")
    if first.producer_principal == first.verifier_principal or second.producer_principal == second.verifier_principal:
        return _reject("producer and verifier must be distinct")
    if first.source_read_id == second.source_read_id:
        return _reject("observations reuse the same underlying source read")
    if first.source_read_digest == second.source_read_digest:
        return _reject("observations reuse the same underlying source projection")
    if second.observed_at <= first.observed_at:
        return _reject("observation time must advance monotonically")
    if _stable_key(first) != _stable_key(second):
        return _reject("stable occurrence identity drifted")
    if _non_monotonic_projection(first) != _non_monotonic_projection(second):
        return _reject("non-monotonic observation drifted")
    if any(
        second.permitted_counters.get(name, 0) < first.permitted_counters.get(name, 0)
        for name in PERMITTED_MONOTONIC_COUNTERS
    ):
        return _reject("permitted counter regressed")

    request = OccurrenceBoundMaintenanceRequest(
        request_id="maintenance-request:" + _canonical_digest(
            {"identity": first.identity.model_dump(), "fingerprint": first.failure_fingerprint}
        ),
        occurrence=first.identity,
        failure_fingerprint=first.failure_fingerprint,
        observation_ids=(_observation_id(first), _observation_id(second)),
    )
    return UnblockerResult(
        outcome=UnblockerOutcome.REQUEST_EMITTED,
        reasons=("two independent matching observations",),
        request=request,
    )


def _safe_checkpoint_root(root: Path) -> Path:
    resolved = root.expanduser().resolve()
    if resolved == Path.cwd().resolve() or (Path.cwd().resolve() in resolved.parents):
        raise ValueError("checkpoint root must be an explicit disposable root outside the project")
    if any(part in {".git", "runtime", "candidate", "candidates", "live"} for part in resolved.parts):
        raise ValueError("checkpoint root resembles a project, candidate, or live runtime root")
    return resolved


class CheckpointStore:
    """Small append-once store; it never opens plan, chain, lease, or runtime state."""

    def __init__(self, root: Path) -> None:
        self.root = _safe_checkpoint_root(Path(root))
        self.directory = self.root / "maintenance-unblocker-checkpoints"

    def write(self, checkpoint: MaintenanceCheckpoint) -> MaintenanceCheckpoint:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{checkpoint.checkpoint_id}.json"
        if path.exists():
            try:
                existing = MaintenanceCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise CheckpointConflict(f"invalid existing checkpoint: {path}") from exc
            if checkpoint.fence < existing.fence:
                raise StaleCheckpointFence(
                    f"stale checkpoint fence {checkpoint.fence} < stored {existing.fence}"
                )
            if existing.model_dump(mode="json") != checkpoint.model_dump(mode="json"):
                raise CheckpointConflict("checkpoint identity already contains different content")
            return existing.model_copy(update={"outcome": "replayed"})
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(checkpoint.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
        return checkpoint


def emit_observation_bound_request(
    observations: Sequence[ObservationEvidence],
    *,
    fence: int = 0,
    checkpoint_store: CheckpointStore | None = None,
) -> UnblockerResult:
    """Emit at most one typed request and optionally checkpoint it durably."""
    result = evaluate_observations(observations, fence=fence)
    if result.request is None or checkpoint_store is None:
        return result
    checkpoint = MaintenanceCheckpoint(
        checkpoint_id=result.request.request_id.removeprefix("maintenance-request:"),
        request_id=result.request.request_id,
        occurrence=result.request.occurrence,
        fence=fence,
        outcome="request_emitted",
        request=result.request,
    )
    try:
        stored = checkpoint_store.write(checkpoint)
    except StaleCheckpointFence as exc:
        return UnblockerResult(
            outcome=UnblockerOutcome.STALE_FENCE,
            reasons=(str(exc),),
            request=result.request,
        )
    except CheckpointConflict as exc:
        return UnblockerResult(
            outcome=UnblockerOutcome.DRIFT_REJECTED,
            reasons=(str(exc),),
            request=result.request,
        )
    if stored.outcome == "replayed":
        return result.model_copy(update={"outcome": UnblockerOutcome.REPLAYED, "checkpoint": stored})
    return result.model_copy(update={"checkpoint": stored})


# Clear aliases for callers that prefer the noun used by the plan card.
Observation = ObservationEvidence
MaintenanceRequest = OccurrenceBoundMaintenanceRequest


__all__ = [
    "CHECKPOINT_SCHEMA_VERSION",
    "CheckpointConflict",
    "CheckpointStore",
    "FixerExecutableRecoveryContract",
    "MaintenanceCheckpoint",
    "MaintenanceRequest",
    "Observation",
    "ObservationEvidence",
    "OccurrenceBoundMaintenanceRequest",
    "PERMITTED_MONOTONIC_COUNTERS",
    "SCHEMA_VERSION",
    "StableOccurrenceIdentity",
    "StaleCheckpointFence",
    "UnblockerOutcome",
    "UnblockerResult",
    "emit_observation_bound_request",
    "evaluate_observations",
]
