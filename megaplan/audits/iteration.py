"""Iteration-pressure analysis — detects recurring flags across critique iterations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from megaplan._core.registries import _concern_word_set, _jaccard_similarity
from megaplan._core.io import read_json
from megaplan.types import PlanState


class IterationPressureEntry(TypedDict):
    fuzzy_group_id: str
    member_flag_ids: list[str]
    iterations_open: int
    addressed_then_reopened_count: int
    representative_concern: str


def compute_flag_history(
    plan_dir: Path, current_iteration: int
) -> list[dict[str, Any]]:
    """Scan critique_v{N}.json artifacts to reconstruct per-flag status transitions."""
    flags_by_id: dict[str, list[dict[str, Any]]] = {}
    for iteration in range(1, current_iteration + 1):
        critique_path = plan_dir / f"critique_v{iteration}.json"
        if not critique_path.exists():
            continue
        critique = read_json(critique_path)
        seen_ids: set[str] = set()
        for check in critique.get("checks", []):
            for finding in check.get("findings", []):
                if finding.get("flagged"):
                    fid = check.get("id", "")
                    if fid:
                        seen_ids.add(fid)
                        flags_by_id.setdefault(fid, []).append(
                            {"iteration": iteration, "status": "open", "concern": finding.get("detail", "")}
                        )
        for flag in critique.get("flags", []):
            fid = flag.get("id", "")
            if fid:
                seen_ids.add(fid)
                flags_by_id.setdefault(fid, []).append(
                    {"iteration": iteration, "status": flag.get("status", "open"), "concern": flag.get("concern", "")}
                )

    faults_path = plan_dir / "faults.json"
    if faults_path.exists():
        faults = read_json(faults_path)
        for flag in faults.get("flags", []):
            fid = flag.get("id", "")
            if fid and fid not in flags_by_id:
                flags_by_id.setdefault(fid, []).append(
                    {"iteration": 0, "status": flag.get("status", "open"), "concern": flag.get("concern", "")}
                )

    result = []
    for fid, entries in flags_by_id.items():
        concern = entries[-1].get("concern", "") if entries else ""
        iterations_seen = sorted({e["iteration"] for e in entries})
        statuses = [e["status"] for e in entries]
        reopen_count = 0
        was_addressed = False
        for s in statuses:
            if s in ("addressed", "verified"):
                was_addressed = True
            elif s == "open" and was_addressed:
                reopen_count += 1
                was_addressed = False
        result.append({
            "id": fid,
            "concern": concern,
            "iterations": iterations_seen,
            "iterations_open": len(iterations_seen),
            "addressed_then_reopened_count": reopen_count,
        })
    return result


def compute_fuzzy_groups(
    flags: list[dict[str, Any]], threshold: float = 0.6
) -> dict[str, list[str]]:
    """Group flags by Jaccard word similarity on concern text."""
    word_sets = {f["id"]: _concern_word_set(f.get("concern", "")) for f in flags}
    assigned: dict[str, str] = {}
    groups: dict[str, list[str]] = {}
    group_counter = 0

    for flag in flags:
        fid = flag["id"]
        if fid in assigned:
            continue
        group_counter += 1
        gid = f"FG-{group_counter:03d}"
        groups[gid] = [fid]
        assigned[fid] = gid

        for other in flags:
            oid = other["id"]
            if oid in assigned:
                continue
            if _jaccard_similarity(word_sets[fid], word_sets[oid]) >= threshold:
                groups[gid].append(oid)
                assigned[oid] = gid

    return groups


def compute_iteration_pressure(
    plan_dir: Path, state: PlanState
) -> list[IterationPressureEntry]:
    current_iteration = state.get("iteration", 1)
    flag_history = compute_flag_history(plan_dir, current_iteration)
    if not flag_history:
        return []

    groups = compute_fuzzy_groups(flag_history, threshold=0.6)
    history_by_id = {f["id"]: f for f in flag_history}

    entries: list[IterationPressureEntry] = []
    for gid, member_ids in groups.items():
        members = [history_by_id[fid] for fid in member_ids if fid in history_by_id]
        if not members:
            continue
        all_iterations: set[int] = set()
        max_reopen = 0
        for m in members:
            all_iterations.update(m.get("iterations", []))
            max_reopen = max(max_reopen, m.get("addressed_then_reopened_count", 0))

        entries.append(IterationPressureEntry(
            fuzzy_group_id=gid,
            member_flag_ids=member_ids,
            iterations_open=len(all_iterations),
            addressed_then_reopened_count=max_reopen,
            representative_concern=members[0].get("concern", ""),
        ))
    return entries


def has_mechanical_recurrence(entries: list[IterationPressureEntry]) -> bool:
    for entry in entries:
        if entry["addressed_then_reopened_count"] >= 2:
            return True
        if entry["iterations_open"] >= 2 and len(entry["member_flag_ids"]) >= 2:
            return True
    return False


def render_pressure_table(entries: list[IterationPressureEntry]) -> str:
    if not entries:
        return ""
    lines = [
        "Iteration Pressure Analysis:",
        f"{'Group':<10} {'Flags':<6} {'Iters':<6} {'Reopened':<9} Concern",
        "-" * 72,
    ]
    for e in entries:
        concern = e["representative_concern"][:50]
        lines.append(
            f"{e['fuzzy_group_id']:<10} {len(e['member_flag_ids']):<6} "
            f"{e['iterations_open']:<6} {e['addressed_then_reopened_count']:<9} {concern}"
        )
    return "\n".join(lines)
