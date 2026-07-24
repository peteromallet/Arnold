from __future__ import annotations

import ast
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Mapping

from arnold_pipelines.megaplan._core import (
    atomic_write_text,
    batch_artifact_index,
    is_creative_mode,
    is_prose_mode,
    list_batch_artifacts,
    read_json,
    render_final_md,
)
from arnold_pipelines.megaplan.authority.batch_scope import (
    BatchScopeQuarantine,
    DISPATCH_IDENTITY_KEY,
    RESULT_ENVELOPES_KEY,
    resolve_batch_authority_metadata,
    resolve_batch_scope,
)
from arnold_pipelines.megaplan.authority.binding import (
    ResultEnvelope,
    SENSE_CHECK_ACK_CLAIM,
    SENSE_CHECK_RESULT_CAPABILITY,
    TASK_COMPLETION_CLAIM,
    TASK_RESULT_CAPABILITY,
)
from arnold_pipelines.megaplan.store import write_plan_artifact_json
from arnold_pipelines.megaplan.forms.stance import validate_stance
from arnold_pipelines.megaplan.types import PlanState
from arnold_pipelines.megaplan.execute.status_constants import (
    EXECUTE_TASK_STATUS_ALIASES,
    TERMINAL_TASK_STATUSES,
)
from arnold_pipelines.run_authority import ContractError, IdempotencyConflict


# Common field name aliases that models use instead of the canonical names.
# Models often use finalize.json's field names (e.g. "id") instead of the
# execute schema's names (e.g. "task_id").
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "task_id": ("id", "taskId", "task"),
    "sense_check_id": ("id", "senseCheckId", "check_id"),
    "executor_notes": ("notes", "executor_note", "note"),
    "executor_note": ("notes", "executor_notes", "note"),
    "concern": ("summary", "description", "issue", "finding"),
    "evidence": ("detail", "details", "explanation", "reasoning"),
}


# Normalize enum values to canonical forms — sourced from the shared
# status_constants module so merge-time aliasing and capture pre-processing
# (model_seam / batch) use the same single source of truth.
_VALUE_ALIASES: dict[str, dict[str, str]] = {
    "status": dict(EXECUTE_TASK_STATUS_ALIASES),
}


_DEVIATION_BLOCKING_PHRASES: tuple[str, ...] = (
    "patch artifact",
    "patch_artifact",
    "patch_corruption",
    "budget exhausted",
    "iteration budget",
    "context budget",
    "out of context",
    # Deliberately do not keyword-match "syntax error"/"syntaxerror" in prose:
    # a task may describe a syntax error it already fixed. Real current Python
    # syntax failures are caught by _validate_python_file_for_task below.
)


GrantAwareValidationOutcome = Literal[
    "accepted",
    "rejected",
    "quarantined",
    "duplicate-idempotent",
    "superseded-or-conflicting",
]


@dataclass(frozen=True, slots=True)
class GrantAwareValidationDecision:
    """One auditable merge-authority decision for a worker result row."""

    outcome: GrantAwareValidationOutcome
    entry_kind: str
    entry_index: int
    subject_id: str | None
    reason: str
    idempotency_key: str | None = None
    envelope_digest: str | None = None
    source_path: str | None = None

    @property
    def accepted_for_merge(self) -> bool:
        return self.outcome == "accepted"

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "entry_kind": self.entry_kind,
            "entry_index": self.entry_index,
            "subject_id": self.subject_id,
            "reason": self.reason,
            "idempotency_key": self.idempotency_key,
            "envelope_digest": self.envelope_digest,
            "source_path": self.source_path,
        }


@dataclass(frozen=True, slots=True)
class _GrantAwareValidationResult:
    entries: list[Any]
    decisions: tuple[GrantAwareValidationDecision, ...]


@dataclass(frozen=True, slots=True)
class _ScopedBatchArtifactMergeResult:
    payload: dict[str, Any] | None = None
    scope_task_ids: tuple[str, ...] = ()
    scope_sense_check_ids: tuple[str, ...] = ()
    merged_task_count: int = 0
    total_task_count: int = 0
    acknowledged_sense_check_count: int = 0
    total_sense_check_count: int = 0
    issues: tuple[str, ...] = ()
    quarantine: BatchScopeQuarantine | None = None

    @property
    def reconciled(self) -> bool:
        return self.quarantine is None


def _append_executor_note(task: dict[str, Any], note: str) -> None:
    existing = task.get("executor_notes")
    if isinstance(existing, str) and existing:
        task["executor_notes"] = f"{existing}\n{note}"
    else:
        task["executor_notes"] = note


def _is_blocking_deviation(deviation: str) -> str | None:
    normalized = deviation.casefold()
    for phrase in _DEVIATION_BLOCKING_PHRASES:
        if phrase in normalized:
            return phrase
    if "correctness" in normalized and "failed" in normalized:
        return "correctness failed"
    if "unfinished" in normalized and "task" in normalized:
        return "unfinished task"
    return None


def _task_deviation_strings(task: dict[str, Any], issues: list[str]) -> list[str]:
    task_deviations = [
        deviation
        for deviation in task.get("deviations", [])
        if isinstance(deviation, str)
    ]
    task_id = task.get("id")
    if not isinstance(task_id, str) or not task_id:
        return task_deviations
    return task_deviations + [
        deviation
        for deviation in issues
        if isinstance(deviation, str) and task_id in deviation
    ]


def _validate_python_file_for_task(task: dict[str, Any], issues: list[str]) -> None:
    for file_name in task.get("files_changed", []) or []:
        if not isinstance(file_name, str) or not file_name.endswith(".py"):
            continue
        path = Path(file_name)
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
            ast.parse(content, filename=str(path))
        except UnicodeDecodeError:
            message = f"patch_corruption: {file_name}: file not valid UTF-8"
        except SyntaxError as exc:
            line = exc.lineno or "unknown"
            message = f"patch_corruption: {file_name} line {line}: {exc.msg}"
        else:
            continue
        task["status"] = "blocked"
        _append_executor_note(task, f"[harness] {message}")
        issues.append(message)


def _apply_task_update_guardrails(
    entries: list[dict[str, Any]],
    *,
    targets_by_id: dict[str, dict[str, Any]],
    id_field: str,
    merge_fields: tuple[str, ...],
    issues: list[str],
) -> None:
    if id_field != "task_id" or "files_changed" not in merge_fields:
        return
    task_ids = {
        entry[id_field]
        for entry in entries
        if isinstance(entry.get(id_field), str)
    }
    for task_id in task_ids:
        task = targets_by_id.get(task_id)
        if task is None:
            continue
        _validate_python_file_for_task(task, issues)
    for task_id in task_ids:
        task = targets_by_id.get(task_id)
        if task is None or task.get("status") not in {"done", "blocked"}:
            continue
        for deviation in _task_deviation_strings(task, issues):
            matched = _is_blocking_deviation(deviation)
            if matched is None:
                continue
            task["status"] = "blocked"
            _append_executor_note(
                task,
                f"[harness] status auto-downgraded: deviation contains {matched}",
            )
            break


def _normalize_field_aliases(entry: dict[str, Any], required_fields: tuple[str, ...]) -> dict[str, Any]:
    """Copy aliased field values to canonical names if the canonical name is missing,
    and normalize enum value synonyms."""
    for field in required_fields:
        if field in entry:
            continue
        aliases = _FIELD_ALIASES.get(field, ())
        for alias in aliases:
            if alias in entry:
                entry[field] = entry[alias]
                break
    # Default missing array fields to [] and missing string fields to ""
    # rather than rejecting. Models often omit empty arrays/strings.
    for field in required_fields:
        if field not in entry:
            if field in ("files_changed", "commands_run"):
                entry[field] = []
            elif field in ("executor_notes", "executor_note"):
                entry[field] = "(not provided)"
    # Normalize enum value aliases
    for field, value_map in _VALUE_ALIASES.items():
        if field in entry and isinstance(entry[field], str):
            canonical = value_map.get(entry[field])
            if canonical is not None:
                entry[field] = canonical
    return entry


def _validate_merge_inputs(
    entries: Any,
    *,
    required_fields: tuple[str, ...],
    optional_fields: tuple[str, ...] = (),
    enum_fields: dict[str, set[str]] | None = None,
    nonempty_fields: set[str] | None = None,
    array_fields: tuple[str, ...] = (),
    object_fields: tuple[str, ...] = (),
    deviations: list[str] | None = None,
    label: str,
) -> list[dict[str, Any]]:
    enum_fields = enum_fields or {}
    nonempty_fields = nonempty_fields or set()
    array_field_set = set(array_fields)
    object_field_set = set(object_fields)
    valid_entries: list[dict[str, Any]] = []
    if not isinstance(entries, list):
        return valid_entries
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            if deviations is not None:
                deviations.append(f"Skipped malformed {label}[{index}]: expected object.")
            continue
        # Normalize field aliases before checking required fields
        _normalize_field_aliases(entry, required_fields)
        if any(field not in entry for field in required_fields):
            if deviations is not None:
                deviations.append(f"Skipped malformed {label}[{index}]: missing required keys.")
            continue
        normalized: dict[str, Any] = {}
        malformed = False
        present_optional_fields = tuple(field for field in optional_fields if field in entry)
        for field in (*required_fields, *present_optional_fields):
            value = entry[field]
            if field in array_field_set:
                if not isinstance(value, list):
                    malformed = True
                    break
                normalized[field] = list(value)
                continue
            if field in object_field_set:
                if not isinstance(value, dict):
                    malformed = True
                    break
                normalized[field] = dict(value)
                continue
            if not isinstance(value, str):
                malformed = True
                break
            allowed = enum_fields.get(field)
            if allowed is not None and value not in allowed:
                malformed = True
                break
            normalized[field] = value
        if malformed:
            if deviations is not None:
                deviations.append(f"Skipped malformed {label}[{index}]: invalid field types or enum values.")
            continue
        empty_field = next((field for field in nonempty_fields if normalized.get(field, "").strip() == ""), None)
        if empty_field is not None:
            if deviations is not None:
                deviations.append(f"Skipped {label}[{index}]: '{empty_field}' must not be empty.")
            continue
        valid_entries.append(normalized)
    return valid_entries


def _payload_has_authority_metadata(payload: Mapping[str, Any]) -> bool:
    return DISPATCH_IDENTITY_KEY in payload or RESULT_ENVELOPES_KEY in payload


def _entry_authority(entry: Mapping[str, Any]) -> Mapping[str, Any]:
    authority = entry.get("authority")
    return authority if isinstance(authority, Mapping) else {}


def _authority_digest(entry: Mapping[str, Any]) -> str | None:
    digest = _entry_authority(entry).get("envelope_digest")
    return digest if isinstance(digest, str) and digest.strip() else None


def _entry_subject_id(entry: Mapping[str, Any], id_field: str) -> str | None:
    value = entry.get(id_field)
    if isinstance(value, str) and value.strip():
        return value
    for alias in _FIELD_ALIASES.get(id_field, ()):
        alias_value = entry.get(alias)
        if isinstance(alias_value, str) and alias_value.strip():
            return alias_value
    return None


def _state_string_at(state: PlanState | None, *paths: tuple[str, ...]) -> str | None:
    if not isinstance(state, Mapping):
        return None
    for path in paths:
        current: Any = state
        for part in path:
            if not isinstance(current, Mapping):
                current = None
                break
            current = current.get(part)
        if isinstance(current, str) and current.strip():
            return current
    return None


def _state_int_at(state: PlanState | None, *paths: tuple[str, ...]) -> int | None:
    if not isinstance(state, Mapping):
        return None
    for path in paths:
        current: Any = state
        for part in path:
            if not isinstance(current, Mapping):
                current = None
                break
            current = current.get(part)
        if isinstance(current, int) and not isinstance(current, bool) and current >= 0:
            return current
    return None


def _expected_plan_revision(state: PlanState | None) -> str | None:
    revision = _state_string_at(
        state,
        ("run_revision",),
        ("plan_revision",),
        ("meta", "run_revision"),
        ("meta", "plan_revision"),
        ("active_step", "run_revision"),
    )
    if revision is not None:
        return revision
    if isinstance(state, Mapping):
        versions = state.get("plan_versions")
        if isinstance(versions, list) and versions:
            latest = versions[-1]
            if isinstance(latest, Mapping):
                for key in ("hash", "file"):
                    value = latest.get(key)
                    if isinstance(value, str) and value.strip():
                        return value
    return None


def _expected_coordinator_attempt_id(state: PlanState | None) -> str | None:
    return _state_string_at(
        state,
        ("coordinator_attempt_id",),
        ("meta", "coordinator_attempt_id"),
        ("active_step", "run_id"),
    )


def _expected_fence_token(state: PlanState | None) -> int | None:
    return _state_int_at(
        state,
        ("fence_token",),
        ("meta", "fence_token"),
        ("active_step", "attempt"),
    )


def _expected_authority_cursor(state: PlanState | None) -> int | None:
    return _state_int_at(
        state,
        ("authority_journal_cursor",),
        ("meta", "authority_journal_cursor"),
        ("meta", "run_authority", "journal_cursor"),
        ("authority", "journal_cursor"),
    )


def _expected_prerequisite_digest(state: PlanState | None) -> str | None:
    return _state_string_at(
        state,
        ("prerequisite_digest",),
        ("meta", "prerequisite_digest"),
        ("execute", "prerequisite_digest"),
    )


def _expected_worker_id(state: PlanState | None) -> str | None:
    return _state_string_at(
        state,
        ("worker_id",),
        ("meta", "worker_id"),
        ("execute", "worker_id"),
    )


def _same_string_set(left: Any, right: tuple[str, ...]) -> bool:
    if not isinstance(left, (list, tuple)):
        return False
    return {item for item in left if isinstance(item, str)} == set(right)


def _validate_authority_echo(
    *,
    entry: Mapping[str, Any],
    envelope: ResultEnvelope,
    expected_capability: str,
) -> str | None:
    authority = _entry_authority(entry)
    if not authority:
        return None
    checks: tuple[tuple[str, Any], ...] = (
        ("dispatch_id", envelope.dispatch_id),
        ("run_revision", envelope.run_revision),
        ("plan_revision", envelope.plan_revision),
        ("prerequisite_digest", envelope.prerequisite_digest),
        ("worker_id", envelope.worker_id),
    )
    for field, expected in checks:
        value = authority.get(field)
        if value is not None and value != expected:
            return f"{field}_echo_mismatch"
    raw_fence = authority.get("fence")
    if raw_fence is not None and raw_fence != envelope.dispatch.fence.to_dict():
        return "coordinator_fence_echo_mismatch"
    raw_scope = authority.get("scope")
    if isinstance(raw_scope, Mapping):
        if "subject_ids" in raw_scope and not _same_string_set(
            raw_scope.get("subject_ids"), envelope.dispatch.subject_ids
        ):
            return "subject_scope_echo_mismatch"
        capabilities = raw_scope.get("capabilities")
        capability_values = {
            item for item in capabilities if isinstance(item, str)
        } if isinstance(capabilities, (list, tuple)) else set()
        if capabilities is not None and (
            not _same_string_set(capabilities, envelope.dispatch.capabilities)
            or expected_capability not in capability_values
        ):
            return "capability_scope_echo_mismatch"
    raw_attempt = authority.get("attempt")
    if raw_attempt is not None and raw_attempt != envelope.attempt.to_dict():
        return "attempt_identity_echo_mismatch"
    return None


def _validate_evidence_refs(envelope: ResultEnvelope) -> str | None:
    evidence_by_id = {item.evidence_id: item for item in envelope.evidence}
    if len(evidence_by_id) != len(envelope.evidence):
        return "duplicate_evidence_ref"
    missing = [item for item in envelope.evidence_ids if item not in evidence_by_id]
    if missing:
        return "missing_evidence_ref"
    for evidence in envelope.evidence:
        if (
            evidence.run_id != envelope.run_id
            or evidence.run_revision != envelope.run_revision
        ):
            return "evidence_identity_mismatch"
    return None


def _validate_cas_expectations(
    envelope: ResultEnvelope,
    *,
    state: PlanState | None,
) -> str | None:
    cursor = _expected_authority_cursor(state)
    expectations = [
        item
        for item in (envelope.dispatch.cas_expectation, envelope.cas_expectation)
        if item is not None
    ]
    for expectation in expectations:
        try:
            expectation.assert_matches(
                run_id=envelope.run_id,
                revision=envelope.run_revision,
                cursor=expectation.expected_cursor if cursor is None else cursor,
            )
        except ContractError:
            return "cas_expectation_mismatch"
    if len(expectations) == 2 and expectations[0].digest() != expectations[1].digest():
        return "cas_expectation_conflict"
    return None


def _validate_entry_against_envelope(
    *,
    entry: Mapping[str, Any],
    entry_kind: str,
    id_field: str,
    subject_id: str,
    envelope: ResultEnvelope,
    target_subject_ids: set[str],
    expected_claim_type: str,
    expected_capability: str,
    state: PlanState | None,
) -> tuple[GrantAwareValidationOutcome, str]:
    if subject_id not in target_subject_ids:
        return "rejected", "subject_outside_dispatched_batch"
    if envelope.subject_id != subject_id:
        return "rejected", "result_envelope_subject_mismatch"
    if envelope.claim.claim_type != expected_claim_type:
        return "rejected", "result_envelope_claim_type_mismatch"
    if envelope.dispatch_id != envelope.claim.grant_id:
        return "quarantined", "dispatch_id_mismatch"
    if subject_id not in envelope.dispatch.subject_ids:
        return "rejected", "subject_outside_dispatch_scope"
    if expected_capability not in envelope.dispatch.capabilities:
        return "rejected", "dispatch_capability_missing"

    expected_revision = _expected_plan_revision(state)
    if expected_revision is not None and envelope.plan_revision != expected_revision:
        return "superseded-or-conflicting", "plan_revision_mismatch"
    expected_coordinator = _expected_coordinator_attempt_id(state)
    if (
        expected_coordinator is not None
        and envelope.dispatch.coordinator_attempt_id != expected_coordinator
    ):
        return "superseded-or-conflicting", "coordinator_fence_mismatch"
    expected_fence = _expected_fence_token(state)
    if expected_fence is not None and envelope.dispatch.fence_token != expected_fence:
        return "superseded-or-conflicting", "coordinator_fence_mismatch"
    expected_prereq = _expected_prerequisite_digest(state)
    if expected_prereq is not None and envelope.prerequisite_digest != expected_prereq:
        return "superseded-or-conflicting", "prerequisite_digest_mismatch"
    expected_worker = _expected_worker_id(state)
    if expected_worker is not None and envelope.worker_id != expected_worker:
        return "rejected", "worker_identity_mismatch"

    echo_reason = _validate_authority_echo(
        entry=entry,
        envelope=envelope,
        expected_capability=expected_capability,
    )
    if echo_reason is not None:
        return "rejected", echo_reason
    evidence_reason = _validate_evidence_refs(envelope)
    if evidence_reason is not None:
        return "quarantined", evidence_reason
    cas_reason = _validate_cas_expectations(envelope, state=state)
    if cas_reason is not None:
        return "superseded-or-conflicting", cas_reason
    return "accepted", f"{entry_kind}_authority_valid"


def _grant_aware_validate_entries(
    entries: Any,
    *,
    payload: Mapping[str, Any],
    target_subject_ids: set[str],
    id_field: str,
    entry_kind: str,
    expected_claim_type: str,
    expected_capability: str,
    issues: list[str],
    state: PlanState | None,
    source_path: str | Path = "<merge-payload>",
    off_scope_outcome: GrantAwareValidationOutcome = "rejected",
) -> _GrantAwareValidationResult:
    if not isinstance(entries, list):
        return _GrantAwareValidationResult([], ())
    source = str(source_path)
    if not _payload_has_authority_metadata(payload):
        accepted_entries: list[dict[str, Any]] = []
        decisions: list[GrantAwareValidationDecision] = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            subject_id = _entry_subject_id(entry, id_field)
            if (
                off_scope_outcome == "quarantined"
                and subject_id is not None
                and subject_id not in target_subject_ids
            ):
                decision = GrantAwareValidationDecision(
                    outcome="quarantined",
                    entry_kind=entry_kind,
                    entry_index=index,
                    subject_id=subject_id,
                    reason="subject_outside_dispatched_batch",
                    source_path=source,
                )
                entry["authority_validation"] = decision.to_dict()
                issues.append(
                    f"Grant-aware validation quarantined {entry_kind}[{decision.entry_index}]"
                    f" for {decision.subject_id}: {decision.reason}"
                    f" (source: {decision.source_path})."
                )
            else:
                decision = GrantAwareValidationDecision(
                    outcome="accepted",
                    entry_kind=entry_kind,
                    entry_index=index,
                    subject_id=subject_id,
                    reason="legacy_no_authority_metadata",
                    source_path=source,
                )
                accepted_entries.append(entry)
            decisions.append(decision)
        return _GrantAwareValidationResult(accepted_entries, tuple(decisions))

    authority_resolution = resolve_batch_authority_metadata(payload, source)
    if authority_resolution.quarantine is not None:
        decisions = tuple(
            GrantAwareValidationDecision(
                outcome="quarantined",
                entry_kind=entry_kind,
                entry_index=index,
                subject_id=_entry_subject_id(entry, id_field) if isinstance(entry, Mapping) else None,
                reason=authority_resolution.quarantine.reason,
                source_path=authority_resolution.quarantine.source_path,
            )
            for index, entry in enumerate(entries)
        )
        for decision in decisions:
            entry = entries[decision.entry_index]
            if isinstance(entry, dict):
                entry["authority_validation"] = decision.to_dict()
            issues.append(
                f"Grant-aware validation quarantined {entry_kind}[{decision.entry_index}]"
                f" for {decision.subject_id or '<unknown>'}: {decision.reason}"
                f" (source: {decision.source_path})."
            )
        return _GrantAwareValidationResult([], decisions)

    metadata = authority_resolution.metadata
    assert metadata is not None
    by_digest = {envelope.digest(): envelope for envelope in metadata.result_envelopes}
    by_subject: dict[str, list[ResultEnvelope]] = {}
    for envelope in metadata.result_envelopes:
        by_subject.setdefault(envelope.subject_id, []).append(envelope)

    accepted_entries: list[dict[str, Any]] = []
    decisions: list[GrantAwareValidationDecision] = []
    seen_idempotency: dict[str, ResultEnvelope] = {}
    used_digests: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        subject_id = _entry_subject_id(entry, id_field)
        digest = _authority_digest(entry)
        envelope = by_digest.get(digest) if digest is not None else None
        if envelope is None and subject_id is not None:
            candidates = [
                candidate
                for candidate in by_subject.get(subject_id, [])
                if candidate.digest() not in used_digests
            ]
            if len(candidates) == 1:
                envelope = candidates[0]
                digest = envelope.digest()
        if subject_id is None:
            decision = GrantAwareValidationDecision(
                outcome="quarantined",
                entry_kind=entry_kind,
                entry_index=index,
                subject_id=None,
                reason="missing_subject_id",
                envelope_digest=digest,
                source_path=source,
            )
        elif subject_id not in target_subject_ids:
            decision = GrantAwareValidationDecision(
                outcome=off_scope_outcome,
                entry_kind=entry_kind,
                entry_index=index,
                subject_id=subject_id,
                reason="subject_outside_dispatched_batch",
                envelope_digest=digest,
                source_path=source,
            )
        elif envelope is None:
            decision = GrantAwareValidationDecision(
                outcome="quarantined",
                entry_kind=entry_kind,
                entry_index=index,
                subject_id=subject_id,
                reason="missing_result_envelope",
                envelope_digest=digest,
                source_path=source,
            )
        else:
            used_digests.add(envelope.digest())
            outcome, reason = _validate_entry_against_envelope(
                entry=entry,
                entry_kind=entry_kind,
                id_field=id_field,
                subject_id=subject_id,
                envelope=envelope,
                target_subject_ids=target_subject_ids,
                expected_claim_type=expected_claim_type,
                expected_capability=expected_capability,
                state=state,
            )
            key = envelope.claim.idempotency_key
            if outcome == "accepted":
                existing = seen_idempotency.get(key)
                if existing is None:
                    seen_idempotency[key] = envelope
                else:
                    try:
                        existing.claim.idempotency.assert_compatible(envelope.claim.idempotency)
                    except IdempotencyConflict:
                        outcome = "superseded-or-conflicting"
                        reason = "idempotency_key_conflict"
                    else:
                        outcome = "duplicate-idempotent"
                        reason = "duplicate_idempotency_key"
            decision = GrantAwareValidationDecision(
                outcome=outcome,
                entry_kind=entry_kind,
                entry_index=index,
                subject_id=subject_id,
                reason=reason,
                idempotency_key=envelope.claim.idempotency_key,
                envelope_digest=envelope.digest(),
                source_path=source,
            )
        decisions.append(decision)
        entry["authority_validation"] = decision.to_dict()
        if decision.accepted_for_merge:
            accepted_entries.append(entry)
        elif decision.outcome != "duplicate-idempotent":
            issues.append(
                f"Grant-aware validation {decision.outcome} {entry_kind}[{decision.entry_index}]"
                f" for {decision.subject_id or '<unknown>'}: {decision.reason}"
                f" (source: {decision.source_path})."
            )
        else:
            issues.append(
                f"Grant-aware validation duplicate-idempotent {entry_kind}[{decision.entry_index}]"
                f" for {decision.subject_id or '<unknown>'}: ignored duplicate"
                f" (source: {decision.source_path})."
            )

    return _GrantAwareValidationResult(accepted_entries, tuple(decisions))


def _merge_validated_entries(
    entries: list[dict[str, Any]],
    *,
    targets_by_id: dict[str, dict[str, Any]],
    id_field: str,
    merge_fields: tuple[str, ...],
    issues: list[str],
    label: str,
) -> int:
    """Merge validated entries into targets, deduplicating by ID. Returns unique merge count."""
    seen: set[str] = set()
    for entry in entries:
        entry_id = entry[id_field]
        target = targets_by_id.get(entry_id)
        if target is None:
            issues.append(f"Skipped {label} for unknown {id_field} '{entry_id}'.")
            continue
        if entry_id in seen:
            issues.append(f"Duplicate {label} for '{entry_id}' — last entry wins.")
        for field in merge_fields:
            if field in entry:
                target[field] = entry[field]
        seen.add(entry_id)
    return len(seen)


def _validate_and_merge_batch(
    entries: Any,
    *,
    required_fields: tuple[str, ...],
    optional_fields: tuple[str, ...] = (),
    targets_by_id: dict[str, dict[str, Any]],
    id_field: str,
    merge_fields: tuple[str, ...],
    issues: list[str],
    validation_label: str,
    merge_label: str,
    incomplete_message: Callable[[int, int], str] | None = None,
    enum_fields: dict[str, set[str]] | None = None,
    nonempty_fields: set[str] | None = None,
    array_fields: tuple[str, ...] = (),
    object_fields: tuple[str, ...] = (),
) -> tuple[int, int]:
    valid_entries = _validate_merge_inputs(
        entries,
        required_fields=required_fields,
        optional_fields=optional_fields,
        enum_fields=enum_fields,
        nonempty_fields=nonempty_fields,
        array_fields=array_fields,
        object_fields=object_fields,
        deviations=issues,
        label=validation_label,
    )
    total = len(targets_by_id)
    merged_count = _merge_validated_entries(
        valid_entries,
        targets_by_id=targets_by_id,
        id_field=id_field,
        merge_fields=merge_fields,
        issues=issues,
        label=merge_label,
    )
    _apply_task_update_guardrails(
        valid_entries,
        targets_by_id=targets_by_id,
        id_field=id_field,
        merge_fields=merge_fields,
        issues=issues,
    )
    if incomplete_message is not None and merged_count < total:
        issues.append(incomplete_message(merged_count, total))
    return merged_count, total


def _snapshot_task_statuses(tasks: list[dict[str, Any]]) -> dict[str, str]:
    return {
        task["id"]: str(task.get("status", ""))
        for task in tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }


def _append_execute_reconciliation_advisories(
    *,
    before_statuses: dict[str, str],
    tasks_by_id: dict[str, dict[str, Any]],
    issues: list[str],
) -> None:
    for task_id, before_status in before_statuses.items():
        after_status = str(tasks_by_id.get(task_id, {}).get("status", ""))
        if before_status not in {"done", "skipped"} or after_status == before_status:
            continue
        issues.append(
            f"Advisory: task {task_id} was {before_status!r} on disk before merge but structured output set it to {after_status!r}. Structured output remains authoritative."
        )


_TIMEOUT_PREFIX = re.compile(
    r"(?:^|\s)timeout\s+(?:(?:--[^\s]+)\s+)*(?P<value>\d+)(?P<unit>[sm]?)\s+"
)


def _test_command_evidence(command: str) -> tuple[int | None, list[str]] | None:
    """Return declared timeout seconds and path selectors for one test command."""

    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    runner_index: int | None = None
    for index, part in enumerate(parts):
        if part == "pytest" or part.endswith("/pytest"):
            runner_index = index
            break
        if part == "--test" and index > 0 and parts[index - 1] == "node":
            runner_index = index
            break
    if runner_index is None:
        return None
    timeout_match = _TIMEOUT_PREFIX.search(command)
    timeout_seconds: int | None = None
    if timeout_match:
        timeout_seconds = int(timeout_match.group("value"))
        if timeout_match.group("unit") == "m":
            timeout_seconds *= 60
    selectors = [
        part.lstrip("./")
        for part in parts[runner_index + 1 :]
        if part
        and not part.startswith("-")
        and (
            "/" in part
            or "::" in part
            or part.endswith((".py", ".js", ".mjs", ".cjs"))
        )
    ]
    return timeout_seconds, selectors


def _enforce_task_test_budgets(
    entries: Iterable[dict[str, Any]],
    *,
    targets_by_id: Mapping[str, dict[str, Any]],
    issues: list[str],
) -> None:
    """Fail closed when v2 task evidence exceeds its admitted narrow-test budget."""

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        task_id = entry.get("task_id")
        target = targets_by_id.get(task_id) if isinstance(task_id, str) else None
        narrow = target.get("narrow_tests") if isinstance(target, dict) else None
        if not isinstance(narrow, Mapping):
            continue  # Stored v1 tasks retain their legacy execution behavior.
        commands = entry.get("commands_run")
        if not isinstance(commands, list):
            continue
        invocations = [
            evidence
            for command in commands
            if isinstance(command, str)
            for evidence in [_test_command_evidence(command)]
            if evidence is not None
        ]
        allowed_selectors = {
            selector.strip().lstrip("./")
            for selector in narrow.get("selectors", [])
            if isinstance(selector, str) and selector.strip()
        }
        max_runs = narrow.get("max_runs")
        max_seconds = narrow.get("max_seconds")
        violations: list[str] = []
        if isinstance(max_runs, int) and len(invocations) > max_runs:
            violations.append(f"{len(invocations)} test runs exceeds max_runs={max_runs}")
        timeout_total = 0
        for timeout_seconds, selectors in invocations:
            if timeout_seconds is None:
                violations.append("test command lacks an admitted timeout wrapper")
            else:
                timeout_total += timeout_seconds
            if not selectors:
                violations.append("test command has no bounded path selector")
                continue
            for selector in selectors:
                selector_base = selector.split("::", 1)[0]
                if not any(
                    selector == allowed
                    or selector_base == allowed.split("::", 1)[0]
                    for allowed in allowed_selectors
                ):
                    violations.append(f"selector {selector!r} is outside narrow_tests.selectors")
        if isinstance(max_seconds, int) and timeout_total > max_seconds:
            violations.append(
                f"declared test timeout total {timeout_total}s exceeds max_seconds={max_seconds}"
            )
        if not violations:
            continue
        reason = "task_test_budget_exhausted: " + "; ".join(dict.fromkeys(violations))
        entry["status"] = "blocked"
        notes = str(entry.get("executor_notes") or "").strip()
        entry["executor_notes"] = f"{notes} [harness] {reason}".strip()
        issues.append(f"Task {task_id} blocked by admitted test budget: {reason}")


def _enforce_task_write_budgets(
    entries: Iterable[dict[str, Any]],
    *,
    targets_by_id: Mapping[str, dict[str, Any]],
    issues: list[str],
) -> None:
    """Block v2 task results that claim writes outside the admitted write set."""

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        task_id = entry.get("task_id")
        target = targets_by_id.get(task_id) if isinstance(task_id, str) else None
        write_set = target.get("write_set") if isinstance(target, dict) else None
        if not isinstance(write_set, Mapping):
            continue
        declared = {
            path.strip().replace("\\", "/").lstrip("./")
            for path in write_set.get("paths", [])
            if isinstance(path, str) and path.strip()
        }
        actual = [
            path.strip().replace("\\", "/").lstrip("./")
            for path in entry.get("files_changed", [])
            if isinstance(path, str) and path.strip()
        ]
        escaped = sorted(set(actual) - declared)
        if not escaped and len(set(actual)) <= 5:
            continue
        reasons: list[str] = []
        if escaped:
            reasons.append(f"undeclared paths {escaped!r}")
        if len(set(actual)) > 5:
            reasons.append(f"{len(set(actual))} actual paths exceeds the 5-path task budget")
        reason = "task_write_set_violation: " + "; ".join(reasons)
        entry["status"] = "blocked"
        notes = str(entry.get("executor_notes") or "").strip()
        entry["executor_notes"] = f"{notes} [harness] {reason}".strip()
        issues.append(f"Task {task_id} blocked by admitted write set: {reason}")


def _merge_batch_results(
    *,
    finalize_data: dict[str, Any],
    payload: dict[str, Any],
    batch_task_ids: list[str],
    batch_sense_check_ids: list[str],
    issues: list[str],
    mode: str = "code",
    state: PlanState | None = None,
    source_path: str | Path = "<merge-payload>",
) -> tuple[int, int, int, int]:
    batch_task_id_set = set(batch_task_ids)
    batch_sense_check_id_set = set(batch_sense_check_ids)
    pre_merge_statuses = _snapshot_task_statuses(
        [
            task
            for task in finalize_data.get("tasks", [])
            if task.get("id") in batch_task_id_set
        ]
    )
    plan_tasks_by_id = {
        task["id"]: task
        for task in finalize_data.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }
    mode_state = state or {"config": {"mode": mode}}
    creative_mode = is_creative_mode(mode_state)
    if creative_mode and isinstance(payload.get("task_updates"), list):
        for task_update in payload["task_updates"]:
            if not isinstance(task_update, dict) or not isinstance(task_update.get("stance"), dict):
                continue
            violations = validate_stance(task_update["stance"])
            if violations:
                task_update["stance_violations"] = violations
    evidence_context_fields = ("head_sha", "code_hash")
    if is_prose_mode(mode_state):
        required_fields = ("task_id", "status", "executor_notes", "sections_written")
        object_fields: tuple[str, ...] = ()
        optional_fields: tuple[str, ...] = evidence_context_fields
        if is_creative_mode(mode_state):
            required_fields = required_fields + ("stance", "stop_signal")
            object_fields = ("stance", "stop_signal")
            optional_fields = ("stance_violations",) + evidence_context_fields
        merge_fields = (
            "status",
            "executor_notes",
            "sections_written",
            "stance",
            "stop_signal",
            "stance_violations",
        ) + evidence_context_fields
        array_fields = ("sections_written", "stance_violations")
    else:
        required_fields = ("task_id", "status", "executor_notes", "files_changed", "commands_run")
        merge_fields = ("status", "executor_notes", "files_changed", "commands_run") + evidence_context_fields
        array_fields = ("files_changed", "commands_run")
        object_fields = ()
        optional_fields = evidence_context_fields
    merge_targets_by_id = {
        task_id: task
        for task_id, task in plan_tasks_by_id.items()
        if task_id in batch_task_id_set
    }
    task_authority = _grant_aware_validate_entries(
        payload.get("task_updates"),
        payload=payload,
        target_subject_ids=batch_task_id_set,
        id_field="task_id",
        entry_kind="task_update",
        expected_claim_type=TASK_COMPLETION_CLAIM,
        expected_capability=TASK_RESULT_CAPABILITY,
        issues=issues,
        state=state,
        source_path=source_path,
        off_scope_outcome="quarantined" if creative_mode else "rejected",
    )
    _enforce_task_test_budgets(
        task_authority.entries,
        targets_by_id=merge_targets_by_id,
        issues=issues,
    )
    _enforce_task_write_budgets(
        task_authority.entries,
        targets_by_id=merge_targets_by_id,
        issues=issues,
    )
    merged_count, _ = _validate_and_merge_batch(
        task_authority.entries,
        required_fields=required_fields,
        optional_fields=optional_fields,
        targets_by_id=merge_targets_by_id,
        id_field="task_id",
        merge_fields=merge_fields,
        issues=issues,
        validation_label="task_updates",
        merge_label="task_update",
        incomplete_message=None,
        enum_fields={"status": set(TERMINAL_TASK_STATUSES)},
        nonempty_fields={"executor_notes"},
        array_fields=array_fields,
        object_fields=object_fields,
    )
    # Check batch-specific coverage: how many of THIS batch's tasks got updates?
    # Any terminal status counts as "tracked" — the executor reported back.
    # "blocked" / "completed" specifically used to be left out of this filter,
    # which produced a false "tracking is incomplete" message when the
    # executor legitimately blocked on a user prerequisite.
    total_batch_tasks = len(batch_task_id_set)
    batch_merged = sum(
        1
        for tid in batch_task_id_set
        if plan_tasks_by_id.get(tid, {}).get("status") in TERMINAL_TASK_STATUSES
    )
    if batch_merged < total_batch_tasks:
        issues.append(
            f"{total_batch_tasks - batch_merged}/{total_batch_tasks} batch tasks have no executor update — tracking is incomplete."
        )
    # Same for sense checks — accept any valid sense check ID.
    all_sense_checks_by_id = {
        sense_check["id"]: sense_check
        for sense_check in finalize_data.get("sense_checks", [])
        if isinstance(sense_check, dict) and isinstance(sense_check.get("id"), str)
    }
    merge_sense_checks_by_id = {
        sense_check_id: sense_check
        for sense_check_id, sense_check in all_sense_checks_by_id.items()
        if sense_check_id in batch_sense_check_id_set
    }
    sense_check_authority = _grant_aware_validate_entries(
        payload.get("sense_check_acknowledgments"),
        payload=payload,
        target_subject_ids=batch_sense_check_id_set,
        id_field="sense_check_id",
        entry_kind="sense_check_acknowledgment",
        expected_claim_type=SENSE_CHECK_ACK_CLAIM,
        expected_capability=SENSE_CHECK_RESULT_CAPABILITY,
        issues=issues,
        state=state,
        source_path=source_path,
        off_scope_outcome="quarantined" if creative_mode else "rejected",
    )
    acknowledged_count, _ = _validate_and_merge_batch(
        sense_check_authority.entries,
        required_fields=("sense_check_id", "executor_note"),
        targets_by_id=merge_sense_checks_by_id,
        id_field="sense_check_id",
        merge_fields=("executor_note",),
        issues=issues,
        validation_label="sense_check_acknowledgments",
        merge_label="sense_check_acknowledgment",
        incomplete_message=None,
        nonempty_fields={"executor_note"},
    )
    total_batch_checks = len(batch_sense_check_id_set)
    batch_acknowledged = sum(
        1
        for sid in batch_sense_check_id_set
        if all_sense_checks_by_id.get(sid, {}).get("executor_note")
    )
    if batch_acknowledged < total_batch_checks:
        issues.append(
            f"{total_batch_checks - batch_acknowledged}/{total_batch_checks} batch sense checks have no executor acknowledgment — tracking is incomplete."
        )
    _append_execute_reconciliation_advisories(
        before_statuses=pre_merge_statuses,
        tasks_by_id=plan_tasks_by_id,
        issues=issues,
    )
    return merged_count, total_batch_tasks, acknowledged_count, total_batch_checks


def _merge_scoped_batch_artifact_through_validator(
    *,
    plan_dir: Path,
    artifact_path: Path,
    payload: Any,
    finalize_data: dict[str, Any],
    known_task_ids: Iterable[str],
    known_sense_check_ids: Iterable[str],
    mode: str,
    state: PlanState,
) -> _ScopedBatchArtifactMergeResult:
    """Prove compatibility scope, then let the grant-aware validator arbitrate rows."""

    if not isinstance(payload, dict):
        return _ScopedBatchArtifactMergeResult(
            quarantine=BatchScopeQuarantine(
                reason="malformed_artifact",
                message="artifact payload must be an object",
                source_path=str(artifact_path),
            )
        )
    resolution = resolve_batch_scope(
        payload,
        artifact_path,
        known_task_ids=known_task_ids,
        known_sense_check_ids=known_sense_check_ids,
        expected_batch_number=batch_artifact_index(artifact_path),
    )
    if resolution.quarantine is not None:
        return _ScopedBatchArtifactMergeResult(quarantine=resolution.quarantine)
    scope = resolution.scope
    assert scope is not None

    issues: list[str] = []
    merged_count, total_task_count, acknowledged_count, total_check_count = _merge_batch_results(
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=list(scope.task_ids),
        batch_sense_check_ids=list(scope.sense_check_ids),
        issues=issues,
        mode=mode,
        state=state,
        source_path=artifact_path,
    )
    return _ScopedBatchArtifactMergeResult(
        payload=payload,
        scope_task_ids=scope.task_ids,
        scope_sense_check_ids=scope.sense_check_ids,
        merged_task_count=merged_count,
        total_task_count=total_task_count,
        acknowledged_sense_check_count=acknowledged_count,
        total_sense_check_count=total_check_count,
        issues=tuple(issues),
    )


def _diagnose_reconciliation_quarantine(
    plan_dir: Path,
    quarantine: BatchScopeQuarantine,
) -> dict[str, Any]:
    """Emit the authority-divergence diagnostic and return its durable details."""

    diagnostic = {
        "diagnostic_version": 1,
        "authority_status": "quarantined",
        "authoritative": False,
        "reason": f"batch_scope_{quarantine.reason}",
        "artifact_path": quarantine.source_path,
        "quarantine": quarantine.to_dict(),
    }
    try:
        from arnold_pipelines.megaplan.observability.events import EventKind, emit

        emit(
            EventKind.AUTHORITY_DIVERGENCE,
            plan_dir=plan_dir,
            phase="execute",
            payload=diagnostic,
        )
    except Exception as error:
        diagnostic["diagnostic_error"] = str(error)
    return diagnostic


def _quarantined_reconciliation_result(
    *,
    plan_dir: Path,
    artifact: Path,
    quarantine: BatchScopeQuarantine,
) -> dict[str, Any]:
    diagnostic = _diagnose_reconciliation_quarantine(plan_dir, quarantine)
    return {
        "reconciled": False,
        "artifact": artifact.name,
        "artifact_path": quarantine.source_path,
        "reason": "execution artifact scope could not be proven",
        "authority_status": "quarantined",
        "quarantine": quarantine.to_dict(),
        "diagnostic": diagnostic,
    }


def reconcile_latest_execution_batch(plan_dir: Path, state: PlanState) -> dict[str, Any]:
    """Best-effort merge of the latest execution_batch_N artifact into finalize.json.

    This is used at failure boundaries outside the execute handler, such as a
    chain phase-complete callback failing after an execute subprocess produced
    a checkpoint artifact. It intentionally treats the latest batch payload as
    structured evidence and lets the normal merge validator decide which
    entries are usable.
    """

    artifacts = list_batch_artifacts(plan_dir)
    if not artifacts:
        return {"reconciled": False, "reason": "no execution batch artifacts"}
    latest = artifacts[-1]
    try:
        payload = read_json(latest)
    except Exception as error:
        return _quarantined_reconciliation_result(
            plan_dir=plan_dir,
            artifact=latest,
            quarantine=BatchScopeQuarantine(
                reason="unreadable_artifact",
                message=f"artifact could not be read as JSON: {error}",
                source_path=str(latest),
            ),
        )
    try:
        finalize_data = read_json(plan_dir / "finalize.json")
    except Exception as error:
        return {
            "reconciled": False,
            "artifact": latest.name,
            "artifact_path": str(latest),
            "reason": f"failed to read finalize payload: {error}",
        }
    if not isinstance(finalize_data, dict):
        return {
            "reconciled": False,
            "artifact": latest.name,
            "artifact_path": str(latest),
            "reason": "finalize payload was not an object",
        }

    known_task_ids = [
        task["id"]
        for task in finalize_data.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    ]
    known_sense_check_ids = [
        check["id"]
        for check in finalize_data.get("sense_checks", [])
        if isinstance(check, dict) and isinstance(check.get("id"), str)
    ]
    merge_result = _merge_scoped_batch_artifact_through_validator(
        plan_dir=plan_dir,
        artifact_path=latest,
        payload=payload,
        finalize_data=finalize_data,
        known_task_ids=known_task_ids,
        known_sense_check_ids=known_sense_check_ids,
        mode=state.get("config", {}).get("mode", "code"),
        state=state,
    )
    if merge_result.quarantine is not None:
        return _quarantined_reconciliation_result(
            plan_dir=plan_dir,
            artifact=latest,
            quarantine=merge_result.quarantine,
        )
    write_plan_artifact_json(plan_dir, "finalize.json", finalize_data, contract_context=None)
    final_md_error: str | None = None
    try:
        atomic_write_text(
            plan_dir / "final.md", render_final_md(finalize_data, phase="execute")
        )
    except Exception as error:
        final_md_error = str(error)
    return {
        "reconciled": True,
        "artifact": latest.name,
        "merged_task_count": merge_result.merged_task_count,
        "total_task_count": merge_result.total_task_count,
        "acknowledged_sense_check_count": merge_result.acknowledged_sense_check_count,
        "total_sense_check_count": merge_result.total_sense_check_count,
        "issues": list(merge_result.issues),
        "final_md_error": final_md_error,
    }
