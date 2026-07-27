"""Focused tests for the intentionally small three-hour fixer."""

from __future__ import annotations

import fcntl
import json
import stat
from datetime import datetime, timezone
from pathlib import Path

from arnold_pipelines.megaplan.cloud import simple_fixer


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor"
SYSTEMD = ROOT / "arnold_pipelines/megaplan/cloud/systemd"


def _marker(
    marker_dir: Path,
    session: str,
    workspace: Path,
    **extra: object,
) -> Path:
    marker_dir.mkdir(parents=True, exist_ok=True)
    path = marker_dir / f"{session}.json"
    payload: dict[str, object] = {
        "session": session,
        "workspace": str(workspace),
        "run_kind": "chain",
        "remote_spec": str(workspace / ".megaplan/initiatives/demo/chain.yaml"),
    }
    payload.update(extra)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _fake_codex(tmp_path: Path) -> tuple[Path, Path, Path]:
    calls = tmp_path / "calls.txt"
    prompts = tmp_path / "prompts.txt"
    binary = tmp_path / "codex"
    binary.write_text(
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
prompt = sys.stdin.read()
calls = Path(os.environ["FAKE_CODEX_CALLS"])
prompts = Path(os.environ["FAKE_CODEX_PROMPTS"])
calls.write_text(calls.read_text() + "call\\n" if calls.exists() else "call\\n")
with prompts.open("a", encoding="utf-8") as handle:
    handle.write(prompt + "\\n---PROMPT---\\n")
marker = os.environ.get("FAKE_CODEX_MUTATE_MARKER")
if marker:
    path = Path(marker)
    payload = json.loads(path.read_text())
    payload["error"] = "new evidence after repair"
    payload["iteration"] = int(payload.get("iteration", 0)) + 1
    path.write_text(json.dumps(payload))
out = Path(args[args.index("--output-last-message") + 1])
out.write_text(json.dumps({"outcomes": [
    {"session": os.environ.get("FAKE_SESSION", "storm"),
     "result": "fixed", "summary": "fixed", "evidence": ["fresh state"]}
]}))
print(json.dumps({"type": "result", "message": "token=super-secret-value-12345"}))
""",
        encoding="utf-8",
    )
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    return binary, calls, prompts


def _args(
    tmp_path: Path,
    marker_dir: Path,
    binary: Path,
) -> object:
    return simple_fixer.build_parser().parse_args(
        [
            "--marker-dir",
            str(marker_dir),
            "--report-dir",
            str(tmp_path / "reports"),
            "--state-file",
            str(tmp_path / "attempts.json"),
            "--lock-file",
            str(tmp_path / "fixer.lock"),
            "--source-root",
            str(ROOT),
            "--codex-bin",
            str(binary),
            "--timeout",
            "30",
        ]
    )


def _latest(tmp_path: Path) -> dict[str, object]:
    return json.loads((tmp_path / "reports/latest.json").read_text(encoding="utf-8"))


def test_wrapper_is_only_container_trampoline_and_single_runner() -> None:
    text = WRAPPER.read_text(encoding="utf-8")
    assert "-m arnold_pipelines.megaplan.cloud.simple_fixer" in text
    assert "arnold-watchdog" not in text
    assert "arnold-repair-trigger" not in text
    assert "launch_hermes_agent" not in text
    assert "managed_agent" not in text
    assert ".cloud-hot-env" not in text
    assert "CLOUD_WATCHDOG_ARNOLD_SRC" not in text
    assert 'MEGAPLAN_SIMPLE_FIXER_SOURCE_ROOT:-/workspace/arnold' in text


def test_systemd_keeps_three_hour_cadence_and_bounds_process_tree() -> None:
    timer = (SYSTEMD / "megaplan-progress-audit.timer").read_text(encoding="utf-8")
    service = (SYSTEMD / "megaplan-progress-audit.service").read_text(encoding="utf-8")
    assert "OnUnitActiveSec=3h" in timer
    assert "RuntimeMaxSec=2h30m" in service
    assert "KillMode=control-group" in service
    assert "TimeoutStopSec=30s" in service


def test_discovery_preserves_completed_and_explicit_operator_pause(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    _marker(marker_dir, "complete", workspace, status="completed")
    _marker(
        marker_dir,
        "complete-with-retained-plan",
        workspace,
        last_state="done",
        current_plan_name="m10",
    )
    _marker(
        marker_dir,
        "paused",
        workspace,
        status="running",
        operator_pause={"active": True, "reason": "human chose pause"},
    )
    _marker(marker_dir, "active", workspace, status="running")
    _marker(
        marker_dir,
        "human-wait",
        workspace,
        status="awaiting_human",
        needs_human={"present": True, "gate_type": "product_decision"},
    )

    snapshots = {item.session: item for item in simple_fixer.discover(marker_dir)}

    assert snapshots["complete"].disposition == "completed"
    assert snapshots["paused"].disposition == "paused"
    assert snapshots["active"].disposition == "nonterminal"
    assert snapshots["complete-with-retained-plan"].disposition == "completed"
    assert snapshots["human-wait"].disposition == "paused"


def test_discovery_excludes_plan_progress_sidecars(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    _marker(marker_dir, "chain", workspace, status="running")
    (marker_dir / "milestone.progress.json").write_text(
        json.dumps(
            {
                "events_mtime": 1785102627.967471,
                "iteration": 9,
                "plan_v_count": 9,
                "unchanged_ticks": 8,
            }
        ),
        encoding="utf-8",
    )

    snapshots = simple_fixer.discover(marker_dir)

    assert [item.session for item in snapshots] == ["chain"]


def test_one_direct_operator_inspects_all_nonterminal_sessions_and_no_children(
    tmp_path: Path, monkeypatch
) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    _marker(marker_dir, "one", workspace, status="blocked")
    _marker(marker_dir, "two", workspace, status="running")
    _marker(marker_dir, "done", workspace, status="completed")
    binary, calls, prompts = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_CALLS", str(calls))
    monkeypatch.setenv("FAKE_CODEX_PROMPTS", str(prompts))
    monkeypatch.setenv("FAKE_SESSION", "one")

    assert simple_fixer.run_cycle(_args(tmp_path, marker_dir, binary)) == 0

    report = _latest(tmp_path)
    assert report["operator"]["count"] == 1
    assert calls.read_text(encoding="utf-8").splitlines() == ["call"]
    prompt = prompts.read_text(encoding="utf-8")
    assert '"session": "one"' in prompt
    assert '"session": "two"' in prompt
    assert '"session": "done"' in prompt
    assert "Do not\nspawn, delegate to, message, or launch any subagent" in prompt
    assert report["operator"]["children_allowed"] is False


def test_historical_missing_active_goal_storm_gets_two_attempt_cap(
    tmp_path: Path, monkeypatch
) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    _marker(marker_dir, "storm", workspace, status="blocked")
    repair_dir = marker_dir / "repair-data"
    repair_dir.mkdir()
    (repair_dir / "storm.repair-data.json").write_text(
        json.dumps(
            {
                "outcome": "repair_exhausted",
                "error": "L2 replan reconciliation requires an active repair goal",
                "investigator_count": 108,
                "meta_repair_attempts": 122,
                "updated_at": "2026-07-26T19:09:00Z",
            }
        ),
        encoding="utf-8",
    )
    binary, calls, prompts = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_CALLS", str(calls))
    monkeypatch.setenv("FAKE_CODEX_PROMPTS", str(prompts))
    monkeypatch.setenv("FAKE_SESSION", "storm")
    args = _args(tmp_path, marker_dir, binary)

    observed: list[tuple[int, bool, str]] = []
    for _ in range(3):
        assert simple_fixer.run_cycle(args) == 0
        row = _latest(tmp_path)["sessions"][0]
        observed.append(
            (row["unchanged_attempts"], row["mutation_allowed"], row["verification"])
        )

    assert observed == [
        (1, True, "no_independent_progress"),
        (2, True, "no_independent_progress"),
        (2, False, "retry_capped_no_mutation_authorized"),
    ]
    # Two repair opportunities total; the third cycle is a deterministic
    # report and launches no operator, never 108 investigator children.
    assert len(calls.read_text(encoding="utf-8").splitlines()) == 2
    state = json.loads((tmp_path / "attempts.json").read_text(encoding="utf-8"))
    assert state["sessions"]["storm"]["unchanged_attempts"] == 2
    assert state["sessions"]["storm"]["reason"] == "unchanged_retry_cap_2"
    assert _latest(tmp_path)["operator"]["count"] == 0


def test_changed_evidence_resets_retry_brake_and_independent_verifier_sees_progress(
    tmp_path: Path, monkeypatch
) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    marker = _marker(marker_dir, "storm", workspace, status="blocked", error="old")
    binary, calls, prompts = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_CALLS", str(calls))
    monkeypatch.setenv("FAKE_CODEX_PROMPTS", str(prompts))
    monkeypatch.setenv("FAKE_SESSION", "storm")
    monkeypatch.setenv("FAKE_CODEX_MUTATE_MARKER", str(marker))

    assert simple_fixer.run_cycle(_args(tmp_path, marker_dir, binary)) == 0

    row = _latest(tmp_path)["sessions"][0]
    assert row["fingerprint_changed"] is True
    assert row["verification"] == "state_cursor_advanced"
    assert row["claimed_result"] == "fixed"


def test_arbitrary_error_or_log_change_is_not_accepted_as_progress(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    marker = _marker(marker_dir, "storm", workspace, status="blocked", error="old")
    before = simple_fixer.discover(marker_dir)[0]
    payload = json.loads(marker.read_text(encoding="utf-8"))
    payload["error"] = "different words but the same stuck cursor"
    marker.write_text(json.dumps(payload), encoding="utf-8")
    after = simple_fixer.discover(marker_dir)[0]

    assert before.fingerprint != after.fingerprint
    assert (
        simple_fixer._verified_progress(before, after, datetime.now(timezone.utc))
        == "no_independent_progress"
    )


def test_transcript_and_reports_are_durably_redacted(tmp_path: Path, monkeypatch) -> None:
    marker_dir = tmp_path / "markers"
    _marker(marker_dir, "storm", tmp_path / "workspace", status="blocked")
    binary, calls, prompts = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_CALLS", str(calls))
    monkeypatch.setenv("FAKE_CODEX_PROMPTS", str(prompts))
    monkeypatch.setenv("FAKE_SESSION", "storm")

    assert simple_fixer.run_cycle(_args(tmp_path, marker_dir, binary)) == 0

    transcripts = list((tmp_path / "reports").glob("*/operator-transcript.jsonl"))
    assert len(transcripts) == 1
    text = transcripts[0].read_text(encoding="utf-8")
    assert "super-secret-value-12345" not in text
    assert "***REDACTED***" in text
    assert (transcripts[0].parent / "report.json").is_file()
    assert (transcripts[0].parent / "report.md").is_file()


def test_global_singleton_does_not_launch_second_operator(tmp_path: Path, monkeypatch) -> None:
    marker_dir = tmp_path / "markers"
    _marker(marker_dir, "storm", tmp_path / "workspace", status="blocked")
    binary, calls, prompts = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_CALLS", str(calls))
    monkeypatch.setenv("FAKE_CODEX_PROMPTS", str(prompts))
    args = _args(tmp_path, marker_dir, binary)
    lock_path = Path(args.lock_file)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert simple_fixer.run_cycle(args) == 0
    assert not calls.exists()
