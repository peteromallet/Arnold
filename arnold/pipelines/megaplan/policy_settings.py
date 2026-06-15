"""Reporting-only registry for Megaplan policy setting ownership.

This module does not introduce new defaults or change any runtime behavior.
It only explains the effective policy values by delegating to the existing
Megaplan defaults and resolver helpers that already own those decisions.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold.pipelines.megaplan.execute import _resolve_execute_approval_mode
from arnold.pipelines.megaplan.execute.batch import _resolve_max_tasks_per_batch
from arnold.pipelines.megaplan.orchestration.execution_evidence import (
    validate_execution_evidence,
)
from arnold.pipelines.megaplan.orchestration.iteration_pressure import (
    compute_iteration_pressure,
    has_mechanical_recurrence,
)
from arnold.pipelines.megaplan.orchestration.recovery_policy import RecoveryPolicy
from arnold.pipelines.megaplan._core import compute_global_batches, split_oversized_batches
from arnold.pipelines.megaplan.execute._binding.tier import select_batch_tier

__all__ = [
    "PolicySettingSpec",
    "SETTING_SPECS",
    "describe_effective_policy_settings",
]


ReportValue = dict[str, Any]


@dataclass(frozen=True)
class PolicySettingSpec:
    """One reporting-only Megaplan policy setting description."""

    key: str
    owner: str
    summary: str
    resolver_ref: str
    reporter: Callable[["_PolicyContext", "PolicySettingSpec"], ReportValue] = field(repr=False)


@dataclass(frozen=True)
class _PolicyContext:
    args: argparse.Namespace | None = None
    state: Mapping[str, Any] | None = None
    finalize_data: Mapping[str, Any] | None = None
    plan_dir: Path | None = None
    project_dir: Path | None = None

    @property
    def config(self) -> Mapping[str, Any]:
        raw = (self.state or {}).get("config", {})
        return raw if isinstance(raw, Mapping) else {}

    @property
    def meta(self) -> Mapping[str, Any]:
        raw = (self.state or {}).get("meta", {})
        return raw if isinstance(raw, Mapping) else {}


def _effective(spec: PolicySettingSpec, *, value: Any, source: str, notes: str = "") -> ReportValue:
    return {
        "key": spec.key,
        "owner": spec.owner,
        "summary": spec.summary,
        "resolver_ref": spec.resolver_ref,
        "status": "effective",
        "value": value,
        "source": source,
        "notes": notes,
    }


def _unset(spec: PolicySettingSpec, *, source: str, notes: str = "") -> ReportValue:
    return {
        "key": spec.key,
        "owner": spec.owner,
        "summary": spec.summary,
        "resolver_ref": spec.resolver_ref,
        "status": "unset",
        "value": None,
        "source": source,
        "notes": notes,
    }


def _unsupported(spec: PolicySettingSpec, *, source: str, notes: str) -> ReportValue:
    return {
        "key": spec.key,
        "owner": spec.owner,
        "summary": spec.summary,
        "resolver_ref": spec.resolver_ref,
        "status": "unsupported",
        "value": None,
        "source": source,
        "notes": notes,
    }


def _read_execute_stage_confirm_destructive_default() -> bool:
    execute_stage_path = Path(__file__).with_name("stages") / "execute.py"
    tree = ast.parse(execute_stage_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
            value_node = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value_node = node.value
        else:
            continue
        if not any(isinstance(target, ast.Name) and target.id == "_DEFAULTS" for target in targets):
            continue
        if not isinstance(value_node, ast.Dict):
            continue
        for key, value in zip(value_node.keys, value_node.values):
            if isinstance(key, ast.Constant) and key.value == "confirm_destructive":
                return bool(ast.literal_eval(value))
    raise ValueError("could not resolve _DEFAULTS['confirm_destructive'] from stages/execute.py")


def _report_destructive_confirmation(ctx: _PolicyContext, spec: PolicySettingSpec) -> ReportValue:
    if ctx.args is not None and hasattr(ctx.args, "confirm_destructive"):
        return _effective(
            spec,
            value=bool(getattr(ctx.args, "confirm_destructive")),
            source="args.confirm_destructive",
            notes="Resolved from the current execute invocation.",
        )
    return _effective(
        spec,
        value=_read_execute_stage_confirm_destructive_default(),
        source="arnold.pipelines.megaplan.stages.execute._DEFAULTS.confirm_destructive",
        notes="Stage default used when no explicit execute args are provided.",
    )


def _report_review_approval(ctx: _PolicyContext, spec: PolicySettingSpec) -> ReportValue:
    auto_approve = bool(ctx.config.get("auto_approve", False))
    arg_user_approved = bool(
        getattr(ctx.args, "user_approved", False)
    ) if ctx.args is not None else False
    gate_value = bool(ctx.meta.get("user_approved_gate", False)) or arg_user_approved
    mode = _resolve_execute_approval_mode(
        auto_approve=auto_approve,
        user_approved_gate=gate_value,
    )
    if auto_approve:
        source = "state.config.auto_approve"
    elif bool(ctx.meta.get("user_approved_gate", False)):
        source = "state.meta.user_approved_gate"
    elif arg_user_approved:
        source = "args.user_approved"
    else:
        source = "default/manual"
    return _effective(spec, value=mode, source=source)


def _report_blocked_lifecycle(ctx: _PolicyContext, spec: PolicySettingSpec) -> ReportValue:
    retry_flag = None
    retry_source = "args.retry_blocked_tasks"
    if ctx.args is not None and hasattr(ctx.args, "retry_blocked_tasks"):
        retry_flag = bool(getattr(ctx.args, "retry_blocked_tasks"))
    policy = RecoveryPolicy()
    return _effective(
        spec,
        value={
            "retry_blocked_tasks": retry_flag,
            "max_blocked_retries": policy.max_blocked_retries,
        },
        source=f"{retry_source} + arnold.pipelines.megaplan.orchestration.recovery_policy.RecoveryPolicy",
        notes="Read-only view over execute retry intent and orchestration retry budget.",
    )


def _report_batch_transitions(ctx: _PolicyContext, spec: PolicySettingSpec) -> ReportValue:
    state = dict(ctx.state or {})
    args = ctx.args or argparse.Namespace()
    max_tasks = _resolve_max_tasks_per_batch(state, args)
    if ctx.args is not None and getattr(ctx.args, "max_tasks_per_batch", None) is not None:
        source = "args.max_tasks_per_batch"
    elif "max_tasks_per_batch" in ctx.config:
        source = "state.config.max_tasks_per_batch"
    else:
        source = "arnold.pipelines.megaplan._core.get_effective(execution.max_tasks_per_batch)"
    value: dict[str, Any] = {"max_tasks_per_batch": max_tasks}
    if isinstance(ctx.finalize_data, Mapping):
        global_batches = compute_global_batches(dict(ctx.finalize_data))
        value["global_batch_count"] = len(split_oversized_batches(global_batches, max_tasks))
    return _effective(spec, value=value, source=source)


def _policy_mode(ctx: _PolicyContext) -> str:
    mode = ctx.config.get("mode")
    if isinstance(mode, str) and mode:
        return mode
    finalize_config = (
        ctx.finalize_data.get("config", {})
        if isinstance(ctx.finalize_data, Mapping)
        else {}
    )
    if isinstance(finalize_config, Mapping):
        final_mode = finalize_config.get("mode")
        if isinstance(final_mode, str) and final_mode:
            return final_mode
    return "code"


def _report_evidence_requirements(ctx: _PolicyContext, spec: PolicySettingSpec) -> ReportValue:
    if not isinstance(ctx.finalize_data, Mapping) or ctx.project_dir is None:
        return _unsupported(
            spec,
            source="validate_execution_evidence",
            notes="finalize_data and project_dir are required to evaluate execution evidence policy.",
        )
    audit = validate_execution_evidence(
        dict(ctx.finalize_data),
        ctx.project_dir,
        plan_dir=ctx.plan_dir,
        artifact_prefix="execution_audit_policy_settings",
        mode=_policy_mode(ctx),
        state=dict(ctx.state) if isinstance(ctx.state, Mapping) else None,
    )
    return _effective(
        spec,
        value={
            "mode": _policy_mode(ctx),
            "skipped": bool(audit.get("skipped", False)),
            "finding_count": len(audit.get("findings", [])),
        },
        source="arnold.pipelines.megaplan.orchestration.execution_evidence.validate_execution_evidence",
        notes="Reporting summarizes the existing evidence audit without mutating finalize data.",
    )


def _report_tier_selection(ctx: _PolicyContext, spec: PolicySettingSpec) -> ReportValue:
    if not isinstance(ctx.finalize_data, Mapping):
        return _unsupported(
            spec,
            source="select_batch_tier",
            notes="finalize_data is required to resolve complexity-derived batch tier selection.",
        )
    tasks = ctx.finalize_data.get("tasks", [])
    batch_task_ids = [
        task.get("id")
        for task in tasks
        if isinstance(task, Mapping) and isinstance(task.get("id"), str)
    ]
    if not batch_task_ids:
        return _unset(
            spec,
            source="finalize_data.tasks",
            notes="No task ids are available for tier resolution.",
        )
    raw_tier_models = getattr(ctx.args, "tier_models", None) if ctx.args is not None else None
    execute_tiers = raw_tier_models.get("execute") if isinstance(raw_tier_models, Mapping) else None
    tier_map = None
    if isinstance(execute_tiers, Mapping):
        normalized: dict[int, str] = {}
        for raw_tier, raw_spec in execute_tiers.items():
            if isinstance(raw_tier, bool):
                continue
            if not isinstance(raw_spec, str) or not raw_spec.strip():
                continue
            if isinstance(raw_tier, int):
                normalized[raw_tier] = raw_spec
            elif isinstance(raw_tier, str) and raw_tier.isdigit():
                normalized[int(raw_tier)] = raw_spec
        tier_map = normalized or None
    return _effective(
        spec,
        value={
            "selected_tier": select_batch_tier(dict(ctx.finalize_data), batch_task_ids),
            "tier_map": tier_map,
        },
        source=(
            "args.tier_models.execute + megaplan.execute._binding.tier.select_batch_tier"
            if tier_map
            else "arnold.pipelines.megaplan.execute._binding.tier.select_batch_tier"
        ),
        notes="Tier-map reporting is omitted when no execute tier_models are active.",
    )


def _report_iteration_pressure(ctx: _PolicyContext, spec: PolicySettingSpec) -> ReportValue:
    if ctx.plan_dir is None or not isinstance(ctx.state, Mapping):
        return _unsupported(
            spec,
            source="compute_iteration_pressure",
            notes="plan_dir and state are required to inspect critique history for iteration pressure.",
        )
    entries = compute_iteration_pressure(ctx.plan_dir, dict(ctx.state))
    if not entries:
        return _unset(
            spec,
            source="critique_v*.json + faults.json",
            notes="No recurring critique history was found for the current iteration window.",
        )
    max_iterations = max(entry["iterations_open"] for entry in entries)
    return _effective(
        spec,
        value={
            "entry_count": len(entries),
            "has_mechanical_recurrence": has_mechanical_recurrence(entries),
            "max_iterations_open": max_iterations,
        },
        source="arnold.pipelines.megaplan.orchestration.iteration_pressure.compute_iteration_pressure",
    )


SETTING_SPECS: tuple[PolicySettingSpec, ...] = (
    PolicySettingSpec(
        key="destructive_confirmation",
        owner="arnold.pipelines.megaplan.execute",
        summary="Execute destructive confirmation gate for code-mode runs.",
        resolver_ref="arnold.pipelines.megaplan.stages.execute._DEFAULTS + megaplan.handlers.execute.handle_execute",
        reporter=_report_destructive_confirmation,
    ),
    PolicySettingSpec(
        key="review_approval",
        owner="arnold.pipelines.megaplan.execute",
        summary="Execute approval mode after the review gate.",
        resolver_ref="arnold.pipelines.megaplan.execute._resolve_execute_approval_mode",
        reporter=_report_review_approval,
    ),
    PolicySettingSpec(
        key="blocked_lifecycle",
        owner="arnold.pipelines.megaplan.execute + arnold.pipelines.megaplan.orchestration",
        summary="Blocked-task retry intent plus orchestration retry budget.",
        resolver_ref="args.retry_blocked_tasks + arnold.pipelines.megaplan.orchestration.recovery_policy.RecoveryPolicy",
        reporter=_report_blocked_lifecycle,
    ),
    PolicySettingSpec(
        key="batch_transitions",
        owner="arnold.pipelines.megaplan.execute",
        summary="Batch sizing and batch-splitting policy during execute.",
        resolver_ref="arnold.pipelines.megaplan.execute.batch._resolve_max_tasks_per_batch",
        reporter=_report_batch_transitions,
    ),
    PolicySettingSpec(
        key="evidence_requirements",
        owner="arnold.pipelines.megaplan.execute + arnold.pipelines.megaplan.orchestration",
        summary="Execution evidence validation mode and current audit status.",
        resolver_ref="arnold.pipelines.megaplan.orchestration.execution_evidence.validate_execution_evidence",
        reporter=_report_evidence_requirements,
    ),
    PolicySettingSpec(
        key="tier_selection",
        owner="arnold.pipelines.megaplan.execute",
        summary="Complexity-derived execute tier selection and optional tier-map routing.",
        resolver_ref="arnold.pipelines.megaplan.handlers.execute._extract_execute_tier_map + megaplan.execute._binding.tier.select_batch_tier",
        reporter=_report_tier_selection,
    ),
    PolicySettingSpec(
        key="iteration_pressure",
        owner="arnold.pipelines.megaplan.orchestration",
        summary="Recurring critique pressure inferred from critique history artifacts.",
        resolver_ref="arnold.pipelines.megaplan.orchestration.iteration_pressure.compute_iteration_pressure",
        reporter=_report_iteration_pressure,
    ),
)


def describe_effective_policy_settings(
    *,
    args: argparse.Namespace | None = None,
    state: Mapping[str, Any] | None = None,
    finalize_data: Mapping[str, Any] | None = None,
    plan_dir: Path | None = None,
    project_dir: Path | None = None,
) -> list[ReportValue]:
    """Describe the effective Megaplan policy settings in a stable order."""
    ctx = _PolicyContext(
        args=args,
        state=state,
        finalize_data=finalize_data,
        plan_dir=plan_dir,
        project_dir=project_dir,
    )
    return [spec.reporter(ctx, spec) for spec in SETTING_SPECS]
