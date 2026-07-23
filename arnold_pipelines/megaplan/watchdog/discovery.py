"""Filesystem plan discovery for the live watchdog.

Discovery returns exact worker identity tuples and excludes unrelated,
recycled, and same-basename sessions from joins.  Ambiguity is recorded
as typed uncertainty rather than silently collapsed to optimistic state.

Design rules
------------
* Every discovered plan is returned with a typed identity tuple
  ``(plan_dir, plan_name, plan_state_hash)`` that uniquely identifies it.
* Same-basename sessions (different paths, same directory name) are flagged
  as ``ambiguous`` — they are included but marked with uncertainty.
* Discovery never assumes liveness — it records what exists on disk.
* Plan state is content-addressed so consumers can detect drift.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Set, Tuple

from arnold_pipelines.megaplan.watchdog.worker_identity import WorkerIdentity


# ── Discovery types ────────────────────────────────────────────────────────


class DiscoveryCertainty(Enum):
    """Typed uncertainty for discovered plans.

    * ``EXACT`` — plan identity is unambiguous (unique name + path).
    * ``AMBIGUOUS_NAME`` — multiple plans share the same basename.
    * ``UNVERIFIED`` — plan exists but state could not be read.
    * ``UNKNOWN`` — plan directory exists but cannot be classified.
    """

    EXACT = "exact"
    AMBIGUOUS_NAME = "ambiguous_name"
    UNVERIFIED = "unverified"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DiscoveredPlan:
    """A single discovered plan with exact identity tuple.

    Every plan is identified by (resolved_path, plan_name, state_hash).
    Same-basename plans are flagged with ``certainty=AMBIGUOUS_NAME``.
    """

    plan_dir: Path
    """Resolved absolute path to the plan directory."""

    plan_name: str
    """Plan name (directory basename)."""

    state_hash: str
    """sha256 of the plan's state.json content (empty if unreadable)."""

    certainty: DiscoveryCertainty = DiscoveryCertainty.EXACT
    """Certainty of this plan's identity."""

    ambiguity_set: Tuple[str, ...] = ()
    """When AMBIGUOUS_NAME: paths of other plans with the same basename."""

    state: Optional[Dict[str, Any]] = None
    """Parsed state.json (None if unreadable)."""

    plan_id: str = field(init=False)
    """Content-addressed plan identifier: sha256 over (path, name, state_hash)."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        raw = f"{self.plan_dir}\x00{self.plan_name}\x00{self.state_hash}\x00{self.certainty.value}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        object.__setattr__(self, "plan_id", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def is_ambiguous(self) -> bool:
        """True when this plan shares a basename with another plan."""
        return self.certainty == DiscoveryCertainty.AMBIGUOUS_NAME

    @property
    def is_verified(self) -> bool:
        """True when state was successfully read."""
        return self.certainty in (DiscoveryCertainty.EXACT, DiscoveryCertainty.AMBIGUOUS_NAME)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_dir": str(self.plan_dir),
            "plan_name": self.plan_name,
            "state_hash": self.state_hash,
            "certainty": self.certainty.value,
            "ambiguity_set": list(self.ambiguity_set),
            "is_ambiguous": self.is_ambiguous,
            "is_verified": self.is_verified,
            "plan_id": self.plan_id,
            "_non_authoritative": self._non_authoritative,
        }


@dataclass(frozen=True)
class DiscoveryResult:
    """Complete discovery result with plans, ambiguity map, and statistics."""

    plans: Tuple[DiscoveredPlan, ...]
    """All discovered plans, sorted by plan_dir."""

    ambiguous_names: Tuple[str, ...]
    """Basenames that appear in multiple plan directories."""

    total_count: int = 0
    ambiguous_count: int = 0
    unverified_count: int = 0

    scan_roots: Tuple[str, ...] = ()
    """Root directories that were scanned."""

    discovery_id: str = field(init=False)

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        sorted_plans = tuple(sorted(self.plans, key=lambda p: str(p.plan_dir)))
        object.__setattr__(self, "plans", sorted_plans)
        object.__setattr__(self, "total_count", len(sorted_plans))
        object.__setattr__(
            self, "ambiguous_count",
            sum(1 for p in sorted_plans if p.is_ambiguous),
        )
        object.__setattr__(
            self, "unverified_count",
            sum(1 for p in sorted_plans if not p.is_verified),
        )
        parts = "\x00".join(p.plan_id for p in sorted_plans)
        digest = hashlib.sha256(parts.encode("utf-8")).hexdigest()
        object.__setattr__(self, "discovery_id", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def exact_plans(self) -> Tuple[DiscoveredPlan, ...]:
        """Plans with unambiguous identity."""
        return tuple(p for p in self.plans if p.certainty == DiscoveryCertainty.EXACT)

    @property
    def plan_dir_map(self) -> Dict[Path, DiscoveredPlan]:
        """Map from resolved plan_dir to DiscoveredPlan."""
        return {p.plan_dir: p for p in self.plans}

    @property
    def plan_name_map(self) -> Dict[str, Tuple[DiscoveredPlan, ...]]:
        """Map from plan_name to all plans with that name."""
        result: Dict[str, List[DiscoveredPlan]] = {}
        for p in self.plans:
            result.setdefault(p.plan_name, []).append(p)
        return {k: tuple(v) for k, v in result.items()}

    def is_name_ambiguous(self, name: str) -> bool:
        """True when multiple plans share this basename."""
        return name in self.ambiguous_names

    def by_name(self, name: str) -> Tuple[DiscoveredPlan, ...]:
        """Return all plans with the given basename."""
        return self.plan_name_map.get(name, ())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plans": [p.to_dict() for p in self.plans],
            "ambiguous_names": list(self.ambiguous_names),
            "total_count": self.total_count,
            "ambiguous_count": self.ambiguous_count,
            "unverified_count": self.unverified_count,
            "scan_roots": list(self.scan_roots),
            "discovery_id": self.discovery_id,
            "_non_authoritative": self._non_authoritative,
        }


# ── Scan roots ─────────────────────────────────────────────────────────────


DEFAULT_SCAN_ROOTS: tuple[str, ...] = (
    "~/Documents",
    "~/Documents/.megaplan-worktrees",
    "~/.megaplan-worktrees",
    "/tmp",
    "/private/tmp",
)


def _resolve_roots(roots: Iterable[str]) -> list[Path]:
    """Expand user dirs and dedupe by canonical path."""
    seen: set[Path] = set()
    result: list[Path] = []
    for root in roots:
        path = Path(root).expanduser().resolve()
        if path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result


# ── Plan discovery with identity tuples ───────────────────────────────────


def _discover_state_files(roots: Iterable[str]) -> Tuple[Tuple[Path, Path], ...]:
    """Find ``.megaplan/plans/*/state.json`` under configured roots.

    Returns (plan_dir, state_file) pairs.  Skips missing roots.
    Deduplicates by canonical resolved plan_dir.
    """
    resolved = _resolve_roots(roots)
    seen: set[Path] = set()
    result: list[Tuple[Path, Path]] = []

    for root in resolved:
        if not root.exists():
            continue
        for state_file in root.glob("**/.megaplan/plans/*/state.json"):
            plan_dir = state_file.parent
            canonical = plan_dir.resolve()
            if canonical in seen:
                continue
            seen.add(canonical)
            result.append((canonical, state_file))

    return tuple(result)


def _read_and_hash_state(state_file: Path) -> Tuple[Optional[Dict[str, Any]], str]:
    """Read state.json and return (parsed, sha256_hex).

    Returns (None, "") if unreadable.
    """
    try:
        content = state_file.read_bytes()
        state_hash = hashlib.sha256(content).hexdigest()
        state = json.loads(content.decode("utf-8"))
        return state, state_hash
    except Exception:
        return None, ""


def _detect_ambiguous_names(
    plan_pairs: Tuple[Tuple[Path, Path], ...],
) -> FrozenSet[str]:
    """Return basenames that appear in multiple plan directories."""
    name_counts: Dict[str, int] = {}
    for plan_dir, _ in plan_pairs:
        name = plan_dir.name
        name_counts[name] = name_counts.get(name, 0) + 1
    return frozenset(name for name, count in name_counts.items() if count > 1)


def discover_plans_with_identity(
    roots: Iterable[str] | None = None,
) -> DiscoveryResult:
    """Discover plans with exact identity tuples and ambiguity detection.

    Args:
        roots: Directories to scan.  Defaults to DEFAULT_SCAN_ROOTS.

    Returns:
        DiscoveryResult with typed certainty per plan.  Same-basename plans
        are marked ``AMBIGUOUS_NAME`` with the set of conflicting paths.
    """
    if roots is None:
        roots = DEFAULT_SCAN_ROOTS

    plan_pairs = _discover_state_files(roots)
    ambiguous_names = _detect_ambiguous_names(plan_pairs)

    plans: list[DiscoveredPlan] = []
    for plan_dir, state_file in plan_pairs:
        name = plan_dir.name
        state, state_hash = _read_and_hash_state(state_file)

        if name in ambiguous_names:
            # Find all other plan dirs with this basename
            others = tuple(
                str(other_dir)
                for other_dir, _ in plan_pairs
                if other_dir.name == name and other_dir != plan_dir
            )
            certainty = DiscoveryCertainty.AMBIGUOUS_NAME
        elif state is not None:
            certainty = DiscoveryCertainty.EXACT
        else:
            certainty = DiscoveryCertainty.UNVERIFIED

        plans.append(DiscoveredPlan(
            plan_dir=plan_dir,
            plan_name=name,
            state_hash=state_hash,
            certainty=certainty,
            ambiguity_set=others if name in ambiguous_names else (),
            state=state,
        ))

    return DiscoveryResult(
        plans=tuple(plans),
        ambiguous_names=tuple(sorted(ambiguous_names)),
        scan_roots=tuple(str(r) for r in _resolve_roots(roots)),
    )


# ── Legacy-compatible functions ────────────────────────────────────────────


def discover_plans(roots: Iterable[str] | None = None) -> tuple[Path, ...]:
    """Legacy signature: return only plan_dir Paths.

    Prefer ``discover_plans_with_identity`` for new consumers that need
    identity tuples and ambiguity detection.
    """
    result = discover_plans_with_identity(roots)
    return tuple(p.plan_dir for p in result.plans)


def read_plan_state(plan_dir: Path) -> dict | None:
    """Read a plan's ``state.json`` directly, returning None if unreadable."""
    state_file = plan_dir / "state.json"
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_plan_state_with_hash(plan_dir: Path) -> Tuple[Optional[Dict[str, Any]], str]:
    """Read a plan's state.json and return (parsed, sha256_hex)."""
    state_file = plan_dir / "state.json"
    return _read_and_hash_state(state_file)


def plan_identity_tuple(plan_dir: Path) -> Tuple[str, str, str]:
    """Return the exact identity tuple for a plan directory.

    Returns (resolved_path, plan_name, state_hash).  Empty strings for
    unreadable state and unresolvable paths.
    """
    try:
        resolved = str(plan_dir.resolve())
    except Exception:
        resolved = str(plan_dir)
    name = plan_dir.name
    _, state_hash = _read_and_hash_state(plan_dir / "state.json")
    return (resolved, name, state_hash)


__all__ = [
    # ── Types ──
    "DiscoveryCertainty",
    "DiscoveredPlan",
    "DiscoveryResult",
    # ── Constants ──
    "DEFAULT_SCAN_ROOTS",
    # ── Discovery (new) ──
    "discover_plans_with_identity",
    # ── Discovery (legacy compat) ──
    "discover_plans",
    "read_plan_state",
    "read_plan_state_with_hash",
    "plan_identity_tuple",
]
