"""Generic artifact-IO chokepoint composed from existing step-IO primitives.

This module is the single neutral entry point a repository / store calls to
classify, gate, and observe a typed-artifact read or write. It composes
``classify_step_io_contract``, ``decision_blocks_read/write``, and
``emit_decision_telemetry`` without re-implementing schema or validator
logic, and without importing any megaplan orchestration surface.

Design points:
* ``LEGACY_UNKNOWN`` short-circuits before any decision/telemetry work:
  legacy / untyped artifacts always pass through unchanged.
* ``warn`` mode never raises; the policy resolver caps blocking semantics
  to ``enforce`` (``decision_blocks_*`` already gates on ``policy.enforces``).
* The read-lenient kill-switch is honoured by the caller-supplied policy —
  this module just trusts ``policy.effective_mode``.
* Telemetry is optional; when ``telemetry_path`` is ``None`` no record is
  emitted (callers that don't want a side-effect channel pass nothing).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arnold.pipeline.step_io_contract import (
    StepIOClassification,
    StepIOContractContext,
    StepIOContractDecision,
    StepIODiagnostic,
    StepIOOperation,
    classify_step_io_contract,
    make_warn_diagnostic,
    is_step_io_envelope,
)
from arnold.pipeline.step_io_policy import (
    StepIOPolicy,
    effective_blocks_read,
    effective_blocks_write,
)
from arnold.pipeline.step_io_telemetry import (
    StepIOViolationRecord,
    emit_decision_telemetry,
)


@dataclass(frozen=True)
class ArtifactIOResult:
    """Outcome of one ``validate_artifact_io`` call.

    ``value`` is what the caller should hand back to user code: the unwrapped
    payload for valid typed artifacts, or the original raw value for legacy /
    pass-through cases.
    """

    classification: StepIOClassification
    decision: StepIOContractDecision | None
    policy: StepIOPolicy
    value: Any
    blocked: bool = False
    block_reason: str = ""
    telemetry_record: StepIOViolationRecord | None = None
    warn_diagnostic: StepIODiagnostic | None = None


class ArtifactIOBlocked(ValueError):
    """Raised when ``enforce`` mode blocks a typed artifact read or write.

    ``result`` and ``decision`` are optional carriers that the blocking
    raise site in :func:`validate_artifact_io` always populates so callers
    can inspect the full classified outcome without re-deriving it.  They
    default to ``None`` to keep other raise sites (e.g. the sidecar
    manifest validator) backward compatible.
    """

    def __init__(
        self,
        *args: object,
        result: ArtifactIOResult | None = None,
        decision: StepIOContractDecision | None = None,
    ) -> None:
        super().__init__(*args)
        self.result = result
        self.decision = decision


def validate_large_artifact_by_manifest(
    blob_path: Path,
    *,
    expected_schema_hash: str,
    max_size: int | None = None,
    recompute_sha256: bool = False,
) -> bool:
    """Validate a >1 MiB artifact through its sidecar manifest.

    The C1 chokepoint trusts the manifest (content_type, schema_hash,
    size, sha256) instead of opening the blob, unless ``recompute_sha256``
    is set (consumer opt-in for tamper detection).

    Returns ``True`` on a clean validation. Raises :class:`ArtifactIOBlocked`
    on disagreement.
    """
    from arnold.pipeline.artifacts import (
        read_sidecar_manifest,
        verify_sidecar_integrity,
    )

    manifest = read_sidecar_manifest(blob_path)
    if manifest is None:
        raise ArtifactIOBlocked(
            f"large artifact missing sidecar manifest: {blob_path}"
        )
    if expected_schema_hash and manifest.schema_hash != expected_schema_hash:
        raise ArtifactIOBlocked(
            f"sidecar schema_hash mismatch: expected {expected_schema_hash!r}, "
            f"got {manifest.schema_hash!r}"
        )
    if max_size is not None and manifest.size > max_size:
        raise ArtifactIOBlocked(
            f"sidecar size {manifest.size} exceeds max_size {max_size}"
        )
    if recompute_sha256 and not verify_sidecar_integrity(blob_path):
        raise ArtifactIOBlocked(
            f"sidecar integrity check failed for {blob_path}"
        )
    return True


def validate_artifact_io(
    value: Any,
    *,
    operation: StepIOOperation | str,
    policy: StepIOPolicy,
    contract_context: StepIOContractContext | None = None,
    artifact: str = "",
    telemetry_path: str | Path | None = None,
) -> ArtifactIOResult:
    """Classify, gate, and observe one typed-artifact IO at a single chokepoint.

    Legacy / non-envelope shapes return immediately with
    ``StepIOClassification.LEGACY_UNKNOWN`` and the value unchanged — no
    decision is constructed and no telemetry is emitted.

    For typed envelopes the function delegates classification to
    ``classify_step_io_contract``, gates blocking through
    ``decision_blocks_{read,write}`` (which only block under ``enforce``),
    and optionally appends a telemetry record. In ``warn`` mode this
    function never raises; the caller observes the decision via the
    returned ``ArtifactIOResult`` and the telemetry record.

    Raises ``ArtifactIOBlocked`` only when ``policy.enforces`` is true and
    the resolved decision blocks the requested operation.
    """

    op = StepIOOperation(operation)

    if not is_step_io_envelope(value):
        return ArtifactIOResult(
            classification=StepIOClassification.LEGACY_UNKNOWN,
            decision=None,
            policy=policy,
            value=value,
        )

    if not policy.enabled:
        return ArtifactIOResult(
            classification=StepIOClassification.LEGACY_UNKNOWN,
            decision=None,
            policy=policy,
            value=value,
        )

    decision = classify_step_io_contract(value, contract_context)
    blocked = (
        effective_blocks_read(decision, policy)
        if op is StepIOOperation.READ
        else effective_blocks_write(decision, policy)
    )

    record = None
    if telemetry_path is not None:
        record = emit_decision_telemetry(
            decision=decision,
            policy=policy,
            artifact=artifact,
            operation=op.value,
            telemetry_path=telemetry_path,
            surface_warn=True,
        )

    effective_value = decision.value if decision.envelope is not None else value
    result = ArtifactIOResult(
        classification=decision.classification,
        decision=decision,
        policy=policy,
        value=effective_value,
        blocked=blocked,
        block_reason=decision.block_reason if blocked else "",
        telemetry_record=record,
        warn_diagnostic=(
            make_warn_diagnostic(decision)
            if policy.warns
            and decision.classification not in (
                StepIOClassification.TYPED_VALID,
                StepIOClassification.LEGACY_UNKNOWN,
            )
            else None
        ),
    )

    if blocked and policy.enforces:
        raise ArtifactIOBlocked(
            f"typed artifact {op.value} blocked: {decision.block_reason}",
            result=result,
            decision=decision,
        )
    return result
