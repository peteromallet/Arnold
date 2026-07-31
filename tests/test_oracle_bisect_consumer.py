"""Retirement contract for the deleted M4 oracle-bisect consumer."""
from __future__ import annotations

from pathlib import Path

from arnold.conformance.deleted_surfaces import M6_DELETION_LIST
from arnold_pipelines.megaplan.chain.m3_dual_green import (
    REPO_ROOT,
    _FLAG_OFF_TARGETS,
    _FLAG_ON_TARGETS,
)


def test_oracle_bisect_tools_are_absent() -> None:
    assert not (REPO_ROOT / "tools" / "m4_oracle_bisect.py").exists()
    assert not (REPO_ROOT / "scripts" / "m4_oracle_bisect.py").exists()


def test_oracle_bisect_tools_have_canonical_archive_dispositions() -> None:
    dispositions = {
        item.surface: item.m5_outcome
        for item in M6_DELETION_LIST
        if item.surface in {"tools/m4_oracle_bisect.py", "scripts/m4_oracle_bisect.py"}
    }
    assert dispositions == {
        "tools/m4_oracle_bisect.py": "archive",
        "scripts/m4_oracle_bisect.py": "archive",
    }


def test_retired_consumer_is_not_an_active_dual_green_target() -> None:
    retired = REPO_ROOT / "tests" / "test_oracle_bisect_consumer.py"
    assert retired not in _FLAG_OFF_TARGETS
    assert retired not in _FLAG_ON_TARGETS
