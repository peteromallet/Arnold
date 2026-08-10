"""Golden artifact path fixtures.

Each fixture file describes one of the three canonical Megaplan artifact
paths defined in docs/arnold/megaplan-artifact-manifest.md: **proceed**,
**review-needs-rework**, and **execute failure/resume**.

These are machine-readable representations of the artifact-path tables,
used by ``test_native_golden_manifest.py`` to validate schema keys,
expected files, receipt metrics, warrant source refs, and D1/D5/D6/D8/D10
obligation coverage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_FIXTURE_DIR = Path(__file__).resolve().parent

ARTIFACT_PATH_NAMES: tuple[str, ...] = (
    "proceed",
    "review_needs_rework",
    "execute_failure_resume",
)

_REQUIRED_KEYS: frozenset[str] = frozenset({
    "schema",
    "artifact_path",
    "description",
    "stages",
    "native_trace_files",
    "obligated_scenarios",
})

_STAGE_REQUIRED_KEYS: frozenset[str] = frozenset({
    "stage",
    "artifacts",
    "content_type",
    "schema_keys",
    "warrant_source_ref",
})


def load_artifact_path_fixture(name: str) -> dict[str, Any]:
    """Load a golden-artifact path fixture by name (without ``.json``)."""
    path = _FIXTURE_DIR / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Golden artifact fixture not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_all_artifact_path_fixtures() -> list[dict[str, Any]]:
    """Return all three golden-artifact path fixtures."""
    return [load_artifact_path_fixture(n) for n in ARTIFACT_PATH_NAMES]
