"""Deterministic incident/problem projection rebuilds for the M1 ledger."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from arnold.runtime.event_journal import read_event_journal_paged

from arnold_pipelines.megaplan.incident.schema import validate_incident_event

_INCIDENT_LEDGER_DIR = Path(".megaplan") / "incident-ledger"
_EVENTS_FILE = "events.jsonl"
MAX_INCIDENT_JOURNAL_LINE_BYTES = 256 * 1024
_INCIDENTS_FILE = "incidents.json"
_PROBLEMS_FILE = "problems.json"
_TRANSIENT_PATH_RE = re.compile(
    r"(?:(?:/tmp|/var/tmp|/private/tmp|/run/user/\d+|/workspace)/[^\s]+)"
)
_ISO_TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[tT ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\b"
)
_DATE_ONLY_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_HEXISH_TOKEN_RE = re.compile(r"\b[a-f0-9]{12,64}\b", re.IGNORECASE)
_ATTEMPT_TOKEN_RE = re.compile(r"\battempt[-_ ]?\d+\b", re.IGNORECASE)
_PID_TOKEN_RE = re.compile(r"\bpid[-_ :=#]*\d+\b", re.IGNORECASE)
_BARE_NUMBER_RE = re.compile(r"\b\d+\b")
_VOLATILE_TOKEN_RE = re.compile(
    r"\b(?:session|worker|container|sandbox|tmp|temp|run|job|exec|process|proc)\b",
    re.IGNORECASE,
)


def rebuild_projections(
    root: Path | None = None,
    *,
    persist: bool = True,
) -> dict[str, Any]:
    """Rebuild deterministic incident/problem projections from ``events.jsonl``.

    ``persist=False`` keeps evaluator-style callers read-only while returning
    the same in-memory projection documents.
    """
    workspace_root = Path.cwd() if root is None else Path(root)
    ledger_dir = workspace_root / _INCIDENT_LEDGER_DIR
    if persist:
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
        "digest": _sha256_file(events_path)
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
    if persist:
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
    line_count = 0
    with events_path.open("rb") as handle:
        lines = handle
        for line_number, encoded in enumerate(lines, start=1):
            line_count = line_number
            if not encoded.strip():
                continue
            if len(encoded) > MAX_INCIDENT_JOURNAL_LINE_BYTES:
                malformed_count += 1
                findings.append(
                    _finding(
                        "oversized_event_line",
                        message=(
                            f"Incident journal line {line_number} exceeds "
                            f"{MAX_INCIDENT_JOURNAL_LINE_BYTES} bytes"
                        ),
                        line_number=line_number,
                        size_bytes=len(encoded),
                    )
                )
                continue
            try:
                line = encoded.decode("utf-8")
                json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
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
        "line_count": line_count,
        "malformed_count": malformed_count,
        "findings": findings,
    }


def _read_valid_journal_events(events_path: Path) -> list[dict[str, Any]]:
    if not events_path.exists():
        return []
    with tempfile.TemporaryDirectory(prefix="incident-projection-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        with events_path.open("rb") as source, (tmp_root / "events.ndjson").open(
            "wb"
        ) as destination:
            for line in source:
                if len(line) <= MAX_INCIDENT_JOURNAL_LINE_BYTES:
                    destination.write(line)
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
    problem_events: dict[str, list[dict[str, Any]]] = {}

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
        problem_events.setdefault(problem_id, []).append(
            {
                "incident_id": incident_id,
                "payload": payload,
                "seq": compact_event["seq"],
            }
        )
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
        _populate_incident_placeholders(incident, findings)

    for problem in problems.values():
        problem["linked_incident_ids"] = sorted(problem["linked_incident_ids"])
        problem["fix_commits"] = sorted(problem["fix_commits"])
        _populate_problem_status(
            problem,
            problem_events.get(problem["problem_id"], []),
        )

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


def _populate_incident_placeholders(
    incident: dict[str, Any],
    findings: list[dict[str, Any]],
) -> None:
    events = sorted(incident["events"], key=lambda item: item["seq"])
    source_fix_seq: int | None = None
    install_sync_applied_seq: int | None = None
    install_sync_applied_has_runtime_identity = False
    install_sync_failed_seq: int | None = None
    repair_retriggered_seq: int | None = None
    full_chain_verified_seq: int | None = None
    repeated_attempt_detected = False
    recovery_without_full_chain = False
    install_activity_without_source_fix = False
    last_attempt_fingerprint: str | None = None
    repeated_attempt_streak = 0

    for event in events:
        event_type = event["type"]
        seq = event["seq"]

        if event_type == "repair_attempt":
            attempt_fingerprint = _attempt_fingerprint(event)
            if attempt_fingerprint == last_attempt_fingerprint:
                repeated_attempt_streak += 1
            else:
                last_attempt_fingerprint = attempt_fingerprint
                repeated_attempt_streak = 1
            if repeated_attempt_streak >= 3 and not repeated_attempt_detected:
                repeated_attempt_detected = True
                findings.append(
                    _finding(
                        "loop_break_repeated_attempt_no_new_evidence",
                        message="Repeated repair_attempt events did not add a new hypothesis or state change",
                        incident_id=incident["incident_id"],
                        seq=seq,
                    )
                )
        else:
            last_attempt_fingerprint = None
            repeated_attempt_streak = 0

        if event_type == "source_fix_committed":
            source_fix_seq = seq
            install_sync_applied_seq = None
            install_sync_applied_has_runtime_identity = False
            install_sync_failed_seq = None
            repair_retriggered_seq = None
            full_chain_verified_seq = None
            continue

        if event_type == "install_sync_applied":
            if source_fix_seq is None or seq <= source_fix_seq:
                install_activity_without_source_fix = True
                continue
            install_sync_applied_seq = seq
            install_sync_failed_seq = None
            repair_retriggered_seq = None
            full_chain_verified_seq = None
            install_sync_applied_has_runtime_identity = _has_runtime_identity_evidence(
                event["evidence"]
            )
            if not install_sync_applied_has_runtime_identity:
                findings.append(
                    _finding(
                        "install_sync_missing_runtime_identity",
                        message="install_sync_applied is missing runtime identity evidence",
                        incident_id=incident["incident_id"],
                        seq=seq,
                    )
                )
            continue

        if event_type == "install_sync_failed":
            if source_fix_seq is None or seq <= source_fix_seq:
                install_activity_without_source_fix = True
                continue
            install_sync_failed_seq = seq
            install_sync_applied_seq = None
            install_sync_applied_has_runtime_identity = False
            repair_retriggered_seq = None
            full_chain_verified_seq = None
            if not _has_runtime_identity_evidence(event["evidence"]):
                findings.append(
                    _finding(
                        "install_sync_missing_runtime_identity",
                        message="install_sync_failed is missing runtime identity evidence",
                        incident_id=incident["incident_id"],
                        seq=seq,
                    )
                )
            continue

        if event_type == "repair_retriggered":
            if source_fix_seq is None:
                install_activity_without_source_fix = True
                continue
            if install_sync_applied_seq is not None and seq > install_sync_applied_seq:
                repair_retriggered_seq = seq
            continue

        if event_type == "verified_recovered" or event["outcome"] == "recovered":
            if source_fix_seq is None:
                if install_sync_applied_seq is not None or install_sync_failed_seq is not None:
                    install_activity_without_source_fix = True
                continue
            if (
                install_sync_applied_seq is not None
                and repair_retriggered_seq is not None
                and seq > repair_retriggered_seq
            ):
                full_chain_verified_seq = seq
            else:
                recovery_without_full_chain = True

    recurred_after_fix = any(
        full_chain_verified_seq is not None
        and event["seq"] > full_chain_verified_seq
        and not _is_terminal_incident_event(event["type"], event["outcome"])
        for event in events
    )

    if install_activity_without_source_fix:
        findings.append(
            _finding(
                "shipped_fix_missing_source_commit",
                message="Shipped-fix evidence exists without a prior source_fix_committed event",
                incident_id=incident["incident_id"],
                seq=incident["last_seq"],
            )
        )
    if recovery_without_full_chain:
        findings.append(
            _finding(
                "shipped_fix_chain_incomplete",
                message="verified_recovered was recorded before the full shipped-fix chain was proven",
                incident_id=incident["incident_id"],
                seq=incident["last_seq"],
            )
        )

    placeholders = incident["placeholders"]
    if source_fix_seq is None and not install_activity_without_source_fix:
        placeholders["install_freshness"] = "unknown"
        placeholders["shipped_fix"] = "unknown"
    elif install_sync_failed_seq is not None:
        placeholders["install_freshness"] = "failed"
        placeholders["shipped_fix"] = "install_failed"
    elif install_sync_applied_seq is not None:
        placeholders["install_freshness"] = (
            "fresh" if install_sync_applied_has_runtime_identity else "unverified"
        )
        if full_chain_verified_seq is not None:
            placeholders["shipped_fix"] = "shipped"
        elif repair_retriggered_seq is not None:
            placeholders["shipped_fix"] = "pending_verification"
        else:
            placeholders["shipped_fix"] = "pending_retrigger"
    elif source_fix_seq is not None:
        placeholders["install_freshness"] = "stale"
        placeholders["shipped_fix"] = "pending_install"
    else:
        placeholders["install_freshness"] = "unknown"
        placeholders["shipped_fix"] = "broken_chain"

    if recurred_after_fix:
        placeholders["recurrence"] = "recurred_after_fix"
    elif repeated_attempt_detected:
        placeholders["recurrence"] = "repeated_attempts_without_new_evidence"
    elif full_chain_verified_seq is not None:
        placeholders["recurrence"] = "none"
    else:
        placeholders["recurrence"] = "unknown"


def _populate_problem_status(
    problem: dict[str, Any],
    events: list[dict[str, Any]],
) -> None:
    sorted_events = sorted(events, key=lambda item: item["seq"])
    source_fix_seq: int | None = None
    install_sync_applied_seq: int | None = None
    repair_retriggered_seq: int | None = None
    source_fix_chain_activity = False
    status = "open"
    recurred_after_fix = False

    for event in sorted_events:
        payload = event["payload"]
        event_type = payload["type"]
        seq = event["seq"]
        recovered = event_type == "verified_recovered" or payload.get("outcome") == "recovered"

        if recovered:
            if source_fix_seq is None and not source_fix_chain_activity:
                status = "fixed"
                continue
            if (
                source_fix_seq is not None
                and install_sync_applied_seq is not None
                and repair_retriggered_seq is not None
                and seq > repair_retriggered_seq
            ):
                status = "fixed"
            elif source_fix_seq is not None:
                status = "mitigated"
            else:
                status = "open"
            continue

        if status == "fixed":
            recurred_after_fix = True
            status = "open"

        if event_type == "source_fix_committed":
            source_fix_chain_activity = True
            source_fix_seq = seq
            install_sync_applied_seq = None
            repair_retriggered_seq = None
            status = "mitigated" if problem["fix_commits"] else "open"
        elif event_type == "install_sync_applied":
            source_fix_chain_activity = True
            if source_fix_seq is not None and seq > source_fix_seq:
                install_sync_applied_seq = seq
                repair_retriggered_seq = None
                status = "mitigated"
        elif event_type == "install_sync_failed":
            source_fix_chain_activity = True
            if source_fix_seq is not None and seq > source_fix_seq:
                install_sync_applied_seq = None
                repair_retriggered_seq = None
                status = "mitigated"
        elif event_type == "repair_retriggered":
            source_fix_chain_activity = True
            if install_sync_applied_seq is not None and seq > install_sync_applied_seq:
                repair_retriggered_seq = seq
                status = "mitigated"

    problem["recurred_after_fix"] = recurred_after_fix
    problem["status"] = status


def _attempt_fingerprint(event: dict[str, Any]) -> str:
    return json.dumps(
        {
            "actor": event["actor"],
            "summary": event["summary"],
            "outcome": event["outcome"],
            "decision": event.get("decision"),
            "actions": event.get("actions"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _has_runtime_identity_evidence(evidence: list[Any]) -> bool:
    for item in evidence:
        if not isinstance(item, dict):
            continue
        if item.get("kind") == "runtime_identity":
            return True
    return False


def _is_terminal_incident_event(event_type: str, outcome: str) -> bool:
    return event_type in _TERMINAL_STATES or outcome == "recovered"


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
    summary = str(payload["summary"]).lower()
    summary = _TRANSIENT_PATH_RE.sub(" transient_path ", summary)
    summary = _ISO_TIMESTAMP_RE.sub(" timestamp ", summary)
    summary = _DATE_ONLY_RE.sub(" date ", summary)
    summary = _PID_TOKEN_RE.sub(" pid ", summary)
    summary = _ATTEMPT_TOKEN_RE.sub(" attempt ", summary)
    summary = _HEXISH_TOKEN_RE.sub(" transient_id ", summary)
    summary = _BARE_NUMBER_RE.sub(" ", summary)
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
    filtered = [
        token
        for token in normalized_parts
        if not _VOLATILE_TOKEN_RE.fullmatch(token)
    ]
    return " ".join(filtered) or "unknown"


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


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
    *,
    persist: bool = True,
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
    projections = rebuild_projections(workspace_root, persist=persist)

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
