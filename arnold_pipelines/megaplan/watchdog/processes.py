"""Process-signature scanning for Megaplan/Arnold/Shannon/Codex/Claude.

Each ProcessRecord can be converted to a normalized :class:`WorkerIdentity`
via :func:`to_worker_identity` for use in liveness correlation.  Recycled,
unrelated, dead, and hung workers produce typed stale or unknown liveness
only — never false-positive progress.

Same-basename sessions are excluded from joins when ambiguity would cause
false correlation.  Unrelated processes (cmdline/cwd not matching any plan)
are recorded as typed uncertainty rather than silently joined.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Tuple

from arnold_pipelines.megaplan._core.state import _pid_is_live
from arnold_pipelines.megaplan.watchdog.worker_identity import (
    WorkerIdentity,
    _read_boot_id,
)


# ── Process correlation certainty ─────────────────────────────────────────


class ProcessCertainty(Enum):
    """Typed certainty for process-to-plan correlation.

    * ``EXACT`` — process is unambiguously correlated to a single plan.
    * ``AMBIGUOUS`` — process cmdline/cwd matches multiple plans.
    * ``SAME_BASENAME`` — process matches a basename shared by multiple plans.
    * ``UNRELATED`` — process does not match any known plan.
    * ``RECYCLED`` — PID matches but boot_id differs (recycled process).
    * ``UNKNOWN`` — could not determine correlation.
    """

    EXACT = "exact"
    AMBIGUOUS = "ambiguous"
    SAME_BASENAME = "same_basename"
    UNRELATED = "unrelated"
    RECYCLED = "recycled"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProcessRecord:
    pid: int
    cmdline: str
    category: str
    is_live: bool
    cwd: str | None = None
    ppid: int | None = None
    elapsed_seconds: float | None = None
    cpu_seconds: float | None = None
    certainty: ProcessCertainty = ProcessCertainty.UNKNOWN
    """Correlation certainty for this process."""

    matched_plan_dirs: Tuple[str, ...] = ()
    """Plan directories matched by this process (empty if unrelated)."""

    boot_id: str = ""
    """System boot ID at scan time (for recycled PID detection)."""

    process_digest: str = field(init=False)
    """Content-addressed process identifier."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        raw = f"{self.pid}\x00{self.cmdline}\x00{self.category}\x00{self.certainty.value}\x00{self.boot_id}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        object.__setattr__(self, "process_digest", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def is_joinable(self) -> bool:
        """True when this process can be safely joined to a plan.

        Excludes unrelated, recycled, and same-basename ambiguous processes.
        Only EXACT and AMBIGUOUS (with a single match) are joinable.
        """
        if self.certainty in (ProcessCertainty.UNRELATED, ProcessCertainty.RECYCLED):
            return False
        if self.certainty == ProcessCertainty.SAME_BASENAME:
            return False
        if self.certainty == ProcessCertainty.AMBIGUOUS and len(self.matched_plan_dirs) > 1:
            return False
        if self.certainty == ProcessCertainty.UNKNOWN:
            return False
        return True

    @property
    def is_excluded_from_joins(self) -> bool:
        """True when this process is explicitly excluded from plan joins."""
        return not self.is_joinable

    @property
    def exclusion_reason(self) -> str:
        """Human-readable reason for join exclusion (empty if joinable)."""
        if self.is_joinable:
            return ""
        if self.certainty == ProcessCertainty.UNRELATED:
            return "unrelated: no plan correlation"
        if self.certainty == ProcessCertainty.RECYCLED:
            return f"recycled: boot_id mismatch (scanned={self.boot_id})"
        if self.certainty == ProcessCertainty.SAME_BASENAME:
            return f"same_basename: ambiguous plan name in cmdline"
        if self.certainty == ProcessCertainty.AMBIGUOUS:
            return f"ambiguous: matches {len(self.matched_plan_dirs)} plans"
        return "unknown certainty"

    def to_worker_identity(self) -> WorkerIdentity:
        """Convert this process record to a normalized worker identity.

        The boot_id is read once and cached.  Heartbeat_seq starts at 0
        (no heartbeat evidence).  Consumers must call
        :meth:`WorkerIdentity.with_heartbeat` when heartbeat evidence is
        available.
        """
        return WorkerIdentity.from_process_record(
            pid=self.pid,
            worker_type=self.category,
            cmdline=self.cmdline,
            cwd=self.cwd or "",
            boot_id=self.boot_id or _read_boot_id() or "",
            started_at_epoch_ms=(time.time() - (self.elapsed_seconds or 0)) * 1000
            if self.elapsed_seconds is not None
            else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pid": self.pid,
            "cmdline": self.cmdline,
            "category": self.category,
            "is_live": self.is_live,
            "cwd": self.cwd,
            "ppid": self.ppid,
            "elapsed_seconds": self.elapsed_seconds,
            "cpu_seconds": self.cpu_seconds,
            "certainty": self.certainty.value,
            "matched_plan_dirs": list(self.matched_plan_dirs),
            "boot_id": self.boot_id,
            "is_joinable": self.is_joinable,
            "is_excluded_from_joins": self.is_excluded_from_joins,
            "exclusion_reason": self.exclusion_reason,
            "process_digest": self.process_digest,
            "_non_authoritative": self._non_authoritative,
        }


_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("megaplan", ("megaplan", "python -m megaplan")),
    ("arnold", ("arnold", "python -m arnold")),
    ("shannon", ("shannon",)),
    ("codex", ("codex",)),
    ("claude", ("claude",)),
)


def _parse_ps_time(value: str) -> float | None:
    """Parse ps ``etime``/``time`` ([[dd-]hh:]mm:ss) to seconds."""
    value = value.strip()
    if not value:
        return None
    try:
        if "-" in value:
            days, rest = value.split("-", 1)
            day_seconds = int(days) * 86400
        else:
            day_seconds = 0
            rest = value
        parts = rest.split(":")
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return day_seconds + int(hours) * 3600 + int(minutes) * 60 + int(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return day_seconds + int(minutes) * 60 + int(seconds)
        if len(parts) == 1:
            return day_seconds + int(parts[0])
    except Exception:
        pass
    return None


def _categorize_cmdline(cmdline: str) -> str | None:
    lowered = cmdline.lower()
    # Split on whitespace, path separators, and dots so dotted module paths
    # like "python -m arnold_pipelines.megaplan" are categorized correctly.
    # Path segments like ".megaplan-worktrees" split into "megaplan-worktrees",
    # which does not exactly match the "megaplan" needle, avoiding false positives.
    tokens = re.split(r"[\s/.]", lowered)
    for category, needles in _CATEGORIES:
        for needle in needles:
            if needle in tokens:
                return category
    return None


def _extract_cwd_from_cmdline(cmdline: str) -> str | None:
    """Best-effort cwd extraction from known cmdline patterns."""
    # Claude daemon: --spawned-by {"cwd":"/path",...}
    match = re.search(r'--spawned-by\s+\{[^}]*"cwd"\s*:\s*"([^"]+)"', cmdline)
    if match:
        return match.group(1)
    # tmux new-session -c /path (only when tmux is the executable).
    if cmdline.lstrip().startswith("tmux") or " tmux " in cmdline:
        match = re.search(r'\s-c\s+(\S+)', cmdline)
        if match:
            return match.group(1)
    # Bash wrapper: last `cd '/path' || cd "/path"` in the command.
    matches = re.findall(r"\bcd\s+['\"]([^'\"]+)['\"]", cmdline)
    if matches:
        return matches[-1]
    return None


def _get_cwd(pid: int) -> str | None:
    """Return the current working directory of *pid* if available."""
    # Linux procfs shortcut (only when procfs is present).
    proc_cwd = Path(f"/proc/{pid}/cwd")
    if proc_cwd.is_symlink():
        try:
            resolved = proc_cwd.resolve()
            if resolved.is_dir():
                return str(resolved)
        except Exception:
            pass
    # macOS / BSD via lsof.
    try:
        result = subprocess.run(
            ["lsof", "-p", str(pid), "-a", "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        for line in result.stdout.splitlines():
            if line.startswith("n"):
                candidate = line[1:]
                if Path(candidate).is_dir():
                    return candidate
    except Exception:
        pass
    return None


def _read_ps() -> list[str]:
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid,ppid,etime,time,args"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout.splitlines()
    except Exception:
        return []


def _detect_ps_format(ps_lines: Iterable[str]) -> str:
    """Return ``metadata`` if ps output includes ppid/etime/time, else ``legacy``."""
    for line in ps_lines:
        stripped = line.strip().lower()
        if stripped.startswith("pid args"):
            return "legacy"
        if "ppid" in stripped and "etime" in stripped:
            return "metadata"
        parts = stripped.split()
        if len(parts) >= 2:
            try:
                int(parts[0])
            except ValueError:
                continue
            try:
                int(parts[1])
                return "metadata" if len(parts) >= 5 else "legacy"
            except ValueError:
                return "legacy"
    return "metadata"


def scan_processes(ps_lines: Iterable[str] | None = None) -> tuple[ProcessRecord, ...]:
    """Parse ``ps`` output for Megaplan/Arnold/Shannon/Codex/Claude processes.

    When *ps_lines* is omitted, reads real ``ps -eo pid,ppid,etime,time,args``
    output. Also attempts to resolve each process's cwd so correlation can match
    processes to plans even when the cmdline does not name the plan directly.

    Each returned record carries a ``certainty`` of UNKNOWN by default.
    Consumers must classify each record as EXACT, AMBIGUOUS, SAME_BASENAME,
    UNRELATED, or RECYCLED after plan discovery to populate ``is_joinable``
    and ``is_excluded_from_joins`` flags.
    """
    if ps_lines is None:
        ps_lines = _read_ps()

    lines = list(ps_lines)
    fmt = _detect_ps_format(lines)
    records: list[ProcessRecord] = []

    # Read boot_id once per scan for recycled PID detection
    scan_boot_id = _read_boot_id() or ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith("pid"):
            continue

        ppid: int | None = None
        elapsed_seconds: float | None = None
        cpu_seconds: float | None = None

        if fmt == "metadata":
            parts = stripped.split(None, 4)
            if len(parts) < 5:
                continue
            try:
                pid = int(parts[0])
                ppid = int(parts[1])
            except ValueError:
                continue
            elapsed_seconds = _parse_ps_time(parts[2])
            cpu_seconds = _parse_ps_time(parts[3])
            cmdline = parts[4]
        else:
            parts = stripped.split(None, 1)
            if len(parts) < 2:
                continue
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            cmdline = parts[1]

        category = _categorize_cmdline(cmdline)
        if category is None:
            continue
        cwd = _extract_cwd_from_cmdline(cmdline) or _get_cwd(pid)
        records.append(
            ProcessRecord(
                pid=pid,
                cmdline=cmdline,
                category=category,
                is_live=_pid_is_live(pid),
                cwd=cwd,
                ppid=ppid,
                elapsed_seconds=elapsed_seconds,
                cpu_seconds=cpu_seconds,
                boot_id=scan_boot_id,
                certainty=ProcessCertainty.UNKNOWN,
                matched_plan_dirs=(),
            )
        )
    return tuple(records)


# ── Join filtering ────────────────────────────────────────────────────────


def filter_joinable_processes(
    processes: Tuple[ProcessRecord, ...],
) -> Tuple[ProcessRecord, ...]:
    """Filter processes to only those that are safe to join to plans.

    Excludes unrelated, recycled, same-basename ambiguous, and unknown
    processes.  Only EXACT and singly-matched AMBIGUOUS processes pass.
    """
    return tuple(p for p in processes if p.is_joinable)


def partition_processes_by_certainty(
    processes: Tuple[ProcessRecord, ...],
) -> Dict[ProcessCertainty, Tuple[ProcessRecord, ...]]:
    """Partition processes by correlation certainty.

    Returns a dict mapping each certainty level to the processes with that
    certainty.  Useful for diagnostics and typed uncertainty reporting.
    """
    result: Dict[ProcessCertainty, List[ProcessRecord]] = {}
    for p in processes:
        result.setdefault(p.certainty, []).append(p)
    return {k: tuple(v) for k, v in result.items()}


def classify_process_record(
    record: ProcessRecord,
    *,
    plan_names: Tuple[str, ...] = (),
    ambiguous_names: FrozenSet[str] = frozenset(),
    plan_dir_map: Optional[Dict[str, Any]] = None,
) -> ProcessRecord:
    """Classify a process record's correlation certainty.

    Checks the process cmdline against known plan names to determine
    whether it is EXACT, AMBIGUOUS, SAME_BASENAME, or UNRELATED.

    Args:
        record: The process record to classify.
        plan_names: Known plan names from discovery.
        ambiguous_names: Plan basenames shared by multiple directories.
        plan_dir_map: Optional map from plan name to plan dirs for matching.

    Returns:
        A new ProcessRecord with updated certainty and matched_plan_dirs.
    """
    lowered = record.cmdline.lower()
    matched: List[str] = []

    for name in plan_names:
        if not name:
            continue
        # Whole-word match (not inside a path)
        if _is_whole_word_in(lowered, name.lower()):
            matched.append(name)

    if not matched:
        # Check cwd against plan names
        cwd_lower = (record.cwd or "").lower()
        for name in plan_names:
            if name.lower() in cwd_lower:
                matched.append(name)

    if not matched:
        object.__setattr__(record, "certainty", ProcessCertainty.UNRELATED)
        object.__setattr__(record, "matched_plan_dirs", ())
        return record

    if len(matched) == 1:
        name = matched[0]
        if name in ambiguous_names:
            object.__setattr__(record, "certainty", ProcessCertainty.SAME_BASENAME)
        else:
            object.__setattr__(record, "certainty", ProcessCertainty.EXACT)
        object.__setattr__(record, "matched_plan_dirs", (name,))
    else:
        # Multiple matches — check if any are ambiguous
        has_ambiguous = any(name in ambiguous_names for name in matched)
        if has_ambiguous:
            object.__setattr__(record, "certainty", ProcessCertainty.SAME_BASENAME)
        else:
            object.__setattr__(record, "certainty", ProcessCertainty.AMBIGUOUS)
        object.__setattr__(record, "matched_plan_dirs", tuple(matched))

    return record


def _is_whole_word_in(text: str, word: str) -> bool:
    """Check if word appears as a whole word (not inside a path) in text."""
    idx = 0
    while True:
        idx = text.find(word, idx)
        if idx == -1:
            return False
        before = text[idx - 1] if idx > 0 else " "
        after = text[idx + len(word)] if idx + len(word) < len(text) else " "
        # Reject if inside a path (surrounded by /)
        if before == "/" or after == "/":
            idx += len(word)
            continue
        if before in {" ", "-", "_", '"', "'"} and after in {" ", "-", "_", '"', "'"}:
            return True
        idx += len(word)
    return False


__all__ = [
    "ProcessCertainty",
    "ProcessRecord",
    "scan_processes",
    "filter_joinable_processes",
    "partition_processes_by_certainty",
    "classify_process_record",
]
