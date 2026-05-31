"""T10 — bare-float PipelineVerdict score grep-gate ratchet.

Forbids `PipelineVerdict(score=<literal-float>` in the new SDK modules
(judge_piece.py, evaluand.py, prompt_cache.py, and the _attributable joins).
Allows only the explicitly listed old-path sites.
"""
from __future__ import annotations

import re
import sys
import types
from pathlib import Path

import pytest

_PATTERN = re.compile(r"PipelineVerdict\(score=[0-9]+\.[0-9]+")

# Files that are ALLOWED to contain the bare-float PipelineVerdict pattern.
# These are planning-binding and old-path sites grandfathered before M5-eval.
_ALLOWLIST: frozenset[str] = frozenset(
    [
        "megaplan/_pipeline/planning.py",
        "megaplan/_pipeline/pattern_types.py",
        "megaplan/_pipeline/pattern_joins.py",
        "megaplan/_pipeline/demo_judges.py",
        "megaplan/_pipeline/stages/inprocess_step.py",
    ]
)

# Files that are explicitly FORBIDDEN from having bare-float scores.
_FORBIDDEN: frozenset[str] = frozenset(
    [
        "megaplan/_pipeline/judge_piece.py",
        "megaplan/observability/evaluand.py",
        "megaplan/observability/prompt_cache.py",
    ]
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _scan_megaplan() -> list[tuple[str, int, str]]:
    """Return (rel_path, lineno, line) for every bare-float PipelineVerdict match."""
    hits: list[tuple[str, int, str]] = []
    for py_file in sorted((_REPO_ROOT / "megaplan").rglob("*.py")):
        rel = str(py_file.relative_to(_REPO_ROOT))
        with open(py_file) as fh:
            for lineno, line in enumerate(fh, start=1):
                if _PATTERN.search(line):
                    hits.append((rel, lineno, line.rstrip()))
    return hits


def test_bare_float_not_in_forbidden_files():
    """None of the forbidden new-SDK files may contain PipelineVerdict(score=<literal-float>."""
    hits = _scan_megaplan()
    violations = [(p, n, ln) for p, n, ln in hits if p in _FORBIDDEN]
    assert not violations, (
        "Bare-float PipelineVerdict found in FORBIDDEN files:\n"
        + "\n".join(f"  {p}:{n}: {ln}" for p, n, ln in violations)
    )


def test_bare_float_only_in_allowlist():
    """Every bare-float PipelineVerdict must be in the allowlisted files."""
    hits = _scan_megaplan()
    violations = [(p, n, ln) for p, n, ln in hits if p not in _ALLOWLIST]
    assert not violations, (
        "Bare-float PipelineVerdict found outside the allowlist:\n"
        + "\n".join(f"  {p}:{n}: {ln}" for p, n, ln in violations)
    )


def test_gate_passes_on_current_tree():
    """Combined gate: current codebase has zero violations."""
    hits = _scan_megaplan()
    violations = [(p, n, ln) for p, n, ln in hits if p not in _ALLOWLIST]
    assert not violations, f"Gate failed on current tree: {violations}"


def test_negative_fixture_fails_gate():
    """A simulated judge_piece.py with a bare-float score MUST fail the gate."""
    bad_module_src = "from megaplan._pipeline.types import PipelineVerdict\nresult = PipelineVerdict(score=0.5)\n"

    saved = sys.modules.get("megaplan._pipeline.judge_piece")
    fake_path = _REPO_ROOT / "megaplan" / "_pipeline" / "_tmp_judge_piece_fixture.py"
    fake_path.write_text(bad_module_src)
    try:
        hits = []
        for py_file in sorted((_REPO_ROOT / "megaplan").rglob("*.py")):
            rel = str(py_file.relative_to(_REPO_ROOT))
            with open(py_file) as fh:
                for lineno, line in enumerate(fh, start=1):
                    if _PATTERN.search(line):
                        hits.append((rel, lineno, line.rstrip()))
        # Treat the fixture file as if it were judge_piece.py (in the forbidden set)
        forbidden_hits = [
            (p, n, ln)
            for p, n, ln in hits
            if "_tmp_judge_piece_fixture" in p or p in _FORBIDDEN
        ]
        assert forbidden_hits, (
            "Negative fixture did not produce a gate violation — test is broken"
        )
    finally:
        fake_path.unlink(missing_ok=True)
