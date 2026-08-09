"""Non-authoritative one-time import of legacy r5 NDJSON evidence.

Legacy r5 records are imported as **non-authoritative historical context**:
persisted (so all available legacy evidence is preserved) but never entering
the v1 replay pipeline and never carrying positive authority.

Filter-and-tag model (North Star: immutability forbids version rewriting):

* The original ``schema_version`` is preserved byte-for-byte -- **never**
  upgraded to ``cl.schema.v1``.
* Each record is tagged ``cl2_kind = "legacy_historical"`` and
  ``envelope.metadata.derived_from_legacy = True``.
* The importer **bypasses** ``persist_occurrence`` /
  ``CritiqueOccurrenceEnvelope.from_dict`` (both hard-reject non-v1 schema
  versions); it builds the ``EXTERNAL_EFFECT_OUTCOME`` payload directly and
  appends via ``store.append_event``.
* Missing evidence is labelled
  ``evidence_availability = EvidenceAvailability.UNAVAILABLE.value`` with
  ``unavailable_reason = "legacy_import"`` -- a labelling convention; the
  ``cl2_kind`` discriminator is the sole operative defense (it excludes these
  records from the replay partition before ``semantic_loop.replay_full``).
* Every record routes through ``IndependentChildDisposition`` (never migrated).
* Stable epoch-prefixed canonical SHA-256 IDs make the same record distinct
  across epochs and make re-import idempotent within an epoch.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from arnold.critique_ledger.persistence_service import (
    LedgerEventContext,
    LedgerEventMapper,
)
from arnold.critique_ledger.schemas import (
    SCHEMA_VERSION,
    SUPPORTED_VERSIONS,
    EvidenceAvailability,
    ParseStatus,
    canonical_hash,
)
from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import AttemptEventType
from arnold_pipelines.megaplan.custody.contracts import (
    normalize_custody_target_key,
    normalize_repair_occurrence_key,
)
from arnold_pipelines.megaplan.migration import (
    ChildIdentity,
    ChildSelector,
    IndependentChildDisposition,
)

#: The discriminator stamped on every imported legacy record.
CL2_KIND_LEGACY_HISTORICAL = "legacy_historical"

#: Reason stamped on missing-evidence legacy records.
LEGACY_UNAVAILABLE_REASON = "legacy_import"

#: Payload keys whose presence indicates retained evidence in a legacy record.
_EVIDENCE_KEYS = (
    "evidence_ref",
    "evidence",
    "redacted_prompt_hash",
    "raw_prompt_hash",
    "raw_completion_hash",
)


@dataclass(frozen=True)
class ImportReport:
    """Outcome of a one-time legacy NDJSON import."""

    total_records: int
    imported: int
    skipped_duplicates: int
    epoch_prefixes: tuple[int, ...]
    legacy_unavailable_count: int
    errors: tuple[str, ...]
    derived_from_legacy_count: int

    @property
    def epoch_prefixes_set(self) -> frozenset[int]:
        return frozenset(self.epoch_prefixes)


@dataclass
class _ImportAccumulator:
    total_records: int = 0
    imported: int = 0
    skipped_duplicates: int = 0
    legacy_unavailable_count: int = 0
    errors: list[str] = field(default_factory=list)
    derived_from_legacy_count: int = 0
    epoch_prefixes: set[int] = field(default_factory=set)

    def to_report(self) -> ImportReport:
        return ImportReport(
            total_records=self.total_records,
            imported=self.imported,
            skipped_duplicates=self.skipped_duplicates,
            epoch_prefixes=tuple(sorted(self.epoch_prefixes)),
            legacy_unavailable_count=self.legacy_unavailable_count,
            errors=tuple(self.errors),
            derived_from_legacy_count=self.derived_from_legacy_count,
        )


class OneTimeImporter:
    """One-time, idempotent importer of legacy r5 NDJSON evidence.

    The importer is non-authoritative: imported records carry
    ``cl2_kind = legacy_historical`` and ``derived_from_legacy = True`` and are
    excluded from the v1 replay partition.  It never calls
    ``persist_occurrence`` or ``CritiqueOccurrenceEnvelope.from_dict``.
    """

    def __init__(
        self,
        store: SqliteAttemptLedgerStore,
        *,
        target_schema: str = SCHEMA_VERSION,
        admissible_target_schemas: frozenset[str] | None = None,
    ) -> None:
        self._store = store
        self._target_schema = target_schema
        self._admissible = admissible_target_schemas or frozenset(SUPPORTED_VERSIONS)

    # ── normalization ──────────────────────────────────────────────────────

    @staticmethod
    def _normalize_key(
        record: Mapping[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Return ``(repair_key_dict, custody_key_dict)`` normalized forms.

        Either may be ``None``; the custody key is derived from the repair
        key's target when only the 10-field form is present.
        """
        repair = normalize_repair_occurrence_key(record)
        custody = normalize_custody_target_key(record)
        repair_dict = repair.to_dict() if repair is not None else None
        custody_dict = custody.to_dict() if custody is not None else None
        # Derive custody key from the repair key's target when only the
        # 10-field form is present.
        if custody_dict is None and repair is not None:
            custody_dict = repair.target.to_dict()
        return repair_dict, custody_dict

    @staticmethod
    def _has_evidence(record: Mapping[str, Any]) -> bool:
        if record.get("evidence_available") is True:
            return True
        return any(
            bool(record.get(key)) for key in _EVIDENCE_KEYS
        )

    @staticmethod
    def _canonical_digest(record: Mapping[str, Any]) -> str:
        """Stable SHA-256 over the canonical JSON of the record."""
        return canonical_hash(dict(record))

    def _epoch_event_id(self, epoch: int, digest: str) -> str:
        """Epoch-prefixed canonical SHA-256 event id."""
        return f"legacy-{epoch}-{digest}"

    def _epoch_idempotency_key(self, epoch: int, digest: str) -> str:
        return f"{CL2_KIND_LEGACY_HISTORICAL}:{epoch}:{digest}"

    # ── envelope construction (bypasses from_dict) ─────────────────────────

    def _build_envelope(
        self,
        record: Mapping[str, Any],
        *,
        attempt_id: str,
        epoch: int,
        digest: str,
        repair_key: Mapping[str, Any] | None,
        custody_key: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        """Build the legacy_historical envelope dict directly.

        The original ``schema_version`` is preserved byte-for-byte (never
        upgraded) and missing evidence is labelled ``UNAVAILABLE``.
        """
        # Preserve the ORIGINAL schema_version exactly; default only when absent.
        schema_version = record.get("schema_version", "cl.m6-corpus.v1")

        has_evidence = self._has_evidence(record)
        evidence_availability = (
            EvidenceAvailability.RETAINED.value
            if has_evidence
            else EvidenceAvailability.UNAVAILABLE.value
        )

        metadata: dict[str, Any] = {
            "derived_from_legacy": True,
            "legacy_epoch": epoch,
            "legacy_canonical_digest": digest,
            "authority_migration": "not_performed",
        }
        if repair_key is not None:
            metadata["normalized_repair_occurrence_key"] = dict(repair_key)
        if custody_key is not None:
            metadata["normalized_custody_target_key"] = dict(custody_key)

        envelope: dict[str, Any] = {
            "schema_version": schema_version,
            "occurrence_id": self._epoch_event_id(epoch, digest),
            "attempt_id": attempt_id,
            "round_label": str(record.get("round_label", "legacy")),
            "finding_id": str(record.get("finding_id", "")),
            "semantic_finding_id": str(record.get("semantic_finding_id", "")),
            "producer_id": str(record.get("producer_id", "legacy-r5")),
            "model_id": str(record.get("model_id", "")),
            "parse_status": ParseStatus.SELECTED.value,
            "evidence_availability": evidence_availability,
            "metadata": metadata,
        }
        if not has_evidence:
            envelope["unavailable_reason"] = LEGACY_UNAVAILABLE_REASON
        for key in _EVIDENCE_KEYS:
            if record.get(key):
                envelope[key] = record[key]
        return envelope

    def _route_independent_child(
        self,
        *,
        digest: str,
        attempt_id: str,
        context: LedgerEventContext,
        custody_key: Mapping[str, Any] | None,
    ) -> IndependentChildDisposition:
        """Route the record as an independent child (never migrated).

        Documents that the legacy parent has no RA owner (historical context).
        """
        child_revision = context.versions.code_version
        selector_payload: dict[str, Any] = (
            dict(custody_key) if custody_key is not None else {"digest": digest}
        )
        selector = ChildSelector(
            child_revision=child_revision, selector=selector_payload
        )
        child = ChildIdentity(
            parent_occurrence_digest=f"sha256:{digest}",
            selector_digest=selector.selector_digest,
            child_revision=child_revision,
            child_run_id=context.identity.run_id,
            coordinator_attempt_id=attempt_id,
            subject_attempt_id=attempt_id,
            wbc_attempt_id=context.grant_ref.grant_id,
            glek=f"sha256:{digest}",
            migration_idempotency_key=self._epoch_idempotency_key(
                0, digest
            ),
        )
        return IndependentChildDisposition(
            child=child,
            selector=selector,
            parent_occurrence_digest=f"sha256:{digest}",
            reason=(
                "legacy r5 import: no Run Authority owner; routed as "
                "independent child (historical context, not migrated)"
            ),
        )

    def import_ndjson(
        self,
        path: Path,
        *,
        epoch: int,
        attempt_id: str,
        context: LedgerEventContext,
    ) -> ImportReport:
        """Import legacy r5 NDJSON evidence line by line.

        Requires prior STARTED + EXTERNAL_EFFECT_INTENT.  Idempotent within
        an epoch: re-importing the same file appends zero new records.
        """
        acc = _ImportAccumulator()
        acc.epoch_prefixes.add(epoch)

        with Path(path).open("r", encoding="utf-8") as handle:
            for line_no, raw in enumerate(handle, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                acc.total_records += 1
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError as exc:
                    acc.errors.append(
                        f"line {line_no}: invalid JSON: {exc}"
                    )
                    continue
                if not isinstance(record, dict):
                    acc.errors.append(
                        f"line {line_no}: expected JSON object, got "
                        f"{type(record).__name__}"
                    )
                    continue

                # Reject unsupported target_schema BEFORE any write — no
                # partial publication of an unsupported target version.
                target = record.get("target_schema")
                if target is not None and target not in self._admissible:
                    acc.errors.append(
                        f"line {line_no}: unsupported target_schema "
                        f"{target!r}; record skipped without publication"
                    )
                    continue

                self._import_record(
                    record,
                    epoch=epoch,
                    attempt_id=attempt_id,
                    context=context,
                    line_no=line_no,
                    acc=acc,
                )

        return acc.to_report()

    def _import_record(
        self,
        record: Mapping[str, Any],
        *,
        epoch: int,
        attempt_id: str,
        context: LedgerEventContext,
        line_no: int,
        acc: _ImportAccumulator,
    ) -> None:
        digest = self._canonical_digest(record)
        repair_key, custody_key = self._normalize_key(record)

        # Route through IndependentChildDisposition (never migrate).
        disposition = self._route_independent_child(
            digest=digest,
            attempt_id=attempt_id,
            context=context,
            custody_key=custody_key,
        )

        envelope = self._build_envelope(
            record,
            attempt_id=attempt_id,
            epoch=epoch,
            digest=digest,
            repair_key=repair_key,
            custody_key=custody_key,
        )
        envelope["metadata"]["independent_child_disposition"] = {
            "action": disposition.action,
            "reason": disposition.reason,
            "requires_human_approval": disposition.requires_human_approval,
        }

        has_evidence = envelope["evidence_availability"] != (
            EvidenceAvailability.UNAVAILABLE.value
        )
        if not has_evidence:
            acc.legacy_unavailable_count += 1

        # Append the raw legacy_historical outcome DIRECTLY via the store,
        # bypassing persist_occurrence/from_dict; the store enforces
        # monotonicity and idempotency.
        sequence = self._store.last_sequence(attempt_id) + 1
        event = LedgerEventMapper._event(
            event_type=AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
            idempotency_key=self._epoch_idempotency_key(epoch, digest),
            context=context,
            sequence=sequence,
            payload={
                "cl2_kind": CL2_KIND_LEGACY_HISTORICAL,
                "envelope": envelope,
            },
        )
        result = self._store.append_event(attempt_id, event)
        if result.is_duplicate:
            acc.skipped_duplicates += 1
        else:
            acc.imported += 1
        # Every processed record is derived-from-legacy (tagged above).
        acc.derived_from_legacy_count += 1


__all__ = [
    "CL2_KIND_LEGACY_HISTORICAL",
    "ImportReport",
    "LEGACY_UNAVAILABLE_REASON",
    "OneTimeImporter",
]
