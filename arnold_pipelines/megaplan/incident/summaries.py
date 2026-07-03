"""Projection-derived, redacted incident/problem summaries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.cloud.redact import redact_payload, redact_text
from arnold_pipelines.megaplan.incident.projection import rebuild_projections
from arnold_pipelines.megaplan.incident.schema import MAX_COMMITTED_OUTPUT_BYTES

_LEDGER_DIR = Path(".megaplan") / "incident-ledger"
_SUMMARIES_DIR = _LEDGER_DIR / "summaries"
_SUMMARY_TEXT_LIMIT_BYTES = 2 * 1024
_REDACTION_ENV: dict[str, str] = {}
_SUMMARY_TEXT_TRUNCATION = " [truncated to fit 2KB summary gate]"
_MAX_EVIDENCE_REFS = 64
_ALLOWED_EVIDENCE_KEYS = {
    "action",
    "artifact_id",
    "artifact_path",
    "commit",
    "event_id",
    "hash",
    "kind",
    "number",
    "path",
    "repo",
    "seq",
    "session_id",
    "sha256",
    "status",
    "url",
}


def write_projection_summaries(
    *,
    projections: dict[str, Any] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Write compact summary documents under ``.megaplan/incident-ledger/summaries``."""
    workspace_root = Path.cwd() if root is None else Path(root)
    docs = projections or rebuild_projections(workspace_root)
    summary_root = workspace_root / _SUMMARIES_DIR
    incidents_dir = summary_root / "incidents"
    problems_dir = summary_root / "problems"
    incidents_dir.mkdir(parents=True, exist_ok=True)
    problems_dir.mkdir(parents=True, exist_ok=True)

    incident_summaries: list[dict[str, Any]] = []
    for incident in docs.get("incidents", {}).get("incidents", []):
        summary_doc = _incident_summary_doc(incident, docs.get("incidents", {}).get("source", {}))
        path = incidents_dir / f"{incident['incident_id']}.json"
        _write_summary_doc(path, summary_doc)
        incident_summaries.append({"incident_id": incident["incident_id"], "path": str(path.relative_to(workspace_root))})

    problem_summaries: list[dict[str, Any]] = []
    for problem in docs.get("problems", {}).get("problems", []):
        summary_doc = _problem_summary_doc(problem, docs.get("problems", {}).get("source", {}))
        path = problems_dir / f"{problem['problem_id']}.json"
        _write_summary_doc(path, summary_doc)
        problem_summaries.append({"problem_id": problem["problem_id"], "path": str(path.relative_to(workspace_root))})

    manifest = {
        "schema_version": 1,
        "generated_at": _utc_now_iso(),
        "incident_count": len(incident_summaries),
        "problem_count": len(problem_summaries),
        "incidents": incident_summaries,
        "problems": problem_summaries,
    }
    _write_summary_doc(summary_root / "index.json", manifest)
    return manifest


def _incident_summary_doc(incident: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    summary_text = _cap_summary_text(
        f"{incident.get('incident_id')}: {incident.get('summary', '')}"
    )
    evidence_refs = _sanitize_evidence_refs(incident.get("evidence_refs", []))
    return {
        "schema_version": 1,
        "kind": "incident_summary",
        "generated_at": _utc_now_iso(),
        "incident_id": incident.get("incident_id"),
        "problem_ids": incident.get("problem_ids", []),
        "summary_text": summary_text,
        "state": incident.get("state"),
        "outcome": incident.get("outcome"),
        "latest_actor": incident.get("latest_actor"),
        "next_expected_event": incident.get("next_expected_event"),
        "deadline_ts": incident.get("deadline_ts"),
        "placeholders": redact_payload(incident.get("placeholders", {}), env=_REDACTION_ENV),
        "source": {
            "projection": "incidents",
            "digest": source.get("digest"),
            "last_seq": incident.get("last_seq"),
        },
        "evidence_ref_count": len(evidence_refs),
        "evidence_refs": evidence_refs,
    }


def _problem_summary_doc(problem: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    summary_text = _cap_summary_text(
        f"{problem.get('problem_id')}: {problem.get('title', '')}"
    )
    return {
        "schema_version": 1,
        "kind": "problem_summary",
        "generated_at": _utc_now_iso(),
        "problem_id": problem.get("problem_id"),
        "summary_text": summary_text,
        "status": problem.get("status"),
        "occurrence_count": problem.get("occurrence_count"),
        "recurred_after_fix": problem.get("recurred_after_fix"),
        "owner_actor": problem.get("owner_actor"),
        "next_review_ts": problem.get("next_review_ts"),
        "linked_incident_ids": problem.get("linked_incident_ids", []),
        "fix_commits": problem.get("fix_commits", []),
        "source": {
            "projection": "problems",
            "digest": source.get("digest"),
            "last_seq": problem.get("last_seen_seq"),
        },
    }


def _write_summary_doc(path: Path, doc: dict[str, Any]) -> None:
    serialized = _serialize_summary_doc(_shrink_summary_doc(doc))
    if len(serialized.encode("utf-8")) > MAX_COMMITTED_OUTPUT_BYTES:
        raise ValueError(f"summary file exceeds {MAX_COMMITTED_OUTPUT_BYTES} bytes after shrinking: {path}")
    path.write_text(serialized + "\n", encoding="utf-8")


def _shrink_summary_doc(doc: dict[str, Any]) -> dict[str, Any]:
    result = redact_payload(doc, env=_REDACTION_ENV)
    evidence_refs = result.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        return result

    original_count = len(evidence_refs)
    trimmed = evidence_refs[:_MAX_EVIDENCE_REFS]
    omitted = original_count - len(trimmed)
    result["evidence_refs"] = trimmed
    if omitted > 0:
        result["omitted_evidence_ref_count"] = omitted

    while len(_serialize_summary_doc(result).encode("utf-8")) > MAX_COMMITTED_OUTPUT_BYTES and result["evidence_refs"]:
        result["evidence_refs"] = result["evidence_refs"][:-1]
        result["omitted_evidence_ref_count"] = original_count - len(result["evidence_refs"])

    if len(_serialize_summary_doc(result).encode("utf-8")) > MAX_COMMITTED_OUTPUT_BYTES:
        result["evidence_refs"] = []
        result["omitted_evidence_ref_count"] = original_count
    return result


def _sanitize_evidence_refs(evidence_refs: list[Any]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for ref in evidence_refs:
        if not isinstance(ref, dict):
            continue
        compact = {
            key: redact_payload(value, env=_REDACTION_ENV)
            for key, value in ref.items()
            if key in _ALLOWED_EVIDENCE_KEYS
        }
        if compact:
            sanitized.append(compact)
    return sanitized


def _cap_summary_text(text: str) -> str:
    redacted = redact_text(text, env=_REDACTION_ENV)
    encoded = redacted.encode("utf-8")
    if len(encoded) <= _SUMMARY_TEXT_LIMIT_BYTES:
        return redacted
    suffix_bytes = _SUMMARY_TEXT_TRUNCATION.encode("utf-8")
    allowed = _SUMMARY_TEXT_LIMIT_BYTES - len(suffix_bytes)
    truncated = encoded[:allowed].decode("utf-8", errors="ignore")
    while len((truncated + _SUMMARY_TEXT_TRUNCATION).encode("utf-8")) > _SUMMARY_TEXT_LIMIT_BYTES and truncated:
        truncated = truncated[:-1]
    return truncated + _SUMMARY_TEXT_TRUNCATION


def _serialize_summary_doc(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=2, sort_keys=True)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["write_projection_summaries"]
