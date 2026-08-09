"""Standalone redaction-policy validation for critique ledger payloads.

This module exposes :func:`validate_redaction_policy`, a side-effect-free
validator built on the existing :class:`RedactionMode` enum.  It inspects a
``RetentionPayloadPolicy.redaction_mode`` and (optionally) a payload dict and
returns a list of human-readable issue strings — an empty list means the
payload conforms.

**Standalone status — not wired into CL2 persistence.**

``validate_redaction_policy`` is a policy/contract check only.  It is NOT
called from :class:`~arnold.critique_ledger.persistence_service.LedgerPersistenceService`,
the one-time importer, the projection builder, or any CL2 write path.  CL2
persists whatever validated envelope it receives; redaction enforcement at
write time is intentionally out of scope for this validator so that the
privacy/security contract is documented and testable without being
implicitly bypassed.  The :data:`WIRED_INTO_CL2_PERSISTENCE` constant is
``False`` and is asserted by the tests to make this status unmistakable.

**Dual-hash behaviour.**

A critique occurrence envelope can carry three content hashes:

* ``redacted_prompt_hash`` — hash of the redacted prompt,
* ``raw_prompt_hash``      — hash of the raw (unredacted) prompt,
* ``raw_completion_hash``  — hash of the raw model completion.

When redaction is *active* (``RedactionMode.DEFAULT_ON`` or
``RedactionMode.ALWAYS``) the redaction contract expects a **dual hash**: the
payload carries BOTH a redacted hash (for safe display) AND a raw hash (for
audit/retention).  ``RedactionMode.NONE`` imposes no dual-hash requirement.
"""

from __future__ import annotations

from typing import Any, Mapping

from arnold.workflow.payload_policy import (
    RedactionMode,
    RetentionPayloadPolicy,
    validate_retention_payload_policy,
)

#: Explicit declaration that this validator is NOT wired into CL2 persistence.
#: Asserted by the tests so the standalone status cannot drift silently.
WIRED_INTO_CL2_PERSISTENCE: bool = False

#: Payload keys that form the redaction dual-hash pair.
_REDACTED_PROMPT_HASH_KEY = "redacted_prompt_hash"
_RAW_PROMPT_HASH_KEY = "raw_prompt_hash"

_VALID_REDACTION_MODES = frozenset(
    {RedactionMode.NONE, RedactionMode.DEFAULT_ON, RedactionMode.ALWAYS}
)
_DUAL_HASH_MODES = frozenset({RedactionMode.DEFAULT_ON, RedactionMode.ALWAYS})


def _has_hash(payload: Mapping[str, Any], key: str) -> bool:
    value = payload.get(key)
    return isinstance(value, str) and value.strip() != ""


def validate_redaction_policy(
    policy: RetentionPayloadPolicy,
    *,
    payload: Mapping[str, Any] | None = None,
) -> list[str]:
    """Validate a retention policy's redaction mode against ``wbc.retention.v1``.

    Args:
        policy: A :class:`RetentionPayloadPolicy` whose ``redaction_mode`` is
            inspected.  Its ``redaction_mode`` must be a known
            :class:`RedactionMode`.
        payload: Optional payload dict to check for dual-hash conformance.

    Returns:
        A list of issue description strings; an empty list means the policy
        and (if provided) payload conform to the redaction contract.

    This validator is NOT wired into CL2 persistence (see module docstring).
    """
    issues: list[str] = []

    mode = policy.redaction_mode
    if mode not in _VALID_REDACTION_MODES:
        issues.append(
            f"Unknown redaction_mode {mode!r}; expected one of "
            f"{sorted(m.value for m in _VALID_REDACTION_MODES)}"
        )
        return issues

    # No redaction requested: the dual-hash contract does not apply.
    if mode == RedactionMode.NONE:
        return issues

    # DEFAULT_ON / ALWAYS: dual-hash contract applies when a payload is given.
    if payload is None:
        return issues

    if not _has_hash(payload, _REDACTED_PROMPT_HASH_KEY):
        issues.append(
            f"redaction_mode {mode.value} requires a {_REDACTED_PROMPT_HASH_KEY!r} "
            f"(redacted prompt hash) for safe display, but it is missing or empty"
        )
    if not _has_hash(payload, _RAW_PROMPT_HASH_KEY):
        issues.append(
            f"redaction_mode {mode.value} requires a {_RAW_PROMPT_HASH_KEY!r} "
            f"(raw prompt hash) for audit retention, but it is missing or empty"
        )

    return issues


def is_dual_hash_required(policy: RetentionPayloadPolicy) -> bool:
    """Return ``True`` when the policy's redaction mode requires a dual hash.

    ``DEFAULT_ON`` and ``ALWAYS`` require both a redacted and a raw prompt
    hash; ``NONE`` does not.
    """
    return policy.redaction_mode in _DUAL_HASH_MODES


__all__ = [
    "WIRED_INTO_CL2_PERSISTENCE",
    "is_dual_hash_required",
    "validate_redaction_policy",
]
