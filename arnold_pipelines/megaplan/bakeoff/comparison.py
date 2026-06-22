"""Comparison schema and markdown rendering for bake-offs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core.io import atomic_write_text
from arnold_pipelines.megaplan.bakeoff.judge import JudgeVerdict
from arnold_pipelines.megaplan.bakeoff.state import BakeoffState, bakeoff_root


COMPARISON_SCHEMA_VERSION = 1
METRIC_KEYS = [
    "duration_s",
    "cost_usd",
    "rework_cycles",
    "escalations",
    "review_verdict",
    "diff_lines",
    "tests_added",
    "scope_drift_severity_by_phase",
]
DOC_METRIC_KEYS = [
    "duration_s",
    "cost_usd",
    "rework_cycles",
    "escalations",
    "review_verdict",
    "doc_path",
    "doc_present",
    "doc_size_bytes",
    "doc_line_count",
    "scope_drift_severity_by_phase",
]


def build_comparison(
    bakeoff_state: BakeoffState,
    profile_metrics: dict[str, dict[str, Any]],
    judge_verdict: JudgeVerdict | None,
) -> dict[str, Any]:
    mode = bakeoff_state.get("mode") or "code"
    metric_keys = DOC_METRIC_KEYS if mode == "doc" else METRIC_KEYS
    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "experiment_id": bakeoff_state["experiment_id"],
        "base_sha": bakeoff_state["base_sha"],
        "idea_hash": bakeoff_state["idea_hash"],
        "mode": mode,
        "output_path": bakeoff_state.get("output_path"),
        "profiles": [
            _comparison_profile(record, profile_metrics.get(record["name"], {}), metric_keys)
            for record in bakeoff_state.get("profiles", [])
        ],
        "judge_verdict": judge_verdict,
        "human_decision": None,
    }


def write_comparison(root: Path, comparison: dict[str, Any]) -> tuple[Path, Path]:
    exp_id = str(comparison["experiment_id"])
    json_path = bakeoff_root(root, exp_id) / "comparison.json"
    md_path = bakeoff_root(root, exp_id) / "comparison.md"
    atomic_write_text(json_path, json.dumps(comparison, indent=2, sort_keys=True) + "\n")
    atomic_write_text(md_path, render_comparison_markdown(comparison))
    return json_path, md_path


def render_comparison_markdown(comparison: dict[str, Any]) -> str:
    mode = comparison.get("mode") or "code"
    if mode == "doc":
        return _render_doc_comparison_markdown(comparison)
    lines = [
        f"# Bake-off comparison: {comparison['experiment_id']}",
        "",
        "| profile | outcome | duration_s | cost_usd | rework | escalations | review | diff_lines | tests_added |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
    ]
    for profile in comparison.get("profiles", []):
        metrics = profile.get("metrics") if isinstance(profile.get("metrics"), dict) else {}
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(profile.get("name")),
                    _cell(profile.get("outcome_status")),
                    _cell(metrics.get("duration_s")),
                    _cell(metrics.get("cost_usd")),
                    _cell(metrics.get("rework_cycles")),
                    _cell(metrics.get("escalations")),
                    _cell(metrics.get("review_verdict")),
                    _cell(metrics.get("diff_lines")),
                    _cell(metrics.get("tests_added")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Judge", ""])
    judge = comparison.get("judge_verdict")
    if judge is None:
        lines.append("judge skipped: no --judge flag")
    else:
        lines.append(f"model: {_cell(judge.get('judge_model'))}")
        rank = judge.get("rank") if isinstance(judge.get("rank"), list) else []
        lines.append(f"rank: {', '.join(str(item) for item in rank)}")
        rationale = judge.get("rationale_per_profile")
        if isinstance(rationale, dict):
            lines.append("")
            for profile, text in rationale.items():
                lines.append(f"- **{profile}**: {text}")
        concerns = judge.get("concerns")
        if isinstance(concerns, list) and concerns:
            lines.append("")
            lines.append("concerns:")
            for concern in concerns:
                lines.append(f"- {concern}")
    return "\n".join(lines) + "\n"


def _comparison_profile(
    record: dict[str, Any],
    metrics_result: dict[str, Any],
    metric_keys: list[str] = METRIC_KEYS,
) -> dict[str, Any]:
    return {
        "name": record.get("name"),
        "worktree_path": record.get("worktree"),
        "plan_id": record.get("plan_id"),
        "outcome_status": metrics_result.get("outcome_status") or _outcome_status(record),
        "metrics": {key: metrics_result.get(key) for key in metric_keys},
        "receipts_ref": metrics_result.get("receipts_ref") or [],
    }


def _render_doc_comparison_markdown(comparison: dict[str, Any]) -> str:
    output_path = comparison.get("output_path")
    header_suffix = f" (doc mode: `{output_path}`)" if output_path else " (doc mode)"
    lines = [
        f"# Bake-off comparison: {comparison['experiment_id']}{header_suffix}",
        "",
        "| profile | outcome | duration_s | cost_usd | rework | escalations | review | doc_present | doc_size_bytes | doc_lines |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | :---: | ---: | ---: |",
    ]
    for profile in comparison.get("profiles", []):
        metrics = profile.get("metrics") if isinstance(profile.get("metrics"), dict) else {}
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(profile.get("name")),
                    _cell(profile.get("outcome_status")),
                    _cell(metrics.get("duration_s")),
                    _cell(metrics.get("cost_usd")),
                    _cell(metrics.get("rework_cycles")),
                    _cell(metrics.get("escalations")),
                    _cell(metrics.get("review_verdict")),
                    _cell(metrics.get("doc_present")),
                    _cell(metrics.get("doc_size_bytes")),
                    _cell(metrics.get("doc_line_count")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Judge", ""])
    judge = comparison.get("judge_verdict")
    if judge is None:
        lines.append("judge skipped: no --judge flag")
    else:
        lines.append(f"model: {_cell(judge.get('judge_model'))}")
        rank = judge.get("rank") if isinstance(judge.get("rank"), list) else []
        lines.append(f"rank: {', '.join(str(item) for item in rank)}")
        rationale = judge.get("rationale_per_profile")
        if isinstance(rationale, dict):
            lines.append("")
            for profile, text in rationale.items():
                lines.append(f"- **{profile}**: {text}")
        concerns = judge.get("concerns")
        if isinstance(concerns, list) and concerns:
            lines.append("")
            lines.append("concerns:")
            for concern in concerns:
                lines.append(f"- {concern}")
    return "\n".join(lines) + "\n"


def _outcome_status(record: dict[str, Any]) -> str | None:
    outcome = record.get("outcome")
    if isinstance(outcome, dict) and isinstance(outcome.get("status"), str):
        return outcome["status"]
    return None


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|")
