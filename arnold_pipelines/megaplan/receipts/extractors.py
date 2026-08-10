"""Mechanical phase-metric extractors for step receipts."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.prep_payload import suggested_approach_lines
from arnold_pipelines.megaplan.receipts.schema import registered_plan_artifact_path


def _safe(fn):
    def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            return {"_extractor_error": str(exc)}

    return wrapper


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text_from_payload(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict or string")
    for key in ("plan", "content", "text", "output"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return json.dumps(payload, sort_keys=True)


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


@_safe
def plan_metrics(payload: dict[str, Any] | str, artifact_path: Path | None = None) -> dict[str, Any]:
    del artifact_path
    text = _text_from_payload(payload)
    tasks = re.findall(r"(?im)^\s*(?:[-*]\s*)?(?:T\d+|Task\s+\d+|##+\s+Step\s+\d+)\b", text)
    files = sorted(set(re.findall(r"\b[\w./-]+\.[A-Za-z0-9]{1,8}\b", text)))
    success = re.findall(r"(?im)success criteria|criterion|criteria", text)
    must = len(re.findall(r"(?i)\bmust\b", text))
    info = len(re.findall(r"(?i)\binfo\b", text))
    warnings = len(re.findall(r"(?i)\bwarning\b|structure_warning", text))
    return {
        "step_count": len(re.findall(r"(?im)^##+\s+Step\s+\d+", text)),
        "task_count": len(tasks),
        "files_referenced": files,
        "oos_file_count": len(re.findall(r"(?i)\bout[- ]of[- ]scope\b|\boos\b", text)),
        "plan_chars": len(text),
        "plan_words": len(re.findall(r"\b\w+\b", text)),
        "success_criteria_count": len(success),
        "must_vs_info_ratio": (must / info) if info else float(must),
        "structure_warnings_count": warnings,
    }


@_safe
def critique_metrics(payload: dict[str, Any], artifact_path: Path | None = None) -> dict[str, Any]:
    del artifact_path
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    checks = _as_list(payload.get("checks"))
    findings_per_check: dict[str, int] = {}
    severities: Counter[str] = Counter()
    clean = 0
    flagged = 0
    for index, check in enumerate(checks, start=1):
        if not isinstance(check, dict):
            continue
        name = str(check.get("id") or check.get("name") or check.get("check") or index)
        findings = _as_list(check.get("findings") or check.get("flags"))
        if not findings and isinstance(check.get("finding"), dict):
            findings = [check["finding"]]
        findings_per_check[name] = len(findings)
        if findings:
            flagged += 1
        else:
            clean += 1
        for finding in findings:
            if isinstance(finding, dict):
                severities[str(finding.get("severity") or "unknown")] += 1
    total = clean + flagged
    return {
        "findings_per_check": findings_per_check,
        "severity_distribution": dict(severities),
        "clean_checks_count": clean,
        "flagged_checks_count": flagged,
        "rubber_stamp_ratio": (clean / total) if total else 0.0,
    }


@_safe
def gate_metrics(payload: dict[str, Any], artifact_path: Path | None = None) -> dict[str, Any]:
    del artifact_path
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    resolved = _as_list(payload.get("blocking_flags_resolved") or payload.get("resolved_flags"))
    remaining = _as_list(payload.get("blocking_flags_remaining") or payload.get("blocking_flags"))
    return {
        "recommendation": payload.get("recommendation"),
        "blocking_flags_resolved": len(resolved),
        "blocking_flags_remaining": len(remaining),
        "override_forced": bool(payload.get("override_forced") or payload.get("forced")),
    }


@_safe
def finalize_metrics(payload: dict[str, Any], artifact_path: Path | None = None) -> dict[str, Any]:
    del artifact_path
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    tasks = _as_list(payload.get("tasks"))
    sense_checks = _as_list(payload.get("sense_checks"))
    evidence_count = 0
    for task in tasks:
        if isinstance(task, dict):
            evidence_count += len(_as_list(task.get("evidence_files")))
    return {
        "tasks_count": len(tasks),
        "sense_checks_count": len(sense_checks),
        "per_task_evidence_file_count": evidence_count,
    }


@_safe
def execute_metrics(aggregate_payload: dict[str, Any], drift_report: Any = None) -> dict[str, Any]:
    if not isinstance(aggregate_payload, dict):
        raise TypeError("aggregate_payload must be a dict")
    task_updates = _as_list(aggregate_payload.get("task_updates") or aggregate_payload.get("tasks"))
    per_task_files = 0
    commands = 0
    for task in task_updates:
        if isinstance(task, dict):
            per_task_files += len(_as_list(task.get("files_changed")))
            commands += len(_as_list(task.get("commands_run")))
    advisory = _as_list(aggregate_payload.get("advisory_issues"))
    blocking = _as_list(aggregate_payload.get("blocking_issues") or aggregate_payload.get("blocking_reasons"))
    claimed = set(aggregate_payload.get("files_changed") or [])
    files_added = set(getattr(drift_report, "files_added", []) or [])
    files_missing = set(getattr(drift_report, "files_missing", []) or [])
    files_in_diff = set(aggregate_payload.get("files_in_diff") or [])
    if not files_in_diff and drift_report is not None:
        files_in_diff = (claimed - files_missing) | files_added
    return {
        "files_claimed": len(claimed),
        "files_in_diff": len(files_in_diff),
        "scope_drift_files_added": len(getattr(drift_report, "files_added", []) or []),
        "scope_drift_files_missing": len(getattr(drift_report, "files_missing", []) or []),
        "loc_added": int(getattr(drift_report, "loc_added", 0) or 0),
        "loc_removed": int(getattr(drift_report, "loc_removed", 0) or 0),
        "loc_added_outside_claimed": int(getattr(drift_report, "loc_added_outside_claimed", 0) or 0),
        "commands_run_count": commands,
        "advisory_issues_count": len(advisory),
        "blocking_issues_count": len(blocking),
        "per_task_files_claimed_count": per_task_files,
    }


@_safe
def review_metrics(payload: dict[str, Any], artifact_path: Path | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    task_verdicts = _as_list(payload.get("task_verdicts"))
    sense_verdicts = _as_list(payload.get("sense_check_verdicts"))
    finalize_payload = None
    if artifact_path is not None:
        finalize_payload = _read_json_if_exists(artifact_path.parent / "finalize.json")
    finalize_tasks = _as_list((finalize_payload or {}).get("tasks"))
    finalize_sense_checks = _as_list((finalize_payload or {}).get("sense_checks"))
    criteria = _as_list(payload.get("criteria") or payload.get("success_criteria"))
    missing_evidence = 0
    rework = len(_as_list(payload.get("rework_items")))
    passed = 0
    deferred = 0
    for item in task_verdicts:
        if isinstance(item, dict):
            missing_evidence += len(_as_list(item.get("missing_evidence")))
            rework += len(_as_list(item.get("rework_items")))
    for criterion in criteria:
        if not isinstance(criterion, dict):
            continue
        verdict = str(criterion.get("verdict") or criterion.get("status") or "").lower()
        if verdict in {"pass", "passed", "satisfied"}:
            passed += 1
        if verdict in {"deferred", "skipped"}:
            deferred += 1
    return {
        "review_verdict": payload.get("review_verdict") or payload.get("verdict"),
        "task_verdicts_count": len(task_verdicts),
        "total_tasks": int(payload.get("total_tasks") or len(finalize_tasks) or len(task_verdicts)),
        "sense_check_verdicts_count": len(sense_verdicts),
        "total_sense_checks": int(payload.get("total_sense_checks") or len(finalize_sense_checks) or len(sense_verdicts)),
        "missing_evidence_count": missing_evidence,
        "rework_items_count": rework,
        "criteria_pass_count": passed,
        "criteria_deferred_count": deferred,
    }


@_safe
def prep_metrics(
    payload: dict[str, Any],
    metrics_payload: dict[str, Any] | None = None,
    resolver_trace: dict[str, Any] | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    del artifact_path
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    metrics_payload = metrics_payload if isinstance(metrics_payload, dict) else {}
    resolver_trace = resolver_trace if isinstance(resolver_trace, dict) else {}
    per_unit = _as_list(metrics_payload.get("per_unit"))
    files = [
        str(item).strip()
        for item in _as_list(metrics_payload.get("files"))
        if str(item).strip()
    ]
    code_refs = [
        str(item).strip()
        for item in _as_list(metrics_payload.get("code_refs"))
        if str(item).strip()
    ]
    missed_units = [
        str(item).strip()
        for item in _as_list(metrics_payload.get("missed_units"))
        if str(item).strip()
    ]
    status_counts = {
        "complete": int(metrics_payload.get("completed_count", 0) or 0),
        "partial": int(metrics_payload.get("partial_count", 0) or 0),
        "timed_out": int(metrics_payload.get("timed_out_count", 0) or 0),
        "error": int(metrics_payload.get("error_count", 0) or 0),
        "not_needed": sum(
            1
            for item in per_unit
            if isinstance(item, dict) and str(item.get("status") or "") == "not_needed"
        ),
    }
    area_count = int(metrics_payload.get("area_count", 0) or 0)
    fanout_count = int(metrics_payload.get("fanout_count", 0) or 0)
    return {
        "skip": bool(payload.get("skip", False)),
        "task_summary_present": bool(str(payload.get("task_summary") or "").strip()),
        "key_evidence_count": len(_as_list(payload.get("key_evidence"))),
        "relevant_code_count": len(_as_list(payload.get("relevant_code"))),
        "test_expectations_count": len(_as_list(payload.get("test_expectations"))),
        "constraints_count": len(_as_list(payload.get("constraints"))),
        "suggested_approach_present": bool(
            suggested_approach_lines(payload.get("suggested_approach"))
        ),
        "primary_criterion_present": bool(str(payload.get("primary_criterion") or "").strip()),
        "area_count": area_count,
        "fanout_count": fanout_count,
        "area_cap": fanout_count,
        "cap_applied": area_count > fanout_count,
        "status_counts": status_counts,
        "completed_count": status_counts["complete"],
        "partial_count": status_counts["partial"],
        "timed_out_count": status_counts["timed_out"],
        "error_count": status_counts["error"],
        "missed_units": missed_units,
        "missed_units_count": len(missed_units),
        "total_cost_usd": float(metrics_payload.get("total_cost_usd", 0.0) or 0.0),
        "prompt_tokens": int(metrics_payload.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(metrics_payload.get("completion_tokens", 0) or 0),
        "total_tokens": int(metrics_payload.get("total_tokens", 0) or 0),
        "elapsed_time_ms": int(metrics_payload.get("elapsed_time_ms", 0) or 0),
        "files": files,
        "files_count": len(files),
        "code_refs": code_refs,
        "code_refs_count": len(code_refs),
        "per_unit_count": len(per_unit),
        "per_unit_statuses": [
            str(item.get("status") or "")
            for item in per_unit
            if isinstance(item, dict) and str(item.get("status") or "")
        ],
        "gap_notes_count": len(_as_list(metrics_payload.get("gap_notes"))),
        "contradiction_notes_count": len(_as_list(metrics_payload.get("contradiction_notes"))),
        "overlap_groups_count": len(_as_list(metrics_payload.get("overlap_groups"))),
        "cross_reference_performed": bool(
            isinstance(metrics_payload.get("cross_reference"), dict)
            and metrics_payload["cross_reference"].get("performed")
        ),
        "cross_reference_missing_files_count": len(
            _as_list((metrics_payload.get("cross_reference") or {}).get("missing_files"))
        ),
        "model_resolution_trace": resolver_trace or metrics_payload.get("model_resolution_trace") or {},
        "critique_flags_count": int(metrics_payload.get("critique_flags_count", 0) or 0),
        "revise_cycles_count": int(metrics_payload.get("revise_cycles_count", 0) or 0),
        "execution_failure_categories": _as_list(metrics_payload.get("execution_failure_categories")),
        "human_override_count": int(metrics_payload.get("human_override_count", 0) or 0),
    }


def extract_for_phase(phase: str, *payloads: Any, artifact_path: Path | None = None, drift_report: Any = None) -> dict[str, Any]:
    if phase == "prep":
        metrics_payload = payloads[1] if len(payloads) > 1 else None
        resolver_trace = payloads[2] if len(payloads) > 2 else None
        return prep_metrics(
            payloads[0] if payloads else {},
            metrics_payload=metrics_payload,
            resolver_trace=resolver_trace,
            artifact_path=artifact_path,
        )
    if phase == "revise":
        return {}
    if phase == "plan":
        return plan_metrics(payloads[0] if payloads else {}, artifact_path=artifact_path)
    if phase == "critique":
        return critique_metrics(payloads[0] if payloads else {}, artifact_path=artifact_path)
    if phase == "gate":
        return gate_metrics(payloads[0] if payloads else {}, artifact_path=artifact_path)
    if phase == "finalize":
        return finalize_metrics(payloads[0] if payloads else {}, artifact_path=artifact_path)
    if phase == "execute":
        return execute_metrics(payloads[0] if payloads else {}, drift_report)
    if phase == "review":
        return review_metrics(payloads[0] if payloads else {}, artifact_path=artifact_path)
    return {}


def load_and_extract(plan_dir: Path, phase: str, iteration: int, *, drift_report: Any = None) -> dict[str, Any]:
    if phase == "prep":
        prep_path = plan_dir / "prep.json"
        payload = _read_json_if_exists(prep_path) or {}
        metrics_payload = _read_json_if_exists(plan_dir / "prep_metrics.json") or {}
        # cache-tolerant: receipts extractor reads a snapshot view.
        state_payload = _read_json_if_exists(plan_dir / "state.json") or {}
        resolver_trace = (
            state_payload.get("config", {}).get("prep_model_resolver_trace")
            if isinstance(state_payload.get("config"), dict)
            else None
        )
        return extract_for_phase(
            phase,
            payload,
            metrics_payload,
            resolver_trace,
            artifact_path=prep_path,
            drift_report=drift_report,
        )
    if phase == "revise":
        return {}
    paths = {
        "plan": registered_plan_artifact_path(plan_dir, iteration),
        "critique": plan_dir / f"critique_v{iteration}.json",
        "gate": plan_dir / f"gate_v{iteration}.json",
        "finalize": plan_dir / "finalize.json",
        "execute": plan_dir / "execution.json",
        "review": plan_dir / "review.json",
    }
    path = paths.get(phase)
    if path is None:
        return {}
    if phase == "plan":
        payload: Any = {"plan": path.read_text(encoding="utf-8")}
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    return extract_for_phase(phase, payload, artifact_path=path, drift_report=drift_report)
