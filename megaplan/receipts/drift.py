"""Pure scope-drift computation for execute receipts."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Literal

BENIGN_PATTERNS = (
    ".megaplan/**",
    "execution.json",
    "final.md",
    "review.json",
    "*.meta.json",
    "package-lock.json",
    "uv.lock",
    "poetry.lock",
    "yarn.lock",
    "Cargo.lock",
    "step_receipt_*.json",
)


@dataclass
class ScopeDriftReport:
    files_added: list[str]
    files_missing: list[str]
    loc_added: int
    loc_removed: int
    loc_added_outside_claimed: int
    severity: Literal["none", "low", "high"]


def _is_benign(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch(normalized, pattern) for pattern in BENIGN_PATTERNS)


def compute_scope_drift(
    *,
    files_claimed: set[str],
    files_in_diff: set[str],
    loc_by_file: dict[str, int],
    files_claimed_for_missing: set[str] | None = None,
) -> ScopeDriftReport:
    files_added = sorted(path for path in files_in_diff - files_claimed if not _is_benign(path))
    # ``files_missing`` (claimed-but-not-in-diff = fabrication / wrong-tree) is a
    # per-call signal. In per-batch execute mode callers union every batch's
    # claims into ``files_claimed`` to avoid false unclaimed-addition findings,
    # but a file legitimately changed in one batch and reverted/superseded in a
    # later batch can be absent from the final diff. The union must not drive
    # missing-file severity.
    missing_baseline = (
        files_claimed if files_claimed_for_missing is None else files_claimed_for_missing
    )
    files_missing = sorted(missing_baseline - files_in_diff)
    loc_added = sum(loc_by_file.values())
    loc_added_outside_claimed = sum(loc_by_file.get(path, 0) for path in files_added)
    # ``files_missing`` means the executor claimed it changed a file that
    # isn't in the diff — i.e. fabricated work, or work that landed in the
    # wrong tree (sandbox escape).  Treat this at least as seriously as
    # writes-without-claims: low for any miss, high once the count is
    # comparable to a real-but-noisy diff (>3 files claimed-but-missing
    # is well past "model forgot to list one").
    if files_added and loc_added_outside_claimed > 20:
        severity: Literal["none", "low", "high"] = "high"
    elif len(files_missing) > 3:
        severity = "high"
    elif files_added or loc_added_outside_claimed > 0 or files_missing:
        severity = "low"
    else:
        severity = "none"
    return ScopeDriftReport(
        files_added=files_added,
        files_missing=files_missing,
        loc_added=loc_added,
        loc_removed=0,
        loc_added_outside_claimed=loc_added_outside_claimed,
        severity=severity,
    )


def _parse_numstat_count(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def collect_loc_by_file(project_dir: Path, candidate_paths: set[str]) -> dict[str, int]:
    """Return added LOC by changed path, including untracked files."""
    if not candidate_paths:
        return {}
    loc_by_file: dict[str, int] = {}
    paths = sorted(candidate_paths)
    try:
        result = subprocess.run(
            ["git", "diff", "--numstat", "HEAD", "--", *paths],
            cwd=project_dir,
            text=True,
            capture_output=True,
            check=False,
        )
    except Exception:
        result = None
    if result is not None and result.returncode == 0:
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            added, _removed, path = parts[0], parts[1], parts[2]
            loc_by_file[path] = _parse_numstat_count(added)
    for path in paths:
        if path in loc_by_file:
            continue
        try:
            loc_by_file[path] = (project_dir / path).read_text(encoding="utf-8").count("\n")
        except Exception:
            loc_by_file[path] = 0
    return loc_by_file
