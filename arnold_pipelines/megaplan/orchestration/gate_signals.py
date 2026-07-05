"""Gate-signal scoring and loop diagnostics."""

from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
from types import MappingProxyType

from arnold_pipelines.megaplan.schemas import GateSignals
from arnold_pipelines.megaplan.types import FLAG_BLOCKING_STATUSES, FlagRecord, PlanState
from arnold_pipelines.megaplan._core import (
    configured_robustness,
    current_iteration_artifact,
    escalated_subsystems,
    extract_subsystem_tag,
    find_matching_debt,
    latest_plan_path,
    load_debt_registry,
    load_flag_registry,
    normalize_text,
    read_json,
    scope_creep_flags,
    unresolved_significant_flags,
)

GATE_SIGNAL_WEIGHT_POLICY = MappingProxyType(
    {
        "security_weight": 3.0,
        "implementation_detail_signals": (
            "column",
            "schema",
            "field",
            "as written",
            "pseudocode",
            "seed sql",
            "placeholder",
        ),
        "implementation_detail_weight": 0.5,
        "category_weights": {
            "correctness": 2.0,
            "completeness": 1.5,
            "performance": 1.0,
            "maintainability": 0.75,
            "other": 1.0,
        },
        "default_weight": 1.0,
    }
)


def flag_weight(flag: FlagRecord) -> float:
    """Weight a flag for gate context. Higher = more blocking."""
    category = flag.get("category", "other")
    concern = flag.get("concern", "").lower()

    if category == "security":
        return float(GATE_SIGNAL_WEIGHT_POLICY["security_weight"])

    implementation_detail_signals = GATE_SIGNAL_WEIGHT_POLICY["implementation_detail_signals"]
    if any(signal in concern for signal in implementation_detail_signals):
        return float(GATE_SIGNAL_WEIGHT_POLICY["implementation_detail_weight"])

    weights = GATE_SIGNAL_WEIGHT_POLICY["category_weights"]
    return float(weights.get(category, GATE_SIGNAL_WEIGHT_POLICY["default_weight"]))


def compute_plan_delta_percent(previous_text: str | None, current_text: str) -> float | None:
    if previous_text is None:
        return None
    ratio = SequenceMatcher(None, previous_text, current_text).ratio()
    return round((1.0 - ratio) * 100.0, 2)


def compute_recurring_critiques(plan_dir: Path, iteration: int) -> list[str]:
    if iteration < 2:
        return []
    previous_path = current_iteration_artifact(plan_dir, "critique", iteration - 1)
    current_path = current_iteration_artifact(plan_dir, "critique", iteration)
    if not previous_path.exists() or not current_path.exists():
        return []
    previous = read_json(previous_path)
    current = read_json(current_path)
    previous_concerns = {normalize_text(flag.get("concern", "")) for flag in previous.get("flags", []) if isinstance(flag, dict)}
    current_concerns = {normalize_text(flag.get("concern", "")) for flag in current.get("flags", []) if isinstance(flag, dict)}
    return sorted(previous_concerns.intersection(current_concerns))


def _previous_iteration_plan_path(plan_dir: Path, state: PlanState) -> Path | None:
    current_version = state["iteration"]
    previous_version = current_version - 1
    if previous_version < 1:
        return None
    matching = [
        record
        for record in state["plan_versions"]
        if record.get("version") == previous_version
    ]
    if not matching:
        return None
    return plan_dir / matching[-1]["file"]


def build_gate_signals(plan_dir: Path, state: PlanState, root: Path | None = None) -> GateSignals:
    iteration = state["iteration"]
    flag_registry = load_flag_registry(plan_dir)
    unresolved = unresolved_significant_flags(flag_registry)
    robustness = configured_robustness(state)
    open_scope_creep = scope_creep_flags(flag_registry, statuses=FLAG_BLOCKING_STATUSES)
    debt_root = root
    if debt_root is None:
        debt_root = plan_dir.parents[2] if len(plan_dir.parents) >= 3 else plan_dir
    debt_registry = load_debt_registry(debt_root)
    significant_count = len(
        [
            flag
            for flag in flag_registry["flags"]
            if flag.get("severity") == "significant" and flag["status"] != "verified"
        ]
    )
    weighted_score = round(sum(flag_weight(flag) for flag in unresolved), 2)
    weighted_history = list(state["meta"].get("weighted_scores", []))
    latest_plan_text = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
    previous_plan_path = _previous_iteration_plan_path(plan_dir, state)
    previous_text = None
    if previous_plan_path is not None and previous_plan_path.exists():
        previous_text = previous_plan_path.read_text(encoding="utf-8")
    plan_delta = compute_plan_delta_percent(previous_text, latest_plan_text)
    recurring = compute_recurring_critiques(plan_dir, iteration)
    from arnold_pipelines.megaplan.flags import flag_resolution_summary

    addressed_flags = [
        {
            "id": flag["id"],
            "concern": flag["concern"],
            "category": flag.get("category", "other"),
            "severity": flag.get("severity", "unknown"),
            "resolution": flag_resolution_summary(flag),
            "addressed_in": flag.get("addressed_in", ""),
        }
        for flag in flag_registry["flags"]
        if flag["status"] == "addressed"
    ]
    resolved_flags = [
        {
            "id": flag["id"],
            "concern": flag["concern"],
            "resolution": flag_resolution_summary(flag),
        }
        for flag in flag_registry["flags"]
        if flag["status"] == "verified"
    ]
    unverifiable_checks: list[dict[str, object]] = []
    critique_path = current_iteration_artifact(plan_dir, "critique", iteration)
    if critique_path.exists():
        critique_payload = read_json(critique_path)
        raw_unverifiable = critique_payload.get("unverifiable_checks", [])
        if isinstance(raw_unverifiable, list):
            unverifiable_checks = [
                item for item in raw_unverifiable if isinstance(item, dict)
            ]

    delta_history = state["meta"].get("plan_deltas", [])
    if weighted_history:
        trajectory = " -> ".join(str(score) for score in weighted_history) + f" -> {weighted_score}"
    else:
        trajectory = str(weighted_score)
    delta_summary = ", ".join(
        "n/a" if delta is None else f"{delta:.1f}%"
        for delta in delta_history
    ) or "n/a"
    loop_summary = (
        f"Iteration {iteration}. Weighted score trajectory: {trajectory}. "
        f"Plan deltas: {delta_summary}. "
        f"Recurring critiques: {len(recurring)}. "
        f"Addressed-unverified flags: {len(addressed_flags)}. "
        f"Resolved flags: {len(resolved_flags)}. "
        f"Open significant flags: {len(unresolved)}."
    )
    debt_overlaps = []
    overlapping_escalated_subsystems: set[str] = set()
    escalated_lookup = {
        subsystem: total
        for subsystem, total, _entries in escalated_subsystems(debt_registry)
    }
    for flag in unresolved:
        subsystem = extract_subsystem_tag(flag["concern"])
        match = find_matching_debt(debt_registry, subsystem, flag["concern"])
        if match is None:
            continue
        debt_overlaps.append(
            {
                "flag_id": flag["id"],
                "debt_id": match["id"],
                "subsystem": subsystem,
                "concern": flag["concern"],
                "debt_concern": match["concern"],
                "occurrence_count": match["occurrence_count"],
                "plan_ids": match["plan_ids"],
            }
        )
        if subsystem in escalated_lookup:
            overlapping_escalated_subsystems.add(subsystem)

    result: GateSignals = {
        "robustness": robustness,
        "signals": {
            "iteration": iteration,
            "idea": state.get("idea", ""),
            "significant_flags": significant_count,
            "unresolved_flags": [
                {
                    "id": flag["id"],
                    "concern": flag["concern"],
                    "category": flag["category"],
                    "severity": flag.get("severity", "unknown"),
                    "status": flag["status"],
                }
                for flag in unresolved
            ],
            "addressed_flags": addressed_flags,
            "resolved_flags": resolved_flags,
            "weighted_score": weighted_score,
            "weighted_history": weighted_history,
            "plan_delta_from_previous": plan_delta,
            "recurring_critiques": recurring,
            "scope_creep_flags": [flag["id"] for flag in open_scope_creep],
            "loop_summary": loop_summary,
            "debt_overlaps": debt_overlaps,
            "escalated_debt_subsystems": [
                {
                    "subsystem": subsystem,
                    "total_occurrences": escalated_lookup[subsystem],
                }
                for subsystem in sorted(overlapping_escalated_subsystems)
            ],
            "repeated_divergence_fingerprint": state.get("meta", {}).get("chain_policy", {}).get("repeated_divergence_fingerprint"),
        },
        "warnings": [],
    }
    if unverifiable_checks:
        result["signals"]["unverifiable_checks"] = unverifiable_checks
        result["signals"]["execution_acceptance_contract"] = {
            "scope": "execute",
            "verification_mode": "verification_suite",
            "required_checks": unverifiable_checks,
        }
    if open_scope_creep:
        result["warnings"].append(
            "Scope creep detected: the plan appears to be expanding beyond the original idea or recorded user notes."
        )
    if iteration >= 5:
        result["warnings"].append(f"Iteration {iteration}: high iteration count.")
    if iteration >= 12:
        result["warnings"].append(
            f"Iteration {iteration}: hard iteration limit reached. Escalation is likely warranted."
        )
    for subsystem in sorted(overlapping_escalated_subsystems):
        result["warnings"].append(
            "Recurring debt detected in subsystem "
            f"'{subsystem}' (total occurrences: {escalated_lookup[subsystem]}). "
            "Recommend holistic redesign rather than another point fix."
        )
    return result
