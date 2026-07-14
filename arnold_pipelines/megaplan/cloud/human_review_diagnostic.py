"""Durably launch one resident-owned diagnostic for a human-review escalation.

The watchdog is a long-lived machine process, so it normally no longer has the
Discord request envelope in its environment.  Cloud launch persists that exact
routing-only envelope in the immutable session marker.  This module validates
and rehydrates that envelope, then delegates through the canonical resident
subagent seam.  It never constructs ``discord_origin`` itself.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.cloud.human_blockers import compute_escalation_id
from arnold_pipelines.megaplan.cloud.redact import redact_payload, redact_text
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.provenance import (
    DELEGATION_CONTEXT_ENV,
    DelegationProvenanceError,
    encoded_provenance,
    normalize_delegation_provenance,
    provenance_from_environment,
)
from arnold_pipelines.megaplan.resident.subagent import launch_subagent_task

SCHEMA = "arnold-human-review-diagnostic-v1"
_ESCALATION_ID = re.compile(r"^esc-[a-f0-9]{16}$")
_MAX_EVIDENCE_CHARS = 18_000
_MAX_ERROR_CHARS = 1_500


@dataclass(frozen=True)
class HumanReviewDiagnosticResult:
    ok: bool
    status: str
    escalation_id: str
    state_path: str
    run_id: str | None = None
    manifest_path: str | None = None
    error: str | None = None
    idempotent_replay: bool = False
    fallback_delivery_required: bool = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _read_optional_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    _atomic_text(path, json.dumps(dict(payload), indent=2, sort_keys=True) + "\n")


def _bounded(value: Any, *, depth: int = 0) -> Any:
    if depth >= 6:
        return "<nested evidence omitted>"
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(value, key=lambda item: str(item))[:48]:
            if str(key) in {"resident_delegation", "notification_context"}:
                continue
            result[str(key)] = _bounded(value[key], depth=depth + 1)
        return result
    if isinstance(value, list):
        return [_bounded(item, depth=depth + 1) for item in value[-6:]]
    if isinstance(value, tuple):
        return [_bounded(item, depth=depth + 1) for item in value[-6:]]
    if isinstance(value, str):
        return value if len(value) <= 2_500 else value[:2_500] + "…<truncated>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:2_500]


def _repair_tail(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    result: dict[str, Any] = {}
    for key in (
        "session",
        "workspace",
        "spec",
        "run_kind",
        "plan_name",
        "outcome",
        "summary",
        "current_failure_context",
        "latest_failure",
    ):
        if key in payload:
            result[key] = payload[key]
    for key in ("attempts", "iterations"):
        value = payload.get(key)
        if isinstance(value, list):
            result[key] = value[-3:]
    return result


def _evidence_snapshot(
    *,
    payload: Mapping[str, Any],
    marker: Mapping[str, Any],
    repair_data_dir: Path,
    session: str,
) -> dict[str, Any]:
    needs_human = _read_optional_object(repair_data_dir / f"{session}.needs-human.json")
    repair_data = _read_optional_object(repair_data_dir / f"{session}.repair-data.json")
    evidence = redact_payload(
        _bounded(
            {
                "watchdog": payload,
                "session_marker": marker,
                "needs_human": needs_human,
                "repair_tail": _repair_tail(repair_data),
            }
        )
    )
    rendered = json.dumps(evidence, sort_keys=True)
    if len(rendered) <= _MAX_EVIDENCE_CHARS:
        return evidence
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    return {
        "watchdog": _bounded(redact_payload(payload)),
        "session_marker": _bounded(redact_payload(marker)),
        "additional_evidence": {
            "sha256": digest,
            "preview": rendered[:8_000] + "…<bounded snapshot truncated>",
        },
    }


def _resolve_provenance(marker: Mapping[str, Any]) -> dict[str, Any]:
    inherited = provenance_from_environment(strict=True)
    marker_raw = marker.get("resident_delegation")
    marker_provenance = (
        normalize_delegation_provenance(marker_raw)
        if isinstance(marker_raw, Mapping)
        else None
    )
    if inherited is not None and marker_provenance is not None and inherited != marker_provenance:
        raise DelegationProvenanceError(
            "inherited resident provenance conflicts with the cloud session marker"
        )
    provenance = inherited or marker_provenance
    if provenance is None:
        raise DelegationProvenanceError(
            "cloud session marker has no resident delegation provenance"
        )
    if provenance.get("applicability") != "applicable" or provenance.get("transport") != "discord":
        raise DelegationProvenanceError(
            "human-review diagnostic has no originating Discord reply target"
        )
    # The canonical resident launcher reads this exact validated envelope.  It
    # derives discord_origin and the durable completion outbox itself.
    os.environ[DELEGATION_CONTEXT_ENV] = encoded_provenance(provenance)
    return provenance


def _escalation_id(payload: Mapping[str, Any], session: str, repair_data_dir: Path) -> str:
    supplied = str(payload.get("escalation_id") or "").strip()
    if supplied:
        if not _ESCALATION_ID.fullmatch(supplied):
            raise ValueError("payload escalation_id is malformed")
        return supplied
    plan = payload.get("plan") if isinstance(payload.get("plan"), Mapping) else {}
    return compute_escalation_id(
        session,
        current_plan=str(plan.get("name") or ""),
        current_plan_name=str(plan.get("name") or ""),
        needs_human_path=str(repair_data_dir / f"{session}.needs-human.json"),
    )


def _task_text(
    *,
    session: str,
    workspace: Path,
    remote_spec: str,
    evidence_path: Path,
    evidence: Mapping[str, Any],
) -> str:
    inline = json.dumps(evidence, indent=2, sort_keys=True)
    return f"""A Megaplan cloud session reached the terminal human-review path after bounded automatic repair/backstop handling.

Investigate the concrete failure for session `{session}`. This is a read-only diagnostic assignment: do not restart Discord, launch or retire an epic, weaken a completion/quality guard, or claim recovery merely from a derived status label.

Trace custody and causality from ground truth to the deepest/root layer available: live process state, the cloud session marker, chain state, current plan state, relevant log/error evidence, repair/meta-repair evidence, and external PR/CI state when applicable. Determine both (1) the first layer that failed and (2) why its next backstop did not catch or resolve it. Clearly separate known facts, evidence-backed inferences, and unknowns. If the available evidence cannot establish the deepest cause, say exactly what is missing and give the safest bounded probe that would establish it.

Return a concise user-facing diagnosis that includes:
- what concretely failed and the evidence for it;
- the most likely root layer and causal chain, with uncertainty called out;
- a prioritized recommendation for reaching or fixing the deepest cause;
- explicit verification steps that would prove the recommendation worked and detect recurrence.

Bounded routes:
- workspace: {workspace}
- remote chain/spec reference: {remote_spec or '<unknown>'}
- durable diagnostic evidence snapshot: {evidence_path}

Bounded evidence captured at escalation (secrets redacted):
```json
{inline}
```
"""


def _validate_manifest(
    manifest_path: Path,
    *,
    run_id: str,
    provenance: Mapping[str, Any],
) -> None:
    manifest = _read_object(manifest_path)
    if str(manifest.get("run_id") or manifest_path.parent.name) != run_id:
        raise ValueError("resident diagnostic manifest run identity does not match launch result")
    launch_provenance = manifest.get("launch_provenance")
    if not isinstance(launch_provenance, Mapping):
        raise ValueError("resident diagnostic manifest has no launch provenance")
    if normalize_delegation_provenance(launch_provenance) != dict(provenance):
        raise ValueError("resident diagnostic manifest changed immutable Discord provenance")
    delivery = manifest.get("completion_delivery")
    if not isinstance(delivery, Mapping) or delivery.get("transport") != "discord":
        raise ValueError("resident diagnostic manifest has no durable Discord completion delivery")
    target = delivery.get("reply_target")
    if not isinstance(target, Mapping):
        raise ValueError("resident diagnostic manifest has no immutable Discord reply target")
    if (
        str(target.get("message_id") or "") != str(provenance["reply_to_message_id"])
        or str(target.get("source_record_id") or "") != str(provenance["source_record_id"])
    ):
        raise ValueError("resident diagnostic completion delivery changed source custody")
    if not manifest.get("launch_idempotency_key") or not delivery.get("idempotency_key"):
        raise ValueError("resident diagnostic manifest lacks canonical launch/delivery idempotency")


def _result_from_state(state: Mapping[str, Any], state_path: Path) -> HumanReviewDiagnosticResult:
    launched = state.get("status") == "launched"
    fallback = state.get("fallback_delivery")
    fallback_delivered = isinstance(fallback, Mapping) and fallback.get("status") == "delivered"
    return HumanReviewDiagnosticResult(
        ok=launched,
        status=str(state.get("status") or "unknown"),
        escalation_id=str(state.get("escalation_id") or ""),
        state_path=str(state_path),
        run_id=str(state.get("run_id") or "") or None,
        manifest_path=str(state.get("manifest_path") or "") or None,
        error=str(state.get("error") or "") or None,
        idempotent_replay=True,
        fallback_delivery_required=not launched and not fallback_delivered,
    )


def launch_human_review_diagnostic(
    *,
    payload_path: str | Path,
    marker_dir: str | Path,
    repair_data_dir: str | Path,
    project_dir: str | Path,
) -> HumanReviewDiagnosticResult:
    payload = _read_object(Path(payload_path))
    session = str(payload.get("session") or "").strip()
    if not session:
        raise ValueError("human-review payload has no session")
    marker_path = Path(marker_dir) / f"{session}.json"
    marker = _read_object(marker_path)
    provenance = _resolve_provenance(marker)
    repair_root = Path(repair_data_dir).resolve()
    escalation_id = _escalation_id(payload, session, repair_root)
    state_dir = repair_root / "human-review-diagnostics" / escalation_id
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "state.json"
    task_path = state_dir / "task.md"
    evidence_path = state_dir / "evidence.json"
    lock_path = state_dir / ".lock"
    custody_id = str(provenance.get("custody_id") or "")

    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        existing = _read_optional_object(state_path)
        if existing is not None:
            if (
                existing.get("schema_version") != SCHEMA
                or existing.get("escalation_id") != escalation_id
                or existing.get("custody_id") != custody_id
            ):
                raise ValueError("existing diagnostic state conflicts with escalation custody")
            if existing.get("status") == "launched":
                manifest_path = Path(str(existing.get("manifest_path") or ""))
                _validate_manifest(
                    manifest_path,
                    run_id=str(existing.get("run_id") or ""),
                    provenance=provenance,
                )
            return _result_from_state(existing, state_path)

        evidence = _evidence_snapshot(
            payload=payload,
            marker=marker,
            repair_data_dir=repair_root,
            session=session,
        )
        _atomic_json(evidence_path, evidence)
        task = _task_text(
            session=session,
            workspace=Path(project_dir).resolve(),
            remote_spec=str(payload.get("remote_spec") or ""),
            evidence_path=evidence_path,
            evidence=evidence,
        )
        _atomic_text(task_path, task)
        created_at = _utc_now()
        initial_state: dict[str, Any] = {
            "schema_version": SCHEMA,
            "status": "launching",
            "escalation_id": escalation_id,
            "session": session,
            "custody_id": custody_id,
            "source_record_id": provenance.get("source_record_id"),
            "task_path": str(task_path),
            "task_sha256": hashlib.sha256(task.encode("utf-8")).hexdigest(),
            "evidence_path": str(evidence_path),
            "created_at": created_at,
            "updated_at": created_at,
        }
        _atomic_json(state_path, initial_state)

        try:
            launch = asyncio.run(
                launch_subagent_task(
                    ResidentConfig(),
                    task=task,
                    description=f"Diagnose Megaplan human review for {session}",
                    project_dir=str(Path(project_dir).resolve()),
                    task_kind="root_cause",
                    difficulty=9,
                )
            )
            if not launch.ok or not launch.run_id or not launch.manifest_path:
                detail = launch.error or launch.stderr or launch.status or "unknown launch failure"
                raise RuntimeError(detail)
            _validate_manifest(
                Path(launch.manifest_path),
                run_id=launch.run_id,
                provenance=provenance,
            )
        except Exception as exc:
            error = redact_text(f"{exc.__class__.__name__}: {exc}")[:_MAX_ERROR_CHARS]
            failed = {
                **initial_state,
                "status": "launch_failed",
                "error": error,
                "updated_at": _utc_now(),
                "fallback_delivery": {"status": "pending"},
            }
            _atomic_json(state_path, failed)
            return HumanReviewDiagnosticResult(
                ok=False,
                status="launch_failed",
                escalation_id=escalation_id,
                state_path=str(state_path),
                error=error,
                fallback_delivery_required=True,
            )

        launched_state = {
            **initial_state,
            "status": "launched",
            "run_id": launch.run_id,
            "manifest_path": launch.manifest_path,
            "updated_at": _utc_now(),
        }
        _atomic_json(state_path, launched_state)
        return HumanReviewDiagnosticResult(
            ok=True,
            status="launched",
            escalation_id=escalation_id,
            state_path=str(state_path),
            run_id=launch.run_id,
            manifest_path=launch.manifest_path,
        )


def record_fallback_delivery(
    *, state_path: str | Path, result_path: str | Path
) -> dict[str, Any]:
    path = Path(state_path).resolve()
    lock_path = path.parent / ".lock"
    result = _read_optional_object(Path(result_path)) or {}
    message_ids = [str(item) for item in result.get("message_ids", []) if str(item)]
    accepted = bool(result.get("ok")) and (
        bool(message_ids)
        or isinstance(result.get("message_count"), int)
        and int(result["message_count"]) > 0
    )
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = _read_object(path)
        current = state.get("fallback_delivery")
        if isinstance(current, Mapping) and current.get("status") == "delivered":
            return dict(current)
        delivery = {
            "status": "delivered" if accepted else "retry_pending",
            "recorded_at": _utc_now(),
            "reason": str(result.get("reason") or "")[:200],
            "channel_id": str(result.get("channel_id") or "")[:40],
            "message_ids": message_ids[:8],
            "message_count": result.get("message_count"),
        }
        state["fallback_delivery"] = delivery
        state["updated_at"] = delivery["recorded_at"]
        _atomic_json(path, state)
        return delivery


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    launch = sub.add_parser("launch")
    launch.add_argument("--payload-file", required=True)
    launch.add_argument("--marker-dir", required=True)
    launch.add_argument("--repair-data-dir", required=True)
    launch.add_argument("--project-dir", required=True)
    fallback = sub.add_parser("record-fallback")
    fallback.add_argument("--state-path", required=True)
    fallback.add_argument("--result-file", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.action == "record-fallback":
        print(
            json.dumps(
                record_fallback_delivery(
                    state_path=args.state_path, result_path=args.result_file
                ),
                sort_keys=True,
            )
        )
        return 0
    try:
        result = launch_human_review_diagnostic(
            payload_path=args.payload_file,
            marker_dir=args.marker_dir,
            repair_data_dir=args.repair_data_dir,
            project_dir=args.project_dir,
        )
    except Exception as exc:
        result = HumanReviewDiagnosticResult(
            ok=False,
            status="launch_failed",
            escalation_id="",
            state_path="",
            error=redact_text(f"{exc.__class__.__name__}: {exc}")[:_MAX_ERROR_CHARS],
            fallback_delivery_required=True,
        )
    print(json.dumps(asdict(result), sort_keys=True))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
