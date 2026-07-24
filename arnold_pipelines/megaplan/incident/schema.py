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

import json
from typing import Any

from arnold_pipelines.megaplan.cloud.redact import redact_payload, redact_text

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
