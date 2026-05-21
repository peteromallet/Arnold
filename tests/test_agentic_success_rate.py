"""Tests for scripts/agentic_success_rate.py.

Covers:
- CLI parsing (all --dry-run flags and options)
- Dry-run output determinism
- Fixture schema validation against tests/fixtures/agentic_success_rate.json
- Budget cap enforcement ($5 per category)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "agentic_success_rate.py"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "agentic_success_rate.json"


# ── CLI parsing tests ────────────────────────────────────────────────────────

def test_cli_help() -> None:
    """--help must print usage and return 0."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, f"--help failed: {proc.stderr}"
    assert "--dry-run" in proc.stdout, "Missing --dry-run in help output"
    assert "--model" in proc.stdout, "Missing --model in help output"
    assert "--max-budget" in proc.stdout, "Missing --max-budget in help output"
    assert "--category" in proc.stdout, "Missing --category in help output"
    assert "--json" in proc.stdout, "Missing --json in help output"


def test_cli_dry_run_default_output() -> None:
    """--dry-run with no other flags must produce human-readable output."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--dry-run"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, f"--dry-run failed: {proc.stderr}"
    assert "Agentic success rate" in proc.stdout, "Missing success rate header"
    assert "dry-run" in proc.stdout.lower(), "Missing dry-run indicator"


def test_cli_dry_run_json_output() -> None:
    """--dry-run --json must produce valid JSON."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--dry-run", "--json"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, f"--dry-run --json failed: {proc.stderr}"

    # Parse JSON output
    result = json.loads(proc.stdout)

    # Check top-level schema
    assert "model" in result
    assert result["dry_run"] is True
    assert "max_budget_per_category" in result
    assert "total_tasks" in result
    assert "successes" in result
    assert "success_rate" in result
    assert "budgets" in result
    assert "spent" in result
    assert "results" in result

    # Must have 4 tasks
    assert result["total_tasks"] == 4, f"Expected 4 tasks, got {result['total_tasks']}"

    # Each result has required fields
    for task_result in result["results"]:
        assert "task_id" in task_result
        assert "category" in task_result
        assert "description" in task_result
        assert "status" in task_result
        assert "success" in task_result
        assert "detail" in task_result
        assert "success_metric" in task_result
        assert "duration_ms" in task_result
        assert "dry_run" in task_result


def test_cli_dry_run_json_is_deterministic() -> None:
    """--dry-run --json must produce identical output across two runs."""
    def run_json():
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--dry-run", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        assert proc.returncode == 0
        return json.loads(proc.stdout)

    result1 = run_json()
    result2 = run_json()

    # Strip timing-dependent fields before comparison
    def _normalize(r):
        for task in r.get("results", []):
            task.pop("duration_ms", None)
        return r

    assert _normalize(result1) == _normalize(result2), (
        "Dry-run output is not deterministic"
    )


def test_cli_category_filter() -> None:
    """--category tweak_and_run must only run that one task."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--dry-run", "--json", "--category", "tweak_and_run"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0
    result = json.loads(proc.stdout)
    assert result["total_tasks"] == 1, f"Expected 1 task, got {result['total_tasks']}"
    assert result["results"][0]["category"] == "tweak_and_run"


def test_cli_invalid_category_rejected() -> None:
    """Invalid --category must be rejected by argparse."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--dry-run", "--category", "nonexistent_category"],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode != 0, "Invalid category should be rejected"


def test_cli_custom_budget() -> None:
    """--max-budget 3.00 must be reflected in output."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--dry-run", "--json", "--max-budget", "3.00"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0
    result = json.loads(proc.stdout)
    assert result["max_budget_per_category"] == 3.0, (
        f"Budget mismatch: {result['max_budget_per_category']}"
    )
    # All budgets in `budgets` dict should be 3.00
    for category, budget in result["budgets"].items():
        assert budget == 3.0, f"Budget for {category} is {budget}, expected 3.0"


# ── Budget cap enforcement ───────────────────────────────────────────────────

def test_default_budget_is_5_dollars() -> None:
    """Default max budget must be $5.00 per category."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--dry-run", "--json"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
    )
    result = json.loads(proc.stdout)
    assert result["max_budget_per_category"] == 5.00, (
        f"Default budget is ${result['max_budget_per_category']}, expected $5.00"
    )


def test_dry_run_spends_zero() -> None:
    """--dry-run must not record any spending."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--dry-run", "--json"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
    )
    result = json.loads(proc.stdout)
    for category, spent in result["spent"].items():
        assert spent == 0.0, f"Dry-run spent ${spent} for {category}, expected $0.00"


def test_dry_run_all_tasks_succeed() -> None:
    """In --dry-run mode, all 4 tasks must report success."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--dry-run", "--json"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
    )
    result = json.loads(proc.stdout)
    assert result["success_rate"] == 1.0, (
        f"Dry-run success rate is {result['success_rate']}, expected 1.0"
    )
    for task in result["results"]:
        assert task["success"], f"Task {task['task_id']} failed in dry-run: {task['detail']}"


# ── Fixture generation and schema validation ─────────────────────────────────

def test_fixture_file_exists() -> None:
    """tests/fixtures/agentic_success_rate.json must exist."""
    assert FIXTURE_PATH.is_file(), (
        f"Fixture file missing: {FIXTURE_PATH}\n"
        f"Generate it with: python scripts/agentic_success_rate.py --dry-run --json > {FIXTURE_PATH}"
    )


def test_fixture_matches_dry_run_schema() -> None:
    """The fixture must have the same schema as a fresh --dry-run output."""
    # Generate fresh dry-run output
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--dry-run", "--json"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
    )
    fresh = json.loads(proc.stdout)

    # Load fixture
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    # Compare top-level keys
    fresh_keys = set(fresh.keys())
    fixture_keys = set(fixture.keys())
    assert fresh_keys == fixture_keys, (
        f"Top-level keys differ: fresh only={fresh_keys - fixture_keys}, "
        f"fixture only={fixture_keys - fresh_keys}"
    )

    # Compare result entry keys
    for i, (fresh_task, fixture_task) in enumerate(zip(fresh["results"], fixture["results"])):
        fresh_task_keys = set(fresh_task.keys())
        fixture_task_keys = set(fixture_task.keys())
        assert fresh_task_keys == fixture_task_keys, (
            f"Result[{i}] keys differ: fresh only={fresh_task_keys - fixture_task_keys}, "
            f"fixture only={fixture_task_keys - fresh_task_keys}"
        )


def test_fixture_has_four_tasks() -> None:
    """The fixture must record results for all 4 tasks."""
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert fixture["total_tasks"] == 4
    assert len(fixture["results"]) == 4

    categories = {r["category"] for r in fixture["results"]}
    assert categories == {"tweak_and_run", "json_to_template", "doctor_all", "node_splice"}, (
        f"Unexpected categories: {categories}"
    )
