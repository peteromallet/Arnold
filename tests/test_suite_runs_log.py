"""Tests for the append-only ndjson log, freshness cache, and stale-baseline
detection in ``megaplan.orchestration.suite_runner``.

Covers:
- ``append_suite_run`` writes one line per record (ndjson).
- ``latest_run_for_phase`` returns the most recent matching record.
- ``freshness_skip`` returns cached ``SuiteRunResult`` on hash match,
  ``None`` on mismatch.
- Corrupted record (missing ``status``, non-list ``failures``) triggers
  ``None`` + structured warning.
- ``is_baseline_stale`` detects stale baselines and returns ``False``
  when no baseline exists.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from megaplan.orchestration.suite_runner import (
    SuiteRunResult,
    _compute_code_hash,
    append_suite_run,
    freshness_skip,
    is_baseline_stale,
    latest_run_for_phase,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(**overrides: object) -> SuiteRunResult:
    """Build a SuiteRunResult with reasonable defaults."""
    defaults: dict[str, object] = {
        "run_id": "abc123def456",
        "phase": "post_execute",
        "command": "pytest --tb=no -q --no-header -rN",
        "duration": 1.5,
        "collected": 5,
        "collected_ids": [
            "tests/test_a.py::test_pass",
            "tests/test_a.py::test_fail",
        ],
        "failures": ["tests/test_a.py::test_fail"],
        "passes": ["tests/test_a.py::test_pass"],
        "status": "failed",
        "exit_code": 1,
        "raw_log_path": Path("/tmp/raw_abc123def456.log"),
        "code_hash": "sha256:deadbeef",
        "collections_parse_ok": True,
    }
    defaults.update(overrides)
    return SuiteRunResult(**{k: v for k, v in defaults.items()})  # type: ignore[arg-type]


def _write_raw_ndjson_line(path: Path, line: str) -> None:
    """Write a single raw line (no validation) to the ndjson log."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# ---------------------------------------------------------------------------
# append_suite_run — one line per record
# ---------------------------------------------------------------------------


def test_append_suite_run_writes_one_line(tmp_path: Path) -> None:
    """append_suite_run writes exactly one ndjson line."""
    plan_dir = tmp_path / "plan"
    result = _make_result(run_id="run1")

    append_suite_run(plan_dir, result)

    ndjson_path = plan_dir / "verification" / "suite_runs.ndjson"
    assert ndjson_path.is_file()

    lines = ndjson_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["run_id"] == "run1"
    assert record["phase"] == "post_execute"
    assert "ts" in record


def test_append_suite_run_appends_not_overwrites(tmp_path: Path) -> None:
    """Multiple calls to append_suite_run produce multiple lines."""
    plan_dir = tmp_path / "plan"
    r1 = _make_result(run_id="run1")
    r2 = _make_result(run_id="run2", phase="baseline")

    append_suite_run(plan_dir, r1)
    append_suite_run(plan_dir, r2)

    ndjson_path = plan_dir / "verification" / "suite_runs.ndjson"
    lines = ndjson_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2

    records = [json.loads(line) for line in lines]
    assert records[0]["run_id"] == "run1"
    assert records[1]["run_id"] == "run2"
    assert records[1]["phase"] == "baseline"


def test_append_suite_run_includes_all_required_fields(tmp_path: Path) -> None:
    """Every appended record has all listed fields."""
    plan_dir = tmp_path / "plan"
    result = _make_result()

    append_suite_run(plan_dir, result)

    ndjson_path = plan_dir / "verification" / "suite_runs.ndjson"
    record = json.loads(ndjson_path.read_text(encoding="utf-8").strip())

    required = {
        "run_id", "phase", "code_hash", "command", "duration",
        "collected", "collected_ids", "failures", "passes", "status",
        "raw_log_path", "collections_parse_ok", "ts",
    }
    assert required <= set(record.keys())


# ---------------------------------------------------------------------------
# latest_run_for_phase
# ---------------------------------------------------------------------------


def test_latest_run_for_phase_returns_most_recent(tmp_path: Path) -> None:
    """latest_run_for_phase returns the last matching record."""
    plan_dir = tmp_path / "plan"
    ver_dir = plan_dir / "verification"
    ver_dir.mkdir(parents=True, exist_ok=True)
    ndjson_path = ver_dir / "suite_runs.ndjson"

    _write_raw_ndjson_line(ndjson_path, json.dumps({
        "run_id": "old", "phase": "post_execute", "code_hash": "sha256:aaa",
        "command": "pytest", "duration": 1.0, "collected": 5,
        "collected_ids": [], "failures": [], "passes": [], "status": "passed",
        "raw_log_path": "/tmp/old.log", "collections_parse_ok": True, "ts": 1000,
    }))
    _write_raw_ndjson_line(ndjson_path, json.dumps({
        "run_id": "new", "phase": "post_execute", "code_hash": "sha256:bbb",
        "command": "pytest", "duration": 2.0, "collected": 5,
        "collected_ids": [], "failures": [], "passes": [], "status": "passed",
        "raw_log_path": "/tmp/new.log", "collections_parse_ok": True, "ts": 2000,
    }))

    latest = latest_run_for_phase(plan_dir, "post_execute")
    assert latest is not None
    assert latest["run_id"] == "new"


def test_latest_run_for_phase_no_match_returns_none(tmp_path: Path) -> None:
    """Returns None when no record matches the phase."""
    plan_dir = tmp_path / "plan"
    ver_dir = plan_dir / "verification"
    ver_dir.mkdir(parents=True, exist_ok=True)
    ndjson_path = ver_dir / "suite_runs.ndjson"

    _write_raw_ndjson_line(ndjson_path, json.dumps({
        "run_id": "r1", "phase": "baseline", "code_hash": "sha256:aaa",
        "command": "pytest", "duration": 1.0, "collected": 5,
        "collected_ids": [], "failures": [], "passes": [], "status": "passed",
        "raw_log_path": "/tmp/r1.log", "collections_parse_ok": True, "ts": 1000,
    }))

    result = latest_run_for_phase(plan_dir, "post_execute")
    assert result is None


def test_latest_run_for_phase_no_file_returns_none(tmp_path: Path) -> None:
    """Returns None when suite_runs.ndjson does not exist."""
    plan_dir = tmp_path / "plan"
    result = latest_run_for_phase(plan_dir, "post_execute")
    assert result is None


# ---------------------------------------------------------------------------
# freshness_skip — hash match returns cached result
# ---------------------------------------------------------------------------


def test_freshness_skip_returns_cached_result_on_hash_match(tmp_path: Path) -> None:
    """When code_hash matches, freshness_skip returns a SuiteRunResult."""
    plan_dir = tmp_path / "plan"
    ver_dir = plan_dir / "verification"
    ver_dir.mkdir(parents=True, exist_ok=True)
    ndjson_path = ver_dir / "suite_runs.ndjson"

    _write_raw_ndjson_line(ndjson_path, json.dumps({
        "run_id": "cached", "phase": "post_execute", "code_hash": "sha256:match",
        "command": "pytest", "duration": 1.5, "collected": 3,
        "collected_ids": ["t1", "t2"], "failures": ["t1"],
        "passes": ["t2"], "status": "failed",
        "raw_log_path": "/tmp/cached.log", "collections_parse_ok": True, "ts": 1000,
    }))

    result = freshness_skip(plan_dir, "sha256:match")
    assert result is not None
    assert result.run_id == "cached"
    assert result.status == "failed"
    assert result.failures == ["t1"]
    assert result.collected_ids == ["t1", "t2"]


def test_freshness_skip_returns_none_on_hash_mismatch(tmp_path: Path) -> None:
    """When code_hash differs, freshness_skip returns None."""
    plan_dir = tmp_path / "plan"
    ver_dir = plan_dir / "verification"
    ver_dir.mkdir(parents=True, exist_ok=True)
    ndjson_path = ver_dir / "suite_runs.ndjson"

    _write_raw_ndjson_line(ndjson_path, json.dumps({
        "run_id": "cached", "phase": "post_execute", "code_hash": "sha256:old",
        "command": "pytest", "duration": 1.5, "collected": 3,
        "collected_ids": [], "failures": [], "passes": [], "status": "passed",
        "raw_log_path": "/tmp/cached.log", "collections_parse_ok": True, "ts": 1000,
    }))

    result = freshness_skip(plan_dir, "sha256:new")
    assert result is None


def test_freshness_skip_returns_none_when_no_record(tmp_path: Path) -> None:
    """When no post_execute record exists, returns None."""
    plan_dir = tmp_path / "plan"
    result = freshness_skip(plan_dir, "sha256:any")
    assert result is None


# ---------------------------------------------------------------------------
# freshness_skip — corrupted records
# ---------------------------------------------------------------------------


def test_freshness_skip_missing_status_returns_none(tmp_path: Path, caplog) -> None:
    """Record missing 'status' triggers None + structured warning."""
    plan_dir = tmp_path / "plan"
    ver_dir = plan_dir / "verification"
    ver_dir.mkdir(parents=True, exist_ok=True)
    ndjson_path = ver_dir / "suite_runs.ndjson"

    _write_raw_ndjson_line(ndjson_path, json.dumps({
        "run_id": "bad", "phase": "post_execute", "code_hash": "sha256:match",
        "command": "pytest", "duration": 1.5, "collected": 3,
        "collected_ids": [], "failures": [], "passes": [],
        # "status" intentionally missing
        "raw_log_path": "/tmp/bad.log", "collections_parse_ok": True, "ts": 1000,
    }))

    with caplog.at_level(logging.WARNING):
        result = freshness_skip(plan_dir, "sha256:match")

    assert result is None
    assert "freshness_skip" in caplog.text
    assert "status" in caplog.text.lower() or "missing fields" in caplog.text.lower()


def test_freshness_skip_non_list_failures_returns_none(tmp_path: Path, caplog) -> None:
    """Record with non-list 'failures' triggers None + warning."""
    plan_dir = tmp_path / "plan"
    ver_dir = plan_dir / "verification"
    ver_dir.mkdir(parents=True, exist_ok=True)
    ndjson_path = ver_dir / "suite_runs.ndjson"

    _write_raw_ndjson_line(ndjson_path, json.dumps({
        "run_id": "bad", "phase": "post_execute", "code_hash": "sha256:match",
        "command": "pytest", "duration": 1.5, "collected": 3,
        "collected_ids": [], "failures": "not_a_list",
        "passes": [], "status": "passed",
        "raw_log_path": "/tmp/bad.log", "collections_parse_ok": True, "ts": 1000,
    }))

    with caplog.at_level(logging.WARNING):
        result = freshness_skip(plan_dir, "sha256:match")

    assert result is None
    assert "freshness_skip" in caplog.text


def test_freshness_skip_non_list_collected_ids_returns_none(tmp_path: Path, caplog) -> None:
    """Record with non-list 'collected_ids' triggers None + warning."""
    plan_dir = tmp_path / "plan"
    ver_dir = plan_dir / "verification"
    ver_dir.mkdir(parents=True, exist_ok=True)
    ndjson_path = ver_dir / "suite_runs.ndjson"

    _write_raw_ndjson_line(ndjson_path, json.dumps({
        "run_id": "bad", "phase": "post_execute", "code_hash": "sha256:match",
        "command": "pytest", "duration": 1.5, "collected": 3,
        "collected_ids": 42,  # not a list
        "failures": [], "passes": [], "status": "passed",
        "raw_log_path": "/tmp/bad.log", "collections_parse_ok": True, "ts": 1000,
    }))

    with caplog.at_level(logging.WARNING):
        result = freshness_skip(plan_dir, "sha256:match")

    assert result is None
    assert "freshness_skip" in caplog.text


def test_freshness_skip_unknown_status_returns_none(tmp_path: Path, caplog) -> None:
    """Record with unknown status value triggers None + warning."""
    plan_dir = tmp_path / "plan"
    ver_dir = plan_dir / "verification"
    ver_dir.mkdir(parents=True, exist_ok=True)
    ndjson_path = ver_dir / "suite_runs.ndjson"

    _write_raw_ndjson_line(ndjson_path, json.dumps({
        "run_id": "bad", "phase": "post_execute", "code_hash": "sha256:match",
        "command": "pytest", "duration": 1.5, "collected": 3,
        "collected_ids": [], "failures": [], "passes": [],
        "status": "bogus_status",
        "raw_log_path": "/tmp/bad.log", "collections_parse_ok": True, "ts": 1000,
    }))

    with caplog.at_level(logging.WARNING):
        result = freshness_skip(plan_dir, "sha256:match")

    assert result is None
    assert "freshness_skip" in caplog.text


# ---------------------------------------------------------------------------
# is_baseline_stale — stale-baseline detection
# ---------------------------------------------------------------------------


def test_is_baseline_stale_returns_true_when_hash_mismatches(tmp_path: Path) -> None:
    """When baseline code_hash differs from current, returns True."""
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".git").mkdir()  # git primary path will run (may fail gracefully)

    ver_dir = plan_dir / "verification"
    ver_dir.mkdir(parents=True, exist_ok=True)
    ndjson_path = ver_dir / "suite_runs.ndjson"

    # Write a baseline record with a hash that will NOT match
    _write_raw_ndjson_line(ndjson_path, json.dumps({
        "run_id": "bl1", "phase": "baseline", "code_hash": "sha256:old_baseline",
        "command": "pytest", "duration": 1.0, "collected": 5,
        "collected_ids": [], "failures": [], "passes": [], "status": "passed",
        "raw_log_path": "/tmp/bl1.log", "collections_parse_ok": True, "ts": 1000,
    }))

    assert is_baseline_stale(plan_dir, project_dir) is True


def test_is_baseline_stale_returns_false_when_hash_matches(tmp_path: Path) -> None:
    """When baseline code_hash matches current, returns False."""
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    # Compute the actual current hash
    current_hash = _compute_code_hash(project_dir)

    ver_dir = plan_dir / "verification"
    ver_dir.mkdir(parents=True, exist_ok=True)
    ndjson_path = ver_dir / "suite_runs.ndjson"

    _write_raw_ndjson_line(ndjson_path, json.dumps({
        "run_id": "bl1", "phase": "baseline", "code_hash": current_hash,
        "command": "pytest", "duration": 1.0, "collected": 5,
        "collected_ids": [], "failures": [], "passes": [], "status": "passed",
        "raw_log_path": "/tmp/bl1.log", "collections_parse_ok": True, "ts": 1000,
    }))

    assert is_baseline_stale(plan_dir, project_dir) is False


def test_is_baseline_stale_returns_false_when_no_baseline(tmp_path: Path) -> None:
    """When no baseline record exists, returns False (not stale, just absent)."""
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    assert is_baseline_stale(plan_dir, project_dir) is False
