"""Flag and debt registry operations."""

from __future__ import annotations

import re
from pathlib import Path

from arnold.pipelines.megaplan.types import (
    DEBT_ESCALATION_THRESHOLD,
    DebtEntry,
    DebtRegistry,
    FLAG_BLOCKING_STATUSES,
    FlagRecord,
    FlagRegistry,
    SCOPE_CREEP_TERMS,
)

from .io import (
    atomic_write_json,
    megaplan_root,
    normalize_text,
    now_utc,
    read_json,
)


# ---------------------------------------------------------------------------
# Flag registry
# ---------------------------------------------------------------------------

def load_flag_registry(plan_dir: Path) -> FlagRegistry:
    path = plan_dir / "faults.json"
    if path.exists():
        return read_json(path)
    return {"flags": []}


def save_flag_registry(plan_dir: Path, registry: FlagRegistry) -> None:
    atomic_write_json(plan_dir / "faults.json", registry)


def unresolved_significant_flags(flag_registry: FlagRegistry) -> list[FlagRecord]:
    return [
        flag
        for flag in flag_registry["flags"]
        if flag.get("severity") == "significant" and flag["status"] in FLAG_BLOCKING_STATUSES
    ]


def is_scope_creep_flag(flag: FlagRecord) -> bool:
    text = f"{flag['concern']} {flag.get('evidence', '')}".lower()
    return any(term in text for term in SCOPE_CREEP_TERMS)


def scope_creep_flags(
    flag_registry: FlagRegistry,
    *,
    statuses: set[str] | None = None,
) -> list[FlagRecord]:
    matches = []
    for flag in flag_registry["flags"]:
        if statuses is not None and flag["status"] not in statuses:
            continue
        if is_scope_creep_flag(flag):
            matches.append(flag)
    return matches


# ---------------------------------------------------------------------------
# Debt registry
# ---------------------------------------------------------------------------

def load_debt_registry(root: Path) -> DebtRegistry:
    path = megaplan_root(root) / "debt.json"
    if path.exists():
        return read_json(path)
    return {"entries": []}


def save_debt_registry(root: Path, registry: DebtRegistry) -> None:
    atomic_write_json(megaplan_root(root) / "debt.json", registry)


def next_debt_id(registry: DebtRegistry) -> str:
    max_id = 0
    for entry in registry["entries"]:
        match = re.fullmatch(r"DEBT-(\d+)", entry["id"])
        if match is None:
            continue
        max_id = max(max_id, int(match.group(1)))
    return f"DEBT-{max_id + 1:03d}"


def _normalize_subsystem_tag(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "untagged"


def extract_subsystem_tag(concern: str) -> str:
    prefix, separator, _ = concern.partition(":")
    if not separator:
        return "untagged"
    return _normalize_subsystem_tag(prefix)


def _concern_word_set(concern: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9]+", normalize_text(concern))
        if token
    }


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def find_matching_debt(registry: DebtRegistry, subsystem: str, concern: str) -> DebtEntry | None:
    normalized_subsystem = _normalize_subsystem_tag(subsystem)
    concern_words = _concern_word_set(concern)
    for entry in registry["entries"]:
        if entry["resolved"]:
            continue
        if entry["subsystem"] != normalized_subsystem:
            continue
        if _jaccard_similarity(_concern_word_set(entry["concern"]), concern_words) > 0.5:
            return entry
    return None


def add_or_increment_debt(
    registry: DebtRegistry,
    subsystem: str,
    concern: str,
    flag_ids: list[str],
    plan_id: str,
) -> DebtEntry:
    normalized_subsystem = _normalize_subsystem_tag(subsystem)
    normalized_concern = normalize_text(concern)
    timestamp = now_utc()
    existing = find_matching_debt(registry, normalized_subsystem, normalized_concern)
    if existing is not None:
        existing["occurrence_count"] += 1
        existing["updated_at"] = timestamp
        for flag_id in flag_ids:
            if flag_id not in existing["flag_ids"]:
                existing["flag_ids"].append(flag_id)
        if plan_id not in existing["plan_ids"]:
            existing["plan_ids"].append(plan_id)
        return existing

    entry: DebtEntry = {
        "id": next_debt_id(registry),
        "subsystem": normalized_subsystem,
        "concern": normalized_concern,
        "flag_ids": list(dict.fromkeys(flag_ids)),
        "plan_ids": [plan_id],
        "occurrence_count": 1,
        "created_at": timestamp,
        "updated_at": timestamp,
        "resolved": False,
        "resolved_by": None,
        "resolved_at": None,
    }
    registry["entries"].append(entry)
    return entry


def resolve_debt(registry: DebtRegistry, debt_id: str, plan_id: str) -> DebtEntry:
    from arnold.pipelines.megaplan.types import CliError

    for entry in registry["entries"]:
        if entry["id"] != debt_id:
            continue
        timestamp = now_utc()
        entry["resolved"] = True
        entry["resolved_by"] = plan_id
        entry["resolved_at"] = timestamp
        entry["updated_at"] = timestamp
        return entry
    raise CliError("missing_debt", f"Debt entry '{debt_id}' does not exist")


def debt_by_subsystem(registry: DebtRegistry) -> dict[str, list[DebtEntry]]:
    grouped: dict[str, list[DebtEntry]] = {}
    for entry in registry["entries"]:
        if entry["resolved"]:
            continue
        grouped.setdefault(entry["subsystem"], []).append(entry)
    return grouped


def subsystem_occurrence_total(entries: list[DebtEntry]) -> int:
    return sum(entry["occurrence_count"] for entry in entries)


def escalated_subsystems(registry: DebtRegistry) -> list[tuple[str, int, list[DebtEntry]]]:
    escalated: list[tuple[str, int, list[DebtEntry]]] = []
    for subsystem, entries in debt_by_subsystem(registry).items():
        total = subsystem_occurrence_total(entries)
        if total >= DEBT_ESCALATION_THRESHOLD:
            escalated.append((subsystem, total, entries))
    escalated.sort(key=lambda item: (-item[1], item[0]))
    return escalated
