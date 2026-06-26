from __future__ import annotations

import time
import json
from pathlib import Path
from typing import Any, Callable, Literal

from arnold_pipelines.megaplan.orchestration.completion_contract import compute_delta
from arnold_pipelines.megaplan.orchestration import suite_runner
from arnold_pipelines.megaplan.orchestration.suite_runner import SuiteRunResult

FULL_SUITE_BACKSTOP_MODE_OFF = "off"
FULL_SUITE_BACKSTOP_MODE_SHADOW = "shadow"
FULL_SUITE_BACKSTOP_MODE_ENFORCE = "enforce"

FullSuiteBackstopMode = Literal["off", "shadow", "enforce"]


def normalize_full_suite_backstop_mode(value: Any) -> FullSuiteBackstopMode:
    """Return a supported full-suite backstop mode, defaulting to shadow."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {
            FULL_SUITE_BACKSTOP_MODE_OFF,
            FULL_SUITE_BACKSTOP_MODE_SHADOW,
            FULL_SUITE_BACKSTOP_MODE_ENFORCE,
        }:
            return normalized  # type: ignore[return-value]
    return FULL_SUITE_BACKSTOP_MODE_SHADOW


def _sorted_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(item for item in value if isinstance(item, str))


def _load_baseline(value: Path | dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, Path):
        try:
            import json

            raw = json.loads(value.read_text(encoding="utf-8"))
        except Exception:
            return None
        return raw if isinstance(raw, dict) else None
    return value if isinstance(value, dict) else None


def _collected_ids_from_result(result: SuiteRunResult) -> list[str]:
    collected = _sorted_strings(result.collected_ids)
    if collected:
        return collected
    return sorted(set(result.failures) | set(result.passes))


def _suite_result_from_backstop_dict(
    data: dict[str, Any],
    *,
    phase: str,
) -> SuiteRunResult | None:
    failures = _sorted_strings(data.get("failing_tests"))
    collected_ids = _sorted_strings(data.get("collected_ids"))
    if not collected_ids:
        collected_ids = list(failures)
    if "failing_tests" not in data:
        return None
    status = "failed" if failures else "passed"
    return SuiteRunResult(
        run_id="full-suite-backstop-json",
        phase=phase,
        command=str(data.get("command") or ""),
        duration=float(data.get("duration_s") or 0.0),
        collected=len(collected_ids),
        collected_ids=collected_ids,
        failures=failures,
        passes=[],
        status=status,
        exit_code=1 if failures else 0,
        raw_log_path=Path(str(data.get("raw_log_path") or "")),
        code_hash=str(data.get("captured_at_sha") or data.get("code_hash") or ""),
        collections_parse_ok=True,
    )


def build_full_suite_baseline(
    result: dict[str, Any],
    *,
    captured_at_sha: str | None,
    milestone: str,
    captured_at: str | None = None,
) -> dict[str, Any] | None:
    """Return the persisted baseline payload for a completed backstop result."""
    if result.get("status") not in {"passed", "failed"}:
        return None
    failing_tests = _sorted_strings(result.get("failing_tests"))
    collected_ids = _sorted_strings(result.get("collected_ids"))
    if not collected_ids:
        collected_ids = list(failing_tests)
    baseline: dict[str, Any] = {
        "failing_tests": failing_tests,
        "collected_ids": collected_ids,
        "captured_at_sha": captured_at_sha,
        "milestone": milestone,
    }
    if captured_at is not None:
        baseline["captured_at"] = captured_at
    return baseline


def run_full_suite_backstop(
    plan_dir: Path,
    project_dir: Path,
    config: dict[str, Any],
    *,
    baseline: Path | dict[str, Any] | None = None,
    writer: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run one suite backstop and return a JSON-serializable summary.

    The caller's config is never mutated. The copied config preserves an
    explicit ``test_command`` or backfills one from ``finalize.json``. If no
    scoped/recorded command exists, the backstop records ``not_applicable`` and
    does not invoke pytest; it must never silently fall back to a bare full
    suite.
    """
    del writer
    full_config = dict(config)
    full_config["test_selection"] = full_config.get("test_selection") or "recorded"
    full_config["plan_dir"] = str(plan_dir)
    if not full_config.get("test_command"):
        command = _recorded_test_command_from_finalize(plan_dir)
        if command:
            full_config["test_command"] = command
    if not full_config.get("test_command"):
        return _not_applicable_result(
            "no recorded test_command in config or finalize.json; not running bare full-suite fallback"
        )

    timeout = full_config.get("test_baseline_timeout", 900)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        timeout = 900
    idle_timeout = full_config.get("test_idle_timeout")
    if not isinstance(idle_timeout, (int, float)) or idle_timeout <= 0:
        idle_timeout = None

    baseline_payload = _load_baseline(baseline)
    baseline_failures = (
        _sorted_strings(baseline_payload.get("failing_tests"))
        if isinstance(baseline_payload, dict)
        else []
    )
    delta_defaults: dict[str, Any] = {
        "newly_failing": [],
        "deleted_tests": [],
        "baseline_failing_count": len(baseline_failures),
        "current_failing_count": 0,
        "delta_computed": False,
    }

    try:
        result = suite_runner.run_suite(
            project_dir,
            full_config,
            phase="full_suite_backstop",
            deadline_seconds=time.monotonic() + float(timeout),
            idle_seconds=float(idle_timeout) if idle_timeout is not None else None,
        )
    except Exception as exc:
        return {
            "status": "error",
            "passed": None,
            "failed": None,
            "failing_tests": None,
            "command": "",
            "duration_s": None,
            "ran": False,
            "note": f"{type(exc).__name__}: {exc}",
            **delta_defaults,
        }

    if result.status == "passed":
        status = "passed"
    elif result.status == "failed":
        status = "failed"
    else:
        status = "error"
    failures = sorted(result.failures)
    collected_ids = _collected_ids_from_result(result)
    summary: dict[str, Any] = {
        "status": status,
        "passed": len(result.passes),
        "failed": len(failures),
        "failing_tests": failures,
        "collected_ids": collected_ids,
        "command": result.command,
        "duration_s": float(result.duration),
        "ran": True,
        "note": "" if status == "passed" else f"suite status={result.status}",
        **{
            **delta_defaults,
            "current_failing_count": len(failures),
        },
    }
    if status == "error":
        return summary

    baseline_result = (
        _suite_result_from_backstop_dict(baseline_payload, phase="full_suite_baseline")
        if isinstance(baseline_payload, dict)
        else None
    )
    if baseline_result is None:
        return summary

    try:
        delta = compute_delta(baseline_result, result)
    except Exception as exc:
        summary["note"] = f"{summary['note']}; delta error={type(exc).__name__}: {exc}".strip("; ")
        return summary

    summary.update(
        {
            "newly_failing": list(delta.newly_failing),
            "deleted_tests": list(delta.deleted_tests),
            "baseline_failing_count": len(baseline_result.failures),
            "current_failing_count": len(failures),
            "delta_computed": True,
        }
    )
    return summary


def _recorded_test_command_from_finalize(plan_dir: Path) -> str | None:
    finalize_path = plan_dir / "finalize.json"
    try:
        finalize = json.loads(finalize_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(finalize, dict):
        return None
    baseline_command = finalize.get("baseline_test_command")
    test_selection = finalize.get("test_selection")
    selected_command = (
        test_selection.get("command_override")
        if isinstance(test_selection, dict)
        else None
    )
    for candidate in (baseline_command, selected_command):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _not_applicable_result(note: str) -> dict[str, Any]:
    return {
        "status": "not_applicable",
        "passed": None,
        "failed": None,
        "failing_tests": [],
        "collected_ids": [],
        "command": "",
        "duration_s": None,
        "ran": False,
        "note": note,
        "newly_failing": [],
        "deleted_tests": [],
        "baseline_failing_count": 0,
        "current_failing_count": 0,
        "delta_computed": False,
    }


def evaluate_full_suite_backstop(result: dict[str, Any], mode: str) -> dict[str, Any]:
    """Evaluate whether a full-suite backstop result blocks milestone advance."""
    normalized = normalize_full_suite_backstop_mode(mode)
    if normalized == FULL_SUITE_BACKSTOP_MODE_OFF:
        return {
            "blocks": False,
            "reason": "full_suite_backstop_mode=off: backstop disabled",
            "mode": normalized,
        }
    if normalized == FULL_SUITE_BACKSTOP_MODE_SHADOW:
        return {
            "blocks": False,
            "reason": "full_suite_backstop_mode=shadow: recorded only",
            "mode": normalized,
        }
    if not isinstance(result, dict) or result.get("delta_computed") is not True:
        return {
            "blocks": True,
            "reason": (
                "backstop could not verify (uncertain) — refusing to advance "
                "under enforce"
            ),
            "mode": normalized,
        }
    newly_failing = _sorted_strings(result.get("newly_failing"))
    deleted_tests = _sorted_strings(result.get("deleted_tests"))
    if newly_failing or deleted_tests:
        return {
            "blocks": True,
            "reason": "full_suite_backstop_mode=enforce: full-suite delta regressed",
            "mode": normalized,
        }
    return {
        "blocks": False,
        "reason": "full_suite_backstop_mode=enforce: full-suite delta clean",
        "mode": normalized,
    }
