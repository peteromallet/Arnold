"""Bounded authoritative context and receipts for two-stage automatic repair."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan.cloud.repair_goal import capture_checkpoint, utc_now
from arnold_pipelines.megaplan.cloud.meta_repair_policy import (
    resolve_authoritative_blocker_id,
)
from arnold_pipelines.megaplan.cloud.redact import redact_payload


REPAIR_INVESTIGATION_CONTEXT_SCHEMA = "arnold-repair-investigation-context-v1"
META_REPAIR_INVESTIGATION_ENVELOPE_SCHEMA = "arnold-meta-repair-investigation-envelope-v2"
REPAIR_INVESTIGATOR_RECEIPT_SCHEMA = "arnold-repair-investigator-receipt-v2"
MAX_CONTEXT_BYTES = 64 * 1024
MAX_OBSERVATION_BUNDLE_BYTES = 48 * 1024
META_REPAIR_OBSERVATION_BUNDLE_SCHEMA = "arnold-meta-repair-observation-bundle-v1"
INVESTIGATION_TARGET_KINDS = frozenset({"l1_repair_target", "l2_repair_system"})
EVIDENCE_SOURCE_KINDS = frozenset(
    {
        "live_process",
        "session_marker",
        "chain_state",
        "plan_state",
        "phase_result",
        "event_log",
        "chain_log",
        "repair_data",
        "repair_queue",
        "repair_goal",
        "meta_repair",
        "source_tree",
        "source_contract",
        "resident_delegation",
        "automatic_system",
        "external_state",
    }
)
RECOMMENDED_ACTIONS = frozenset(
    {"preserve_live", "repair_source", "repair_target", "recover_state", "replan"}
)
SAFE_REPAIR_TARGET_KINDS = frozenset(
    {"none", "arnold_source", "target_workspace", "plan_state_via_cli", "repair_custody"}
)


def _load(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(dict(value), sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _file_reference(kind: str, path: str | Path, *, json_pointer: str = "") -> dict[str, Any]:
    """Return an immutable, typed pointer without embedding artifact contents."""

    artifact = Path(path)
    try:
        digest = hashlib.sha256()
        with artifact.open("rb") as handle:
            before = os.fstat(handle.fileno())
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            after = os.fstat(handle.fileno())
    except OSError as exc:
        raise ValueError(f"required {kind} artifact is unreadable: {artifact}") from exc
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise ValueError(f"required {kind} artifact changed while it was referenced: {artifact}")
    return {
        "kind": kind,
        "path": str(artifact),
        "json_pointer": json_pointer,
        "sha256": digest.hexdigest(),
        "size_bytes": after.st_size,
    }


def _text(value: object, limit: int = 4000) -> str:
    return str(value or "")[:limit]


def _summary_items(value: object) -> list[object]:
    """Normalize legacy report fields without guessing away their evidence.

    Repair reports have historically emitted ``what_tried`` and ``validation``
    as lists, mappings, or scalar strings.  Context construction is a custody
    boundary: a new producer shape must stay visible to the investigator, but
    it must never crash the constructor and strand the repair goal.
    """

    if value in (None, "", [], {}):
        return []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return [value]


def _attempt_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    report = value.get("dev_report") if isinstance(value.get("dev_report"), Mapping) else {}
    return {
        "attempt_id": value.get("attempt_id"),
        "dispatched_at": _text(value.get("dispatched_at"), 100),
        "finished_at": _text(value.get("finished_at"), 100),
        "blocker_id": _text(value.get("blocker_id"), 300),
        "problem_signature": value.get("problem_signature")
        if isinstance(value.get("problem_signature"), Mapping)
        else {},
        "failure_classification": _text(value.get("failure_classification"), 300),
        "hypothesis": _text(value.get("dev_hypothesis") or report.get("hypothesis"), 3000),
        "classification": _text(report.get("classification"), 300),
        "what_tried": [
            _text(item, 1000)
            for item in _summary_items(value.get("dev_summary") or report.get("what_tried"))[-8:]
        ],
        "validation": [
            _text(item, 1000) for item in _summary_items(report.get("validation"))[-8:]
        ],
        "pushed_commit": _text(value.get("dev_fix_sha") or report.get("pushed_commit"), 100),
        "outcome": _text(value.get("outcome") or value.get("status"), 300),
    }


def _phase_result_summary(plan_state_path: object) -> dict[str, Any]:
    if not plan_state_path:
        return {}
    path = Path(str(plan_state_path)).parent / "phase_result.json"
    value = _load(path)
    if not value:
        return {}
    deviations = value.get("deviations") if isinstance(value.get("deviations"), list) else []
    blocked_tasks = value.get("blocked_tasks") if isinstance(value.get("blocked_tasks"), list) else []
    return {
        "path": str(path),
        "phase": _text(value.get("phase"), 200),
        "exit_kind": _text(value.get("exit_kind"), 300),
        "invocation_id": _text(value.get("invocation_id"), 300),
        "blocked_tasks": [item if isinstance(item, Mapping) else _text(item, 1000) for item in blocked_tasks[-20:]],
        "deviations": [item if isinstance(item, Mapping) else {"message": _text(item, 4000)} for item in deviations[-20:]],
        "external_error": value.get("external_error"),
    }


def _evidence_source(kind: str, path: object, observed: object, *, authority: int) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": _text(path, 2000),
        "authority": authority,
        "observed": observed if isinstance(observed, (Mapping, list)) else _text(observed, 4000),
    }


def _common_required_output(target_kind: str) -> dict[str, Any]:
    return {
        "schema_version": REPAIR_INVESTIGATOR_RECEIPT_SCHEMA,
        "context_digest": "<exact context digest>",
        "target_kind": target_kind,
        "actual_failure": {
            "classification": "live_failure|stale_state|custody_failure|infrastructure_failure|unknown",
            "mechanism": "<actual failure mechanism, not a derived status label>",
            "error": "<exact error/contradiction or unknown>",
        },
        "evidence_sources": [
            {
                "kind": "plan_state",
                "path": "<authoritative path>",
                "authority": 4,
                "observed": "<bounded observation>",
            }
        ],
        "custody_status": "consistent|contradictory|unknown",
        "custody_contradictions": [
            {
                "left_source": "<source/path>",
                "right_source": "<source/path>",
                "contradiction": "<what disagrees>",
            }
        ],
        "intended_recovery": {
            "predicate": "<blocker-clearance and progress condition>",
            "blocker_cleared_required": True,
            "fresh_progress_required": True,
            "beyond_stage_required": True,
        },
        "safe_repair_target": {
            "kind": "none|arnold_source|target_workspace|plan_state_via_cli|repair_custody",
            "scope": "<bounded path/component or none>",
            "rationale": "<why this is the safe ownership boundary>",
        },
        "safe_repair_target_by_action": {
            "preserve_live": ["none"],
            "replan": ["none", "repair_custody"],
            "repair_source": ["arnold_source", "target_workspace"],
            "repair_target": ["target_workspace"],
            "recover_state": ["plan_state_via_cli", "repair_custody"],
        },
        "handoff_allowed_mutations_by_action": {
            "preserve_live": ["none"],
            "replan": ["none"],
            "repair_source": ["arnold_source:<bounded component>"],
            "repair_target": ["target_workspace:<bounded component>"],
            "recover_state": ["supported_cli:<exact command>"],
        },
        "replan_contract": (
            "replan handoff.allowed_mutations MUST equal [\"none\"] and never authorizes "
            "an L1 mutation; repair_custody may be named only in safe_repair_target.kind "
            "as the bounded L2/root-cause target when custody is contradictory"
        ),
        "handoff": {
            "action": "preserve_live|repair_source|repair_target|recover_state|replan",
            "allowed_mutations": ["<use one exact action-specific example below>"],
            "forbidden_mutations": ["<unsafe mutation>"],
        },
        "action_specific_handoff_examples": {
            "preserve_live": {"action": "preserve_live", "allowed_mutations": ["none"]},
            "replan": {"action": "replan", "allowed_mutations": ["none"]},
            "repair_source": {
                "action": "repair_source",
                "allowed_mutations": ["arnold_source:<bounded component>"],
            },
            "repair_target": {
                "action": "repair_target",
                "allowed_mutations": ["target_workspace:<bounded component>"],
            },
            "recover_state": {
                "action": "recover_state",
                "allowed_mutations": ["supported_cli:<exact command>"],
            },
        },
        "mutation_contract": (
            "recover_state may authorize only a named supported CLI or repair_custody "
            "operation; it never authorizes direct JSON edits or hand-advancing a chain"
        ),
        "four_axis": {
            "TRACKED": "pass|fail|unknown",
            "FIXED": "pass|fail|unknown",
            "INTENT": "pass|fail|unknown",
            "CONTEXT": "pass|fail|unknown",
        },
        "prior_repairs_considered": ["<attempt id, receipt, or explicit none>"],
        "preserve_live": False,
        "recommended_action": "preserve_live|repair_source|repair_target|recover_state|replan",
        "guard_weakening_risk": "none|identified|unknown",
    }


def _context_contradictions(
    *,
    request_mismatch: bool,
    request_path: object,
    goal_path: object,
    goal_target: Mapping[str, Any],
    session: str,
    current: Mapping[str, Any],
) -> list[dict[str, str]]:
    contradictions: list[dict[str, str]] = []
    if request_mismatch:
        contradictions.append(
            {
                "left_source": _text(request_path, 2000) or "repair_queue",
                "right_source": _text(current.get("plan_state_path"), 2000) or "current_target",
                "contradiction": "queued request plan/stage does not match the current target",
            }
        )
    goal_session = _text(goal_target.get("session"), 300)
    if goal_session and goal_session != session:
        contradictions.append(
            {
                "left_source": _text(goal_path, 2000) or "repair_goal",
                "right_source": "current_session",
                "contradiction": "repair-goal session identity differs from the current session",
            }
        )
    goal_plan = _text(goal_target.get("plan_name"), 500)
    current_plan = _text(current.get("plan_name"), 500)
    if goal_plan and current_plan and goal_plan != current_plan:
        contradictions.append(
            {
                "left_source": _text(goal_path, 2000) or "repair_goal",
                "right_source": _text(current.get("plan_state_path"), 2000) or "plan_state",
                "contradiction": "repair-goal plan identity differs from the current plan",
            }
        )
    session_identity = (
        current.get("session_identity")
        if isinstance(current.get("session_identity"), Mapping)
        else {}
    )
    if session_identity.get("identity_matches") is False:
        contradictions.append(
            {
                "left_source": _text(goal_path, 2000) or "repair_goal",
                "right_source": _text(session_identity.get("marker_path"), 2000) or "session_marker",
                "contradiction": "repair-goal target identity differs from the authoritative session marker",
            }
        )
    return contradictions


def build_investigation_context(
    *,
    workspace: str | Path,
    session: str,
    remote_spec: str,
    repair_data_path: str | Path,
    request_path: str | Path | None,
    goal_path: str | Path,
    l2_handoff_path: str | Path | None = None,
    l2_context_digest: str = "",
    max_prior_attempts: int = 6,
) -> dict[str, Any]:
    repair_data = _load(repair_data_path)
    request = _load(request_path)
    goal = _load(goal_path)
    goal_target = goal.get("target") if isinstance(goal.get("target"), Mapping) else {}
    frozen_checkpoint = (
        goal.get("frozen_checkpoint")
        if isinstance(goal.get("frozen_checkpoint"), Mapping)
        else {}
    )
    plan_name = _text(goal_target.get("plan_name") or repair_data.get("plan_name"), 500)
    current = capture_checkpoint(
        workspace=workspace,
        plan_name=plan_name,
        remote_spec=remote_spec,
        marker_dir=str(goal_target.get("marker_dir") or ""),
        session=session,
    )
    phase_result = _phase_result_summary(current.get("plan_state_path"))
    phase_exit_kind = _text(phase_result.get("exit_kind"), 300).lower()
    phase_result_blocked = bool(
        phase_result and phase_exit_kind not in {"", "success", "succeeded", "completed", "done"}
    )
    request_signature = (
        request.get("problem_signature")
        if isinstance(request.get("problem_signature"), Mapping)
        else {}
    )
    request_target = request.get("target") if isinstance(request.get("target"), Mapping) else {}
    request_plan = _text(
        request_signature.get("milestone_or_plan") or request_target.get("plan_name"), 500
    )
    request_stage = _text(request_signature.get("phase_or_step"), 200).lower()
    current_plan = _text(current.get("plan_name"), 500)
    current_stage = _text(current.get("target_stage"), 200).lower()
    request_mismatch = bool(
        request_plan and current_plan and request_plan != current_plan
    )
    request_stage_transition = bool(
        request_stage and current_stage and request_stage != current_stage
    )
    attempts = [item for item in repair_data.get("attempts") or [] if isinstance(item, Mapping)]
    contradictions = _context_contradictions(
        request_mismatch=request_mismatch,
        request_path=request_path,
        goal_path=goal_path,
        goal_target=goal_target,
        session=session,
        current=current,
    )
    recovery_contract = (
        dict(goal.get("recovery_contract"))
        if isinstance(goal.get("recovery_contract"), Mapping)
        else {}
    )
    meta_handoff = (
        repair_data.get("meta_investigation")
        if isinstance(repair_data.get("meta_investigation"), Mapping)
        else {}
    )
    explicit_handoff_path = str(l2_handoff_path or "").strip()
    access_receipt_path = Path(
        explicit_handoff_path or str(meta_handoff.get("access_receipt_path") or "")
    )
    access_receipt = _load(access_receipt_path)
    external_observation: dict[str, Any] = {}
    external_observation_path = ""
    if explicit_handoff_path or str(meta_handoff.get("access_receipt_path") or "").strip():
        expected_handoff_digest = (
            str(l2_context_digest or "").strip()
            or str(meta_handoff.get("context_digest") or "").strip()
        )
        if (
            access_receipt.get("schema_version") != META_REPAIR_OBSERVATION_BUNDLE_SCHEMA
            or access_receipt.get("access_verified") is not True
            or not expected_handoff_digest
            or access_receipt.get("context_digest") != expected_handoff_digest
        ):
            raise ValueError("L2-to-L1 evidence handoff receipt is invalid")
        for item in access_receipt.get("observations") or []:
            if isinstance(item, Mapping) and item.get("kind") == "external_state":
                observed = _bounded_observation(
                    "external_state", _verified_reference_bytes(item)
                )
                if isinstance(observed, Mapping):
                    external_observation = dict(observed)
                    external_observation_path = str(item.get("path") or "")
                break
        if not external_observation:
            raise ValueError("L2-to-L1 evidence handoff lacks external state")
    evidence_sources = [
        _evidence_source("repair_data", repair_data_path, {
            "outcome": repair_data.get("outcome"),
            "current_attempt_id": repair_data.get("current_attempt_id"),
            "attempt_count": len(attempts),
        }, authority=7),
        _evidence_source("repair_goal", goal_path, {
            "goal_id": goal.get("goal_id"),
            "checkpoint_digest": goal.get("checkpoint_digest"),
            "status": goal.get("status"),
        }, authority=6),
    ]
    if request_path:
        evidence_sources.append(
            _evidence_source("repair_queue", request_path, {
                "request_id": request.get("request_id"),
                "problem_signature": request_signature,
            }, authority=8)
        )
    if current.get("plan_state_path"):
        evidence_sources.append(
            _evidence_source("plan_state", current.get("plan_state_path"), current, authority=4)
        )
    if phase_result:
        evidence_sources.append(
            _evidence_source("phase_result", phase_result.get("path"), phase_result, authority=5)
        )
    if external_observation:
        evidence_sources.append(
            _evidence_source(
                "external_state",
                external_observation_path,
                external_observation,
                authority=4,
            )
        )
    external_guard = (
        external_observation.get("external_guard")
        if isinstance(external_observation.get("external_guard"), Mapping)
        else {}
    )
    external_failure = (
        {
            "failure_kind": "external_pr_ci_guard_failed",
            "message": "fresh external PR/CI evidence reports a failing required check",
            "external_guard": external_guard,
        }
        if external_guard.get("status") == "failed"
        else {}
    )
    frozen_failure = (
        frozen_checkpoint.get("latest_failure")
        if isinstance(frozen_checkpoint.get("latest_failure"), Mapping)
        else {}
    )
    current_authoritative_failure = external_failure or (
        current.get("latest_failure")
        if isinstance(current.get("latest_failure"), Mapping)
        else {}
    )
    blocker_transitioned = bool(
        frozen_failure
        and current_authoritative_failure
        and _digest(dict(frozen_failure)) != _digest(dict(current_authoritative_failure))
    )
    context: dict[str, Any] = {
        "schema_version": REPAIR_INVESTIGATION_CONTEXT_SCHEMA,
        "target_kind": "l1_repair_target",
        "generated_at": utc_now(),
        "session": session,
        "workspace": str(Path(workspace)),
        "remote_spec": remote_spec,
        "repair_data_path": str(Path(repair_data_path)),
        "request_path": str(Path(request_path)) if request_path else "",
        "goal_path": str(Path(goal_path)),
        "goal_id": _text(goal.get("goal_id"), 300),
        "checkpoint_digest": _text(goal.get("checkpoint_digest"), 100),
        "frozen_checkpoint": dict(frozen_checkpoint),
        "recovery_contract": recovery_contract,
        "current": current,
        "current_phase_result": phase_result,
        "exact_error": external_failure
        or current.get("latest_failure")
        or (phase_result if phase_result_blocked else {})
        or frozen_checkpoint.get("latest_failure")
        or {},
        "request": {
            "request_id": _text(request.get("request_id"), 300),
            "created_at": _text(request.get("created_at"), 100),
            "problem_signature": dict(request_signature),
            "target": dict(request_target),
            "matches_current_target": not request_mismatch,
            "stage_transition": request_stage_transition,
            "stage_transition_remains_same_goal": bool(
                request_stage_transition and not request_mismatch
            ),
            "mismatch_reason": (
                f"queued request plan {request_plan!r} disagrees with current {current_plan!r}"
                if request_mismatch
                else ""
            ),
        },
        "prior_repairs": [_attempt_summary(item) for item in attempts[-max_prior_attempts:]],
        "repair_outcome": _text(repair_data.get("outcome"), 300),
        "managed_run_id": _text(repair_data.get("managed_agent_run_id"), 300),
        "evidence_sources": evidence_sources,
        "custody_status": "contradictory" if contradictions else "consistent",
        "custody_contradictions": contradictions,
        "goal_continuity": {
            "status": "successor_blocker" if blocker_transitioned else "same_blocker_or_unknown",
            "checkpoint_role": "immutable_acceptance_baseline",
            "same_goal_continuity_valid": not contradictions,
            "current_blocker_may_differ": True,
            "reason": (
                "A durable repair goal owns the recovery outcome, not one immutable failure label. "
                "A newly exposed authoritative blocker remains inside the same goal until accepted "
                "progress advances beyond the frozen checkpoint. Blocker evolution alone is not a "
                "custody contradiction."
            ),
        },
        "intended_recovery": {
            "predicate": _text(
                recovery_contract.get("predicate")
                or "original blocker cleared; applicable worker fresh; accepted progress beyond frozen stage",
                2000,
            ),
            "blocker_cleared_required": True,
            "fresh_progress_required": True,
            "beyond_stage_required": True,
        },
        "safe_repair_boundaries": {
            "allowed": ["arnold_source", "target_workspace", "plan_state_via_cli", "repair_custody"],
            "forbidden": ["guard_weakening", "direct_state_edit", "duplicate_live_worker", "uncited_mutation"],
        },
        "required_investigator_output": _common_required_output("l1_repair_target"),
    }
    digest_payload = dict(context)
    context["context_digest"] = _digest(digest_payload)
    encoded = json.dumps(context, sort_keys=True, separators=(",", ":"), default=str).encode()
    if len(encoded) > MAX_CONTEXT_BYTES:
        # Preserve the newest and most relevant history while failing closed on
        # unbounded context growth.
        context["prior_repairs"] = context["prior_repairs"][-3:]
        context["context_digest"] = _digest({k: v for k, v in context.items() if k != "context_digest"})
        encoded = json.dumps(context, sort_keys=True, separators=(",", ":"), default=str).encode()
    if len(encoded) > MAX_CONTEXT_BYTES:
        raise ValueError("bounded repair investigation context exceeds 64 KiB")
    return context


def _git_observation(root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"path": str(root), "head": "", "branch": "", "dirty": None}
    for key, args in (
        ("head", ["rev-parse", "HEAD"]),
        ("branch", ["symbolic-ref", "--quiet", "--short", "HEAD"]),
        ("status", ["status", "--porcelain", "--untracked-files=no"]),
    ):
        try:
            proc = subprocess.run(
                ["git", "-C", str(root), *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode == 0:
            value = proc.stdout.strip()
            if key == "status":
                result["dirty"] = bool(value)
            else:
                result[key] = value
    return result


def _external_pr_snapshot(
    *, session: str, workspace: Path, repair_root: Path
) -> Path:
    """Persist a fresh, bounded read-only PR/CI observation for custody review."""

    evidence_dir = repair_root / "meta" / "evidence"
    safe_session = re.sub(r"[^A-Za-z0-9_.-]+", "-", session).strip("-") or "session"
    fields = (
        "number,url,state,isDraft,mergeStateStatus,headRefName,headRefOid,"
        "baseRefName,baseRefOid,updatedAt,statusCheckRollup"
    )
    snapshot: dict[str, Any] = {
        "schema_version": "arnold-external-pr-ci-observation-v1",
        "captured_at": utc_now(),
        "workspace": str(workspace),
        "query": "gh pr view --json <bounded fields>",
        "available": False,
    }
    try:
        proc = subprocess.run(
            ["gh", "pr", "view", "--json", fields],
            cwd=workspace,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        snapshot["returncode"] = proc.returncode
        if proc.returncode == 0:
            value = json.loads(proc.stdout)
            if isinstance(value, Mapping):
                snapshot["available"] = True
                snapshot["pull_request"] = dict(value)
        else:
            snapshot["error"] = _text(proc.stderr, 1000)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        snapshot["error"] = type(exc).__name__
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    output = evidence_dir / f"{safe_session}-external-state-{digest}.json"
    if output.exists():
        if _load(output) != snapshot:
            raise ValueError("content-addressed external-state evidence disagrees")
    else:
        _atomic_write(output, snapshot)
    return output


def build_meta_investigation_context(
    *,
    session: str,
    trigger: str,
    repair_data_dir: str | Path,
    marker_dir: str | Path,
    arnold_src: str | Path,
    request_id: str = "",
    blocker_id: str = "",
) -> dict[str, Any]:
    """Build a minimal, reference-only, read-only L2 launch envelope."""

    repair_root = Path(repair_data_dir)
    marker_root = Path(marker_dir)
    source_root = Path(arnold_src)
    repair_path = repair_root / f"{session}.repair-data.json"
    marker_path = marker_root / f"{session}.json"
    repair_data = _load(repair_path)
    if not repair_data:
        raise ValueError(f"required repair data is missing or invalid: {repair_path}")
    marker = _load(marker_path)
    if not marker:
        raise ValueError(f"required session marker is missing or invalid: {marker_path}")
    repair_goal_ref = (
        repair_data.get("repair_goal")
        if isinstance(repair_data.get("repair_goal"), Mapping)
        else {}
    )
    goal_path = Path(str(repair_goal_ref.get("goal_path") or ""))
    goal = _load(goal_path)
    if not goal:
        raise ValueError("repair data does not point to a readable authoritative repair goal")
    goal_id = _text(goal.get("goal_id"), 300)
    checkpoint_digest = _text(goal.get("checkpoint_digest"), 100)
    if not goal_id or not checkpoint_digest:
        raise ValueError("authoritative repair goal identity is incomplete")
    if repair_goal_ref.get("goal_id") not in (None, "", goal_id):
        raise ValueError("repair data and authoritative repair goal identity disagree")
    if repair_goal_ref.get("checkpoint_digest") not in (None, "", checkpoint_digest):
        raise ValueError("repair data and authoritative repair goal checkpoint disagree")
    goal_target = goal.get("target") if isinstance(goal.get("target"), Mapping) else {}
    authoritative_blocker, blocker_identity_drift = resolve_authoritative_blocker_id(
        session,
        repair_data_dir=repair_root,
        supplied_blocker_id=blocker_id,
    )
    meta_dir = repair_root / "meta"
    meta_paths = sorted(meta_dir.glob(f"*{session}*.json"), key=lambda item: item.stat().st_mtime)[-5:]
    current_target: dict[str, Any] = {}
    try:
        from arnold_pipelines.megaplan.cloud.current_target import resolve_current_target

        current_target = resolve_current_target(
            session,
            marker_dir=marker_root,
            repair_data_dir=repair_root,
        )
    except Exception as exc:  # evidence failure must remain visible and fail closed
        current_target = {"observation_error": type(exc).__name__}
    source_custody = _git_observation(source_root)
    if not source_custody.get("head") or source_custody.get("dirty") is None:
        raise ValueError("Arnold source custody could not be established")

    evidence_refs = [
        _file_reference("repair_data", repair_path),
        _file_reference("session_marker", marker_path),
        _file_reference("repair_goal", goal_path),
    ]
    target_workspace = Path(str(marker.get("workspace") or ""))
    if not str(marker.get("workspace") or "").strip():
        raise ValueError("session marker does not identify a target workspace")
    external_path = _external_pr_snapshot(
        session=session, workspace=target_workspace, repair_root=repair_root
    )
    evidence_refs.append(_file_reference("external_state", external_path))
    current_paths = (
        ("chain_state", (current_target.get("chain_state") or {}).get("path")),
        ("plan_state", (current_target.get("plan_state") or {}).get("path")),
        ("event_log", (current_target.get("event_cursors") or {}).get("events_path")),
        ("chain_log", (current_target.get("chain_log") or {}).get("path")),
    )
    seen_paths = {item["path"] for item in evidence_refs}
    for kind, path in current_paths:
        if path and str(path) not in seen_paths and Path(str(path)).is_file():
            evidence_refs.append(_file_reference(kind, str(path)))
            seen_paths.add(str(path))
    for path in meta_paths:
        if str(path) not in seen_paths:
            evidence_refs.append(_file_reference("meta_repair", path))
            seen_paths.add(str(path))

    delegation = (
        repair_data.get("resident_delegation")
        if isinstance(repair_data.get("resident_delegation"), Mapping)
        else {}
    )
    if delegation:
        provenance_ref = _file_reference(
            "resident_delegation", repair_path, json_pointer="/resident_delegation"
        )
        provenance_ref.update(
            {
                "custody_id": _text(delegation.get("custody_id"), 300),
                "source_record_id": _text(delegation.get("source_record_id"), 300),
                "root_run_id": _text(delegation.get("root_run_id"), 300),
            }
        )
    else:
        provenance_ref = {
            "kind": "automatic_system",
            "path": str(repair_path),
            "json_pointer": "",
            "sha256": evidence_refs[0]["sha256"],
            "size_bytes": evidence_refs[0]["size_bytes"],
            "custody_id": "",
            "source_record_id": "",
            "root_run_id": _text(repair_data.get("managed_agent_run_id"), 300),
        }

    contract_path = source_root / "arnold_pipelines/megaplan/cloud/repair_investigation.py"
    context: dict[str, Any] = {
        "schema_version": META_REPAIR_INVESTIGATION_ENVELOPE_SCHEMA,
        "target_kind": "l2_repair_system",
        "generated_at": utc_now(),
        "objective": (
            "Determine why ordinary repair failed, identify the first broken repair layer and "
            "its missed backstop, and return one read-only safe-mutation handoff."
        ),
        "identity": {
            "session": _text(session, 300),
            "trigger": _text(trigger, 300),
            "repair_goal_id": goal_id,
            "repair_checkpoint_digest": checkpoint_digest,
            "repair_request_id": _text(request_id or repair_data.get("request_id"), 300),
            "blocker_id": _text(authoritative_blocker, 300),
            "dispatch_blocker_id": _text(blocker_id, 300),
            "blocker_identity_drift": blocker_identity_drift,
        },
        "provenance_ref": provenance_ref,
        "source_custody": source_custody,
        "evidence_refs": evidence_refs,
        "authorization": {
            "mode": "read_only",
            "mutation_authorized": False,
            "allowed_handoff_targets": ["arnold_source", "repair_custody"],
            "forbidden": ["audited_workspace", "direct_chain_state_edit", "guard_weakening"],
        },
        "receipt_contract_ref": {
            **_file_reference("source_contract", contract_path),
            "schema_version": REPAIR_INVESTIGATOR_RECEIPT_SCHEMA,
            "validator": "validate_investigator_receipt",
        },
    }
    validate_meta_investigation_context(context, require_digest=False)
    context["context_digest"] = _digest(context)
    encoded = json.dumps(context, sort_keys=True, separators=(",", ":"), default=str).encode()
    if len(encoded) > MAX_CONTEXT_BYTES:
        raise ValueError("minimal meta-repair investigation envelope exceeds 64 KiB")
    validate_meta_investigation_context(context, require_digest=True)
    return context


def validate_meta_investigation_context(
    value: Mapping[str, Any], *, require_digest: bool = True
) -> dict[str, Any]:
    """Fail closed unless an L2 envelope is reference-only and custody-bound."""

    if value.get("schema_version") != META_REPAIR_INVESTIGATION_ENVELOPE_SCHEMA:
        raise ValueError("meta-repair investigation envelope schema is invalid")
    if value.get("target_kind") != "l2_repair_system":
        raise ValueError("meta-repair investigation target kind is invalid")
    if any(
        field in value
        for field in (
            "repair_data",
            "session_marker",
            "current_target",
            "evidence_sources",
            "required_investigator_output",
        )
    ):
        raise ValueError("meta-repair investigation envelope contains inlined evidence")
    objective = str(value.get("objective") or "")
    if not objective or len(objective.encode("utf-8")) > 1000:
        raise ValueError("meta-repair investigation objective is invalid")
    identity = value.get("identity")
    if not isinstance(identity, Mapping) or not all(
        str(identity.get(field) or "").strip()
        for field in ("session", "trigger", "repair_goal_id", "repair_checkpoint_digest")
    ):
        raise ValueError("meta-repair investigation identity is incomplete")
    authorization = value.get("authorization")
    if not isinstance(authorization, Mapping) or authorization.get("mode") != "read_only":
        raise ValueError("meta-repair investigation authorization mode is invalid")
    if authorization.get("mutation_authorized") is not False:
        raise ValueError("meta-repair investigation must not authorize mutation")
    if set(authorization.get("allowed_handoff_targets") or []) != {
        "arnold_source",
        "repair_custody",
    }:
        raise ValueError("meta-repair investigation handoff scope is invalid")
    refs = value.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        raise ValueError("meta-repair investigation evidence references are missing")
    required_kinds = {"repair_data", "session_marker", "repair_goal", "external_state"}
    observed_kinds: set[str] = set()
    for ref in [*refs, value.get("provenance_ref"), value.get("receipt_contract_ref")]:
        if not isinstance(ref, Mapping):
            raise ValueError("meta-repair investigation reference is invalid")
        kind = str(ref.get("kind") or "")
        path = str(ref.get("path") or "")
        digest = str(ref.get("sha256") or "")
        if not kind or not Path(path).is_absolute() or len(digest) != 64:
            raise ValueError("meta-repair investigation reference is incomplete")
        if not isinstance(ref.get("size_bytes"), int) or int(ref["size_bytes"]) < 0:
            raise ValueError("meta-repair investigation reference size is invalid")
        observed_kinds.add(kind)
    if not required_kinds.issubset(observed_kinds):
        raise ValueError("meta-repair investigation lacks authoritative evidence routes")
    contract = value.get("receipt_contract_ref")
    if (
        not isinstance(contract, Mapping)
        or contract.get("schema_version") != REPAIR_INVESTIGATOR_RECEIPT_SCHEMA
        or contract.get("validator") != "validate_investigator_receipt"
    ):
        raise ValueError("meta-repair investigation receipt contract is invalid")
    source = value.get("source_custody")
    if not isinstance(source, Mapping) or not all(
        str(source.get(field) or "").strip() for field in ("path", "head")
    ) or not isinstance(source.get("dirty"), bool):
        raise ValueError("meta-repair investigation source custody is incomplete")
    if require_digest:
        observed = str(value.get("context_digest") or "")
        recomputed = _digest({key: item for key, item in value.items() if key != "context_digest"})
        if len(observed) != 64 or observed != recomputed:
            raise ValueError("meta-repair investigation envelope digest disagrees")
    return dict(value)


def _verified_reference_bytes(ref: Mapping[str, Any]) -> bytes:
    path = Path(str(ref.get("path") or ""))
    expected_size = ref.get("size_bytes")
    expected_digest = str(ref.get("sha256") or "")
    if not path.is_absolute() or not isinstance(expected_size, int) or expected_size < 0:
        raise ValueError("observation reference identity is incomplete")
    digest = hashlib.sha256()
    kind = str(ref.get("kind") or "")
    json_required = kind not in {"event_log", "chain_log"}
    if json_required and expected_size > 32 * 1024 * 1024:
        raise ValueError(f"authoritative JSON observation exceeds 32 MiB: {path}")
    chunks: list[bytes] = []
    observed_size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            observed_size += len(chunk)
            digest.update(chunk)
            # Only JSON custody artifacts need parsing; logs are tailed below.
            if json_required:
                chunks.append(chunk)
    if observed_size != expected_size or digest.hexdigest() != expected_digest:
        raise ValueError(f"observation reference content disagrees: {path}")
    if chunks:
        return b"".join(chunks)
    with path.open("rb") as handle:
        handle.seek(max(0, expected_size - 8192))
        return handle.read(8192)


def _bounded_observation(kind: str, encoded: bytes) -> Any:
    try:
        value = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"tail": encoded.decode("utf-8", errors="replace")[-3000:]}
    if not isinstance(value, Mapping):
        return {"value_type": type(value).__name__}
    keys_by_kind = {
        "repair_data": (
            "session", "outcome", "request_id", "blocker_id", "plan_name",
            "repair_goal", "meta_investigation", "target", "verification",
            "evidence_compaction", "current_failure_context",
        ),
        "session_marker": (
            "session", "workspace", "remote_spec", "spec", "should_run",
            "status", "started_at", "updated_at", "resident_delegation",
        ),
        "repair_goal": (
            "goal_id", "status", "checkpoint_digest", "target", "owner",
            "owners", "frozen_checkpoint", "recovery_contract",
            "recovery_acceptance", "recovery_gate_failures", "last_evaluation",
            "evaluation", "created_at", "updated_at",
        ),
        "chain_state": (
            "chain_id", "current", "current_plan", "current_milestone_index",
            "last_state", "milestones", "metadata", "updated_at",
        ),
        "plan_state": (
            "current_state", "current_phase", "latest_failure", "active_step",
            "review", "updated_at", "history",
        ),
        "meta_repair": (
            "meta_repair_id", "session", "trigger", "outcome", "diagnosis",
            "reason", "blocker_id", "investigation", "recorded_at",
        ),
        "external_state": (
            "schema_version", "captured_at", "workspace", "available",
            "returncode", "error", "pull_request",
        ),
    }
    selected = {key: value[key] for key in keys_by_kind.get(kind, ()) if key in value}
    if kind == "external_state":
        pull = value.get("pull_request") if isinstance(value.get("pull_request"), Mapping) else {}
        checks = pull.get("statusCheckRollup") if isinstance(pull, Mapping) else []
        check_summaries = []
        for item in checks if isinstance(checks, list) else []:
            if not isinstance(item, Mapping):
                continue
            check_summaries.append(
                {
                    "name": _text(item.get("name"), 300),
                    "status": _text(item.get("status"), 100),
                    "conclusion": _text(item.get("conclusion"), 100),
                    "detailsUrl": _text(item.get("detailsUrl"), 1000),
                }
            )
        failing = [
            item for item in check_summaries
            if item["conclusion"].upper() in {"FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}
        ]
        pending = [
            item for item in check_summaries
            if item["status"].upper() not in {"COMPLETED", "SUCCESS"}
            and not item["conclusion"]
        ]
        selected["external_guard"] = {
            "status": (
                "unknown"
                if value.get("available") is not True
                else "failed"
                if failing
                else "pending"
                if pending
                else "clear"
            ),
            "failing_checks": failing,
            "pending_checks": pending,
            "merge_state": _text(pull.get("mergeStateStatus"), 100),
            "head_oid": _text(pull.get("headRefOid"), 100),
        }
    if kind == "repair_data" and isinstance(selected.get("current_failure_context"), Mapping):
        current = selected["current_failure_context"]
        selected["current_failure_context"] = {
            key: current[key]
            for key in (
                "failure_classification", "stale_state", "state_mismatch",
                "plan_latest_failure", "chain_state_summary", "last_gate",
                "chain_log_path", "run_log_path",
            )
            if key in current
        }
    if kind in {"source_contract", "resident_delegation", "automatic_system"}:
        return {"verified": True}
    for list_key in ("attempts", "iterations"):
        items = value.get(list_key)
        if kind == "repair_data" and isinstance(items, list):
            selected[f"{list_key}_count"] = len(items)
            selected[f"recent_{list_key}"] = [
                _attempt_summary(item) for item in items[-3:] if isinstance(item, Mapping)
            ]
    if kind == "plan_state" and isinstance(selected.get("history"), list):
        selected["history"] = selected["history"][-5:]
    return _bound_observation_value(
        selected or {"keys": sorted(str(key) for key in value)[:100]}
    )


def _bound_observation_value(value: Any, *, depth: int = 0) -> Any:
    """Deterministically cap nested derived observations, never source evidence."""

    if depth >= 3:
        return _text(value, 300)
    if isinstance(value, str):
        return value[:600]
    if isinstance(value, Mapping):
        keys = list(value)[:15]
        return {
            str(key): _bound_observation_value(value[key], depth=depth + 1)
            for key in keys
        }
    if isinstance(value, list):
        return [
            _bound_observation_value(item, depth=depth + 1) for item in value[-3:]
        ]
    return value


def build_meta_observation_bundle(context_path: str | Path) -> dict[str, Any]:
    """Broker verified, bounded observations when host read-only sandboxing is absent."""

    context = _load(context_path)
    validate_meta_investigation_context(context, require_digest=True)
    refs = [
        *(context.get("evidence_refs") or []),
        context.get("provenance_ref"),
        context.get("receipt_contract_ref"),
    ]
    observations: list[dict[str, Any]] = []
    for ref in refs:
        if not isinstance(ref, Mapping):
            raise ValueError("observation reference is invalid")
        encoded = _verified_reference_bytes(ref)
        kind = str(ref.get("kind") or "")
        observations.append(
            {
                "kind": kind,
                "path": str(ref.get("path") or ""),
                "sha256": str(ref.get("sha256") or ""),
                "size_bytes": int(ref.get("size_bytes") or 0),
                "observed": _bounded_observation(kind, encoded),
            }
        )
    required_receipt = _common_required_output("l2_repair_system")
    external_guard_status = "unknown"
    for item in observations:
        if item.get("kind") != "external_state":
            continue
        observed = item.get("observed")
        if isinstance(observed, Mapping):
            guard = observed.get("external_guard")
            if isinstance(guard, Mapping):
                external_guard_status = str(guard.get("status") or "unknown")
        break
    if external_guard_status != "clear":
        required_receipt["recommended_action"] = "replan"
        required_receipt["safe_repair_target"]["kind"] = "repair_custody"
        required_receipt["handoff"] = {
            "action": "replan",
            "allowed_mutations": ["none"],
            "forbidden_mutations": [
                "direct_chain_state_edit",
                "recover_state",
                "hand_advance_chain",
            ],
        }
    bundle = redact_payload(
        {
            "schema_version": META_REPAIR_OBSERVATION_BUNDLE_SCHEMA,
            "context_digest": context["context_digest"],
            "access_verified": True,
            "required_receipt_shape": required_receipt,
            "external_guard_policy": (
                "A failed or pending PR/CI check forbids recover_state and chain-state "
                "synchronization. Return replan targeting repair_custody so ordinary L1 "
                "receives the fresh external failure; never hand-advance the chain."
            ),
            "observations": observations,
        }
    )
    encoded_bundle = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded_bundle) > MAX_OBSERVATION_BUNDLE_BYTES:
        raise ValueError("brokered meta-repair observations exceed 48 KiB")
    return bundle


def validate_investigator_receipt(
    value: Mapping[str, Any], *, expected_context_digest: str,
    observation_bundle: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if value.get("schema_version") != REPAIR_INVESTIGATOR_RECEIPT_SCHEMA:
        raise ValueError("investigator receipt schema is invalid")
    if value.get("context_digest") != expected_context_digest:
        raise ValueError("investigator receipt context digest disagrees")
    if value.get("target_kind") not in INVESTIGATION_TARGET_KINDS:
        raise ValueError("investigator receipt target_kind is invalid")
    for field in ("recommended_action", "guard_weakening_risk", "custody_status"):
        if not str(value.get(field) or "").strip():
            raise ValueError(f"investigator receipt missing {field}")
    if value.get("recommended_action") not in RECOMMENDED_ACTIONS:
        raise ValueError("investigator receipt recommended_action is invalid")
    if value.get("custody_status") not in {"consistent", "contradictory", "unknown"}:
        raise ValueError("investigator receipt custody_status is invalid")
    if not isinstance(value.get("preserve_live"), bool):
        raise ValueError("investigator receipt preserve_live must be boolean")
    actual_failure = value.get("actual_failure")
    if not isinstance(actual_failure, Mapping):
        raise ValueError("investigator receipt actual_failure is invalid")
    if actual_failure.get("classification") not in {
        "live_failure", "stale_state", "custody_failure", "infrastructure_failure", "unknown"
    }:
        raise ValueError("investigator receipt actual_failure classification is invalid")
    for field in ("mechanism", "error"):
        if not str(actual_failure.get(field) or "").strip():
            raise ValueError(f"investigator receipt actual_failure missing {field}")
    sources = value.get("evidence_sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("investigator receipt evidence_sources is invalid")
    for source in sources:
        if not isinstance(source, Mapping) or source.get("kind") not in EVIDENCE_SOURCE_KINDS:
            raise ValueError("investigator receipt evidence source kind is invalid")
        if not str(source.get("path") or "").strip() or source.get("observed") in (None, "", [], {}):
            raise ValueError("investigator receipt evidence source is incomplete")
    contradictions = value.get("custody_contradictions")
    if not isinstance(contradictions, list):
        raise ValueError("investigator receipt custody_contradictions is invalid")
    if value.get("custody_status") == "contradictory" and not contradictions:
        raise ValueError("contradictory custody requires contradiction evidence")
    for item in contradictions:
        if not isinstance(item, Mapping) or not all(
            str(item.get(field) or "").strip()
            for field in ("left_source", "right_source", "contradiction")
        ):
            raise ValueError("investigator receipt custody contradiction is incomplete")
    recovery = value.get("intended_recovery")
    if not isinstance(recovery, Mapping) or not str(recovery.get("predicate") or "").strip():
        raise ValueError("investigator receipt intended_recovery is invalid")
    for field in ("blocker_cleared_required", "fresh_progress_required", "beyond_stage_required"):
        if not isinstance(recovery.get(field), bool):
            raise ValueError(f"investigator receipt intended_recovery missing {field}")
    target = value.get("safe_repair_target")
    if not isinstance(target, Mapping) or target.get("kind") not in SAFE_REPAIR_TARGET_KINDS:
        raise ValueError("investigator receipt safe_repair_target is invalid")
    for field in ("scope", "rationale"):
        if not str(target.get(field) or "").strip():
            raise ValueError(f"investigator receipt safe_repair_target missing {field}")
    handoff = value.get("handoff")
    if not isinstance(handoff, Mapping) or handoff.get("action") != value.get("recommended_action"):
        raise ValueError("investigator receipt handoff action disagrees")
    for field in ("allowed_mutations", "forbidden_mutations"):
        items = handoff.get(field)
        if not isinstance(items, list) or not items or not all(str(item).strip() for item in items):
            raise ValueError(f"investigator receipt handoff {field} is invalid")
    allowed_mutations = {str(item).strip() for item in handoff.get("allowed_mutations") or []}
    if value.get("recommended_action") in {"preserve_live", "replan"}:
        if allowed_mutations != {"none"}:
            raise ValueError("non-mutating investigator handoff must allow only none")
    if value.get("recommended_action") in {"repair_source", "repair_target", "recover_state"}:
        if allowed_mutations == {"none"} or "none" in allowed_mutations:
            raise ValueError("mutating investigator handoff did not name a bounded mutation")
    if value.get("recommended_action") == "recover_state" and not any(
        "cli" in item.lower() or "repair_custody" in item.lower()
        for item in allowed_mutations
    ):
        raise ValueError("state recovery handoff must name a supported CLI or repair custody operation")
    four_axis = value.get("four_axis")
    if not isinstance(four_axis, Mapping) or any(
        four_axis.get(axis) not in {"pass", "fail", "unknown"}
        for axis in ("TRACKED", "FIXED", "INTENT", "CONTEXT")
    ):
        raise ValueError("investigator receipt four_axis is invalid")
    prior = value.get("prior_repairs_considered")
    if not isinstance(prior, list) or not prior or not all(str(item).strip() for item in prior):
        raise ValueError("investigator receipt prior_repairs_considered is invalid")
    if value.get("custody_status") == "unknown" and value.get("recommended_action") != "replan":
        raise ValueError("unknown custody must fail closed to replan")
    if value.get("guard_weakening_risk") != "none" and value.get("recommended_action") != "replan":
        raise ValueError("guard weakening risk must fail closed to replan")
    if value.get("preserve_live") and value.get("recommended_action") != "preserve_live":
        raise ValueError("preserve_live receipt action disagrees")
    action = str(value.get("recommended_action") or "")
    target_kind = str(target.get("kind") or "")
    allowed_targets = {
        "preserve_live": {"none"},
        "replan": {"none", "repair_custody"},
        "repair_source": {"arnold_source", "target_workspace"},
        "repair_target": {"target_workspace"},
        "recover_state": {"plan_state_via_cli", "repair_custody"},
    }
    if target_kind not in allowed_targets[action]:
        raise ValueError("investigator action and safe repair target disagree")
    if isinstance(observation_bundle, Mapping):
        if observation_bundle.get("context_digest") != expected_context_digest:
            raise ValueError("investigator observation bundle digest disagrees")
        external_guard = {}
        for item in observation_bundle.get("observations") or []:
            if isinstance(item, Mapping) and item.get("kind") == "external_state":
                observed = item.get("observed")
                if isinstance(observed, Mapping):
                    external_guard = (
                        observed.get("external_guard")
                        if isinstance(observed.get("external_guard"), Mapping)
                        else {}
                    )
                break
        if external_guard.get("status") != "clear" and action == "recover_state":
            raise ValueError(
                "state recovery cannot bypass a failing or pending external PR/CI guard"
            )
    if (
        action == "replan"
        and target_kind == "repair_custody"
        and value.get("custody_status") != "contradictory"
    ):
        raise ValueError(
            "replan may name repair_custody only for contradictory custody"
        )
    validated = dict(value)
    validated["receipt_digest"] = _digest(
        {key: item for key, item in validated.items() if key != "receipt_digest"}
    )
    return validated


def summarize_investigation_artifacts(
    repair_data: Mapping[str, Any], *, field: str = "investigation"
) -> dict[str, Any]:
    """Return deterministic L1/L2 investigation health for repair and L3 audit."""

    investigation = repair_data.get(field)
    if not isinstance(investigation, Mapping):
        return {
            "required": True,
            "status": "missing",
            "reason": f"repair data has no {field} handoff",
        }
    if investigation.get("status") == "failed":
        return {
            "required": True,
            "status": "invalid",
            "reason": _text(investigation.get("reason"), 1000)
            or f"{field} failed before a valid handoff",
            "context_path": _text(investigation.get("context_path"), 2000),
            "receipt_path": _text(investigation.get("receipt_path"), 2000),
            "failure_code": _text(investigation.get("failure_code"), 300),
            "executor_error": _text(investigation.get("executor_error"), 1000),
            "executor_mode": _text(investigation.get("executor_mode"), 300),
            "access_receipt_path": _text(
                investigation.get("access_receipt_path"), 2000
            ),
        }
    context_path = Path(str(investigation.get("context_path") or ""))
    receipt_path = Path(str(investigation.get("receipt_path") or ""))
    digest = str(investigation.get("context_digest") or "")
    context = _load(context_path)
    receipt = _load(receipt_path)
    if not context or not receipt or not digest:
        return {
            "required": True,
            "status": "missing",
            "reason": "investigation context, digest, or receipt is absent",
            "context_path": str(context_path),
            "receipt_path": str(receipt_path),
        }
    try:
        validated = validate_investigator_receipt(receipt, expected_context_digest=digest)
    except ValueError as exc:
        return {
            "required": True,
            "status": "invalid",
            "reason": str(exc),
            "context_path": str(context_path),
            "receipt_path": str(receipt_path),
            "context_digest": digest,
        }
    recomputed_context_digest = _digest({k: v for k, v in context.items() if k != "context_digest"})
    if context.get("context_digest") != digest or recomputed_context_digest != digest:
        return {
            "required": True,
            "status": "invalid",
            "reason": "durable context digest disagrees with repair handoff",
            "context_path": str(context_path),
            "receipt_path": str(receipt_path),
            "context_digest": digest,
        }
    if validated.get("target_kind") != context.get("target_kind"):
        return {
            "required": True,
            "status": "invalid",
            "reason": "investigation receipt target kind disagrees with context",
            "context_path": str(context_path),
            "receipt_path": str(receipt_path),
            "context_digest": digest,
        }
    return {
        "required": True,
        "status": "accepted",
        "target_kind": validated.get("target_kind"),
        "context_path": str(context_path),
        "receipt_path": str(receipt_path),
        "context_digest": digest,
        "receipt_digest": validated.get("receipt_digest"),
        "actual_failure_classification": (validated.get("actual_failure") or {}).get("classification"),
        "evidence_source_kinds": sorted(
            {str(item.get("kind")) for item in validated.get("evidence_sources") or [] if isinstance(item, Mapping)}
        ),
        "custody_status": validated.get("custody_status"),
        "contradiction_count": len(validated.get("custody_contradictions") or []),
        "recommended_action": validated.get("recommended_action"),
        "safe_repair_target": validated.get("safe_repair_target"),
        "intended_recovery": validated.get("intended_recovery"),
        "four_axis": validated.get("four_axis"),
    }


def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(dict(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--workspace", required=True)
    build.add_argument("--session", required=True)
    build.add_argument("--remote-spec", required=True)
    build.add_argument("--repair-data", required=True)
    build.add_argument("--request-path", default="")
    build.add_argument("--goal-path", required=True)
    build.add_argument("--l2-handoff-path", default="")
    build.add_argument("--l2-context-digest", default="")
    build.add_argument("--output", required=True)
    build_meta = sub.add_parser("build-meta")
    build_meta.add_argument("--session", required=True)
    build_meta.add_argument("--trigger", required=True)
    build_meta.add_argument("--repair-data-dir", required=True)
    build_meta.add_argument("--marker-dir", required=True)
    build_meta.add_argument("--arnold-src", required=True)
    build_meta.add_argument("--request-id", default="")
    build_meta.add_argument("--blocker-id", default="")
    build_meta.add_argument("--output", required=True)
    observe_meta = sub.add_parser("observe-meta")
    observe_meta.add_argument("--context", required=True)
    observe_meta.add_argument("--output", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--receipt", required=True)
    validate.add_argument("--context-digest", required=True)
    validate.add_argument("--observation", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build":
        value = build_investigation_context(
            workspace=args.workspace,
            session=args.session,
            remote_spec=args.remote_spec,
            repair_data_path=args.repair_data,
            request_path=args.request_path,
            goal_path=args.goal_path,
            l2_handoff_path=args.l2_handoff_path,
            l2_context_digest=args.l2_context_digest,
        )
        _atomic_write(Path(args.output), value)
    elif args.command == "build-meta":
        value = build_meta_investigation_context(
            session=args.session,
            trigger=args.trigger,
            repair_data_dir=args.repair_data_dir,
            marker_dir=args.marker_dir,
            arnold_src=args.arnold_src,
            request_id=args.request_id,
            blocker_id=args.blocker_id,
        )
        _atomic_write(Path(args.output), value)
    elif args.command == "observe-meta":
        value = build_meta_observation_bundle(args.context)
        _atomic_write(Path(args.output), value)
    else:
        value = validate_investigator_receipt(
            _load(args.receipt),
            expected_context_digest=args.context_digest,
            observation_bundle=_load(args.observation) if args.observation else None,
        )
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "MAX_CONTEXT_BYTES",
    "META_REPAIR_INVESTIGATION_ENVELOPE_SCHEMA",
    "REPAIR_INVESTIGATION_CONTEXT_SCHEMA",
    "REPAIR_INVESTIGATOR_RECEIPT_SCHEMA",
    "EVIDENCE_SOURCE_KINDS",
    "INVESTIGATION_TARGET_KINDS",
    "build_meta_investigation_context",
    "build_meta_observation_bundle",
    "build_investigation_context",
    "summarize_investigation_artifacts",
    "validate_meta_investigation_context",
    "validate_investigator_receipt",
]
