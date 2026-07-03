"""Incident event schema — validation and normalization for M1.

Exports
-------
* ``validate_incident_event(event)`` — validate and return a normalized
  shallow copy.  Preserves unknown fields, rejects missing or malformed
  required fields with field-specific ``ValueError``, and enforces
  ``schema_version == 1``, ISO-8601-like timestamps, string IDs,
  list-shaped ``evidence`` and ``parent`` fields, and a ``summary``
  length cap of 2048 characters.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_M1_FIELDS: tuple[str, ...] = (
    "incident_id",
    "type",
    "actor",
    "timestamp",
    "summary",
)

REQUIRED_LIST_FIELDS: tuple[str, ...] = (
    "evidence",
    "parent",
)

MAX_SUMMARY_LENGTH: int = 2048


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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_incident_event(event: dict[str, Any]) -> dict[str, Any]:
    """Validate an incident event and return a normalized shallow copy.

    Validation rules (M1)
    ----------------------
    * *event* must be a ``dict``.
    * ``schema_version`` must be exactly ``1``.
    * Required string fields: ``incident_id``, ``type``, ``actor``,
      ``timestamp``, ``summary``.
    * ``timestamp`` must be ISO-8601-like (``YYYY-MM-DD...``).
    * ``summary`` length must be <= 2048 characters.
    * Required list fields: ``evidence``, ``parent``.

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

    # ── timestamp ───────────────────────────────────────────────────
    _check_timestamp(event["timestamp"], "timestamp")

    # ── required list fields ────────────────────────────────────────
    for field in REQUIRED_LIST_FIELDS:
        _check_list_field(event, field)

    # ── return normalized shallow copy (preserve unknown fields) ────
    return dict(event)
