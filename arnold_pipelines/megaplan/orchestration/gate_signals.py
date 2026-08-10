"""Gate-signal scoring and loop diagnostics."""

from __future__ import annotations

import re
import subprocess
from difflib import SequenceMatcher
from pathlib import Path
from types import MappingProxyType
from typing import Any

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
    now_utc,
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

# --------------------------------------------------------------------------- #
# CL4 (Plan Step 8): BRIDGE-mode in-band markers.
#
# CL4 operates in BRIDGE mode because the CL3 handoff is missing and five
# CL1/CL2 blockers are carried forward unresolved. The gate signal carries
# these markers in-band so a downstream gate/finalize consumer reading the
# signal can never mistake a BRIDGE-mode artifact for canonical gate or
# finalize authority. The markers are sourced from the same constants used
# by the CL4 handoff (docs/critique-ledger/handoffs/cl4-role-flow.json) and
# the inherited CL1/CL2 blocker set.
# --------------------------------------------------------------------------- #

#: CL4 runs in canonical (non-BRIDGE) mode after the CL5 cutover. The CL3
#: handoff is now resolved, all CL1/CL2 blockers are cleared, and the
#: module-level BRIDGE markers are disabled. NOTE: this constant only governs
#: the marker freshly emitted on each gate signal; canonical gate authority is
#: still denied at runtime whenever any *source receipt* in the clearance chain
#: carries bridge_mode=true (enforced at critique_custody.py from the aggregated
#: clearance chain, NOT from this constant). The cutover receipt generator
#: produces bridge_mode=false source receipts by construction once this flips.
CL4_BRIDGE_MODE: bool = False

#: The CL1/CL2 blockers previously carried forward into CL4. After the CL5
#: cutover all five blockers are resolved, so the carried set is empty. (The
#: same ids remain recorded as resolved in cl1-contract-oracle.json /
#: cl2-ledger-replay.json and the CL4 handoff's cl1_cl2_blockers_carried block.)
CL4_CARRIED_BLOCKERS: tuple[str, ...] = ()

#: Reconciliation relationships that ground a semantic-recurrence judgment.
#: Unlike exact-text adjacency, semantic recurrence requires evaluator-
#: authored reconciliation evidence asserting that two findings are the same
#: concern. NEW/UNRELATED/UNCERTAIN are deliberately excluded — they assert
#: non-sameness or uncertainty, not recurrence.
_SEMANTIC_RECURRENCE_RELATIONSHIPS = frozenset({"DUPLICATE", "REFINEMENT", "MERGE"})

# --------------------------------------------------------------------------- #
# Git-plumbing baseline-presence oracle (Horizon B)
#
# The gate worker must never infer that a pinned baseline commit is "absent"
# from a naive `.git/` filesystem content search: loose objects are stored
# zlib-compressed, packed objects are binary, and objects may be reachable
# through alternates or a linked-worktree common directory. The only
# authoritative presence check is git plumbing (`git cat-file -e` and
# `git rev-parse --verify`). This oracle computes that receipt once, in the
# engine, and injects it into gate signals so the gate worker receives ground
# truth instead of guessing from a `.git/` search.
# --------------------------------------------------------------------------- #

#: Matches full 40-hex commit object ids referenced in plan text.
_GIT_SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")

#: Bounded number of referenced SHAs verified per gate-signals build.
_MAX_BASELINE_PRESENCE_REFS = 12

#: Default search roots for a pinned baseline commit, in priority order.
_BASELINE_REF_SEARCH_PATHS = (
    "NORTHSTAR.md",
)


def _git_plumbing(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run one git plumbing command against *root*, never raising."""
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(
            ["git", "-C", str(root), *args],
            returncode=127,
            stdout="",
            stderr=f"git invocation failed: {exc}",
        )


def git_object_presence_receipt(project_dir: Path, sha: str) -> dict[str, Any]:
    """Return a typed git-plumbing receipt for one commit object.

    Presence is decided exclusively by ``git cat-file -e <sha>^{commit}`` and
    ``git rev-parse --verify <sha>^{commit}``. The receipt also records the
    repository identity (git dir, common dir, HEAD) and a resolved tree id
    when the object exists, so downstream consumers never need to search
    ``.git`` on disk.
    """
    cat_file = _git_plumbing(project_dir, "cat-file", "-e", f"{sha}^{{commit}}")
    rev_parse = _git_plumbing(project_dir, "rev-parse", "--verify", f"{sha}^{{commit}}")
    present = cat_file.returncode == 0 and rev_parse.returncode == 0
    receipt: dict[str, Any] = {
        "schema": "arnold.megaplan.git_object_presence.v1",
        "sha": sha,
        "present": present,
        "method": "git cat-file -e <sha>^{commit} && git rev-parse --verify <sha>^{commit}",
        "cat_file_exit": cat_file.returncode,
        "rev_parse_exit": rev_parse.returncode,
        "checked_at": now_utc(),
    }
    if present:
        tree = _git_plumbing(project_dir, "rev-parse", f"{sha}^{{tree}}")
        if tree.returncode == 0:
            receipt["tree"] = tree.stdout.strip()
        git_dir = _git_plumbing(project_dir, "rev-parse", "--git-dir")
        if git_dir.returncode == 0:
            receipt["git_dir"] = git_dir.stdout.strip()
        common_dir = _git_plumbing(project_dir, "rev-parse", "--git-common-dir")
        if common_dir.returncode == 0:
            receipt["common_dir"] = common_dir.stdout.strip()
        head = _git_plumbing(project_dir, "rev-parse", "HEAD")
        if head.returncode == 0:
            receipt["head"] = head.stdout.strip()
    return receipt


def baseline_presence_signals(plan_dir: Path, state: PlanState, root: Path | None = None) -> dict[str, Any]:
    """Build the authoritative baseline-presence evidence block for gate signals.

    Scans the latest plan text plus the NORTHSTAR/prelaunch-disposition anchor
    documents for pinned 40-hex commit references and verifies each via git
    plumbing. Returns ``{"schema": ..., "project_dir": ..., "receipts": [...]}``.
    """
    project_dir = Path(str((state.get("config") or {}).get("project_dir") or "."))
    plan_path = latest_plan_path(plan_dir, state)
    candidates: list[str] = []
    for path in (plan_path, *_BASELINE_REF_SEARCH_PATHS):
        candidate = path if isinstance(path, Path) else project_dir / path
        try:
            if candidate.is_file():
                candidates.extend(_GIT_SHA_RE.findall(candidate.read_text(encoding="utf-8")))
        except OSError:
            continue
    unique_shas: list[str] = []
    for sha in candidates:
        if sha not in unique_shas:
            unique_shas.append(sha)
    receipts = [
        git_object_presence_receipt(project_dir, sha)
        for sha in unique_shas[:_MAX_BASELINE_PRESENCE_REFS]
    ]
    return {
        "schema": "arnold.megaplan.baseline_presence.v1",
        "project_dir": str(project_dir),
        "checked_at": now_utc(),
        "receipts": receipts,
        "count": len(receipts),
    }



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


def compute_adjacent_text_matches(plan_dir: Path, iteration: int) -> list[str]:
    """Return the exact-text adjacency matches for an iteration.

    This is the renamed informational form of the exact-text comparison
    previously emitted only as ``recurring_critiques``. The deprecated
    ``recurring_critiques`` alias is now populated from this list so the six
    ``.get("recurring_critiques", ...)`` consumers keep working unchanged.
    """
    return compute_recurring_critiques(plan_dir, iteration)


def compute_semantic_recurrence(plan_dir: Path, iteration: int) -> bool:
    """Return True when reconciliation evidence grounds a semantic-recurrence
    judgment for the current iteration.

    Unlike ``adjacent_text_matches`` (exact-text overlap), semantic recurrence
    is grounded in evaluator-authored reconciliation data: it is True only
    when a reconciliation event carrying a DUPLICATE, REFINEMENT, or MERGE
    relationship is present. This prevents recurrence from collapsing back to
    text equality. NEW / UNRELATED / UNCERTAIN assert non-sameness or
    uncertainty and are excluded.

    The reconciliation evidence is read from either a dedicated
    ``reconciliation_v{iteration}.json`` artifact or a
    ``reconciliation_events`` list embedded in the critique artifact. When no
    reconciliation evidence is available (the normal case until CL5 wires the
    critique-ledger semantic loop into the runtime), the result is False — a
    truthful ``no evidence`` rather than a silent text-derived True.
    """
    payloads: list[Any] = []
    reconciliation_path = current_iteration_artifact(plan_dir, "reconciliation", iteration)
    if reconciliation_path.exists():
        try:
            payloads.append(read_json(reconciliation_path))
        except (OSError, ValueError):
            pass
    critique_path = current_iteration_artifact(plan_dir, "critique", iteration)
    if critique_path.exists():
        try:
            critique_payload = read_json(critique_path)
        except (OSError, ValueError):
            critique_payload = {}
        embedded = critique_payload.get("reconciliation_events") if isinstance(critique_payload, dict) else None
        if isinstance(embedded, list):
            payloads.append({"reconciliation_events": embedded})
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        events = payload.get("reconciliation_events", [])
        if not isinstance(events, list):
            continue
        for event in events:
            if not isinstance(event, dict):
                continue
            relationship = str(event.get("relationship", ""))
            if relationship in _SEMANTIC_RECURRENCE_RELATIONSHIPS:
                return True
    return False


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
    # CL4 (Plan Step 8): split the exact-text output into the informational
    # ``adjacent_text_matches`` list and its boolean complement
    # ``no_adjacent_text_match``, add the reconciliation-grounded
    # ``semantic_recurrence`` flag, and keep ``recurring_critiques`` as a
    # deprecated alias populated from adjacent_text_matches so the six legacy
    # .get()-based consumers keep working unchanged.
    adjacent_text_matches = compute_adjacent_text_matches(plan_dir, iteration)
    recurring = adjacent_text_matches  # deprecated alias, same value
    no_adjacent_text_match = len(adjacent_text_matches) == 0
    semantic_recurrence = compute_semantic_recurrence(plan_dir, iteration)
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
            # CL4 (Plan Step 8) / CL5 (Plan Step 7b): exact-text adjacency
            # split + reconciliation-grounded recurrence + BRIDGE-mode in-band
            # markers. ``adjacent_text_matches`` is informational (the exact-
            # text overlap); ``no_adjacent_text_match`` is its boolean
            # complement; ``semantic_recurrence`` is True only when
            # reconciliation evidence (DUPLICATE/REFINEMENT/MERGE) supports it.
            # The deprecated ``recurring_critiques`` output alias was retired
            # in CL5 Step 7b; the internal ``compute_recurring_critiques``
            # function remains as the implementation of
            # ``compute_adjacent_text_matches`` (a cosmetic naming detail).
            "adjacent_text_matches": adjacent_text_matches,
            "no_adjacent_text_match": no_adjacent_text_match,
            "semantic_recurrence": semantic_recurrence,
            "bridge_mode": CL4_BRIDGE_MODE,
            "carried_blockers": list(CL4_CARRIED_BLOCKERS),
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
    # Horizon B: inject the authoritative git-plumbing baseline-presence receipt
    # so gate workers never infer commit absence from a naive `.git/` content
    # search (loose objects are compressed; packed/alternates/common-dir objects
    # are invisible to filesystem text search).
    result["signals"]["baseline_presence"] = baseline_presence_signals(plan_dir, state, root)
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
