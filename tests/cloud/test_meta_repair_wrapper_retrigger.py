from __future__ import annotations

import hashlib
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
            f"ARNOLD_META_REPAIR_LOOP_ORIGIN={shlex.quote(str(WRAPPER_PATH))}",
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


def test_repair_loop_bin_rejects_stale_installed_override(tmp_path: Path) -> None:
    text = _meta_repair_wrapper()
    start = text.index('MARKER_DIR="${MEGAPLAN_META_MARKER_DIR:-/workspace/.megaplan/cloud-sessions}"')
    end = text.index('REPAIR_DATA_PATH="$REPAIR_DATA_DIR/${SESSION}.repair-data.json"')
    prolog = text[start:end]
    stale = tmp_path / "arnold-repair-loop"
    stale.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
    stale.chmod(0o755)
    script = "\n".join(
        [
            "set -eu",
            "SESSION=demo-session",
            f"MEGAPLAN_META_ARNOLD_SRC={shlex.quote(str(REPO_ROOT))}",
            "MEGAPLAN_META_SELF_PATH=/usr/local/bin/arnold-meta-repair-loop",
            f"ARNOLD_META_REPAIR_LOOP_ORIGIN={shlex.quote(str(WRAPPER_PATH))}",
            f"MEGAPLAN_META_REPAIR_LOOP_BIN={shlex.quote(str(stale))}",
            prolog,
            'printf "REPAIR_LOOP_BIN=%s\\n" "$REPAIR_LOOP_BIN"',
        ]
    )

    result = subprocess.run(
        ["bash", "-lc", script], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert (
        f"REPAIR_LOOP_BIN={REPO_ROOT}/arnold_pipelines/megaplan/cloud/wrappers/"
        "arnold-repair-loop"
    ) in result.stdout
    assert "ignoring repair-loop override that differs from repaired source" in result.stderr


def test_stale_installed_meta_wrapper_hands_off_to_custody_source(
    tmp_path: Path,
) -> None:
    text = _meta_repair_wrapper()
    start = text.index('ARNOLD_SRC="${MEGAPLAN_META_ARNOLD_SRC:-')
    end = text.index('SELF_PATH="${MEGAPLAN_META_SELF_PATH:-', start)
    handoff = text[start:end]
    source_root = tmp_path / "source"
    source_wrapper = (
        source_root
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "wrappers"
        / "arnold-meta-repair-loop"
    )
    source_wrapper.parent.mkdir(parents=True)
    source_wrapper.write_text(
        "#!/usr/bin/env bash\nprintf 'custody-source:%s\\n' \"$*\"\n",
        encoding="utf-8",
    )
    source_wrapper.chmod(0o755)
    installed = tmp_path / "arnold-meta-repair-loop"
    installed.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
    installed.chmod(0o755)
    script = "\n".join(
        [
            "set -eu",
            "set -- demo-session l1_custody_failure",
            f"MEGAPLAN_META_ARNOLD_SRC={shlex.quote(str(source_root))}",
            f"ARNOLD_META_REPAIR_LOOP_ORIGIN={shlex.quote(str(installed))}",
            handoff,
            "echo stale-wrapper-continued",
        ]
    )

    result = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "custody-source:demo-session l1_custody_failure"
    assert "stale-wrapper-continued" not in result.stdout


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


def test_l3_trigger_requires_typed_request_and_uses_pointer_prompt() -> None:
    text = _meta_repair_wrapper()

    assert 'if [[ "$WATCHDOG_TRIGGER" == "l3_progress_auditor" ]]' in text
    assert "validate_l3_repair_dispatch_context" in text
    assert '"${CLOUD_WATCHDOG_REPAIR_REQUEST_ID:-}"' in text
    assert '"${ARNOLD_REPAIR_QUEUE_ROOT:-}"' in text
    assert '"${ARNOLD_L3_REPAIR_OUTCOME_PATH:-}"' in text
    assert "arnold-l3-meta-repair-pointer-v1" in (
        REPO_ROOT
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "progress_auditor_escalation.py"
    ).read_text(encoding="utf-8")
    assert "deep repair pointer exceeds its 8 KiB prompt budget" in text
    assert "json.dumps(pointer, indent=2, sort_keys=True)" in text
    assert "json.dumps(payload, indent=2, sort_keys=True)" not in text


def test_meta_repair_provenance_bootstrap_uses_safe_python_path() -> None:
    text = _meta_repair_wrapper()
    assert 'PYTHONSAFEPATH=1 PYTHONPATH="$META_REPAIR_PYTHONPATH" python3 -P - \\' in text
    assert 'INSTALL_SYNC_STATUS="commit_custody_failed"' in text
    assert "will NOT install sync or retrigger ordinary repair" in text
    assert 'post_retrigger_verification["commit_custody"]' in text


def test_l2_observation_contract_attestation_rejects_stale_source_scope(
    tmp_path: Path,
) -> None:
    text = _meta_repair_wrapper()
    start = text.index("attest_meta_investigation_contract_artifact() {")
    end = text.index("\n}\n", start) + 3
    function = text[start:end]
    contract = REPO_ROOT / "arnold_pipelines/megaplan/cloud/repair_investigation.py"
    source_observation = {
        "kind": "source_contract",
        "path": str(contract),
        "sha256": hashlib.sha256(contract.read_bytes()).hexdigest(),
    }
    observation_path = tmp_path / "observation.json"
    required = {
        "safe_repair_target_by_action": {"repair_source": ["arnold_source"]},
        "handoff_allowed_mutations_by_action": {
            "repair_source": [
                "arnold_source:arnold_pipelines/megaplan/cloud/<bounded component>",
                "arnold_source:tests/cloud/<bounded component>",
            ]
        },
        "l2_source_boundary": (
            "Target application files remain target_workspace work owned by L1."
        ),
    }
    observation_path.write_text(
        json.dumps(
            {
                "required_receipt_shape": required,
                "observations": [source_observation],
            }
        ),
        encoding="utf-8",
    )
    script = "\n".join(
        [
            function,
            f"MEGAPLAN_SUPERVISOR_STDLIB_PYTHON={shlex.quote(sys.executable)}",
            f"META_INVESTIGATION_OBSERVATION_PATH={shlex.quote(str(observation_path))}",
            f"ARNOLD_SRC={shlex.quote(str(REPO_ROOT))}",
            "attest_meta_investigation_contract_artifact",
        ]
    )

    accepted = subprocess.run(
        ["bash", "-lc", script], capture_output=True, text=True, check=False
    )
    assert accepted.returncode == 0, accepted.stderr

    required["safe_repair_target_by_action"]["repair_source"] = [
        "arnold_source",
        "target_workspace",
    ]
    observation_path.write_text(
        json.dumps(
            {
                "required_receipt_shape": required,
                "observations": [source_observation],
            }
        ),
        encoding="utf-8",
    )
    rejected = subprocess.run(
        ["bash", "-lc", script], capture_output=True, text=True, check=False
    )
    assert rejected.returncode != 0
    assert "permits repair_source outside Arnold source" in rejected.stderr


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
        '"$META_WORKER_MANIFEST" "${CLOUD_WATCHDOG_REPAIR_BLOCKER_ID:-}" <<'
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
            "blocker:demo",
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
        '"$INSTALL_SYNC_EVENT_ID" "$REPAIR_DATA_PATH" "$MARKER_DIR" '
        '"$META_INVESTIGATION_OBSERVATION_PATH" "$META_INVESTIGATION_CONTEXT_DIGEST" '
        '"$META_INVESTIGATION_RECEIPT_PATH" <<'
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

    goal_path = tmp_path / "repair-goal.json"
    goal_path.write_text(
        json.dumps(
            {
                "schema_version": "arnold-repair-goal-v1",
                "goal_id": "repair-goal-demo",
                "status": "active",
                "terminal": False,
                "checkpoint_digest": "checkpoint-demo",
                "target": {
                    "session": "demo-session",
                    "workspace": str(workspace),
                    "remote_spec": str(spec_path),
                    "blocker_id": "blocker:demo",
                },
            }
        ),
        encoding="utf-8",
    )
    handoff_path = tmp_path / "l2-handoff.json"
    handoff_path.write_text("{}\n", encoding="utf-8")
    receipt_path = tmp_path / "l2-receipt.json"
    receipt_path.write_text(
        json.dumps({"receipt_digest": "receipt-demo"}), encoding="utf-8"
    )

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
                    "blocker_id": "blocker:demo",
                    "repair_goal": {
                        "goal_id": "repair-goal-demo",
                        "goal_path": str(goal_path),
                        "checkpoint_digest": "checkpoint-demo",
                    },
                    "outcome": "complete",
                    "verification": {
                        "outcome": "complete",
                        "original_blocker": {"blocker_id": "blocker:demo"},
                        "observation": {
                            "blocker_id": "blocker:demo",
                            "blocker_cleared": True,
                            "directly_observed": True,
                            "independent": True,
                            "canonical_runner_live": True,
                            "fresh_progress_beyond_checkpoint": True,
                            "continued_progress": True,
                            "first_progress_observed_at": "2026-07-04T01:01:00Z",
                            "observed_at": "2026-07-04T01:02:00Z",
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
    env["CLOUD_WATCHDOG_REPAIR_BLOCKER_ID"] = ""
    env["CLOUD_WATCHDOG_REPAIR_REQUEST_ID"] = "request:demo"
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
            str(handoff_path),
            "context-demo",
            str(receipt_path),
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


def test_meta_investigator_gets_one_bounded_schema_correction_retry() -> None:
    wrapper = _meta_repair_wrapper()

    assert "invalid_candidate_receipt" in wrapper
    assert "validator_error" in wrapper
    assert ".invalid-1.json" in wrapper
    assert ".correction-1.md" in wrapper
    assert "correction envelope failed 64 KiB preflight" in wrapper
    assert ":correction:1" in wrapper
    assert "launching one bounded correction" in wrapper
    assert "invent new evidence, broaden mutation scope" in wrapper
    assert (
        "preserve_live is valid only when a correct live worker is actually present"
        in wrapper
    )
