"""Bounded authoritative context and receipts for two-stage automatic repair."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan.cloud.repair_goal import capture_checkpoint, utc_now


REPAIR_INVESTIGATION_CONTEXT_SCHEMA = "arnold-repair-investigation-context-v1"
REPAIR_INVESTIGATOR_RECEIPT_SCHEMA = "arnold-repair-investigator-receipt-v1"
MAX_CONTEXT_BYTES = 64 * 1024


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
            for item in (value.get("dev_summary") or report.get("what_tried") or [])[-8:]
        ],
        "validation": [_text(item, 1000) for item in (report.get("validation") or [])[-8:]],
        "pushed_commit": _text(value.get("dev_fix_sha") or report.get("pushed_commit"), 100),
        "outcome": _text(value.get("outcome") or value.get("status"), 300),
    }


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
    context: dict[str, Any] = {
        "schema_version": REPAIR_INVESTIGATION_CONTEXT_SCHEMA,
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
        "recovery_contract": dict(goal.get("recovery_contract"))
        if isinstance(goal.get("recovery_contract"), Mapping)
        else {},
        "current": current,
        "exact_error": current.get("latest_failure")
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
        "required_investigator_output": {
            "schema_version": REPAIR_INVESTIGATOR_RECEIPT_SCHEMA,
            "context_digest": "<exact context digest>",
            "real_blocker": "<mechanism, not a generic label>",
            "evidence_paths": ["<authoritative path>"],
            "prior_repairs_considered": ["<attempt id or receipt>"],
            "preserve_live": False,
            "recommended_action": "preserve_live|repair_source|repair_target|recover_state|replan",
            "guard_weakening_risk": "none|identified",
        },
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


def validate_investigator_receipt(
    value: Mapping[str, Any], *, expected_context_digest: str
) -> dict[str, Any]:
    if value.get("schema_version") != REPAIR_INVESTIGATOR_RECEIPT_SCHEMA:
        raise ValueError("investigator receipt schema is invalid")
    if value.get("context_digest") != expected_context_digest:
        raise ValueError("investigator receipt context digest disagrees")
    for field in ("real_blocker", "recommended_action", "guard_weakening_risk"):
        if not str(value.get(field) or "").strip():
            raise ValueError(f"investigator receipt missing {field}")
    if value.get("recommended_action") not in {
        "preserve_live",
        "repair_source",
        "repair_target",
        "recover_state",
        "replan",
    }:
        raise ValueError("investigator receipt recommended_action is invalid")
    if not isinstance(value.get("preserve_live"), bool):
        raise ValueError("investigator receipt preserve_live must be boolean")
    for field in ("evidence_paths", "prior_repairs_considered"):
        items = value.get(field)
        if not isinstance(items, list) or not items or not all(str(item).strip() for item in items):
            raise ValueError(f"investigator receipt {field} is invalid")
    return dict(value)


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
    "build_investigation_context",
    "validate_investigator_receipt",
]
