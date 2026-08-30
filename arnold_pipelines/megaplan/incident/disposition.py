"""Canonical disposition records and the non-signalling disposition CLI.

The helper records evidence; it deliberately never calls ``kill``.  Signal
sites can therefore enforce record-before-signal by invoking this module and
only signalling after a successful acknowledgement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from typing import Any

from .ledger import IncidentLedger
from .schema import (
    CauseKind,
    DispositionMode,
    NonWorkerSignalDisposition,
    ObservedProcessDeath,
    WorkerDisposition,
    confirmation_ttl_s,
    validate_nbf_event,
)


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def confirmation_id(*, site_id: str, subject_class: str, victim_pid: int, victim_process_start_identity: str, relevant_progress_identity: str, supervisor_incarnation_identity: str, cause_kind: str, schema_version: int = 1) -> str:
    return _digest({"confirmation_schema_version": schema_version, "site_id": site_id, "subject_class": subject_class, "victim_pid": victim_pid, "victim_process_start_identity": victim_process_start_identity, "relevant_progress_identity": relevant_progress_identity, "supervisor_incarnation_identity": supervisor_incarnation_identity, "cause_kind": cause_kind})


def record_disposition(ledger: IncidentLedger, disposition: WorkerDisposition | ObservedProcessDeath | NonWorkerSignalDisposition | dict[str, Any]) -> dict[str, Any]:
    """Validate and synchronously append a disposition through the ledger."""
    return ledger.append_disposition(disposition)


def observe_confirmation(ledger: IncidentLedger, *, site_id: str, subject_class: str, plan_id: str | None, admission_receipt_id: str | None, victim_pid: int, victim_process_start_identity: str, relevant_progress_identity: str, supervisor_incarnation_identity: str, cause_kind: str, scan_interval_s: float, confirmation_policy_identity: str = "default-v1", observed_at: str | None = None, evidence: Any = None, actor: str = "supervisor") -> dict[str, Any]:
    if not isinstance(victim_pid, int) or isinstance(victim_pid, bool) or victim_pid <= 0:
        raise ValueError("victim_pid must be positive")
    ttl = confirmation_ttl_s(scan_interval_s)
    observed = observed_at or datetime.now(timezone.utc).isoformat()
    # ISO strings are compared by callers; timestamps are persisted verbatim
    # to preserve external clock evidence.
    try:
        first = datetime.fromisoformat(observed.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be ISO-8601") from exc
    cid = confirmation_id(site_id=site_id, subject_class=subject_class, victim_pid=victim_pid, victim_process_start_identity=victim_process_start_identity, relevant_progress_identity=relevant_progress_identity, supervisor_incarnation_identity=supervisor_incarnation_identity, cause_kind=cause_kind)
    payload = {"schema_version": 1, "event_type": "supervision_confirmation_observed", "event_id": _digest(("observed", cid, observed)), "confirmation_id": cid, "site_id": site_id, "subject_class": subject_class, "plan_id": plan_id, "admission_receipt_id": admission_receipt_id, "victim_pid": victim_pid, "victim_process_start_identity": victim_process_start_identity, "relevant_progress_identity": relevant_progress_identity, "supervisor_incarnation_identity": supervisor_incarnation_identity, "cause_kind": cause_kind, "scan_interval_s": scan_interval_s, "confirmation_policy_identity": confirmation_policy_identity, "first_observed_at": observed, "expires_at": (first.timestamp() + ttl), "evidence_digest": _digest(evidence if evidence is not None else {}), "recorded_at": datetime.now(timezone.utc).isoformat(), "actor": actor}
    return ledger.observe_confirmation(payload)


def consume_confirmation(ledger: IncidentLedger, *, confirmation_id_value: str, second_observed_at: str, second_evidence: Any, actor: str = "supervisor", disposition_id: str | None = None, victim_pid: int | None = None, victim_process_start_identity: str | None = None, relevant_progress_identity: str | None = None, supervisor_incarnation_identity: str | None = None, cause_kind: str | None = None, scan_interval_s: float | None = None, expires_at: float | None = None, confirmation_policy_identity: str | None = None, schema_version: int | None = None) -> dict[str, Any]:
    """Consume proof only when every second-scan identity is supplied."""
    required = {
        "victim_pid": victim_pid,
        "victim_process_start_identity": victim_process_start_identity,
        "relevant_progress_identity": relevant_progress_identity,
        "supervisor_incarnation_identity": supervisor_incarnation_identity,
        "cause_kind": cause_kind,
        "scan_interval_s": scan_interval_s,
        "expires_at": expires_at,
        "confirmation_policy_identity": confirmation_policy_identity,
        "schema_version": schema_version,
    }
    if any(value is None for value in required.values()):
        raise ValueError("confirmation identity is mandatory for the second scan")
    return ledger.consume_confirmation(
        confirmation_id=confirmation_id_value,
        second_observed_at=second_observed_at,
        second_evidence_digest=_digest(second_evidence),
        victim_pid=victim_pid,
        victim_process_start_identity=victim_process_start_identity,
        relevant_progress_identity=relevant_progress_identity,
        supervisor_incarnation_identity=supervisor_incarnation_identity,
        cause_kind=cause_kind,
        scan_interval_s=scan_interval_s,
        expires_at=expires_at,
        confirmation_policy_identity=confirmation_policy_identity,
        schema_version=schema_version,
        disposition_id=disposition_id,
        actor=actor,
    )


def _record_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m arnold_pipelines.megaplan.incident.disposition record")
    parser.add_argument("record", choices=("record",))
    parser.add_argument("--ledger-root", required=True)
    parser.add_argument("--json-stdin", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.buffer.read()
        if not raw.strip() or not raw.decode("utf-8"):
            raise ValueError("stdin must contain one UTF-8 JSON object")
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("stdin must contain one JSON object")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"disposition schema error: {exc}", file=sys.stderr)
        return 2
    try:
        ledger_root = __import__("pathlib").Path(args.ledger_root)
        if not ledger_root.exists() or not ledger_root.is_dir():
            raise ValueError("ledger root must be an existing directory")
        ledger = IncidentLedger(ledger_root)
    except (OSError, ValueError) as exc:
        print(f"invalid ledger location: {exc}", file=sys.stderr)
        return 4
    try:
        # Schema is always the first semantic gate.  This prevents malformed
        # worker payloads from being reclassified as a missing confirmation.
        validate_nbf_event(payload)
    except ValueError as exc:
        print(f"disposition schema error: {exc}", file=sys.stderr)
        return 2
    try:
        # A CLI worker disposition is a sustained-proof consumer.  Confirmation
        # lookup is read-only here; append_disposition rechecks it under the
        # ledger lock before committing the disposition.
        if payload.get("event_type") == "worker_disposition" and not payload.get("confirmation_event_id"):
            print("required confirmation missing", file=sys.stderr)
            return 5
        confirmation_ref = payload.get("confirmation_event_id")
        if confirmation_ref:
            confirmation = ledger.projection().get("confirmations", {}).get(confirmation_ref)
            if not confirmation or not confirmation.get("consumed") or confirmation.get("expired") or confirmation.get("replaced"):
                print("required confirmation missing or not consumed", file=sys.stderr)
                return 5
            if payload.get("event_type") == "worker_disposition":
                evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
                identity_pairs = (
                    ("admission_receipt_id", payload.get("admission_receipt_id")),
                    ("victim_pid", payload.get("victim_pid")),
                    ("victim_process_start_identity", payload.get("victim_process_start_identity")),
                    ("cause_kind", payload.get("cause_kind")),
                    ("relevant_progress_identity", payload.get("relevant_progress_identity", evidence.get("relevant_progress_identity"))),
                    ("supervisor_incarnation_identity", payload.get("supervisor_incarnation_identity", evidence.get("supervisor_incarnation_identity"))),
                )
                if any(value is None or confirmation.get(name) != value for name, value in identity_pairs if name in confirmation):
                    print("required confirmation identity mismatch", file=sys.stderr)
                    return 5
                consumed = next((r.get("payload", {}) for r in ledger.read_nbf_events() if r.get("payload", {}).get("event_type") == "supervision_confirmation_consumed" and r.get("payload", {}).get("confirmation_id") == confirmation_ref), None)
                # A consumed proof is single-use.  The sole successful CLI
                # consumer must be the disposition it was bound to; an
                # unbound or differently bound replay is status 5.
                if not consumed or consumed.get("disposition_id") != payload.get("disposition_id"):
                    print("required confirmation disposition mismatch", file=sys.stderr)
                    return 5
                if any(r.get("payload", {}).get("event_type") == "worker_disposition"
                       and r.get("payload", {}).get("disposition_id") == payload.get("disposition_id")
                       for r in ledger.read_nbf_events()):
                    print("disposition replay already consumed", file=sys.stderr)
                    return 5
        record = ledger.append_disposition(payload)
    except OSError as exc:
        print(f"ledger append failure: {exc}", file=sys.stderr)
        return 3
    except ValueError as exc:
        # At this point payload validation already succeeded.  A ValueError is
        # therefore a durable ledger/context failure, not malformed input.
        message = str(exc)
        if "confirmation" in message:
            print(f"required confirmation unavailable: {exc}", file=sys.stderr)
            return 5
        print(f"ledger append failure: {exc}", file=sys.stderr)
        return 3
    record_payload = record.get("payload", {})
    record_identity = record_payload.get("event_id") or record_payload.get("disposition_id") or record_payload.get("observation_id")
    out = {"disposition_id": payload.get("disposition_id") or payload.get("observation_id"), "ledger_event_id": record_identity, "record_id": record_identity}
    print(json.dumps(out, sort_keys=True, separators=(",", ":")))
    return 0


def main(argv: list[str] | None = None) -> int:
    return _record_cli(list(argv) if argv is not None else sys.argv[1:])


__all__ = ["WorkerDisposition", "ObservedProcessDeath", "NonWorkerSignalDisposition", "record_disposition", "confirmation_id", "confirmation_ttl_s", "observe_confirmation", "consume_confirmation", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
