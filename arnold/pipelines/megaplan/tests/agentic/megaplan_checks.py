"""
megaplan_checks.py — friction-signal extractors for megaplan evidence packs.

Five pure functions, each accepting a Path (evidence_dir) and returning a
structured dict with ``count``, ``passed``, and ``detail`` fields.

Bundled via :func:`project_universal_checks` — the single entry point
expected by sisypy's ``AgenticProjectAdapter`` contract.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Signal 1 — invalid_transitions
# ---------------------------------------------------------------------------

def _check_invalid_transitions(evidence_dir: Path) -> dict[str, Any]:
    """Count case-sensitive ``invalid_transition`` hits in stderr + command_log."""
    count = 0
    locations: list[str] = []

    # stderr.log
    stderr = evidence_dir / "stderr.log"
    if stderr.is_file():
        text = stderr.read_text(errors="replace")
        hits = text.count("invalid_transition")
        if hits:
            count += hits
            locations.append(f"stderr.log ({hits})")

    # command_log.jsonl
    cmdlog = evidence_dir / "command_log.jsonl"
    if cmdlog.is_file():
        for lineno, line in enumerate(cmdlog.read_text(errors="replace").splitlines(), 1):
            if line.strip():
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Search all string values (nested one level only — command_log
                # entries are flat dicts).
                for val in obj.values():
                    if isinstance(val, str):
                        hits = val.count("invalid_transition")
                        if hits:
                            count += hits
                            locations.append(f"command_log.jsonl:{lineno} ({hits})")

    passed = count == 0
    return {
        "count": count,
        "passed": passed,
        "detail": f"invalid_transition occurrences: {locations if locations else 'none'}",
    }


# ---------------------------------------------------------------------------
# Signal 2 — overrides
# ---------------------------------------------------------------------------

_OVERRIDE_RE = re.compile(r"\bmegaplan\s+override\s+(?P<verb>[\w-]+)?")


def _check_overrides(evidence_dir: Path) -> dict[str, Any]:
    """Count ``megaplan override <verb>`` invocations in stdout + stderr."""
    count = 0
    verbs: list[str] = []

    for filename in ("stdout.log", "stderr.log"):
        fp = evidence_dir / filename
        if fp.is_file():
            text = fp.read_text(errors="replace")
            for m in _OVERRIDE_RE.finditer(text):
                count += 1
                verb = m.group("verb")
                if verb:
                    verbs.append(verb)

    passed = count == 0
    return {
        "count": count,
        "passed": passed,
        "detail": f"override verbs: {verbs if verbs else 'none'}",
    }


# ---------------------------------------------------------------------------
# Signal 3 — auto_downgraded
# ---------------------------------------------------------------------------


def _check_auto_downgraded(evidence_dir: Path) -> dict[str, Any]:
    """Find ``Auto-downgraded`` hits in captured gate.json files."""
    count = 0
    locations: list[str] = []

    ps_dir = evidence_dir / "project_specific"
    if ps_dir.is_dir():
        for gate_file in ps_dir.rglob("gate.json"):
            text = gate_file.read_text(errors="replace")
            hits = text.count("Auto-downgraded")
            if hits:
                count += hits
                locations.append(f"{gate_file.relative_to(evidence_dir)} ({hits})")

    passed = count == 0
    return {
        "count": count,
        "passed": passed,
        "detail": f"Auto-downgraded hits: {locations if locations else 'none'}",
    }


# ---------------------------------------------------------------------------
# Signal 4 — status_loops
# ---------------------------------------------------------------------------

_STATUS_RE = re.compile(r"\bmegaplan\s+status\b")
# Mutating megaplan commands — anything that changes state rather than reads it.
_MUTATING_PATTERNS = [
    r"\bmegaplan\s+run\b",
    r"\bmegaplan\s+init\b",
    r"\bmegaplan\s+plan\b",
    r"\bmegaplan\s+advance\b",
    r"\bmegaplan\s+override\b",
    r"\bmegaplan\s+review\b",
    r"\bmegaplan\s+approve\b",
    r"\bmegaplan\s+done\b",
    r"\bmegaplan\s+reject\b",
    r"\bmegaplan\s+block\b",
    r"\bmegaplan\s+config\b",
    r"\bmegaplan\s+create\b",
    r"\bmegaplan\s+new\b",
]
_MUTATING_RE = re.compile("|".join(_MUTATING_PATTERNS))


def _check_status_loops(evidence_dir: Path) -> dict[str, Any]:
    """Count runs of ≥3 consecutive ``megaplan status`` with no mutating command."""
    count = 0
    cmdlog = evidence_dir / "command_log.jsonl"
    if not cmdlog.is_file():
        return {"count": 0, "passed": True, "detail": "no command_log.jsonl"}

    # Build a boolean sequence: True = megaplan status, False = mutating command.
    seq: list[bool] = []
    for line in cmdlog.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        cmd = obj.get("command", "")
        if not isinstance(cmd, str) or not cmd:
            continue
        if _STATUS_RE.search(cmd):
            seq.append(True)
        elif _MUTATING_RE.search(cmd):
            seq.append(False)
        else:
            # Non-megaplan commands don't reset the count but aren't counted as status.
            seq.append(False)  # treat as reset for safety

    # Find runs of ≥3 consecutive True values.
    run_len = 0
    for v in seq:
        if v:
            run_len += 1
        else:
            if run_len >= 3:
                count += 1
            run_len = 0
    if run_len >= 3:
        count += 1

    passed = count == 0
    return {
        "count": count,
        "passed": passed,
        "detail": f"≥3-consecutive status runs: {count}",
    }


# ---------------------------------------------------------------------------
# Signal 5 — direct_edits
# ---------------------------------------------------------------------------


def _check_direct_edits(evidence_dir: Path) -> dict[str, Any]:
    """Count non-test .py files in git_diff.patch without preceding ``megaplan init``.

    Excludes files that were already dirty (modified or untracked) at scenario
    start, per ``git_status_before.txt``. Without this exclusion, every run in
    a worktree that carried over uncommitted changes would falsely flag those
    carry-over files as direct edits by the actor.
    """
    diff_file = evidence_dir / "git_diff.patch"
    if not diff_file.is_file():
        return {"count": 0, "passed": True, "detail": "no git_diff.patch"}

    # Build the carry-over exclusion set from git_status_before.txt
    # (porcelain format: two-char status code, space, path).
    before_dirty: set[str] = set()
    before_file = evidence_dir / "git_status_before.txt"
    fallback_note = ""
    if before_file.is_file():
        for line in before_file.read_text(errors="replace").splitlines():
            if len(line) < 4:
                continue
            # Format: XY <path>  (porcelain), with renames: "R  old -> new".
            path = line[3:].strip()
            if " -> " in path:
                # Rename: count the destination path as dirty.
                _, _, path = path.partition(" -> ")
            if path:
                before_dirty.add(path.strip())
    else:
        fallback_note = " (no git_status_before.txt — counting all)"

    # Extract changed .py files (non-test).
    changed_py: list[str] = []
    excluded_carryover: list[str] = []
    diff_text = diff_file.read_text(errors="replace")
    for m in re.finditer(r"^diff --git a/(.+?) b/(.+?)$", diff_text, re.MULTILINE):
        path_b = m.group(2)
        if not (
            path_b.endswith(".py")
            and "/test" not in path_b
            and "/tests/" not in path_b
        ):
            continue
        if path_b in before_dirty:
            excluded_carryover.append(path_b)
            continue
        changed_py.append(path_b)

    if not changed_py:
        detail = "no scenario-introduced non-test .py changes"
        if excluded_carryover:
            detail += f" ({len(excluded_carryover)} carry-over excluded)"
        detail += fallback_note
        return {"count": 0, "passed": True, "detail": detail}

    # Check whether megaplan init preceded any edits.
    has_init = False
    cmdlog = evidence_dir / "command_log.jsonl"
    if cmdlog.is_file():
        for line in cmdlog.read_text(errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            cmd = obj.get("command", "")
            if isinstance(cmd, str) and re.search(r"\bmegaplan\s+init\b", cmd):
                has_init = True
                break

    count = 0 if has_init else len(changed_py)
    passed = count == 0
    detail = (
        f"direct .py edits: {changed_py if count else 'none'} "
        f"(init seen: {has_init})"
    )
    if excluded_carryover:
        detail += f"; {len(excluded_carryover)} carry-over excluded"
    if fallback_note:
        detail += fallback_note
    return {
        "count": count,
        "passed": passed,
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# Bundle — project_universal_checks
# ---------------------------------------------------------------------------


def project_universal_checks(evidence_dir: Path) -> dict[str, Any]:
    """Run all five megaplan friction-signal extractors.

    Returns a dict mapping each signal name to a structured result dict
    with ``count``, ``passed``, and ``detail`` fields.
    """
    return {
        "invalid_transitions": _check_invalid_transitions(evidence_dir),
        "overrides": _check_overrides(evidence_dir),
        "auto_downgraded": _check_auto_downgraded(evidence_dir),
        "status_loops": _check_status_loops(evidence_dir),
        "direct_edits": _check_direct_edits(evidence_dir),
    }
