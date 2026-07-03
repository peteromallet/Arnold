"""Deterministic incident/problem projection rebuilds for the M1 ledger."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from arnold.runtime.event_journal import read_event_journal_paged

from arnold_pipelines.megaplan.incident.schema import validate_incident_event

_INCIDENT_LEDGER_DIR = Path(".megaplan") / "incident-ledger"
_EVENTS_FILE = "events.jsonl"
_INCIDENTS_FILE = "incidents.json"
_PROBLEMS_FILE = "problems.json"


def rebuild_projections(root: Path | None = None) -> dict[str, Any]:
    """Rebuild deterministic incident/problem projections from ``events.jsonl``."""
    workspace_root = Path.cwd() if root is None else Path(root)
    ledger_dir = workspace_root / _INCIDENT_LEDGER_DIR
    ledger_dir.mkdir(parents=True, exist_ok=True)
    events_path = ledger_dir / _EVENTS_FILE

    raw_scan = _scan_raw_lines(events_path)
    integrity_findings = list(raw_scan["findings"])
    valid_events = _read_valid_journal_events(events_path)
    incident_events, schema_findings = _validate_incident_events(valid_events)
    integrity_findings.extend(schema_findings)

    incidents, problems, fold_findings = _fold_projection_records(incident_events)
    integrity_findings.extend(fold_findings)

    source_meta = {
        "digest": _sha256_text(events_path.read_text(encoding="utf-8"))
        if events_path.exists()
        else "sha256:" + hashlib.sha256(b"").hexdigest(),
        "event_count": len(incident_events),
        "journal_line_count": raw_scan["line_count"],
        "last_seq": max((event["seq"] for event in incident_events), default=None),
        "malformed_line_count": raw_scan["malformed_count"],
    }
    integrity_findings.extend(
        _projection_divergence_findings(
            ledger_dir / _INCIDENTS_FILE,
            projection_name="incidents",
            source_meta=source_meta,
        )
    )
    integrity_findings.extend(
        _projection_divergence_findings(
            ledger_dir / _PROBLEMS_FILE,
            projection_name="problems",
            source_meta=source_meta,
        )
    )
    integrity_findings = _sorted_findings(integrity_findings)

    incidents_doc = {
        "schema_version": 1,
        "projection": "incidents",
        "source": source_meta,
        "integrity": integrity_findings,
        "incidents": sorted(
            incidents.values(),
            key=lambda item: (item["incident_id"], item["last_seq"], item["first_seq"]),
        ),
    }
    problems_doc = {
        "schema_version": 1,
        "projection": "problems",
        "source": source_meta,
        "integrity": integrity_findings,
        "problems": sorted(
            problems.values(),
            key=lambda item: (item["problem_id"], item["last_seen_seq"], item["first_seen_seq"]),
        ),
    }
    _write_projection(ledger_dir / _INCIDENTS_FILE, incidents_doc)
    _write_projection(ledger_dir / _PROBLEMS_FILE, problems_doc)
    return {
        "incidents": incidents_doc,
        "problems": problems_doc,
    }


def _scan_raw_lines(events_path: Path) -> dict[str, Any]:
    if not events_path.exists():
        return {
            "line_count": 0,
            "malformed_count": 0,
            "findings": [],
        }

    findings: list[dict[str, Any]] = []
    malformed_count = 0
    lines = events_path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            malformed_count += 1
            findings.append(
                _finding(
                    "malformed_json",
                    message=f"Malformed JSON at line {line_number}",
                    line_number=line_number,
                    error=str(exc),
                )
            )
    return {
        "line_count": len(lines),
        "malformed_count": malformed_count,
        "findings": findings,
    }


def _read_valid_journal_events(events_path: Path) -> list[dict[str, Any]]:
    if not events_path.exists():
        return []
    with tempfile.TemporaryDirectory(prefix="incident-projection-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        (tmp_root / "events.ndjson").write_text(
            events_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return read_event_journal_paged(tmp_root, sort_page=True)


def _validate_incident_events(
    journal_events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    incident_events: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for event in journal_events:
        seq = event.get("seq")
        kind = event.get("kind")
        payload = event.get("payload")
        if not isinstance(kind, str) or not kind.startswith("incident."):
            continue
        if not isinstance(payload, dict):
            findings.append(
                _finding(
                    "schema_failure",
                    message="Incident journal payload must be an object",
                    seq=seq,
                    kind=kind,
                )
            )
            continue
        try:
            normalized = validate_incident_event(payload)
        except ValueError as exc:
            findings.append(
                _finding(
                    "schema_failure",
                    message=str(exc),
                    seq=seq,
                    kind=kind,
                    incident_id=_payload_incident_id(payload),
                )
            )
            continue

        incident_events.append(
            {
                "kind": kind,
                "payload": normalized,
                "seq": seq,
                "ts_utc": event.get("ts_utc"),
            }
        )
    return incident_events, findings


def _fold_projection_records(
    incident_events: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    incidents: dict[str, dict[str, Any]] = {}
    problems: dict[str, dict[str, Any]] = {}
    known_event_refs: set[str] = set()

    for event in incident_events:
        payload = event["payload"]
        incident_id = _payload_incident_id(payload)
        incident = incidents.setdefault(incident_id, _new_incident_record(incident_id))
        compact_event = _compact_event(event)
        incident["events"].append(compact_event)
        incident["event_count"] += 1
        incident["first_seq"] = compact_event["seq"] if incident["first_seq"] is None else incident["first_seq"]
        incident["last_seq"] = compact_event["seq"]
        event_ts = _payload_ts(payload)
        incident["first_timestamp"] = incident["first_timestamp"] or event_ts
        incident["last_timestamp"] = event_ts
        incident["state"] = payload["type"]
        incident["outcome"] = payload.get("outcome", "unknown")
        incident["summary"] = payload["summary"]
        incident["latest_actor"] = payload["actor"]
        incident["latest_kind"] = event["kind"]
        incident["next_expected_event"] = payload.get("next_expected_event")
        incident["deadline_ts"] = payload.get("deadline_ts")

        session_id = payload.get("session_id")
        if isinstance(session_id, str) and session_id:
            incident["session_ids"].add(session_id)

        for evidence_ref in payload.get("evidence", []):
            incident["evidence_refs"].append(evidence_ref)

        decision = payload.get("decision")
        if isinstance(decision, dict):
            incident["decisions"].append(
                {"seq": compact_event["seq"], "decision": decision}
            )

        actions = payload.get("actions")
        if isinstance(actions, list):
            incident["actions"].append(
                {"seq": compact_event["seq"], "actions": actions}
            )

        attempt_id = payload.get("attempt_id")
        if isinstance(attempt_id, str) and attempt_id:
            attempt = incident["attempts"].setdefault(
                attempt_id,
                {
                    "attempt_id": attempt_id,
                    "event_seqs": [],
                    "types": [],
                    "latest_outcome": None,
                },
            )
            attempt["event_seqs"].append(compact_event["seq"])
            attempt["types"].append(payload["type"])
            attempt["latest_outcome"] = payload.get("outcome", attempt["latest_outcome"])

        claim_record = _claim_record(payload, compact_event["seq"])
        if claim_record is not None:
            incident["claims"].append(claim_record)

        event_ref = _event_ref(payload, compact_event["seq"])
        known_event_refs.add(event_ref)

        for parent_ref in _normalize_ref_list(payload):
            if parent_ref not in known_event_refs:
                findings.append(
                    _finding(
                        "dangling_parent_ref",
                        message=f"Dangling parent reference {parent_ref!r}",
                        incident_id=incident_id,
                        seq=compact_event["seq"],
                        ref=parent_ref,
                    )
                )

        trigger_ref = _normalize_trigger_ref(payload)
        if trigger_ref is not None and trigger_ref not in known_event_refs:
            findings.append(
                _finding(
                    "dangling_trigger_ref",
                    message=f"Dangling trigger reference {trigger_ref!r}",
                    incident_id=incident_id,
                    seq=compact_event["seq"],
                    ref=trigger_ref,
                )
            )

        problem_id = _problem_id_for_payload(payload)
        problem = problems.setdefault(problem_id, _new_problem_record(problem_id, payload))
        problem["linked_incident_ids"].add(incident_id)
        problem["occurrence_count"] += 1
        problem["last_seen_ts"] = event_ts
        problem["last_seen_seq"] = compact_event["seq"]
        if problem["first_seen_ts"] is None:
            problem["first_seen_ts"] = event_ts
        if problem["first_seen_seq"] is None:
            problem["first_seen_seq"] = compact_event["seq"]
        problem["title"] = problem["title"] or payload["summary"]
        problem["owner_actor"] = payload["actor"]
        if payload["type"] == "source_fix_committed":
            commit_ref = _extract_fix_commit(payload)
            if commit_ref is not None and commit_ref not in problem["fix_commits"]:
                problem["fix_commits"].append(commit_ref)
                problem["status"] = "mitigated"
        if payload["type"] == "verified_recovered" or payload.get("outcome") == "recovered":
            if problem["fix_commits"]:
                problem["status"] = "fixed"
        elif problem["status"] == "fixed":
            problem["recurred_after_fix"] = True
            problem["status"] = "open"

    for incident in incidents.values():
        incident["session_ids"] = sorted(incident["session_ids"])
        incident["problem_ids"] = sorted(
            {
                _problem_id_for_payload(event["payload"])
                for event in incident_events
                if _payload_incident_id(event["payload"]) == incident["incident_id"]
            }
        )
        incident["evidence_refs"] = _stable_sort_json_values(incident["evidence_refs"])
        incident["claims"] = sorted(
            incident["claims"],
            key=lambda item: (item["status"], item["seq"], item.get("claim_id") or ""),
        )
        incident["decisions"] = sorted(
            incident["decisions"],
            key=lambda item: item["seq"],
        )
        incident["actions"] = sorted(
            incident["actions"],
            key=lambda item: item["seq"],
        )
        incident["attempts"] = [
            incident["attempts"][attempt_id]
            for attempt_id in sorted(incident["attempts"])
        ]

    for problem in problems.values():
        problem["linked_incident_ids"] = sorted(problem["linked_incident_ids"])
        problem["fix_commits"] = sorted(problem["fix_commits"])

    return incidents, problems, findings


def _new_incident_record(incident_id: str) -> dict[str, Any]:
    return {
        "incident_id": incident_id,
        "state": "unknown",
        "outcome": "unknown",
        "summary": "",
        "latest_actor": None,
        "latest_kind": None,
        "next_expected_event": None,
        "deadline_ts": None,
        "event_count": 0,
        "first_seq": None,
        "last_seq": None,
        "first_timestamp": None,
        "last_timestamp": None,
        "session_ids": set(),
        "problem_ids": [],
        "events": [],
        "claims": [],
        "attempts": {},
        "actions": [],
        "decisions": [],
        "evidence_refs": [],
        "placeholders": {
            "install_freshness": "unknown",
            "recurrence": "unknown",
            "shipped_fix": "unknown",
        },
    }


def _new_problem_record(problem_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized_signature = _normalized_signature(payload)
    return {
        "problem_id": problem_id,
        "title": payload["summary"],
        "scope": payload.get("scope", "unknown"),
        "normalized_signature": normalized_signature,
        "first_seen_ts": None,
        "last_seen_ts": None,
        "first_seen_seq": None,
        "last_seen_seq": None,
        "occurrence_count": 0,
        "linked_incident_ids": set(),
        "fix_commits": [],
        "recurred_after_fix": False,
        "status": "open",
        "owner_actor": None,
        "next_review_ts": payload.get("deadline_ts"),
    }


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = event["payload"]
    compact = {
        "seq": event["seq"],
        "kind": event["kind"],
        "actor": payload["actor"],
        "type": payload["type"],
        "timestamp": _payload_ts(payload),
        "summary": payload["summary"],
        "outcome": payload.get("outcome", "unknown"),
        "evidence": payload.get("evidence", []),
        "parent": payload.get("parent_event_ids", payload.get("parent", [])),
        "trigger": payload.get("trigger_event_id", payload.get("trigger")),
        "next_expected_event": payload.get("next_expected_event"),
        "deadline_ts": payload.get("deadline_ts"),
        "session_id": payload.get("session_id"),
        "problem_id": payload.get("problem_id"),
        "attempt_id": payload.get("attempt_id"),
        "event_id": payload.get("event_id"),
    }
    if "decision" in payload:
        compact["decision"] = payload["decision"]
    if "actions" in payload:
        compact["actions"] = payload["actions"]
    return compact


def _claim_record(payload: dict[str, Any], seq: int | None) -> dict[str, Any] | None:
    if not (
        payload["type"].startswith("claim.")
        or payload["type"].startswith("claim_")
        or "claim_id" in payload
    ):
        return None
    status = payload["type"].split(".", 1)[-1].split("_", 1)[-1]
    return {
        "claim_id": payload.get("claim_id"),
        "actor": payload["actor"],
        "expected_transition": payload.get("next_expected_event"),
        "status": status,
        "summary": payload["summary"],
        "deadline_ts": payload.get("deadline_ts"),
        "seq": seq,
    }


def _normalize_ref_list(payload: dict[str, Any]) -> list[str]:
    raw_refs = payload.get("parent_event_ids", payload.get("parent", []))
    refs: list[str] = []
    if isinstance(raw_refs, list):
        for ref in raw_refs:
            normalized = _normalize_ref(ref)
            if normalized is not None:
                refs.append(normalized)
    return refs


def _normalize_trigger_ref(payload: dict[str, Any]) -> str | None:
    return _normalize_ref(payload.get("trigger_event_id", payload.get("trigger")))


def _normalize_ref(ref: Any) -> str | None:
    if isinstance(ref, int):
        return f"seq:{ref}"
    if isinstance(ref, str) and ref:
        return ref if not ref.isdigit() else f"seq:{ref}"
    return None


def _event_ref(payload: dict[str, Any], seq: int | None) -> str:
    event_id = payload.get("event_id")
    if isinstance(event_id, str) and event_id:
        return event_id
    return f"seq:{seq}"


def _payload_incident_id(payload: dict[str, Any]) -> str:
    incident_id = payload.get("incident_id")
    if isinstance(incident_id, str) and incident_id:
        return incident_id

    session_id = payload.get("session_id")
    if isinstance(session_id, str) and session_id:
        return f"session:{session_id}"

    event_id = payload.get("event_id")
    if isinstance(event_id, str) and event_id:
        return f"event:{event_id}"

    return "incident:unknown"


def _payload_ts(payload: dict[str, Any]) -> str:
    value = payload.get("ts", payload.get("timestamp"))
    return value if isinstance(value, str) else ""


def _problem_id_for_payload(payload: dict[str, Any]) -> str:
    problem_id = payload.get("problem_id")
    if isinstance(problem_id, str) and problem_id:
        return problem_id
    signature = _normalized_signature(payload)
    digest = hashlib.sha256(
        f"{payload.get('scope', 'unknown')}::{signature}".encode("utf-8")
    ).hexdigest()
    return f"problem-{digest[:12]}"


def _normalized_signature(payload: dict[str, Any]) -> str:
    summary = payload["summary"].lower()
    normalized_parts: list[str] = []
    current = []
    for char in summary:
        if char.isalpha():
            current.append(char)
            continue
        if current:
            normalized_parts.append("".join(current))
            current = []
    if current:
        normalized_parts.append("".join(current))
    return " ".join(normalized_parts) or "unknown"


def _extract_fix_commit(payload: dict[str, Any]) -> str | None:
    links = payload.get("links")
    if isinstance(links, dict):
        for key in ("commit", "commit_sha", "git_commit"):
            value = links.get(key)
            if isinstance(value, str) and value:
                return value
    commit_sha = payload.get("commit_sha")
    if isinstance(commit_sha, str) and commit_sha:
        return commit_sha
    return None


def _projection_divergence_findings(
    path: Path,
    *,
    projection_name: str,
    source_meta: dict[str, Any],
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [
            _finding(
                "index_divergence",
                message=f"{projection_name} projection is not valid JSON",
                projection=projection_name,
                error=str(exc),
            )
        ]

    existing_source = existing.get("source")
    if not isinstance(existing_source, dict):
        return [
            _finding(
                "index_divergence",
                message=f"{projection_name} projection is missing source metadata",
                projection=projection_name,
            )
        ]

    for key in ("digest", "last_seq"):
        if existing_source.get(key) != source_meta.get(key):
            return [
                _finding(
                    "index_divergence",
                    message=(
                        f"{projection_name} projection source metadata diverged for {key}: "
                        f"{existing_source.get(key)!r} != {source_meta.get(key)!r}"
                    ),
                    projection=projection_name,
                    expected=source_meta.get(key),
                    actual=existing_source.get(key),
                )
            ]
    return []


def _write_projection(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_sort_json_values(values: list[Any]) -> list[Any]:
    return sorted(values, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))


def _sorted_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        findings,
        key=lambda item: (
            item["code"],
            item.get("incident_id") or "",
            -1 if item.get("seq") is None else item["seq"],
            -1 if item.get("line_number") is None else item["line_number"],
            item["message"],
        ),
    )


def _finding(code: str, *, message: str, **details: Any) -> dict[str, Any]:
    finding = {
        "code": code,
        "message": message,
        "recommendation": "system.integrity_repair",
        "severity": "error",
    }
    finding.update(details)
    return finding


# ---------------------------------------------------------------------------
# M1 terminal / active incident classification
# ---------------------------------------------------------------------------

_TERMINAL_STATES: frozenset[str] = frozenset(
    {
        "resolved",
        "closed",
        "verified_recovered",
        "cancelled",
        "archived",
    }
)


def _is_active(state: str) -> bool:
    """Return True if *state* is not a recognised terminal state."""
    return state not in _TERMINAL_STATES


# ---------------------------------------------------------------------------
# Public read-only projection views
# ---------------------------------------------------------------------------


def list_incidents(
    active_only: bool = True,
    root: Path | None = None,
) -> list[dict[str, Any]]:
    """Return a lightweight list of incident summaries.

    Parameters
    ----------
    active_only:
        When ``True`` (the default), only incidents whose ``state`` is not
        a recognised terminal state are included.
    root:
        Workspace root directory.  Defaults to the current working directory.
    """
    projections = rebuild_projections(root)
    incidents = projections["incidents"]["incidents"]
    if active_only:
        incidents = [inc for inc in incidents if _is_active(inc["state"])]
    return [
        {
            "incident_id": inc["incident_id"],
            "state": inc["state"],
            "outcome": inc.get("outcome", "unknown"),
            "summary": inc.get("summary", ""),
            "latest_actor": inc.get("latest_actor"),
            "event_count": inc.get("event_count", 0),
            "first_timestamp": inc.get("first_timestamp"),
            "last_timestamp": inc.get("last_timestamp"),
            "deadline_ts": inc.get("deadline_ts"),
            "next_expected_event": inc.get("next_expected_event"),
            "placeholders": inc.get("placeholders"),
        }
        for inc in incidents
    ]


def build_brief(
    id_or_session: str,
    root: Path | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Build a bounded incident brief, resolved by incident or session id.

    The brief includes the current state, next-expected event, deadline
    (with overdue/approaching/ok classification when *now* is supplied),
    active and expired claims, evidence refs with ``MISSING`` markers
    for inaccessible filesystem paths, attempt summaries, M1 placeholders,
    and integrity findings recommending ``system.integrity_repair``.

    Parameters
    ----------
    id_or_session:
        An ``incident_id`` or ``session_id`` to look up.
    root:
        Workspace root directory.  Defaults to the current working directory.
    now:
        ISO-8601-like reference timestamp for deadline classification.
        When omitted no ``deadline_status`` key is emitted.
    """
    workspace_root = Path.cwd() if root is None else Path(root)
    projections = rebuild_projections(workspace_root)

    # ── resolve incident ────────────────────────────────────────────
    incident = _resolve_incident(projections, id_or_session)
    if incident is None:
        return {
            "found": False,
            "query": id_or_session,
            "integrity": _integrity_recommendation(projections),
        }

    # ── deadline status ─────────────────────────────────────────────
    deadline_ts = incident.get("deadline_ts")
    deadline_status = None
    if now is not None and isinstance(deadline_ts, str) and deadline_ts:
        deadline_status = _classify_deadline(deadline_ts, now)

    # ── claims (active vs expired) ──────────────────────────────────
    claims = _classify_claims(incident.get("claims", []), now)

    # ── evidence (with MISSING markers) ─────────────────────────────
    evidence = _annotate_evidence(incident.get("evidence_refs", []), workspace_root)

    # ── attempts summary ────────────────────────────────────────────
    attempts = _summarise_attempts(incident.get("attempts", []))

    # ── assemble brief ──────────────────────────────────────────────
    brief: dict[str, Any] = {
        "found": True,
        "incident_id": incident["incident_id"],
        "state": incident["state"],
        "outcome": incident.get("outcome", "unknown"),
        "summary": incident.get("summary", ""),
        "latest_actor": incident.get("latest_actor"),
        "next_expected_event": incident.get("next_expected_event"),
        "deadline_ts": deadline_ts,
        "event_count": incident.get("event_count", 0),
        "first_timestamp": incident.get("first_timestamp"),
        "last_timestamp": incident.get("last_timestamp"),
        "claims": claims,
        "evidence": evidence,
        "attempts": attempts,
        "placeholders": incident.get("placeholders"),
        "integrity": _integrity_recommendation(projections),
    }
    if deadline_status is not None:
        brief["deadline_status"] = deadline_status

    return brief


# ---------------------------------------------------------------------------
# Brief helpers
# ---------------------------------------------------------------------------


def _resolve_incident(
    projections: dict[str, Any],
    id_or_session: str,
) -> dict[str, Any] | None:
    """Return the first incident matching *id_or_session* by id or session."""
    incidents = projections["incidents"]["incidents"]
    for inc in incidents:
        if inc["incident_id"] == id_or_session:
            return inc
    for inc in incidents:
        if id_or_session in inc.get("session_ids", []):
            return inc
    return None


def _classify_deadline(deadline_ts: str, now: str) -> str:
    """Classify a deadline relative to *now*.

    Returns one of ``"overdue"``, ``"approaching"``, or ``"ok"``.
    Comparison is lexical (ISO-8601 sortability) so it tolerates
    a wide range of timestamp variants.
    """
    if deadline_ts <= now:
        return "overdue"
    # Treat deadlines within the next 5 minutes as "approaching".
    # Simple heuristic: if the prefix up to minutes is the same and the
    # minute delta is <= 5 we call it approaching.
    if (
        len(deadline_ts) >= 16
        and len(now) >= 16
        and deadline_ts[:16] == now[:16]
    ):
        # same YYYY-MM-DDTHH:MM
        try:
            deadline_sec = int(deadline_ts[17:19]) if len(deadline_ts) >= 19 else 0
            now_sec = int(now[17:19]) if len(now) >= 19 else 0
            if 0 <= deadline_sec - now_sec <= 300:  # within 5 min
                return "approaching"
        except (ValueError, IndexError):
            pass
    # Fallback: if deadline is within 5 minutes based on string prefix
    if deadline_ts[:15] == now[:15]:  # YYYY-MM-DDTHH:M
        return "approaching"
    return "ok"


def _classify_claims(
    claims: list[dict[str, Any]],
    now: str | None,
) -> list[dict[str, Any]]:
    """Tag each claim as *active* or *expired* relative to *now*."""
    result: list[dict[str, Any]] = []
    for claim in claims:
        entry = dict(claim)
        if now is not None:
            deadline = claim.get("deadline_ts")
            if isinstance(deadline, str) and deadline:
                entry["classification"] = "expired" if deadline <= now else "active"
            else:
                entry["classification"] = "active"
        else:
            entry["classification"] = "unknown"
        result.append(entry)
    return result


def _annotate_evidence(
    evidence_refs: list[Any],
    workspace_root: Path,
) -> list[dict[str, Any]]:
    """Return evidence refs with ``MISSING`` marker for inaccessible paths."""
    annotated: list[dict[str, Any]] = []
    for ref in evidence_refs:
        entry: dict[str, Any]
        if isinstance(ref, dict):
            entry = dict(ref)
        else:
            entry = {"ref": ref}

        path = entry.get("path")
        if isinstance(path, str):
            full_path = workspace_root / path
            if not full_path.exists():
                entry["status"] = "MISSING"
            else:
                entry["status"] = "present"
        annotated.append(entry)
    return annotated


def _summarise_attempts(
    attempts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return a summary view of each attempt."""
    return [
        {
            "attempt_id": a["attempt_id"],
            "event_count": len(a.get("event_seqs", [])),
            "latest_outcome": a.get("latest_outcome"),
            "types": a.get("types", []),
        }
        for a in attempts
    ]


def _integrity_recommendation(projections: dict[str, Any]) -> dict[str, Any]:
    """Return a brief integrity summary with a repair recommendation."""
    findings = projections.get("incidents", {}).get("integrity", [])
    return {
        "finding_count": len(findings),
        "recommendation": "system.integrity_repair",
        "severity": "error" if findings else "ok",
    }


__all__ = ["build_brief", "list_incidents", "rebuild_projections"]
