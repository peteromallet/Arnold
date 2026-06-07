"""Parallel Hermes review runner.

The preloaded-template-ID convention is the preferred way to get structured
output from focused review agents: write the exact slot shape first, then have
each agent fill that file instead of inventing IDs in free-form JSON.

This module intentionally mirrors `megaplan.orchestration.parallel_critique` so the two phase
runners remain easy to compare and later extract into a shared utility.
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import Any

from arnold.pipelines.megaplan._core import WorkerUnit, WorkerUnitResult, load_flag_registry, read_json, schemas_root, scatter_worker_units
from arnold.pipelines.megaplan.model_seam import ModelTier
from arnold.pipelines.megaplan.prompts.review import (
    _filtered_prior_flags,
    _write_criteria_verdict_review_template,
    _write_single_check_review_template,
    parallel_criteria_review_prompt,
    single_check_review_prompt,
)
from arnold.pipelines.megaplan.types import AgentMode, CliError, PlanState
from arnold.pipelines.megaplan.workers import STEP_SCHEMA_FILENAMES, WorkerResult

from arnold.pipelines.megaplan.runtime.key_pool import (
    resolve_model as _resolve_model,
)


def _clean_review_check_payload(payload: dict[str, Any]) -> None:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return
    for check in checks:
        if not isinstance(check, dict):
            continue
        check.pop("guidance", None)
        check.pop("prior_findings", None)


def _merge_unique(groups: list[list[str]]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            if item not in seen:
                seen.add(item)
                merged.append(item)
    return merged


def _review_worker_db_path(plan_dir: Path, identifier: str) -> Path:
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", identifier)
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return plan_dir / ".hermes_state" / f"state_{sanitized or 'default'}.db"


def _review_reasoning_config(resolved_model: str | None) -> dict[str, bool] | None:
    model_lower = (resolved_model or "").lower()
    reasoning_families = ("qwen/qwen3", "deepseek/deepseek-r1")
    if any(model_lower.startswith(prefix) for prefix in reasoning_families):
        return {"enabled": False}
    return None


def _review_agent_mode(model: str | None, resolved_model: str | None) -> AgentMode:
    return AgentMode(
        agent="hermes",
        mode="persistent",
        refreshed=False,
        model=model,
        resolved_model=resolved_model,
    )


def _review_worker_options(
    *,
    output_path: Path,
    session_db_path: Path,
    resolved_model: str | None,
) -> dict[str, object]:
    options: dict[str, object] = {
        "output_path": str(output_path),
        "template_path": str(output_path),
        "session_db_path": str(session_db_path),
        "max_tokens": 32768,
    }
    if resolved_model:
        options["resolved_model"] = resolved_model
    reasoning_config = _review_reasoning_config(resolved_model)
    if reasoning_config is not None:
        options["reasoning_config"] = reasoning_config
    return options


def _parse_parallel_review_result(
    index: int,
    item: WorkerUnitResult,
    unit: WorkerUnit,
) -> tuple[int, dict[str, Any], list[str], list[str], float, int, int, int]:
    del index
    payload = item.payload
    if not isinstance(payload, dict):
        raise CliError("worker_parse_error", "Review worker payload must be a dict")
    _clean_review_check_payload(payload)
    payload_checks = payload.get("checks")
    if not isinstance(payload_checks, list) or len(payload_checks) != 1 or not isinstance(payload_checks[0], dict):
        check_id = unit.extra.get("check_id", "?")
        raise CliError(
            "worker_parse_error",
            f"Parallel review output for check '{check_id}' did not contain exactly one check",
            extra={"raw_output": item.raw_output},
        )
    verified = payload.get("verified_flag_ids", [])
    disputed = payload.get("disputed_flag_ids", [])
    return (
        int(unit.extra.get("index", 0) or 0),
        payload_checks[0],
        verified if isinstance(verified, list) else [],
        disputed if isinstance(disputed, list) else [],
        item.cost_usd,
        item.prompt_tokens,
        item.completion_tokens,
        item.total_tokens,
    )


def _parse_parallel_review_side_result(
    index: int,
    item: WorkerUnitResult,
    unit: WorkerUnit,
) -> tuple[dict[str, Any], float, int, int, int]:
    del index, unit
    payload = item.payload
    if not isinstance(payload, dict):
        raise CliError("worker_parse_error", "Review criteria payload must be a dict")
    return (
        payload,
        item.cost_usd,
        item.prompt_tokens,
        item.completion_tokens,
        item.total_tokens,
    )


def run_parallel_review(
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    model: str | None,
    checks: tuple[Any, ...],
    pre_check_flags: list[dict[str, Any]],
    max_concurrent: int | None = None,
) -> WorkerResult:
    started = time.monotonic()
    read_json(schemas_root(root) / STEP_SCHEMA_FILENAMES["review"])
    prior_flags = load_flag_registry(plan_dir).get("flags", [])
    resolved_model, _agent_kwargs = _resolve_model(model)
    resolved = _review_agent_mode(model, resolved_model)
    schema = read_json(schemas_root(root) / STEP_SCHEMA_FILENAMES["review"])

    units: list[WorkerUnit] = []
    for index, check in enumerate(checks):
        check_id = check["id"] if isinstance(check, dict) else getattr(check, "id")
        output_path = _write_single_check_review_template(plan_dir, state, check, f"review_check_{check_id}.json")
        prompt = single_check_review_prompt(
            state,
            plan_dir,
            root,
            check,
            output_path,
            pre_check_flags,
            _filtered_prior_flags(check, prior_flags),
        )
        units.append(
            WorkerUnit(
                step="review",
                resolved=resolved,
                prompt=prompt,
                output_path=output_path,
                read_only=True,
                validation_step="review",
                schema=schema,
                model=resolved_model,
                tier=ModelTier.ENFORCED,
                extra={
                    "index": index,
                    "check_id": check_id,
                    "ledger_step_label": check_id,
                    "worker_options": _review_worker_options(
                        output_path=output_path,
                        session_db_path=_review_worker_db_path(plan_dir, f"review_{check_id}"),
                        resolved_model=resolved_model,
                    ),
                },
            )
        )

    criteria_output_path = _write_criteria_verdict_review_template(plan_dir, state, "review_criteria_verdict.json")
    criteria_unit = WorkerUnit(
        step="review",
        resolved=resolved,
        prompt=parallel_criteria_review_prompt(state, plan_dir, root, criteria_output_path),
        output_path=criteria_output_path,
        read_only=True,
        validation_step="review",
        schema=schema,
        model=resolved_model,
        tier=ModelTier.ENFORCED,
        extra={
            "ledger_step_label": "criteria_verdict",
            "worker_options": _review_worker_options(
                output_path=criteria_output_path,
                session_db_path=_review_worker_db_path(plan_dir, "review_criteria_verdict"),
                resolved_model=resolved_model,
            ),
        },
    )

    args = argparse.Namespace(agent=None, hermes=None, phase_model=[], ephemeral=False, fresh=False, persist=False)
    sr = scatter_worker_units(
        units=units,
        side_units=[criteria_unit],
        state=state,
        plan_dir=plan_dir,
        root=root,
        args=args,
        parse_result=_parse_parallel_review_result,
        parse_side_result=_parse_parallel_review_side_result,
        max_concurrent=max_concurrent,
    )

    criteria_payload, *_ = sr.side_results[0]
    if criteria_payload is None:
        raise CliError("worker_error", "Parallel review did not return a criteria verdict payload")

    ordered_checks: list[dict[str, Any]] = []
    verified_groups: list[list[str]] = []
    disputed_groups: list[list[str]] = []
    for item in sr.ordered_results:
        _index, check_payload, verified_ids, disputed_ids, *_metrics = item
        ordered_checks.append(check_payload)
        verified_groups.append(verified_ids)
        disputed_groups.append(disputed_ids)
    disputed_flag_ids = _merge_unique(disputed_groups)
    disputed_set = set(disputed_flag_ids)
    verified_flag_ids = [
        flag_id for flag_id in _merge_unique(verified_groups) if flag_id not in disputed_set
    ]

    return WorkerResult(
        payload={
            "checks": ordered_checks,
            "verified_flag_ids": verified_flag_ids,
            "disputed_flag_ids": disputed_flag_ids,
            "criteria_payload": criteria_payload,
        },
        raw_output="parallel",
        duration_ms=int((time.monotonic() - started) * 1000),
        cost_usd=sr.total_cost,
        session_id=None,
        prompt_tokens=sr.total_prompt_tokens,
        completion_tokens=sr.total_completion_tokens,
        total_tokens=sr.total_tokens,
    )
