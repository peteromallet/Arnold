"""Generic suspension contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from arnold.kernel.capabilities import DispatchKey
from arnold.kernel.ids import ReentryId
from arnold.kernel.replay import ReplayCursor, ReplayDecision, ReplayResolution


_REF_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


class SuspensionState(StrEnum):
    """Lifecycle labels for a suspended run."""

    PENDING = "pending"
    RESUMED = "resumed"
    CANCELLED = "cancelled"
    QUARANTINED = "quarantined"


@dataclass(frozen=True)
class SuspendCapabilityRoute:
    """Route used to suspend and later re-enter a workflow."""

    route_id: str
    dispatch_key: DispatchKey
    reentry_id: ReentryId
    payload_schema_hash: str | None = None


@dataclass(frozen=True)
class SuspensionRecord:
    """Serializable state for a suspended run."""

    run_id: str
    manifest_hash: str
    node_ref: str
    route: SuspendCapabilityRoute
    state: SuspensionState = SuspensionState.PENDING


@dataclass(frozen=True)
class SuspensionCursor:
    """Cursor that pins a suspension point inside a workflow run."""

    cursor: ReplayCursor
    node_ref: str
    route_id: str
    payload_schema_hash: str | None = None

    def __post_init__(self) -> None:
        if not _REF_SEGMENT_RE.fullmatch(self.node_ref):
            raise ValueError("node_ref contains characters outside the ref alphabet")
        if not _REF_SEGMENT_RE.fullmatch(self.route_id):
            raise ValueError("route_id contains characters outside the ref alphabet")


@dataclass(frozen=True)
class ResumeCursor:
    """Cursor plus validated resume payload required to resume a run."""

    suspension: SuspensionCursor
    resume_schema_hash: str | None = None
    resume_payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResumeValidation:
    """Outcome of validating a resume payload against a suspension route."""

    ok: bool
    reason: str | None = None


def validate_suspension_record(
    record: SuspensionRecord,
    *,
    expected_manifest_hash: str,
    allowed_states: set[SuspensionState] | None = None,
) -> ReplayResolution:
    """Validate that a suspension record matches the current run context."""

    if record.manifest_hash != expected_manifest_hash:
        return ReplayResolution(
            decision=ReplayDecision.QUARANTINE,
            reason="suspension record manifest_hash does not match expected manifest hash",
        )

    allowed = allowed_states or {SuspensionState.PENDING}
    if record.state not in allowed:
        return ReplayResolution(
            decision=ReplayDecision.QUARANTINE,
            reason=f"suspension record state {record.state.value!r} is not in {set(s.value for s in allowed)}",
        )

    return ReplayResolution(
        decision=ReplayDecision.REUSE,
        reason="suspension record is valid for the current run context",
    )


def validate_resume_payload(
    payload: Mapping[str, Any],
    *,
    resume_schema_hash: str | None,
    validator: Any | None = None,
) -> ResumeValidation:
    """Validate a resume payload against a registered schema validator.

    If ``resume_schema_hash`` is None, any payload is accepted. If a
    ``validator`` callable is supplied, it must return a truthy value for the
    payload to be accepted. The runtime never treats schema hashes as dynamic
    import paths.
    """

    if resume_schema_hash is None:
        return ResumeValidation(ok=True, reason="no resume schema required")

    if validator is None:
        return ResumeValidation(
            ok=False,
            reason="resume schema required but no validator registered",
        )

    try:
        result = validator(payload)
    except Exception as exc:  # noqa: BLE001
        return ResumeValidation(ok=False, reason=f"validator raised: {exc}")

    if not result:
        return ResumeValidation(ok=False, reason="resume payload failed schema validation")

    return ResumeValidation(ok=True, reason="resume payload validated")
