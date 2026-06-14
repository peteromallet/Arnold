"""JSONL telemetry writer/reader for step IO violation records.

This module emits human-readable, queryable JSON-lines records for every
contract decision that is not ``typed_valid`` or ``legacy_unknown`` so that
operators and automated tooling can audit typed-artifact IO behavior without
parsing structured Python objects.

All records are appended to a single JSONL file; the file is safe for
concurrent readers (append-only), and records are written atomically
(OS-level line-buffered).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold.pipeline.step_io_contract import (
    StepIOClassification,
    StepIOContractDecision,
    StepIOEnvelope,
    make_warn_diagnostic,
)
from arnold.pipeline.step_io_policy import StepIOPolicy

TELEMETRY_FILENAME = "step_io_contract_violations.jsonl"
SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class StepIOViolationRecord:
    """A single telemetry record for a non-``ok`` contract decision.

    Every field is designed to be human-readable in a plain JSON viewer and
    queryable with off-the-shelf JSONL tools (``jq``, ``grep``, etc.).
    """

    timestamp: str
    seam: str
    pipeline_id: str | None
    producer_step: str | None
    producer_port: str | None
    consumer_step: str | None
    consumer_port: str | None
    mode: str
    artifact: str
    operation: str
    logical_type: str
    schema_version: str
    classification: str
    diagnostic_details: list[dict[str, str]] = field(default_factory=list)
    block_reason: str = ""
    record_schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_decision(
        cls,
        *,
        decision: StepIOContractDecision,
        policy: StepIOPolicy,
        artifact: str,
        operation: str,
        seam: str = "step_io",
        pipeline_id: str | None = None,
        producer_step: str | None = None,
        producer_port: str | None = None,
        consumer_step: str | None = None,
        consumer_port: str | None = None,
        envelope: StepIOEnvelope | None = None,
    ) -> StepIOViolationRecord:
        """Build a violation record from a contract decision and policy."""
        envelope = envelope or decision.envelope
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            seam=seam,
            pipeline_id=pipeline_id,
            producer_step=producer_step,
            producer_port=producer_port,
            consumer_step=consumer_step,
            consumer_port=consumer_port,
            mode=policy.effective_mode,
            artifact=artifact,
            operation=operation,
            logical_type=envelope.logical_type if envelope is not None else "",
            schema_version=envelope.schema_version if envelope is not None else "",
            classification=decision.classification.value,
            diagnostic_details=[
                {"code": d.code, "message": d.message, "payload_pointer": d.payload_pointer, "schema_pointer": d.schema_pointer}
                for d in decision.diagnostics
            ],
            block_reason=decision.block_reason,
        )

    def to_json(self) -> dict[str, Any]:
        """Serialize to a plain dict for JSONL writing."""
        return asdict(self)


def _is_violation_classification(classification: StepIOClassification) -> bool:
    """Return True when the classification should produce a telemetry record."""
    return classification not in (
        StepIOClassification.TYPED_VALID,
        StepIOClassification.LEGACY_UNKNOWN,
    )


def emit_decision_telemetry(
    *,
    decision: StepIOContractDecision,
    policy: StepIOPolicy,
    artifact: str,
    operation: str,
    telemetry_path: str | Path,
    seam: str = "step_io",
    pipeline_id: str | None = None,
    producer_step: str | None = None,
    producer_port: str | None = None,
    consumer_step: str | None = None,
    consumer_port: str | None = None,
    envelope: StepIOEnvelope | None = None,
    surface_warn: bool = False,
) -> StepIOViolationRecord | None:
    """Emit a JSONL telemetry record for a non-ok contract decision.

    Returns the record that was written, or ``None`` when the classification
    is ``typed_valid`` or ``legacy_unknown`` (nothing is written).
    When *policy* is in off mode, nothing is emitted.
    """
    if not policy.enabled:
        return None
    if not _is_violation_classification(decision.classification):
        return None

    record = StepIOViolationRecord.from_decision(
        decision=decision,
        policy=policy,
        artifact=artifact,
        operation=operation,
        seam=seam,
        pipeline_id=pipeline_id,
        producer_step=producer_step,
        producer_port=producer_port,
        consumer_step=consumer_step,
        consumer_port=consumer_port,
        envelope=envelope,
    )
    if surface_warn and policy.warns and _is_violation_classification(decision.classification):
        warn_diag = make_warn_diagnostic(decision)
        record = StepIOViolationRecord(
            timestamp=record.timestamp,
            seam=record.seam,
            pipeline_id=record.pipeline_id,
            producer_step=record.producer_step,
            producer_port=record.producer_port,
            consumer_step=record.consumer_step,
            consumer_port=record.consumer_port,
            mode=record.mode,
            artifact=record.artifact,
            operation=record.operation,
            logical_type=record.logical_type,
            schema_version=record.schema_version,
            classification=record.classification,
            diagnostic_details=[
                {
                    "code": warn_diag.code,
                    "message": warn_diag.message,
                    "payload_pointer": warn_diag.payload_pointer,
                    "schema_pointer": warn_diag.schema_pointer,
                },
                *record.diagnostic_details,
            ],
            block_reason=record.block_reason,
            record_schema_version=record.record_schema_version,
        )
    append_violation_record(telemetry_path, record)
    return record


def append_violation_record(path: str | Path, record: StepIOViolationRecord) -> None:
    """Append a single JSONL record to *path*.

    Creates the parent directory if it does not exist.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record.to_json(), sort_keys=True, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def read_violation_records(path: str | Path) -> list[dict[str, Any]]:
    """Read all JSONL records from *path*, returning a list of raw dicts.

    Returns an empty list when the file does not exist.
    Malformed lines are silently skipped so a partial write does not break the
    reader.
    """
    path = Path(path)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return records
