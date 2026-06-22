"""Append-only suite-run log helpers."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.orchestration.suite_runner import SuiteRunResult, _compute_code_hash

logger = logging.getLogger(__name__)

try:
    from arnold_pipelines.megaplan._core.io import clock  # type: ignore[attr-defined]
except ImportError:
    _now = time.time
else:
    _now = clock  # type: ignore[assignment]

KNOWN_STATUSES: frozenset[str] = frozenset({
    "passed", "failed", "runner_error", "not_applicable", "timeout",
})
REQUIRED_RECORD_FIELDS: frozenset[str] = frozenset({
    "run_id", "phase", "code_hash", "command", "duration",
    "collected", "collected_ids", "failures", "passes", "status",
    "raw_log_path", "collections_parse_ok", "ts",
})


def append_suite_run(plan_dir: Path, result: SuiteRunResult) -> None:
    ver_dir = plan_dir / "verification"
    ver_dir.mkdir(parents=True, exist_ok=True)
    record: dict[str, object] = {
        "run_id": result.run_id,
        "phase": result.phase,
        "code_hash": result.code_hash,
        "command": result.command,
        "duration": result.duration,
        "collected": result.collected,
        "collected_ids": result.collected_ids,
        "failures": result.failures,
        "passes": result.passes,
        "status": result.status,
        "raw_log_path": str(result.raw_log_path),
        "collections_parse_ok": result.collections_parse_ok,
        "ts": _now(),
    }
    path = ver_dir / "suite_runs.ndjson"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def latest_run_for_phase(plan_dir: Path, phase: str) -> dict[str, Any] | None:
    path = plan_dir / "verification" / "suite_runs.ndjson"
    if not path.is_file():
        return None
    latest: dict[str, Any] | None = None
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            try:
                record: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("phase") == phase:
                latest = record
    return latest


def _record_to_result(record: dict[str, Any]) -> SuiteRunResult:
    raw_log_path = record.get("raw_log_path", "")
    return SuiteRunResult(
        run_id=str(record["run_id"]),
        phase=str(record["phase"]),
        code_hash=str(record["code_hash"]),
        command=str(record["command"]),
        duration=float(record["duration"]),
        collected=int(record["collected"]),
        collected_ids=list(record["collected_ids"]),
        failures=list(record["failures"]),
        passes=list(record["passes"]),
        status=str(record["status"]),
        exit_code=record.get("exit_code"),
        raw_log_path=Path(raw_log_path) if raw_log_path else Path(),
        collections_parse_ok=bool(record.get("collections_parse_ok", False)),
    )


def freshness_skip(
    plan_dir: Path, current_code_hash: str, *, phase: str = "post_execute",
) -> SuiteRunResult | None:
    record = latest_run_for_phase(plan_dir, phase)
    if record is None:
        return None
    missing = REQUIRED_RECORD_FIELDS - set(record.keys())
    bad_shape = (
        missing
        or record.get("status") not in KNOWN_STATUSES
        or not isinstance(record.get("failures"), list)
        or not isinstance(record.get("collected_ids"), list)
    )
    if bad_shape:
        logger.warning(
            "freshness_skip: cached %s record %s failed validation "
            "(missing fields=%s); triggering fresh run",
            phase,
            record.get("run_id", "<unknown>"),
            sorted(missing),
        )
        return None
    if record["code_hash"] != current_code_hash:
        return None
    return _record_to_result(record)


def is_baseline_stale(
    plan_dir: Path,
    project_dir: Path,
    *,
    hash_paths: list[str] | None = None,
) -> bool:
    baseline_record = latest_run_for_phase(plan_dir, "baseline")
    if baseline_record is None:
        return False
    return baseline_record.get("code_hash") != _compute_code_hash(project_dir, paths=hash_paths)
