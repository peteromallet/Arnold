"""Incident ledger append wrapper for the canonical M1 event stream."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import sys
import uuid
from typing import Any, Callable

from arnold.runtime.event_journal import NdjsonEventJournal

from arnold_pipelines.megaplan.incident.schema import validate_incident_event

_INCIDENT_LEDGER_DIR = Path(".megaplan") / "incident-ledger"
_EVENTS_FILE = "events.jsonl"


# ---------------------------------------------------------------------------
# P2 — typed runtime transition events
# ---------------------------------------------------------------------------
# One typed deviation/fallback event path. Every runtime manifest selection,
# declared deviation, and fallback consideration/decision is appended to the
# incident ledger BEFORE the caller performs any dispatch side effect. The
# append is synchronous and never swallowed: a policy rejection (ValueError)
# or a journal write failure (OSError) propagates to the caller, which MUST
# treat it as "do not dispatch". Emitting is a pure append-only ledger write
# — it never dispatches repair and never triggers a scan.

EVENT_MANIFEST_SELECTED = "runtime.manifest_selected"
EVENT_DEVIATION_DECLARED = "runtime.deviation_declared"
EVENT_FALLBACK_CONSIDERED = "runtime.fallback_considered"
EVENT_FALLBACK_TAKEN = "runtime.fallback_taken"
EVENT_FALLBACK_REJECTED = "runtime.fallback_rejected"

RUNTIME_TRANSITION_EVENT_TYPES: tuple[str, ...] = (
    EVENT_MANIFEST_SELECTED,
    EVENT_DEVIATION_DECLARED,
    EVENT_FALLBACK_CONSIDERED,
    EVENT_FALLBACK_TAKEN,
    EVENT_FALLBACK_REJECTED,
)

# Failure-class policy: a fallback may be TAKEN only for retryable
# availability/infrastructure failures. Auth/config, semantic, schema, test,
# evidence, and post-mutation execute failures are permanent deviations —
# they must be recorded as REJECTED, never masked behind a fallback.
RETRYABLE_FAILURE_CLASSES: frozenset[str] = frozenset(
    {"availability", "infrastructure"}
)
NON_RETRYABLE_FAILURE_CLASSES: frozenset[str] = frozenset(
    {"auth", "config", "semantic", "schema", "test", "evidence", "execute"}
)
KNOWN_FAILURE_CLASSES: frozenset[str] = (
    RETRYABLE_FAILURE_CLASSES | NON_RETRYABLE_FAILURE_CLASSES
)

_EVENT_ID_PREFIXES: dict[str, str] = {
    EVENT_MANIFEST_SELECTED: "runtime-manifest-selected",
    EVENT_DEVIATION_DECLARED: "runtime-deviation-declared",
    EVENT_FALLBACK_CONSIDERED: "runtime-fallback-considered",
    EVENT_FALLBACK_TAKEN: "runtime-fallback-taken",
    EVENT_FALLBACK_REJECTED: "runtime-fallback-rejected",
}

_DEFAULT_OUTCOMES: dict[str, str] = {
    EVENT_MANIFEST_SELECTED: "selected",
    EVENT_DEVIATION_DECLARED: "declared",
    EVENT_FALLBACK_CONSIDERED: "considered",
    EVENT_FALLBACK_TAKEN: "taken",
    EVENT_FALLBACK_REJECTED: "rejected",
}

_DEFAULT_SUMMARIES: dict[str, str] = {
    EVENT_MANIFEST_SELECTED: "runtime manifest selected",
    EVENT_DEVIATION_DECLARED: "runtime deviation declared",
    EVENT_FALLBACK_CONSIDERED: "runtime fallback considered",
    EVENT_FALLBACK_TAKEN: "runtime fallback taken",
    EVENT_FALLBACK_REJECTED: "runtime fallback rejected",
}


def is_retryable_failure_class(failure_class: str | None) -> bool:
    """True iff *failure_class* is a retryable availability/infrastructure class."""
    return failure_class in RETRYABLE_FAILURE_CLASSES


def _normalize_chain_digest(digest: str) -> str:
    """Normalize a ``chain_spec_sha256`` contract digest, or ``""`` when empty."""
    digest = str(digest).strip()
    if not digest:
        return ""
    if digest.startswith("sha256:"):
        hex_part = digest[len("sha256:") :]
        if len(hex_part) != 64 or any(
            char not in "0123456789abcdefABCDEF" for char in hex_part
        ):
            raise ValueError(
                "chain_spec_sha256 must be 'sha256:' followed by 64 hex chars "
                f"(got {digest!r})"
            )
        return "sha256:" + hex_part.lower()
    return digest


class _IncidentEventJournal(NdjsonEventJournal):
    """Reuse runtime journal locking/seq semantics with the M1 filename."""

    def __init__(self, artifact_root: Path) -> None:
        super().__init__(artifact_root)
        self._ndjson_path = self._root / _EVENTS_FILE


class IncidentLedger:
    """Append-only incident ledger rooted at ``<root>/.megaplan/incident-ledger``."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = Path.cwd() if root is None else Path(root)
        self._ledger_dir = self._root / _INCIDENT_LEDGER_DIR
        self._journal = _IncidentEventJournal(self._ledger_dir)

    @property
    def ledger_dir(self) -> Path:
        return self._ledger_dir

    @property
    def events_path(self) -> Path:
        return self._ledger_dir / _EVENTS_FILE

    def append_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Redact, validate, and append one incident event to the canonical ledger."""
        payload = validate_incident_event(event)
        return self._journal.emit(
            f"incident.{payload['type']}",
            payload=payload,
        )

    def append_authorized_lifecycle_event(
        self,
        *,
        occurrence_id: str,
        transition: str,
        owner: str,
        grant_id: str,
        custody_epoch: int,
        run_authority_check: Callable[[str, str], bool],
        custody_check: Callable[[str, int, str], bool],
        session_id: str = "",
    ) -> dict[str, Any]:
        """Append an acknowledged/resolved event after live authority rereads.

        The notification store intentionally has no lifecycle writer. This
        method is the canonical incident-owned writer: the current Run
        Authority and Custody sources validate the owner/grant/epoch before
        an append-only event is committed. A card or caller-supplied JSON
        authority blob cannot satisfy either check.
        """
        if transition not in {"acknowledged", "resolved"}:
            raise ValueError("incident lifecycle transition must be acknowledged or resolved")
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("owner must be a non-empty canonical identity")
        if not isinstance(grant_id, str) or not grant_id.strip():
            raise ValueError("grant_id must be a non-empty current grant identity")
        if not isinstance(custody_epoch, int) or isinstance(custody_epoch, bool) or custody_epoch < 1:
            raise ValueError("custody_epoch must be a positive current epoch")
        if not callable(run_authority_check) or not run_authority_check(grant_id, owner):
            raise ValueError("Run Authority grant/owner is not current")
        if not callable(custody_check) or not custody_check(owner, custody_epoch, occurrence_id):
            raise ValueError("Custody owner/epoch is not current")
        occurrence_id = str(occurrence_id).strip()
        if not occurrence_id:
            raise ValueError("occurrence_id must be a non-empty canonical identity")
        event_key = hashlib.sha256(
            json.dumps(
                [occurrence_id, transition, owner, grant_id, custody_epoch],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        return self.append_event(
            {
                "schema_version": 1,
                "event_id": f"incident-lifecycle-{event_key}",
                "ts": now,
                "type": transition,
                "actor": owner,
                "scope": f"incident:{occurrence_id}",
                "outcome": "accepted",
                "summary": f"Incident {transition} through canonical Run Authority and Custody",
                "evidence": [
                    f"run-authority:{grant_id}",
                    f"custody:{owner}:{custody_epoch}",
                ],
                "parent_event_ids": [],
                "next_expected_event": None,
                "deadline_ts": None,
                "trigger_event_id": None,
                "incident_id": occurrence_id,
                "session_id": session_id or None,
                "run_authority_grant_id": grant_id,
                "custody_epoch": custody_epoch,
            }
        )


class RuntimeTransitionWriter:
    """Append-only writer for the five typed runtime transition events.

    Every emit is a pure ledger append routed through :class:`IncidentLedger`
    (validate -> redact -> flocked monotonic append). Emitting NEVER performs
    a dispatch side effect and never triggers a scan — mirror the
    side-effect-free watchdog bridge event pattern.

    Failures propagate and MUST block dispatch:

    * ``ValueError`` — policy rejection (non-retryable ``fallback_taken``,
      unknown failure class, missing required field, malformed digest).
    * ``OSError`` — journal write failure.

    A caller MUST treat either exception as "the transition was not durably
    recorded, so do not perform the dispatch side effect".
    """

    def __init__(
        self,
        root: Path | None = None,
        *,
        ledger: IncidentLedger | None = None,
    ) -> None:
        self._ledger = ledger if ledger is not None else IncidentLedger(root)

    # ── public emit methods ────────────────────────────────────────────

    def emit_manifest_selected(
        self,
        *,
        scope: str,
        candidate_to: str | dict[str, Any],
        candidate_from: str | dict[str, Any] | None = None,
        error: str = "",
        attempt: int | str = "",
        chain_spec_sha256: str = "",
        evidence: list[Any] | None = None,
        actor: str = "runtime",
        session_id: str = "",
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Record ``runtime.manifest_selected`` before a runtime selection."""
        return self._emit(
            EVENT_MANIFEST_SELECTED,
            scope=scope,
            failure_class=None,
            chain_spec_sha256=chain_spec_sha256,
            attempt=attempt,
            error=error,
            evidence=evidence if evidence is not None else [],
            candidate_from=candidate_from,
            candidate_to=candidate_to,
            actor=actor,
            session_id=session_id,
            summary=summary,
        )

    def emit_deviation_declared(
        self,
        *,
        scope: str,
        failure_class: str,
        error: str,
        chain_spec_sha256: str,
        candidate_from: str | dict[str, Any] | None = None,
        candidate_to: str | dict[str, Any] | None = None,
        attempt: int | str = "",
        evidence: list[Any] | None = None,
        actor: str = "runtime",
        session_id: str = "",
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Record ``runtime.deviation_declared`` for a declared deviation."""
        return self._emit(
            EVENT_DEVIATION_DECLARED,
            scope=scope,
            failure_class=failure_class,
            chain_spec_sha256=chain_spec_sha256,
            attempt=attempt,
            error=error,
            evidence=evidence if evidence is not None else [],
            candidate_from=candidate_from,
            candidate_to=candidate_to,
            actor=actor,
            session_id=session_id,
            summary=summary,
        )

    def emit_fallback_considered(
        self,
        *,
        scope: str,
        failure_class: str,
        chain_spec_sha256: str,
        candidate_from: str | dict[str, Any] | None = None,
        candidate_to: str | dict[str, Any] | None = None,
        error: str = "",
        attempt: int | str = "",
        evidence: list[Any] | None = None,
        actor: str = "runtime",
        session_id: str = "",
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Record ``runtime.fallback_considered`` before a fallback decision."""
        return self._emit(
            EVENT_FALLBACK_CONSIDERED,
            scope=scope,
            failure_class=failure_class,
            chain_spec_sha256=chain_spec_sha256,
            attempt=attempt,
            error=error,
            evidence=evidence if evidence is not None else [],
            candidate_from=candidate_from,
            candidate_to=candidate_to,
            actor=actor,
            session_id=session_id,
            summary=summary,
        )

    def emit_fallback_taken(
        self,
        *,
        scope: str,
        failure_class: str,
        chain_spec_sha256: str,
        candidate_from: str | dict[str, Any] | None = None,
        candidate_to: str | dict[str, Any] | None = None,
        error: str = "",
        attempt: int | str = "",
        evidence: list[Any] | None = None,
        actor: str = "runtime",
        session_id: str = "",
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Record ``runtime.fallback_taken`` — only for retryable classes.

        Raises
        ------
        ValueError
            When *failure_class* is not in :data:`RETRYABLE_FAILURE_CLASSES`.
            Non-retryable deviations MUST be recorded with
            :meth:`emit_fallback_rejected` instead.
        """
        return self._emit(
            EVENT_FALLBACK_TAKEN,
            scope=scope,
            failure_class=failure_class,
            chain_spec_sha256=chain_spec_sha256,
            attempt=attempt,
            error=error,
            evidence=evidence if evidence is not None else [],
            candidate_from=candidate_from,
            candidate_to=candidate_to,
            actor=actor,
            session_id=session_id,
            summary=summary,
        )

    def emit_fallback_rejected(
        self,
        *,
        scope: str,
        failure_class: str,
        chain_spec_sha256: str,
        candidate_from: str | dict[str, Any] | None = None,
        candidate_to: str | dict[str, Any] | None = None,
        error: str = "",
        attempt: int | str = "",
        evidence: list[Any] | None = None,
        actor: str = "runtime",
        session_id: str = "",
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Record ``runtime.fallback_rejected`` for a declined fallback."""
        return self._emit(
            EVENT_FALLBACK_REJECTED,
            scope=scope,
            failure_class=failure_class,
            chain_spec_sha256=chain_spec_sha256,
            attempt=attempt,
            error=error,
            evidence=evidence if evidence is not None else [],
            candidate_from=candidate_from,
            candidate_to=candidate_to,
            actor=actor,
            session_id=session_id,
            summary=summary,
        )

    # ── shared emit + failure-class gate ───────────────────────────────

    def _emit(
        self,
        event_type: str,
        *,
        scope: str,
        failure_class: str | None,
        chain_spec_sha256: str,
        attempt: int | str,
        error: str,
        evidence: list[Any],
        candidate_from: str | dict[str, Any] | None,
        candidate_to: str | dict[str, Any] | None,
        actor: str,
        session_id: str,
        summary: str | None,
    ) -> dict[str, Any]:
        if event_type not in _EVENT_ID_PREFIXES:
            raise ValueError(f"unknown runtime transition event type: {event_type!r}")
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("scope must be a non-empty canonical identity")
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("actor must be a non-empty canonical identity")
        if not isinstance(session_id, str):
            raise ValueError("session_id must be a string")
        if not isinstance(error, str):
            raise ValueError("error must be a normalized string")
        if not isinstance(attempt, (int, str)) or isinstance(attempt, bool):
            raise ValueError("attempt must be an int or a string")
        if not isinstance(evidence, list):
            raise ValueError("evidence must be a list")
        for label, value in (
            ("candidate_from", candidate_from),
            ("candidate_to", candidate_to),
        ):
            if value is not None and not isinstance(value, (str, dict)):
                raise ValueError(f"{label} must be a string, a dict, or None")
            if isinstance(value, dict):
                try:
                    json.dumps(value, sort_keys=True, separators=(",", ":"))
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"{label} must be JSON serializable"
                    ) from exc
        chain_spec_sha256 = _normalize_chain_digest(chain_spec_sha256)

        # ── failure-class policy ───────────────────────────────────────
        if failure_class is not None:
            if not isinstance(failure_class, str) or not failure_class.strip():
                raise ValueError("failure_class must be a non-empty string")
            failure_class = failure_class.strip()
            if failure_class not in KNOWN_FAILURE_CLASSES:
                raise ValueError(
                    f"failure_class must be one of {sorted(KNOWN_FAILURE_CLASSES)} "
                    f"(got {failure_class!r})"
                )
        if event_type in {
            EVENT_DEVIATION_DECLARED,
            EVENT_FALLBACK_CONSIDERED,
            EVENT_FALLBACK_TAKEN,
            EVENT_FALLBACK_REJECTED,
        }:
            if not failure_class:
                raise ValueError(f"{event_type} requires a failure_class")
            if not chain_spec_sha256:
                raise ValueError(f"{event_type} requires chain_spec_sha256")
        if event_type == EVENT_FALLBACK_TAKEN and not is_retryable_failure_class(
            failure_class
        ):
            raise ValueError(
                f"runtime.fallback_taken requires a retryable failure class "
                f"(one of {sorted(RETRYABLE_FAILURE_CLASSES)}); non-retryable "
                f"deviations must be recorded with emit_fallback_rejected "
                f"(got {failure_class!r})"
            )

        # ── event assembly ─────────────────────────────────────────────
        base_summary = _DEFAULT_SUMMARIES[event_type]
        if failure_class:
            base_summary = f"{base_summary} (failure_class={failure_class})"
        now = datetime.now(timezone.utc).isoformat()
        event: dict[str, Any] = {
            "schema_version": 1,
            "event_id": f"{_EVENT_ID_PREFIXES[event_type]}-{uuid.uuid4().hex[:12]}",
            "ts": now,
            "type": event_type,
            "actor": actor,
            "scope": scope,
            "outcome": _DEFAULT_OUTCOMES[event_type],
            "summary": summary if summary is not None else base_summary,
            "evidence": evidence,
            "parent_event_ids": [],
            "next_expected_event": None,
            "deadline_ts": None,
            "trigger_event_id": None,
            "candidate_from": candidate_from,
            "candidate_to": candidate_to,
            "error": error,
            "attempt": attempt,
            "chain_spec_sha256": chain_spec_sha256,
            "failure_class": failure_class,
            "session_id": session_id or None,
        }
        return self._ledger.append_event(event)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for bash wrappers: append one typed runtime transition.

    A non-zero exit (or a raised exception) means the transition was NOT
    durably recorded — callers MUST treat it as "do not dispatch". On
    success the full journal envelope (with ``seq`` and ``kind``) is printed
    as one JSON line to stdout.

    Exit codes: 0 = appended; 1 = policy rejection / ledger write failure
    (nothing written); 2 = usage error (argparse).
    """
    short_names = {
        event_type.removeprefix("runtime."): event_type
        for event_type in RUNTIME_TRANSITION_EVENT_TYPES
    }
    choices = list(short_names) + list(RUNTIME_TRANSITION_EVENT_TYPES)

    parser = argparse.ArgumentParser(
        prog="megaplan runtime-transition",
        description=(
            "Append one typed runtime transition event to the incident ledger "
            "BEFORE any dispatch side effect. Non-zero exit = do not dispatch."
        ),
    )
    parser.add_argument(
        "event",
        choices=choices,
        help=(
            "manifest_selected | deviation_declared | fallback_considered | "
            "fallback_taken | fallback_rejected (dotted form also accepted)"
        ),
    )
    parser.add_argument(
        "--root",
        default=None,
        help="workspace root for the incident ledger (default: cwd)",
    )
    parser.add_argument(
        "--scope",
        required=True,
        help="session-scoped identity, e.g. chain:<session-id>",
    )
    parser.add_argument("--actor", default="runtime", help="attribution identity")
    parser.add_argument(
        "--session-id", default="", help="optional session id for the payload"
    )
    parser.add_argument(
        "--candidate-from",
        default=None,
        help="previous candidate: plain string or JSON value",
    )
    parser.add_argument(
        "--candidate-to",
        default=None,
        help="selected/fallback candidate: plain string or JSON value",
    )
    parser.add_argument("--error", default="", help="normalized error string")
    parser.add_argument(
        "--attempt", default="", help="attempt number or attempt id"
    )
    parser.add_argument(
        "--chain-spec-sha256",
        default="",
        help="contract digest 'sha256:<64 hex>' (required for deviation/fallback events)",
    )
    parser.add_argument(
        "--failure-class",
        default=None,
        help="one of availability, infrastructure, auth, config, semantic, schema, test, evidence, execute",
    )
    parser.add_argument(
        "--evidence",
        default="[]",
        help="JSON array of evidence references (default: '[]')",
    )
    parser.add_argument("--summary", default=None, help="override the summary text")

    args = parser.parse_args(argv)
    event_type = short_names.get(args.event, args.event)

    try:
        evidence = json.loads(args.evidence)
        if not isinstance(evidence, list):
            raise ValueError("--evidence must decode to a JSON array")
    except json.JSONDecodeError as exc:
        print(f"invalid --evidence JSON: {exc}", file=sys.stderr)
        return 1

    def _candidate(value: str | None) -> str | dict[str, Any] | None:
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    writer = RuntimeTransitionWriter(Path(args.root) if args.root else None)
    try:
        if event_type == EVENT_MANIFEST_SELECTED:
            appended = writer.emit_manifest_selected(
                scope=args.scope,
                candidate_to=_candidate(args.candidate_to),
                candidate_from=_candidate(args.candidate_from),
                error=args.error,
                attempt=args.attempt,
                chain_spec_sha256=args.chain_spec_sha256,
                evidence=evidence,
                actor=args.actor,
                session_id=args.session_id,
                summary=args.summary,
            )
        else:
            emit = {
                EVENT_DEVIATION_DECLARED: writer.emit_deviation_declared,
                EVENT_FALLBACK_CONSIDERED: writer.emit_fallback_considered,
                EVENT_FALLBACK_TAKEN: writer.emit_fallback_taken,
                EVENT_FALLBACK_REJECTED: writer.emit_fallback_rejected,
            }[event_type]
            appended = emit(
                scope=args.scope,
                failure_class=args.failure_class,
                chain_spec_sha256=args.chain_spec_sha256,
                candidate_from=_candidate(args.candidate_from),
                candidate_to=_candidate(args.candidate_to),
                error=args.error,
                attempt=args.attempt,
                evidence=evidence,
                actor=args.actor,
                session_id=args.session_id,
                summary=args.summary,
            )
    except (ValueError, OSError) as exc:
        print(f"runtime transition not recorded ({event_type}): {exc}", file=sys.stderr)
        return 1

    print(json.dumps(appended, sort_keys=True, separators=(",", ":")))
    return 0


__all__ = [
    "IncidentLedger",
    "RuntimeTransitionWriter",
    "EVENT_MANIFEST_SELECTED",
    "EVENT_DEVIATION_DECLARED",
    "EVENT_FALLBACK_CONSIDERED",
    "EVENT_FALLBACK_TAKEN",
    "EVENT_FALLBACK_REJECTED",
    "RUNTIME_TRANSITION_EVENT_TYPES",
    "RETRYABLE_FAILURE_CLASSES",
    "NON_RETRYABLE_FAILURE_CLASSES",
    "KNOWN_FAILURE_CLASSES",
    "is_retryable_failure_class",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
