"""M8A report-only fixture corpus.

Synthetic v2 fixtures that reproduce documented Transaction Spine and Strategy
Roadmap failure modes without treating historical M6/incident documents as
executable task graphs.  These fixtures are consumed by downstream compiler,
admission, splitting, and circuit tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_FIXTURE_DIR = Path(__file__).resolve().parent


def _load_json(name: str) -> dict[str, Any]:
    path = _FIXTURE_DIR / name
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def transaction_spine_serial() -> dict[str, Any]:
    """30-task / 29-edge fully-serial Transaction Spine synthetic v2 payload."""
    return _load_json("transaction-spine-serial.json")


def strategy_validation_tasks() -> dict[str, Any]:
    """Strategy-equivalent validation task v2 payload."""
    return _load_json("strategy-validation.json")


def complexity_7_8_9_cases() -> dict[str, Any]:
    """Complexity 7, 8, and 9 tasks with checkpoint contracts."""
    return _load_json("complexity-7-8-9.json")


def repeated_budget_failures() -> dict[str, Any]:
    """Repeated budget-failure shape."""
    return _load_json("repeated-budget-failures.json")


def six_task_rework() -> dict[str, Any]:
    """Six-task rework shape exceeding the five-task ceiling."""
    return _load_json("six-task-rework.json")


def documentation_fixture_hashes() -> dict[str, Any]:
    """Hash and limitation records for historical M6/incident evidence."""
    return _load_json("documentation-fixture-hashes.json")


__all__ = [
    "transaction_spine_serial",
    "strategy_validation_tasks",
    "complexity_7_8_9_cases",
    "repeated_budget_failures",
    "six_task_rework",
    "documentation_fixture_hashes",
]
