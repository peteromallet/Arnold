"""Incident event schema — validation and normalization for M1.

Exports
-------
* ``validate_incident_event(event)`` — validate and return a normalized
  shallow copy.  Preserves unknown fields, rejects missing or malformed
  required fields with field-specific ``ValueError``, and enforces
  ``schema_version == 1``, ISO-8601-like timestamps, string IDs,
  list-shaped ``evidence`` and ``parent_event_ids`` fields, and a
  ``summary`` length cap of 2048 characters.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from arnold_pipelines.megaplan.cloud.redact import redact_payload, redact_text
from arnold_pipelines.megaplan.maintenance.identity import (
    MAINTENANCE_SCHEMA_VERSION,
    canonical_json,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_M1_FIELDS: tuple[str, ...] = (
    "event_id",
    "ts",
    "type",
    "actor",
    "scope",
    "outcome",
    "summary",
)

REQUIRED_LIST_FIELDS: tuple[str, ...] = (
    "evidence",
    "parent_event_ids",
)

REQUIRED_NULLABLE_STRING_FIELDS: tuple[str, ...] = (
    "next_expected_event",
    "deadline_ts",
    "trigger_event_id",
)

OPTIONAL_NULLABLE_STRING_FIELDS: tuple[str, ...] = (
    "incident_id",
    "session_id",
    "initiative",
    "plan",
    "problem_id",
    "supersedes_event_id",
    "attempt_id",
)

#: Maintenance event kinds routed through the strict Maintenance codec.
#: These exactly mirror the closed Maintenance ``EventKind`` vocabulary
#: (detection / efficiency_analysis / audit_report).  An incident event whose
#: ``type`` is one of these AND whose payload carries the canonical
#: Maintenance occurrence identity is routed through the strict codec
#: (``strict_loads`` on the Maintenance event contract) instead of the legacy
#: permissive M1 validation; every other event keeps the legacy behavior
#: unchanged, including unknown-field preservation.
MAINTENANCE_EVENT_TYPES: frozenset[str] = frozenset(
    {"detection", "efficiency_analysis", "audit_report"}
)

#: Legacy occurrence-only row kinds.  Detection / efficiency_analysis /
#: audit_report rows keep the occurrence-only idempotency key so legacy M2
#: detection, analysis, and audit consumers (and M2 replay) remain
#: byte-compatible.  Only Operational lifecycle rows (see
#: :func:`is_operational_lifecycle_row`) derive the strict action key.
LEGACY_OCCURRENCE_ONLY_KINDS: frozenset[str] = frozenset(
    {"detection", "efficiency_analysis", "audit_report"}
)

#: The five frozen coordinates every canonical operational action key binds:
#: schema version, canonical occurrence digest, action type, policy version,
#: and target identity.  The tuple is the persisted compatibility contract;
#: it must never be reordered or re-keyed.
OPERATIONAL_KEY_COORDINATES: tuple[str, ...] = (
    "schema_version",
    "occurrence_digest",
    "action_kind",
    "policy_version",
    "target",
)

_SHA256_HEX = frozenset("0123456789abcdef")


def is_maintenance_event(event: dict[str, Any]) -> bool:
    """Return whether *event* is a strict Maintenance event (codec-routed).

    A Maintenance event is recognized by its closed kind vocabulary plus the
    canonical occurrence identity / event-kind markers that only the strict
    Maintenance contract carries.  Legacy incident events (including watchdog
    detections that predate the Maintenance contract) never carry
    ``occurrence_id``/``event_kind`` and therefore keep the legacy path.
    """
    return (
        isinstance(event, dict)
        and (
            event.get("type") in MAINTENANCE_EVENT_TYPES
            or event.get("event_kind") in MAINTENANCE_EVENT_TYPES
        )
        and "occurrence_id" in event
    )


# ---------------------------------------------------------------------------
# Lifecycle action idempotency keys (M3 Step 2, incident schema boundary)
# ---------------------------------------------------------------------------
# Operational lifecycle records (repair request, source change, installation,
# retrigger, progress observation, checkpoint verification, terminal
# verification, recurrence, human escalation) coexist for one canonical
# occurrence.  Their persisted idempotency keys are derived from the five
# frozen coordinates — schema version, canonical occurrence digest, action
# type, policy version, and target identity — so distinct actions for one
# occurrence get distinct keys while an exact retry reproduces the same key.
# Legacy detection / efficiency_analysis / audit_report rows keep the
# occurrence-only key (M2 compatibility): exactly one record per occurrence.


def _require_operational_coordinate(value: Any, *, what: str) -> str:
    """Return *value* when it is a non-empty string, else fail closed."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"operational lifecycle row requires {what}")
    return value


def operational_action_key(
    *,
    schema_version: int,
    occurrence_digest: str,
    action_kind: str,
    policy_version: str,
    target: str,
) -> str:
    """Derive the canonical lifecycle action idempotency key.

    The key is the sha256 of the canonical JSON encoding of the five frozen
    coordinates (:data:`OPERATIONAL_KEY_COORDINATES`): schema version,
    canonical occurrence digest, action type, policy version, and target
    identity.  Distinct lifecycle actions for one occurrence therefore
    coexist with distinct keys, an exact retry reproduces the same key, and a
    change in any coordinate produces a different key.  Malformed or missing
    coordinates raise ``ValueError`` — a key is never derived from guessed
    values.

    This is the persisted compatibility contract consumed by the shared
    incident journal (T4): legacy rows keep occurrence-only keys via
    :func:`legacy_occurrence_idempotency_key`.
    """
    if schema_version != MAINTENANCE_SCHEMA_VERSION:
        raise ValueError(
            "operational action key requires schema_version "
            f"{MAINTENANCE_SCHEMA_VERSION}, got {schema_version!r}"
        )
    occurrence_digest = _require_operational_coordinate(
        occurrence_digest, what="occurrence digest"
    )
    if len(occurrence_digest) != 64 or any(
        char not in _SHA256_HEX for char in occurrence_digest
    ):
        raise ValueError(
            "operational action key requires a 64-character lowercase "
            "sha256 occurrence digest"
        )
    action_kind = _require_operational_coordinate(action_kind, what="action kind")
    policy_version = _require_operational_coordinate(
        policy_version, what="policy version"
    )
    target = _require_operational_coordinate(target, what="target identity")
    material = canonical_json(
        {
            "schema_version": schema_version,
            "occurrence_digest": occurrence_digest,
            "action_kind": action_kind,
            "policy_version": policy_version,
            "target": target,
        }
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def is_operational_lifecycle_row(event: Any) -> bool:
    """Return whether *event* is a persisted operational lifecycle row.

    An operational row carries the closed ``action_kind`` plus the canonical
    ``occurrence`` coordinate object (with ``canonical_digest``); legacy
    detection / efficiency_analysis / audit_report rows carry a plain
    occurrence-only ``occurrence_id`` and are never misread as operational.
    """
    return (
        isinstance(event, dict)
        and isinstance(event.get("action_kind"), str)
        and isinstance(event.get("occurrence"), dict)
        and isinstance(event["occurrence"].get("canonical_digest"), str)
    )


def legacy_occurrence_idempotency_key(event: Any) -> str:
    """Return the occurrence-only key retained for legacy rows.

    Legacy detection / efficiency_analysis / audit_report rows stay keyed by
    the occurrence identity alone (M2 compatibility): exactly one record per
    occurrence, and detection/analysis/audit consumers keep their lookups.
    A malformed row raises ``ValueError`` instead of guessing.
    """
    if not isinstance(event, dict):
        raise ValueError(
            "legacy occurrence idempotency key requires a dict event"
        )
    occurrence_id = event.get("occurrence_id")
    if not isinstance(occurrence_id, str) or not occurrence_id:
        raise ValueError(
            "legacy occurrence idempotency key requires a non-empty "
            "occurrence_id"
        )
    return occurrence_id


def _checkpoint_window_key(base_key: str, window: str) -> str:
    """Fold one canonical checkpoint window into a checkpoint action key.

    A policy-required checkpoint window is a distinct stable lifecycle
    identity: the four ``checkpoint_verification`` actions for one occurrence
    coexist (immediate / five_minute / one_hour / next_three_hour), while an
    exact retry of the SAME window reproduces the SAME key (dedup by window
    identity, never rewrite).  Applies ONLY to ``checkpoint_verification``
    rows; the five-coordinate action-key contract is unchanged for every
    other action and for direct callers.
    """
    return hashlib.sha256(
        canonical_json(
            {"base_key": base_key, "checkpoint_window": window}
        ).encode("utf-8")
    ).hexdigest()


def lifecycle_idempotency_key(event: Any) -> str:
    """Return the canonical persisted lifecycle idempotency key for *event*.

    Operational lifecycle rows derive the strict action key from schema
    version, canonical occurrence digest, action type, policy version, and
    target identity (see :func:`operational_action_key`); legacy
    detection / efficiency_analysis / audit_report rows keep the
    occurrence-only key.  The discriminator is exact: an operational row
    always carries ``action_kind`` plus the canonical ``occurrence``
    coordinate object, so a legacy row can never be routed to the strict key
    and an operational row can never collapse onto the occurrence-only key.
    """
    if is_operational_lifecycle_row(event):
        occurrence = event["occurrence"]
        policy = event.get("policy")
        target = event.get("target")
        if not isinstance(policy, dict) or not isinstance(target, dict):
            raise ValueError(
                "operational lifecycle row requires policy and target "
                "coordinate objects"
            )
        schema_version = event.get("schema_version")
        if schema_version != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                "operational lifecycle row requires schema_version "
                f"{MAINTENANCE_SCHEMA_VERSION}, got {schema_version!r}"
            )
        key = operational_action_key(
            schema_version=schema_version,
            occurrence_digest=occurrence["canonical_digest"],
            action_kind=event["action_kind"],
            policy_version=_require_operational_coordinate(
                policy.get("policy_version"), what="policy version"
            ),
            target=_require_operational_coordinate(
                target.get("target"), what="target identity"
            ),
        )
        if event["action_kind"] == "checkpoint_verification":
            payload = event.get("payload")
            if not isinstance(payload, dict):
                raise ValueError(
                    "checkpoint verification requires a payload object"
                )
            return _checkpoint_window_key(
                key,
                _require_operational_coordinate(
                    payload.get("checkpoint"), what="checkpoint window"
                ),
            )
        return key
    return legacy_occurrence_idempotency_key(event)


def operational_event_action_key(event: Any) -> str:
    """Derive the canonical action key for an ``OperationalEvent`` model.

    *event* must expose the frozen operational coordinates (``schema_version``,
    ``occurrence.canonical_digest``, ``action_kind.value``,
    ``policy.policy_version``, ``target.target``).  The function is
    duck-typed so the incident schema never imports the operational event
    envelope at module scope.
    """
    key = operational_action_key(
        schema_version=event.schema_version,
        occurrence_digest=event.occurrence.canonical_digest,
        action_kind=event.action_kind.value,
        policy_version=event.policy.policy_version,
        target=event.target.target,
    )
    if event.action_kind.value == "checkpoint_verification":
        return _checkpoint_window_key(
            key, _require_operational_coordinate(
                event.payload.checkpoint.value, what="checkpoint window"
            )
        )
    return key


def validate_maintenance_event(event: dict[str, Any]) -> dict[str, Any]:
    """Strict-route *event* through the canonical Maintenance codec.

    The event is decoded with ``strict_loads`` against the closed
    Maintenance event contract (missing/unknown fields and identity
    mismatches fail) and re-encoded canonically, so the stored payload is
    byte-stable and the canonical digest is reproducible.  Unknown fields
    are accepted ONLY inside the explicit ``extensions`` map.
    """
    from arnold_pipelines.megaplan.maintenance.events import MaintenanceEvent
    from arnold_pipelines.megaplan.maintenance.identity import (
        MaintenanceCodecError,
        canonical_dumps,
        strict_loads,
    )

    try:
        model = strict_loads(MaintenanceEvent, event)
    except MaintenanceCodecError as exc:
        raise ValueError(
            "maintenance event strict decode failed for type "
            f"{event.get('type')!r}: {exc}"
        ) from exc
    return json.loads(canonical_dumps(model))

MAX_SUMMARY_LENGTH: int = 2048
MAX_COMMITTED_OUTPUT_BYTES: int = 50 * 1024
MAX_STRUCTURED_FIELD_BYTES: int = 64 * 1024
_ALWAYS_ON_REDACTION_ENV: dict[str, str] = {}
_COMMITTED_OUTPUT_TRUNCATION_TEMPLATE = (
    "\n[truncated {omitted} bytes to satisfy the 50KB committed-output cap]"
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _check_required_field(
    event: dict[str, Any],
    field: str,
) -> None:
    """Raise ``ValueError`` if *field* is missing or not a non-empty string."""
    if field not in event:
        raise ValueError(f"incident event requires '{field}'")
    value = event[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"incident event '{field}' must be a non-empty string"
        )


def _check_list_field(
    event: dict[str, Any],
    field: str,
) -> None:
    """Raise ``ValueError`` if *field* is missing or not a list."""
    if field not in event:
        raise ValueError(f"incident event requires '{field}'")
    value = event[field]
    if not isinstance(value, list):
        raise ValueError(
            f"incident event '{field}' must be a list"
        )


def _check_string_or_none_field(
    event: dict[str, Any],
    field: str,
    *,
    required: bool,
) -> None:
    """Raise ``ValueError`` if *field* is missing or malformed."""
    if field not in event:
        if required:
            raise ValueError(f"incident event requires '{field}'")
        return
    value = event[field]
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"incident event '{field}' must be a non-empty string or null"
        )


def _check_object_or_none_field(
    event: dict[str, Any],
    field: str,
) -> None:
    """Raise ``ValueError`` if an optional field is present but malformed."""
    if field not in event:
        return
    value = event[field]
    if value is None or isinstance(value, dict):
        return
    raise ValueError(
        f"incident event '{field}' must be an object or null"
    )


def _check_timestamp(value: str, field: str) -> None:
    """Loosely validate an ISO-8601-like timestamp.

    Requires at minimum ``YYYY-MM-DD`` with optional ``T`` time and
    ``Z``/offset suffix.  This is intentionally more permissive than
    ``datetime.fromisoformat`` to accept common variants.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"incident event '{field}' must be an ISO-8601-like timestamp string"
        )
    stripped = value.strip()
    # Must have at least YYYY-MM-DD
    if len(stripped) < 10 or stripped[4] != "-" or stripped[7] != "-":
        raise ValueError(
            f"incident event '{field}' must be an ISO-8601-like timestamp (got {value!r})"
        )
    # The date portion must be digits (basic check)
    try:
        int(stripped[:4])
        int(stripped[5:7])
        int(stripped[8:10])
    except (ValueError, IndexError):
        raise ValueError(
            f"incident event '{field}' must be an ISO-8601-like timestamp (got {value!r})"
        )


def redact_incident_event(event: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with write-path/publication fields redacted.

    Redaction is intentionally always-on for ledger/publication paths, even when
    cloud log redaction has been disabled via environment flags.
    """
    redacted = dict(event)
    if "summary" in redacted:
        redacted["summary"] = redact_text(
            redacted["summary"],
            env=_ALWAYS_ON_REDACTION_ENV,
        )
    for field in ("evidence", "links", "decision", "actions"):
        if field in redacted:
            redacted[field] = redact_payload(
                redacted[field],
                env=_ALWAYS_ON_REDACTION_ENV,
            )
    return redacted


def cap_committed_output_text(
    text: str,
    *,
    limit_bytes: int = MAX_COMMITTED_OUTPUT_BYTES,
) -> str:
    """Return *text* capped to *limit_bytes* UTF-8 bytes with a marker."""
    if limit_bytes <= 0:
        raise ValueError("limit_bytes must be positive")
    if not isinstance(text, str):
        raise ValueError("committed output must be a string")
    encoded = text.encode("utf-8")
    if len(encoded) <= limit_bytes:
        return text
    omitted = len(encoded) - limit_bytes
    suffix = _COMMITTED_OUTPUT_TRUNCATION_TEMPLATE.format(omitted=omitted)
    suffix_bytes = suffix.encode("utf-8")
    if len(suffix_bytes) >= limit_bytes:
        return suffix_bytes[:limit_bytes].decode("utf-8", errors="ignore")
    allowed = limit_bytes - len(suffix_bytes)
    truncated = encoded[:allowed].decode("utf-8", errors="ignore")
    while len((truncated + suffix).encode("utf-8")) > limit_bytes and truncated:
        truncated = truncated[:-1]
    return truncated + suffix


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_incident_event(event: dict[str, Any]) -> dict[str, Any]:
    """Validate an incident event and return a normalized shallow copy.

    Validation rules (M1)
    ----------------------
    * *event* must be a ``dict``.
    * ``schema_version`` must be exactly ``1``.
    * Required string fields: ``event_id``, ``ts``, ``type``, ``actor``,
      ``scope``, ``outcome``, ``summary``.
    * Required nullable string fields: ``next_expected_event``,
      ``deadline_ts``, ``trigger_event_id``.
    * ``ts`` and present ``deadline_ts`` values must be ISO-8601-like
      (``YYYY-MM-DD...``).
    * ``summary`` length must be <= 2048 characters.
    * Required list fields: ``evidence``, ``parent_event_ids``.

    Forward compatibility
    ---------------------
    Unknown fields present in *event* are preserved in the returned
    shallow copy.

    Returns
    -------
    dict
        A shallow copy of *event* with all original keys intact.

    Raises
    ------
    ValueError
        If any validation rule is violated.  The message always names
        the offending field.
    """
    if not isinstance(event, dict):
        raise ValueError("incident event must be a dict")
    # Route only Maintenance event kinds through the strict codec; everything
    # else (including legacy extensions) keeps the permissive M1 path below.
    if is_maintenance_event(event):
        return validate_maintenance_event(event)
    # Reject expanding evidence before recursive regex redaction. This keeps a
    # malformed historical auditor event from consuming gigabytes while the
    # projection layer validates it, and prevents recursive report/decision
    # embedding from entering the append-only ledger in the first place.
    structured_bytes = 0
    for field in ("evidence", "links", "decision", "actions"):
        if field not in event:
            continue
        try:
            encoded = json.dumps(
                event[field],
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"incident event '{field}' must be JSON serializable"
            ) from exc
        if len(encoded) > MAX_STRUCTURED_FIELD_BYTES:
            raise ValueError(
                f"incident event '{field}' must be <= {MAX_STRUCTURED_FIELD_BYTES} bytes "
                f"(got {len(encoded)})"
            )
        structured_bytes += len(encoded)
    if structured_bytes > MAX_STRUCTURED_FIELD_BYTES:
        raise ValueError(
            "incident event structured fields must be <= "
            f"{MAX_STRUCTURED_FIELD_BYTES} bytes in aggregate (got {structured_bytes})"
        )
    event = redact_incident_event(event)

    # ── schema_version ──────────────────────────────────────────────
    sv = event.get("schema_version")
    if sv != 1:
        raise ValueError(
            f"incident event schema_version must be 1 (got {sv!r})"
        )

    # ── required string fields ──────────────────────────────────────
    for field in REQUIRED_M1_FIELDS:
        _check_required_field(event, field)

    # ── summary length cap ──────────────────────────────────────────
    summary = event["summary"]
    if len(summary) > MAX_SUMMARY_LENGTH:
        raise ValueError(
            f"incident event 'summary' must be <= {MAX_SUMMARY_LENGTH} "
            f"characters (got {len(summary)})"
        )

    # ── required nullable string fields ─────────────────────────────
    for field in REQUIRED_NULLABLE_STRING_FIELDS:
        _check_string_or_none_field(event, field, required=True)

    for field in OPTIONAL_NULLABLE_STRING_FIELDS:
        _check_string_or_none_field(event, field, required=False)

    _check_object_or_none_field(event, "links")

    # ── timestamps ──────────────────────────────────────────────────
    _check_timestamp(event["ts"], "ts")
    deadline_ts = event["deadline_ts"]
    if deadline_ts is not None:
        _check_timestamp(deadline_ts, "deadline_ts")

    # ── required list fields ────────────────────────────────────────
    for field in REQUIRED_LIST_FIELDS:
        _check_list_field(event, field)

    # ── return normalized shallow copy (preserve unknown fields) ────
    return dict(event)
