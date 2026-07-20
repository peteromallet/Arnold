"""Bounded authoritative context and receipts for two-stage automatic repair."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan.cloud.repair_goal import capture_checkpoint, utc_now
from arnold_pipelines.megaplan.cloud.meta_repair_policy import (
    resolve_authoritative_blocker_id,
)
from arnold_pipelines.megaplan.cloud.redact import redact_payload
from arnold_pipelines.megaplan.resident.provenance import (
    normalize_delegation_provenance,
    provenance_from_environment,
)


REPAIR_INVESTIGATION_CONTEXT_SCHEMA = "arnold-repair-investigation-context-v1"
META_REPAIR_INVESTIGATION_ENVELOPE_SCHEMA = "arnold-meta-repair-investigation-envelope-v2"
REPAIR_INVESTIGATOR_RECEIPT_SCHEMA = "arnold-repair-investigator-receipt-v2"
MAX_CONTEXT_BYTES = 64 * 1024
MAX_RECEIPT_BYTES = 64 * 1024
MAX_OBSERVATION_BUNDLE_BYTES = 48 * 1024
META_REPAIR_OBSERVATION_BUNDLE_SCHEMA = "arnold-meta-repair-observation-bundle-v1"
REPAIR_OBSERVATION_BUNDLE_SCHEMA = "arnold-repair-observation-bundle-v1"
INVESTIGATION_TARGET_KINDS = frozenset({"l1_repair_target", "l2_repair_system"})
EVIDENCE_SOURCE_KINDS = frozenset(
    {
        "live_process",
        "session_marker",
        "chain_state",
        "plan_state",
        "phase_result",
        "review_artifact",
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
L2_ARNOLD_SOURCE_COMPONENT_PREFIXES = (
    "arnold_pipelines/megaplan/cloud",
    "tests/cloud",
)


def _validate_l2_source_handoff(
    value: Mapping[str, Any], *, action: str, target_kind: str,
    allowed_mutations: set[str],
) -> None:
    """Keep L2 source authority inside the Arnold repair-system checkout.

    A free-form ``arnold_source:`` label is not custody.  L2 may hand a
    mutating worker only normalized repo-relative repair-system components;
    target-application code must remain owned by ordinary L1 repair.
    """

    if value.get("target_kind") != "l2_repair_system" or action != "repair_source":
        return
    if target_kind != "arnold_source":
        raise ValueError("L2 source repair must target arnold_source")
    if not allowed_mutations:
        raise ValueError("L2 source repair must name an Arnold repair-system component")
    for mutation in allowed_mutations:
        prefix, separator, component = mutation.partition(":")
        if prefix != "arnold_source" or not separator:
            raise ValueError(
                "L2 source repair mutations must use arnold_source:<repo-relative component>"
            )
        if (
            not component
            or component.startswith("/")
            or "\\" in component
            or any(character.isspace() for character in component)
        ):
            raise ValueError("L2 source repair component is not a normalized repo-relative path")
        parts = component.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("L2 source repair component is not a normalized repo-relative path")
        if not any(
            component == allowed or component.startswith(f"{allowed}/")
            for allowed in L2_ARNOLD_SOURCE_COMPONENT_PREFIXES
        ):
            raise ValueError("L2 source repair component is outside Arnold repair-system scope")


def _validate_l1_target_handoff(
    value: Mapping[str, Any], *, action: str, target_kind: str,
    allowed_mutations: set[str], investigation_context: Mapping[str, Any],
) -> None:
    """Reject workspace-wide or free-form L1 mutation grants.

    The investigator may authorize files or bounded repo-relative component
    directories. An absolute workspace path is target discovery, not a
    mutation boundary.
    """

    if value.get("target_kind") != "l1_repair_target" or action != "repair_target":
        return
    if target_kind != "target_workspace" or not allowed_mutations:
        raise ValueError("L1 target repair must name target_workspace components")
    if len(allowed_mutations) > 32:
        raise ValueError("L1 target repair names too many mutation components")
    for mutation in allowed_mutations:
        prefix, separator, component = mutation.partition(":")
        if prefix != "target_workspace" or not separator:
            raise ValueError(
                "L1 target repair mutations must use target_workspace:<repo-relative component>"
            )
        if (
            not component
            or component.startswith("/")
            or "\\" in component
            or any(character.isspace() for character in component)
        ):
            raise ValueError("L1 target repair component is not a normalized repo-relative path")
        parts = component.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("L1 target repair component is not a normalized repo-relative path")
    workspace = str(investigation_context.get("workspace") or "").strip()
    if not workspace or not Path(workspace).is_absolute():
        raise ValueError("L1 target repair context lacks an absolute target workspace")


def _load(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _load_bounded_json(path: str | Path, *, max_bytes: int, label: str) -> dict[str, Any]:
    source = Path(path)
    try:
        encoded = source.open("rb").read(max_bytes + 1)
    except OSError as exc:
        raise ValueError(f"cannot read {label}: {source}") from exc
    if len(encoded) > max_bytes:
        raise ValueError(f"{label} exceeds {max_bytes}-byte bound")
    try:
        value = json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


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


def _review_quality_blocker_summary(plan_state_path: object) -> dict[str, Any]:
    """Return bounded authoritative rework evidence for a blocked review.

    A workspace HEAD change is not evidence that a review blocker was fixed.
    Keep the review verdict and its concrete rework target in the L1 envelope so
    the investigator cannot replace the persisted quality decision with a
    generic stale-state inference.
    """

    if not plan_state_path:
        return {}
    path = Path(str(plan_state_path)).parent / "review.json"
    try:
        stat = path.stat()
        if stat.st_size > 2 * 1024 * 1024:
            raise ValueError(f"review artifact exceeds 2 MiB bound: {path}")
        raw = path.read_bytes()
        if len(raw) != stat.st_size:
            raise ValueError(f"review artifact changed while read: {path}")
        value = json.loads(raw)
    except FileNotFoundError:
        return {"path": str(path), "present": False}
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"review artifact is unreadable: {path}") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"review artifact is not an object: {path}")

    criteria = value.get("criteria") if isinstance(value.get("criteria"), list) else []
    failed_criteria = []
    for item in criteria:
        if not isinstance(item, Mapping) or str(item.get("pass") or "").lower() != "fail":
            continue
        failed_criteria.append(
            {
                "name": _text(item.get("name"), 750),
                "evidence": _text(item.get("evidence"), 1000),
            }
        )
    rework = value.get("rework_items") if isinstance(value.get("rework_items"), list) else []
    rework_items = []
    for item in rework[-6:]:
        if not isinstance(item, Mapping):
            continue
        check = item.get("deterministic_check")
        check_summary = {}
        if isinstance(check, Mapping):
            check_summary = {
                "command": _text(check.get("command"), 1500),
                "baseline_status": _text(check.get("baseline_status"), 500),
                "post_status": _text(check.get("post_status"), 500),
            }
        rework_items.append(
            {
                "task_id": _text(item.get("task_id"), 200),
                "issue": _text(item.get("issue"), 1000),
                "expected": _text(item.get("expected"), 1000),
                "actual": _text(item.get("actual"), 1000),
                "evidence_file": _text(item.get("evidence_file"), 500),
                "deterministic_check": check_summary,
            }
        )
    return {
        "path": str(path),
        "present": True,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "review_verdict": _text(value.get("review_verdict"), 300),
        "summary": _text(value.get("summary"), 1000),
        "issues": [_text(item, 1000) for item in (value.get("issues") or [])[-6:]],
        "failed_criteria": failed_criteria[-6:],
        "rework_items": rework_items,
    }


def _durable_quality_repair_evidence(
    repair_data: Mapping[str, Any],
    current: Mapping[str, Any],
    review_quality_blocker: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind a prior target repair to the current HEAD and review rework scope."""

    workspace_head = _text(current.get("workspace_head"), 100).lower()
    if len(workspace_head) != 40 or any(
        char not in "0123456789abcdef" for char in workspace_head
    ):
        return {"verified": False, "reason": "current workspace HEAD is unavailable"}
    rework_scopes = {
        _text(item.get("evidence_file"), 1000)
        for item in review_quality_blocker.get("rework_items") or []
        if isinstance(item, Mapping) and _text(item.get("evidence_file"), 1000)
    }
    candidates = [
        item
        for collection in (
            repair_data.get("attempts") or [],
            repair_data.get("iterations") or [],
        )
        for item in collection
        if isinstance(item, Mapping)
    ]
    for item in reversed(candidates):
        try:
            if int(item.get("dev_turn_rc")) != 0:
                continue
        except (TypeError, ValueError):
            continue
        dev_fix_sha = _text(item.get("dev_fix_sha"), 100).lower()
        if dev_fix_sha != workspace_head:
            continue
        report = item.get("dev_report")
        report = report if isinstance(report, Mapping) else {}
        validation = report.get("validation")
        if validation in (None, "", [], {}):
            continue
        local_commit = _text(report.get("local_commit"), 100).lower()
        if len(local_commit) < 7 or not workspace_head.startswith(local_commit):
            continue
        target = report.get("safe_repair_target")
        target = target if isinstance(target, Mapping) else {}
        target_scope = _text(target.get("scope") or target.get("path"), 2000)
        if target.get("kind") != "target_workspace" or not target_scope:
            continue
        if rework_scopes and not any(
            scope == target_scope or target_scope.endswith(f"/{scope}")
            for scope in rework_scopes
        ):
            continue
        return {
            "verified": True,
            "workspace_head": workspace_head,
            "dev_fix_sha": dev_fix_sha,
            "attempt_id": item.get("attempt_id") or item.get("i"),
            "target_kind": target.get("kind"),
            "target_scope": target_scope,
            "validation_present": True,
        }
    return {
        "verified": False,
        "workspace_head": workspace_head,
        "reason": "no successful validated target repair is bound to current HEAD and rework scope",
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
            "preserve_live": {
                "action": "preserve_live",
                "allowed_mutations": ["none"],
                "forbidden_mutations": ["all_mutations"],
            },
            "replan": {
                "action": "replan",
                "allowed_mutations": ["none"],
                "forbidden_mutations": [
                    "direct_chain_state_edit",
                    "recover_state",
                    "hand_advance_chain",
                ],
            },
            "repair_source": {
                "action": "repair_source",
                "allowed_mutations": ["arnold_source:<bounded component>"],
                "forbidden_mutations": [
                    "audited_workspace",
                    "direct_chain_state_edit",
                    "guard_weakening",
                ],
            },
            "repair_target": {
                "action": "repair_target",
                "allowed_mutations": ["target_workspace:<bounded component>"],
                "forbidden_mutations": [
                    "arnold_source",
                    "direct_chain_state_edit",
                    "guard_weakening",
                ],
            },
            "recover_state": {
                "action": "recover_state",
                "allowed_mutations": ["supported_cli:<exact command>"],
                "forbidden_mutations": [
                    "direct_chain_state_edit",
                    "hand_advance_chain",
                    "guard_weakening",
                ],
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
    l2_replan_epoch: int | str | None = None,
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
    latest_failure = (
        current.get("latest_failure")
        if isinstance(current.get("latest_failure"), Mapping)
        else {}
    )
    latest_failure_kind = _text(latest_failure.get("kind"), 300).lower()
    durable_quality_block = bool(
        str(current.get("plan_state") or "").lower() == "blocked"
        and (
            "quality" in latest_failure_kind
            or phase_exit_kind == "blocked_by_quality"
        )
    )
    review_quality_blocker = (
        _review_quality_blocker_summary(current.get("plan_state_path"))
        if durable_quality_block
        else {}
    )
    durable_quality_repair = (
        _durable_quality_repair_evidence(
            repair_data,
            current,
            review_quality_blocker,
        )
        if durable_quality_block
        else {"verified": False, "reason": "no active durable quality block"}
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
    l2_replan_authorization: dict[str, Any] = {"verified": False}
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
        requested_epoch = int(l2_replan_epoch or 0)
        if requested_epoch:
            active_epoch = int(goal.get("active_replan_epoch") or 0)
            replans = goal.get("l2_replans") if isinstance(goal.get("l2_replans"), list) else []
            matching_replan = next(
                (
                    item
                    for item in replans
                    if isinstance(item, Mapping)
                    and int(item.get("epoch") or 0) == requested_epoch
                    and str(item.get("context_digest") or "") == expected_handoff_digest
                ),
                None,
            )
            target_identity = {
                "session": _text(goal_target.get("session"), 300),
                "workspace": str(Path(str(goal_target.get("workspace") or ""))),
                "remote_spec": _text(goal_target.get("remote_spec"), 2000),
            }
            actual_identity = {
                "session": _text(session, 300),
                "workspace": str(Path(workspace)),
                "remote_spec": _text(remote_spec, 2000),
            }
            if (
                active_epoch != requested_epoch
                or matching_replan is None
                or target_identity != actual_identity
            ):
                raise ValueError("L2-to-L1 replan authorization is stale or disagrees with goal identity")
            l2_replan_authorization = {
                "verified": True,
                "replan_epoch": requested_epoch,
                "context_digest": expected_handoff_digest,
                "frozen_checkpoint_digest": _text(
                    matching_replan.get("frozen_checkpoint_digest"), 100
                ),
                "allowed_recovery": "recover_state_via_supported_cli_only",
                "forbidden": [
                    "direct_state_edit",
                    "hand_advance_chain",
                    "duplicate_live_worker",
                ],
            }
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
    target_source_state = _git_observation(Path(workspace), include_status_paths=True)
    evidence_sources.append(
        _evidence_source(
            "source_tree",
            workspace,
            target_source_state,
            authority=5,
        )
    )
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
    if review_quality_blocker:
        evidence_sources.append(
            _evidence_source(
                "review_artifact",
                review_quality_blocker.get("path"),
                review_quality_blocker,
                authority=5,
            )
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
    chain_start_cli = shlex.join(
        [
            "python",
            "-P",
            "-m",
            "arnold_pipelines.megaplan",
            "chain",
            "start",
            "--spec",
            str(remote_spec),
            "--project-dir",
            str(Path(workspace)),
        ]
    )
    plan_state_payload = _load(current.get("plan_state_path"))
    superseded_failure = _superseded_failure_evidence(plan_state_payload)
    historical_failure_recovery = {
        "applicable": bool(superseded_failure.get("detected")),
        "evidence": superseded_failure,
        "authority": "guarded_override_cli_then_ordinary_chain_start",
    }
    supported_recovery_cli = chain_start_cli
    if superseded_failure.get("detected") is True and plan_name:
        recover_blocked_cli = shlex.join(
            [
                "python",
                "-P",
                "-m",
                "arnold_pipelines.megaplan",
                "override",
                "recover-blocked",
                "--project-dir",
                str(Path(workspace)),
                "--plan",
                plan_name,
                "--reason",
                (
                    "automatic repair verified that the repeated-failure block references "
                    "a historical occurrence superseded by a later same-phase success"
                ),
            ]
        )
        supported_recovery_cli = f"{recover_blocked_cli} && {chain_start_cli}"
    required_investigator_output = _common_required_output("l1_repair_target")
    required_investigator_output["action_specific_handoff_examples"]["recover_state"][
        "allowed_mutations"
    ] = [f"supported_cli:{supported_recovery_cli}"]
    if durable_quality_block and durable_quality_repair.get("verified") is not True:
        rework_items = (
            review_quality_blocker.get("rework_items")
            if isinstance(review_quality_blocker.get("rework_items"), list)
            else []
        )
        repair_files = [
            _text(item.get("evidence_file"), 500)
            for item in rework_items
            if isinstance(item, Mapping) and _text(item.get("evidence_file"), 500)
        ]
        repair_scope = ",".join(repair_files)[:2000] or "current review rework target"
        required_investigator_output.update(
            {
                "recommended_action": "repair_target",
                "safe_repair_target": {
                    "kind": "target_workspace",
                    "scope": repair_scope,
                    "rationale": (
                        "The authoritative blocked review artifact names unresolved target "
                        "rework; state replay is prohibited until that rework is repaired."
                    ),
                },
                "handoff": {
                    "action": "repair_target",
                    "allowed_mutations": [f"target_workspace:{repair_scope}"],
                    "forbidden_mutations": [
                        "arnold_source",
                        "direct_chain_state_edit",
                        "hand_advance_chain",
                        "guard_weakening",
                    ],
                },
                "prohibited_actions": {
                    "recover_state": (
                        "persisted review-quality blocker has concrete unresolved rework"
                    )
                },
            }
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
        "durable_quality_block": {
            "active": durable_quality_block,
            "recover_state_allowed": bool(
                not durable_quality_block
                or durable_quality_repair.get("verified") is True
            ),
            "reason": (
                "A persisted blocked review verdict is authoritative until its concrete "
                "rework is repaired by a validated commit bound to the current HEAD and "
                "target scope."
                if durable_quality_block and durable_quality_repair.get("verified") is not True
                else (
                    "The bounded target repair is durably bound to the current HEAD; "
                    "recovery may record resolution=fixed and must rerun review."
                    if durable_quality_block
                    else ""
                )
            ),
            "repair_evidence": durable_quality_repair,
            "review_artifact": {
                key: review_quality_blocker.get(key)
                for key in ("path", "present", "sha256", "size_bytes", "review_verdict")
            },
            "allowed_actions": (
                ["repair_source", "repair_target", "replan"]
                if durable_quality_block and durable_quality_repair.get("verified") is not True
                else [
                    "preserve_live",
                    "repair_source",
                    "repair_target",
                    "recover_state",
                    "replan",
                ]
            ),
        },
        "exact_error": external_failure
        or current.get("latest_failure")
        or (phase_result if phase_result_blocked else {})
        or (
            {
                "failure_kind": "active_unowned_repair_goal",
                "message": (
                    "L2 verified the recovery epoch; no canonical runner is live and "
                    "the exact supported recovery CLI has not yet produced accepted progress"
                ),
                "replan_epoch": l2_replan_authorization.get("replan_epoch"),
            }
            if l2_replan_authorization.get("verified") is True
            else {}
        )
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
        "l2_replan_authorization": l2_replan_authorization,
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
        "historical_failure_recovery": historical_failure_recovery,
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
            "supported_recovery_cli": supported_recovery_cli,
        },
        "required_investigator_output": required_investigator_output,
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


def _git_observation(
    root: Path, *, include_status_paths: bool = False
) -> dict[str, Any]:
    result: dict[str, Any] = {"path": str(root), "head": "", "branch": "", "dirty": None}
    status_args = [
        "status",
        "--porcelain=v1",
        "--untracked-files=all" if include_status_paths else "--untracked-files=no",
    ]
    for key, args in (
        ("head", ["rev-parse", "HEAD"]),
        ("branch", ["symbolic-ref", "--quiet", "--short", "HEAD"]),
        ("status", status_args),
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
            value = (
                proc.stdout.rstrip("\r\n")
                if key == "status"
                else proc.stdout.strip()
            )
            if key == "status":
                result["dirty"] = bool(value)
                if include_status_paths:
                    # File names are necessary mutation-scope evidence for the
                    # tool-less investigator. Keep the observation bounded so
                    # a pathological worktree cannot expand the receipt prompt.
                    lines = [line[:500] for line in value.splitlines()[:160]]
                    result["status_paths"] = lines
                    result["status_paths_truncated"] = len(value.splitlines()) > len(lines)
            else:
                result[key] = value
    return result


def _external_pr_snapshot(
    *,
    session: str,
    workspace: Path,
    repair_root: Path,
    pull_request_number: int | None = None,
) -> Path:
    """Persist a fresh, bounded read-only PR/CI observation for custody review."""

    evidence_dir = repair_root / "meta" / "evidence"
    safe_session = re.sub(r"[^A-Za-z0-9_.-]+", "-", session).strip("-") or "session"
    fields = (
        "number,url,state,isDraft,mergeStateStatus,headRefName,headRefOid,"
        "baseRefName,baseRefOid,updatedAt,statusCheckRollup"
    )
    selector = str(pull_request_number) if pull_request_number else "current_branch"
    snapshot: dict[str, Any] = {
        "schema_version": "arnold-external-pr-ci-observation-v1",
        "captured_at": utc_now(),
        "workspace": str(workspace),
        "query": f"gh pr view {selector} --json <bounded fields>",
        "available": False,
    }
    try:
        command = ["gh", "pr", "view"]
        if pull_request_number:
            command.append(str(pull_request_number))
        command.extend(["--json", fields])
        proc = subprocess.run(
            command,
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
    resident_delegation: Mapping[str, Any] | None = None,
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
    chain_state_ref = current_target.get("chain_state")
    chain_state_ref = chain_state_ref if isinstance(chain_state_ref, Mapping) else {}
    chain_state = _load(str(chain_state_ref.get("path") or ""))
    try:
        pull_request_number = int(chain_state.get("pr_number") or 0)
    except (TypeError, ValueError):
        pull_request_number = 0
    external_path = _external_pr_snapshot(
        session=session,
        workspace=target_workspace,
        repair_root=repair_root,
        pull_request_number=pull_request_number if pull_request_number > 0 else None,
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

    inherited_delegation = (
        normalize_delegation_provenance(resident_delegation)
        if resident_delegation is not None
        else None
    )
    if inherited_delegation is not None:
        encoded_delegation = json.dumps(
            inherited_delegation, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        delegation_digest = hashlib.sha256(encoded_delegation).hexdigest()
        safe_session = re.sub(r"[^A-Za-z0-9_.-]+", "-", session).strip("-") or "session"
        delegation_path = (
            repair_root
            / "meta"
            / "evidence"
            / f"{safe_session}-resident-delegation-{delegation_digest}.json"
        )
        if delegation_path.exists():
            if _load(delegation_path) != inherited_delegation:
                raise ValueError("content-addressed resident delegation evidence disagrees")
        else:
            _atomic_write(delegation_path, inherited_delegation)
        delegation = inherited_delegation
        delegation_source_path = delegation_path
        delegation_pointer = ""
    else:
        delegation = (
            repair_data.get("resident_delegation")
            if isinstance(repair_data.get("resident_delegation"), Mapping)
            else {}
        )
        delegation_source_path = repair_path
        delegation_pointer = "/resident_delegation"
    if delegation:
        provenance_ref = _file_reference(
            "resident_delegation",
            delegation_source_path,
            json_pointer=delegation_pointer,
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


def _superseded_failure_evidence(value: Mapping[str, Any]) -> dict[str, Any]:
    """Expose when a repeated-failure block points at superseded history."""

    latest = value.get("latest_failure")
    history = value.get("history")
    if not isinstance(latest, Mapping) or not isinstance(history, list):
        return {"detected": False}
    if str(latest.get("kind") or "").strip() != "repeated_failure_signature":
        return {"detected": False}
    metadata = latest.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    failure_step = str(metadata.get("failure_step") or "").strip().lower()
    failure_message = _text(metadata.get("failure_message"), 600)
    reported_index = metadata.get("failure_history_index")
    matching_index: int | None = None
    if isinstance(reported_index, int) and 0 <= reported_index < len(history):
        matching_index = reported_index
    if matching_index is None:
        for index, entry in enumerate(history):
            if not isinstance(entry, Mapping):
                continue
            step = str(entry.get("step") or entry.get("phase") or "").strip().lower()
            message = _text(entry.get("message"), 600)
            if failure_step and step != failure_step:
                continue
            if failure_message and message != failure_message:
                continue
            result = str(entry.get("result") or "").strip().lower()
            if result in {"error", "failed", "failure", "blocked"}:
                matching_index = index
    if matching_index is None:
        return {"detected": False}
    historical = history[matching_index]
    historical_step = str(
        historical.get("step") or historical.get("phase") or failure_step
    ).strip().lower()
    later_successes: list[dict[str, Any]] = []
    for index, entry in enumerate(history[matching_index + 1 :], matching_index + 1):
        if not isinstance(entry, Mapping):
            continue
        step = str(entry.get("step") or entry.get("phase") or "").strip().lower()
        result = str(entry.get("result") or "").strip().lower()
        if step == historical_step and result in {
            "success", "succeeded", "done", "pass", "passed", "ok",
        }:
            later_successes.append(
                {
                    "history_index": index,
                    "timestamp": _text(
                        entry.get("timestamp") or entry.get("completed_at"), 100
                    ),
                    "artifact_hash": _text(entry.get("artifact_hash"), 100),
                }
            )
    return {
        "detected": bool(later_successes),
        "failure_step": historical_step,
        "historical_failure_index": matching_index,
        "historical_failure_timestamp": _text(
            historical.get("timestamp") or historical.get("completed_at"), 100
        ),
        "later_same_phase_successes": later_successes[-5:],
        "reported_repeat_count": metadata.get("count"),
        "root_cause_hint": (
            "historical same-phase failure was counted after a later success; "
            "repair repeated-failure occurrence tracking and retrigger ordinary repair"
            if later_successes
            else ""
        ),
    }


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
            "repair_goal", "target", "verification",
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
        pr_state = _text(pull.get("state"), 100).upper()
        is_draft = pull.get("isDraft") is True
        selected["external_guard"] = {
            "status": (
                "unknown"
                if value.get("available") is not True
                else "failed"
                if failing or pr_state == "CLOSED"
                else "pending"
                if pending or is_draft or pr_state != "MERGED"
                else "clear"
            ),
            "failing_checks": failing,
            "pending_checks": pending,
            "pr_state": pr_state,
            "is_draft": is_draft,
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
    if kind == "repair_data" and isinstance(value.get("meta_investigation"), Mapping):
        prior = value["meta_investigation"]
        selected["prior_meta_investigation_summary"] = {
            key: prior[key]
            for key in (
                "actual_failure", "recommended_action", "four_axis",
                "safe_repair_target", "target_kind", "investigator_run_id",
                "receipt_path",
            )
            if key in prior
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
        selected["superseded_failure_evidence"] = _superseded_failure_evidence(value)
        selected["history"] = selected["history"][-8:]
    return _bound_observation_value(
        selected or {"keys": sorted(str(key) for key in value)[:100]}
    )


def _bound_observation_value(value: Any, *, depth: int = 0) -> Any:
    """Deterministically cap nested derived observations, never source evidence."""

    if depth >= 3:
        if value is None or isinstance(value, (bool, int, float)):
            return value
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


def _external_guard_applicability(
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Decide whether PR/CI state is operative for the current blocker."""

    chain_state = ""
    failure_kind = ""
    failure_phase = ""
    for item in observations:
        observed = item.get("observed")
        if not isinstance(observed, Mapping):
            continue
        if item.get("kind") == "chain_state":
            current = observed.get("current")
            current = current if isinstance(current, Mapping) else {}
            chain_state = str(
                observed.get("chain_last_state")
                or observed.get("last_state")
                or current.get("last_state")
                or ""
            ).strip().lower()
        elif item.get("kind") == "plan_state":
            current = observed.get("current")
            current = current if isinstance(current, Mapping) else {}
            chain_state = str(
                observed.get("chain_last_state")
                or observed.get("last_state")
                or current.get("last_state")
                or chain_state
            ).strip().lower()
            latest = observed.get("latest_failure")
            latest = latest if isinstance(latest, Mapping) else {}
            metadata = latest.get("metadata")
            metadata = metadata if isinstance(metadata, Mapping) else {}
            failure_kind = str(
                latest.get("kind") or observed.get("failure_kind") or ""
            ).strip().lower()
            failure_phase = str(
                metadata.get("phase")
                or metadata.get("failure_step")
                or observed.get("current_phase")
                or observed.get("target_stage")
                or ""
            ).strip().lower()
    pr_states = {"awaiting_pr_merge", "pr_pending", "ci_pending", "ci_failed"}
    pr_phases = {"pr", "pull_request", "merge", "ci", "publication", "publish"}
    pr_stage_known = (
        chain_state in pr_states
        or failure_phase in pr_phases
        or failure_kind.startswith(("pr_", "ci_", "publication_"))
    )
    non_pr_failure_known = bool(failure_kind or failure_phase) and not pr_stage_known
    current_stage_known = pr_stage_known or non_pr_failure_known
    applies = pr_stage_known or not non_pr_failure_known
    return {
        "applies": applies,
        "chain_state": chain_state,
        "failure_kind": failure_kind,
        "failure_phase": failure_phase,
        "reason": (
            "current workflow phase is unavailable, so external guards remain fail-closed"
            if not current_stage_known
            else "external PR/CI state is the operative workflow gate"
            if applies
            else "external PR/CI state is corroborating context for the active non-PR blocker"
        ),
    }


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
    quality_resolution_commit_custody: dict[str, Any] = {}
    for ref in refs:
        if not isinstance(ref, Mapping):
            raise ValueError("observation reference is invalid")
        encoded = _verified_reference_bytes(ref)
        kind = str(ref.get("kind") or "")
        observed = _bounded_observation(kind, encoded)
        if kind == "repair_goal" and isinstance(observed, Mapping):
            last_evaluation = observed.get("last_evaluation")
            last_evaluation = (
                last_evaluation if isinstance(last_evaluation, Mapping) else {}
            )
            commit_custody = last_evaluation.get(
                "quality_resolution_commit_custody"
            )
            if isinstance(commit_custody, Mapping):
                quality_resolution_commit_custody = {
                    key: commit_custody.get(key)
                    for key in ("verified", "required_commits", "missing_commits")
                }
        observations.append(
            {
                "kind": kind,
                "path": str(ref.get("path") or ""),
                "sha256": str(ref.get("sha256") or ""),
                "size_bytes": int(ref.get("size_bytes") or 0),
                "observed": observed,
            }
        )
    required_receipt = _common_required_output("l2_repair_system")
    required_receipt["safe_repair_target_by_action"]["repair_source"] = [
        "arnold_source"
    ]
    required_receipt["handoff_allowed_mutations_by_action"]["repair_source"] = [
        "arnold_source:arnold_pipelines/megaplan/cloud/<bounded component>",
        "arnold_source:tests/cloud/<bounded component>",
    ]
    required_receipt["l2_source_boundary"] = (
        "repair_source may name only normalized repo-relative Arnold repair-system "
        "components under arnold_pipelines/megaplan/cloud or tests/cloud. Target "
        "application files remain target_workspace work owned by ordinary L1 repair."
    )
    # Replace the illustrative placeholder with the one current immutable
    # envelope identity. Prior receipts are summarized above without their old
    # digests so the model cannot accidentally bind its response to stale custody.
    required_receipt["context_digest"] = context["context_digest"]
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
    missing_quality_commits = quality_resolution_commit_custody.get(
        "missing_commits"
    ) not in (None, "", [], "[]")
    external_guard_applicability = _external_guard_applicability(observations)
    external_guard_blocks = (
        external_guard_applicability["applies"]
        and external_guard_status != "clear"
    )
    if external_guard_blocks or missing_quality_commits:
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
                "A failed or pending PR/CI check forbids recover_state only when the "
                "current chain/failure phase makes that external guard operative. When a "
                "non-PR blocker is active, PR state is corroborating context and must not "
                "displace the actual failure. Never hand-advance the chain."
            ),
            "external_guard_applicability": external_guard_applicability,
            "quality_resolution_commit_custody": quality_resolution_commit_custody,
            "quality_commit_policy": (
                "Missing durable quality-resolution commits forbid recover_state and "
                "chain-state synchronization. Replan to ordinary L1 so the bounded "
                "target/source repair can be integrated; never discard commit custody."
            ),
            "observations": observations,
        }
    )
    encoded_bundle = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded_bundle) > MAX_OBSERVATION_BUNDLE_BYTES:
        raise ValueError("brokered meta-repair observations exceed 48 KiB")
    return bundle


def build_repair_observation_bundle(context_path: str | Path) -> dict[str, Any]:
    """Broker one bounded L1 view when the host cannot enforce read-only tools."""

    context = _load_bounded_json(
        context_path,
        max_bytes=MAX_CONTEXT_BYTES,
        label="repair investigation context",
    )
    if context.get("schema_version") != REPAIR_INVESTIGATION_CONTEXT_SCHEMA:
        raise ValueError("repair investigation context schema is invalid")
    digest = str(context.get("context_digest") or "")
    recomputed = _digest({key: value for key, value in context.items() if key != "context_digest"})
    if not digest or digest != recomputed:
        raise ValueError("repair investigation context digest disagrees")

    observations: list[dict[str, Any]] = []
    for source in context.get("evidence_sources") or []:
        if not isinstance(source, Mapping) or source.get("kind") not in EVIDENCE_SOURCE_KINDS:
            raise ValueError("repair investigation evidence source is invalid")
        observations.append(
            {
                "kind": source.get("kind"),
                "path": str(source.get("path") or ""),
                "authority": source.get("authority"),
                "observed": _bound_observation_value(source.get("observed")),
            }
        )

    analysis_keys = (
        "exact_error",
        "frozen_checkpoint",
        "current",
        "current_phase_result",
        "custody_contradictions",
        "custody_status",
        "durable_quality_block",
        "goal_continuity",
        "historical_failure_recovery",
        "intended_recovery",
        "l2_replan_authorization",
        "prior_repairs",
        "recovery_contract",
        "repair_outcome",
        "request",
        "safe_repair_boundaries",
    )
    required_receipt = context.get("required_investigator_output")
    required_receipt = dict(required_receipt) if isinstance(required_receipt, Mapping) else {}
    required_receipt["context_digest"] = digest
    external_guard_applicability = _external_guard_applicability(observations)
    bundle = redact_payload(
        {
            "schema_version": REPAIR_OBSERVATION_BUNDLE_SCHEMA,
            "context_digest": digest,
            "session": context.get("session"),
            "goal_id": context.get("goal_id"),
            "target_kind": context.get("target_kind"),
            "access_verified": True,
            "analysis_context": {
                key: _bound_observation_value(context.get(key))
                for key in analysis_keys
                if key in context
            },
            "external_guard_policy": (
                "A failed or pending PR/CI check forbids recover_state only when the "
                "current chain/failure phase makes that external guard operative. When a "
                "non-PR blocker is active, PR state is corroborating context and must not "
                "displace the actual failure. Never hand-advance the chain."
            ),
            "external_guard_applicability": external_guard_applicability,
            "required_receipt_shape": required_receipt,
            "observations": observations,
        }
    )
    encoded_bundle = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded_bundle) > MAX_OBSERVATION_BUNDLE_BYTES:
        raise ValueError("brokered repair observations exceed 48 KiB")
    return bundle


def validate_investigator_receipt(
    value: Mapping[str, Any], *, expected_context_digest: str,
    observation_bundle: Mapping[str, Any] | None = None,
    investigation_context: Mapping[str, Any] | None = None,
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
    if action == "preserve_live" and value.get("preserve_live") is not True:
        raise ValueError("preserve_live action requires an explicit live-worker receipt")
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
    _validate_l2_source_handoff(
        value,
        action=action,
        target_kind=target_kind,
        allowed_mutations=allowed_mutations,
    )
    if isinstance(investigation_context, Mapping):
        if investigation_context.get("context_digest") != expected_context_digest:
            raise ValueError("investigator context digest disagrees")
        _validate_l1_target_handoff(
            value,
            action=action,
            target_kind=target_kind,
            allowed_mutations=allowed_mutations,
            investigation_context=investigation_context,
        )
        quality_block = investigation_context.get("durable_quality_block")
        if (
            isinstance(quality_block, Mapping)
            and quality_block.get("active") is True
            and action == "recover_state"
        ):
            repair_evidence = quality_block.get("repair_evidence")
            repair_evidence = (
                repair_evidence if isinstance(repair_evidence, Mapping) else {}
            )
            current = investigation_context.get("current")
            current = current if isinstance(current, Mapping) else {}
            current_head = str(current.get("workspace_head") or "").strip().lower()
            evidence_head = str(
                repair_evidence.get("workspace_head") or ""
            ).strip().lower()
            if not (
                quality_block.get("recover_state_allowed") is True
                and repair_evidence.get("verified") is True
                and len(current_head) == 40
                and all(char in "0123456789abcdef" for char in current_head)
                and evidence_head == current_head
                and str(repair_evidence.get("dev_fix_sha") or "").strip().lower()
                == current_head
                and repair_evidence.get("target_kind") == "target_workspace"
                and str(repair_evidence.get("target_scope") or "").strip()
                and repair_evidence.get("validation_present") is True
            ):
                raise ValueError(
                    "state recovery cannot replay a durable review-quality block before its "
                    "bounded rework target is repaired"
                )
        current = investigation_context.get("current")
        current = current if isinstance(current, Mapping) else {}
        commit_custody = current.get("quality_resolution_commit_custody")
        commit_custody = commit_custody if isinstance(commit_custody, Mapping) else {}
        if (
            action == "recover_state"
            and commit_custody.get("verified") is not True
            and commit_custody.get("missing_commits")
        ):
            raise ValueError(
                "state recovery cannot discard missing durable quality-resolution commits"
            )
    if isinstance(observation_bundle, Mapping):
        if observation_bundle.get("context_digest") != expected_context_digest:
            raise ValueError("investigator observation bundle digest disagrees")
        external_guard = {}
        external_guard_applicability = observation_bundle.get(
            "external_guard_applicability"
        )
        external_guard_applicability = (
            external_guard_applicability
            if isinstance(external_guard_applicability, Mapping)
            else {"applies": True}
        )
        live_worker_observed = False
        bundle_commit_custody = observation_bundle.get(
            "quality_resolution_commit_custody"
        )
        bundle_commit_custody = (
            bundle_commit_custody
            if isinstance(bundle_commit_custody, Mapping)
            else {}
        )
        bundle_missing = bundle_commit_custody.get("missing_commits")
        missing_quality_commits = (
            bundle_commit_custody.get("verified") is not True
            and bundle_missing not in (None, "", [], "[]")
        )
        for item in observation_bundle.get("observations") or []:
            if not isinstance(item, Mapping):
                continue
            observed = item.get("observed")
            observed = observed if isinstance(observed, Mapping) else {}
            if item.get("kind") == "external_state":
                if observed:
                    external_guard = (
                        observed.get("external_guard")
                        if isinstance(observed.get("external_guard"), Mapping)
                        else {}
                    )
            if item.get("kind") == "live_process" and any(
                observed.get(field) is True
                for field in ("live", "pid_live", "session_live", "canonical_runner_live")
            ):
                live_worker_observed = True
            if item.get("kind") == "repair_data":
                target_observation = observed.get("target")
                target_observation = (
                    target_observation
                    if isinstance(target_observation, Mapping)
                    else {}
                )
                heartbeat = target_observation.get("active_step_heartbeat")
                heartbeat = heartbeat if isinstance(heartbeat, Mapping) else {}
                tmux_process = target_observation.get("tmux_process")
                tmux_process = (
                    tmux_process if isinstance(tmux_process, Mapping) else {}
                )
                if (
                    heartbeat.get("active") is True
                    and heartbeat.get("pid_live") is True
                ) or (
                    tmux_process.get("live_status") == "alive"
                    and (
                        tmux_process.get("pid_live") is True
                        or tmux_process.get("session_live") is True
                    )
                ):
                    live_worker_observed = True
            if item.get("kind") == "repair_goal":
                last_evaluation = observed.get("last_evaluation")
                last_evaluation = (
                    last_evaluation if isinstance(last_evaluation, Mapping) else {}
                )
                commit_custody = last_evaluation.get(
                    "quality_resolution_commit_custody"
                )
                commit_custody = (
                    commit_custody if isinstance(commit_custody, Mapping) else {}
                )
                missing = commit_custody.get("missing_commits")
                if (
                    commit_custody.get("verified") is not True
                    and missing not in (None, "", [], "[]")
                ):
                    missing_quality_commits = True
        if (
            external_guard_applicability.get("applies") is not False
            and external_guard.get("status") != "clear"
            and action == "recover_state"
        ):
            raise ValueError(
                "state recovery cannot bypass a failing or pending external PR/CI guard"
            )
        if missing_quality_commits and action == "recover_state":
            raise ValueError(
                "state recovery cannot discard missing durable quality-resolution commits"
            )
        if action == "preserve_live" and not live_worker_observed:
            raise ValueError(
                "preserve_live cannot strand an active goal without verified live-worker evidence"
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
        validated = validate_investigator_receipt(
            receipt,
            expected_context_digest=digest,
            investigation_context=context,
        )
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
    actual_failure = validated.get("actual_failure")
    actual_failure = actual_failure if isinstance(actual_failure, Mapping) else {}
    return {
        "required": True,
        "status": "accepted",
        "target_kind": validated.get("target_kind"),
        "context_path": str(context_path),
        "receipt_path": str(receipt_path),
        "context_digest": digest,
        "receipt_digest": validated.get("receipt_digest"),
        "actual_failure_classification": actual_failure.get("classification"),
        "actual_failure": {
            "classification": _text(actual_failure.get("classification"), 100),
            "error": _text(actual_failure.get("error"), 1000),
            "mechanism": _text(actual_failure.get("mechanism"), 2000),
        },
        "evidence_source_kinds": sorted(
            {str(item.get("kind")) for item in validated.get("evidence_sources") or [] if isinstance(item, Mapping)}
        ),
        "custody_status": validated.get("custody_status"),
        "contradiction_count": len(validated.get("custody_contradictions") or []),
        "recommended_action": validated.get("recommended_action"),
        "safe_repair_target": validated.get("safe_repair_target"),
        "intended_recovery": validated.get("intended_recovery"),
        "four_axis": validated.get("four_axis"),
        "access_receipt_path": str(investigation.get("access_receipt_path") or ""),
    }


def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    # Builders enforce their byte ceilings against canonical compact JSON.
    # Persist that same representation; pretty-printing after the check can
    # otherwise turn an accepted 64 KiB context into an oversized transport.
    temporary.write_text(
        json.dumps(dict(value), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
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
    build.add_argument("--l2-replan-epoch", default="0")
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
    observe = sub.add_parser("observe")
    observe.add_argument("--context", required=True)
    observe.add_argument("--output", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--receipt", required=True)
    validate.add_argument("--context-digest", required=True)
    validate.add_argument("--observation", default="")
    validate.add_argument("--context", default="")
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
            l2_replan_epoch=args.l2_replan_epoch,
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
            resident_delegation=provenance_from_environment(strict=True),
        )
        _atomic_write(Path(args.output), value)
    elif args.command == "observe-meta":
        value = build_meta_observation_bundle(args.context)
        _atomic_write(Path(args.output), value)
    elif args.command == "observe":
        value = build_repair_observation_bundle(args.context)
        _atomic_write(Path(args.output), value)
    else:
        value = validate_investigator_receipt(
            _load_bounded_json(
                args.receipt,
                max_bytes=MAX_RECEIPT_BYTES,
                label="investigator receipt",
            ),
            expected_context_digest=args.context_digest,
            observation_bundle=(
                _load_bounded_json(
                    args.observation,
                    # The builder bounds the compact JSON payload to 48 KiB,
                    # while its durable pretty-printed representation can be
                    # larger. Keep the transport ceiling at the shared 64 KiB
                    # fail-closed envelope.
                    max_bytes=MAX_CONTEXT_BYTES,
                    label="investigator observation bundle",
                )
                if args.observation
                else None
            ),
            investigation_context=(
                _load_bounded_json(
                    args.context,
                    max_bytes=MAX_CONTEXT_BYTES,
                    label="repair investigation context",
                )
                if args.context
                else None
            ),
        )
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "MAX_CONTEXT_BYTES",
    "MAX_RECEIPT_BYTES",
    "META_REPAIR_INVESTIGATION_ENVELOPE_SCHEMA",
    "REPAIR_INVESTIGATION_CONTEXT_SCHEMA",
    "REPAIR_INVESTIGATOR_RECEIPT_SCHEMA",
    "EVIDENCE_SOURCE_KINDS",
    "INVESTIGATION_TARGET_KINDS",
    "build_meta_investigation_context",
    "build_meta_observation_bundle",
    "build_repair_observation_bundle",
    "build_investigation_context",
    "summarize_investigation_artifacts",
    "validate_meta_investigation_context",
    "validate_investigator_receipt",
]
