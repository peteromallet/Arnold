"""Independent, read-only rederivation for deployed M11 workflow canaries."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from arnold.workflow.attempt_ledger_store import _deserialize_ledger_event
from arnold.workflow.execution_attempt_ledger import AttemptEventType
from arnold_pipelines.megaplan.chain.spec import ChainState, _state_path_for
from arnold_pipelines.megaplan.custody.phase_wbc import PHASE_WBC_LEDGER_FILENAME

from .m11_live_canary import (
    SCHEMA,
    CanarySafetyError,
    _atomic_json,
    _digest,
    _load_hashed_json,
    _sha256_file,
    _utc_now,
)
from .m11_workflow_canary_runner import ADAPTER_ID, PRODUCER_ID, SCENARIOS


VERDICT_KIND = "deployed_workflow_canary_verified_verdict"
VERIFIER_ID = "megaplan.m11_workflow_canary.independent_verifier.v1"


def _fail(message: str) -> None:
    raise CanarySafetyError(message)


def _timestamp(value: Any, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        _fail(f"{field} is not a valid ISO-8601 timestamp")
    if parsed.tzinfo is None:
        _fail(f"{field} must include a timezone")
    return parsed


def _exact_inventory(evidence_root: Path, manifest: dict[str, Any]) -> None:
    expected = manifest.get("files")
    if not isinstance(expected, list):
        _fail("frozen manifest files must be a list")
    expected_by_path: dict[str, dict[str, Any]] = {}
    for record in expected:
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("path"), str)
            or record["path"] in expected_by_path
        ):
            _fail("frozen manifest contains malformed or duplicate paths")
        expected_by_path[record["path"]] = record
    actual = {
        path.relative_to(evidence_root).as_posix(): path
        for path in evidence_root.rglob("*")
        if path.is_file()
    }
    if set(actual) != set(expected_by_path):
        missing = sorted(set(expected_by_path) - set(actual))
        extra = sorted(set(actual) - set(expected_by_path))
        _fail(f"frozen evidence inventory mismatch: missing={missing}, extra={extra}")
    for relative, path in actual.items():
        record = expected_by_path[relative]
        if path.stat().st_size != record.get("size") or _sha256_file(path) != record.get("sha256"):
            _fail(f"frozen evidence changed: {relative}")


def _attempt_ids(db_path: Path) -> list[str]:
    uri = db_path.resolve().as_uri() + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute(
            "SELECT DISTINCT attempt_id FROM attempt_events ORDER BY attempt_id"
        ).fetchall()
    finally:
        connection.close()
    return [str(row[0]) for row in rows]


def _events_by_step(
    plan_dir: Path,
    *,
    window: tuple[datetime, datetime],
) -> dict[str, list[tuple[str, tuple[Any, ...]]]]:
    db_path = plan_dir / PHASE_WBC_LEDGER_FILENAME
    if not db_path.is_file():
        _fail(f"missing canonical Phase-WBC store: {db_path}")
    result: dict[str, list[tuple[str, tuple[Any, ...]]]] = {}
    uri = db_path.resolve().as_uri() + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    try:
        for attempt_id in _attempt_ids(db_path):
            rows = connection.execute(
                "SELECT event_json FROM attempt_events "
                "WHERE attempt_id = ? ORDER BY sequence",
                (attempt_id,),
            ).fetchall()
            events = tuple(
                _deserialize_ledger_event(json.loads(str(row[0])))
                for row in rows
            )
            if not events:
                _fail(f"empty reserved attempt {attempt_id}")
            first = events[0]
            step = str(first.identity.step_id)
            for event in events:
                if event.identity.attempt_id != attempt_id:
                    _fail("attempt identity does not match store key")
                if event.identity.step_id != step:
                    _fail("one attempt spans multiple workflow steps")
                if event.provenance.tool_id != "megaplan.phase_wbc":
                    _fail(f"attempt {attempt_id} lacks canonical producer provenance")
                if event.payload.get("__wbc_runtime__", {}).get("promotion_mode") != "action_off":
                    _fail(f"attempt {attempt_id} lacks canonical WBC runtime evidence")
                occurred = _timestamp(
                    event.occurred_at,
                    field=f"attempt {attempt_id} occurred_at",
                )
                observed = _timestamp(
                    event.observed_at,
                    field=f"attempt {attempt_id} observed_at",
                )
                if not (window[0] <= occurred <= observed <= window[1]):
                    _fail(f"attempt {attempt_id} falls outside its admitted evidence window")
                if event.identity.run_id != plan_dir.name:
                    _fail(f"attempt {attempt_id} is joined to the wrong workflow run")
            result.setdefault(step, []).append((attempt_id, events))
    finally:
        connection.close()
    return result


def _require_lifecycle(
    events: dict[str, list[tuple[str, tuple[Any, ...]]]],
    step: str,
    expected: tuple[AttemptEventType, ...],
    *,
    count: int = 1,
) -> list[str]:
    attempts = events.get(step, [])
    if len(attempts) != count:
        _fail(f"{step} requires {count} attempts, found {len(attempts)}")
    ids: list[str] = []
    for attempt_id, stream in attempts:
        kinds = tuple(event.event_type for event in stream)
        if kinds != expected:
            _fail(f"{step} lifecycle mismatch: {kinds}")
        if [event.sequence for event in stream] != list(range(1, len(stream) + 1)):
            _fail(f"{step} event ordering is not contiguous")
        ids.append(attempt_id)
    return ids


def _boundary_history(plan_dir: Path, boundary_id: str, minimum: int) -> list[Path]:
    history = plan_dir / "boundary_receipts" / "history" / boundary_id
    paths = sorted(history.glob("v*.json")) if history.is_dir() else []
    if len(paths) < minimum:
        _fail(f"{boundary_id} requires at least {minimum} immutable receipts")
    return paths


def _verify_acceptance(
    plan_dir: Path,
    scenario: str,
    admission: dict[str, Any],
) -> dict[str, Any]:
    spec_path = plan_dir / "canary-chain.yaml"
    state_path = _state_path_for(spec_path)
    try:
        state_payload = json.loads(state_path.read_text(encoding="utf-8"))
        state = ChainState.from_dict(state_payload)
    except Exception as exc:
        _fail(f"{scenario} chain state is unreadable: {exc}")
    state.completion_contract_mode = "atomic"
    if not state.validate_acceptance_receipt(
        scenario, plan_dir=plan_dir, require_committed=True
    ):
        _fail(f"{scenario} committed acceptance transaction did not revalidate")
    record = next(
        (item for item in state.completed if item.get("label") == scenario),
        None,
    )
    if not isinstance(record, dict):
        _fail(f"{scenario} completion record missing")
    if record.get("source_commit_ref") != admission["deployment"]["expected_revision"]:
        _fail(f"{scenario} accepted the wrong source revision")
    if record.get("runtime_identity") != admission["runtime_receipt"]["runtime_identity"]:
        _fail(f"{scenario} accepted the wrong runtime identity")
    return {
        "transaction_id": record["transaction_id"],
        "snapshot_hash": record["snapshot_hash"],
        "state_sha256": _sha256_file(state_path),
    }


def _verify_scenario(
    evidence_root: Path,
    scenario: str,
    plan_relative: str,
    admission: dict[str, Any],
    window: tuple[datetime, datetime],
) -> dict[str, Any]:
    plan_dir = (evidence_root / plan_relative).resolve()
    try:
        plan_dir.relative_to(evidence_root.resolve())
    except ValueError:
        _fail(f"{scenario} plan path escapes frozen evidence root")
    try:
        marker = json.loads(
            (plan_dir / "scenario-produced.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        _fail(f"{scenario} lacks canonical handler producer provenance")
    if (
        marker.get("scenario_id") != scenario
        or marker.get("producer_id") != PRODUCER_ID
        or marker.get("adapter_id") != ADAPTER_ID
        or not isinstance(marker.get("handler_outputs"), list)
        or not marker["handler_outputs"]
    ):
        _fail(f"{scenario} lacks canonical handler producer provenance")
    state_payload = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    parity_errors = (
        state_payload.get("meta", {}).get("schema_parity_errors")
        if isinstance(state_payload, dict)
        and isinstance(state_payload.get("meta"), dict)
        else None
    )
    if parity_errors:
        _fail(f"{scenario} has blocking structured-output schema parity errors")
    events = _events_by_step(plan_dir, window=window)
    if scenario == "fresh_plan":
        attempt_ids = _require_lifecycle(
            events,
            "plan",
            (AttemptEventType.STARTED, AttemptEventType.COMPLETED),
        )
        _boundary_history(plan_dir, "plan_to_critique", 1)
    elif scenario == "resume_from_suspension":
        attempt_ids = _require_lifecycle(
            events,
            "prep",
            (
                AttemptEventType.STARTED,
                AttemptEventType.SUSPENDED,
                AttemptEventType.RESUMED,
                AttemptEventType.COMPLETED,
            ),
        )
        stream = events["prep"][0][1]
        original = stream[0].identity.invocation_id
        reentry = stream[2].payload.get("reentry_invocation_id")
        if not reentry or reentry == original or stream[3].payload.get("reentry_invocation_id") != reentry:
            _fail("resume scenario lacks a distinct, joined reentry invocation")
    elif scenario == "three_gate_iterations":
        attempt_ids = _require_lifecycle(
            events,
            "gate",
            (AttemptEventType.STARTED, AttemptEventType.COMPLETED),
            count=3,
        )
        _boundary_history(plan_dir, "gate_to_revise", 3)
    else:
        attempt_ids = []
        for step in (
            "tiebreaker_researcher",
            "tiebreaker_challenger",
            "tiebreaker_synthesis",
            "tiebreaker_decision",
        ):
            attempt_ids.extend(
                _require_lifecycle(
                    events,
                    step,
                    (AttemptEventType.STARTED, AttemptEventType.COMPLETED),
                )
            )
        decisions = json.loads(
            (plan_dir / "tiebreaker_decisions.json").read_text(encoding="utf-8")
        )
        if (
            not isinstance(decisions, list)
            or len(decisions) != 1
            or decisions[0].get("action") != "pick"
        ):
            _fail("tiebreaker decision routing is missing or ambiguous")
    acceptance = _verify_acceptance(plan_dir, scenario, admission)
    return {
        "scenario_id": scenario,
        "attempt_ids": attempt_ids,
        "producer_marker_sha256": _sha256_file(plan_dir / "scenario-produced.json"),
        "acceptance": acceptance,
    }


def derive_deployed_workflow_canary(
    *,
    root: Path,
    expected_verdict_path: Path | None = None,
) -> dict[str, Any]:
    workflow_dir = root / "workflow-canary"
    admission = _load_hashed_json(workflow_dir / "admission.json")
    manifest = _load_hashed_json(workflow_dir / "frozen-manifest.json")
    if (
        manifest.get("producer_id") != PRODUCER_ID
        or manifest.get("admission_sha256") != admission.get("content_sha256")
    ):
        _fail("frozen manifest is not bound to the admitted producer/run")
    runtime = Path(str(admission["runtime_receipt"]["path"]))
    if _sha256_file(runtime) != admission["runtime_receipt"]["sha256"]:
        _fail("runtime receipt changed after admission")
    evidence_root = Path(str(manifest["evidence_root"])).resolve()
    if evidence_root != (root / "workflow-canary-evidence").resolve():
        _fail("manifest evidence root is not the admitted canary evidence root")
    _exact_inventory(evidence_root, manifest)
    run = _load_hashed_json(evidence_root / "run.json")
    if (
        run.get("producer_id") != PRODUCER_ID
        or run.get("adapter_id") != ADAPTER_ID
        or run.get("admission_sha256") != admission["content_sha256"]
        or set(run.get("scenarios", {})) != set(SCENARIOS)
    ):
        _fail("run record is incomplete or not bound to admission")
    admitted_at = _timestamp(admission.get("admitted_at"), field="admitted_at")
    started_at = _timestamp(run.get("started_at"), field="run.started_at")
    completed_at = _timestamp(run.get("completed_at"), field="run.completed_at")
    frozen_at = _timestamp(manifest.get("frozen_at"), field="manifest.frozen_at")
    if not (admitted_at <= started_at <= completed_at <= frozen_at):
        _fail("workflow canary timestamps are outside the admitted evidence window")
    plan_paths = [
        descriptor.get("plan_dir")
        for descriptor in run["scenarios"].values()
        if isinstance(descriptor, dict)
    ]
    if len(plan_paths) != len(set(plan_paths)):
        _fail("scenario roots are not unique")
    scenario_results: list[dict[str, Any]] = []
    all_attempt_ids: list[str] = []
    for scenario in SCENARIOS:
        descriptor = run["scenarios"][scenario]
        if not isinstance(descriptor, dict) or not isinstance(descriptor.get("plan_dir"), str):
            _fail(f"{scenario} descriptor is malformed")
        result = _verify_scenario(
            evidence_root,
            scenario,
            descriptor["plan_dir"],
            admission,
            (started_at, completed_at),
        )
        scenario_results.append(result)
        all_attempt_ids.extend(result["attempt_ids"])
    if len(all_attempt_ids) != len(set(all_attempt_ids)):
        _fail("attempt identity was reused across scenarios")
    existing_verdict = (
        _load_hashed_json(expected_verdict_path)
        if expected_verdict_path is not None
        else None
    )
    verified_at = (
        str(existing_verdict.get("verified_at"))
        if isinstance(existing_verdict, dict)
        and isinstance(existing_verdict.get("verified_at"), str)
        else _utc_now()
    )
    verdict = {
        "schema": SCHEMA,
        "kind": VERDICT_KIND,
        "verifier_id": VERIFIER_ID,
        "job_id": admission["job_id"],
        "admission_sha256": admission["content_sha256"],
        "manifest_sha256": manifest["content_sha256"],
        "deployment": admission["deployment"],
        "runtime_receipt": admission["runtime_receipt"],
        "scenarios": scenario_results,
        "deployed_proof_status": "verified",
        "passed": True,
        "verified_at": verified_at,
    }
    verdict["content_sha256"] = _digest(verdict)
    if existing_verdict is not None:
        if existing_verdict != verdict:
            _fail("stored verdict does not match independent rederivation")
    return verdict


def verify_and_write_deployed_workflow_canary(*, root: Path) -> dict[str, Any]:
    """Rederive first, then exclusively write the verifier-owned verdict."""

    verdict_path = root / "workflow-canary" / "verdict.json"
    if verdict_path.exists():
        return derive_deployed_workflow_canary(
            root=root,
            expected_verdict_path=verdict_path,
        )
    verdict = derive_deployed_workflow_canary(root=root)
    _atomic_json(verdict_path, verdict, exclusive=True)
    return verdict


def validate_stored_deployed_workflow_canary_verdict(path: Path) -> bool:
    try:
        if path.name != "verdict.json" or path.parent.name != "workflow-canary":
            return False
        root = path.parent.parent
        derive_deployed_workflow_canary(root=root, expected_verdict_path=path)
        return True
    except Exception:
        return False


__all__ = [
    "VERDICT_KIND",
    "VERIFIER_ID",
    "derive_deployed_workflow_canary",
    "validate_stored_deployed_workflow_canary_verdict",
    "verify_and_write_deployed_workflow_canary",
]
