"""FaultRegistry — Sprint 5 Chunk D, second primitive.

A typed primitive that judge-kind Steps populate to track findings
across iterations. Mirrors what handle_critique writes to
``faults.json`` today, but as a Step-side primitive any pipeline
can use without leaning on the handler internals.

Usage::

    registry = FaultRegistry.load(ctx.plan_dir)
    registry.add(Fault(
        id="short-sentences",
        kind="style",
        severity="significant",
        details="3 sentences under 6 words.",
    ))
    registry.save(ctx.plan_dir)

Each ``add`` call appends to the fault's iteration history. The
``addressed_then_reopened_count`` rises when a fault returns after
being marked addressed — the same signal the gate's TIEBREAKER
recommendation reads off today.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

log = logging.getLogger("megaplan")


FaultSeverity = Literal["significant", "minor", "info"]
FaultStatus = Literal["open", "addressed", "dismissed"]


@dataclass
class FaultIterationEntry:
    iteration: int
    status: FaultStatus
    note: str = ""


@dataclass
class Fault:
    id: str
    kind: str
    severity: FaultSeverity = "significant"
    details: str = ""
    status: FaultStatus = "open"
    history: list[FaultIterationEntry] = field(default_factory=list)

    @property
    def addressed_then_reopened_count(self) -> int:
        """How many times this fault has been addressed and reopened.

        Matches the gate's TIEBREAKER trigger signal: rises by 1
        every time an ``"addressed"`` entry is followed by an
        ``"open"`` entry in the history.
        """
        count = 0
        prev: FaultStatus | None = None
        for entry in self.history:
            if entry.status == "open" and prev == "addressed":
                count += 1
            prev = entry.status
        return count


@dataclass
class FaultRegistry:
    """Mutable collection of :class:`Fault`s, persisted to faults.json.

    Load with :meth:`load`, mutate via :meth:`add` / :meth:`mark`,
    persist with :meth:`save`. The on-disk format is::

        {"faults": [{"id": ..., "kind": ..., ..., "history": [...]}]}
    """

    faults: dict[str, Fault] = field(default_factory=dict)
    iteration: int = 0

    @classmethod
    def load(cls, plan_dir: Path) -> "FaultRegistry":
        path = Path(plan_dir) / "faults.json"
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            log.warning(
                "M3A_WARN_CORRUPT_FAULTS read fallback (reason=corrupt_json, path=%s)",
                path,
                exc_info=True,
            )
            return cls()
        faults: dict[str, Fault] = {}
        for entry in data.get("faults", []):
            if not isinstance(entry, dict):
                continue
            history = [
                FaultIterationEntry(
                    iteration=int(h.get("iteration", 0)),
                    status=h.get("status", "open"),
                    note=h.get("note", ""),
                )
                for h in entry.get("history", [])
                if isinstance(h, dict)
            ]
            fault_id = entry.get("id")
            if not isinstance(fault_id, str):
                continue
            faults[fault_id] = Fault(
                id=fault_id,
                kind=entry.get("kind", ""),
                severity=entry.get("severity", "significant"),
                details=entry.get("details", ""),
                status=entry.get("status", "open"),
                history=history,
            )
        return cls(faults=faults, iteration=int(data.get("iteration", 0)))

    def save(self, plan_dir: Path) -> Path:
        path = Path(plan_dir) / "faults.json"
        payload = {
            "iteration": self.iteration,
            "faults": [
                {
                    "id": f.id,
                    "kind": f.kind,
                    "severity": f.severity,
                    "details": f.details,
                    "status": f.status,
                    "history": [
                        {"iteration": h.iteration, "status": h.status, "note": h.note}
                        for h in f.history
                    ],
                }
                for f in self.faults.values()
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        return path

    def add(self, fault: Fault, *, iteration: int | None = None) -> Fault:
        """Add a new fault or update an existing one.

        If the fault id already exists, the iteration entry appends
        to its history; the fault's top-level status reflects the
        latest history entry.
        """
        iter_no = self.iteration if iteration is None else iteration
        existing = self.faults.get(fault.id)
        if existing is None:
            fault.history.append(
                FaultIterationEntry(
                    iteration=iter_no, status=fault.status, note=fault.details,
                )
            )
            self.faults[fault.id] = fault
            return fault
        existing.history.append(
            FaultIterationEntry(
                iteration=iter_no, status=fault.status, note=fault.details,
            )
        )
        existing.status = fault.status
        existing.severity = fault.severity or existing.severity
        existing.details = fault.details or existing.details
        existing.kind = fault.kind or existing.kind
        return existing

    def mark(
        self,
        fault_id: str,
        status: FaultStatus,
        *,
        note: str = "",
        iteration: int | None = None,
    ) -> None:
        """Append a status change to an existing fault's history."""
        existing = self.faults.get(fault_id)
        if existing is None:
            raise KeyError(f"no fault {fault_id!r} registered")
        iter_no = self.iteration if iteration is None else iteration
        existing.history.append(
            FaultIterationEntry(iteration=iter_no, status=status, note=note)
        )
        existing.status = status

    def open_significant(self) -> list[Fault]:
        return [
            f for f in self.faults.values()
            if f.status == "open" and f.severity == "significant"
        ]

    def reopened_repeatedly(self, threshold: int = 2) -> list[Fault]:
        """Faults whose addressed-then-reopened count hits ``threshold``."""
        return [
            f for f in self.faults.values()
            if f.addressed_then_reopened_count >= threshold
        ]
