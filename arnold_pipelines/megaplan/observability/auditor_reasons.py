"""Deterministic progress-auditor reason reduction.

The reducer accepts already-collected evidence records and emits one reason
per reason family.  It is deliberately read-only: it never consults live
state, appends events, or invents evidence IDs.  A reason is emitted only
when the triggering source records carry exact evidence IDs.
"""

from __future__ import annotations

import copy
import enum
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence


class AuditorReasonFamily(str, enum.Enum):
    """Stable reason families emitted by the deterministic auditor reducer."""

    CONSECUTIVE_NORMALIZED_BLOCKS = "consecutive_normalized_blocks"
    SIGNATURE_DRIFT = "signature_drift"
    UNCLOSED_CUSTODY = "unclosed_custody"
    INDEX_MISMATCH = "index_mismatch"
    DETECTION_SLO_BREACH = "detection_slo_breach"
    EXECUTOR_REPAIR_OVERLAP = "executor_repair_overlap"
    CROSS_SESSION_JOINS = "cross_session_joins"
    PROJECTION_AMPLIFICATION = "projection_amplification"
    FULL_SERIALITY = "full_seriality"
    OVERSIZED_REWORK = "oversized_rework"
    INVALID_MODEL = "invalid_model"
    MISSING_LEDGER_COVERAGE = "missing_ledger_coverage"


REASON_ORDER: tuple[AuditorReasonFamily, ...] = tuple(AuditorReasonFamily)


@dataclass(frozen=True)
class AuditorReason:
    """One normalized auditor reason with exact source-evidence bindings."""

    family: AuditorReasonFamily
    evidence_ids: tuple[str, ...]
    summary: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def reason_id(self) -> str:
        """Stable ID for the reason occurrence."""

        payload = {
            "family": self.family.value,
            "evidence_ids": list(self.evidence_ids),
            "details": self.details,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
        return f"{self.family.value}:{digest}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a deterministic JSON-ready mapping."""

        data: dict[str, Any] = {
            "reason_id": self.reason_id,
            "family": self.family.value,
            "evidence_ids": list(self.evidence_ids),
            "summary": self.summary,
        }
        if self.details:
            data["details"] = _json_safe(self.details)
        return data


_Record = Mapping[str, Any]


def reduce_auditor_reasons(records: Sequence[_Record]) -> tuple[AuditorReason, ...]:
    """Reduce normalized evidence records to deterministic auditor reasons.

    The reducer emits at most one reason per :class:`AuditorReasonFamily`.
    Reasons with incomplete source-evidence bindings are suppressed rather
    than receiving synthetic IDs.
    """

    indexed = tuple(_IndexedRecord(i, record) for i, record in enumerate(records))
    ordered = tuple(sorted(indexed, key=_record_sort_key))
    reasons: list[AuditorReason] = []
    for family in REASON_ORDER:
        reason = _DETECTORS[family](ordered)
        if reason is not None and reason.evidence_ids:
            reasons.append(reason)
    return tuple(reasons)


def auditor_reason_fixture(family: AuditorReasonFamily | str) -> tuple[dict[str, Any], ...]:
    """Return the canonical fixture records for one reason family."""

    normalized = AuditorReasonFamily(family)
    return tuple(copy.deepcopy(record) for record in _FIXTURES[normalized])


def auditor_reason_fixtures() -> tuple[dict[str, Any], ...]:
    """Return canonical fixture records that fire all reason families once."""

    records: list[dict[str, Any]] = []
    for family in REASON_ORDER:
        records.extend(auditor_reason_fixture(family))
    return tuple(records)


@dataclass(frozen=True)
class _IndexedRecord:
    index: int
    record: _Record


def _record_sort_key(item: _IndexedRecord) -> tuple[int, str, str, int]:
    record = item.record
    sequence = _int_value(record, "sequence", "seq", "ledger_sequence")
    sequence_key = sequence if sequence is not None else 10**12
    return (
        sequence_key,
        _str_value(record, "ts_utc", "timestamp", "observed_at"),
        _evidence_id(record) or "",
        item.index,
    )


def _make_reason(
    family: AuditorReasonFamily,
    records: Iterable[_IndexedRecord],
    summary: str,
    details: Mapping[str, Any] | None = None,
) -> AuditorReason | None:
    evidence_ids = _evidence_ids(records)
    if not evidence_ids:
        return None
    return AuditorReason(
        family=family,
        evidence_ids=evidence_ids,
        summary=summary,
        details=dict(details or {}),
    )


def _evidence_ids(records: Iterable[_IndexedRecord]) -> tuple[str, ...]:
    ids: list[str] = []
    seen: set[str] = set()
    for item in records:
        evidence_id = _evidence_id(item.record)
        if not evidence_id:
            return ()
        if evidence_id not in seen:
            ids.append(evidence_id)
            seen.add(evidence_id)
    return tuple(ids)


def _evidence_id(record: _Record) -> str | None:
    for key in ("evidence_id", "id"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _str_value(record: _Record, *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is not None:
            return str(value)
    return ""


def _value(record: _Record, *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None:
            return value
    return None


def _int_value(record: _Record, *keys: str) -> int | None:
    value = _value(record, *keys)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_value(record: _Record, *keys: str) -> float | None:
    value = _value(record, *keys)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_kind(record: _Record, *kinds: str) -> bool:
    kind = _str_value(record, "kind", "event_type", "type")
    return kind in kinds


def _explicit_family(record: _Record, family: AuditorReasonFamily) -> bool:
    value = _str_value(record, "auditor_reason_family", "reason_family", "reason")
    return value == family.value


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _detect_consecutive_normalized_blocks(
    records: Sequence[_IndexedRecord],
) -> AuditorReason | None:
    blocking = [
        item
        for item in records
        if _explicit_family(item.record, AuditorReasonFamily.CONSECUTIVE_NORMALIZED_BLOCKS)
        or (
            _is_kind(item.record, "normalized_block", "block")
            and _str_value(item.record, "status", "outcome", "state")
            in {"blocked", "human_blocked", "stale", "no_progress"}
        )
    ]
    previous: _IndexedRecord | None = None
    for item in blocking:
        signature = _str_value(
            item.record,
            "normalized_block",
            "normalized_signature",
            "block_signature",
            "signature",
        )
        if previous is not None:
            previous_signature = _str_value(
                previous.record,
                "normalized_block",
                "normalized_signature",
                "block_signature",
                "signature",
            )
            if signature and signature == previous_signature:
                return _make_reason(
                    AuditorReasonFamily.CONSECUTIVE_NORMALIZED_BLOCKS,
                    (previous, item),
                    "Consecutive auditor blocks normalized to the same signature.",
                    {"normalized_signature": signature},
                )
        previous = item
    return None


def _detect_signature_drift(records: Sequence[_IndexedRecord]) -> AuditorReason | None:
    by_subject: dict[str, dict[str, _IndexedRecord]] = {}
    for item in records:
        record = item.record
        if _explicit_family(record, AuditorReasonFamily.SIGNATURE_DRIFT):
            return _make_reason(
                AuditorReasonFamily.SIGNATURE_DRIFT,
                (item,),
                "Observed signature disagrees with expected signature.",
                {
                    "expected": _str_value(record, "expected_signature", "expected_digest"),
                    "observed": _str_value(record, "observed_signature", "actual_digest"),
                },
            )
        subject = _str_value(record, "signature_subject", "subject", "projection_id")
        signature = _str_value(record, "signature", "digest", "source_digest")
        if not subject or not signature:
            continue
        signatures = by_subject.setdefault(subject, {})
        signatures.setdefault(signature, item)
        if len(signatures) > 1:
            selected = tuple(signatures[sig] for sig in sorted(signatures)[:2])
            return _make_reason(
                AuditorReasonFamily.SIGNATURE_DRIFT,
                selected,
                "Multiple signatures were observed for the same subject.",
                {"subject": subject, "signatures": sorted(signatures)[:2]},
            )
    return None


def _detect_unclosed_custody(records: Sequence[_IndexedRecord]) -> AuditorReason | None:
    opens: dict[str, _IndexedRecord] = {}
    closed: set[str] = set()
    for item in records:
        record = item.record
        if _explicit_family(record, AuditorReasonFamily.UNCLOSED_CUSTODY):
            return _make_reason(
                AuditorReasonFamily.UNCLOSED_CUSTODY,
                (item,),
                "Custody was opened without a matching close.",
                {"custody_id": _str_value(record, "custody_id", "lease_id")},
            )
        if not _is_kind(record, "custody", "custody_lease"):
            continue
        custody_id = _str_value(record, "custody_id", "lease_id", "owner_token")
        action = _str_value(record, "action", "state", "status")
        if not custody_id:
            continue
        if action in {"opened", "acquired", "active"}:
            opens.setdefault(custody_id, item)
        elif action in {"closed", "released", "expired"}:
            closed.add(custody_id)
    for custody_id in sorted(opens):
        if custody_id not in closed:
            return _make_reason(
                AuditorReasonFamily.UNCLOSED_CUSTODY,
                (opens[custody_id],),
                "Custody was opened without a matching close.",
                {"custody_id": custody_id},
            )
    return None


def _detect_index_mismatch(records: Sequence[_IndexedRecord]) -> AuditorReason | None:
    for item in records:
        record = item.record
        expected = _value(record, "expected_index", "source_index")
        observed = _value(record, "observed_index", "projection_index", "current_index")
        if _explicit_family(record, AuditorReasonFamily.INDEX_MISMATCH) or (
            expected is not None and observed is not None and expected != observed
        ):
            return _make_reason(
                AuditorReasonFamily.INDEX_MISMATCH,
                (item,),
                "Projection index does not match the source index.",
                {"expected_index": expected, "observed_index": observed},
            )
    return None


def _detect_detection_slo_breach(records: Sequence[_IndexedRecord]) -> AuditorReason | None:
    for item in records:
        record = item.record
        elapsed = _float_value(record, "detection_latency_ms", "elapsed_ms", "lag_ms")
        limit = _float_value(record, "detection_slo_ms", "slo_ms", "max_lag_ms")
        if _explicit_family(record, AuditorReasonFamily.DETECTION_SLO_BREACH) or (
            elapsed is not None and limit is not None and elapsed > limit
        ):
            return _make_reason(
                AuditorReasonFamily.DETECTION_SLO_BREACH,
                (item,),
                "Auditor detection exceeded the configured SLO.",
                {"elapsed_ms": elapsed, "slo_ms": limit},
            )
    return None


def _detect_executor_repair_overlap(records: Sequence[_IndexedRecord]) -> AuditorReason | None:
    explicit = _first_explicit(records, AuditorReasonFamily.EXECUTOR_REPAIR_OVERLAP)
    if explicit is not None:
        return _make_reason(
            AuditorReasonFamily.EXECUTOR_REPAIR_OVERLAP,
            (explicit,),
            "Executor and repair activity overlapped.",
        )
    executors = [item for item in records if _is_kind(item.record, "executor_active", "executor")]
    repairs = [item for item in records if _is_kind(item.record, "repair_active", "repair")]
    for executor in executors:
        for repair in repairs:
            if _same_scope(executor.record, repair.record) and _intervals_overlap(
                executor.record,
                repair.record,
            ):
                return _make_reason(
                    AuditorReasonFamily.EXECUTOR_REPAIR_OVERLAP,
                    (executor, repair),
                    "Executor and repair activity overlapped for the same scope.",
                    {"scope": _scope_key(executor.record)},
                )
    return None


def _detect_cross_session_joins(records: Sequence[_IndexedRecord]) -> AuditorReason | None:
    for item in records:
        record = item.record
        left = _str_value(record, "left_session_id", "session_id")
        right = _str_value(record, "right_session_id", "joined_session_id", "source_session_id")
        if _explicit_family(record, AuditorReasonFamily.CROSS_SESSION_JOINS) or (
            left and right and left != right
        ):
            return _make_reason(
                AuditorReasonFamily.CROSS_SESSION_JOINS,
                (item,),
                "Evidence join crossed session identity.",
                {"left_session_id": left, "right_session_id": right},
            )
    return None


def _detect_projection_amplification(records: Sequence[_IndexedRecord]) -> AuditorReason | None:
    for item in records:
        record = item.record
        source_count = _float_value(record, "source_record_count", "input_count")
        output_count = _float_value(record, "projection_record_count", "output_count")
        limit = _float_value(record, "max_amplification_ratio", "amplification_limit")
        ratio = (output_count / source_count) if source_count and output_count is not None else None
        if _explicit_family(record, AuditorReasonFamily.PROJECTION_AMPLIFICATION) or (
            ratio is not None and limit is not None and ratio > limit
        ):
            return _make_reason(
                AuditorReasonFamily.PROJECTION_AMPLIFICATION,
                (item,),
                "Projection expanded source records beyond the allowed ratio.",
                {
                    "source_record_count": source_count,
                    "projection_record_count": output_count,
                    "ratio": ratio,
                    "limit": limit,
                },
            )
    return None


def _detect_full_seriality(records: Sequence[_IndexedRecord]) -> AuditorReason | None:
    for item in records:
        record = item.record
        parallelism = _int_value(record, "parallelism", "observed_parallelism")
        eligible = _int_value(record, "eligible_parallelism", "available_parallelism")
        total = _int_value(record, "total_tasks")
        serial = _int_value(record, "serial_tasks")
        fully_serial = bool(total and serial == total and total > 1)
        if _explicit_family(record, AuditorReasonFamily.FULL_SERIALITY) or (
            parallelism == 1 and eligible is not None and eligible > 1
        ) or fully_serial:
            return _make_reason(
                AuditorReasonFamily.FULL_SERIALITY,
                (item,),
                "Work that could run concurrently was fully serialized.",
                {
                    "parallelism": parallelism,
                    "eligible_parallelism": eligible,
                    "serial_tasks": serial,
                    "total_tasks": total,
                },
            )
    return None


def _detect_oversized_rework(records: Sequence[_IndexedRecord]) -> AuditorReason | None:
    for item in records:
        record = item.record
        rework = _float_value(record, "rework_bytes", "rework_delta", "changed_bytes")
        limit = _float_value(record, "max_rework_bytes", "rework_limit")
        if _explicit_family(record, AuditorReasonFamily.OVERSIZED_REWORK) or (
            rework is not None and limit is not None and rework > limit
        ):
            return _make_reason(
                AuditorReasonFamily.OVERSIZED_REWORK,
                (item,),
                "Rework size exceeded the configured bound.",
                {"rework": rework, "limit": limit},
            )
    return None


def _detect_invalid_model(records: Sequence[_IndexedRecord]) -> AuditorReason | None:
    for item in records:
        record = item.record
        model = _str_value(record, "model", "model_actual")
        status = _str_value(record, "model_status", "validation_status")
        valid_models = _value(record, "valid_models", "allowed_models")
        valid_set = {str(model_name) for model_name in valid_models or ()}
        if _explicit_family(record, AuditorReasonFamily.INVALID_MODEL) or (
            model and valid_set and model not in valid_set
        ) or status == "invalid":
            return _make_reason(
                AuditorReasonFamily.INVALID_MODEL,
                (item,),
                "Execution used a model outside the allowed model set.",
                {"model": model, "valid_models": sorted(valid_set), "status": status},
            )
    return None


def _detect_missing_ledger_coverage(records: Sequence[_IndexedRecord]) -> AuditorReason | None:
    for item in records:
        record = item.record
        missing = _value(record, "missing_work_classes", "missing_ledger_classes", "missing")
        expected = set(
            str(value)
            for value in _value(record, "expected_work_classes", "expected") or ()
        )
        observed = set(
            str(value)
            for value in _value(record, "observed_work_classes", "observed") or ()
        )
        computed_missing = sorted(expected - observed) if expected else []
        missing_values = [str(value) for value in (missing or computed_missing)]
        if _explicit_family(record, AuditorReasonFamily.MISSING_LEDGER_COVERAGE) or missing_values:
            return _make_reason(
                AuditorReasonFamily.MISSING_LEDGER_COVERAGE,
                (item,),
                "Work ledger coverage is missing required classes.",
                {"missing": sorted(missing_values)},
            )
    return None


def _first_explicit(
    records: Sequence[_IndexedRecord],
    family: AuditorReasonFamily,
) -> _IndexedRecord | None:
    for item in records:
        if _explicit_family(item.record, family):
            return item
    return None


def _scope_key(record: _Record) -> tuple[str, str, str, str]:
    return (
        _str_value(record, "environment", "environment_id"),
        _str_value(record, "session_id"),
        _str_value(record, "task_id", "task"),
        _str_value(record, "attempt_id", "attempt"),
    )


def _same_scope(left: _Record, right: _Record) -> bool:
    left_scope = _scope_key(left)
    right_scope = _scope_key(right)
    return any(left_scope) and left_scope == right_scope


def _interval(record: _Record) -> tuple[float, float] | None:
    start = _float_value(record, "start_ms")
    end = _float_value(record, "end_ms")
    if start is not None and end is not None:
        return (start, end)
    start_s = _str_value(record, "started_at", "start")
    end_s = _str_value(record, "ended_at", "end")
    if start_s and end_s:
        parsed_start = _parse_timestamp_ms(start_s)
        parsed_end = _parse_timestamp_ms(end_s)
        if parsed_start is not None and parsed_end is not None:
            return (parsed_start, parsed_end)
    return None


def _parse_timestamp_ms(value: str) -> float | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000
    except ValueError:
        return None


def _intervals_overlap(left: _Record, right: _Record) -> bool:
    left_interval = _interval(left)
    right_interval = _interval(right)
    if left_interval is None or right_interval is None:
        return False
    left_start, left_end = left_interval
    right_start, right_end = right_interval
    return max(left_start, right_start) < min(left_end, right_end)


_DETECTORS = {
    AuditorReasonFamily.CONSECUTIVE_NORMALIZED_BLOCKS: _detect_consecutive_normalized_blocks,
    AuditorReasonFamily.SIGNATURE_DRIFT: _detect_signature_drift,
    AuditorReasonFamily.UNCLOSED_CUSTODY: _detect_unclosed_custody,
    AuditorReasonFamily.INDEX_MISMATCH: _detect_index_mismatch,
    AuditorReasonFamily.DETECTION_SLO_BREACH: _detect_detection_slo_breach,
    AuditorReasonFamily.EXECUTOR_REPAIR_OVERLAP: _detect_executor_repair_overlap,
    AuditorReasonFamily.CROSS_SESSION_JOINS: _detect_cross_session_joins,
    AuditorReasonFamily.PROJECTION_AMPLIFICATION: _detect_projection_amplification,
    AuditorReasonFamily.FULL_SERIALITY: _detect_full_seriality,
    AuditorReasonFamily.OVERSIZED_REWORK: _detect_oversized_rework,
    AuditorReasonFamily.INVALID_MODEL: _detect_invalid_model,
    AuditorReasonFamily.MISSING_LEDGER_COVERAGE: _detect_missing_ledger_coverage,
}


_FIXTURES: dict[AuditorReasonFamily, tuple[dict[str, Any], ...]] = {
    AuditorReasonFamily.CONSECUTIVE_NORMALIZED_BLOCKS: (
        {
            "evidence_id": "ev-consecutive-block-1",
            "sequence": 10,
            "kind": "normalized_block",
            "status": "blocked",
            "normalized_signature": "missing-ledger-seq",
        },
        {
            "evidence_id": "ev-consecutive-block-2",
            "sequence": 11,
            "kind": "normalized_block",
            "status": "blocked",
            "normalized_signature": "missing-ledger-seq",
        },
    ),
    AuditorReasonFamily.SIGNATURE_DRIFT: (
        {
            "evidence_id": "ev-signature-drift",
            "sequence": 20,
            "kind": "signature_check",
            "auditor_reason_family": "signature_drift",
            "expected_signature": "sha256:expected",
            "observed_signature": "sha256:observed",
        },
    ),
    AuditorReasonFamily.UNCLOSED_CUSTODY: (
        {
            "evidence_id": "ev-unclosed-custody",
            "sequence": 30,
            "kind": "custody_lease",
            "action": "opened",
            "custody_id": "lease-1",
        },
    ),
    AuditorReasonFamily.INDEX_MISMATCH: (
        {
            "evidence_id": "ev-index-mismatch",
            "sequence": 40,
            "kind": "index_check",
            "expected_index": 7,
            "observed_index": 5,
        },
    ),
    AuditorReasonFamily.DETECTION_SLO_BREACH: (
        {
            "evidence_id": "ev-detection-slo",
            "sequence": 50,
            "kind": "detection_check",
            "detection_latency_ms": 65_000,
            "detection_slo_ms": 60_000,
        },
    ),
    AuditorReasonFamily.EXECUTOR_REPAIR_OVERLAP: (
        {
            "evidence_id": "ev-executor-active",
            "sequence": 60,
            "kind": "executor_active",
            "environment": "prod",
            "session_id": "session-a",
            "task_id": "T1",
            "attempt_id": "attempt-1",
            "start_ms": 1_000,
            "end_ms": 5_000,
        },
        {
            "evidence_id": "ev-repair-active",
            "sequence": 61,
            "kind": "repair_active",
            "environment": "prod",
            "session_id": "session-a",
            "task_id": "T1",
            "attempt_id": "attempt-1",
            "start_ms": 3_000,
            "end_ms": 6_000,
        },
    ),
    AuditorReasonFamily.CROSS_SESSION_JOINS: (
        {
            "evidence_id": "ev-cross-session-join",
            "sequence": 70,
            "kind": "join_check",
            "left_session_id": "session-a",
            "right_session_id": "session-b",
        },
    ),
    AuditorReasonFamily.PROJECTION_AMPLIFICATION: (
        {
            "evidence_id": "ev-projection-amplification",
            "sequence": 80,
            "kind": "projection_rebuild",
            "source_record_count": 3,
            "projection_record_count": 25,
            "max_amplification_ratio": 4,
        },
    ),
    AuditorReasonFamily.FULL_SERIALITY: (
        {
            "evidence_id": "ev-full-seriality",
            "sequence": 90,
            "kind": "scheduling_check",
            "parallelism": 1,
            "eligible_parallelism": 4,
        },
    ),
    AuditorReasonFamily.OVERSIZED_REWORK: (
        {
            "evidence_id": "ev-oversized-rework",
            "sequence": 100,
            "kind": "rework_check",
            "rework_bytes": 12_000,
            "max_rework_bytes": 4_000,
        },
    ),
    AuditorReasonFamily.INVALID_MODEL: (
        {
            "evidence_id": "ev-invalid-model",
            "sequence": 110,
            "kind": "model_check",
            "model": "unsupported-model",
            "valid_models": ["gpt-5.5", "claude-sonnet-4-6"],
        },
    ),
    AuditorReasonFamily.MISSING_LEDGER_COVERAGE: (
        {
            "evidence_id": "ev-missing-ledger-coverage",
            "sequence": 120,
            "kind": "ledger_coverage",
            "expected_work_classes": ["productive", "review_proof", "replay"],
            "observed_work_classes": ["productive"],
        },
    ),
}


__all__ = [
    "AuditorReason",
    "AuditorReasonFamily",
    "REASON_ORDER",
    "auditor_reason_fixture",
    "auditor_reason_fixtures",
    "reduce_auditor_reasons",
]
