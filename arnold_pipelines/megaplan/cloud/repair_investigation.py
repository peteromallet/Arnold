"""Bounded authoritative context and receipts for two-stage automatic repair."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan.cloud.repair_goal import capture_checkpoint, utc_now


REPAIR_INVESTIGATION_CONTEXT_SCHEMA = "arnold-repair-investigation-context-v1"
REPAIR_INVESTIGATOR_RECEIPT_SCHEMA = "arnold-repair-investigator-receipt-v2"
MAX_CONTEXT_BYTES = 64 * 1024
INVESTIGATION_TARGET_KINDS = frozenset({"l1_repair_target", "l2_repair_system"})
EVIDENCE_SOURCE_KINDS = frozenset(
    {
        "live_process",
        "session_marker",
        "chain_state",
        "plan_state",
        "phase_result",
        "event_log",
        "repair_data",
        "repair_queue",
        "repair_goal",
        "meta_repair",
        "source_tree",
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
        "action_target_contract": {
            "preserve_live": ["none"],
            "replan": ["none"],
            "repair_source": ["arnold_source", "target_workspace"],
            "repair_target": ["target_workspace"],
            "recover_state": ["plan_state_via_cli", "repair_custody"],
        },
        "handoff": {
            "action": "preserve_live|repair_source|repair_target|recover_state|replan",
            "allowed_mutations": ["<bounded mutation or none>"],
            "forbidden_mutations": ["<unsafe mutation>"],
        },
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
    frozen_checkpoint: Mapping[str, Any],
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
    frozen_failure = frozen_checkpoint.get("latest_failure")
    current_failure = current.get("latest_failure")
    if isinstance(frozen_failure, Mapping) and isinstance(current_failure, Mapping):
        frozen_fingerprint = _digest(dict(frozen_failure))
        current_fingerprint = _digest(dict(current_failure))
        if frozen_fingerprint != current_fingerprint:
            contradictions.append(
                {
                    "left_source": _text(goal_path, 2000) or "repair_goal",
                    "right_source": _text(current.get("plan_state_path"), 2000) or "plan_state",
                    "contradiction": "frozen repair-goal failure differs from current plan failure",
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
        (request_plan and current_plan and request_plan != current_plan)
        or (request_stage and current_stage and request_stage != current_stage)
    )
    attempts = [item for item in repair_data.get("attempts") or [] if isinstance(item, Mapping)]
    contradictions = _context_contradictions(
        request_mismatch=request_mismatch,
        request_path=request_path,
        goal_path=goal_path,
        frozen_checkpoint=frozen_checkpoint,
        current=current,
    )
    recovery_contract = (
        dict(goal.get("recovery_contract"))
        if isinstance(goal.get("recovery_contract"), Mapping)
        else {}
    )
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
        "exact_error": current.get("latest_failure")
        or (phase_result if phase_result_blocked else {})
        or frozen_checkpoint.get("latest_failure")
        or {},
        "request": {
            "request_id": _text(request.get("request_id"), 300),
            "created_at": _text(request.get("created_at"), 100),
            "problem_signature": dict(request_signature),
            "target": dict(request_target),
            "matches_current_target": not request_mismatch,
            "mismatch_reason": (
                f"queued request plan/stage {request_plan!r}/{request_stage!r} disagrees with "
                f"current {current_plan!r}/{current_stage!r}"
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


def build_meta_investigation_context(
    *,
    session: str,
    trigger: str,
    repair_data_dir: str | Path,
    marker_dir: str | Path,
    arnold_src: str | Path,
) -> dict[str, Any]:
    """Build the bounded, read-only L2 investigation input.

    This deliberately shares evidence-source, contradiction, recovery, and
    handoff semantics with L1 without coupling the six-hour auditor to a
    mutating dispatcher.
    """

    repair_root = Path(repair_data_dir)
    marker_root = Path(marker_dir)
    source_root = Path(arnold_src)
    repair_path = repair_root / f"{session}.repair-data.json"
    marker_path = marker_root / f"{session}.json"
    repair_data = _load(repair_path)
    marker = _load(marker_path)
    meta_dir = repair_root / "meta"
    meta_paths = sorted(meta_dir.glob(f"*{session}*.json"), key=lambda item: item.stat().st_mtime)[-5:]
    meta_records = [_load(path) for path in meta_paths]
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
    source_tree = _git_observation(source_root)
    contradictions: list[dict[str, str]] = []
    outcome = _text(repair_data.get("outcome"), 200).lower()
    if outcome in {"running", "repairing"} and not repair_data.get("current_attempt_id"):
        contradictions.append(
            {
                "left_source": str(repair_path),
                "right_source": str(marker_path),
                "contradiction": "repair-data claims active repair without a current attempt owner",
            }
        )
    if current_target.get("observation_error"):
        contradictions.append(
            {
                "left_source": str(marker_path),
                "right_source": "current_target_resolver",
                "contradiction": "current target could not be resolved from marker/repair custody",
            }
        )
    evidence_sources = [
        _evidence_source("repair_data", repair_path, repair_data, authority=7),
        _evidence_source("session_marker", marker_path, marker, authority=2),
        _evidence_source("source_tree", source_root, source_tree, authority=9),
    ]
    for path, record in zip(meta_paths, meta_records):
        evidence_sources.append(_evidence_source("meta_repair", path, record, authority=10))
    context: dict[str, Any] = {
        "schema_version": REPAIR_INVESTIGATION_CONTEXT_SCHEMA,
        "target_kind": "l2_repair_system",
        "generated_at": utc_now(),
        "session": session,
        "trigger": _text(trigger, 300),
        "repair_data_path": str(repair_path),
        "marker_path": str(marker_path),
        "arnold_src": str(source_root),
        "actual_failure_seed": {
            "repair_outcome": repair_data.get("outcome"),
            "latest_failure": repair_data.get("latest_failure"),
            "trigger": trigger,
        },
        "current_target": current_target,
        "source_tree": source_tree,
        "evidence_sources": evidence_sources,
        "custody_status": "contradictory" if contradictions else "consistent",
        "custody_contradictions": contradictions,
        "intended_recovery": {
            "predicate": (
                "fix the first broken repair layer and its backstop, retrigger ordinary L1, "
                "then verify the original blocker cleared with fresh accepted progress beyond "
                "the frozen stage"
            ),
            "blocker_cleared_required": True,
            "fresh_progress_required": True,
            "beyond_stage_required": True,
        },
        "safe_repair_boundaries": {
            "allowed": ["arnold_source", "repair_custody"],
            "forbidden": ["audited_workspace", "direct_chain_state_edit", "guard_weakening", "uncited_mutation"],
        },
        "required_investigator_output": _common_required_output("l2_repair_system"),
    }
    context["context_digest"] = _digest(context)
    encoded = json.dumps(context, sort_keys=True, separators=(",", ":"), default=str).encode()
    if len(encoded) > MAX_CONTEXT_BYTES:
        context["evidence_sources"] = context["evidence_sources"][-4:]
        context["context_digest"] = _digest({k: v for k, v in context.items() if k != "context_digest"})
        encoded = json.dumps(context, sort_keys=True, separators=(",", ":"), default=str).encode()
    if len(encoded) > MAX_CONTEXT_BYTES:
        raise ValueError("bounded meta-repair investigation context exceeds 64 KiB")
    return context


def validate_investigator_receipt(
    value: Mapping[str, Any], *, expected_context_digest: str
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
        "replan": {"none"},
        "repair_source": {"arnold_source", "target_workspace"},
        "repair_target": {"target_workspace"},
        "recover_state": {"plan_state_via_cli", "repair_custody"},
    }
    if target_kind not in allowed_targets[action]:
        raise ValueError("investigator action and safe repair target disagree")
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
    build.add_argument("--output", required=True)
    build_meta = sub.add_parser("build-meta")
    build_meta.add_argument("--session", required=True)
    build_meta.add_argument("--trigger", required=True)
    build_meta.add_argument("--repair-data-dir", required=True)
    build_meta.add_argument("--marker-dir", required=True)
    build_meta.add_argument("--arnold-src", required=True)
    build_meta.add_argument("--output", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--receipt", required=True)
    validate.add_argument("--context-digest", required=True)
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
        )
        _atomic_write(Path(args.output), value)
    elif args.command == "build-meta":
        value = build_meta_investigation_context(
            session=args.session,
            trigger=args.trigger,
            repair_data_dir=args.repair_data_dir,
            marker_dir=args.marker_dir,
            arnold_src=args.arnold_src,
        )
        _atomic_write(Path(args.output), value)
    else:
        value = validate_investigator_receipt(
            _load(args.receipt), expected_context_digest=args.context_digest
        )
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "MAX_CONTEXT_BYTES",
    "REPAIR_INVESTIGATION_CONTEXT_SCHEMA",
    "REPAIR_INVESTIGATOR_RECEIPT_SCHEMA",
    "EVIDENCE_SOURCE_KINDS",
    "INVESTIGATION_TARGET_KINDS",
    "build_meta_investigation_context",
    "build_investigation_context",
    "summarize_investigation_artifacts",
    "validate_investigator_receipt",
]
