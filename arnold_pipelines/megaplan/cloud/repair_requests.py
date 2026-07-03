"""Immutable failure-triggered repair request queue markers."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

from arnold_pipelines.megaplan.cloud import repair_contract
from arnold_pipelines.megaplan.cloud.redact import redact_payload
from arnold_pipelines.megaplan.cloud.repair_recurrence import PROBLEM_SIGNATURE_FIELDS

QUEUE_DIR_NAME = "repair-queue"
REQUESTS_DIR_NAME = "requests"
DECISIONS_DIR_NAME = "decisions"
CURRENT_SCHEMA_VERSION = 1

DecisionKind = Literal["accepted", "coalesced", "stale", "superseded", "malformed", "dispatched"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repair_queue_dir(marker_dir: str | Path) -> Path:
    """Return the marker-dir-adjacent repair queue directory."""

    markers = Path(marker_dir)
    return markers.parent / QUEUE_DIR_NAME


def requests_dir(queue_dir: str | Path) -> Path:
    return Path(queue_dir) / REQUESTS_DIR_NAME


def decisions_dir(queue_dir: str | Path) -> Path:
    return Path(queue_dir) / DECISIONS_DIR_NAME


def normalize_problem_signature(problem_signature: Mapping[str, Any]) -> dict[str, str]:
    """Return only the canonical signature fields, normalized for identity."""

    return {
        field: str(problem_signature.get(field) or "").strip()
        for field in PROBLEM_SIGNATURE_FIELDS
    }


def problem_signature_key(problem_signature: Mapping[str, Any]) -> str:
    normalized = normalize_problem_signature(problem_signature)
    return _sha256_json([normalized[field] for field in PROBLEM_SIGNATURE_FIELDS])


def redacted_hint_hash(root_cause_hint: Any) -> str:
    """Hash the redacted root-cause hint without exposing the raw hint."""

    redacted = redact_payload(root_cause_hint)
    return _sha256_json(redacted)


def request_id_for(
    *,
    session: str,
    problem_signature: Mapping[str, Any],
    root_cause_hint: Any = "",
) -> str:
    """Return a stable request id unaffected by timestamps or raw hint text."""

    return _sha256_json(
        {
            "session": str(session or "").strip(),
            "problem_signature": normalize_problem_signature(problem_signature),
            "root_cause_hint_hash": redacted_hint_hash(root_cause_hint),
        }
    )


def enqueue_repair_request(
    *,
    marker_dir: str | Path,
    session: str,
    problem_signature: Mapping[str, Any],
    root_cause_hint: Any = "",
    source: str,
    target: Mapping[str, Any] | None = None,
    workspace: str | Path | None = None,
    run_kind: str = "",
    created_at: str | None = None,
    stale_reason: str = "",
    superseded_by: str = "",
) -> dict[str, Any]:
    """Write a request marker once, recording any rejection/coalescing separately."""

    queue_root = repair_queue_dir(marker_dir)
    normalized_signature = normalize_problem_signature(problem_signature)
    hint_hash = redacted_hint_hash(root_cause_hint)
    request_id = request_id_for(
        session=session,
        problem_signature=normalized_signature,
        root_cause_hint=root_cause_hint,
    )
    request_path = requests_dir(queue_root) / f"{request_id}.json"
    record = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "kind": "repair_request",
        "request_id": request_id,
        "created_at": created_at or utc_now(),
        "source": str(source or "").strip(),
        "session": str(session or "").strip(),
        "workspace": str(workspace or ""),
        "run_kind": str(run_kind or "").strip(),
        "marker_dir": str(Path(marker_dir)),
        "queue_dir": str(queue_root),
        "target": _stable_mapping(target or {}),
        "problem_signature": normalized_signature,
        "problem_signature_key": problem_signature_key(normalized_signature),
        "root_cause_hint_hash": hint_hash,
        "root_cause_hint_hash_algorithm": "sha256(redact_payload(root_cause_hint))",
    }

    if stale_reason:
        _write_once_json(request_path, record)
        decision = write_decision(
            queue_root,
            request_id=request_id,
            decision="stale",
            reason=stale_reason,
            related_request_id="",
        )
        return {"status": "stale", "request": record, "path": str(request_path), "decision": decision}
    if superseded_by:
        _write_once_json(request_path, record)
        decision = write_decision(
            queue_root,
            request_id=request_id,
            decision="superseded",
            reason="superseded by newer live repair target",
            related_request_id=superseded_by,
        )
        return {"status": "superseded", "request": record, "path": str(request_path), "decision": decision}

    existing = find_pending_by_signature(queue_root, normalized_signature)
    if existing is not None and existing["request_id"] != request_id:
        decision = write_decision(
            queue_root,
            request_id=request_id,
            decision="coalesced",
            reason="matching problem signature already queued",
            related_request_id=existing["request_id"],
        )
        return {"status": "coalesced", "request": record, "path": str(request_path), "decision": decision}

    wrote = _write_once_json(request_path, record)
    if not wrote:
        decision = write_decision(
            queue_root,
            request_id=request_id,
            decision="coalesced",
            reason="request marker already exists",
            related_request_id=request_id,
        )
        return {"status": "coalesced", "request": record, "path": str(request_path), "decision": decision}

    decision = write_decision(
        queue_root,
        request_id=request_id,
        decision="accepted",
        reason="queued",
        related_request_id="",
    )
    return {"status": "queued", "request": record, "path": str(request_path), "decision": decision}


def enqueue_human_gate_repair_request(
    *,
    marker_dir: str | Path,
    session: str,
    workspace: str | Path,
    run_kind: str,
    plan_name: str,
    pipeline_name: str,
    artifact_stage: str,
    step_name: str,
    prompt: str,
) -> dict[str, Any] | None:
    """Megaplan-owned hook used by the neutral human-gate step."""

    from arnold_pipelines.megaplan.cloud.feature_flags import repair_request_queue_enabled

    if not repair_request_queue_enabled():
        return None
    return enqueue_repair_request(
        marker_dir=marker_dir,
        session=session,
        source="human_gate",
        workspace=workspace,
        run_kind=run_kind,
        target={
            "plan_dir": str(marker_dir),
            "plan_name": plan_name,
            "pipeline_name": pipeline_name,
            "workspace_path": str(workspace),
        },
        problem_signature={
            "failure_kind": "human_gate",
            "current_state": pipeline_name,
            "phase_or_step": artifact_stage,
            "milestone_or_plan": step_name,
            "gate_recommendation": "",
            "blocked_task_id": "",
        },
        root_cause_hint=prompt,
    )


def iter_repair_requests(
    marker_dir_or_queue_dir: str | Path,
    *,
    marker_dir: bool = True,
    include_malformed: bool = False,
) -> list[dict[str, Any]]:
    """Return request records in deterministic order, tolerating bad files."""

    queue_root = repair_queue_dir(marker_dir_or_queue_dir) if marker_dir else Path(marker_dir_or_queue_dir)
    records: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []
    for path in sorted(requests_dir(queue_root).glob("*.json"), key=lambda item: item.name):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            malformed.append(_malformed_record(path, exc))
            continue
        if not isinstance(payload, dict):
            malformed.append(_malformed_record(path, ValueError("request marker is not a JSON object")))
            continue
        required = {"schema_version", "kind", "request_id", "problem_signature"}
        if not required.issubset(payload) or payload.get("kind") != "repair_request":
            malformed.append(_malformed_record(path, ValueError("request marker has invalid shape")))
            continue
        payload = dict(payload)
        payload["_path"] = str(path)
        records.append(payload)
    records.sort(key=_request_sort_key)
    if include_malformed:
        records.extend(sorted(malformed, key=lambda item: item["path"]))
    return records


def find_pending_by_signature(
    queue_dir: str | Path,
    problem_signature: Mapping[str, Any],
) -> dict[str, Any] | None:
    key = problem_signature_key(problem_signature)
    decided = _decided_request_ids(queue_dir)
    for record in iter_repair_requests(queue_dir, marker_dir=False):
        if record.get("request_id") in decided:
            continue
        if record.get("problem_signature_key") == key:
            return record
    return None


def write_decision(
    queue_dir: str | Path,
    *,
    request_id: str,
    decision: DecisionKind,
    reason: str,
    related_request_id: str = "",
    created_at: str | None = None,
) -> dict[str, Any]:
    """Write an immutable decision record separate from request markers."""

    when = created_at or utc_now()
    record = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "kind": "repair_request_decision",
        "decision_id": _sha256_json(
            {
                "request_id": request_id,
                "decision": decision,
                "reason": reason,
                "related_request_id": related_request_id,
                "created_at": when,
            }
        ),
        "request_id": str(request_id or "").strip(),
        "decision": decision,
        "reason": str(reason or "").strip(),
        "related_request_id": str(related_request_id or "").strip(),
        "created_at": when,
    }
    path = decisions_dir(queue_dir) / f"{when.replace(':', '').replace('-', '')}-{record['decision_id']}.json"
    _write_once_json(path, record)
    return {**record, "_path": str(path)}


def record_malformed_file(queue_dir: str | Path, path: str | Path, reason: str) -> dict[str, Any]:
    return write_decision(
        queue_dir,
        request_id=_sha256_json(str(Path(path))),
        decision="malformed",
        reason=reason,
        related_request_id=str(path),
    )


def _decided_request_ids(queue_dir: str | Path) -> set[str]:
    decided: set[str] = set()
    for path in sorted(decisions_dir(queue_dir).glob("*.json"), key=lambda item: item.name):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        decision = payload.get("decision")
        if decision in {"stale", "superseded", "dispatched"}:
            request_id = payload.get("request_id")
            if isinstance(request_id, str) and request_id:
                decided.add(request_id)
    return decided


def _write_once_json(path: Path, payload: Mapping[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".claim")
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    try:
        os.close(fd)
        if path.exists():
            return False
        repair_contract.atomic_write_json(path, payload)
        return True
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stable_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value[key] for key in sorted(value)}


def _request_sort_key(record: Mapping[str, Any]) -> tuple[str, str]:
    return (str(record.get("created_at") or ""), str(record.get("request_id") or ""))


def _malformed_record(path: Path, exc: Exception) -> dict[str, Any]:
    return {
        "kind": "malformed_repair_request",
        "path": str(path),
        "reason": str(exc),
    }


__all__ = [
    "PROBLEM_SIGNATURE_FIELDS",
    "DecisionKind",
    "enqueue_human_gate_repair_request",
    "enqueue_repair_request",
    "find_pending_by_signature",
    "iter_repair_requests",
    "normalize_problem_signature",
    "problem_signature_key",
    "record_malformed_file",
    "redacted_hint_hash",
    "repair_queue_dir",
    "request_id_for",
    "write_decision",
]
