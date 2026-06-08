"""Resume-cursor carrier and legacy-resume migration contract.

This module owns two neutral types and one pure function:

* :class:`ResumeCursorRef` — opaque pointer the runtime hands to a plugin
  driver on ``resume``. Arnold does not interpret its body.
* :class:`TrustTransition` — pair of trust-state labels describing how a
  resume changes the runtime's trust posture (e.g. ``unknown`` →
  ``quarantined-manifest-mismatch``).
* :func:`migrate_legacy_resume` — pure read of a legacy persisted state
  blob into an :class:`ResumeCursorRef` plus a :class:`TrustTransition`.
  The migration NEVER writes state; callers own persistence.

Boundary discipline
-------------------

No ``megaplan`` imports.  No forbidden vocabulary literals.  Trust-state
labels and migration outcome labels are runtime-neutral.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

__all__ = [
    "ResumeCursorRef",
    "TrustTransition",
    "TRUST_UNKNOWN",
    "TRUST_TRUSTED",
    "TRUST_QUARANTINED_MANIFEST_MISMATCH",
    "migrate_legacy_resume",
]


# ---------------------------------------------------------------------------
# Trust-state labels (runtime-neutral)
# ---------------------------------------------------------------------------

TRUST_UNKNOWN: str = "unknown"
TRUST_TRUSTED: str = "trusted"
TRUST_QUARANTINED_MANIFEST_MISMATCH: str = "quarantined-manifest-mismatch"


# ---------------------------------------------------------------------------
# Carriers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResumeCursorRef:
    """Opaque pointer the runtime hands to a plugin driver on resume.

    The runtime treats ``cursor`` as opaque bytes-or-mapping; only the
    plugin that emitted the cursor interprets its body.  ``plugin_id``
    and ``run_id`` are runtime-owned identifiers used to route the
    cursor back to the correct plugin and run.
    """

    plugin_id: str
    run_id: str
    cursor: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TrustTransition:
    """A transition between two trust-state labels.

    Both labels are opaque strings (``unknown``, ``trusted``,
    ``quarantined-manifest-mismatch``, …). Arnold does not impose policy
    on what a label means — plugins read the post-transition label and
    decide whether to accept the resume.
    """

    before: str
    after: str


# ---------------------------------------------------------------------------
# Legacy-resume migration
# ---------------------------------------------------------------------------


_MALFORMED_RESULT: tuple[None, TrustTransition] = (
    None,
    TrustTransition(TRUST_UNKNOWN, TRUST_UNKNOWN),
)


def _is_str(v: Any) -> bool:
    return isinstance(v, str) and bool(v)


def migrate_legacy_resume(
    legacy_state: Any,
    *,
    current_manifest_hash: str,
) -> tuple[ResumeCursorRef | None, TrustTransition]:
    """Read a legacy persisted state blob and produce an Arnold resume.

    Parameters
    ----------
    legacy_state
        A ``dict``-shaped mapping previously written by a legacy plugin.
        Either the legacy ``phase`` key or the legacy ``stage`` key may
        identify the in-flight step; both are accepted and both are
        excluded from the cursor payload (they encode plugin-owned
        vocabulary the runtime never re-interprets).
    current_manifest_hash
        The manifest hash recorded against the *current* plugin build.
        Compared against ``legacy_state["manifest_hash"]`` (or
        ``manifest_sha256``) to decide the post-migration trust state.

    Returns
    -------
    ``(ResumeCursorRef | None, TrustTransition)``
        ``(None, TrustTransition("unknown", "unknown"))`` for every
        malformed-state case (non-mapping input, missing identifiers,
        non-string identifiers).  On a manifest-hash mismatch, the
        post-state label is ``quarantined-manifest-mismatch``.  On an
        already-migrated state (an existing ``runtime_envelope`` block
        with a usable ``resume_cursor``), the call is idempotent and
        returns the same cursor + a trusted transition.

    This function is pure — it never writes ``legacy_state`` or any
    other persistence target.
    """
    if not isinstance(legacy_state, Mapping):
        return _MALFORMED_RESULT

    # -- Idempotent path: already migrated ----------------------------------
    envelope_block = legacy_state.get("runtime_envelope")
    if isinstance(envelope_block, Mapping):
        plugin_id = envelope_block.get("plugin_id")
        run_id = envelope_block.get("run_id")
        existing_cursor = envelope_block.get("resume_cursor")
        if not (_is_str(plugin_id) and _is_str(run_id)):
            return _MALFORMED_RESULT
        cursor_body: Mapping[str, Any]
        if isinstance(existing_cursor, Mapping):
            cursor_body = dict(existing_cursor)
        else:
            cursor_body = {}
        # Already-migrated states do not re-run the hash check; the runtime
        # has already trusted (or quarantined) the state on the first
        # migration and recorded the outcome in the envelope block.
        return (
            ResumeCursorRef(
                plugin_id=str(plugin_id),
                run_id=str(run_id),
                cursor=cursor_body,
            ),
            TrustTransition(TRUST_UNKNOWN, TRUST_TRUSTED),
        )

    # -- Fresh-migration path -----------------------------------------------
    plugin_id = legacy_state.get("plugin_id")
    run_id = legacy_state.get("run_id")
    if not (_is_str(plugin_id) and _is_str(run_id)):
        return _MALFORMED_RESULT

    if not _is_str(current_manifest_hash):
        return _MALFORMED_RESULT

    legacy_hash = legacy_state.get("manifest_hash")
    if not _is_str(legacy_hash):
        legacy_hash = legacy_state.get("manifest_sha256")
    if not _is_str(legacy_hash):
        return _MALFORMED_RESULT

    # Excluded legacy step-identifier keys (plugin-owned vocabulary) must
    # NOT leak into the neutral cursor payload.
    excluded_keys = {
        "phase",
        "stage",
        "plugin_id",
        "run_id",
        "manifest_hash",
        "manifest_sha256",
        "runtime_envelope",
    }
    cursor_payload: dict[str, Any] = {
        k: v for k, v in legacy_state.items() if k not in excluded_keys
    }

    if legacy_hash != current_manifest_hash:
        return (
            ResumeCursorRef(
                plugin_id=str(plugin_id),
                run_id=str(run_id),
                cursor=cursor_payload,
            ),
            TrustTransition(TRUST_UNKNOWN, TRUST_QUARANTINED_MANIFEST_MISMATCH),
        )

    return (
        ResumeCursorRef(
            plugin_id=str(plugin_id),
            run_id=str(run_id),
            cursor=cursor_payload,
        ),
        TrustTransition(TRUST_UNKNOWN, TRUST_TRUSTED),
    )
