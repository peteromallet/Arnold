from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_PATH = (
    REPO_ROOT
    / "arnold_pipelines"
    / "megaplan"
    / "cloud"
    / "wrappers"
    / "arnold-meta-repair-loop"
)


def _meta_repair_wrapper() -> str:
    return WRAPPER_PATH.read_text(encoding="utf-8")


def _extract_meta_repair_embedded_python(marker: str) -> str:
    text = _meta_repair_wrapper()
    start = text.index(marker)
    start = text.index("\n", start) + 1
    end = text.index("\nPY\n", start)
    return text[start:end]


def test_repair_loop_bin_falls_back_when_override_missing() -> None:
    text = _meta_repair_wrapper()
    start = text.index('MARKER_DIR="${MEGAPLAN_META_MARKER_DIR:-/workspace/.megaplan/cloud-sessions}"')
    end = text.index('REPAIR_DATA_PATH="$REPAIR_DATA_DIR/${SESSION}.repair-data.json"')
    prolog = text[start:end]

    script = "\n".join(
        [
            "set -eu",
            "SESSION=demo-session",
            f"MEGAPLAN_META_ARNOLD_SRC={shlex.quote(str(REPO_ROOT))}",
            "MEGAPLAN_META_SELF_PATH=/usr/local/bin/arnold-meta-repair-loop",
            "MEGAPLAN_META_REPAIR_LOOP_BIN=/tmp/missing-repair-loop",
            prolog,
            'printf "REPAIR_LOOP_BIN=%s\\n" "$REPAIR_LOOP_BIN"',
        ]
    )

    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (
        f"REPAIR_LOOP_BIN={REPO_ROOT}/arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop"
        in result.stdout
    )


def test_unrecordable_codex_response_dispatches_direct_hermes() -> None:
    text = _meta_repair_wrapper()

    assert 'if ! has_recordable_verdict "$RESP_PATH"; then' in text
    assert "run_direct_hermes_fallback || true" in text
    assert '--query-file "$FALLBACK_BRIEF_PATH"' in text
    assert '--project-dir /workspace' in text
    assert 'cd /workspace || exit 1' in text
    assert 'sys.modules["megaplan.agent"] = agent_probe' in text
    assert 'runpy.run_path(launcher, run_name="__main__")' in text


def test_meta_repair_wrapper_fails_closed_on_commit_custody() -> None:
    text = _meta_repair_wrapper()

    assert 'SOURCE_BASELINE_HEAD="$(git -C "$ARNOLD_SRC" rev-parse HEAD' in text
    assert "verify_meta_repair_commit_custody" in text


def test_meta_repair_provenance_bootstrap_uses_safe_python_path() -> None:
    text = _meta_repair_wrapper()
    assert 'PYTHONSAFEPATH=1 PYTHONPATH="$WRAPPER_REPO_ROOT:$ARNOLD_SRC:${PYTHONPATH:-}" python3 -P - "$marker_path"' in text
    assert 'INSTALL_SYNC_STATUS="commit_custody_failed"' in text
    assert "will NOT install sync or retrigger ordinary repair" in text
    assert 'post_retrigger_verification["commit_custody"]' in text


def test_recordable_verdict_check_rejects_arbitrary_output(tmp_path: Path) -> None:
    text = _meta_repair_wrapper()
    start = text.index("has_recordable_verdict() {")
    end = text.index("\n\nrun_direct_hermes_fallback()", start)
    function = text[start:end]
    response_path = tmp_path / "response.txt"

    response_path.write_text("diagnosis without verdict\n", encoding="utf-8")
    rejected = subprocess.run(
        ["bash", "-lc", f"{function}\nhas_recordable_verdict {shlex.quote(str(response_path))}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert rejected.returncode == 1

    response_path.write_text("ESCALATE\noperator action required\n", encoding="utf-8")
    accepted = subprocess.run(
        ["bash", "-lc", f"{function}\nhas_recordable_verdict {shlex.quote(str(response_path))}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert accepted.returncode == 0


def test_direct_hermes_requires_a_recordable_verdict() -> None:
    text = _meta_repair_wrapper()

    assert 'if ! has_recordable_verdict "$FALLBACK_RESP_PATH"; then' in text
    assert 'log "direct Hermes fallback produced no recordable verdict"' in text
    assert 'cp "$FALLBACK_RESP_PATH" "$RESP_PATH"' in text


def test_failed_launch_persists_retryable_negative_evidence() -> None:
    text = _meta_repair_wrapper()

    assert "persist_unrecordable_launch_failure()" in text
    assert 'outcome="model_tool_launch_failure"' in text
    assert "Codex meta-repair orchestrator returned no output and direct Hermes" in text
    assert "recursion guard remains unpoisoned" in text


def test_failed_launch_record_does_not_poison_recursion(tmp_path: Path) -> None:
    marker = (
        '"$SESSION" "$TRIGGER_TYPE" "$REPAIR_DATA_DIR" "$RESP_PATH" '
        '"$ERR_PATH" <<'
    )
    program = _extract_meta_repair_embedded_python(marker)
    prog_path = tmp_path / "_persist_launch_failure.py"
    prog_path.write_text(program, encoding="utf-8")
    repair_data_dir = tmp_path / "repair-data"
    response_path = tmp_path / "response.txt"
    response_path.write_text("unrecordable response\n", encoding="utf-8")
    error_path = tmp_path / "response.err"
    error_path.write_text("provider unavailable\n", encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"

    result = subprocess.run(
        [
            sys.executable,
            str(prog_path),
            "demo-session",
            "model_tool_launch_failure",
            str(repair_data_dir),
            str(response_path),
            str(error_path),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    records = list((repair_data_dir / "meta").glob("*.json"))
    assert len(records) == 1
    payload = json.loads(records[0].read_text(encoding="utf-8"))
    assert payload["outcome"] == "model_tool_launch_failure"

    from arnold_pipelines.megaplan.cloud.meta_repair_policy import (
        check_meta_repair_recursion,
    )

    recursion = check_meta_repair_recursion(
        "demo-session", repair_data_dir=repair_data_dir
    )
    assert recursion.recursing is False
    assert recursion.existing_meta_repair_ids == ()


def test_persist_record_marks_retrigger_verification_failure(tmp_path: Path) -> None:
    marker = (
        'python3 - "$SESSION" "$TRIGGER_TYPE" "$VERDICT" "$RESP_PATH" '
        '"$BRIEF_PATH" "$REPAIR_DATA_DIR" "$META_WORKER_RUN_ID" '
        '"$META_WORKER_MANIFEST" <<'
    )
    program = _extract_meta_repair_embedded_python(marker)
    prog_path = tmp_path / "_persist.py"
    prog_path.write_text(program, encoding="utf-8")

    resp_path = tmp_path / "resp.txt"
    resp_path.write_text("FIXED\nrepair applied\n", encoding="utf-8")
    brief_path = tmp_path / "brief.md"
    brief_path.write_text("brief\n", encoding="utf-8")
    repair_data_dir = tmp_path / "repair-data"
    repair_data_dir.mkdir()

    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    env["INSTALL_SYNC_JSON"] = json.dumps({"status": "applied"})
    env["POST_RETRIGGER_VERIFICATION_JSON"] = json.dumps(
        {
            "retriggered": True,
            "accepted": False,
            "outcome": "retrigger_verification_missing",
            "rejection_reason": "ordinary repair retrigger helper produced no verification record (returncode=1)",
            "retrigger_command": "arnold-repair-loop demo-session",
        }
    )

    result = subprocess.run(
        [
            sys.executable,
            str(prog_path),
            "demo-session",
            "persistent_recurring_retry",
            "FIXED",
            str(resp_path),
            str(brief_path),
            str(repair_data_dir / "demo-session.repair-data.json"),
            "",
            "",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    record_path = ""
    for line in result.stdout.splitlines():
        if line.startswith("RECORD_PATH="):
            record_path = line.split("=", 1)[1]
            break
    assert record_path

    payload = json.loads(Path(record_path).read_text(encoding="utf-8"))
    assert payload["outcome"] == "retrigger_verification_missing"
    assert payload["post_retrigger_verification"]["accepted"] is False
    assert (
        payload["post_retrigger_verification"]["rejection_reason"]
        == "ordinary repair retrigger helper produced no verification record (returncode=1)"
    )
    assert payload["retrigger_command"] == "arnold-repair-loop demo-session"


def test_retrigger_helper_passes_workspace_and_remote_spec(tmp_path: Path) -> None:
    marker = (
        'python3 - "$SESSION" "$REPAIR_LOOP_BIN" "$WRAPPER_REPO_ROOT" '
        '"$INSTALL_SYNC_EVENT_ID" "$REPAIR_DATA_PATH" "$MARKER_DIR" <<'
    )
    program = _extract_meta_repair_embedded_python(marker)
    prog_path = tmp_path / "_retrigger.py"
    prog_path.write_text(program, encoding="utf-8")

    repair_data_dir = tmp_path / "repair-data"
    repair_data_dir.mkdir()
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "target-workspace"
    workspace.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones:\n  - label: m1\n", encoding="utf-8")
    chain_path = workspace / ".megaplan" / "plans" / ".chains" / "chain-demo.json"
    chain_path.parent.mkdir(parents=True, exist_ok=True)
    chain_path.write_text(
        json.dumps(
            {
                "current_plan_name": "demo-plan",
                "last_state": "done",
                "milestones": [{"label": "m1"}],
                "completed": [{"label": "m1", "status": "done"}],
            }
        ),
        encoding="utf-8",
    )
    plan_path = workspace / ".megaplan" / "plans" / "demo-plan" / "state.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps({"current_state": "done"}), encoding="utf-8")

    (marker_dir / "demo-session.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "workspace": str(workspace),
                "remote_spec": str(spec_path),
                "run_kind": "chain",
            }
        ),
        encoding="utf-8",
    )
    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
                {
                    "session": "demo-session",
                    "outcome": "complete",
                    "verification": {
                        "outcome": "complete",
                        "original_blocker": {"blocker_id": "blocker:demo"},
                        "observation": {
                            "blocker_id": "blocker:demo",
                            "blocker_cleared": True,
                            "directly_observed": True,
                            "independent": True,
                            "observed_at": "2026-07-04T01:01:00Z",
                        },
                        "repair_completed_at": "2026-07-04T01:00:00Z",
                    },
                }
        ),
        encoding="utf-8",
    )

    argv_log = tmp_path / "argv.log"
    repair_loop_bin = tmp_path / "fake-repair-loop"
    repair_loop_bin.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$@\" > {shlex.quote(str(argv_log))}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    repair_loop_bin.chmod(repair_loop_bin.stat().st_mode | 0o111)

    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    result = subprocess.run(
        [
            sys.executable,
            str(prog_path),
            "demo-session",
                str(repair_loop_bin),
                str(tmp_path),
                "",
                str(repair_data_dir / "demo-session.repair-data.json"),
                str(marker_dir),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    argv = argv_log.read_text(encoding="utf-8").splitlines()
    assert argv == ["demo-session", str(workspace), str(spec_path)]

    verification_json = ""
    for line in result.stdout.splitlines():
        if line.startswith("VERIFICATION_JSON="):
            verification_json = line.split("=", 1)[1]
            break
    assert verification_json
    payload = json.loads(verification_json)
    assert payload["accepted"] is True
    assert payload["retrigger_command"] == (
        f"{repair_loop_bin} demo-session {workspace} {spec_path}"
    )
