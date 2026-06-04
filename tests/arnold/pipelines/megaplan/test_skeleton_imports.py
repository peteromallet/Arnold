"""Import smoke tests for the M5b plugin domain packages."""

from __future__ import annotations

import importlib

import pytest


# ── per-package import smoke ────────────────────────────────────────────

@pytest.mark.parametrize(
    "pkg_name",
    [
        "arnold.pipelines.megaplan.execute",
        "arnold.pipelines.megaplan.review",
        "arnold.pipelines.megaplan.orchestration",
        "arnold.pipelines.megaplan.audits",
    ],
)
def test_can_import_plugin_domain_package(pkg_name: str) -> None:
    """Each plugin domain package must be importable without error."""
    mod = importlib.import_module(pkg_name)
    assert mod is not None


# ── no-accidental-content sanity ───────────────────────────────────────

def test_execute_skeleton_is_empty() -> None:
    """The execute skeleton MUST NOT yet re-export implementation symbols."""
    import arnold.pipelines.megaplan.execute as pkg
    # Only dunder attrs + package docstring — no implementation symbols
    public = [n for n in dir(pkg) if not n.startswith("_")]
    assert public == [], (
        f"execute skeleton should be empty, got: {public}"
    )


def test_review_skeleton_is_empty() -> None:
    """The review skeleton MUST NOT yet re-export implementation symbols."""
    import arnold.pipelines.megaplan.review as pkg
    public = [n for n in dir(pkg) if not n.startswith("_")]
    assert public == [], (
        f"review skeleton should be empty, got: {public}"
    )


def test_orchestration_package_init_stays_lean() -> None:
    """The orchestration package keeps its public API in submodules, not __init__."""
    import arnold.pipelines.megaplan.orchestration as pkg
    public = [n for n in dir(pkg) if not n.startswith("_")]
    assert "PhaseResult" not in public
    assert "run_parallel_critique" not in public


def test_audits_package_init_stays_lean() -> None:
    """The audits package keeps its public API in submodules, not __init__."""
    import arnold.pipelines.megaplan.audits as pkg
    public = [n for n in dir(pkg) if not n.startswith("_")]
    assert "run_quality_checks" not in public
    assert "validate_capabilities" not in public
