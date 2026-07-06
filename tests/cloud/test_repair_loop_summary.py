from __future__ import annotations

import json
from pathlib import Path

from tests.cloud.test_watchdog_wrappers import _extract_repair_program, _run_embedded_python


def test_render_failure_summary_prefers_authoritative_live_plan_failure_shape(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps(
            {
                "initial_facts": {},
                "iterations": [
                    {
                        "attempt_id": 4,
                        "failure_classification": "authentication_or_credentials_error",
                        "plan_latest_failure": {
                            "kind": "execution_blocked",
                            "phase": "execute",
                            "current_state": "blocked",
                            "recorded_at": "2026-07-06T19:19:31Z",
                            "message": "execute reported prerequisite-blocked tasks: T4",
                        },
                        "stale_state": {
                            "classification": "LIVE FAILURE",
                            "summary": "latest_failure is recent; no successful event was found after it",
                        },
                        "raw_failure_signals": [
                            "latest_failure.kind: execution_blocked",
                            "latest_failure.message: execute reported prerequisite-blocked tasks: T4",
                            "chain log: missing credentials from stale verifier warning",
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    summary_program = _extract_repair_program(
        "render_failure_summary",
        "python3 - \"$data_path\" <<'PY'",
    )
    result = _run_embedded_python(summary_program, str(data_path))

    assert result.returncode == 0, result.stderr
    summary = result.stdout
    assert "- failure classification: blocked_state_or_recovery_error" in summary
    assert "- latest_failure: kind=execution_blocked recorded_at=2026-07-06T19:19:31Z" in summary
    assert (
        "- recommended repair action: investigate the blocked execute task; "
        "fix the task-level target code or plan state when the blocker is not an Arnold engine bug"
    ) in summary
    assert "dispatch dev-fix to fix the Arnold source root cause" not in summary
