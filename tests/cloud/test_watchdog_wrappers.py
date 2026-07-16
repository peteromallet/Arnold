"""Regression tests for cloud watchdog wrapper invariants."""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import shlex
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import repair_lock, repair_requests
from arnold_pipelines.megaplan.cloud.fixer_prompt_policy import (
    PROCESS_CUSTODY_FAIL_CLOSED_POLICY,
)
from arnold_pipelines.megaplan.cloud.redact import REDACTION


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"
SYSTEMD_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "systemd"


@pytest.fixture(autouse=True)
def _isolate_resident_delegation_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wrapper unit tests opt in to delegation provenance explicitly."""

    monkeypatch.delenv("ARNOLD_RESIDENT_DELEGATION_CONTEXT", raising=False)


def _wrapper(name: str) -> str:
    return (WRAPPER_DIR / name).read_text(encoding="utf-8")


def _systemd_file(name: str) -> str:
    return (SYSTEMD_DIR / name).read_text(encoding="utf-8")


def _discover_wrapper() -> str:
    return _wrapper("arnold-cloud-discover")


def _repair_wrapper() -> str:
    return _wrapper("arnold-repair-loop")


def test_auditor_classifies_meta_trigger_rejection_as_current_failure(
    tmp_path: Path,
) -> None:
    text = _wrapper("arnold-progress-auditor")
    start = text.index("def _meta_run_failure_code(path):")
    end = text.index("\ndef _text_has_meta_launch_failure(", start)
    namespace: dict[str, object] = {}
    exec("import re\n" + text[start:end], namespace)
    failure_code = namespace["_meta_run_failure_code"]
    assert callable(failure_code)
    log = tmp_path / "meta.log"
    log.write_text(
        "[meta-repair 2026-07-16T00:44:11+00:00] "
        "no meta-repair trigger matched; exiting\n",
        encoding="utf-8",
    )

    assert failure_code(log) == "meta_repair_trigger_rejected"
    assert '"trigger_rejected": bool(current_episode and trigger_rejected)' in text
    assert 'or meta.get("trigger_rejection_count")' in text


def test_progress_auditor_review_uses_bounded_pointer_and_typed_response() -> None:
    text = _wrapper("arnold-progress-auditor")

    assert "bounded_audit_review_pointer" in text
    assert 'cat "$review_evidence"' in text
    assert 'cat "$gather_file"' not in text
    assert "AUDIT_REVIEW_EVIDENCE_MAX_BYTES=65536" in text
    assert "AUDIT_REVIEW_BRIEF_MAX_BYTES=131072" in text
    assert '--output-last-message "$model_resp_path"' in text
    assert "normalize_audit_review_response" in text
    assert 'data["hypothesis"] = text[:2000]' in text


def test_progress_auditor_completion_evidence_records_approval_corrective_path() -> None:
    text = _wrapper("arnold-progress-auditor")

    assert 'escalation.get("decision") == "approval_required"' in text
    assert 'corrective_path.get("action") == "await_human_pr_merge"' in text
    assert 'corrective_path.get("repair_dispatch_permitted") is False' in text
    assert '"recommendation": "auditor_escalate_to_human"' in text
    assert 'aggregate_next_event = "human_approval.pr_merge"' in text


def test_relaunch_scripts_preserve_managed_repair_route_context() -> None:
    watchdog = _wrapper("arnold-watchdog")
    repair_loop = _repair_wrapper()
    for text in (watchdog, repair_loop):
        assert "export ARNOLD_REPAIR_QUEUE_ROOT=" in text
        assert "export ARNOLD_REPAIR_MARKER_DIR=" in text
        assert "export ARNOLD_REPAIR_SESSION=" in text
        assert "export ARNOLD_REPAIR_RUN_KIND=" in text
    assert "operator-managed runtime environment inside the new child" in repair_loop
    assert ". /workspace/.cloud-hot-env" in repair_loop


def test_superfixer_wrappers_prefer_pinned_runtime_source() -> None:
    assert 'SRC_DIR="${MEGAPLAN_RUNTIME_SRC:-${CLOUD_WATCHDOG_ARNOLD_SRC:-/workspace/arnold}}"' in _wrapper("arnold-watchdog")
    assert 'ARNOLD_SRC="${MEGAPLAN_RUNTIME_SRC:-${CLOUD_WATCHDOG_ARNOLD_SRC:-/workspace/arnold}}"' in _repair_wrapper()
    assert 'ARNOLD_SRC="${MEGAPLAN_META_ARNOLD_SRC:-${MEGAPLAN_RUNTIME_SRC:-/workspace/arnold}}"' in _wrapper("arnold-meta-repair-loop")
    auditor = _wrapper("arnold-progress-auditor")
    assert "${MEGAPLAN_AUDIT_ARNOLD_SRC:-${MEGAPLAN_RUNTIME_SRC:-" in auditor


@pytest.mark.parametrize(
    ("wrapper_name", "prefix"),
    [
        ("arnold-watchdog", "ARNOLD_WATCHDOG"),
        ("arnold-repair-loop", "ARNOLD_REPAIR_LOOP"),
        ("arnold-meta-repair-loop", "ARNOLD_META_REPAIR_LOOP"),
        ("arnold-progress-auditor", "ARNOLD_PROGRESS_AUDITOR"),
    ],
)
def test_long_running_superfixer_wrappers_pin_syntax_checked_source_snapshot(
    wrapper_name: str, prefix: str
) -> None:
    text = _wrapper(wrapper_name)

    assert f'{prefix}_ORIGIN="${{{prefix}_ORIGIN:-' in text
    assert f'${{{prefix}_SNAPSHOT_ACTIVE:-0}}' in text
    assert "mktemp" in text
    assert "bash -n" in text
    assert f"export {prefix}_SNAPSHOT_ACTIVE=1" in text
    assert f'{prefix}_SNAPSHOT_PATH="${{BASH_SOURCE[0]:-$0}}"' in text
    assert f'trap \'rm -f -- "${prefix}_SNAPSHOT_PATH"\' EXIT' in text
    assert 'trap \'rm -f -- "${BASH_SOURCE[0]:-$0}"\' EXIT' not in text


@pytest.mark.parametrize(
    ("wrapper_name", "prefix", "args", "expected_returncode"),
    [
        ("arnold-repair-loop", "arnold-repair-loop", [], 64),
        ("arnold-meta-repair-loop", "arnold-meta-repair-loop", [], 64),
    ],
)
def test_wrapper_snapshot_is_removed_after_fail_closed_usage_exit(
    tmp_path: Path,
    wrapper_name: str,
    prefix: str,
    args: list[str],
    expected_returncode: int,
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    result = subprocess.run(
        ["bash", str(WRAPPER_DIR / wrapper_name), *args],
        env={**os.environ, "TMPDIR": str(snapshot_dir)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == expected_returncode
    assert not list(snapshot_dir.glob(f"{prefix}.*"))


def test_repair_wrapper_snapshot_survives_origin_replacement_while_waiting(
    tmp_path: Path,
) -> None:
    wrapper = _repair_wrapper()
    bootstrap = wrapper[: wrapper.index("\n\nif [[ $# -lt 3 ]]")]
    origin = tmp_path / "repair-wrapper"
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    origin.write_text(
        bootstrap
        + "\nprintf 'snapshot-ready\\n'\n"
        + "sleep 0.25\n"
        + "printf 'snapshot-finished\\n'\n",
        encoding="utf-8",
    )
    process = subprocess.Popen(
        ["bash", str(origin)],
        env={**os.environ, "TMPDIR": str(snapshot_dir)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stdout.readline().strip() == "snapshot-ready"

    # This would produce the exact lazy-parser EOF class if Bash resumed from
    # the mutable origin rather than its already validated snapshot.
    origin.write_text('printf "unterminated\n', encoding="utf-8")
    stdout, stderr = process.communicate(timeout=5)

    assert process.returncode == 0, stderr
    assert stdout.strip() == "snapshot-finished"
    assert not list(snapshot_dir.glob("arnold-repair-loop.*"))


def _extract_repair_function(name: str) -> str:
    text = _repair_wrapper()
    start = text.index(f"{name}() {{")
    end = text.index("\n}\n", start) + 3
    return text[start:end]


def test_repair_wrappers_restore_managed_upstream_custody_before_marker() -> None:
    repair = _repair_wrapper()
    meta = _meta_repair_wrapper()

    for wrapper in (repair, meta):
        function = wrapper[
            wrapper.index("load_resident_delegation_context() {") :
            wrapper.index("\n}\n", wrapper.index("load_resident_delegation_context() {")) + 3
        ]
        assert '"${ARNOLD_MANAGED_AGENT_MANIFEST:-}"' in function
        assert 'manifest.get("upstream_custody")' in function
        assert function.index('manifest.get("upstream_custody")') < function.index(
            'marker.get("resident_delegation")'
        )
        assert "invalid managed-agent upstream custody" in function


def _extract_wrapper_function(name: str) -> str:
    text = _wrapper("arnold-watchdog")
    start = text.index(f"{name}() {{")
    end = text.index("\n}\n", start) + 3
    return text[start:end]


def _extract_auditor_function(name: str) -> str:
    text = _wrapper("arnold-progress-auditor")
    start = text.index(f"{name}() {{")
    end = text.index("\n}\n", start) + 3
    return text[start:end]


def _extract_wrapper_function_until(name: str, next_name: str) -> str:
    text = _wrapper("arnold-watchdog")
    start = text.index(f"{name}() {{")
    end = text.index(f"\n{next_name}() {{", start)
    return text[start:end]


def _extract_relaunch_functions(wrapper_kind: str) -> list[str]:
    """Extract the resolver with its complete wrapper-specific dependency closure."""
    extract = (
        _extract_wrapper_function
        if wrapper_kind == "watchdog"
        else _extract_repair_function
    )
    names = [
        "default_plan_relaunch_command",
        "resume_plan_relaunch_command",
        "chain_resume_plan_relaunch_command_if_needed",
        "stale_marker_relaunch_command",
        "default_chain_relaunch_command",
    ]
    if wrapper_kind == "repair":
        names.append("_repair_loop_acceptance_gate")
    names.append("resolve_relaunch_command")
    return [extract(name) for name in names]


def _extract_reap_program() -> str:
    text = _wrapper("arnold-watchdog")
    start = text.index("reap_stale_repair_candidates() {")
    marker = "python3 - \"$REAP_AGE_SECS\" \"$REAP_ORPHAN_AGE_SECS\" <<'PY'"
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    return text[py_start:py_end]


def _load_reap_module(tmp_path: Path):
    mod_path = tmp_path / "_reap_prog.py"
    mod_path.write_text(_extract_reap_program(), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("_reap_prog", mod_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extract_repair_stall_program() -> str:
    text = _wrapper("arnold-watchdog")
    start = text.index("reap_stalled_repair_candidates() {")
    marker = None
    for candidate in (
        "python3 - \"$MARKER_DIR\" \"$REPAIR_OPERATOR_ROOT\" "
        "\"$REAP_STALL_GRACE_SECS\" \"$REAP_STALL_IDLE_SECS\" "
        "\"$REAP_AGE_SECS\" <<'PY'",
        "python3 - \"$MARKER_DIR\" \"$KIMI_OPERATOR_ROOT\" "
        "\"$REAP_STALL_GRACE_SECS\" \"$REAP_STALL_IDLE_SECS\" "
        "\"$REAP_AGE_SECS\" <<'PY'",
    ):
        if candidate in text[start:]:
            marker = candidate
            break
    assert marker is not None
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    return text[py_start:py_end]


def _extract_repair_program(function_name: str, marker: str) -> str:
    text = _repair_wrapper()
    start = text.index(f"{function_name}() {{")
    try:
        py_start = text.index(marker, start)
    except ValueError:
        if function_name == "collect_failure_context_json":
            for fallback in (
                "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" \"$MARKER_DIR\" \"$DATA_DIR\" \"$REMOTE_SPEC\" <<'PY'",
                "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" \"$MARKER_DIR\" \"$DATA_DIR\" <<'PY'",
            ):
                try:
                    py_start = text.index(fallback, start)
                    break
                except ValueError:
                    continue
            else:
                raise
        elif function_name == "repair_target_completion_status":
            py_start = text.index(
                "python3 - \"$workspace\" \"$run_kind\" \"$plan_name\" \"$REMOTE_SPEC\" <<'PY'",
                start,
            )
        else:
            raise
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    return text[py_start:py_end]


def _run_repair_stall(
    tmp_path: Path,
    ps_rows: str,
    marker_dir: Path,
    operator_root: Path,
    grace_secs: int = 900,
    idle_secs: int = 600,
    reap_age_secs: int = 7200,
) -> list[str]:
    program = _extract_repair_stall_program()
    prog_path = tmp_path / "_repair_stall_prog.py"
    prog_path.write_text(program, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(prog_path),
            str(marker_dir),
            str(operator_root),
            str(grace_secs),
            str(idle_secs),
            str(reap_age_secs),
        ],
        input=ps_rows,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return [line for line in result.stdout.strip().splitlines() if line]


def _run_embedded_python(program: str, *args: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        prog_path = Path(tmpdir) / "_embedded.py"
        prog_path.write_text(program, encoding="utf-8")
        env = dict(os.environ)
        # Embedded wrapper fixtures must not inherit the resident process's
        # immutable Discord delegation envelope unless a test supplies one.
        env.pop("ARNOLD_RESIDENT_DELEGATION_CONTEXT", None)
        env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
        return subprocess.run(
            [sys.executable, str(prog_path), *args],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )


def _run_repair_data_init_for_contract_tests(
    data_path: Path,
    *,
    progress_path: Path,
    failure_context: dict[str, object],
) -> None:
    result = _run_repair_data_init(data_path, progress_path=progress_path, failure_context=failure_context)
    assert result.returncode == 0, result.stderr


def _run_repair_data_init(
    data_path: Path,
    *,
    progress_path: Path,
    session: str = "demo-session",
    workspace: str = "/tmp/workspace",
    spec: str = "/tmp/workspace/.megaplan/initiatives/demo/chain.yaml",
    run_kind: str = "chain",
    plan_name: str = "demo-plan",
    arnold_src: str | None = None,
    sync_branch: str = "editable-install",
    run_dir: str = "/tmp/run-dir",
    relaunch_command: str = "python -m arnold_pipelines.megaplan chain tick",
    initial_health: str = "dead",
    marker_json: str = '{"run_kind":"chain"}',
    source_git: str = "main\n",
    workspace_git: str = "feature\n",
    chain_log: str = "chain-log",
    watchdog_log: str = "watchdog-log",
    tmux_info: str = "tmux-pane",
    chain_state: str = "/tmp/workspace/.megaplan/plans/.chains/chain-demo.json",
    failure_context: dict[str, object] | None = None,
) -> subprocess.CompletedProcess[str]:
    program = _extract_repair_program(
        "repair_data_init",
        "PYTHONPATH=\"$ARNOLD_SRC:${PYTHONPATH:-}\" python3 - \"$DATA_FILE\" \"$PROGRESS_FILE\" \"$SESSION\" \"$WORKSPACE\" \"$REMOTE_SPEC\" \"$run_kind\" \"$plan_name\" \"$ARNOLD_SRC\" \"$SYNC_BRANCH\" \"$RUN_DIR\" \"$relaunch_command\" \"$initial_health\" \"$payload_dir\" \"${CLOUD_WATCHDOG_REPAIR_REQUEST_ID:-}\" \"${CLOUD_WATCHDOG_REPAIR_BLOCKER_ID:-}\" <<'PY'",
    )
    payload_dir = data_path.parent / f"{data_path.stem}-repair-init-payload"
    payload_dir.mkdir(exist_ok=True)
    (payload_dir / "marker_json").write_text(marker_json, encoding="utf-8")
    (payload_dir / "source_git").write_text(source_git, encoding="utf-8")
    (payload_dir / "workspace_git").write_text(workspace_git, encoding="utf-8")
    (payload_dir / "chain_log").write_text(chain_log, encoding="utf-8")
    (payload_dir / "watchdog_log").write_text(watchdog_log, encoding="utf-8")
    (payload_dir / "tmux_info").write_text(tmux_info, encoding="utf-8")
    (payload_dir / "chain_state").write_text(chain_state, encoding="utf-8")
    (payload_dir / "failure_context").write_text(json.dumps(failure_context or {}), encoding="utf-8")
    return _run_embedded_python(
        program,
        str(data_path),
        str(progress_path),
        session,
        workspace,
        spec,
        run_kind,
        plan_name,
        arnold_src or str(REPO_ROOT),
        sync_branch,
        run_dir,
        relaunch_command,
        initial_health,
        str(payload_dir),
        "",
        "",
    )


def _run_write_needs_human_marker(
    data_path: Path,
    out_path: Path,
    *,
    discord_status: str = "delivered",
) -> subprocess.CompletedProcess[str]:
    program = _extract_repair_program(
        "write_needs_human_marker",
        "PYTHONPATH=\"$ARNOLD_SRC:${PYTHONPATH:-}\" python3 - \"$DATA_FILE\" \"$NEEDS_HUMAN_FILE\" \"$discord_status\" <<'PY'",
    )
    return _run_embedded_python(program, str(data_path), str(out_path), discord_status)


def _run_watchdog_shell(script: str, *, path_prefix: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    # Watchdog tests execute extracted production shell functions.  Never let
    # ambient credentials grant those functions outbound notification
    # authority; delivery tests must inject an explicit local stub instead.
    for name in (
        "DISCORD_BOT_TOKEN",
        "DISCORD_DM_USER_ID",
        "DISCORD_WEBHOOK_URL",
        "REPORT_WEBHOOK",
        "SLACK_WEBHOOK_URL",
        "PYTEST_CURRENT_TEST",
    ):
        env.pop(name, None)
    env["DISCORD_DM_BIN"] = "/bin/false"
    if path_prefix is not None:
        env["PATH"] = f"{path_prefix}:{env.get('PATH', '')}"
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_run_watchdog_shell_strips_ambient_notification_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "DISCORD_BOT_TOKEN",
        "DISCORD_DM_USER_ID",
        "DISCORD_WEBHOOK_URL",
        "REPORT_WEBHOOK",
        "SLACK_WEBHOOK_URL",
    ):
        monkeypatch.setenv(name, "live-secret")
    monkeypatch.setenv("DISCORD_DM_BIN", "/bin/true")

    result = _run_watchdog_shell(
        """
for name in DISCORD_BOT_TOKEN DISCORD_DM_USER_ID DISCORD_WEBHOOK_URL REPORT_WEBHOOK SLACK_WEBHOOK_URL; do
  [[ -z "${!name:-}" ]] || exit 20
done
[[ "$DISCORD_DM_BIN" == /bin/false ]] || exit 21
"""
    )

    assert result.returncode == 0, result.stderr


def _read_incident_event_payloads(root: Path) -> list[dict[str, object]]:
    events_path = root / ".megaplan" / "incident-ledger" / "events.jsonl"
    if not events_path.exists():
        return []
    payloads: list[dict[str, object]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payloads.append(json.loads(stripped)["payload"])
    return payloads


def _run_discover(
    tmp_path: Path,
    *,
    marker_dir: Path,
    src_dir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = f"{tmp_path}:{env.get('PATH', '')}"
    env.setdefault("MEGAPLAN_DISCOVER_WORKSPACE_ROOT", str(tmp_path / "workspace-root"))
    return subprocess.run(
        [
            "bash",
            str(WRAPPER_DIR / "arnold-cloud-discover"),
            "tmux-unmarked",
            "--marker-dir",
            str(marker_dir),
            "--src-dir",
            str(src_dir or REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_watchdog_defaults_editable_install_to_dedicated_branch() -> None:
    text = _wrapper("arnold-watchdog")

    assert (
        'SRC_DIR="${MEGAPLAN_RUNTIME_SRC:-${CLOUD_WATCHDOG_ARNOLD_SRC:-/workspace/arnold}}"'
        in text
    )
    assert 'SYNC_BRANCH="${CLOUD_WATCHDOG_SYNC_BRANCH:-editible-install}"' in text
    assert 'REPAIR_TRIGGER_BIN="${CLOUD_WATCHDOG_REPAIR_TRIGGER_BIN:-$SRC_DIR/arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-trigger}"' in text
    assert 'REPAIR_TRIGGER_BIN="${CLOUD_WATCHDOG_REPAIR_TRIGGER_BIN:-$WRAPPER_REPO_ROOT/arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-trigger}"' not in text
    assert 'SYNC_BRANCH="${CLOUD_WATCHDOG_SYNC_BRANCH:-${MEGAPLAN_REF' not in text
    assert "workflow-manifest-runtime" not in text


def test_watchdog_sync_does_not_broadly_commit_source_drift() -> None:
    text = _wrapper("arnold-watchdog")
    start = text.index("sync_editable_source_branch() {")
    end = text.index("\n\ncodex_repair_editable_install() {", start)
    sync_body = text[start:end]

    assert "git add -A -- arnold_pipelines/megaplan/skills" in sync_body
    assert "source checkout has non-sync drift; not auto-committing" in sync_body
    assert "git add -A &&" not in sync_body


def test_host_watchdog_ensure_starts_shell_wrapped_watchdog_and_verifies_liveness() -> None:
    text = _systemd_file("ensure-megaplan-watchdog")

    assert "tmux new-session -d -s watchdog -c /workspace /usr/local/bin/arnold-watchdog" in text
    assert "bash -lc 'exec /usr/local/bin/arnold-watchdog'" not in text
    assert "tmux new-session -d -s watchdog -c /workspace exec /usr/local/bin/arnold-watchdog" not in text
    assert "watchdog_restart_failed_not_alive" in text
    assert text.count("tmux has-session -t watchdog") >= 2


def test_watchdog_flags_incomplete_markers_instead_of_dispatching_without_custody() -> None:
    text = _wrapper("arnold-watchdog")

    assert 'report_item "$report_items" "" "flag" "setup_invalid" "missing session: $marker"' in text
    assert 'report_item "$report_items" "$session" "flag" "workspace_missing" "missing workspace: $marker"' in text
    assert 'report_item "$report_items" "$session" "flag" "setup_invalid" "missing remote_spec: $marker" "$workspace"' in text
    assert '"skip" "spec_missing"' not in text
    assert '"skip" "workspace_missing"' not in text


def test_repair_loop_dev_prompt_uses_bounded_typed_pointers() -> None:
    text = _repair_wrapper()
    prompt = _extract_repair_function("write_dev_prompt")

    assert 'DEV_PROMPT_MAX_BYTES="${CLOUD_WATCHDOG_DEV_PROMPT_MAX_BYTES:-65536}"' in text
    assert "Bounded authoritative pointers:" in prompt
    assert "investigator context (maximum 65,536 bytes)" in prompt
    assert "validated receipt (maximum 65,536 bytes)" in prompt
    assert "managed provenance manifest" in prompt
    assert "Act only inside the receipt's mutation scope" in prompt
    assert "never copy expanding logs, histories, state blobs" in prompt
    assert 'prompt_bytes="$(wc -c < "$prompt_path"' in prompt
    assert "dev prompt exceeds ${max_bytes}-byte bound" in prompt
    assert "render_failure_summary" not in prompt
    assert "render_chain_health_block" not in prompt
    assert "render_recurrence_block" not in prompt
    assert "investigation_receipt" not in prompt


def test_repair_loop_large_failure_context_is_passed_by_file() -> None:
    text = _repair_wrapper()

    assert '"$initial_health" "$payload_dir"' in text
    assert '"$detail" "$failure_context_file"' in text
    assert '"$turn_rc" "$failure_context_file"' in text
    assert '"$PROGRESS_FILE" "$failure_context_file"' in text
    assert 'failure_context_payload = json.loads(read_payload("failure_context") or "{}")' in text
    assert 'json.loads(pathlib.Path(failure_context_path).read_text(encoding="utf-8"))' in text
    assert 'json.loads(pathlib.Path(failure_context_path_raw).read_text(encoding="utf-8"))' in text
    assert '"$initial_health" "$marker_json"' not in text
    assert '"$detail" "$failure_context" <<' not in text
    assert '"$turn_rc" "$failure_context" <<' not in text
    assert '"$PROGRESS_FILE" "$failure_context" "$iteration"' not in text


def test_repair_loop_prompt_files_redact_secret_bearers_before_dispatch(tmp_path: Path) -> None:
    dev_prompt = tmp_path / "dev-prompt.md"
    kimi_prompt = tmp_path / "kimi-prompt.md"
    script = "\n\n".join(
        [
            _extract_repair_function("redact_inline_text"),
            _extract_repair_function("redact_file_in_place"),
            _extract_repair_function("render_process_custody_policy"),
            _extract_repair_function("write_dev_prompt"),
            _extract_repair_function("write_kimi_prompt"),
            f"ARNOLD_SRC={shlex.quote(str(REPO_ROOT))}",
            "SESSION=demo-session",
            "WORKSPACE=/tmp/workspace",
            "RUN_KIND=chain",
            "REMOTE_SPEC=/tmp/workspace/.megaplan/initiatives/demo/chain.yaml",
            "PLAN_NAME=demo-plan",
            "SYNC_BRANCH=editible-install",
            "DATA_FILE=/tmp/repair-data.json",
            "FINDINGS_DOC=/tmp/findings.md",
            "render_failure_summary() { printf '%s\\n' 'Authorization: Bearer bearer-secret-token-value'; }",
            "render_chain_health_block() { printf '%s\\n' 'curl --header Authorization: Bearer bearer-secret-token-value'; }",
            "render_recurrence_block() { printf '%s\\n' 'export API_TOKEN=supersecret'; }",
            (
                f"write_dev_prompt {shlex.quote(str(dev_prompt))} requested-model dispatch-model "
                f"{shlex.quote(str(tmp_path / 'report.json'))} 0"
            ),
            (
                f"write_kimi_prompt {shlex.quote(str(kimi_prompt))} "
                f"{shlex.quote('python relaunch.py --token supersecret')} "
                f"{shlex.quote(str(tmp_path / 'kimi-report.json'))}"
            ),
        ]
    )

    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    dev_text = dev_prompt.read_text(encoding="utf-8")
    kimi_text = kimi_prompt.read_text(encoding="utf-8")
    assert "bearer-secret-token-value" not in dev_text
    assert "supersecret" not in dev_text
    assert "supersecret" not in kimi_text
    assert REDACTION in kimi_text


def test_repair_loop_dev_prompt_does_not_inline_pathological_evidence_and_fails_closed(
    tmp_path: Path,
) -> None:
    context_path = tmp_path / "context.json"
    receipt_path = tmp_path / "receipt.json"
    prompt_path = tmp_path / "prompt.md"
    oversized_prompt_path = tmp_path / "oversized-prompt.md"
    pathological = "expanding-status-history-log" * 900_000
    context_path.write_text(pathological, encoding="utf-8")
    receipt_path.write_text(pathological, encoding="utf-8")
    script = "\n\n".join(
        [
            _extract_repair_function("write_dev_prompt"),
            "render_process_custody_policy() { printf '%s\\n' 'bounded custody'; }",
            "repair_delivery_policy() { printf '%s\\n' 'commit locally; do not push'; }",
            "redact_file_in_place() { :; }",
            "SESSION=demo-session",
            "WORKSPACE=/tmp/workspace",
            "ARNOLD_SRC=/tmp/runtime",
            "SYNC_BRANCH=target-branch",
            "DATA_FILE=/tmp/repair-data.json",
            "ARNOLD_REPAIR_GOAL_ID=goal-1",
            "ARNOLD_REPAIR_GOAL_PATH=/tmp/goal.json",
            "ARNOLD_REPAIR_CHECKPOINT_DIGEST=checkpoint-1",
            f"INVESTIGATION_CONTEXT_PATH={shlex.quote(str(context_path))}",
            f"INVESTIGATOR_RECEIPT_PATH={shlex.quote(str(receipt_path))}",
            "INVESTIGATION_CONTEXT_DIGEST=context-digest-1",
            "DEV_PROMPT_MAX_BYTES=65536",
            (
                f"write_dev_prompt {shlex.quote(str(prompt_path))} requested dispatch "
                f"{shlex.quote(str(tmp_path / 'report.json'))} 0"
            ),
            f"test $(wc -c < {shlex.quote(str(prompt_path))}) -lt 8192",
            f"! grep -q expanding-status-history-log {shlex.quote(str(prompt_path))}",
            "DEV_PROMPT_MAX_BYTES=512",
            (
                f"! write_dev_prompt {shlex.quote(str(oversized_prompt_path))} requested dispatch "
                f"{shlex.quote(str(tmp_path / 'report-2.json'))} 0"
            ),
            f"test ! -e {shlex.quote(str(oversized_prompt_path))}",
        ]
    )

    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    assert prompt_path.stat().st_size < 8192


def test_repair_loop_requires_fresh_investigation_after_dev_mutation() -> None:
    text = _repair_wrapper()
    dev_call = text.index('run_dev_fix_turn "$iteration"')
    reinvestigate = text.index(
        'repair_data_set_outcome "repair_applied_reinvestigate"', dev_call
    )
    owner_exit = text.index("exit 1", reinvestigate)
    legacy_recovery = text.index(
        'recover_blocked_after_dev_fix_if_possible "$iteration"', dev_call
    ) if 'recover_blocked_after_dev_fix_if_possible "$iteration"' in text[dev_call:] else -1
    mechanical = text.index('mechanical_launch_step "$iteration"', dev_call)

    assert reinvestigate < owner_exit < mechanical
    assert legacy_recovery == -1
    assert "fresh investigation required before recovery" in text[reinvestigate:mechanical]


def test_repair_loop_effective_fixer_prompts_require_canonical_process_custody_policy(
    tmp_path: Path,
) -> None:
    dev_prompt = tmp_path / "dev-prompt.md"
    kimi_prompt = tmp_path / "kimi-prompt.md"
    script = "\n\n".join(
        [
            _extract_repair_function("redact_inline_text"),
            _extract_repair_function("redact_file_in_place"),
            _extract_repair_function("render_process_custody_policy"),
            _extract_repair_function("write_dev_prompt"),
            _extract_repair_function("write_kimi_prompt"),
            f"ARNOLD_SRC={shlex.quote(str(REPO_ROOT))}",
            f"WRAPPER_REPO_ROOT={shlex.quote(str(REPO_ROOT))}",
            f"MEGAPLAN_SUPERVISOR_PYTHON={shlex.quote(sys.executable)}",
            "SESSION=demo-session",
            "WORKSPACE=/tmp/workspace",
            "RUN_KIND=chain",
            "REMOTE_SPEC=/tmp/workspace/.megaplan/initiatives/demo/chain.yaml",
            "PLAN_NAME=demo-plan",
            "SYNC_BRANCH=editible-install",
            "DATA_FILE=/tmp/repair-data.json",
            "FINDINGS_DOC=/tmp/findings.md",
            "ARNOLD_REPAIR_GOAL_PATH=/tmp/goal.json",
            "ARNOLD_REPAIR_GOAL_ID=goal-1",
            "ARNOLD_REPAIR_CHECKPOINT_DIGEST=checkpoint-1",
            "INVESTIGATION_CONTEXT_PATH=/tmp/investigation.json",
            "INVESTIGATOR_RECEIPT_PATH=/tmp/investigator-receipt.json",
            "INVESTIGATION_CONTEXT_DIGEST=context-1",
            "render_failure_summary() { printf '%s\\n' 'incident'; }",
            "render_chain_health_block() { :; }",
            "render_recurrence_block() { :; }",
            "render_canonical_block() { :; }",
            (
                f"write_dev_prompt {shlex.quote(str(dev_prompt))} requested-model dispatch-model "
                f"{shlex.quote(str(tmp_path / 'report.json'))} 0"
            ),
            (
                f"write_kimi_prompt {shlex.quote(str(kimi_prompt))} relaunch-command "
                f"{shlex.quote(str(tmp_path / 'kimi-report.json'))}"
            ),
        ]
    )

    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    for prompt_path in (dev_prompt, kimi_prompt):
        prompt = prompt_path.read_text(encoding="utf-8")
        assert PROCESS_CUSTODY_FAIL_CLOSED_POLICY in prompt
        assert "apparent duplication, or inference is never" in prompt
        assert "process holding your durable goal" in prompt


def test_repair_loop_fixer_prompt_composition_fails_closed_when_policy_is_unavailable(
    tmp_path: Path,
) -> None:
    prompt_path = tmp_path / "must-not-exist.md"
    script = "\n\n".join(
        [
            _extract_repair_function("write_dev_prompt"),
            "render_failure_summary() { :; }",
            "render_chain_health_block() { :; }",
            "render_recurrence_block() { :; }",
            "render_canonical_block() { :; }",
            "render_process_custody_policy() { return 1; }",
            (
                f"! write_dev_prompt {shlex.quote(str(prompt_path))} requested dispatch "
                f"{shlex.quote(str(tmp_path / 'report.json'))} 0"
            ),
            f"test ! -e {shlex.quote(str(prompt_path))}",
        ]
    )

    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_repair_prompt_ignores_stale_projected_blocked_chain_health(tmp_path: Path) -> None:
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"current_state": "blocked", "active_step": None}),
        encoding="utf-8",
    )
    chain_path = chain_dir / "chain-demo.json"
    chain_path.write_text(
        json.dumps({"current_plan_name": plan_name, "last_state": "blocked"}),
        encoding="utf-8",
    )
    artifact = repair_dir / "demo-session.chain-health.json"
    artifact.write_text(
        json.dumps(
            {
                "status": "chain_no_advance",
                "issue_kind": "chain_no_advance",
                "snapshot": {"plan_has_active_step": False},
                "chain_state_summary": {
                    "path": str(chain_path),
                    "current_plan_name": plan_name,
                    "last_state": "blocked",
                },
                "evidence_markdown": "## CHAIN HEALTH EVIDENCE\n- stale",
            }
        ),
        encoding="utf-8",
    )

    script = "\n".join(
        [
            _extract_repair_function("render_chain_health_block"),
            "SESSION=demo-session",
            f"DATA_FILE={shlex.quote(str(repair_dir / 'demo-session.repair-data.json'))}",
            "render_chain_health_block",
            f"test ! -e {shlex.quote(str(artifact))}",
        ]
    )
    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_repair_loop_collects_failure_signal_narrative_and_event_tail(tmp_path: Path) -> None:
    workspace = tmp_path / "workflow"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)

    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "finalized",
                "iteration": 21,
                "latest_failure": {
                    "kind": "phase_failed",
                    "message": "phase 'execute' internal_error",
                    "phase": "execute",
                    "recorded_at": "2026-06-28T19:30:34Z",
                    "metadata": {
                        "exit_code": 2,
                        "stderr": "__main__.py: error: unrecognized arguments: --confirm-destructive",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "events.ndjson").write_text(
        "\n".join(
            [
                json.dumps({"kind": "phase_started", "phase": "execute", "payload": {"msg": "launch execute"}}),
                json.dumps({"kind": "phase_failed", "phase": "execute", "payload": {"reason": "cli rejected flags"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "user_actions": [
                    {
                        "id": "ua-01-decide-cleanup",
                        "phase": "before_execute",
                        "blocks_task_ids": ["T1"],
                        "rationale": "Maintainer decision affects cleanup.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "user_actions.md").write_text(
        "# User Actions\n\n- **ua-01-decide-cleanup**: Decide cleanup scope.\n",
        encoding="utf-8",
    )
    (chain_dir / "chain-demo.json").write_text(
        json.dumps(
            {
                "current_plan_name": "demo-plan",
                "last_state": "awaiting_human",
                "events": [{"msg": "milestone demo starting"}, {"msg": "resuming existing plan demo-plan"}],
            }
        ),
        encoding="utf-8",
    )
    (workspace / ".megaplan" / "cloud-chain-demo.log").write_text(
        "\n".join(
            [
                "[chain] milestone demo starting",
                "[chain] resuming existing plan demo-plan",
                "[auto demo-plan] phase 'execute' exited with internal_error",
                "__main__.py: error: unrecognized arguments: --confirm-destructive",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(program, str(workspace), "demo", "chain", "")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["failure_classification"] == "cli_or_argument_error"
    assert any("unrecognized arguments" in item for item in payload["raw_failure_signals"])
    assert "phase 'execute' exited with internal_error" in payload["chain_log_tail"]
    assert "execute:phase_failed | reason=cli rejected flags" in payload["plan_events_tail"]
    assert payload["plan_latest_failure"]["state_path"].endswith("/demo-plan/state.json")
    user_action_context = payload["user_action_context"]
    assert user_action_context["user_actions_path"].endswith("/demo-plan/user_actions.md")
    assert user_action_context["unresolved_user_actions"][0]["id"] == "ua-01-decide-cleanup"
    assert user_action_context["unresolved_user_actions"][0]["blocks_task_ids"] == ["T1"]


def test_repair_loop_collects_execute_attempt_artifacts_and_renders_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workflow"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)

    history = [
        {
            "step": "execute",
            "result": "blocked",
            "timestamp": f"2026-06-29T02:0{i}:00Z",
            "output_file": "execution_batch_2.json",
        }
        for i in range(8)
    ]
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "finalized",
                "iteration": 21,
                "latest_failure": {
                    "kind": "phase_failed",
                    "message": "phase 'execute' internal_error",
                    "phase": "execute",
                    "recorded_at": "2026-06-29T01:00:00Z",
                    "metadata": {"stderr": "old internal_error"},
                },
                "history": history,
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "events.ndjson").write_text(
        json.dumps({"kind": "phase_end", "phase": "execute", "payload": {"status": "blocked"}}) + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execute_batch_2_output.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {"task_id": "m7-01", "status": "completed", "executor_notes": "done"},
                    {"task_id": "m7-13-full-suite-final-gate", "status": "pending", "executor_notes": ""},
                ]
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_2.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {"task_id": "m7-01", "status": "completed", "executor_notes": "done"},
                    {
                        "task_id": "m7-13-full-suite-final-gate",
                        "status": "blocked",
                        "executor_notes": "Deferred by harness until baseline is available.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "baseline_test_failures": None,
                "baseline_test_note": "runner error exit code 2",
                "baseline_test_collection_errors": ["tests/test_import_bad.py"],
                "tasks": [
                    {"id": "m7-01", "status": "completed", "executor_notes": "done"},
                    {
                        "id": "m7-13-full-suite-final-gate",
                        "status": "skipped",
                        "reviewer_verdict": "deferred_baseline_unavailable",
                        "executor_notes": (
                            "Collection failed with 43 errors - stale test imports "
                            "of deleted arnold.pipeline.*"
                        ),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "full_suite_backstop.json").write_text(
        json.dumps(
            {
                "status": "failed",
                "baseline_failing_count": 0,
                "current_failing_count": 43,
                "failing_tests": ["tests/test_import_bad.py"],
                "collection_errors": ["tests/test_import_bad.py"],
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "review.json").write_text(
        json.dumps(
            {
                "outcome": {
                    "result": "blocked",
                    "review_verdict": "needs_rework",
                    "state": "blocked",
                },
                "blocking_rework_items": [
                    {
                        "task_id": "T1",
                        "issue": "Backend agentic replay gate and path helpers are missing.",
                        "expected": "routes.py contains _is_agentic_replay_enabled and ID validation.",
                        "actual": "No agentic-replay symbols exist in routes.py.",
                        "evidence_file": "vibecomfy/comfy_nodes/agent/routes.py",
                        "source": "review_backend_missing",
                        "deterministic_check": {
                            "command": "python -m pytest tests/test_agentic_replay_routes.py -v",
                            "post_status": "failed",
                        },
                    },
                    {
                        "task_id": "T2",
                        "issue": "Backend discovery routes are not implemented.",
                        "expected": "GET /vibecomfy/agentic-replay/runs returns sanitized run records.",
                        "actual": "No discovery endpoints or helpers exist in routes.py.",
                        "evidence_file": "vibecomfy/comfy_nodes/agent/routes.py",
                        "deterministic_check": {
                            "command": "grep -n 'agentic-replay/runs' vibecomfy/comfy_nodes/agent/routes.py",
                            "post_status": "failed",
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (chain_dir / "chain-demo.json").write_text(
        json.dumps({"current_plan_name": "demo-plan", "last_state": "blocked"}),
        encoding="utf-8",
    )

    collect_program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(collect_program, str(workspace), "demo", "chain", "")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    execute_context = payload["execute_attempt_context"]
    assert execute_context["execute_batch_output"]["path"].endswith("execute_batch_2_output.json")
    assert execute_context["execution_batch"]["status_counts"]["blocked"] == 1
    assert execute_context["finalize"]["baseline_test_failures"] is None
    assert execute_context["plan_history"]["consecutive_execute_blocked"] == 8
    assert execute_context["review"]["review_verdict"] == "needs_rework"
    assert execute_context["review"]["blocking_rework_items"][0]["task_id"] == "T1"

    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps({"initial_facts": {}, "iterations": [payload]}),
        encoding="utf-8",
    )
    summary_program = _extract_repair_program(
        "render_failure_summary",
        "python3 - \"$data_path\" <<'PY'",
    )
    summary_result = _run_embedded_python(summary_program, str(data_path))

    assert summary_result.returncode == 0, summary_result.stderr
    summary = summary_result.stdout
    assert summary.startswith("## LAST EXECUTE ATTEMPT")
    assert "Blocked/deferred task: m7-13-full-suite-final-gate" in summary
    assert "Deferred by harness until baseline is available." in summary
    assert "baseline_test_failures is null" in summary
    assert "runner error exit code 2" in summary
    assert "pytest collection: 1 errors" in summary
    assert "8 consecutive execute=blocked" in summary
    assert "NOTE: this may be STALE" in summary
    assert "## Review Blocking Rework" in summary
    assert "concrete implementation blockers, not a human gate" in summary
    assert "T1: Backend agentic replay gate and path helpers are missing." in summary
    assert "evidence_file: vibecomfy/comfy_nodes/agent/routes.py" in summary
    assert "deterministic_check: python -m pytest tests/test_agentic_replay_routes.py -v" in summary


def test_repair_loop_summary_prefers_pending_execute_tasks_over_baseline_deferral(tmp_path: Path) -> None:
    workspace = tmp_path / "workflow"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)

    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "blocked",
                "latest_failure": {
                    "kind": "execution_blocked",
                    "phase": "execute",
                    "message": "execute blocked by quality gates",
                },
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "events.ndjson").write_text(
        "execute:authority_divergence | reason=missing_linked_evidence; task_id=T1\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_5.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {"task_id": "T5", "status": "done", "executor_notes": "completed"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "execute_batch_5_output.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {"task_id": "T5", "status": "done", "executor_notes": "completed"},
                ],
                "output": "T5 completed",
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "baseline_test_failures": None,
                "baseline_test_note": "Baseline capture failed: runner error (exit code: 4)",
                "tasks": [
                    {
                        "id": "T1",
                        "status": "skipped",
                        "reviewer_verdict": "deferred_baseline_unavailable",
                        "executor_notes": (
                            "Deferred by harness: baseline_test_failures is null, so this "
                            "no-new-failures checkpoint cannot compare against a recorded baseline."
                        ),
                    },
                    {"id": "T5", "status": "done", "executor_notes": "completed"},
                    {"id": "T6", "status": "pending"},
                    {"id": "T7", "status": "pending"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (chain_dir / "chain-demo.json").write_text(
        json.dumps({"current_plan_name": "demo-plan", "last_state": "blocked"}),
        encoding="utf-8",
    )

    collect_program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(collect_program, str(workspace), "demo", "chain", "")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)

    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps({"initial_facts": {}, "iterations": [payload]}),
        encoding="utf-8",
    )
    summary_program = _extract_repair_program(
        "render_failure_summary",
        "python3 - \"$data_path\" <<'PY'",
    )
    summary_result = _run_embedded_python(summary_program, str(data_path))

    assert summary_result.returncode == 0, summary_result.stderr
    summary = summary_result.stdout
    assert "Blocked/deferred task: none found in execute/finalize artifacts" in summary
    assert "Pending execute tasks: T6, T7" in summary
    assert "Blocked/deferred task: T1" not in summary


def test_repair_loop_collects_stale_state_classification(tmp_path: Path) -> None:
    workspace = tmp_path / "workflow"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)

    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "finalized",
                "latest_failure": {
                    "kind": "phase_failed",
                    "message": "phase 'execute' internal_error",
                    "phase": "execute",
                    "recorded_at": "2026-06-29T01:00:00Z",
                    "metadata": {"stderr": "unrecognized arguments: --retry-blocked-tasks"},
                },
                "history": [
                    {
                        "step": "execute",
                        "result": "blocked",
                        "timestamp": "2026-06-29T02:00:00Z",
                        "duration_ms": 0,
                        "artifact_hash": "sha256:repeat",
                        "output_file": "execution.json",
                    },
                    {
                        "step": "execute",
                        "result": "blocked",
                        "timestamp": "2026-06-29T02:01:00Z",
                        "duration_ms": 0,
                        "artifact_hash": "sha256:repeat",
                        "output_file": "execution.json",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "events.ndjson").write_text(
        json.dumps(
            {
                "seq": 10,
                "kind": "gate",
                "phase": "gate",
                "ts_utc": "2026-06-29T01:30:00Z",
                "payload": {"recommendation": "PROCEED"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (chain_dir / "chain-demo.json").write_text(
        json.dumps({"current_plan_name": "demo-plan", "last_state": "awaiting_human"}),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(program, str(workspace), "demo", "chain", "")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["failure_classification"] == "stale_state"
    assert payload["state_mismatch"]["detected"] is False
    stale = payload["stale_state"]
    assert stale["classification"] == "STALE STATE"
    assert stale["latest_failure_stale"] is True
    assert stale["latest_success_after_failure"]["timestamp"] == "2026-06-29T01:30:00Z"
    assert stale["stale_block_replay"]["detected"] is True
    assert stale["stale_block_replay"]["artifact_hash"] == "sha256:repeat"


def test_repair_loop_classifies_github_large_file_push_rejection(tmp_path: Path) -> None:
    workspace = tmp_path / "workflow"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)
    message = (
        "phase-complete callback failed after 'review': "
        "git push --no-verify origin HEAD:demo exited 1"
    )
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "failed",
                "latest_failure": {
                    "kind": "phase_callback_failed",
                    "message": message,
                    "phase": "review",
                    "recorded_at": "2026-07-02T15:32:20Z",
                },
            }
        ),
        encoding="utf-8",
    )
    (chain_dir / "chain-demo.json").write_text(
        json.dumps({"current_plan_name": "demo-plan", "last_state": "failed"}),
        encoding="utf-8",
    )
    (workspace / ".megaplan" / "cloud-chain-demo.log").write_text(
        "\n".join(
            [
                "[chain] git push --no-verify origin HEAD:demo -> rc=1",
                "remote: error: GH001: Large files detected.",
                "remote: error: File .megaplan/epics/demo-plan/events.jsonl is 101.74 MB; this exceeds GitHub's file size limit of 100.00 MB",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(program, str(workspace), "demo", "chain", "")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["failure_classification"] == "git_large_file_push_rejection"
    assert "GH001" in payload["chain_log_tail"]
    assert payload["plan_latest_failure"]["kind"] == "phase_callback_failed"


def test_repair_loop_collects_named_single_plan_in_mixed_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workflow"
    target = workspace / ".megaplan" / "plans" / "target-plan"
    unrelated = workspace / ".megaplan" / "plans" / "newer-unrelated"
    _write_plan(
        target,
        {
            "name": "target-plan",
            "current_state": "planning",
            "latest_failure": None,
            "history": [],
        },
        plan_v_bodies={"plan_v1.md": "target"},
        events_body=json.dumps({"kind": "plan_started", "phase": "plan"}) + "\n",
    )
    _write_plan(
        unrelated,
        {
            "name": "newer-unrelated",
            "current_state": "blocked",
            "latest_failure": {
                "kind": "phase_failed",
                "phase": "execute",
                "message": "newer unrelated failure",
            },
            "history": [{"step": "execute", "result": "error"}],
        },
        plan_v_bodies={"plan_v1.md": "unrelated"},
        events_body=json.dumps({"kind": "phase_end", "phase": "execute", "payload": {"status": "failed"}}) + "\n",
    )
    log_dir = workspace / ".megaplan" / "cloud-logs"
    log_dir.mkdir(parents=True)
    (log_dir / "target-plan-cloud.log").write_text("target plan log line\n", encoding="utf-8")
    old_ts = time.time() - 600
    new_ts = time.time()
    os.utime(target / "state.json", (old_ts, old_ts))
    os.utime(unrelated / "state.json", (new_ts, new_ts))

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(program, str(workspace), "single-session", "plan", "target-plan")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["run_kind"] == "plan"
    assert payload["requested_plan_name"] == "target-plan"
    assert payload["plan_latest_failure"]["plan_name"] == "target-plan"
    assert payload["plan_latest_failure"]["state_path"].endswith("/target-plan/state.json")
    assert payload["failure_classification"] == "unknown_failure_mode"
    assert "target plan log line" in payload["run_log_tail"]
    assert payload["chain_log_tail"] == ""
    assert payload["chain_state_summary"] == {}


def test_repair_loop_classifies_repeated_failure_signature_as_repairable(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workflow"
    plan_dir = workspace / ".megaplan" / "plans" / "target-plan"
    _write_plan(
        plan_dir,
        {
            "name": "target-plan",
            "current_state": "blocked",
            "latest_failure": {
                "kind": "repeated_failure_signature",
                "phase": "finalize",
                "message": (
                    "same semantic failure repeated 3 times: finalize: "
                    "test_blast_radius selectors are missing or empty"
                ),
                "metadata": {"count": 3},
            },
            "history": [],
        },
        plan_v_bodies={"plan_v1.md": "target"},
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(program, str(workspace), "single-session", "plan", "target-plan")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["failure_classification"] == "blocked_state_or_recovery_error"
    assert payload["plan_latest_failure"]["kind"] == "repeated_failure_signature"


def test_repair_loop_prefers_awaiting_human_over_timeout_text_in_prep_clarification(tmp_path: Path) -> None:
    workspace = tmp_path / "workflow"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "awaiting_human_verify",
                "latest_failure": None,
                "clarification": {
                    "source": "prep",
                    "questions": ["Should M1 target surviving workflow modules?"],
                },
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "events.ndjson").write_text(
        "\n".join(
            [
                json.dumps({"kind": "artifact_written", "payload": {"path": "prep.json"}}),
                json.dumps(
                    {
                        "kind": "state_written",
                        "payload": {
                            "state": {
                                "current_state": "awaiting_human_verify",
                                "config": {"test_baseline_timeout": 900},
                                "clarification": {"source": "prep", "questions": ["q1"]},
                            }
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(program, str(workspace), "demo", "plan", "demo-plan")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["failure_classification"] == "awaiting_human_user_action_gate"
    assert payload["plan_runtime_state"]["clarification_source"] == "prep"
    assert payload["plan_runtime_state"]["clarification_question_count"] == 1
    assert payload["plan_runtime_state"]["clarification_questions"] == [
        "Should M1 target surviving workflow modules?"
    ]
    assert "resume-clarify" in payload["stale_state"]["recommended_action"]


def test_repair_loop_clear_stale_state_trims_replay_tail_and_backs_up_phase_result(tmp_path: Path) -> None:
    plan_dir = tmp_path / "workflow" / ".megaplan" / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True)
    state_path = plan_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "latest_failure": {"kind": "phase_failed", "recorded_at": "2026-06-29T01:00:00Z"},
                "history": [
                    {"step": "gate", "result": "success", "timestamp": "2026-06-29T01:30:00Z"},
                    {
                        "step": "execute",
                        "result": "blocked",
                        "duration_ms": 0,
                        "artifact_hash": "sha256:repeat",
                        "timestamp": "2026-06-29T02:00:00Z",
                    },
                    {
                        "step": "execute",
                        "result": "blocked",
                        "duration_ms": 0,
                        "artifact_hash": "sha256:repeat",
                        "timestamp": "2026-06-29T02:01:00Z",
                    },
                ],
                "meta": {},
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "phase_result.json").write_text(
        json.dumps({"phase": "execute", "exit_kind": "blocked_by_prereq"}),
        encoding="utf-8",
    )
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(json.dumps({"initial_facts": {}, "iterations": []}), encoding="utf-8")
    failure_context = {
        "plan_latest_failure": {"state_path": str(state_path)},
        "stale_state": {
            "classification": "STALE STATE",
            "latest_failure_stale": True,
            "latest_success_after_failure": {"timestamp": "2026-06-29T01:30:00Z"},
            "stale_block_replay": {
                "detected": True,
                "artifact_hash": "sha256:repeat",
                "duration_ms": 0,
            },
        },
    }

    failure_context_path = tmp_path / "failure-context.json"
    failure_context_path.write_text(json.dumps(failure_context), encoding="utf-8")
    program = _extract_repair_program(
        "repair_clear_stale_state_if_needed",
        "PYTHONPATH=\"$ARNOLD_SRC:${PYTHONPATH:-}\" python3 - \"$DATA_FILE\" \"$failure_context_file\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path), str(failure_context_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("cleared:")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["latest_failure"] is None
    assert [item["step"] for item in state["history"]] == ["gate"]
    assert not (plan_dir / "phase_result.json").exists()
    assert list(plan_dir.glob("phase_result.stale-*.json"))
    repair_data = json.loads(data_path.read_text(encoding="utf-8"))
    assert repair_data["stale_state_actions"][0]["actions"]


def test_repair_loop_clear_stale_state_syncs_plan_chain_mismatch(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo-plan"
    chain_dir = tmp_path / ".megaplan" / "initiatives" / "demo" / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)
    state_path = plan_dir / "state.json"
    chain_path = chain_dir / "chain-demo.json"
    state_path.write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "finalized",
                "latest_failure": None,
                "meta": {},
            }
        ),
        encoding="utf-8",
    )
    chain_path.write_text(
        json.dumps(
            {
                "current_plan_name": "demo-plan",
                "last_state": "awaiting_human",
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(json.dumps({"initial_facts": {}, "iterations": []}), encoding="utf-8")
    failure_context = {
        "plan_latest_failure": {
            "plan_name": "demo-plan",
            "state_path": str(state_path),
            "current_state": "finalized",
        },
        "stale_state": {
            "classification": "NO LATEST FAILURE",
            "summary": "no latest_failure is set",
        },
        "state_mismatch": {
            "detected": True,
            "plan_state": "finalized",
            "chain_last_state": "awaiting_human",
            "plan_name": "demo-plan",
            "chain_plan_name": "demo-plan",
            "plan_state_path": str(state_path),
            "chain_state_path": str(chain_path),
        },
    }

    failure_context_path = tmp_path / "failure-context.json"
    failure_context_path.write_text(json.dumps(failure_context), encoding="utf-8")
    program = _extract_repair_program(
        "repair_clear_stale_state_if_needed",
        "PYTHONPATH=\"$ARNOLD_SRC:${PYTHONPATH:-}\" python3 - \"$DATA_FILE\" \"$failure_context_file\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path), str(failure_context_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("cleared:")
    assert "state mismatch detected + cleared" in result.stdout
    chain_state = json.loads(chain_path.read_text(encoding="utf-8"))
    assert chain_state["last_state"] == "finalized"
    records = chain_state["metadata"]["watchdog_repair_state_mismatch_clears"]
    assert records[0]["chain_last_state_was"] == "awaiting_human"
    repair_data = json.loads(data_path.read_text(encoding="utf-8"))
    action = repair_data["stale_state_actions"][0]
    assert action["state_mismatch"]["cleared"] is True
    assert repair_data["initial_facts"]["state_mismatch"]["cleared"] is True


def test_repair_loop_collects_state_meta_user_action_resolutions(tmp_path: Path) -> None:
    workspace = tmp_path / "workflow"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)

    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "finalized",
                "latest_failure": {"kind": "phase_failed", "message": "phase 'execute' internal_error"},
                "meta": {
                    "user_action_resolutions": {
                        "ua-01-decide-cleanup": {"state": "satisfied", "reason": "covered by evidence"}
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "user_actions": [
                    {
                        "id": "ua-01-decide-cleanup",
                        "phase": "before_execute",
                        "blocks_task_ids": ["T1"],
                        "rationale": "Maintainer decision affects cleanup.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "user_actions.md").write_text(
        "# User Actions\n\n- **ua-01-decide-cleanup**: Decide cleanup scope.\n",
        encoding="utf-8",
    )
    (chain_dir / "chain-demo.json").write_text(
        json.dumps({"current_plan_name": "demo-plan", "last_state": "awaiting_human"}),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(program, str(workspace), "demo", "chain", "")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["user_action_context"]["unresolved_user_actions"] == []


def test_repair_loop_collects_provider_profile_viability_for_unavailable_claude(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workflow"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)

    empty_path = tmp_path / "empty-bin"
    empty_path.mkdir()
    monkeypatch.setenv("PATH", str(empty_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)

    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "blocked",
                "resume_cursor": {"phase": "plan", "retry_strategy": "check_provider_and_retry"},
                "latest_failure": {
                    "kind": "external_error_resume_required",
                    "phase": "recover-blocked",
                    "message": (
                        "recover-blocked is for explicit task or quality blockers. "
                        "This blocked plan stopped on an external provider error; "
                        "fix provider/profile settings if needed, then run "
                        "`megaplan resume --plan demo-plan`."
                    ),
                },
                "history": [
                    {"step": "prep", "result": "success", "timestamp": "2026-07-11T01:38:14Z"},
                    {
                        "step": "plan",
                        "result": "error",
                        "message": "Codex usage limit reached. Re-run the same step on Codex once before changing agent.",
                        "timestamp": "2026-07-11T01:38:26Z",
                    },
                ],
                "config": {
                    "project_dir": str(workspace),
                    "profile": "all-claude",
                    "vendor": "claude",
                    "phase_model": [
                        "plan=claude:high",
                        "critique=claude",
                        "execute=claude",
                    ],
                },
                "meta": {},
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "events.ndjson").write_text("recover-blocked:phase_start\n", encoding="utf-8")
    (chain_dir / "chain-demo.json").write_text(
        json.dumps({"current_plan_name": "demo-plan", "last_state": "blocked"}),
        encoding="utf-8",
    )

    collect_program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(collect_program, str(workspace), "demo", "chain", "")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    viability = payload["provider_profile_viability"]
    assert viability["detected"] is True
    assert viability["current_profile"] == "all-claude"
    assert viability["claude_available"] is False
    assert viability["codex_available"] is True
    assert viability["deepseek_available"] is True
    assert viability["quota_in_history"] is True
    assert "Claude/Shannon is unavailable" in viability["diagnosis"]
    assert "all-deepseek-pro-direct" in viability["recommended_action"]
    assert "set-profile" in viability["vendor_switch_note"]


def test_repair_loop_summary_renders_provider_profile_viability_block(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps(
            {
                "initial_facts": {},
                "iterations": [
                    {
                        "failure_classification": "blocked_state_or_recovery_error",
                        "raw_failure_signals": ["latest_failure.message: external provider error"],
                        "run_log_tail": "resume failed",
                        "plan_events_tail": "recover-blocked:phase_start",
                        "plan_latest_failure": {
                            "current_state": "blocked",
                            "phase": "recover-blocked",
                            "kind": "external_error_resume_required",
                            "message": "external provider error",
                            "recorded_at": "2026-07-11T01:38:34Z",
                            "metadata": {"exit_code": 1},
                        },
                        "chain_state_summary": {
                            "last_state": "blocked",
                            "current_state": "",
                            "current_plan_name": "demo-plan",
                        },
                        "provider_profile_viability": {
                            "current_profile": "all-claude",
                            "current_vendor": "claude",
                            "codex_available": True,
                            "claude_available": False,
                            "deepseek_available": True,
                            "selected_specs": {
                                "plan": "claude:high",
                                "execute": "claude",
                            },
                            "floored_specs": {
                                "plan": "codex:high",
                                "execute": "codex",
                            },
                            "diagnosis": (
                                "current profile/phase_model targets Claude, but Claude/Shannon "
                                "is unavailable on this worker; recent plan history shows a "
                                "Codex quota failure"
                            ),
                            "recommended_action": (
                                "If escaping a Codex quota failure, do not switch to all-claude "
                                "on this worker. Prefer a DeepSeek-capable profile such as "
                                "all-deepseek-pro-direct or partnered-5."
                            ),
                            "vendor_switch_note": (
                                "`override set-profile` preserves the current premium vendor "
                                "when it rewrites named profiles."
                            ),
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "render_failure_summary",
        "python3 - \"$data_path\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path))

    assert result.returncode == 0, result.stderr
    summary = result.stdout
    assert "## Provider/Profile Viability" in summary
    assert "current profile=all-claude vendor=claude" in summary
    assert "available routes: codex=yes, claude=no, deepseek=yes" in summary
    assert "selected specs: plan=claude:high, execute=claude" in summary
    assert "available-model floor: plan=codex:high, execute=codex" in summary
    assert "all-deepseek-pro-direct or partnered-5" in summary
    assert "set-profile` preserves the current premium vendor" in summary


def test_repair_data_init_preserves_legacy_top_level_shape_via_contract(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    progress_path = tmp_path / "repair-progress.json"
    data_path.write_text(
        json.dumps(
            {
                "repair_run_count": 2,
                "attempt_counter": 7,
                "iterations": [{"attempt_id": 7, "legacy": True}],
            }
        ),
        encoding="utf-8",
    )
    failure_context = {
        "failure_classification": "blocked_state_or_recovery_error",
        "chain_log_tail": "context-chain-log",
        "chain_log_path": "/tmp/chain.log",
        "run_log_tail": "context-run-log",
        "run_log_path": "/tmp/run.log",
        "chain_recent_events": [{"kind": "phase_failed"}],
        "plan_events_tail": "plan-tail",
        "plan_events_path": "/tmp/events.ndjson",
        "stale_state": {"classification": "STALE STATE"},
        "state_mismatch": {"detected": False},
        "raw_failure_signals": ["latest_failure.kind: phase_failed"],
        "mechanical_log_tail": "mechanical-tail",
        "mechanical_log_path": "/tmp/mechanical.log",
        "plan_latest_failure": {"kind": "phase_failed"},
        "chain_state_summary": {"last_state": "blocked"},
        "plan_runtime_state": {"current_state": "blocked"},
        "last_gate": {"recommendation": "ITERATE"},
        "user_action_context": {"unresolved_user_actions": []},
        "execute_attempt_context": {"execution_batch": {"blocked_or_deferred_tasks": []}},
        "resolver_output": {"target_id": "demo-session:demo-plan", "authoritative_source": "marker"},
    }

    result = _run_repair_data_init(data_path, progress_path=progress_path, failure_context=failure_context)

    assert result.returncode == 0, result.stderr
    assert json.loads(data_path.read_text(encoding="utf-8")) == {
        "session": "demo-session",
        "workspace": "/tmp/workspace",
        "spec": "/tmp/workspace/.megaplan/initiatives/demo/chain.yaml",
        "run_kind": "chain",
        "plan_name": "demo-plan",
        "arnold_src": str(REPO_ROOT),
        "sync_branch": "editable-install",
        "run_dir": "/tmp/run-dir",
        "progress_path": str(progress_path),
        "repair_run_count": 3,
        "attempt_counter": 7,
        "initial_facts": {
            "relaunch_command": "python -m arnold_pipelines.megaplan chain tick",
            "initial_health": "dead",
            "marker_json": '{"run_kind":"chain"}',
            "source_git": "main\n",
            "workspace_git": "feature\n",
            "failure_context": failure_context,
            "chain_log_tail": "context-chain-log",
            "chain_log_path": "/tmp/chain.log",
            "run_log_tail": "context-run-log",
            "run_log_path": "/tmp/run.log",
            "chain_recent_events": [{"kind": "phase_failed"}],
            "plan_events_tail": "plan-tail",
            "plan_events_path": "/tmp/events.ndjson",
            "failure_classification": "blocked_state_or_recovery_error",
            "stale_state": {"classification": "STALE STATE"},
            "state_mismatch": {"detected": False},
            "raw_failure_signals": ["latest_failure.kind: phase_failed"],
            "mechanical_log_tail": "mechanical-tail",
            "mechanical_log_path": "/tmp/mechanical.log",
            "plan_latest_failure": {"kind": "phase_failed"},
            "chain_state_summary": {"last_state": "blocked"},
            "plan_runtime_state": {"current_state": "blocked"},
            "last_gate": {"recommendation": "ITERATE"},
            "user_action_context": {"unresolved_user_actions": []},
            "execute_attempt_context": {"execution_batch": {"blocked_or_deferred_tasks": []}},
            "resolver_output": {"target_id": "demo-session:demo-plan", "authoritative_source": "marker"},
            "watchdog_log_tail": "watchdog-log",
            "tmux_pane_tail": "tmux-pane",
            "chain_state_files": "/tmp/workspace/.megaplan/plans/.chains/chain-demo.json",
            "semantic_health": {},
            "semantic_context": {},
            "custody_projection": {},
        },
        "attempts": [{"attempt_id": 7, "legacy": True}],
        "current_attempt_id": None,
        "current_signature": {},
        "current_advancement_snapshot": {},
        "current_recurrence": {},
        "current_failure_context": failure_context,
        "run_recurrence_detected": False,
        "iterations": [],
        "outcome": "repair_launch_unverified",
        "request_id": "",
        "blocker_id": "",
        "schema_version": 1,
        "target": {"target_id": "demo-session:demo-plan", "authoritative_source": "marker"},
        "incident_id": "inc-demo-session",
        "attempt_ids": [],
        "verification": {},
        "discord_escalation": {},
        "known_prior_issue_refs": [],
    }


def test_repair_data_init_redacts_persisted_log_tails_and_failure_metadata(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    progress_path = tmp_path / "repair-progress.json"
    failure_context = {
        "failure_classification": "blocked_state_or_recovery_error",
        "chain_log_tail": "Authorization: Bearer bearer-secret-token-value",
        "chain_log_path": "/tmp/chain.log",
        "run_log_tail": "export API_TOKEN=abc1234567890",
        "run_log_path": "/tmp/run.log",
        "chain_recent_events": [{"kind": "phase_failed"}],
        "plan_events_tail": "curl --api-key sk-proj-abcdefghijklmnopqrstuvwxyz123456",
        "plan_events_path": "/tmp/events.ndjson",
        "stale_state": {"classification": "STALE STATE"},
        "state_mismatch": {"detected": False},
        "raw_failure_signals": ["Authorization: Bearer bearer-secret-token-value"],
        "mechanical_log_tail": "postgresql://arnold:swordfish@localhost:5432/app",
        "mechanical_log_path": "/tmp/mechanical.log",
        "plan_latest_failure": {
            "kind": "phase_failed",
            "metadata": {"stderr": "Authorization: Bearer bearer-secret-token-value"},
        },
        "chain_state_summary": {"last_state": "blocked"},
        "plan_runtime_state": {"current_state": "blocked"},
        "last_gate": {"recommendation": "ITERATE"},
        "user_action_context": {"unresolved_user_actions": []},
        "execute_attempt_context": {"execution_batch": {"blocked_or_deferred_tasks": []}},
        "resolver_output": {"target_id": "demo-session:demo-plan", "authoritative_source": "marker"},
    }

    result = _run_repair_data_init(data_path, progress_path=progress_path, failure_context=failure_context)

    assert result.returncode == 0, result.stderr
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    persisted = json.dumps(payload, sort_keys=True)
    assert "bearer-secret-token-value" not in persisted
    assert "abc1234567890" not in persisted
    assert "swordfish" not in persisted
    assert "sk-proj-abcdefghijklmnopqrstuvwxyz123456" not in persisted
    assert payload["initial_facts"]["chain_log_tail"] == f"Authorization: Bearer {REDACTION}"
    assert payload["initial_facts"]["run_log_tail"] == f"export API_TOKEN={REDACTION}"
    assert payload["initial_facts"]["mechanical_log_tail"] == f"postgresql://arnold:{REDACTION}@localhost:5432/app"


def test_repair_data_dev_and_mechanical_writers_preserve_legacy_shapes(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    report_path = tmp_path / "dev-report.json"
    progress_path = tmp_path / "repair-progress.json"
    failure_context = {
        "failure_classification": "cli_or_argument_error",
        "stale_state": {"classification": "LIVE FAILURE"},
        "state_mismatch": {"detected": False},
        "raw_failure_signals": ["stderr: unrecognized arguments"],
        "chain_log_tail": "chain-tail",
        "chain_log_path": "/tmp/chain.log",
        "run_log_tail": "run-tail",
        "run_log_path": "/tmp/run.log",
        "chain_recent_events": [{"kind": "phase_failed"}],
        "plan_events_tail": "events-tail",
        "plan_events_path": "/tmp/events.ndjson",
        "mechanical_log_tail": "mechanical-tail",
        "mechanical_log_path": "/tmp/mech.log",
        "plan_latest_failure": {"kind": "phase_failed", "metadata": {"stderr": "boom"}},
        "chain_state_summary": {"current_plan_name": "demo-plan", "last_state": "blocked"},
        "plan_runtime_state": {"current_state": "blocked"},
        "last_gate": {"recommendation": "ITERATE"},
        "user_action_context": {"unresolved_user_actions": [{"id": "ua-1"}]},
        "execute_attempt_context": {"execution_batch": {"blocked_or_deferred_tasks": [{"task_id": "T9"}]}},
        "resolver_output": {"target_id": "demo-session:demo-plan", "authoritative_source": "marker"},
    }
    init_result = _run_repair_data_init(data_path, progress_path=progress_path, failure_context=failure_context)
    assert init_result.returncode == 0, init_result.stderr
    report = {
        "pushed_commit": "abc1234",
        "hypothesis": "cli flags drifted",
        "what_tried": "removed unsupported flag",
        "validation": ["pytest tests/cloud/test_watchdog_wrappers.py"],
        "structural_pattern": "flag drift",
        "other_instantiations": ["other wrapper"],
        "human_review_recommendation": "audit caller defaults",
        "findings_doc_path": "/tmp/findings.md",
        "findings_doc_appended": True,
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")

    dev_program = _extract_repair_program(
        "repair_data_record_dev",
        "PYTHONPATH=\"$ARNOLD_SRC:${PYTHONPATH:-}\" python3 - \"$DATA_FILE\" \"$iteration\" \"$attempt_id\" \"$requested_model\" \"$dispatch_model\" \"$fallback_reason\" \"$report_path\" \"$turn_rc\" \"$before_sha\" \"$after_sha\" <<'PY'",
    )
    dev_result = _run_embedded_python(
        dev_program,
        str(data_path),
        "1",
        "4",
        "gpt-5.4",
        "gpt-5.5",
        "safety fallback",
        str(report_path),
        "17",
        "deadbeef",
        "abc1234",
    )
    assert dev_result.returncode == 0, dev_result.stderr

    mechanical_program = _extract_repair_program(
        "repair_data_record_mechanical",
        "PYTHONPATH=\"$ARNOLD_SRC:${PYTHONPATH:-}\" python3 - \"$DATA_FILE\" \"$iteration\" \"$attempt_id\" \"$status\" \"$detail\" \"$failure_context_file\" <<'PY'",
    )
    mechanical_failure_context_path = data_path.parent / "mechanical-failure-context.json"
    mechanical_failure_context_path.write_text(json.dumps(failure_context), encoding="utf-8")
    mechanical_result = _run_embedded_python(
        mechanical_program,
        str(data_path),
        "1",
        "4",
        "failed:retrying_failure",
        "launch blocked by prereq",
        str(mechanical_failure_context_path),
    )
    assert mechanical_result.returncode == 0, mechanical_result.stderr
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    assert payload["target"] == {"target_id": "demo-session:demo-plan", "authoritative_source": "marker"}
    assert payload["initial_facts"]["resolver_output"] == failure_context["resolver_output"]
    assert payload["iterations"][0]["resolver_output"] == failure_context["resolver_output"]
    assert payload["attempts"][0]["resolver_output"] == failure_context["resolver_output"]

    payload = json.loads(data_path.read_text(encoding="utf-8"))
    assert len(payload["iterations"]) == 1
    assert len(payload["attempts"]) == 1
    iteration = payload["iterations"][0]
    attempt = payload["attempts"][0]
    for item in (iteration, attempt):
        assert item["attempt_id"] == 4
        assert item["dev_model_requested"] == "gpt-5.4"
        assert item["dev_model"] == "gpt-5.5"
        assert item["dev_turn_rc"] == 17
        assert item["dev_fix_sha"] == ""
        assert item["dev_hypothesis"] == "cli flags drifted"
        assert item["dev_report"] == report
        assert item["failure_context"] == failure_context
        assert item["mechanical_launch"] == "failed:retrying_failure"
        assert item["mechanical_detail"] == "launch blocked by prereq"
    assert iteration["dev_report_path"] == str(report_path)
    assert iteration["dev_before_sha"] == "deadbeef"
    assert iteration["dev_after_sha"] == "abc1234"
    assert iteration["dev_fix_changed"] is False
    assert attempt["post_launch_failure_context"] == failure_context


def test_repair_data_records_iteration_zero_baseline_without_index_error(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "repair-data.json"
    failure_context_path = tmp_path / "failure-context.json"
    data_path.write_text('{"attempts": [], "iterations": []}\n', encoding="utf-8")
    failure_context_path.write_text(
        json.dumps(
            {
                "failure_classification": "stale_chain_state_after_terminal_plan",
                "chain_state_summary": {"last_state": "awaiting_pr_merge"},
                "plan_runtime_state": {"current_state": "done"},
            }
        ),
        encoding="utf-8",
    )
    program = _extract_repair_program(
        "repair_data_record_mechanical",
        "PYTHONPATH=\"$ARNOLD_SRC:${PYTHONPATH:-}\" python3 - \"$DATA_FILE\" \"$iteration\" \"$attempt_id\" \"$status\" \"$detail\" \"$failure_context_file\" <<'PY'",
    )

    result = _run_embedded_python(
        program,
        str(data_path),
        "0",
        "0",
        "failed:awaiting_pr_merge",
        "baseline supported CLI returned rc=0 but PR remains open",
        str(failure_context_path),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    assert payload["iterations"] == []
    assert payload["baseline_mechanical"]["i"] == 0
    assert payload["baseline_mechanical"]["mechanical_launch"] == (
        "failed:awaiting_pr_merge"
    )
    assert payload["baseline_mechanical"]["chain_state_summary"] == {
        "last_state": "awaiting_pr_merge"
    }


def test_repair_data_kimi_and_outcome_writers_preserve_legacy_shapes(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    report_path = tmp_path / "kimi-report.json"
    progress_path = tmp_path / "repair-progress.json"
    failure_context = {
        "failure_classification": "blocked_state_or_recovery_error",
        "stale_state": {"classification": "STALE STATE"},
        "state_mismatch": {"detected": False},
        "raw_failure_signals": ["stderr: repair still blocked"],
        "chain_log_tail": "chain-tail",
        "chain_log_path": "/tmp/chain.log",
        "run_log_tail": "run-tail",
        "run_log_path": "/tmp/run.log",
        "chain_recent_events": [{"kind": "phase_failed"}],
        "plan_events_tail": "events-tail",
        "plan_events_path": "/tmp/events.ndjson",
        "plan_latest_failure": {"kind": "phase_failed"},
        "chain_state_summary": {"current_plan_name": "demo-plan", "last_state": "blocked"},
        "plan_runtime_state": {"current_state": "blocked"},
        "last_gate": {"recommendation": "ITERATE"},
        "user_action_context": {"unresolved_user_actions": []},
        "execute_attempt_context": {"execution_batch": {"blocked_or_deferred_tasks": []}},
        "resolver_output": {"target_id": "demo-session:demo-plan", "authoritative_source": "marker"},
    }
    _run_repair_data_init_for_contract_tests(
        data_path,
        progress_path=progress_path,
        failure_context=failure_context,
    )
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    payload["attempt_counter"] = 7
    payload["current_attempt_id"] = 7
    payload["attempts"] = [{"attempt_id": 7, "repair_run_count": 1, "iteration": 1}]
    payload["iterations"] = [{"i": 1, "attempt_id": 7}]
    data_path.write_text(json.dumps(payload), encoding="utf-8")
    report = {
        "diagnosis": "repair loop still sees stale gating state",
        "why": "mechanical relaunch did not advance the plan",
        "launch_result": "no_progress",
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")

    kimi_program = _extract_repair_program(
        "repair_data_record_kimi",
        "PYTHONPATH=\"$ARNOLD_SRC:${PYTHONPATH:-}\" python3 - \"$DATA_FILE\" \"$iteration\" \"$attempt_id\" \"$status\" \"$report_path\" \"$turn_rc\" \"$failure_context_file\" <<'PY'",
    )
    kimi_failure_context_path = data_path.parent / "kimi-failure-context.json"
    kimi_failure_context_path.write_text(json.dumps(failure_context), encoding="utf-8")
    kimi_result = _run_embedded_python(
        kimi_program,
        str(data_path),
        "1",
        "7",
        "running",
        str(report_path),
        "23",
        str(kimi_failure_context_path),
    )
    assert kimi_result.returncode == 0, kimi_result.stderr

    outcome_program = _extract_repair_program(
        "repair_data_set_outcome",
        "PYTHONPATH=\"$ARNOLD_SRC:${PYTHONPATH:-}\" python3 - \"$DATA_FILE\" \"$outcome\" <<'PY'",
    )
    outcome_result = _run_embedded_python(outcome_program, str(data_path), "discord_escalated")
    assert outcome_result.returncode == 0, outcome_result.stderr

    payload = json.loads(data_path.read_text(encoding="utf-8"))
    assert payload["outcome"] == "discord_escalated"
    assert payload["iterations"] == [
        {
            "i": 1,
            "attempt_id": 7,
            "kimi_model": "kimi-k2.7-code",
            "kimi_turn_rc": 23,
            "kimi_launch": "running",
            "kimi_diagnosis": "repair loop still sees stale gating state",
            "why": "mechanical relaunch did not advance the plan",
            "failure_context": failure_context,
            "failure_classification": "blocked_state_or_recovery_error",
            "stale_state": {"classification": "STALE STATE"},
            "state_mismatch": {"detected": False},
            "raw_failure_signals": ["stderr: repair still blocked"],
            "chain_log_tail": "chain-tail",
            "chain_log_path": "/tmp/chain.log",
            "run_log_tail": "run-tail",
            "run_log_path": "/tmp/run.log",
            "chain_recent_events": [{"kind": "phase_failed"}],
            "plan_events_tail": "events-tail",
            "plan_events_path": "/tmp/events.ndjson",
            "plan_latest_failure": {"kind": "phase_failed"},
            "chain_state_summary": {"current_plan_name": "demo-plan", "last_state": "blocked"},
            "plan_runtime_state": {"current_state": "blocked"},
            "last_gate": {"recommendation": "ITERATE"},
            "user_action_context": {"unresolved_user_actions": []},
            "execute_attempt_context": {"execution_batch": {"blocked_or_deferred_tasks": []}},
            "resolver_output": {"target_id": "demo-session:demo-plan", "authoritative_source": "marker"},
            "kimi_report": report,
        }
    ]
    assert payload["attempts"] == [
        {
            "attempt_id": 7,
            "repair_run_count": 1,
            "iteration": 1,
            "kimi_model": "kimi-k2.7-code",
            "kimi_turn_rc": 23,
            "kimi_launch": "running",
            "kimi_diagnosis": "repair loop still sees stale gating state",
            "why": "mechanical relaunch did not advance the plan",
            "resolver_output": {"target_id": "demo-session:demo-plan", "authoritative_source": "marker"},
            "post_kimi_failure_context": failure_context,
            "kimi_report": report,
        }
    ]


def test_repair_clear_stale_state_preserves_legacy_repair_data_shapes(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo-plan"
    chain_dir = tmp_path / ".megaplan" / "initiatives" / "demo" / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)
    state_path = plan_dir / "state.json"
    chain_path = chain_dir / "chain-demo.json"
    state_path.write_text(
        json.dumps({"name": "demo-plan", "current_state": "finalized", "latest_failure": None, "meta": {}}),
        encoding="utf-8",
    )
    chain_path.write_text(
        json.dumps({"current_plan_name": "demo-plan", "last_state": "awaiting_human", "metadata": {}}),
        encoding="utf-8",
    )
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps(
            {
                "initial_facts": {
                    "failure_context": {
                        "stale_state": {"classification": "NO LATEST FAILURE"},
                        "state_mismatch": {"detected": True},
                    }
                },
                "iterations": [],
            }
        ),
        encoding="utf-8",
    )
    failure_context = {
        "plan_latest_failure": {
            "plan_name": "demo-plan",
            "state_path": str(state_path),
            "current_state": "finalized",
        },
        "stale_state": {
            "classification": "NO LATEST FAILURE",
            "summary": "no latest_failure is set",
        },
        "state_mismatch": {
            "detected": True,
            "plan_state": "finalized",
            "chain_last_state": "awaiting_human",
            "plan_name": "demo-plan",
            "chain_plan_name": "demo-plan",
            "plan_state_path": str(state_path),
            "chain_state_path": str(chain_path),
        },
    }

    failure_context_path = tmp_path / "failure-context.json"
    failure_context_path.write_text(json.dumps(failure_context), encoding="utf-8")
    program = _extract_repair_program(
        "repair_clear_stale_state_if_needed",
        "PYTHONPATH=\"$ARNOLD_SRC:${PYTHONPATH:-}\" python3 - \"$DATA_FILE\" \"$failure_context_file\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path), str(failure_context_path))

    assert result.returncode == 0, result.stderr
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    assert payload["stale_state_actions"] == [
        {
            "recorded_at": payload["stale_state_actions"][0]["recorded_at"],
            "actions": [
                "state mismatch detected + cleared (plan=finalized, chain was awaiting_human, synced)"
            ],
            "stale_state": {
                "classification": "NO LATEST FAILURE",
                "summary": "no latest_failure is set",
            },
            "state_mismatch": {
                "detected": True,
                "plan_state": "finalized",
                "chain_last_state": "awaiting_human",
                "plan_name": "demo-plan",
                "chain_plan_name": "demo-plan",
                "plan_state_path": str(state_path),
                "chain_state_path": str(chain_path),
                "cleared": True,
                "action_taken": "cleared chain last_state to match plan current_state (finalized)",
            },
            "state_path": str(state_path),
        }
    ]


def test_repair_clear_stale_state_syncs_chain_for_planned_state_mismatch(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(json.dumps({}), encoding="utf-8")
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "planned",
                "latest_failure": None,
            }
        ),
        encoding="utf-8",
    )
    chain_path = tmp_path / "chain.json"
    chain_path.write_text(
        json.dumps({"current_plan_name": "demo-plan", "last_state": "blocked"}),
        encoding="utf-8",
    )
    failure_context = {
        "stale_state": {
            "classification": "NO LATEST FAILURE",
            "summary": "no latest_failure is set",
        },
        "state_mismatch": {
            "detected": True,
            "plan_state": "planned",
            "chain_last_state": "blocked",
            "plan_name": "demo-plan",
            "chain_plan_name": "demo-plan",
            "plan_state_path": str(state_path),
            "chain_state_path": str(chain_path),
        },
    }

    failure_context_path = tmp_path / "failure-context.json"
    failure_context_path.write_text(json.dumps(failure_context), encoding="utf-8")
    program = _extract_repair_program(
        "repair_clear_stale_state_if_needed",
        "PYTHONPATH=\"$ARNOLD_SRC:${PYTHONPATH:-}\" python3 - \"$DATA_FILE\" \"$failure_context_file\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path), str(failure_context_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("cleared:")
    assert "state mismatch detected + cleared" in result.stdout
    chain_state = json.loads(chain_path.read_text(encoding="utf-8"))
    assert chain_state["last_state"] == "planned"
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    action = payload["stale_state_actions"][0]
    assert action["state_mismatch"]["cleared"] is True
    assert action["state_mismatch"]["action_taken"] == (
        "cleared chain last_state to match plan current_state (planned)"
    )
    assert payload["initial_facts"]["failure_context"]["state_mismatch"]["cleared"] is True
    assert payload["initial_facts"]["state_mismatch"]["action_taken"] == (
        "cleared chain last_state to match plan current_state (planned)"
    )


def test_repair_clear_stale_state_clears_dead_active_step_and_syncs_executed_chain(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(json.dumps({}), encoding="utf-8")
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "executed",
                "latest_failure": None,
                "resume_cursor": {"phase": "review", "retry_strategy": "manual_review"},
                "active_step": {"phase": "review", "worker_pid": -1},
            }
        ),
        encoding="utf-8",
    )
    chain_path = tmp_path / "chain.json"
    chain_path.write_text(
        json.dumps({"current_plan_name": "demo-plan", "last_state": "blocked"}),
        encoding="utf-8",
    )
    failure_context = {
        "failure_classification": "stale_state",
        "stale_state": {
            "classification": "NO LATEST FAILURE",
            "summary": "no latest_failure is set",
        },
        "state_mismatch": {
            "detected": True,
            "plan_state": "executed",
            "chain_last_state": "blocked",
            "plan_name": "demo-plan",
            "chain_plan_name": "demo-plan",
            "plan_state_path": str(state_path),
            "chain_state_path": str(chain_path),
        },
        "resolver_output": {
            "stale_evidence": [{"kind": "stale_active_step_dead_pid"}],
        },
    }

    failure_context_path = tmp_path / "failure-context.json"
    failure_context_path.write_text(json.dumps(failure_context), encoding="utf-8")
    program = _extract_repair_program(
        "repair_clear_stale_state_if_needed",
        "PYTHONPATH=\"$ARNOLD_SRC:${PYTHONPATH:-}\" python3 - \"$DATA_FILE\" \"$failure_context_file\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path), str(failure_context_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("cleared:")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert "active_step" not in state
    chain_state = json.loads(chain_path.read_text(encoding="utf-8"))
    assert chain_state["last_state"] == "executed"
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    action = payload["stale_state_actions"][0]
    assert "cleared orphaned active_step for dead worker PID" in action["actions"]
    assert action["state_mismatch"]["cleared"] is True


def test_repair_loop_summary_inlines_error_narrative_and_attempt_history(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps(
            {
                "initial_facts": {},
                "iterations": [
                    {
                        "i": 1,
                        "dev_model": "gpt-5.4",
                        "dev_summary": "cleared stale markers only",
                        "mechanical_launch": "failed:retrying_failure",
                        "kimi_launch": "failed:retrying_failure",
                        "why": "status label changed but same execute failure remained",
                    },
                    {
                        "i": 2,
                        "dev_model": "gpt-5.5",
                        "failure_classification": "cli_or_argument_error",
                        "raw_failure_signals": [
                            "__main__.py: error: unrecognized arguments: --confirm-destructive --user-approved"
                        ],
                        "chain_log_tail": "[chain] resuming existing plan demo-plan\n[auto demo-plan] phase 'execute' exited with internal_error",
                        "plan_events_tail": "execute:phase_failed | reason=cli rejected flags",
                        "plan_latest_failure": {
                            "current_state": "finalized",
                            "phase": "execute",
                            "iteration": 21,
                            "kind": "phase_failed",
                            "message": "phase 'execute' internal_error",
                            "recorded_at": "2026-06-28T19:30:34Z",
                            "state_path": "/tmp/demo/state.json",
                            "events_path": "/tmp/demo/events.ndjson",
                            "metadata": {"exit_code": 2},
                        },
                        "chain_state_summary": {
                            "path": "/tmp/demo/chain.json",
                            "last_state": "awaiting_human",
                            "current_plan_name": "demo-plan",
                        },
                        "user_action_context": {
                            "plan_dir": "/tmp/demo",
                            "user_actions_path": "/tmp/demo/user_actions.md",
                            "resolutions_path": "/tmp/demo/user_action_resolutions.json",
                            "finalize_path": "/tmp/demo/finalize.json",
                            "user_actions_md": "# User Actions\n\n- **ua-01-decide-cleanup**: Decide cleanup scope.",
                            "unresolved_user_actions": [
                                {
                                    "id": "ua-01-decide-cleanup",
                                    "phase": "before_execute",
                                    "blocks_task_ids": ["T1"],
                                    "resolution_state": "unresolved",
                                    "summary": "Decide cleanup scope.",
                                }
                            ],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "render_failure_summary",
        "python3 - \"$data_path\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path))

    assert result.returncode == 0, result.stderr
    summary = result.stdout
    assert "## Incident Snapshot" in summary
    assert "unrecognized arguments: --confirm-destructive --user-approved" in summary
    assert "[auto demo-plan] phase 'execute' exited with internal_error" in summary
    assert "## Prior repair attempts" in summary
    assert "i1 model=gpt-5.4 attempted=cleared stale markers only" in summary
    assert "plan events: /tmp/demo/events.ndjson" in summary
    assert "## User Action Gate" in summary
    assert "ua-01-decide-cleanup" in summary
    assert "user action resolutions: /tmp/demo/user_action_resolutions.json" in summary


def test_repair_loop_summary_falls_back_to_latest_failure_metadata(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps(
            {
                "initial_facts": {},
                "iterations": [
                    {
                        "i": 1,
                        "dev_model": "gpt-5.4",
                        "mechanical_launch": "failed:retrying_failure",
                        "chain_log_tail": "[chain] resuming existing plan demo-plan",
                        "plan_latest_failure": {
                            "current_state": "finalized",
                            "phase": "execute",
                            "iteration": 21,
                            "kind": "phase_failed",
                            "message": "phase 'execute' internal_error",
                            "metadata": {
                                "exit_code": 2,
                                "stderr": (
                                    "usage: __main__.py [-h]\n"
                                    "__main__.py: error: unrecognized arguments: --confirm-destructive --user-approved"
                                ),
                            },
                        },
                        "chain_state_summary": {
                            "last_state": "awaiting_human",
                            "current_plan_name": "demo-plan",
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "render_failure_summary",
        "python3 - \"$data_path\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path))

    assert result.returncode == 0, result.stderr
    summary = result.stdout
    assert "failure classification: cli_or_argument_error" in summary
    assert "latest_failure.metadata.stderr:" in summary
    assert "unrecognized arguments: --confirm-destructive --user-approved" in summary
    assert "latest_failure.metadata.exit_code: 2" in summary


def test_repair_loop_renders_recurrence_block_from_controlled_signature_history(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps(
            {
                "attempts": [
                    {
                        "attempt_id": 1,
                        "dev_model": "gpt-5.4",
                        "dev_summary": "patched prompt-path normalization only",
                        "dev_fix_sha": "abc1234",
                        "dev_hypothesis": "worker read stale prompt target",
                    },
                    {
                        "attempt_id": 2,
                        "dev_model": "gpt-5.5",
                        "dev_summary": "cleared stale state only",
                        "dev_fix_sha": "def5678",
                        "dev_hypothesis": "plan state was stale",
                    },
                ],
                "current_recurrence": {
                    "detected": True,
                    "attempt_number": 3,
                    "problem_signature": {
                        "failure_kind": "authority_divergence",
                        "current_state": "blocked",
                        "phase_or_step": "execute",
                        "milestone_or_plan": "m7-final-gate",
                        "gate_recommendation": "ITERATE",
                        "blocked_task_id": "m7-13-full-suite-final-gate",
                    },
                    "layer1": {"detected": True, "matching_attempt_ids": [1, 2], "repeat_count": 2},
                    "layer2": {
                        "detected": True,
                        "no_advance_dispatch_count": 3,
                        "min_dispatches": 3,
                        "window_seconds": 21600,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "render_recurrence_block",
        "python3 - \"$DATA_FILE\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path))

    assert result.returncode == 0, result.stderr
    block = result.stdout
    assert "## RECURRENCE EVIDENCE" in block
    assert "This is attempt 3 for the same controlled-field symptom (recurrence detected)." in block
    assert "The symptom came back despite these prior fixes:" in block
    assert "Recurrence means the prior attempts may have treated symptoms, not the cause." in block
    assert "Layer 1 fired" in block
    assert "Layer 2 fired" in block
    assert "authority_divergence" in block
    assert "attempt 1: model=gpt-5.4" in block
    assert "attempt 2: model=gpt-5.5" in block


def test_repair_loop_classifies_completed_chain_as_chain_completed(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": "",
                "current_state": "",
                "last_state": "done",
            }
        ),
        encoding="utf-8",
    )
    (workspace / ".megaplan" / "cloud-chain-demo-chain.log").write_text(
        "[chain] all milestones complete\n",
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(program, str(workspace), "demo-chain", "chain", "")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["failure_classification"] == "chain_completed"


def test_repair_loop_classifies_completed_chain_with_null_current_fields(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": None,
                "current_state": None,
                "last_state": "done",
                "events": [{"msg": "all milestones complete"}],
            }
        ),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(program, str(workspace), "demo-chain", "chain", "")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["failure_classification"] == "chain_completed"


def test_repair_loop_does_not_classify_partial_done_chain_as_completed(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        "\n".join(
            [
                "milestones:",
                "  - label: m1",
                "    title: M1",
                "  - label: m2",
                "    title: M2",
            ]
        ),
        encoding="utf-8",
    )
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": "",
                "current_state": "",
                "last_state": "done",
                "current_milestone_index": 1,
                "completed": [{"label": "m1", "status": "merged"}],
            }
        ),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(
        program,
        str(workspace),
        "demo-chain",
        "chain",
        "",
        str(workspace / ".megaplan" / "cloud-sessions"),
        str(workspace / ".megaplan" / "cloud-sessions" / "repair-data"),
        str(spec_path),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["failure_classification"] != "chain_completed"
    assert payload["chain_state_summary"]["last_state"] == "done"
    assert payload["chain_state_summary"]["milestone_count"] == 2
    assert payload["chain_state_summary"]["completed_count"] == 1


def test_repair_loop_reclassifies_completed_chain_history_unknown_sentinels(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps(
            {
                "iterations": [
                    {
                        "failure_classification": "timeout_or_hang",
                        "plan_latest_failure": {"kind": "phase_failed", "message": "phase failed"},
                        "raw_failure_signals": ["latest_failure.kind: phase_failed"],
                        "chain_state_summary": {
                            "last_state": "done",
                            "current_plan_name": "unknown",
                            "current_state": "unknown",
                            "events": [{"msg": "all milestones complete"}],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "render_failure_summary",
        "python3 - \"$data_path\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path))

    assert result.returncode == 0, result.stderr
    assert "failure classification: chain_completed" in result.stdout


def test_repair_loop_exits_immediately_for_completed_chain(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_root = tmp_path / "repair-root"
    workspace = tmp_path / "ws"
    bin_dir = tmp_path / "bin"
    marker_dir.mkdir()
    repair_root.mkdir()
    workspace.mkdir()
    bin_dir.mkdir()

    calls_log = tmp_path / "calls.log"
    for name in ("tmux", "codex"):
        path = bin_dir / name
        path.write_text(
            "#!/usr/bin/env bash\n"
            f"printf '%s\\n' {name!r} >> {str(calls_log)!r}\n"
            "exit 97\n",
            encoding="utf-8",
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    timeout_path = bin_dir / "timeout"
    timeout_path.write_text(
        "#!/usr/bin/env bash\n"
        "shift\n"
        "exec \"$@\"\n",
        encoding="utf-8",
    )
    timeout_path.chmod(timeout_path.stat().st_mode | stat.S_IXUSR)

    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    marker_path = marker_dir / "demo-session.json"
    marker_path.write_text(json.dumps({"run_kind": "chain"}), encoding="utf-8")
    _write_chain_state(
        workspace / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_plan_name": "demo-plan",
            "current_milestone_index": 3,
            "last_state": "done",
            "completed": [{"label": "m1"}, {"label": "m2"}, {"label": "m3"}],
            "milestones": [{"label": "m1"}, {"label": "m2"}, {"label": "m3"}],
        },
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "demo-plan",
        {
            "name": "demo-plan",
            "current_state": "blocked",
            "iteration": 3,
            "latest_failure": {"kind": "authority_divergence", "message": "stale", "recorded_at": "2026-06-29T00:00:00Z"},
        },
    )

    env = dict(os.environ)
    env.pop("CLOUD_WATCHDOG_REPAIR_LOOP_ACTIVE", None)
    env.pop("CLOUD_WATCHDOG_REPAIR_LOOP_SESSION", None)
    env.pop("CLOUD_WATCHDOG_REPAIR_LOOP_PID", None)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["CLOUD_WATCHDOG_MARKER_DIR"] = str(marker_dir)
    env["CLOUD_WATCHDOG_REPAIR_ROOT"] = str(repair_root)
    env["CLOUD_WATCHDOG_REPAIR_DATA_DIR"] = str(marker_dir / "repair-data")
    result = subprocess.run(
        ["bash", str(WRAPPER_DIR / "arnold-repair-loop"), "demo-session", str(workspace), str(spec_path)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    combined = f"{result.stdout}\n{result.stderr}"
    assert "chain already complete; no repair needed" in combined
    assert not calls_log.exists() or not calls_log.read_text(encoding="utf-8").strip()
    assert not (marker_dir / "demo-session.repair-loop.pid").exists()


def test_repair_loop_exits_for_terminal_plan_with_stale_chain_state(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "ws"
    marker_dir.mkdir()

    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones:\n  - label: m1\n", encoding="utf-8")
    _write_chain_state(
        workspace / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_plan_name": "demo-plan",
            "current_milestone_index": 0,
            "last_state": "validation_failed",
            "completed": [],
            "milestones": [{"label": "m1"}],
        },
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "demo-plan",
        {
            "name": "demo-plan",
            "current_state": "done",
            "iteration": 1,
            "latest_failure": None,
        },
    )

    script = "\n\n".join(
        [
            _extract_repair_function("repair_target_completion_status"),
            f"REMOTE_SPEC={str(spec_path)!r}",
            "SESSION=demo-session",
            f"MARKER_DIR={str(marker_dir)!r}",
            f"ARNOLD_SRC={str(REPO_ROOT)!r}",
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"repair_target_completion_status {str(workspace)!r} chain demo-plan",
        ]
    )
    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    fields = result.stdout.strip().split("\t")
    assert fields[0] == "0"
    assert fields[3].endswith("chain-demo.json")
    assert fields[5] == "done"


def test_repair_loop_terminal_plan_cannot_override_incomplete_chain_without_sidecar(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones:\n  - label: m1\n  - label: m2\n", encoding="utf-8")
    _write_chain_state(
        workspace / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_plan_name": "sprint-1",
            "current_milestone_index": 0,
            "last_state": "blocked",
            "completed": [],
        },
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "sprint-1",
        {
            "name": "sprint-1",
            "current_state": "done",
            "active_step": None,
        },
    )

    script = "\n\n".join(
        [
            _extract_repair_function("repair_target_completion_status"),
            f"REMOTE_SPEC={str(spec_path)!r}",
            "SESSION=demo-session",
            f"MARKER_DIR={str(marker_dir)!r}",
            f"ARNOLD_SRC={str(REPO_ROOT)!r}",
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"repair_target_completion_status {str(workspace)!r} chain sprint-1",
        ]
    )
    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    fields = result.stdout.strip().split("\t")
    assert fields[0] == "0"
    assert fields[3].endswith("chain-demo.json")
    assert fields[5] == "done"



def test_repair_source_workspace_accepts_authenticated_engine_remote(tmp_path: Path) -> None:
    arnold_src = tmp_path / "arnold-src"
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    marker_path = tmp_path / "marker.json"
    log_path = tmp_path / "repair.log"
    arnold_src.mkdir()
    workspace.mkdir()
    run_dir.mkdir()

    subprocess.run(["git", "init", str(arnold_src)], check=True, capture_output=True, text=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(arnold_src),
            "remote",
            "add",
            "origin",
            "https://x-access-token:demo-token@github.com/acme/demo.git",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "init", str(workspace)], check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-C", str(workspace), "remote", "add", "origin", "https://github.com/acme/demo.git"],
        check=True,
        capture_output=True,
        text=True,
    )
    marker_path.write_text(json.dumps({"repo_url": "https://github.com/acme/demo.git"}), encoding="utf-8")

    script = "\n".join(
        [
            _extract_repair_function("repair_source_workspace_if_possible"),
            f"RUN_DIR={shlex.quote(str(run_dir))}",
            f"ARNOLD_SRC={shlex.quote(str(arnold_src))}",
            f"MARKER_PATH={shlex.quote(str(marker_path))}",
            f"WORKSPACE={shlex.quote(str(workspace))}",
            f"LOG={shlex.quote(str(log_path))}",
            "SYNC_BRANCH=editible-install",
            "require_repair_lock_held() { :; }",
            "ensure_repair_budget_available() { :; }",
            "log() { printf '%s\\n' \"$*\" >> \"$LOG\"; }",
            "repair_source_workspace_if_possible >/dev/null 2>&1 || true",
            "cat \"$RUN_DIR/source-workspace-repair.json\"",
        ]
    )
    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["reason"] == "workspace_git_present"
    assert "source_repo_identity_mismatch" not in log_path.read_text(encoding="utf-8")


def test_repair_source_workspace_redacts_authenticated_mismatch_details(tmp_path: Path) -> None:
    arnold_src = tmp_path / "arnold-src"
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    marker_path = tmp_path / "marker.json"
    log_path = tmp_path / "repair.log"
    arnold_src.mkdir()
    workspace.mkdir()
    run_dir.mkdir()

    subprocess.run(["git", "init", str(arnold_src)], check=True, capture_output=True, text=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(arnold_src),
            "remote",
            "add",
            "origin",
            "https://x-access-token:demo-token@github.com/acme/demo.git",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    marker_path.write_text(json.dumps({"repo_url": "https://github.com/acme/other.git"}), encoding="utf-8")

    script = "\n".join(
        [
            _extract_repair_function("repair_source_workspace_if_possible"),
            f"RUN_DIR={shlex.quote(str(run_dir))}",
            f"ARNOLD_SRC={shlex.quote(str(arnold_src))}",
            f"MARKER_PATH={shlex.quote(str(marker_path))}",
            f"WORKSPACE={shlex.quote(str(workspace))}",
            f"LOG={shlex.quote(str(log_path))}",
            "SYNC_BRANCH=editible-install",
            "require_repair_lock_held() { :; }",
            "ensure_repair_budget_available() { :; }",
            "log() { printf '%s\\n' \"$*\" >> \"$LOG\"; }",
            "repair_source_workspace_if_possible >/dev/null 2>&1 || true",
            "cat \"$RUN_DIR/source-workspace-repair.json\"",
        ]
    )
    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["reason"] == "source_repo_identity_mismatch"
    assert payload["details"] == {
        "source_origin": "github.com/acme/demo",
        "expected_origin": "github.com/acme/other",
    }
    assert "demo-token" not in result.stdout


def test_repair_loop_terminal_plan_is_not_complete_when_chain_health_is_incomplete(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        "milestones:\n"
        "  - label: m1\n"
        "  - label: m2\n",
        encoding="utf-8",
    )
    _write_chain_state(
        workspace / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_plan_name": "demo-plan",
            "current_milestone_index": 1,
            "last_state": "authority_divergence",
            "completed": [{"label": "m1", "status": "done"}],
        },
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "demo-plan",
        {"name": "demo-plan", "current_state": "done"},
    )
    (marker_dir / "demo-session.chain-health.progress.json").write_text(
        json.dumps(
            {
                "chain_complete": False,
                "completed_count": 1,
                "milestone_count": 2,
                "pr_number": 90,
                "pr_state": "open",
            }
        ),
        encoding="utf-8",
    )

    script = "\n\n".join(
        [
            _extract_repair_function("repair_target_completion_status"),
            f"REMOTE_SPEC={str(spec_path)!r}",
            "SESSION=demo-session",
            f"MARKER_DIR={str(marker_dir)!r}",
            f"repair_target_completion_status {str(workspace)!r} chain ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    fields = result.stdout.strip().split("\t")
    assert fields[0] == "0"

def test_watchdog_liveness_is_scoped_to_marked_chain_spec() -> None:
    text = _wrapper("arnold-watchdog")

    assert 'local remote_spec="$3"' in text
    assert "ps -eww -o args=" in text
    assert 'grep -Fq -- "$remote_spec"' in text
    assert 'health="$(session_health_status "$session" "$workspace" "$remote_spec" "$run_kind" "$plan_name")"' in text



def test_watchdog_terminal_plan_does_not_complete_chain_when_health_says_incomplete(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        "milestones:\n"
        "  - label: m1\n"
        "  - label: m2\n",
        encoding="utf-8",
    )
    _write_chain_state(
        workspace / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_plan_name": "demo-plan",
            "current_milestone_index": 1,
            "last_state": "authority_divergence",
            "completed": [{"label": "m1", "status": "done"}],
        },
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "demo-plan",
        {"name": "demo-plan", "current_state": "done"},
    )
    (marker_dir / "demo-session.chain-health.progress.json").write_text(
        json.dumps(
            {
                "chain_complete": False,
                "completed_count": 1,
                "milestone_count": 2,
                "pr_number": 90,
                "pr_state": "open",
            }
        ),
        encoding="utf-8",
    )
    current_target = {
        "plan_state": {"current_state": "done"},
        "stale_evidence": [{"kind": "stale_chain_state_after_terminal_plan"}],
    }
    script = "\n\n".join(
        [
            _extract_wrapper_function("session_terminal_status"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"session_terminal_status demo-session {str(workspace)!r} {str(spec_path)!r} chain {shlex.quote(json.dumps(current_target))} {str(marker_dir)!r}",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""

def test_watchdog_checks_plan_phase_health_even_when_session_alive() -> None:
    text = _wrapper("arnold-watchdog")

    assert "plan_phase_health_status()" in text
    assert 'phase_health="$(plan_phase_health_status "$workspace" "$run_kind" "$plan_name")"' in text
    assert 'if failure_kind != "phase_failed":' in text
    assert "success_after_failure" in text
    assert 'f"recorded={recorded_at or' in text
    assert 'session alive but plan unhealthy' in text
    assert 'report_item "$report_items" "$session" "repair" "repair_running"' in text
    assert 'report_item "$report_items" "$session" "repair" "repair_dispatched"' in text


def test_watchdog_plan_status_exports_stale_active_step_pid(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    initiative_dir = workspace / ".megaplan" / "initiatives" / "demo"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)
    initiative_dir.mkdir(parents=True)
    spec_path = initiative_dir / "chain.yaml"
    spec_path.write_text("milestones:\n  - label: m1\n", encoding="utf-8")
    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"chain-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": "demo-plan",
                "current_milestone_index": 0,
                "last_state": "initialized",
                "completed": [],
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "initialized",
                "active_step": {
                    "phase": "prep",
                    "worker_pid": 99999999,
                    "attempt": 1,
                },
            }
        ),
        encoding="utf-8",
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            f"plan_attention_status_env {str(workspace)!r} {str(spec_path)!r} chain ''",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert "PLAN_STATUS_ACTIVE_STEP_PRESENT=1" in lines
    assert "PLAN_STATUS_ACTIVE_STEP_PHASE=prep" in lines
    assert "PLAN_STATUS_ACTIVE_STEP_WORKER_PID=99999999" in lines
    assert "PLAN_STATUS_ACTIVE_STEP_PID_ALIVE=0" in lines


def test_watchdog_routes_dead_active_step_to_repair_dispatch() -> None:
    text = _wrapper("arnold-watchdog")

    assert 'PLAN_STATUS_ACTIVE_STEP_PRESENT=0' in text
    assert 'PLAN_STATUS_ACTIVE_STEP_PID_ALIVE=' in text
    assert 'stale_active_step: plan=${PLAN_STATUS_PLAN_NAME:-unknown}' in text
    assert (
        'repair_unintended_stop "$report_items" "$session" "$workspace" "$remote_spec" '
        '"$stale_active_summary"'
    ) in text


def test_watchdog_reaper_is_wired_into_scan_and_report_summary() -> None:
    text = _wrapper("arnold-watchdog")

    assert 'REAP_AGE_SECS="${CLOUD_WATCHDOG_REAP_AGE_SECS:-7200}"' in text
    assert 'REAP_ORPHAN_AGE_SECS="${CLOUD_WATCHDOG_REAP_ORPHAN_AGE_SECS:-3900}"' in text
    assert 'REAP_STALL_GRACE_SECS="${CLOUD_WATCHDOG_REAP_STALL_GRACE_SECS:-900}"' in text
    assert 'REAP_STALL_IDLE_SECS="${CLOUD_WATCHDOG_REAP_STALL_IDLE_SECS:-600}"' in text
    assert 'KIMI_OPERATOR_ROOT="${KIMI_GOAL_OPERATOR_ROOT:-/workspace/kimi-goal-operator}"' in text
    assert "reap_stale_repairs()" in text
    assert "reap_stalled_repair_candidates()" in text
    assert 'reap_stale_repairs "$report_items"' in text
    assert '"reaped_repairs": len(reaped)' in text
    assert 'report_item "$report_items" "${session:-}" "reap" "reaped"' in text


def test_watchdog_reap_decision_helper_reaps_only_stale_cloud_repairs(tmp_path: Path) -> None:
    module = _load_reap_module(tmp_path)

    over_age = module.decide_reap(
        {
            "pid": 4100,
            "ppid": 4000,
            "pgid": 4100,
            "etimes": 7201,
            "args": "/usr/local/bin/arnold-kimi-goal-operator demo-session /tmp/ws /tmp/spec.json",
        },
        7200,
        3900,
    )
    assert over_age["reap"] is True
    assert over_age["rule"] == "age_backstop"
    assert over_age["session"] == "demo-session"

    orphaned = module.decide_reap(
        {
            "pid": 5100,
            "ppid": 1,
            "pgid": 5000,
            "etimes": 3901,
            "args": (
                "python3 -m arnold.agent.run_agent "
                "--query='The user's invariant is: workflows on this Hetzner worker should never pause unexpectedly. "
                "Current Incident: Session: orphan-session Workspace: /tmp/ws'"
            ),
        },
        7200,
        3900,
    )
    assert orphaned["reap"] is True
    assert orphaned["rule"] == "orphan_fast_path"
    assert orphaned["session"] == "orphan-session"

    under_age = module.decide_reap(
        {
            "pid": 6100,
            "ppid": 6000,
            "pgid": 6000,
            "etimes": 600,
            "args": (
                "codex exec --sandbox danger-full-access "
                "'You are the watchdog repair-loop dev-fix agent for a stopped Arnold cloud session. "
                "Context: Session: fresh-session Workspace: /tmp/ws'"
            ),
        },
        7200,
        3900,
    )
    assert under_age["reap"] is False
    assert under_age["reason"] == "under_age"

    watchdog = module.decide_reap(
        {
            "pid": 7100,
            "ppid": 1,
            "pgid": 7100,
            "etimes": 9000,
            "args": "bash /usr/local/bin/arnold-watchdog --once",
        },
        7200,
        3900,
    )
    assert watchdog["reap"] is False
    assert watchdog["reason"] == "non_target"

    auditor = module.decide_reap(
        {
            "pid": 7200,
            "ppid": 1,
            "pgid": 7200,
            "etimes": 9000,
            "args": "bash /usr/local/bin/arnold-progress-auditor --once",
        },
        7200,
        3900,
    )
    assert auditor["reap"] is False
    assert auditor["reason"] == "non_target"

    non_arnold = module.decide_reap(
        {
            "pid": 7300,
            "ppid": 1,
            "pgid": 7300,
            "etimes": 99999,
            "args": "python3 -m http.server 8080",
        },
        7200,
        3900,
    )
    assert non_arnold["reap"] is False
    assert non_arnold["reason"] == "non_target"


def test_watchdog_progress_reap_decision_uses_log_idle_and_fails_safe(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    operator_root = tmp_path / "kimi-goal-operator"
    marker_dir.mkdir()
    operator_root.mkdir()
    now = time.time()

    stale_dir = operator_root / "20260628T000000Z-demo-session"
    stale_dir.mkdir()
    stale_operator = stale_dir / "operator.log"
    stale_codex = stale_dir / "codex-repair.log"
    stale_operator.write_text("operator\n", encoding="utf-8")
    stale_codex.write_text("codex\n", encoding="utf-8")
    stale_ts = now - 901
    os.utime(stale_operator, (stale_ts, stale_ts))
    os.utime(stale_codex, (stale_ts, stale_ts))
    os.utime(stale_dir, (stale_ts, stale_ts))

    stale_rows = (
        "4100 4000 4100 1800 "
        "/usr/local/bin/arnold-kimi-goal-operator demo-session /tmp/ws /tmp/spec.json\n"
    )
    stale_out = _run_repair_stall(tmp_path, stale_rows, marker_dir, operator_root)
    assert len(stale_out) == 1
    stale_fields = stale_out[0].split("\t")
    assert stale_fields[0] == "4100"
    assert stale_fields[6] == "stalled"
    assert stale_fields[7].startswith("stall_idle_")
    assert stale_fields[8] == str(stale_dir)
    assert int(stale_fields[9]) >= 600
    snapshot = marker_dir / "demo-session.reap-progress.json"
    snap_payload = json.loads(snapshot.read_text(encoding="utf-8"))
    assert snap_payload["operator_dir"] == str(stale_dir)
    assert "last_advance_ts" in snap_payload

    active_dir = operator_root / "20260628T000500Z-active-session"
    active_dir.mkdir()
    active_operator = active_dir / "operator.log"
    active_operator.write_text("still making progress\n", encoding="utf-8")
    active_ts = now - 30
    os.utime(active_operator, (active_ts, active_ts))
    os.utime(active_dir, (active_ts, active_ts))
    active_rows = (
        "5100 5000 5100 1800 "
        "/usr/local/bin/arnold-kimi-goal-operator active-session /tmp/ws /tmp/spec.json\n"
    )
    assert _run_repair_stall(tmp_path, active_rows, marker_dir, operator_root) == []
    active_snapshot = marker_dir / "active-session.reap-progress.json"
    assert active_snapshot.exists()

    unmappable_rows = (
        "6100 6000 6100 1800 "
        "/usr/local/bin/arnold-kimi-goal-operator missing-session /tmp/ws /tmp/spec.json\n"
    )
    assert _run_repair_stall(tmp_path, unmappable_rows, marker_dir, operator_root) == []
    assert not (marker_dir / "missing-session.reap-progress.json").exists()


def test_watchdog_kimi_operator_dedupe_does_not_match_its_own_grep() -> None:
    text = _wrapper("arnold-watchdog")

    assert 'pathlib.Path(f"/proc/{pid}/cmdline").read_bytes()' in text
    assert 'if pid in {self_pid, parent_pid}:' in text
    assert 'args[idx + 1] == session_name' in text
    assert 'args[idx + 1] == session' in text
    assert 'printf \'%s/%s.kimi-pgid\' "$MARKER_DIR" "$1"' in text
    assert 'kill -0 -- "-$pgid"' in text
    assert 'grep -F "[a]rnold-kimi-goal-operator $session "' not in text


def test_watchdog_kimi_repair_is_backgrounded_so_it_cannot_block_the_tick() -> None:
    text = _wrapper("arnold-watchdog")

    # The bounded repair loop is launched in the background (setsid ... &) so a
    # repair on one session cannot block the tick from scanning/reporting the
    # other sessions.
    assert "dispatch_kimi_repair()" in text
    assert "python3 -P -m arnold_pipelines.megaplan.managed_agent run" in text
    assert "--run-kind automatic_repair" in text
    assert 'setsid "${managed_cmd[@]}"' in text
    assert 'PRIMARY_REPAIR_BIN="${CLOUD_WATCHDOG_PRIMARY_REPAIR_BIN:-$PRIMARY_REPAIR_SOURCE_BIN}"' in text
    assert "kimi_dispatch_marker_set" in text
    assert "mechanical_relaunch_attempted_previously" in text
    assert "kimi_dispatch_failed_previously" in text
    # The direct-relaunch fallback consumes the marker (repair loop tried and exited w/o recovery).
    assert "session stopped; repair loop tried and exited without recovery -> direct relaunch" in text
    assert "session stopped; mechanical relaunch first" in text
    assert "session stopped after mechanical relaunch: background-dispatched repair loop" in text
    # The marker is cleared once the session is observed alive + healthy.
    assert "kimi_dispatch_marker_clear" in text
    assert 'rm -f "$(kimi_dispatch_marker_path "$1")" "$(kimi_pgid_path "$1")"' in text
    assert 'kill -- "-$pgid"' in text

    # No bare synchronous foreground Kimi invocation remains: every operator
    # call site either guards (kimi_operator_running), dispatches in the
    # background (dispatch_kimi_repair / setsid), or is a marker/log line.
    for ln in text.splitlines():
        if 'arnold-kimi-goal-operator "$session" "$workspace" "$remote_spec"' in ln:
            assert any(tok in ln for tok in (
                "setsid", "dispatch_kimi_repair", "kimi_operator_running",
                "kimi_dispatch", "log ",
            )), f"bare synchronous Kimi invocation remains: {ln!r}"


def test_watchdog_managed_repair_dispatches_pin_the_selected_runtime() -> None:
    text = _wrapper("arnold-watchdog")

    assert text.count("python3 -P -m arnold_pipelines.megaplan.managed_agent run") == 2
    assert text.count("PYTHONSAFEPATH=1 \\") >= 4
    assert "route_l1_launch_failure_to_meta_repair" in text
    assert text.count(
        'route_l1_launch_failure_to_meta_repair "$session" "$workspace" "$remote_spec" "$report_items"'
    ) == 2
    repair_unintended = text[text.index("repair_unintended_stop() {"):text.index("compare_needs_human_to_resolver() {")]
    assert "route_l1_launch_failure_to_meta_repair" in repair_unintended
    assert text.index("route_l1_launch_failure_to_meta_repair()") < text.index(
        'log "session requires human review session=$session'
    )


def test_watchdog_failed_launch_releases_only_exact_unbound_claim(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    queue_dir = repair_requests.repair_queue_dir(marker_dir)
    owner_pid = os.getpid()
    released_blocker = "blocker:v1:release"
    retained_blocker = "blocker:v1:retained"
    repair_requests.claim_active_repair_request(
        queue_dir,
        blocker_id=released_blocker,
        request_id="req-release",
        actor="arnold-watchdog",
        session="demo-session",
        pid=owner_pid,
    )
    repair_requests.claim_active_repair_request(
        queue_dir,
        blocker_id=retained_blocker,
        request_id="req-retained",
        actor="arnold-watchdog",
        session="demo-session",
        pid=owner_pid,
        extra={
            "managed_agent_run_id": "managed-run-live",
            "managed_manifest_path": "/tmp/managed-run-live/manifest.json",
        },
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("release_failed_repair_launch_claim"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            (
                "release_failed_repair_launch_claim demo-session req-release "
                f"{released_blocker!r} 99999999 {owner_pid}; echo released:$?"
            ),
            (
                "release_failed_repair_launch_claim demo-session req-retained "
                f"{retained_blocker!r} 99999999 {owner_pid}; echo retained:$?"
            ),
        ]
    )
    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == ["released:0", "retained:1"]
    assert not repair_requests.active_repair_claim_lock_dir(queue_dir, released_blocker).exists()
    assert repair_requests.active_repair_claim_lock_dir(queue_dir, retained_blocker).exists()


def test_watchdog_routes_confirmed_l1_launch_failure_to_l2() -> None:
    script = "\n\n".join(
        [
            _extract_wrapper_function("route_l1_launch_failure_to_meta_repair"),
            """
REPAIR_DISPATCH_RESULT=launch_failed
dispatch_meta_repair() {
  echo "META:$5" >&2
  REPAIR_DISPATCH_RESULT=dispatched
  return 0
}
log() { echo "LOG:$*" >&2; }
report_item() { echo "REPORT:$3:$4:$5"; }
route_l1_launch_failure_to_meta_repair demo-session /tmp/ws /tmp/spec /tmp/report
echo "status:$REPAIR_DISPATCH_RESULT"
""".strip(),
        ]
    )
    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == [
        "REPORT:meta_repair:dispatched:L2 took custody after confirmed L1 launch failure",
        "status:dispatched",
    ]
    assert "META:model_tool_launch_failure" in result.stderr
    assert "L2 now has custody" in result.stderr


def test_retained_goal_launch_failure_transfers_custody_to_l2() -> None:
    script = "\n\n".join(
        [
            _extract_wrapper_function("route_l1_launch_failure_to_meta_repair"),
            _extract_wrapper_function("repair_unintended_stop"),
            """
REPAIR_DISPATCH_RESULT=unavailable
repair_loop_busy_state() { echo none; }
repair_unhealthy_session() { REPAIR_DISPATCH_RESULT=launch_failed; return 1; }
dispatch_meta_repair() { REPAIR_DISPATCH_RESULT=dispatched; return 0; }
log() { :; }
report_item() { echo "$3:$4:$5"; }
repair_unintended_stop /tmp/report demo-session /tmp/ws /tmp/spec retained_goal_owner_missing
echo "status:$REPAIR_DISPATCH_RESULT"
""".strip(),
        ]
    )
    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == [
        "meta_repair:dispatched:L2 took custody after confirmed L1 launch failure",
        "status:dispatched",
    ]


def test_watchdog_repair_dispatch_is_scoped_per_session() -> None:
    text = _wrapper("arnold-watchdog")

    assert "repair_pidfile_path()" in text
    assert "repair_loop_pid_matches_session()" in text
    assert "repair_loop_busy_state()" in text
    assert 'repair_busy="$(repair_loop_busy_state "$session")"' in text
    assert 'pidfile="$(repair_pidfile_path "$session")"' in text
    assert 'if repair_loop_pid_matches_session "$existing_pid" "$session"; then' in text
    assert "another repair loop already running; waiting turn" in text


def test_watchdog_kimi_operator_running_falls_back_to_pgid_pidfile_and_clear_removes_it(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    session = "demo-session"
    pgid_path = marker_dir / f"{session}.kimi-pgid"
    marker_path = marker_dir / f"{session}.kimi-dispatch"
    pgid_path.write_text("4242\n", encoding="utf-8")
    marker_path.write_text("2026-06-28T00:00:00Z\n", encoding="utf-8")

    script = "\n\n".join(
        [
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("kimi_dispatch_marker_clear"),
            _extract_wrapper_function("kimi_operator_running"),
            f"""
MARKER_DIR={str(marker_dir)!r}
pgrep() {{
  return 1
}}
kill() {{
  if [[ "$#" -eq 3 && "$1" == "-0" && "$2" == "--" && "$3" == "-4242" ]]; then
    return 0
  fi
  return 1
}}
ps() {{
  cat <<'EOF'
 4242 python3 -m arnold.agent.run_agent --goal repair
EOF
}}
if kimi_operator_running {session!r}; then
  echo running
else
  echo stopped
fi
kimi_dispatch_marker_clear {session!r}
if [[ ! -e {str(pgid_path)!r} && ! -e {str(marker_path)!r} ]]; then
  echo cleared
fi
""".strip(),
        ]
    )
    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == ["running", "cleared"]


def test_watchdog_skips_same_session_dispatch_when_repair_loop_is_already_running(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = workspace / "demo-spec.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    report_path = tmp_path / "report.tsv"

    script = "\n\n".join(
        [
            _extract_wrapper_function("safe_name"),
            _extract_wrapper_function("repair_pidfile_path"),
            _extract_wrapper_function("repair_loop_pid_matches_session"),
            _extract_wrapper_function("repair_loop_busy_state"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo stopped; }
plan_attention_status_env() { return 0; }
kimi_operator_running() { [[ "$1" == "demo-session" ]]; }
mechanical_relaunch_attempted_previously() { return 1; }
kimi_dispatch_failed_previously() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_running\trepair already running\t" in report
    assert "DISPATCH" not in result.stderr
    assert "TMUX" not in result.stderr


def test_watchdog_allows_concurrent_repairs_for_different_sessions(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    log_path = tmp_path / "watchdog.log"
    launch_log = tmp_path / "repair-launches.log"
    repair_bin = tmp_path / "fake-repair-loop"
    repair_bin.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$1\" >> {str(launch_log)!r}\n"
        "sleep 5\n",
        encoding="utf-8",
    )
    repair_bin.chmod(repair_bin.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("safe_name"),
            _extract_wrapper_function("repair_pidfile_path"),
            _extract_wrapper_function("repair_loop_pid_matches_session"),
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("kimi_dispatch_marker_set"),
            _extract_wrapper_function("kimi_operator_running"),
            _extract_wrapper_function("repair_loop_busy_state"),
            _extract_wrapper_function("emit_watchdog_incident_bridge_event"),
            _extract_wrapper_function("confirm_managed_agent_dispatch"),
            _extract_wrapper_function("dispatch_kimi_repair"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"PRIMARY_REPAIR_BIN={str(repair_bin)!r}",
            f"PRIMARY_REPAIR_BASENAME={repair_bin.name!r}",
            f"LOG={str(log_path)!r}",
            """
log() { printf '%s\n' "$*" >> "$LOG"; }
dispatch_kimi_repair demo-a /tmp/ws /tmp/spec
echo "first:${REPAIR_DISPATCH_RESULT:-unset}"
dispatch_kimi_repair demo-b /tmp/ws /tmp/spec
echo "second:${REPAIR_DISPATCH_RESULT:-unset}"
for _ in {1..20}; do
  [[ -f __LAUNCH_LOG__ ]] && [[ "$(wc -l < __LAUNCH_LOG__)" -ge 2 ]] && break
  sleep 0.1
done
if [[ -f "$(kimi_pgid_path demo-a)" ]]; then
  demo_pgid="$(cat "$(kimi_pgid_path demo-a)")"
  kill -- "-$demo_pgid" 2>/dev/null || kill "$demo_pgid" 2>/dev/null || true
fi
if [[ -f "$(kimi_pgid_path demo-b)" ]]; then
  demo_pgid="$(cat "$(kimi_pgid_path demo-b)")"
  kill -- "-$demo_pgid" 2>/dev/null || kill "$demo_pgid" 2>/dev/null || true
fi
sleep 0.1
""".replace("__LAUNCH_LOG__", shlex.quote(str(launch_log))).strip(),
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == ["first:dispatched", "second:dispatched"]
    assert sorted(launch_log.read_text(encoding="utf-8").strip().splitlines()) == ["demo-a", "demo-b"]


def test_watchdog_dispatch_skips_duplicate_same_session_repair(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "watchdog.log"
    repair_bin = tmp_path / "fake-repair-loop"
    repair_bin.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    repair_bin.chmod(repair_bin.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("dispatch_kimi_repair"),
            f"PRIMARY_REPAIR_BIN={str(repair_bin)!r}",
            f"LOG={str(log_path)!r}",
            """
log() { printf '%s\n' "$*" >> "$LOG"; }
repair_loop_busy_state() { echo same_session; }
emit_watchdog_incident_bridge_event() { :; }
dispatch_kimi_repair demo-a /tmp/ws /tmp/spec
echo "${REPAIR_DISPATCH_RESULT:-unset}"
""".strip(),
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "busy"
    assert "repair loop already active; skipping dispatch session=demo-a" in log_path.read_text(
        encoding="utf-8"
    )


def test_watchdog_dispatch_skips_when_request_claim_is_already_held(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    log_path = tmp_path / "watchdog.log"
    launch_log = tmp_path / "repair-launches.log"
    repair_bin = tmp_path / "fake-repair-loop"
    repair_bin.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$1\" >> {str(launch_log)!r}\n"
        "sleep 5\n",
        encoding="utf-8",
    )
    repair_bin.chmod(repair_bin.stat().st_mode | stat.S_IXUSR)
    blocker_id = "blocker:v1:test"
    request_id = "req-test"
    repair_requests.claim_active_repair_request(
        repair_requests.repair_queue_dir(marker_dir),
        blocker_id=blocker_id,
        request_id=request_id,
        actor="other-trigger",
        session="demo-claimed",
        pid=os.getpid(),
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("safe_name"),
            _extract_wrapper_function("repair_pidfile_path"),
            _extract_wrapper_function("repair_loop_pid_matches_session"),
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("kimi_dispatch_marker_set"),
            _extract_wrapper_function("kimi_operator_running"),
            _extract_wrapper_function("repair_loop_busy_state"),
            _extract_wrapper_function("emit_watchdog_incident_bridge_event"),
            _extract_wrapper_function("claim_active_repair_launch"),
            _extract_wrapper_function("dispatch_kimi_repair"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"PRIMARY_REPAIR_BIN={str(repair_bin)!r}",
            f"PRIMARY_REPAIR_BASENAME={repair_bin.name!r}",
            f"LOG={str(log_path)!r}",
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"PLAN_STATUS_BLOCKER_ID={blocker_id!r}",
            f"PLAN_STATUS_REQUEST_ID={request_id!r}",
            "PLAN_STATUS_DISPATCH_DECISION=dispatch_l1_repair",
            """
log() { printf '%s\n' "$*" >> "$LOG"; }
dispatch_kimi_repair demo-claimed /tmp/ws /tmp/spec
echo "status:${REPAIR_DISPATCH_RESULT:-unset}"
""".strip(),
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == ["status:busy"]
    assert not launch_log.exists()
    assert "repair request already claimed; skipping dispatch session=demo-claimed request=req-test" in log_path.read_text(
        encoding="utf-8"
    )


def test_watchdog_dispatch_reclaims_stale_request_claim_and_launches(tmp_path: Path) -> None:
    marker_dir = tmp_path / ".megaplan" / "cloud-sessions"
    marker_dir.mkdir(parents=True)
    log_path = tmp_path / "watchdog.log"
    launch_log = tmp_path / "repair-launches.log"
    repair_bin = tmp_path / "fake-repair-loop"
    repair_bin.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$1\" >> {str(launch_log)!r}\n"
        "sleep 5\n",
        encoding="utf-8",
    )
    repair_bin.chmod(repair_bin.stat().st_mode | stat.S_IXUSR)
    blocker_id = "blocker:v1:test-stale"
    request_id = "req-live"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repair_requests.claim_active_repair_request(
        repair_requests.repair_queue_dir(marker_dir),
        blocker_id=blocker_id,
        request_id="req-stale",
        actor="other-trigger",
        session="demo-a",
        pid=99999999,
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("claim_active_repair_launch"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            (
                "claim_active_repair_launch demo-a "
                f"{shlex.quote(str(workspace))} /tmp/spec "
                f"{shlex.quote(blocker_id)} {shlex.quote(request_id)}"
            ),
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "claimed"
    assert not launch_log.exists()


def test_watchdog_claim_refuses_dispatch_without_request_and_blocker_identity(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / ".megaplan" / "cloud-sessions"
    marker_dir.mkdir(parents=True)
    script = "\n\n".join(
        [
            _extract_wrapper_function("claim_active_repair_launch"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            "PLAN_STATUS_DISPATCH_DECISION=",
            "claim_active_repair_launch demo-session /tmp/workspace /tmp/spec",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 1
    assert result.stdout.strip() == "missing_identity"


def test_watchdog_claim_accepts_inherited_goal_request_and_blocker_identity(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / ".megaplan" / "cloud-sessions"
    marker_dir.mkdir(parents=True)
    script = "\n\n".join(
        [
            _extract_wrapper_function("claim_active_repair_launch"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            "PLAN_STATUS_DISPATCH_DECISION=",
            (
                "claim_active_repair_launch demo-session /tmp/workspace /tmp/spec "
                "blocker:v1:goal-owner-missing request-current-plan"
            ),
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0
    assert result.stdout.strip() == "claimed"


def test_watchdog_kimi_dispatch_emits_incident_dispatch_statuses(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repair_dir = marker_dir / "repair-data"
    repair_dir.mkdir()
    (repair_dir / "demo-session.repair-data.json").write_text(
        json.dumps({"incident_id": "inc-600"}),
        encoding="utf-8",
    )
    log_path = tmp_path / "watchdog.log"
    repair_bin = tmp_path / "fake-repair-loop"
    repair_bin.write_text("#!/usr/bin/env bash\nsleep 5\n", encoding="utf-8")
    repair_bin.chmod(repair_bin.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("safe_name"),
            _extract_wrapper_function("repair_pidfile_path"),
            _extract_wrapper_function("repair_loop_pid_matches_session"),
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("kimi_dispatch_marker_set"),
            _extract_wrapper_function("kimi_operator_running"),
            _extract_wrapper_function("repair_loop_busy_state"),
            _extract_wrapper_function("emit_watchdog_incident_bridge_event"),
            _extract_wrapper_function("confirm_managed_agent_dispatch"),
            _extract_wrapper_function("dispatch_kimi_repair"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_dir)!r}",
            f"PRIMARY_REPAIR_BIN={str(repair_bin)!r}",
            f"PRIMARY_REPAIR_BASENAME={repair_bin.name!r}",
            f"LOG={str(log_path)!r}",
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            """
log() { printf '%s\n' "$*" >> "$LOG"; }
repair_loop_busy_state() {
  if [[ -f "$(kimi_dispatch_marker_path "$1")" ]]; then echo same_session; else echo none; fi
}
dispatch_kimi_repair demo-session __WORKSPACE__ /tmp/spec.yaml
echo "first:${REPAIR_DISPATCH_RESULT:-unset}"
sleep 0.2
dispatch_kimi_repair demo-session __WORKSPACE__ /tmp/spec.yaml
echo "second:${REPAIR_DISPATCH_RESULT:-unset}"
if [[ -f "$(kimi_pgid_path demo-session)" ]]; then
  demo_pgid="$(cat "$(kimi_pgid_path demo-session)")"
  kill -- "-$demo_pgid" 2>/dev/null || kill "$demo_pgid" 2>/dev/null || true
fi
""".replace("__WORKSPACE__", shlex.quote(str(workspace))).strip(),
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == ["first:dispatched", "second:busy"]
    payloads = _read_incident_event_payloads(workspace)
    dispatch_payloads = [payload for payload in payloads if payload["type"] == "dispatch"]
    assert [payload["outcome"] for payload in dispatch_payloads] == ["dispatched", "busy"]
    assert {payload["type"] for payload in payloads} >= {"claim.acquired", "repair_attempt"}
    assert dispatch_payloads[0]["decision"]["repair_actor"] == "immediate_repair"
    marker_fields = (marker_dir / "demo-session.kimi-dispatch").read_text().strip().split("\t")
    assert marker_fields[:2] == ["arnold-dispatch-marker-v2", "managed_agent"]
    managed_run_id, managed_manifest_path = marker_fields[3:5]
    managed = json.loads(Path(managed_manifest_path).read_text(encoding="utf-8"))
    assert managed["run_id"] == managed_run_id
    assert managed["launch_provenance"]["origin_kind"] == "watchdog_repair"


def test_watchdog_meta_dispatch_emits_incident_statuses(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repair_dir = marker_dir / "repair-data"
    repair_dir.mkdir(parents=True)
    (repair_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
            {"incident_id": "inc-601", "blocker_id": "blocker:v1:test"}
        ),
        encoding="utf-8",
    )
    meta_dir = repair_dir / "meta"
    meta_dir.mkdir()
    (meta_dir / "existing-001.json").write_text(
        json.dumps(
            {
                "meta_repair_id": "existing-001",
                "session": "demo-session",
                "blocker_id": "blocker:v1:test",
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"
    fake_bin = tmp_path / "arnold-meta-repair-loop"
    fake_bin.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_bin.chmod(0o755)

    script = _build_meta_dispatch_script(
        marker_dir,
        report_path,
        meta_repair_bin=str(fake_bin),
        log_path=str(log_path),
        extra_lines=[
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"dispatch_meta_repair demo-session {str(workspace)!r} /tmp/spec.yaml {str(report_path)!r}",
            'echo "disabled:${REPAIR_DISPATCH_RESULT:-unset}"',
        ],
    )
    script = script.replace("META_REPAIR_ENABLED_FLAG=1", "META_REPAIR_ENABLED_FLAG=0")

    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "disabled:disabled" in result.stdout

    script_recursive = _build_meta_dispatch_script(
        marker_dir,
        report_path,
        meta_repair_bin=str(fake_bin),
        log_path=str(log_path),
        extra_lines=[
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"dispatch_meta_repair demo-session {str(workspace)!r} /tmp/spec.yaml {str(report_path)!r}",
            'echo "recursive:${REPAIR_DISPATCH_RESULT:-unset}"',
        ],
    )
    result_recursive = subprocess.run(
        ["bash", "-lc", script_recursive],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result_recursive.returncode == 0, result_recursive.stderr
    assert "recursive:recursive" in result_recursive.stdout
    payloads = _read_incident_event_payloads(workspace)
    assert [payload["outcome"] for payload in payloads] == ["disabled", "recursion_blocked"]
    assert all(payload["decision"]["repair_actor"] == "meta_repair" for payload in payloads)


@pytest.mark.parametrize(
    ("case_name", "script_body", "expected_outcome"),
    [
        (
            "stale",
            """
session_health_status() { echo stale; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
chain_health_status() {
  CHAIN_HEALTH_STATUS=ok
  CHAIN_HEALTH_SUMMARY=
  CHAIN_HEALTH_ARTIFACT_PATH=
  CHAIN_HEALTH_LOG_MESSAGE=
}
repair_unhealthy_session() { return 0; }
dispatch_kimi_repair() { REPAIR_DISPATCH_RESULT=dispatched; return 0; }
mechanical_relaunch_attempted_previously() { return 1; }
kimi_dispatch_failed_previously() { return 1; }
kimi_dispatch_marker_set() { :; }
kimi_dispatch_marker_clear() { :; }
""",
            "stale",
        ),
        (
            "stopped",
            """
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
chain_health_status() {
  CHAIN_HEALTH_STATUS=ok
  CHAIN_HEALTH_SUMMARY=
  CHAIN_HEALTH_ARTIFACT_PATH=
  CHAIN_HEALTH_LOG_MESSAGE=
}
dispatch_kimi_repair() { REPAIR_DISPATCH_RESULT=dispatched; return 0; }
mechanical_relaunch_attempted_previously() { return 0; }
kimi_dispatch_failed_previously() { return 1; }
kimi_dispatch_marker_set() { :; }
kimi_dispatch_marker_clear() { :; }
""",
            "stopped",
        ),
        (
            "unhealthy",
            """
session_health_status() { echo alive; }
plan_phase_health_status() { echo unhealthy_plan; }
plan_progress_stall_status() { echo ok; }
chain_health_status() {
  CHAIN_HEALTH_STATUS=ok
  CHAIN_HEALTH_SUMMARY=
  CHAIN_HEALTH_ARTIFACT_PATH=
  CHAIN_HEALTH_LOG_MESSAGE=
}
dispatch_kimi_repair() { REPAIR_DISPATCH_RESULT=dispatched; return 0; }
""",
            "unhealthy",
        ),
        (
            "progress_stall",
            """
session_health_status() { echo alive; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo progress_stall:demo-plan iteration=9; }
chain_health_status() {
  CHAIN_HEALTH_STATUS=ok
  CHAIN_HEALTH_SUMMARY=
  CHAIN_HEALTH_ARTIFACT_PATH=
  CHAIN_HEALTH_LOG_MESSAGE=
}
repair_unintended_stop() { return 0; }
dispatch_kimi_repair() { REPAIR_DISPATCH_RESULT=dispatched; return 0; }
""",
            "progress_stall",
        ),
        (
            "chain_health_failure",
            """
session_health_status() { echo dead; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
chain_health_status() {
  CHAIN_HEALTH_STATUS=chain_large_file_push_rejection
  CHAIN_HEALTH_SUMMARY=chain cycle detected
  CHAIN_HEALTH_ARTIFACT_PATH=/tmp/chain-health.json
  CHAIN_HEALTH_LOG_MESSAGE=
}
dispatch_kimi_repair() { REPAIR_DISPATCH_RESULT=dispatched; return 0; }
""",
            "chain_health_failure",
        ),
        (
            "state_mismatch",
            """
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
chain_health_status() {
  CHAIN_HEALTH_STATUS=ok
  CHAIN_HEALTH_SUMMARY=
  CHAIN_HEALTH_ARTIFACT_PATH=
  CHAIN_HEALTH_LOG_MESSAGE=
}
plan_attention_status_env() {
  cat <<'EOF'
PLAN_STATUS_STATE_MISMATCH=1
PLAN_STATUS_STATE_MISMATCH_SUMMARY='plan/chain mismatch detected'
EOF
}
dispatch_kimi_repair() { REPAIR_DISPATCH_RESULT=dispatched; return 0; }
""",
            "state_mismatch",
        ),
    ],
)
def test_launch_chain_tick_emits_incident_detection_outcomes(
    tmp_path: Path,
    case_name: str,
    script_body: str,
    expected_outcome: str,
) -> None:
    marker_dir = tmp_path / f"markers-{case_name}"
    marker_dir.mkdir()
    repair_dir = marker_dir / "repair-data"
    repair_dir.mkdir()
    workspace = tmp_path / f"workspace-{case_name}"
    workspace.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    (repair_dir / "demo-session.repair-data.json").write_text(
        json.dumps({"incident_id": f"inc-{case_name}"}),
        encoding="utf-8",
    )
    report_path = tmp_path / f"report-{case_name}.tsv"
    log_path = tmp_path / f"watchdog-{case_name}.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("emit_watchdog_incident_bridge_event"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_dir)!r}",
            f"LOG={str(log_path)!r}",
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            """
report_item() { :; }
log() { printf '%s\n' "$*" >> "$LOG"; }
session_terminal_status() { return 0; }
resolve_existing_remote_spec() { printf '%s\n' "$3"; }
repair_needs_human_path() { printf '%s\n' "$REPAIR_DATA_DIR/$1.needs-human.json"; }
repair_needs_human_matches_current_plan() { return 1; }
workspace_has_other_alive_session() { return 1; }
notify_needs_human() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
repair_loop_busy_state() { echo none; }
plan_attention_status_env() { return 0; }
plan_terminal_status() { echo none; }
ensure_install_or_repair() { return 0; }
tmux() { return 1; }
""".strip(),
            script_body.strip(),
            (
                f"launch_chain_tick demo-session {str(workspace)!r} "
                f"{str(spec_path)!r} {str(report_path)!r} chain '' ''"
            ),
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    payloads = _read_incident_event_payloads(workspace)
    assert payloads[0]["type"] == "detection"
    assert payloads[0]["outcome"] == expected_outcome


def test_repair_loop_serializes_same_session_invocations_and_cleans_pidfile_on_term(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_root = tmp_path / "repair-root"
    workspace = tmp_path / "ws"
    bin_dir = tmp_path / "bin"
    marker_dir.mkdir()
    repair_root.mkdir()
    workspace.mkdir()
    bin_dir.mkdir()

    marker_path = marker_dir / "demo-session.json"
    marker_path.write_text(
        json.dumps({"run_kind": "plan", "plan_name": "demo-plan", "relaunch_command": "true"}),
        encoding="utf-8",
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "demo-plan",
        {
            "name": "demo-plan",
            "current_state": "blocked",
            "iteration": 1,
            "latest_failure": {
                "kind": "phase_failed",
                "message": "boom",
                "recorded_at": "2026-06-29T00:00:00Z",
                "metadata": {"exit_code": 1},
            },
        },
    )

    timeout_path = bin_dir / "timeout"
    timeout_path.write_text(
        "#!/usr/bin/env bash\n"
        "shift\n"
        "exec \"$@\"\n",
        encoding="utf-8",
    )
    timeout_path.chmod(timeout_path.stat().st_mode | stat.S_IXUSR)
    codex_path = bin_dir / "codex"
    codex_path.write_text(
        "#!/usr/bin/env bash\n"
        "sleep 5\n",
        encoding="utf-8",
    )
    codex_path.chmod(codex_path.stat().st_mode | stat.S_IXUSR)
    launcher_path = tmp_path / "launcher.py"
    launcher_path.write_text("import time\n\ntime.sleep(5)\n", encoding="utf-8")

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["CLOUD_WATCHDOG_MARKER_DIR"] = str(marker_dir)
    env["CLOUD_WATCHDOG_REPAIR_ROOT"] = str(repair_root)
    env["CLOUD_WATCHDOG_REPAIR_DATA_DIR"] = str(marker_dir / "repair-data")
    env["CLOUD_WATCHDOG_HERMES_LAUNCHER"] = str(launcher_path)

    args = ["bash", str(WRAPPER_DIR / "arnold-repair-loop"), "demo-session", str(workspace), "/tmp/spec.json"]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    pidfile = marker_dir / "demo-session.repair-loop.pid"
    try:
        for _ in range(300):
            if pidfile.exists():
                break
            time.sleep(0.05)
        assert pidfile.exists(), "repair loop never claimed pidfile"

        second = subprocess.run(args, capture_output=True, text=True, env=env, check=False)
        assert second.returncode == 75
        assert "another repair loop is already active" in f"{second.stdout}\n{second.stderr}"
    finally:
        proc.terminate()
        proc.wait(timeout=15)

    assert not pidfile.exists()


def test_repair_loop_reclaims_stale_pidfile_on_start(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_root = tmp_path / "repair-root"
    workspace = tmp_path / "ws"
    bin_dir = tmp_path / "bin"
    marker_dir.mkdir()
    repair_root.mkdir()
    workspace.mkdir()
    bin_dir.mkdir()

    marker_path = marker_dir / "demo-session.json"
    marker_path.write_text(
        json.dumps({"run_kind": "plan", "plan_name": "demo-plan", "relaunch_command": "true"}),
        encoding="utf-8",
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "demo-plan",
        {
            "name": "demo-plan",
            "current_state": "blocked",
            "iteration": 1,
            "latest_failure": {
                "kind": "phase_failed",
                "message": "boom",
                "recorded_at": "2026-06-29T00:00:00Z",
                "metadata": {"exit_code": 1},
            },
        },
    )
    stale_pidfile = marker_dir / "demo-session.repair-loop.pid"
    stale_pidfile.write_text("999999\n", encoding="utf-8")

    timeout_path = bin_dir / "timeout"
    timeout_path.write_text(
        "#!/usr/bin/env bash\n"
        "shift\n"
        "exec \"$@\"\n",
        encoding="utf-8",
    )
    timeout_path.chmod(timeout_path.stat().st_mode | stat.S_IXUSR)
    codex_path = bin_dir / "codex"
    codex_path.write_text(
        "#!/usr/bin/env bash\n"
        "sleep 5\n",
        encoding="utf-8",
    )
    codex_path.chmod(codex_path.stat().st_mode | stat.S_IXUSR)
    launcher_path = tmp_path / "launcher.py"
    launcher_path.write_text("import time\n\ntime.sleep(5)\n", encoding="utf-8")

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["CLOUD_WATCHDOG_MARKER_DIR"] = str(marker_dir)
    env["CLOUD_WATCHDOG_REPAIR_ROOT"] = str(repair_root)
    env["CLOUD_WATCHDOG_REPAIR_DATA_DIR"] = str(marker_dir / "repair-data")
    env["CLOUD_WATCHDOG_HERMES_LAUNCHER"] = str(launcher_path)

    proc = subprocess.Popen(
        ["bash", str(WRAPPER_DIR / "arnold-repair-loop"), "demo-session", str(workspace), "/tmp/spec.json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        for _ in range(300):
            if stale_pidfile.exists() and stale_pidfile.read_text(encoding="utf-8").strip() == str(proc.pid):
                break
            time.sleep(0.05)
        if proc.poll() is not None:
            stdout, stderr = proc.communicate()
            pytest.fail(
                f"repair loop exited before claiming pidfile rc={proc.returncode} "
                f"stdout={stdout!r} stderr={stderr!r}"
            )
        assert stale_pidfile.read_text(encoding="utf-8").strip() == str(proc.pid)
    finally:
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=15)

    combined = f"{stdout}\n{stderr}"
    assert "stale repair pidfile detected; reclaiming" in combined
    assert not stale_pidfile.exists()


def test_repair_loop_reclaims_pidfile_after_kill9_with_child_alive(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_root = tmp_path / "repair-root"
    workspace = tmp_path / "ws"
    bin_dir = tmp_path / "bin"
    codex_pids = tmp_path / "codex-pids.txt"
    marker_dir.mkdir()
    repair_root.mkdir()
    workspace.mkdir()
    bin_dir.mkdir()

    (marker_dir / "demo-session.json").write_text(
        json.dumps({"run_kind": "plan", "plan_name": "demo-plan", "relaunch_command": "true"}),
        encoding="utf-8",
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "demo-plan",
        {
            "name": "demo-plan",
            "current_state": "blocked",
            "iteration": 1,
            "latest_failure": {
                "kind": "phase_failed",
                "message": "boom",
                "recorded_at": "2026-06-29T00:00:00Z",
                "metadata": {"exit_code": 1},
            },
        },
    )

    timeout_path = bin_dir / "timeout"
    timeout_path.write_text(
        "#!/usr/bin/env bash\n"
        "shift\n"
        "exec \"$@\"\n",
        encoding="utf-8",
    )
    timeout_path.chmod(timeout_path.stat().st_mode | stat.S_IXUSR)
    codex_path = bin_dir / "codex"
    codex_path.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$$\" >> {shlex.quote(str(codex_pids))}\n"
        "sleep 30\n",
        encoding="utf-8",
    )
    codex_path.chmod(codex_path.stat().st_mode | stat.S_IXUSR)
    launcher_path = tmp_path / "launcher.py"
    launcher_path.write_text("import time\n\ntime.sleep(30)\n", encoding="utf-8")

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["CLOUD_WATCHDOG_MARKER_DIR"] = str(marker_dir)
    env["CLOUD_WATCHDOG_REPAIR_ROOT"] = str(repair_root)
    env["CLOUD_WATCHDOG_REPAIR_DATA_DIR"] = str(marker_dir / "repair-data")
    env["CLOUD_WATCHDOG_HERMES_LAUNCHER"] = str(launcher_path)

    args = ["bash", str(WRAPPER_DIR / "arnold-repair-loop"), "demo-session", str(workspace), "/tmp/spec.json"]
    pidfile = marker_dir / "demo-session.repair-loop.pid"
    first = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    second: subprocess.Popen[str] | None = None
    try:
        for _ in range(300):
            if pidfile.exists() and pidfile.read_text(encoding="utf-8").strip() == str(first.pid):
                break
            time.sleep(0.05)
        assert pidfile.read_text(encoding="utf-8").strip() == str(first.pid)

        first.kill()
        first.wait(timeout=15)
        assert pidfile.exists(), "kill -9 should leave a stale pidfile for recovery"

        second = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        for _ in range(300):
            if pidfile.exists() and pidfile.read_text(encoding="utf-8").strip() == str(second.pid):
                break
            time.sleep(0.05)
        assert pidfile.read_text(encoding="utf-8").strip() == str(second.pid)
    finally:
        if second is not None and second.poll() is None:
            second.terminate()
            second.communicate(timeout=15)
        if first.poll() is None:
            first.terminate()
            first.wait(timeout=15)
        if codex_pids.exists():
            for raw_pid in codex_pids.read_text(encoding="utf-8").splitlines():
                if raw_pid.strip().isdigit():
                    subprocess.run(["kill", "-9", raw_pid.strip()], check=False)


def test_repair_loop_busy_directory_lock_exits_without_mutating_repair_data(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_root = tmp_path / "repair-root"
    workspace = tmp_path / "ws"
    marker_dir.mkdir()
    repair_root.mkdir()
    workspace.mkdir()

    (marker_dir / "demo-session.json").write_text(
        json.dumps({"run_kind": "plan", "plan_name": "demo-plan", "relaunch_command": "true"}),
        encoding="utf-8",
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "demo-plan",
        {
            "name": "demo-plan",
            "current_state": "blocked",
            "iteration": 1,
            "latest_failure": {
                "kind": "phase_failed",
                "message": "boom",
                "recorded_at": "2026-06-29T00:00:00Z",
                "metadata": {"exit_code": 1},
            },
        },
    )

    holder = subprocess.Popen(["sleep", "30"])
    lock_dir = marker_dir / "demo-session.repair-loop.lock"
    try:
        acquired = repair_lock.acquire_repair_lock(
            lock_dir,
            session="demo-session",
            pid=holder.pid,
            command="sleep 30",
            cwd=str(workspace),
        )
        assert acquired.acquired

        env = dict(os.environ)
        env["CLOUD_WATCHDOG_ARNOLD_SRC"] = str(REPO_ROOT)
        env["CLOUD_WATCHDOG_MARKER_DIR"] = str(marker_dir)
        env["CLOUD_WATCHDOG_REPAIR_ROOT"] = str(repair_root)
        env["CLOUD_WATCHDOG_REPAIR_DATA_DIR"] = str(marker_dir / "repair-data")

        result = subprocess.run(
            ["bash", str(WRAPPER_DIR / "arnold-repair-loop"), "demo-session", str(workspace), "/tmp/spec.json"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    finally:
        holder.terminate()
        holder.wait(timeout=15)
        repair_lock.release_repair_lock(lock_dir, expected_pid=holder.pid)

    assert result.returncode == 75
    assert "another repair loop is already active" in f"{result.stdout}\n{result.stderr}"
    assert not (marker_dir / "repair-data" / "demo-session.repair-data.json").exists()
    assert not (marker_dir / "demo-session.repair-loop.pid").exists()


def test_watchdog_complete_teardown_collects_setsid_descendant_pgids(tmp_path: Path) -> None:
    ps_path = tmp_path / "ps"
    ps_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        "100 1 100\n"
        "101 100 100\n"
        "102 101 102\n"
        "103 102 102\n"
        "EOF\n",
        encoding="utf-8",
    )
    ps_path.chmod(ps_path.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("repair_tree_pgids"),
            """
PATH=%s:$PATH
repair_tree_pgids 100 100
""".strip() % str(tmp_path),
        ]
    )
    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().split() == ["100", "102"]


def test_watchdog_treats_supervisor_retry_before_process_liveness_as_unhealthy() -> None:
    text = _extract_wrapper_function("session_health_status")

    pane_check = "tmux capture-pane"
    retry_check = "retrying_failure"
    process_check = 'if chain_process_is_alive "$remote_spec"; then'

    assert text.index(pane_check) < text.index(process_check)
    assert text.index(retry_check) < text.index(process_check)
    assert '"error": "invalid_spec"' in text


def test_watchdog_skips_relaunch_while_review_pr_is_still_open() -> None:
    text = _wrapper("arnold-watchdog")

    assert "chain_wait_status()" in text
    assert 'wait_status="$(chain_wait_status "$workspace" "$remote_spec")"' in text
    assert 'if [[ "$health" == "awaiting_pr_merge" ]]; then' in text
    assert "reconcile_awaiting_pr_merge" in text
    assert 'report_item "$report_items" "$session" "observe" "awaiting_pr_merge" "session waiting on PR merge: ${pr_reconcile_message:-$pr_reconcile_status}"' in text
    assert '["gh", "pr", "view", str(pr_number), "--json", "state"]' in text
    assert '["gh", "pr", "merge", str(pr_number), *flags]' in text


def test_watchdog_stopped_tmux_reports_awaiting_pr_merge_from_chain_state(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("merge_policy: review\n", encoding="utf-8")
    (chain_dir / "demo-chain.json").write_text(
        json.dumps({"last_state": "awaiting_pr_merge"}),
        encoding="utf-8",
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("chain_wait_status"),
            _extract_wrapper_function("session_health_status"),
            """
matching_runner_process_alive() { return 1; }
tmux() {
  if [[ "$1" == "has-session" ]]; then
    return 1
  fi
  return 0
}
""".strip(),
            f"session_health_status demo-session {str(workspace)!r} {str(spec_path)!r} chain ''",
        ]
    )
    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "awaiting_pr_merge"


def test_watchdog_stopped_tmux_prefers_live_chain_process_over_wait_state(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("merge_policy: review\n", encoding="utf-8")
    (chain_dir / "demo-chain.json").write_text(
        json.dumps({"last_state": "awaiting_human_verify"}),
        encoding="utf-8",
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("chain_wait_status"),
            _extract_wrapper_function("session_health_status"),
            f"""
matching_runner_process_alive() {{ return 0; }}
tmux() {{
  if [[ "$1" == "has-session" ]]; then
    return 1
  fi
  return 0
}}
ps() {{
  printf '%s\\n' 'python3 -P -m arnold_pipelines.megaplan chain start --spec {str(spec_path)} --project-dir {str(workspace)}'
}}
""".strip(),
            f"session_health_status demo-session {str(workspace)!r} {str(spec_path)!r} chain ''",
        ]
    )
    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "alive"


def test_watchdog_terminal_status_accepts_label_only_completed_chain(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    spec_path = workspace / ".megaplan" / "briefs" / "python-shaped-workflow-authoring" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(
        "\n".join(
            [
                "merge_policy: review",
                "milestones:",
                "  - label: m1",
                "  - label: m2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_chain_state(
        chain_dir / "chain-demo.json",
        {
            "last_state": "done",
            "current_milestone_index": 2,
            "current_plan_name": "",
            "completed": [{"label": "m1"}, {"label": "m2"}],
            "pr_number": 128,
            "pr_state": "merged",
        },
    )
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()

    script = "\n\n".join(
        [
            _extract_wrapper_function("session_terminal_status"),
            f"MARKER_DIR={str(tmp_path / 'markers')!r}",
            f"REPAIR_DATA_DIR={str(repair_dir)!r}",
            f"session_terminal_status demo-session {str(workspace)!r} {str(spec_path)!r} chain",
        ]
    )
    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "complete\tchain complete"


def test_watchdog_terminal_status_reads_spec_local_chain_state(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    spec_path = workspace / ".megaplan" / "briefs" / "god-file-splits" / "chain.yaml"
    chain_dir = spec_path.parent / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    spec_path.write_text(
        "\n".join(
            [
                "milestones:",
                "  - label: split-comfy-nodes-agent-edit",
                "  - label: split-porting-emitter-py-god",
                "  - label: split-porting-edit-apply-py",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_chain_state(
        chain_dir / "chain-demo.json",
        {
            "last_state": "done",
            "current_milestone_index": 3,
            "current_plan_name": "",
            "completed": [
                {"label": "split-comfy-nodes-agent-edit"},
                {"label": "split-porting-emitter-py-god"},
                {"label": "split-porting-edit-apply-py"},
            ],
            "events": [{"msg": "all milestones complete"}],
        },
    )
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()

    script = "\n\n".join(
        [
            _extract_wrapper_function("session_terminal_status"),
            f"MARKER_DIR={str(tmp_path / 'markers')!r}",
            f"REPAIR_DATA_DIR={str(repair_dir)!r}",
            f"session_terminal_status demo-session {str(workspace)!r} {str(spec_path)!r} chain",
        ]
    )
    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "complete\tchain complete"


def test_watchdog_auto_merge_policy_attempts_pr_merge_before_waiting(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("merge_policy: auto\n", encoding="utf-8")
    (chain_dir / "demo-chain.json").write_text(
        json.dumps({"last_state": "awaiting_pr_merge", "pr_number": 42}),
        encoding="utf-8",
    )

    gh_log = tmp_path / "gh.log"
    merged_flag = tmp_path / "merged"
    gh_path = tmp_path / "gh"
    gh_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"printf '%s\\n' \"$*\" >> {str(gh_log)!r}",
                "if [[ \"$1 $2 $3\" == \"pr view 42\" ]]; then",
                f"  if [[ -f {str(merged_flag)!r} ]]; then",
                "    printf '%s\\n' '{\"state\":\"MERGED\"}'",
                "  else",
                "    printf '%s\\n' '{\"state\":\"OPEN\"}'",
                "  fi",
                "  exit 0",
                "fi",
                "if [[ \"$1 $2 $3\" == \"pr ready 42\" ]]; then",
                "  exit 0",
                "fi",
                "if [[ \"$1 $2 $3\" == \"pr merge 42\" ]]; then",
                f"  touch {str(merged_flag)!r}",
                "  exit 0",
                "fi",
                "exit 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("chain_wait_status"),
            f"chain_wait_status {str(workspace)!r} {str(spec_path)!r}",
        ]
    )
    result = _run_watchdog_shell(script, path_prefix=tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "none"
    gh_calls = gh_log.read_text(encoding="utf-8").splitlines()
    assert "pr ready 42" in gh_calls
    assert "pr merge 42 --auto --squash --delete-branch" in gh_calls


def test_watchdog_finalized_plan_never_authorizes_pr_merge(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("merge_policy: auto\n", encoding="utf-8")
    (chain_dir / "demo-chain.json").write_text(
        json.dumps(
            {
                "last_state": "finalized",
                "current_plan_name": "demo-plan",
                "pr_number": 42,
            }
        ),
        encoding="utf-8",
    )
    gh_log = tmp_path / "gh.log"
    gh_path = tmp_path / "gh"
    gh_path.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$*\" >> {str(gh_log)!r}\n"
        "exit 1\n",
        encoding="utf-8",
    )
    gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("chain_wait_status"),
            f"chain_wait_status {str(workspace)!r} {str(spec_path)!r}",
        ]
    )
    result = _run_watchdog_shell(script, path_prefix=tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "none"
    assert not gh_log.exists()


def test_watchdog_auto_policy_merged_pr_fetches_origin_before_relaunch(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    marker_dir = tmp_path / "markers"
    repair_dir = tmp_path / "repair-data"
    marker_dir.mkdir()
    repair_dir.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("merge_policy: auto\n", encoding="utf-8")
    chain_path = workspace / ".megaplan" / "plans" / ".chains" / "demo-chain.json"
    _write_chain_state(
        chain_path,
        {"last_state": "awaiting_pr_merge", "pr_number": 42, "pr_state": "open"},
    )
    report_path = tmp_path / "report.tsv"
    call_log = tmp_path / "calls.log"
    gh_path = tmp_path / "gh"
    gh_path.write_text(
        "#!/usr/bin/env bash\n"
        f"printf 'gh %s\\n' \"$*\" >> {str(call_log)!r}\n"
        "if [[ \"$1 $2 $3\" == \"pr view 42\" ]]; then\n"
        "  printf '%s\\n' '{\"state\":\"MERGED\",\"mergeCommit\":{\"oid\":\"abc123\"}}'\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)
    git_path = tmp_path / "git"
    git_path.write_text(
        "#!/usr/bin/env bash\n"
        f"printf 'git %s\\n' \"$*\" >> {str(call_log)!r}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    git_path.chmod(git_path.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("json_field"),
            _extract_wrapper_function("safe_name"),
            _extract_wrapper_function("reconcile_awaiting_pr_merge"),
            _extract_wrapper_function("launch_chain_tick"),
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_dir)!r}",
            """
log() { printf '%s\n' "$*" >> "$CALL_LOG"; }
report_item() { printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"; }
session_health_status() { echo awaiting_pr_merge; }
chain_health_status() { CHAIN_HEALTH_STATUS=ok; }
plan_terminal_status() { echo none; }
plan_attention_status_env() { :; }
repair_needs_human_path() { printf '%s/%s.needs-human.json\n' "$REPAIR_DATA_DIR" "$1"; }
workspace_has_other_alive_session() { return 1; }
repair_loop_busy_state() { echo none; }
mechanical_relaunch_attempted_previously() { return 1; }
kimi_dispatch_failed_previously() { return 1; }
kimi_dispatch_marker_set() { :; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
tmux() { printf 'tmux %s\n' "$*" >> "$CALL_LOG"; return 0; }
mktemp() { printf '%s\n' "$LAUNCH_SCRIPT"; }
chmod() { :; }
""".strip(),
            f"CALL_LOG={str(call_log)!r}",
            f"LAUNCH_SCRIPT={str(tmp_path / 'launch.sh')!r}",
            f"launch_chain_tick demo-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script, path_prefix=tmp_path)
    assert result.returncode == 0, result.stderr
    calls = call_log.read_text(encoding="utf-8")
    assert "gh pr view 42 --json state,mergeCommit" in calls
    assert "git fetch origin --prune" in calls
    assert "git cat-file -e abc123^{commit}" in calls
    assert "session awaiting PR merge reconciled merged; falling through to relaunch" in calls
    assert "tmux new-session -d -s demo-session" in calls


def test_watchdog_auto_policy_open_pr_queues_evidence_and_preserves_wait(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARNOLD_REPAIR_REQUEST_QUEUE", "1")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    marker_dir = tmp_path / "markers"
    repair_dir = tmp_path / "repair-data"
    marker_dir.mkdir()
    repair_dir.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("merge_policy: auto\n", encoding="utf-8")
    chain_path = workspace / ".megaplan" / "plans" / ".chains" / "demo-chain.json"
    _write_chain_state(
        chain_path,
        {"last_state": "awaiting_pr_merge", "pr_number": 43, "pr_state": "open"},
    )
    report_path = tmp_path / "report.tsv"
    call_log = tmp_path / "calls.log"
    gh_path = tmp_path / "gh"
    gh_path.write_text(
        "#!/usr/bin/env bash\n"
        f"printf 'gh %s\\n' \"$*\" >> {str(call_log)!r}\n"
        "if [[ \"$1 $2 $3\" == \"pr view 43\" ]]; then\n"
        "  printf '%s\\n' '{\"state\":\"OPEN\"}'\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("reconcile_awaiting_pr_merge"),
            _extract_wrapper_function("launch_chain_tick"),
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_dir)!r}",
            """
log() { printf '%s\n' "$*" >> "$CALL_LOG"; }
report_item() { printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"; }
session_health_status() { echo awaiting_pr_merge; }
chain_health_status() { CHAIN_HEALTH_STATUS=ok; }
repair_needs_human_path() { printf '%s/%s.needs-human.json\n' "$REPAIR_DATA_DIR" "$1"; }
tmux() { printf 'TMUX %s\n' "$*" >> "$CALL_LOG"; return 0; }
""".strip(),
            f"CALL_LOG={str(call_log)!r}",
            f"launch_chain_tick demo-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script, path_prefix=tmp_path)
    assert result.returncode == 0, result.stderr
    calls = call_log.read_text(encoding="utf-8")
    assert "gh pr view 43 --json state,mergeCommit" in calls
    assert "session awaiting PR merge: demo-session detail=PR #43 state=open evidence=queued" in calls
    assert "TMUX" not in calls
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tawaiting_pr_merge\tsession waiting on PR merge: PR #43 state=open evidence=queued\t" in report
    queued = list((tmp_path / ".megaplan" / "repair-queue" / "requests").glob("*.json"))
    assert len(queued) == 1
    payload = json.loads(queued[0].read_text(encoding="utf-8"))
    assert payload["source"] == "watchdog_pr_merge_reconciliation"
    assert payload["target"]["pr_number"] == 43


def test_watchdog_queue_writers_use_explicit_central_queue_root() -> None:
    text = _wrapper("arnold-watchdog")

    assert text.count("queue_root=repair_queue_dir(marker_dir)") >= 2


def test_watchdog_relaunch_runs_editable_install_code_against_active_workspace() -> None:
    text = _wrapper("arnold-watchdog")

    assert "if [[ -f /workspace/.cloud-hot-env ]]; then set -a; . /workspace/.cloud-hot-env; set +a; fi;" in text
    assert "resolve_relaunch_command()" in text
    assert "default_plan_relaunch_command()" in text
    assert "python3 -P -m arnold_pipelines.megaplan chain start" in text
    assert "python3 -P -m arnold_pipelines.megaplan auto --plan" in text
    assert '"$session" "$workspace" "$remote_spec" "$run_kind" "$plan_name" "$relaunch_command"' in text
    assert "--project-dir %q --one" not in text
    assert 'tmux kill-session -t "$session"' in text
    assert 'sleep 0.2' in text
    assert "relaunch raced with existing tmux session" in text
    assert "session exists after relaunch race" in text
    assert "export ARNOLD_SUPERVISE_SESSION=" in text
    assert "export ARNOLD_SUPERVISE_WORKSPACE=" in text
    assert "export ARNOLD_SUPERVISE_REMOTE_SPEC=" in text
    assert "export ARNOLD_SUPERVISE_RUN_KIND=" in text
    assert "printf -v quoted_command_shell '%q' \"$quoted_command\"" in text
    assert 'bash -lc $quoted_command_shell' in text
    assert 'bash -lc "$quoted_command"' not in text


def test_watchdog_relaunch_requires_substantive_health_before_reporting_restart() -> None:
    text = _wrapper("arnold-watchdog")

    assert "verify_relaunch_health()" in text
    assert 'verified_health="$(verify_relaunch_health ' in text
    assert '"restart_failed" "tmux relaunch did not produce a healthy runner' in text
    assert 'dispatch_kimi_repair "$session" "$workspace" "$remote_spec"' in text


def test_verify_relaunch_health_rejects_tmux_only_false_success() -> None:
    script = "\n\n".join(
        [
            _extract_wrapper_function("verify_relaunch_health"),
            """
checks=0
session_health_status() {
  checks=$((checks + 1))
  printf '%s\n' stopped
}
sleep() { :; }
verify_relaunch_health demo /workspace/demo /workspace/demo/chain.yaml chain '' 2
""".strip(),
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 1
    assert result.stdout.strip() == "stopped"


def test_verify_relaunch_health_fails_fast_on_launch_log_failure() -> None:
    script = "\n\n".join(
        [
            _extract_wrapper_function("verify_relaunch_health"),
            """
session_health_status() { printf '%s\n' chain_log_failure; }
sleep() { printf '%s\n' unexpected-sleep >&2; }
verify_relaunch_health demo /workspace/demo /workspace/demo/chain.yaml chain '' 15
""".strip(),
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 1
    assert result.stdout.strip() == "chain_log_failure"
    assert "unexpected-sleep" not in result.stderr


def test_supervise_exhaustion_queues_repair_request() -> None:
    text = _wrapper("arnold-supervise")
    helper = (REPO_ROOT / "arnold_pipelines/megaplan/cloud/supervise.py").read_text(
        encoding="utf-8"
    )

    assert "queue_repair_request()" in text
    assert "enqueue_supervisor_repair_request" in text
    assert 'source="arnold_supervise_exit"' in helper
    assert '"failure_kind": "supervised_run_exhausted"' in helper
    assert "non-quota retries exhausted" in text
    assert "exit_with_repair_request" in text
    assert "SUPERVISE_SESSION" in text
    assert "SUPERVISE_WORKSPACE" in text
    assert "SUPERVISE_REMOTE_SPEC" in text


def test_supervise_deterministic_binding_failure_does_not_retry(tmp_path: Path) -> None:
    command = tmp_path / "binding-drift"
    command.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' '{\"success\":false,\"error\":\"chain_execution_binding_drift\"}'\n"
        "exit 1\n",
        encoding="utf-8",
    )
    command.chmod(command.stat().st_mode | stat.S_IXUSR)
    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}",
            "ARNOLD_AUTONOMY": "1",
            "ARNOLD_REPAIR_TRIGGER_ENABLED": "1",
            "ARNOLD_SUPERVISE_LOG": str(tmp_path / "supervise.log"),
        }
    )

    result = subprocess.run(
        ["bash", str(WRAPPER_DIR / "arnold-supervise"), "binding", str(command)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=10,
    )

    assert result.returncode == 1
    assert "refusing retry spin" in result.stdout
    assert "error retry" not in result.stdout


def test_supervise_durable_review_quality_block_does_not_retry(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    plan_dir = workspace / ".megaplan" / "plans" / "review-plan"
    chain_dir.mkdir(parents=True)
    plan_dir.mkdir(parents=True)
    (chain_dir / "chain-demo.json").write_text(
        json.dumps({"current_plan_name": "review-plan", "last_state": "blocked"}),
        encoding="utf-8",
    )
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "current_state": "blocked",
                "latest_failure": {
                    "kind": "review_quality_blocked_unknown",
                    "message": "review rework budget exhausted with unresolved quality blockers",
                },
            }
        ),
        encoding="utf-8",
    )
    command = tmp_path / "blocked-review"
    command.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    command.chmod(command.stat().st_mode | stat.S_IXUSR)
    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}",
            "ARNOLD_AUTONOMY": "1",
            "ARNOLD_REPAIR_TRIGGER_ENABLED": "1",
            "ARNOLD_SUPERVISE_LOG": str(tmp_path / "supervise.log"),
            "ARNOLD_SUPERVISE_SESSION": "demo",
            "ARNOLD_SUPERVISE_WORKSPACE": str(workspace),
            "ARNOLD_SUPERVISE_REMOTE_SPEC": str(workspace / "chain.yaml"),
            "ARNOLD_SUPERVISE_RUN_KIND": "chain",
            "ARNOLD_REPAIR_QUEUE_ROOT": str(tmp_path / "repair-queue"),
            "CLOUD_WATCHDOG_MARKER_DIR": str(tmp_path / "markers"),
        }
    )

    result = subprocess.run(
        ["bash", str(WRAPPER_DIR / "arnold-supervise"), "quality", str(command)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=10,
    )

    assert result.returncode == 1
    assert "durable_review_quality_block:review_quality_blocked_unknown" in result.stdout
    assert "refusing retry spin" in result.stdout
    assert "error retry" not in result.stdout


def test_watchdog_adopts_markerless_bootstrap_tmux_run(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace_root = tmp_path / "workspace-root"
    workspace = workspace_root / "test-watchdog-vibecomfy-per-workflow-window-chat-20260628"
    (workspace / ".megaplan" / "plans" / "per-workflow-window-chat-cloud-20260628").mkdir(parents=True, exist_ok=True)

    tmux_path = tmp_path / "tmux"
    tmux_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        f"vibecomfy-per-workflow-window-chat\t4000\t{workspace}\t"
        "cd "
        f"{workspace}"
        " && MEGAPLAN_TRUSTED_CONTAINER=1 python3 -m arnold_pipelines.megaplan init "
        "--project-dir . --idea-file .megaplan/initiatives/per-workflow-window-chat/briefs/per-workflow-window-chat.md "
        "--name per-workflow-window-chat-cloud-20260628 --auto-start\n"
        "EOF\n",
        encoding="utf-8",
    )
    tmux_path.chmod(tmux_path.stat().st_mode | stat.S_IXUSR)

    ps_path = tmp_path / "ps"
    ps_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        "4000 1 bash -lc bootstrap\n"
        "4001 4000 /root/.pyenv/versions/3.11.11/bin/python3 -m arnold_pipelines.megaplan init "
        "--project-dir . --idea-file .megaplan/initiatives/per-workflow-window-chat/briefs/per-workflow-window-chat.md "
        "--name per-workflow-window-chat-cloud-20260628 --auto-start\n"
        "4002 4001 /root/.pyenv/versions/3.11.11/bin/python3 -m arnold_pipelines.megaplan critique "
        "--plan per-workflow-window-chat-cloud-20260628\n"
        "EOF\n",
        encoding="utf-8",
    )
    ps_path.chmod(ps_path.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("adopt_unmarked_tmux_sessions"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"DISCOVER_BIN={str(WRAPPER_DIR / 'arnold-cloud-discover')!r}",
            f"export MEGAPLAN_DISCOVER_WORKSPACE_ROOT={str(workspace_root)!r}",
            "adopt_unmarked_tmux_sessions",
        ]
    )
    result = _run_watchdog_shell(script, path_prefix=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "vibecomfy-per-workflow-window-chat" in result.stdout

    marker_path = marker_dir / "vibecomfy-per-workflow-window-chat.json"
    payload = json.loads(marker_path.read_text(encoding="utf-8"))
    assert payload["session"] == "vibecomfy-per-workflow-window-chat"
    assert payload["workspace"] == str(workspace)
    assert payload["run_kind"] == "plan"
    assert payload["plan_name"] == "per-workflow-window-chat-cloud-20260628"
    assert payload["remote_spec"] == ".megaplan/initiatives/per-workflow-window-chat/briefs/per-workflow-window-chat.md"
    assert "python3 -P -m arnold_pipelines.megaplan auto --plan per-workflow-window-chat-cloud-20260628" in payload["relaunch_command"]


def test_watchdog_does_not_adopt_non_arnold_tmux_sessions(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace_root = tmp_path / "workspace-root"
    workspace = workspace_root / "test-watchdog-random-workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    tmux_path = tmp_path / "tmux"
    tmux_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        f"scratch\t5000\t{workspace}\tbash -lc 'python3 -m http.server 8080'\n"
        "EOF\n",
        encoding="utf-8",
    )
    tmux_path.chmod(tmux_path.stat().st_mode | stat.S_IXUSR)

    ps_path = tmp_path / "ps"
    ps_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        "5000 1 bash -lc python3 -m http.server 8080\n"
        "5001 5000 python3 -m http.server 8080\n"
        "EOF\n",
        encoding="utf-8",
    )
    ps_path.chmod(ps_path.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("adopt_unmarked_tmux_sessions"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"DISCOVER_BIN={str(WRAPPER_DIR / 'arnold-cloud-discover')!r}",
            f"export MEGAPLAN_DISCOVER_WORKSPACE_ROOT={str(workspace_root)!r}",
            "adopt_unmarked_tmux_sessions",
        ]
    )
    result = _run_watchdog_shell(script, path_prefix=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""
    assert not marker_dir.exists()


def test_shared_cloud_discover_finds_markerless_arnold_tmux_session_and_skips_supervisors(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    workspace_root = tmp_path / "workspace-root"
    workspace = workspace_root / "test-shared-discover-vibecomfy"
    (workspace / ".megaplan" / "plans" / "shared-discover-plan").mkdir(parents=True, exist_ok=True)

    tmux_path = tmp_path / "tmux"
    tmux_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        f"vibecomfy-shared-discover\t4000\t{workspace}\t"
        "cd "
        f"{workspace}"
        " && python3 -m arnold_pipelines.megaplan init --project-dir . "
        "--idea-file .megaplan/initiatives/shared/briefs/shared.md --name shared-discover-plan --auto-start\n"
        f"watchdog-demo\t5000\t{workspace}\tbash -lc '/usr/local/bin/arnold-watchdog --once'\n"
        f"kimi-helper\t6000\t{workspace}\tbash -lc '/usr/local/bin/arnold-kimi-goal-operator demo'\n"
        "EOF\n",
        encoding="utf-8",
    )
    tmux_path.chmod(tmux_path.stat().st_mode | stat.S_IXUSR)

    ps_path = tmp_path / "ps"
    ps_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        "4000 1 bash -lc bootstrap\n"
        "4001 4000 python3 -m arnold_pipelines.megaplan init --project-dir . "
        "--idea-file .megaplan/initiatives/shared/briefs/shared.md --name shared-discover-plan --auto-start\n"
        "5000 1 bash -lc /usr/local/bin/arnold-watchdog --once\n"
        "6000 1 bash -lc /usr/local/bin/arnold-kimi-goal-operator demo\n"
        "EOF\n",
        encoding="utf-8",
    )
    ps_path.chmod(ps_path.stat().st_mode | stat.S_IXUSR)

    result = _run_discover(tmp_path, marker_dir=marker_dir)
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.strip().splitlines() if line]
    assert len(lines) == 1
    fields = lines[0].split("\t")
    assert fields[0] == "vibecomfy-shared-discover"
    assert fields[1] == str(workspace)
    assert fields[2] == ".megaplan/initiatives/shared/briefs/shared.md"
    assert fields[3] == "plan"
    assert fields[4] == "shared-discover-plan"
    assert "python3 -P -m arnold_pipelines.megaplan auto --plan shared-discover-plan" in fields[5]


def test_watchdog_plan_markers_relaunch_with_auto_not_chain_start(tmp_path: Path) -> None:
    script = "\n\n".join(
        [
            *_extract_relaunch_functions("watchdog"),
            f"SRC_DIR={str(REPO_ROOT)!r}",
            "SYNC_BRANCH=editible-install",
            "resolve_relaunch_command demo-session /tmp/workspace /tmp/not-a-chain.yaml plan demo-plan ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert "python3 -P -m arnold_pipelines.megaplan auto --plan demo-plan" in result.stdout
    assert "chain start" not in result.stdout


def test_watchdog_stale_marker_relaunch_command_regenerates_clean_runtime_chain_command() -> None:
    stale_command = (
        "{ set -e\n"
        "if [ -n \"$(git -C \"$SRC\" status --porcelain --untracked-files=no)\" ]; then\n"
        "  echo \"[megaplan-refresh] refusing editable install refresh: tracked changes in source checkout at $SRC\"\n"
        "  exit 19\n"
        "fi\n"
        "} >> .megaplan/cloud-chain-progress-auditor-stage-metrics.log 2>&1 && "
        "cd /workspace/progress-auditor-stage-metrics/Arnold && "
        "PYTHONPATH=/workspace/arnold:${PYTHONPATH:-} python -P -m arnold_pipelines.megaplan chain start"
    )
    script = "\n\n".join(
        [
            *_extract_relaunch_functions("watchdog"),
            f"SRC_DIR={str(REPO_ROOT)!r}",
            "SYNC_BRANCH=editible-install",
            (
                "resolve_relaunch_command progress-auditor-stage-metrics "
                "/workspace/progress-auditor-stage-metrics/Arnold "
                "/workspace/progress-auditor-stage-metrics/Arnold/.megaplan/initiatives/progress-auditor-stage-metrics/chain.yaml "
                f"chain '' {shlex.quote(stale_command)}"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert "source checkout dirty; using current source checkout at $SRC to avoid stale runtime mirror" in result.stdout
    assert "MEGAPLAN_RUNTIME_SRC" in result.stdout
    assert "/workspace/progress-auditor-stage-metrics/Arnold/.megaplan/runtime/editable-engine" in result.stdout
    assert "python3 -P -m arnold_pipelines.megaplan chain start" in result.stdout
    assert "refusing editable install refresh: tracked changes in source checkout" not in result.stdout


def test_watchdog_nonstale_marker_relaunch_command_is_preserved() -> None:
    script = "\n\n".join(
        [
            *_extract_relaunch_functions("watchdog"),
            f"SRC_DIR={str(REPO_ROOT)!r}",
            "SYNC_BRANCH=editible-install",
            "resolve_relaunch_command demo-session /tmp/workspace /tmp/chain.yaml chain '' 'echo marker-command'",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "echo marker-command"


@pytest.mark.parametrize("wrapper_kind", ["watchdog", "repair"])
def test_chain_resume_authority_outranks_marker_command_and_discovers_plan(
    tmp_path: Path,
    wrapper_kind: str,
) -> None:
    workspace = tmp_path / "workspace"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    plan_name = "resume-required-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "current_state": "blocked",
                "resume_cursor": {
                    "phase": "plan",
                    "retry_strategy": "check_provider_and_retry",
                },
                "latest_failure": {
                    "kind": "external_error_resume_required",
                    "phase": "recover-blocked",
                },
            }
        ),
        encoding="utf-8",
    )
    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    (chain_dir / f"chain-{digest}.json").write_text(
        json.dumps({"current_plan_name": plan_name, "last_state": "blocked"}),
        encoding="utf-8",
    )

    source_var = "SRC_DIR" if wrapper_kind == "watchdog" else "ARNOLD_SRC"
    script = "\n\n".join(
        [
            *_extract_relaunch_functions(wrapper_kind),
            f"{source_var}={str(REPO_ROOT)!r}",
            "SYNC_BRANCH=editible-install",
            (
                f"resolve_relaunch_command demo-session {str(workspace)!r} "
                f"{str(spec_path)!r} chain '' 'echo marker-chain-start'"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert f"megaplan resume --plan {plan_name}" in result.stdout
    assert "marker-chain-start" not in result.stdout


def test_repair_loop_stale_marker_relaunch_command_regenerates_clean_runtime_chain_command() -> None:
    stale_command = (
        "{ set -e\n"
        "if [ -n \"$(git -C \"$SRC\" status --porcelain --untracked-files=no)\" ]; then\n"
        "  echo \"[megaplan-refresh] refusing editable install refresh: tracked changes in source checkout at $SRC\"\n"
        "  exit 19\n"
        "fi\n"
        "} >> .megaplan/cloud-chain-progress-auditor-stage-metrics.log 2>&1 && "
        "cd /workspace/progress-auditor-stage-metrics/Arnold && "
        "PYTHONPATH=/workspace/arnold:${PYTHONPATH:-} python -P -m arnold_pipelines.megaplan chain start"
    )
    script = "\n\n".join(
        [
            *_extract_relaunch_functions("repair"),
            f"ARNOLD_SRC={str(REPO_ROOT)!r}",
            "SYNC_BRANCH=editible-install",
            (
                "resolve_relaunch_command progress-auditor-stage-metrics "
                "/workspace/progress-auditor-stage-metrics/Arnold "
                "/workspace/progress-auditor-stage-metrics/Arnold/.megaplan/initiatives/progress-auditor-stage-metrics/chain.yaml "
                f"chain '' {shlex.quote(stale_command)}"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert "source checkout dirty; using current source checkout at $SRC to avoid stale runtime mirror" in result.stdout
    assert "MEGAPLAN_RUNTIME_SRC" in result.stdout
    assert "/workspace/progress-auditor-stage-metrics/Arnold/.megaplan/runtime/editable-engine" in result.stdout
    assert "python3 -P -m arnold_pipelines.megaplan chain start" in result.stdout
    assert "refusing editable install refresh: tracked changes in source checkout" not in result.stdout


@pytest.mark.parametrize("wrapper_kind", ["watchdog", "repair"])
def test_persisted_push_capable_marker_command_is_always_regenerated(
    wrapper_kind: str,
) -> None:
    stale_command = (
        "echo '[megaplan-refresh] refusing editable install refresh:'; "
        "echo 'source checkout dirty; using clean runtime mirror'; "
        "echo 'source checkout has local commits not contained in origin/$REF; attempting push'; "
        "git -C \"$SRC\" push origin \"$REF\"; "
        "git -C \"$MEGAPLAN_RUNTIME_SRC\" merge-base --is-ancestor HEAD \"origin/$REF\""
    )
    extract = _extract_wrapper_function if wrapper_kind == "watchdog" else _extract_repair_function
    source_var = "SRC_DIR" if wrapper_kind == "watchdog" else "ARNOLD_SRC"
    script = "\n\n".join(
        [
            extract("default_plan_relaunch_command"),
            extract("resume_plan_relaunch_command"),
            extract("chain_resume_plan_relaunch_command_if_needed"),
            extract("stale_marker_relaunch_command"),
            extract("default_chain_relaunch_command"),
            extract("resolve_relaunch_command"),
            f"{source_var}={str(REPO_ROOT)!r}",
            "SYNC_BRANCH=editible-install",
            (
                "resolve_relaunch_command demo-session /tmp/workspace /tmp/chain.yaml "
                f"chain '' {shlex.quote(stale_command)}"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert "python3 -P -m arnold_pipelines.megaplan chain start" in result.stdout
    assert "using current source checkout at $SRC" in result.stdout
    assert "attempting push" not in result.stdout
    assert 'git -C "$SRC" push origin' not in result.stdout


def _post_dev_quality_recovery_fixture(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    from arnold_pipelines.megaplan.orchestration.phase_result import Deviation, PhaseResult

    workspace = tmp_path / "workspace"
    plan_name = "quality-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "current_state": "blocked",
                "active_step": None,
                "resume_cursor": {"phase": "review", "retry_strategy": "manual_review"},
                "latest_failure": {
                    "kind": "review_quality_blocked_unknown",
                    "phase": "review",
                },
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "phase_result.json").write_text(
        json.dumps(
            PhaseResult(
                phase="review",
                invocation_id="review-invocation",
                exit_kind="blocked_by_quality",
                deviations=(
                    Deviation(
                        kind="quality_gate",
                        message="review found a deterministic acceptance defect",
                    ),
                ),
            ).to_dict()
        ),
        encoding="utf-8",
    )
    (plan_dir / "review.json").write_text(
        json.dumps(
            {
                "review_verdict": "needs_rework",
                "rework_items": [{"evidence_file": "module.py"}],
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(workspace), "add", "."], check=True)
    subprocess.run(["git", "-C", str(workspace), "commit", "-qm", "quality repair"], check=True)
    head = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    report_path = tmp_path / "dev-report.json"
    safe_target = {"kind": "target_workspace", "scope": "module.py"}
    dev_report = {
        "local_commit": head,
        "safe_repair_target": safe_target,
        "validation": {"focused": "passed"},
    }
    report_path.write_text(json.dumps(dev_report), encoding="utf-8")
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps(
            {
                "iterations": [
                    {
                        "i": 1,
                        "dev_turn_rc": 0,
                        "dev_report_path": str(report_path),
                        "dev_before_sha": "a" * 40,
                        "dev_after_sha": head,
                        "dev_fix_sha": head,
                        "dev_fix_changed": True,
                        "dev_report": dev_report,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    receipt_path = tmp_path / "investigator.json"
    receipt_path.write_text(
        json.dumps(
            {
                "recommended_action": "repair_target",
                "safe_repair_target": safe_target,
            }
        ),
        encoding="utf-8",
    )
    return workspace, data_path, receipt_path, plan_name


def test_post_dev_quality_recovery_uses_fixed_resolution_and_supported_cli(
    tmp_path: Path,
) -> None:
    workspace, data_path, receipt_path, plan_name = _post_dev_quality_recovery_fixture(tmp_path)
    script = "\n\n".join(
        [
            _extract_repair_function("post_dev_fix_quality_recovery_command_if_needed"),
            f"WORKSPACE={str(workspace)!r}",
            f"PLAN_NAME={plan_name!r}",
            f"DATA_FILE={str(data_path)!r}",
            f"INVESTIGATOR_RECEIPT_PATH={str(receipt_path)!r}",
            f"ARNOLD_SRC={str(REPO_ROOT)!r}",
            "post_dev_fix_quality_recovery_command_if_needed 1 'echo ordinary-relaunch'",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert "quality-gate resolve" in result.stdout
    assert "quality-gate resolve --project-dir" not in result.stdout
    assert "override recover-blocked --project-dir" in result.stdout
    assert "--resolution fixed" in result.stdout
    assert "override recover-blocked" in result.stdout
    assert "ordinary-relaunch" in result.stdout
    assert "accepted_with_debt" not in result.stdout
    assert "local dev fix commit:" in result.stdout
    assert len(result.stdout.encode("utf-8")) <= 16384


def test_post_dev_quality_recovery_accepts_exact_recover_state_cli(
    tmp_path: Path,
) -> None:
    workspace, data_path, receipt_path, plan_name = _post_dev_quality_recovery_fixture(tmp_path)
    ordinary_relaunch = "echo ordinary-relaunch"
    receipt_path.write_text(
        json.dumps(
            {
                "recommended_action": "recover_state",
                "safe_repair_target": {
                    "kind": "plan_state_via_cli",
                    "scope": "supported chain start",
                },
                "handoff": {
                    "allowed_mutations": [f"supported_cli:{ordinary_relaunch}"]
                },
            }
        ),
        encoding="utf-8",
    )
    script = "\n\n".join(
        [
            _extract_repair_function("post_dev_fix_quality_recovery_command_if_needed"),
            f"WORKSPACE={str(workspace)!r}",
            f"PLAN_NAME={plan_name!r}",
            f"DATA_FILE={str(data_path)!r}",
            f"INVESTIGATOR_RECEIPT_PATH={str(receipt_path)!r}",
            f"ARNOLD_SRC={str(REPO_ROOT)!r}",
            f"post_dev_fix_quality_recovery_command_if_needed 1 {ordinary_relaunch!r}",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert "quality-gate resolve" in result.stdout
    assert "quality-gate resolve --project-dir" not in result.stdout
    assert "override recover-blocked --project-dir" in result.stdout
    assert "--resolution fixed" in result.stdout
    assert "override recover-blocked" in result.stdout
    assert ordinary_relaunch in result.stdout


def test_post_dev_quality_recovery_rejects_recover_state_cli_mismatch(
    tmp_path: Path,
) -> None:
    workspace, data_path, receipt_path, plan_name = _post_dev_quality_recovery_fixture(tmp_path)
    receipt_path.write_text(
        json.dumps(
            {
                "recommended_action": "recover_state",
                "safe_repair_target": {
                    "kind": "plan_state_via_cli",
                    "scope": "supported chain start",
                },
                "handoff": {"allowed_mutations": ["supported_cli:echo stale-command"]},
            }
        ),
        encoding="utf-8",
    )
    script = "\n\n".join(
        [
            _extract_repair_function("post_dev_fix_quality_recovery_command_if_needed"),
            f"WORKSPACE={str(workspace)!r}",
            f"PLAN_NAME={plan_name!r}",
            f"DATA_FILE={str(data_path)!r}",
            f"INVESTIGATOR_RECEIPT_PATH={str(receipt_path)!r}",
            f"ARNOLD_SRC={str(REPO_ROOT)!r}",
            "post_dev_fix_quality_recovery_command_if_needed 1 'echo ordinary-relaunch'",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_post_dev_quality_recovery_rejects_unchanged_or_unbounded_evidence(
    tmp_path: Path,
) -> None:
    workspace, data_path, receipt_path, plan_name = _post_dev_quality_recovery_fixture(tmp_path)
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    payload["iterations"][0]["dev_fix_changed"] = False
    data_path.write_text(json.dumps(payload), encoding="utf-8")
    script = "\n\n".join(
        [
            _extract_repair_function("post_dev_fix_quality_recovery_command_if_needed"),
            f"WORKSPACE={str(workspace)!r}",
            f"PLAN_NAME={plan_name!r}",
            f"DATA_FILE={str(data_path)!r}",
            f"INVESTIGATOR_RECEIPT_PATH={str(receipt_path)!r}",
            f"ARNOLD_SRC={str(REPO_ROOT)!r}",
            "post_dev_fix_quality_recovery_command_if_needed 1 'echo ordinary-relaunch'",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_post_dev_quality_recovery_rejects_unpublished_tracked_branch_fix(
    tmp_path: Path,
) -> None:
    workspace, data_path, receipt_path, plan_name = _post_dev_quality_recovery_fixture(tmp_path)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "-C", str(workspace), "remote", "add", "origin", str(remote)], check=True)
    branch = subprocess.run(
        ["git", "-C", str(workspace), "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(workspace), "push", "-q", "-u", "origin", branch],
        check=True,
    )
    before = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (workspace / "module.py").write_text("fixed = True\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(workspace), "add", "module.py"], check=True)
    subprocess.run(["git", "-C", str(workspace), "commit", "-qm", "local repair"], check=True)
    after = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    entry = payload["iterations"][0]
    entry["dev_before_sha"] = before
    entry["dev_after_sha"] = after
    entry["dev_fix_sha"] = after
    entry["dev_fix_changed"] = True
    entry["dev_report"]["local_commit"] = after
    report_path = Path(entry["dev_report_path"])
    report_path.write_text(json.dumps(entry["dev_report"]), encoding="utf-8")
    data_path.write_text(json.dumps(payload), encoding="utf-8")
    script = "\n\n".join(
        [
            _extract_repair_function("post_dev_fix_quality_recovery_command_if_needed"),
            f"WORKSPACE={str(workspace)!r}",
            f"PLAN_NAME={plan_name!r}",
            f"DATA_FILE={str(data_path)!r}",
            f"INVESTIGATOR_RECEIPT_PATH={str(receipt_path)!r}",
            f"ARNOLD_SRC={str(REPO_ROOT)!r}",
            "post_dev_fix_quality_recovery_command_if_needed 1 'echo ordinary-relaunch'",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode != 0
    assert result.stdout == ""
    assert "not contained in tracked branch" in result.stderr
    assert "publication authorization is required" in result.stderr


def test_prior_receipted_legacy_dev_fix_can_enter_quality_recovery(tmp_path: Path) -> None:
    workspace, data_path, receipt_path, plan_name = _post_dev_quality_recovery_fixture(tmp_path)
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    entry = payload["iterations"][0]
    entry.pop("dev_before_sha")
    entry.pop("dev_after_sha")
    entry.pop("dev_fix_changed")
    entry.pop("dev_report_path")
    data_path.write_text(json.dumps(payload), encoding="utf-8")
    script = "\n\n".join(
        [
            _extract_repair_function("prior_receipted_dev_fix_iteration"),
            _extract_repair_function("post_dev_fix_quality_recovery_command_if_needed"),
            f"WORKSPACE={str(workspace)!r}",
            f"PLAN_NAME={plan_name!r}",
            f"DATA_FILE={str(data_path)!r}",
            f"INVESTIGATOR_RECEIPT_PATH={str(receipt_path)!r}",
            f"ARNOLD_SRC={str(REPO_ROOT)!r}",
            "prior_receipted_dev_fix_iteration",
            "post_dev_fix_quality_recovery_command_if_needed 1 'echo ordinary-relaunch'",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[0] == "1"
    assert "quality-gate resolve" in result.stdout
    assert f"bounded repair data:{data_path}#iterations[0].dev_report" in result.stdout


def test_prior_receipted_attempt_can_enter_recover_state_quality_recovery(
    tmp_path: Path,
) -> None:
    workspace, data_path, receipt_path, plan_name = _post_dev_quality_recovery_fixture(tmp_path)
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    entry = payload.pop("iterations")[0]
    entry.pop("dev_before_sha")
    entry.pop("dev_after_sha")
    entry.pop("dev_fix_changed")
    entry.pop("dev_report_path")
    payload["attempts"] = [entry]
    data_path.write_text(json.dumps(payload), encoding="utf-8")
    ordinary_relaunch = "echo ordinary-relaunch"
    receipt_path.write_text(
        json.dumps(
            {
                "recommended_action": "recover_state",
                "safe_repair_target": {
                    "kind": "plan_state_via_cli",
                    "scope": "supported chain start",
                },
                "handoff": {
                    "allowed_mutations": [f"supported_cli:{ordinary_relaunch}"]
                },
            }
        ),
        encoding="utf-8",
    )
    script = "\n\n".join(
        [
            _extract_repair_function("prior_receipted_dev_fix_iteration"),
            _extract_repair_function("post_dev_fix_quality_recovery_command_if_needed"),
            f"WORKSPACE={str(workspace)!r}",
            f"PLAN_NAME={plan_name!r}",
            f"DATA_FILE={str(data_path)!r}",
            f"INVESTIGATOR_RECEIPT_PATH={str(receipt_path)!r}",
            f"ARNOLD_SRC={str(REPO_ROOT)!r}",
            'locator="$(prior_receipted_dev_fix_iteration)"',
            'printf "%s\\n" "$locator"',
            f"post_dev_fix_quality_recovery_command_if_needed \"$locator\" {ordinary_relaunch!r}",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0] == "attempts:0"
    assert "quality-gate resolve" in result.stdout
    assert f"bounded repair data:{data_path}#attempts[0].dev_report" in result.stdout


def test_verified_quality_recovery_cannot_fall_back_without_receipt_locator(
    tmp_path: Path,
) -> None:
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps(
            {
                "durable_quality_block": {
                    "active": True,
                    "repair_evidence": {"verified": True},
                }
            }
        ),
        encoding="utf-8",
    )
    script = "\n\n".join(
        [
            _extract_repair_function("quality_recovery_requirement"),
            _extract_repair_function("select_mechanical_relaunch_command"),
            "post_dev_fix_quality_recovery_command_if_needed() { printf '%s\\n' 'unsafe-fallback'; }",
            f"INVESTIGATION_CONTEXT_PATH={str(context)!r}",
            "INVESTIGATOR_RECOMMENDED_ACTION=recover_state",
            "POST_DEV_FIX_ITERATION=",
            "select_mechanical_relaunch_command 'ordinary-relaunch'",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 76
    assert result.stdout == ""
    assert "no bounded dev-fix receipt locator" in result.stderr


def test_verified_quality_recovery_cannot_fall_back_when_receipt_mismatches(
    tmp_path: Path,
) -> None:
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps(
            {
                "durable_quality_block": {
                    "active": True,
                    "repair_evidence": {"verified": True},
                }
            }
        ),
        encoding="utf-8",
    )
    script = "\n\n".join(
        [
            _extract_repair_function("quality_recovery_requirement"),
            _extract_repair_function("select_mechanical_relaunch_command"),
            "post_dev_fix_quality_recovery_command_if_needed() { return 0; }",
            f"INVESTIGATION_CONTEXT_PATH={str(context)!r}",
            "INVESTIGATOR_RECOMMENDED_ACTION=recover_state",
            "POST_DEV_FIX_ITERATION=attempts:17",
            "select_mechanical_relaunch_command 'ordinary-relaunch'",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 76
    assert result.stdout == ""
    assert "could not construct its receipt-bound command" in result.stderr


def test_quality_recovery_context_bound_fails_closed(tmp_path: Path) -> None:
    context = tmp_path / "context.json"
    context.write_text(" " * 65_537, encoding="utf-8")
    script = "\n\n".join(
        [
            _extract_repair_function("quality_recovery_requirement"),
            _extract_repair_function("select_mechanical_relaunch_command"),
            "post_dev_fix_quality_recovery_command_if_needed() { return 0; }",
            f"INVESTIGATION_CONTEXT_PATH={str(context)!r}",
            "INVESTIGATOR_RECOMMENDED_ACTION=recover_state",
            "POST_DEV_FIX_ITERATION=attempts:17",
            "select_mechanical_relaunch_command 'ordinary-relaunch'",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 76
    assert result.stdout == ""
    assert "65536-byte bound" in result.stderr


def test_chain_marker_plan_identity_binds_from_validated_context(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    plan_name = "current-chain-plan"
    state_path = workspace / ".megaplan" / "plans" / plan_name / "state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{}", encoding="utf-8")
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps({"current": {"plan_name": plan_name}}), encoding="utf-8"
    )
    script = "\n\n".join(
        [
            _extract_repair_function("bind_plan_name_from_investigation_context"),
            f"INVESTIGATION_CONTEXT_PATH={str(context)!r}",
            f"WORKSPACE={str(workspace)!r}",
            "PLAN_NAME=",
            "bind_plan_name_from_investigation_context",
            "printf '%s\\n' \"$PLAN_NAME\"",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == plan_name


def test_context_plan_identity_cannot_override_marker_identity(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    plan_name = "context-plan"
    state_path = workspace / ".megaplan" / "plans" / plan_name / "state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{}", encoding="utf-8")
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps({"current": {"plan_name": plan_name}}), encoding="utf-8"
    )
    script = "\n\n".join(
        [
            _extract_repair_function("bind_plan_name_from_investigation_context"),
            f"INVESTIGATION_CONTEXT_PATH={str(context)!r}",
            f"WORKSPACE={str(workspace)!r}",
            "PLAN_NAME=marker-plan",
            "bind_plan_name_from_investigation_context",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 76
    assert "conflicts with validated investigation context" in result.stderr


def test_receipted_live_runner_gets_bounded_launch_settle_observation(
    tmp_path: Path,
) -> None:
    calls = tmp_path / "calls"
    script = "\n\n".join(
        [
            _extract_repair_function("wait_for_repair_goal_progress_if_live"),
            f"CALLS={str(calls)!r}",
            "repair_goal_control_snapshot() { if [[ -f \"$CALLS\" ]]; then printf '%s\\n' '{\"status\":\"progressed\",\"evaluation\":{\"control_action\":\"\",\"reason\":\"accepted\"},\"observation\":{}}'; else : > \"$CALLS\"; printf '%s\\n' '{\"status\":\"active\",\"evaluation\":{\"control_action\":\"investigate\",\"reason\":\"awaiting activity\"},\"observation\":{\"runner_transition\":{\"runner_pid_live\":true}}}'; fi; }",
            "repair_data_set_outcome() { :; }",
            "clear_repair_markers() { :; }",
            "repair_goal_record_terminal_failure() { :; }",
            "ensure_repair_budget_available() { :; }",
            "cap_timeout_to_repair_budget() { printf '%s\\n' 0; }",
            "log() { :; }",
            "SESSION=test-session",
            "REPAIR_GOAL_POLL_SECS=0",
            "CLOUD_WATCHDOG_REPAIR_LAUNCH_SETTLE_SECS=120",
            "wait_for_repair_goal_progress_if_live post-launch",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert calls.exists()


def test_receipted_quality_prelude_gets_bounded_launch_settle_observation(
    tmp_path: Path,
) -> None:
    calls = tmp_path / "calls"
    script = "\n\n".join(
        [
            _extract_repair_function("wait_for_repair_goal_progress_if_live"),
            f"CALLS={str(calls)!r}",
            "repair_goal_control_snapshot() { if [[ -f \"$CALLS\" ]]; then printf '%s\\n' '{\"status\":\"progressed\",\"evaluation\":{\"control_action\":\"\",\"reason\":\"accepted\"},\"observation\":{}}'; else : > \"$CALLS\"; printf '%s\\n' '{\"status\":\"active\",\"evaluation\":{\"control_action\":\"investigate\",\"reason\":\"quality prelude running\"},\"observation\":{\"runner_transition\":{\"runner_pid_live\":false}}}'; fi; }",
            "tmux() { [[ \"$1\" == has-session && \"$2\" == -t && \"$3\" == test-session ]]; }",
            "repair_data_set_outcome() { :; }",
            "clear_repair_markers() { :; }",
            "repair_goal_record_terminal_failure() { :; }",
            "ensure_repair_budget_available() { :; }",
            "cap_timeout_to_repair_budget() { printf '%s\\n' 0; }",
            "log() { :; }",
            "SESSION=test-session",
            "REPAIR_GOAL_POLL_SECS=0",
            "CLOUD_WATCHDOG_REPAIR_LAUNCH_SETTLE_SECS=120",
            "wait_for_repair_goal_progress_if_live post-launch",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert calls.exists()


def test_watchdog_chain_relaunch_prefers_plan_resume_for_external_resume_required(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True)
    (workspace / ".megaplan" / "cloud-logs").mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "current_state": "blocked",
                "resume_cursor": {"phase": "plan", "retry_strategy": "check_provider_and_retry"},
                "latest_failure": {
                    "kind": "external_error_resume_required",
                    "phase": "recover-blocked",
                },
            }
        ),
        encoding="utf-8",
    )
    script = "\n\n".join(
        [
            *_extract_relaunch_functions("watchdog"),
            f"SRC_DIR={str(REPO_ROOT)!r}",
            "SYNC_BRANCH=editible-install",
            (
                f"resolve_relaunch_command demo-session {shlex.quote(str(workspace))} "
                f"/tmp/chain.yaml chain demo-plan ''"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert "python3 -P -m arnold_pipelines.megaplan resume --plan demo-plan" in result.stdout
    assert "chain start" not in result.stdout


def test_repair_loop_chain_relaunch_prefers_plan_resume_for_external_resume_required(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True)
    (workspace / ".megaplan" / "cloud-logs").mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "current_state": "blocked",
                "resume_cursor": {"phase": "plan", "retry_strategy": "check_provider_and_retry"},
                "latest_failure": {
                    "kind": "external_error_resume_required",
                    "phase": "recover-blocked",
                },
            }
        ),
        encoding="utf-8",
    )
    script = "\n\n".join(
        [
            *_extract_relaunch_functions("repair"),
            f"ARNOLD_SRC={str(REPO_ROOT)!r}",
            "SYNC_BRANCH=editible-install",
            (
                f"resolve_relaunch_command demo-session {shlex.quote(str(workspace))} "
                f"/tmp/chain.yaml chain demo-plan ''"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert "python3 -P -m arnold_pipelines.megaplan resume --plan demo-plan" in result.stdout
    assert "chain start" not in result.stdout


def test_extracted_repair_relaunch_resolver_preserves_rejected_acceptance_gate(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    script = "\n\n".join(
        [
            *_extract_relaunch_functions("repair"),
            "log() { :; }",
            "report_item() { :; }",
            "python3() {",
            "  if [[ \"$1\" == \"-P\" && \"$2\" == \"-\" ]]; then",
            "    echo '{\"gate_open\": false, \"reason\": \"fixture rejection\"}'",
            "    return 0",
            "  fi",
            "  command python3 \"$@\"",
            "}",
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"ARNOLD_SRC={str(REPO_ROOT)!r}",
            f"REPAIR_DATA_DIR={str(tmp_path)!r}",
            f"REPORT_PATH={str(tmp_path / 'report.tsv')!r}",
            "SYNC_BRANCH=editible-install",
            (
                f"resolve_relaunch_command demo-session {str(tmp_path)!r} "
                f"{str(spec_path)!r} chain '' 'echo must-not-run'"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 1
    assert result.stdout == "failed:acceptance_gate_closed\n"
    assert "command not found" not in result.stderr
    assert "must-not-run" not in result.stdout


def test_watchdog_done_plan_reports_complete_without_repair_or_relaunch(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {"iteration": 1, "current_state": "done", "active_step": None},
        events_body="{}\n",
    )

    marker_path = marker_dir / "demo-session.json"
    marker_path.write_text("marker\n", encoding="utf-8")
    progress_path = marker_dir / f"{plan_name}.progress.json"
    progress_path.write_text("{}\n", encoding="utf-8")
    report_path = tmp_path / "report.tsv"

    script = "\n\n".join(
        [
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("session_marker_path"),
            _extract_wrapper_function("kimi_dispatch_marker_clear"),
            _extract_wrapper_function("clear_session_tracking_artifacts"),
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
kimi_dispatch_marker_set() { :; }
mechanical_relaunch_attempted_previously() { return 1; }
kimi_dispatch_failed_previously() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
plan_attention_status_env() {
  cat <<'EOF'
PLAN_STATUS_FOUND='1'
PLAN_STATUS_PLAN_NAME='demo-plan'
PLAN_STATUS_CURRENT_STATE=''
PLAN_STATUS_RETRY_STRATEGY=''
PLAN_STATUS_FAILURE_KIND=''
PLAN_STATUS_FAILURE_MESSAGE=''
PLAN_STATUS_FAILURE_PHASE=''
PLAN_STATUS_FAILURE_RECORDED_AT=''
PLAN_STATUS_TIERS_TRIED=''
PLAN_STATUS_PUSHED_COMMITS=''
PLAN_STATUS_MANUAL_REVIEW='0'
EOF
}
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} chain {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert marker_path.exists()
    assert progress_path.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tcomplete\tplan complete\t" in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX" not in result.stderr


def test_watchdog_done_plan_without_marker_plan_name_uses_newest_plan_dir(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    older_plan = workspace / ".megaplan" / "plans" / "older-plan"
    newer_plan = workspace / ".megaplan" / "plans" / "newer-plan"
    _write_plan(older_plan, {"iteration": 1, "current_state": "planning", "active_step": None})
    _write_plan(newer_plan, {"iteration": 1, "current_state": "done", "active_step": None})
    old_ts = time.time() - 60
    new_ts = time.time()
    os.utime(older_plan / "state.json", (old_ts, old_ts))
    os.utime(newer_plan / "state.json", (new_ts, new_ts))
    report_path = tmp_path / "report.tsv"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
kimi_dispatch_marker_set() { :; }
mechanical_relaunch_attempted_previously() { return 1; }
kimi_dispatch_failed_previously() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
plan_attention_status_env() {
  cat <<'EOF'
PLAN_STATUS_FOUND='1'
PLAN_STATUS_PLAN_NAME='newer-plan'
PLAN_STATUS_CURRENT_STATE=''
PLAN_STATUS_RETRY_STRATEGY=''
PLAN_STATUS_FAILURE_KIND=''
PLAN_STATUS_FAILURE_MESSAGE=''
PLAN_STATUS_FAILURE_PHASE=''
PLAN_STATUS_FAILURE_RECORDED_AT=''
PLAN_STATUS_TIERS_TRIED=''
PLAN_STATUS_PUSHED_COMMITS=''
PLAN_STATUS_MANUAL_REVIEW='0'
EOF
}
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} plan '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tcomplete\tplan complete\t" in report
    assert "spec_missing" not in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX" not in result.stderr


def test_watchdog_manual_review_plan_state_reports_needs_human_not_complete(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "iteration": 3,
            "current_state": "manual_review",
            "resume_cursor": {"retry_strategy": "manual_review"},
            "latest_failure": {"kind": "iteration_cap", "message": "review required"},
        },
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
session_terminal_status() { return 0; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
resolve_existing_remote_spec() { printf '%s\n' "$3"; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
notify_needs_human() {
  report_item "$1" "$2" "observe" "needs_human" "$7" "$3" "$4"
  log "needs-human webhook unset"
}
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} plan {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tneeds_human\tmanual_review halt;" in report
    assert "\tobserve\tcomplete\t" not in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr
    assert "needs-human webhook unset" in log_path.read_text(encoding="utf-8")


def test_watchdog_blocked_recovery_manual_review_dispatches_repair_before_needs_human(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "iteration": 10,
            "current_state": "blocked",
            "resume_cursor": {"phase": "review", "retry_strategy": "manual_review"},
            "latest_failure": {
                "kind": "blocked_recovery_not_resolved",
                "message": "recover-blocked requires every current blocker to be explicitly resolved as non-terminal",
                "phase": "recover-blocked",
            },
        },
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} plan {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\tblocked_recovery manual_review repair loop dispatched before needs_human\t" in report
    assert "\tobserve\tneeds_human\t" not in report
    assert "DISPATCH" in result.stderr
    assert "REPAIR" not in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr
    assert "needs-human webhook unset" not in log_path.read_text(encoding="utf-8")


def test_watchdog_auto_stall_manual_review_dispatches_repair_before_needs_human(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "iteration": 6,
            "current_state": "critiqued",
            "resume_cursor": {"retry_strategy": "manual_review"},
            "latest_failure": {
                "kind": "stalled",
                "message": "stalled at 'critiqued' for 5 iterations",
                "metadata": {"manual_review_origin": "auto_stall"},
            },
        },
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("repair_needs_human_path"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} plan {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\tauto_stall manual_review repair loop dispatched before needs_human\t" in report
    assert "\tobserve\tneeds_human\t" not in report
    assert "DISPATCH" in result.stderr
    assert "REPAIR" not in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr
    assert "needs-human webhook unset" not in log_path.read_text(encoding="utf-8")


def test_watchdog_legacy_stalled_manual_review_dispatches_repair_before_needs_human(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "iteration": 9,
            "current_state": "critiqued",
            "resume_cursor": {"phase": "override add-note", "retry_strategy": "manual_review"},
            "latest_failure": {
                "kind": "stalled",
                "message": "stalled at 'critiqued' for 5 iterations",
                "phase": "override add-note",
                "metadata": {"stall_count": 5, "iteration": 9},
            },
        },
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("repair_needs_human_path"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} plan {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\tauto_stall manual_review repair loop dispatched before needs_human\t" in report
    assert "\tobserve\tneeds_human\t" not in report
    assert "DISPATCH" in result.stderr
    assert "REPAIR" not in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr


def test_watchdog_awaiting_human_plan_state_dispatches_repair_before_needs_human(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "iteration": 3,
            "current_state": "awaiting_human",
            "latest_failure": {
                "kind": "blocked_by_prereq",
                "message": "execute reported blocked tasks awaiting user action: T1",
            },
        },
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("repair_needs_human_path"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} plan {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\tawaiting_human repair loop dispatched before needs_human\t" in report
    assert "\tobserve\tneeds_human\t" not in report
    assert "\tobserve\tcomplete\t" not in report
    assert "DISPATCH" in result.stderr
    assert "REPAIR" not in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr
    assert "needs-human webhook unset" not in log_path.read_text(encoding="utf-8")


def test_watchdog_awaiting_human_verify_prep_clarification_dispatches_repair(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "iteration": 3,
            "current_state": "awaiting_human_verify",
            "clarification": {
                "source": "prep",
                "questions": ["Which schema is authoritative?", "Which artifact should be backfilled?"],
            },
        },
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("repair_needs_human_path"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} plan {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\tawaiting_human repair loop dispatched before needs_human\t" in report
    assert "\tobserve\tneeds_human\t" not in report
    assert "DISPATCH" in result.stderr
    assert "REPAIR" not in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "needs-human webhook unset" not in log_path.read_text(encoding="utf-8")


def test_watchdog_nonterminal_plan_state_mechanically_relaunches_before_kimi(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {"iteration": 1, "current_state": "planning", "active_step": {"phase": "plan", "attempt": 1}},
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"

    script = "\n\n".join(
        [
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("kimi_dispatch_marker_set"),
            _extract_wrapper_function("mechanical_relaunch_attempted_previously"),
            _extract_wrapper_function("kimi_dispatch_failed_previously"),
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() {
  if [[ "$1" == "has-session" ]]; then
    return 1
  fi
  if [[ "$1" == "new-session" ]]; then
    echo TMUX_NEW >&2
    return 0
  fi
  echo "TMUX_$1" >&2
  return 0
}
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} plan {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trestart\trestarted\tstopped session relaunched\t" in report
    assert "\tobserve\tcomplete\t" not in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX_NEW" in result.stderr
    mechanical_marker = (marker_dir / "demo-session.kimi-dispatch").read_text().rstrip("\n").split("\t")
    assert mechanical_marker[:2] == [
        "arnold-dispatch-marker-v2",
        "deterministic_relaunch",
    ]
    assert mechanical_marker[3:] == ["", ""]


def test_watchdog_fences_mechanical_relaunch_for_phase_contract_failure(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "m6-exact-contract"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "iteration": 5,
            "current_state": "blocked",
            "active_step": None,
            "resume_cursor": {
                "phase": "critique",
                "retry_strategy": "repair_phase_contract",
            },
            "latest_failure": {
                "kind": "deterministic_phase_failure",
                "phase": "critique",
                "message": "critique contract failed three times",
            },
        },
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { echo INSTALL >&2; return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 0; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} plan {plan_name!r} ''",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_unavailable\tdeterministic phase-contract failure requires a claimed repair request before relaunch\t" in report
    assert "\trestart\trestarted\t" not in report
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr
    assert "mechanical relaunch fenced pending phase-contract repair custody" in log_path.read_text(encoding="utf-8")


def test_watchdog_chain_session_is_not_short_circuited_by_done_plan_state(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {"iteration": 1, "current_state": "done", "active_step": None},
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
kimi_dispatch_marker_set() { :; }
mechanical_relaunch_attempted_previously() { return 1; }
kimi_dispatch_failed_previously() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() {
  if [[ "$1" == "has-session" ]]; then
    return 1
  fi
  if [[ "$1" == "new-session" ]]; then
    echo TMUX_NEW >&2
    return 0
  fi
  echo "TMUX_$1" >&2
  return 0
}
plan_attention_status_env() {
  cat <<'EOF'
PLAN_STATUS_FOUND='0'
PLAN_STATUS_PLAN_NAME=''
PLAN_STATUS_CURRENT_STATE=''
PLAN_STATUS_RETRY_STRATEGY=''
PLAN_STATUS_FAILURE_KIND=''
PLAN_STATUS_FAILURE_MESSAGE=''
PLAN_STATUS_FAILURE_PHASE=''
PLAN_STATUS_FAILURE_RECORDED_AT=''
PLAN_STATUS_TIERS_TRIED=''
PLAN_STATUS_PUSHED_COMMITS=''
PLAN_STATUS_MANUAL_REVIEW='0'
EOF
}
""".strip(),
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/initiatives/demo-chain/chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trestart\trestarted\tstopped session relaunched\t" in report
    assert "\tobserve\tcomplete\t" not in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX_NEW" in result.stderr


def test_watchdog_unreadable_plan_state_falls_through_to_existing_stopped_path(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text("{not-json\n", encoding="utf-8")
    report_path = tmp_path / "report.tsv"

    script = "\n\n".join(
        [
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("kimi_dispatch_marker_set"),
            _extract_wrapper_function("mechanical_relaunch_attempted_previously"),
            _extract_wrapper_function("kimi_dispatch_failed_previously"),
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() {
  if [[ "$1" == "has-session" ]]; then
    return 1
  fi
  if [[ "$1" == "new-session" ]]; then
    echo TMUX_NEW >&2
    return 0
  fi
  echo "TMUX_$1" >&2
  return 0
}
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} chain {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trestart\trestarted\tstopped session relaunched\t" in report
    assert "\tobserve\tcomplete\t" not in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX_NEW" in result.stderr


def test_watchdog_restopped_session_falls_back_to_kimi_after_mechanical_relaunch(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {"iteration": 1, "current_state": "planning", "active_step": {"phase": "plan", "attempt": 1}},
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"
    (marker_dir / "demo-session.kimi-dispatch").write_text("2026-06-28T00:00:00Z\n", encoding="utf-8")

    script = "\n\n".join(
        [
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("mechanical_relaunch_attempted_previously"),
            _extract_wrapper_function("kimi_dispatch_failed_previously"),
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo stopped; }
session_terminal_status() { return 0; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
resolve_existing_remote_spec() { printf '%s\n' "$3"; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
notify_needs_human() {
  report_item "$1" "$2" "observe" "needs_human" "$7" "$3" "$4"
  log "needs-human webhook unset"
}
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} chain {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\trepair loop dispatched after mechanical relaunch\t" in report
    assert "DISPATCH" in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX" not in result.stderr


def test_repair_unhealthy_session_retries_root_cause_repair_after_recurring_outcome(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = tmp_path / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    session = "demo-session"
    (marker_dir / f"{session}.kimi-dispatch").write_text("2026-07-02T00:00:00Z\n", encoding="utf-8")
    (marker_dir / f"{session}.kimi-pgid").write_text("12345\n", encoding="utf-8")
    (repair_data_dir / f"{session}.repair-data.json").write_text(
        json.dumps({"outcome": "recurring_retry_pending"}),
        encoding="utf-8",
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("safe_name"),
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("kimi_dispatch_marker_clear"),
            _extract_wrapper_function("kimi_dispatch_failed_previously"),
            _extract_wrapper_function("repair_data_outcome_for_session"),
            _extract_wrapper_function("repair_outcome_wants_repair_retry"),
            _extract_wrapper_function("mechanical_relaunch_attempted_previously"),
            _extract_wrapper_function("repair_unhealthy_session"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            """
log() { echo "LOG $*" >&2; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; REPAIR_DISPATCH_RESULT=dispatched; return 0; }
tmux() { echo "TMUX $*" >&2; return 0; }
repair_unhealthy_session demo-session /workspace/example .megaplan/initiatives/demo/briefs/demo.md stopped
""".strip(),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert "previous repair outcome requires another root-cause repair" in result.stderr
    assert "DISPATCH" in result.stderr


def test_repair_unhealthy_session_preserves_direct_relaunch_after_timeout(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = tmp_path / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    session = "demo-session"
    (marker_dir / f"{session}.kimi-dispatch").write_text("2026-07-02T00:00:00Z\n", encoding="utf-8")
    (marker_dir / f"{session}.kimi-pgid").write_text("12345\n", encoding="utf-8")
    (repair_data_dir / f"{session}.repair-data.json").write_text(
        json.dumps({"outcome": "repair_timeout"}),
        encoding="utf-8",
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("safe_name"),
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("kimi_dispatch_marker_clear"),
            _extract_wrapper_function("kimi_dispatch_failed_previously"),
            _extract_wrapper_function("repair_data_outcome_for_session"),
            _extract_wrapper_function("repair_outcome_wants_repair_retry"),
            _extract_wrapper_function("mechanical_relaunch_attempted_previously"),
            _extract_wrapper_function("repair_unhealthy_session"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            """
log() { echo "LOG $*" >&2; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; REPAIR_DISPATCH_RESULT=dispatched; return 0; }
tmux() { echo "TMUX $*" >&2; return 0; }
repair_unhealthy_session demo-session /workspace/example .megaplan/initiatives/demo/briefs/demo.md stopped
""".strip(),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 1, result.stderr
    assert "repair loop tried and exited without recovery -> direct relaunch" in result.stderr
    assert "DISPATCH" not in result.stderr


def test_repair_unhealthy_session_preserves_direct_relaunch_after_repair_exhausted(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = tmp_path / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    session = "demo-session"
    (marker_dir / f"{session}.kimi-dispatch").write_text("2026-07-02T00:00:00Z\n", encoding="utf-8")
    (marker_dir / f"{session}.kimi-pgid").write_text("12345\n", encoding="utf-8")
    (repair_data_dir / f"{session}.repair-data.json").write_text(
        json.dumps({"outcome": "repair_exhausted"}),
        encoding="utf-8",
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("safe_name"),
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("kimi_dispatch_marker_clear"),
            _extract_wrapper_function("kimi_dispatch_failed_previously"),
            _extract_wrapper_function("repair_data_outcome_for_session"),
            _extract_wrapper_function("repair_outcome_wants_repair_retry"),
            _extract_wrapper_function("mechanical_relaunch_attempted_previously"),
            _extract_wrapper_function("repair_unhealthy_session"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            """
log() { echo "LOG $*" >&2; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; REPAIR_DISPATCH_RESULT=dispatched; return 0; }
tmux() { echo "TMUX $*" >&2; return 0; }
repair_unhealthy_session demo-session /workspace/example .megaplan/initiatives/demo/briefs/demo.md stopped
""".strip(),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 1, result.stderr
    assert "repair loop tried and exited without recovery -> direct relaunch" in result.stderr
    assert "DISPATCH" not in result.stderr


def test_repair_unhealthy_session_preserves_direct_relaunch_for_non_retry_repair_outcome(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = tmp_path / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    session = "demo-session"
    (marker_dir / f"{session}.kimi-dispatch").write_text("2026-07-02T00:00:00Z\n", encoding="utf-8")
    (marker_dir / f"{session}.kimi-pgid").write_text("12345\n", encoding="utf-8")
    (repair_data_dir / f"{session}.repair-data.json").write_text(
        json.dumps({"outcome": "discord_escalated"}),
        encoding="utf-8",
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("safe_name"),
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("kimi_dispatch_marker_clear"),
            _extract_wrapper_function("kimi_dispatch_failed_previously"),
            _extract_wrapper_function("repair_data_outcome_for_session"),
            _extract_wrapper_function("repair_outcome_wants_repair_retry"),
            _extract_wrapper_function("mechanical_relaunch_attempted_previously"),
            _extract_wrapper_function("repair_unhealthy_session"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            """
log() { echo "LOG $*" >&2; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; REPAIR_DISPATCH_RESULT=dispatched; return 0; }
tmux() { echo "TMUX $*" >&2; return 0; }
repair_unhealthy_session demo-session /workspace/example .megaplan/initiatives/demo/briefs/demo.md stopped
""".strip(),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 1, result.stderr
    assert "repair loop tried and exited without recovery -> direct relaunch" in result.stderr
    assert "DISPATCH" not in result.stderr


def test_watchdog_manual_review_chain_state_reports_needs_human_without_relaunch_or_kimi(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "iteration": 9,
            "current_state": "blocked",
            "resume_cursor": {"phase": "recover-blocked", "retry_strategy": "manual_review"},
            "latest_failure": {"kind": "iteration_cap", "message": "exceeded max_iterations=200"},
            "history": [
                {
                    "step": "execute",
                    "result": "blocked",
                    "batch_to_tier": [
                        {"actual_agent": "codex", "actual_model": "gpt-5.4"},
                        {"tier_model_spec": "codex:gpt-5.5"},
                    ],
                }
            ],
        },
        events_body="{}\n",
    )
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": plan_name,
                "last_state": "blocked",
                "last_pushed_commit": "abc123def456",
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
session_terminal_status() { return 0; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
resolve_existing_remote_spec() { printf '%s\n' "$3"; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
notify_needs_human() {
  report_item "$1" "$2" "observe" "needs_human" "$7" "$3" "$4"
  log "needs-human webhook unset"
}
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/initiatives/demo-chain/chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tneeds_human\tmanual_review halt;" in report
    assert "abc123def456" in report
    assert "gpt-5.4" in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX" not in result.stderr
    assert "needs-human webhook unset" in log_path.read_text(encoding="utf-8")


def test_watchdog_manual_review_repairable_fixture_dispatches_l1_without_needs_human(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "agentic-replay-viewer"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "iteration": 4,
            "name": plan_name,
            "current_state": "blocked",
            "resume_cursor": {"phase": "execute", "retry_strategy": "manual_review"},
            "latest_failure": {
                "kind": "blocked_recovery_not_resolved",
                "message": "repairable blocker",
                "phase": "execute",
                "metadata": {"blocked_task_id": "T1"},
            },
        },
        events_body="{}\n",
    )
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps({"current_plan_name": plan_name, "last_state": "blocked"}),
        encoding="utf-8",
    )
    (marker_dir / "demo-chain.json").write_text(
        json.dumps(
            {
                "session": "demo-chain",
                "workspace": str(workspace),
                "remote_spec": str(spec_path),
                "run_kind": "chain",
                "plan_name": plan_name,
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
session_terminal_status() { return 0; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
resolve_existing_remote_spec() { printf '%s\n' "$3"; }
dispatch_kimi_repair() { echo DISPATCH >&2; REPAIR_DISPATCH_RESULT=dispatched; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
notify_needs_human() {
  report_item "$1" "$2" "observe" "needs_human" "$7" "$3" "$4"
  log "needs-human webhook unset"
}
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/initiatives/demo-chain/chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\tmanual_review repair loop dispatched before needs_human\t" in report
    assert "\tobserve\tneeds_human\t" not in report
    assert "DISPATCH" in result.stderr
    assert "needs-human webhook unset" not in log_path.read_text(encoding="utf-8")


def test_watchdog_execution_blocked_manual_review_dispatches_l1_without_needs_human(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "progress-auditor-stage-20260704-1400"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "iteration": 8,
            "name": plan_name,
            "current_state": "blocked",
            "resume_cursor": {"phase": "execute", "retry_strategy": "manual_review"},
            "latest_failure": {
                "kind": "execution_blocked",
                "message": "execute reported prerequisite-blocked tasks: T4",
                "phase": "execute",
                "metadata": {"blocking_reasons": ["T4 fixture evidence not surfaced"]},
            },
        },
        events_body="{}\n",
    )
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps({"current_plan_name": plan_name, "last_state": "blocked"}),
        encoding="utf-8",
    )
    (marker_dir / "demo-chain.json").write_text(
        json.dumps(
            {
                "session": "demo-chain",
                "workspace": str(workspace),
                "remote_spec": str(spec_path),
                "run_kind": "chain",
                "plan_name": plan_name,
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
session_terminal_status() { return 0; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
resolve_existing_remote_spec() { printf '%s\n' "$3"; }
dispatch_kimi_repair() { echo DISPATCH >&2; REPAIR_DISPATCH_RESULT=dispatched; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
notify_needs_human() {
  report_item "$1" "$2" "observe" "needs_human" "$7" "$3" "$4"
  log "needs-human webhook unset"
}
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/initiatives/demo-chain/chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\tmanual_review repair loop dispatched before needs_human\t" in report
    assert "\tobserve\tneeds_human\t" not in report
    assert "DISPATCH" in result.stderr
    assert "needs-human webhook unset" not in log_path.read_text(encoding="utf-8")


def test_watchdog_awaiting_human_chain_state_dispatches_repair_before_needs_human(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    _write_plan(
        plan_dir,
        {
            "iteration": 9,
            "current_state": "finalized",
        },
        events_body="{}\n",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "m7-06-runtime-deletion-target-purge",
                        "description": "Delete runtime targets.",
                        "status": "blocked",
                    }
                ],
                "user_actions": [
                    {
                        "id": "ua-01-reclassify-deletion-targets",
                        "phase": "before_execute",
                        "blocks_task_ids": ["m7-06-runtime-deletion-target-purge"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": plan_name,
                "last_state": "awaiting_human",
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("repair_needs_human_path"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/initiatives/demo-chain/chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\tstate mismatch repair loop dispatched\t" in report
    assert "\tobserve\tneeds_human\t" not in report
    assert "DISPATCH" in result.stderr
    assert "REPAIR" not in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr
    assert "needs-human webhook unset" not in log_path.read_text(encoding="utf-8")


def test_watchdog_awaiting_human_verify_chain_state_dispatches_repair_before_relaunch(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "iteration": 1,
            "current_state": "awaiting_human_verify",
            "clarification": {
                "intent_summary": "prep surfaced 2 blocking ambiguities; answer and resume",
                "questions": ["Q1", "Q2"],
                "source": "prep",
            },
        },
        events_body="{}\n",
    )
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": plan_name,
                "last_state": "awaiting_human_verify",
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("repair_needs_human_path"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
chain_health_status() {
  CHAIN_HEALTH_STATUS=ok
  CHAIN_HEALTH_SUMMARY=
  CHAIN_HEALTH_ARTIFACT_PATH=
  CHAIN_HEALTH_LOG_MESSAGE=
}
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\tawaiting_human repair loop dispatched before needs_human\t" in report
    assert "\trestart\trestarted\tstopped session relaunched\t" not in report
    assert "DISPATCH" in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr
    assert "REPAIR" not in result.stderr


def test_watchdog_completed_chain_state_reports_complete_without_repair(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": "",
                "current_state": "",
                "last_state": "done",
                "events": [{"msg": "all milestones complete"}],
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/initiatives/demo-chain/chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tcomplete\tchain complete\t" in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr


def test_watchdog_partial_done_chain_state_relaunches_next_milestone(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    repair_data_dir = marker_dir / "repair-data"
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        "milestones:\n"
        "- label: m1\n"
        "- label: m2\n"
        "- label: m3\n"
        "- label: m4\n"
        "- label: m5\n",
        encoding="utf-8",
    )
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_milestone_index": 3,
                "current_plan_name": None,
                "last_state": "done",
                "pr_number": None,
                "pr_state": None,
                "completed": [
                    {"label": "m1", "status": "done"},
                    {"label": "m2", "status": "done"},
                    {"label": "m3", "status": "done"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (chain_dir / "chain-stale-complete.json").write_text(
        json.dumps(
            {
                "current_plan_name": "",
                "last_state": "done",
                "events": [{"msg": "all milestones complete"}],
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("session_terminal_status"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
chain_health_status() { CHAIN_HEALTH_STATUS=ok; CHAIN_HEALTH_KIND=; CHAIN_HEALTH_SUMMARY=; return 0; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
repair_needs_human_path() { printf '%s\n' /no/such/repair-needs-human.json; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
mechanical_relaunch_attempted_previously() { return 1; }
kimi_dispatch_failed_previously() { return 1; }
kimi_dispatch_marker_set() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 0; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 0; }
""".strip(),
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/initiatives/demo-chain/chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tcomplete\tchain complete\t" not in report
    assert "RELAUNCH" in result.stderr
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr

def test_watchdog_missing_chain_spec_uses_terminal_chain_state_without_repair(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": "",
                "current_state": "",
                "last_state": "done",
                "events": [{"msg": "all milestones complete"}],
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("session_terminal_status"),
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(marker_dir / 'repair-data')!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/initiatives/demo-chain/chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tcomplete\tchain complete\t" in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr


def test_watchdog_missing_workspace_uses_completed_repair_history_without_repair(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "missing-ws"
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"
    (repair_data_dir / "demo-chain.repair-data.json").write_text(
        json.dumps(
            {
                "session": "demo-chain",
                "attempts": [
                    {
                        "failure_classification": "chain_completed",
                        "chain_state_summary": {
                            "current_plan_name": "",
                            "current_state": "",
                            "last_state": "done",
                            "events": [{"msg": "all milestones complete"}],
                        },
                        "failure_context": {
                            "failure_classification": "chain_completed",
                            "chain_state_summary": {
                                "current_plan_name": "",
                                "current_state": "",
                                "last_state": "done",
                            },
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("session_terminal_status"),
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-chain {str(workspace)!r} /missing/demo-chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tcomplete\tchain complete\t" in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr


def test_watchdog_missing_base_ref_chain_state_reports_needs_human_without_plan_state(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": None,
                "last_state": "missing_base_ref",
                "metadata": {
                    "missing_base_ref": {
                        "base_branch": "stack/base",
                        "last_known_sha": "abc123def456",
                        "message": "Base branch 'stack/base' is missing on origin and no local ref is available to restore it.",
                        "recorded_at": "2026-06-28T00:00:00Z",
                        "retry_strategy": "manual_review",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/initiatives/demo-chain/chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tneeds_human\tmanual_review halt;" in report
    assert "state=missing_base_ref" in report
    assert "failure=missing_base_ref" in report
    assert "missing_base_ref" in report
    assert "stack/base" in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX" not in result.stderr


def test_watchdog_normal_chain_state_does_not_force_missing_base_ref_manual_review(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": None,
                "last_state": "blocked",
                "metadata": {"note": "not missing base ref"},
            }
        ),
        encoding="utf-8",
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            f"eval \"$(plan_attention_status_env {str(workspace)!r} {str(spec_path)!r} chain '')\"",
            "printf '%s\\t%s\\t%s\\n' \"$PLAN_STATUS_MANUAL_REVIEW\" \"$PLAN_STATUS_FAILURE_KIND\" \"$PLAN_STATUS_CURRENT_STATE\"",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0"


def test_watchdog_scan_once_completes_when_chain_state_is_unreadable(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / "demo-session.json"
    marker_path.write_text(
        json.dumps(
            {
                "session": "demo-session",
                "workspace": str(workspace),
                "remote_spec": ".megaplan/initiatives/demo-chain/chain.yaml",
                "run_kind": "chain",
            }
        ),
        encoding="utf-8",
    )
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text("{not-json\n", encoding="utf-8")
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("json_field"),
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("launch_chain_tick"),
            _extract_wrapper_function("scan_once_unlocked"),
            _extract_wrapper_function("scan_once"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"LOG={str(log_path)!r}",
            f"SCAN_LOCK_FILE={str(tmp_path / 'watchdog-scan.lock')!r}",
            "SCAN_LOCK_WAIT_SECS=0",
            "COOPERATIVE_ONCE=0",
            "WATCHDOG_BOOTSTRAP_RECOVERED=0",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
bootstrap_watchdog_observation() { return 0; }
write_watchdog_sweep_health() { return 0; }
write_watchdog_heartbeat() { :; }
write_status_snapshot() { :; }
repair_trigger_scan() { :; }
run_repair_data_maintenance() { :; }
maybe_reexec_updated_watchdog() { :; }
sync_editable_source_branch() { return 0; }
adopt_unmarked_tmux_sessions() { return 0; }
reap_stale_repairs() { return 0; }
emit_report() { cp "$1" REPORT_PATH_PLACEHOLDER; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
mechanical_relaunch_attempted_previously() { return 0; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
kimi_dispatch_failed_previously() { return 1; }
kimi_dispatch_marker_set() { :; }
kimi_dispatch_marker_clear() { :; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".replace("REPORT_PATH_PLACEHOLDER", str(report_path)).strip(),
            "scan_once",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    log_text = log_path.read_text(encoding="utf-8")
    assert "current-target observe session=demo-session evidence=" in log_text
    assert "scan complete markers=1" in log_text
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\trepair loop dispatched after mechanical relaunch\t" in report
    assert "needs_human" not in report
    assert "DISPATCH" in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX" not in result.stderr


def test_repair_loop_collect_failure_context_includes_resolver_output(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    workspace.mkdir()
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    (marker_dir / "demo-session.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "workspace": str(workspace),
                "remote_spec": ".megaplan/initiatives/demo/chain.yaml",
                "run_kind": "chain",
                "plan_name": "demo-plan",
            }
        ),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" \"$MARKER_DIR\" \"$DATA_DIR\" <<'PY'",
    )
    env = dict(os.environ)
    env["MARKER_DIR"] = str(marker_dir)
    env["DATA_DIR"] = str(repair_data_dir)
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    prog_path = tmp_path / "_collect_failure_context.py"
    prog_path.write_text(program, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(prog_path),
            str(workspace),
            "demo-session",
            "chain",
            "",
            str(marker_dir),
            str(repair_data_dir),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["resolver_output"]["session"] == "demo-session"
    assert payload["resolver_output"]["authoritative_source"] in {"marker", "plan_state", "chain_state"}


def test_watchdog_needs_human_webhook_posts_once_when_configured(tmp_path: Path) -> None:
    dm_helper = tmp_path / "arnold-discord-dm"
    dm_helper.write_text(
        "#!/usr/bin/env bash\n"
        "cat >/dev/null\n"
        "printf '%s\\n' '{\"ok\": false, \"reason\": \"send_failed\"}'\n",
        encoding="utf-8",
    )
    dm_helper.chmod(dm_helper.stat().st_mode | stat.S_IXUSR)

    curl_path = tmp_path / "curl"
    curl_path.write_text(
        "#!/usr/bin/env bash\n"
        f"echo called >> {str(tmp_path / 'curl-calls.txt')!r}\n"
        f"for arg in \"$@\"; do\n"
        "  case \"$arg\" in\n"
        f"    @*) cp \"${{arg#@}}\" {str(tmp_path / 'webhook-payload.json')!r} ;;\n"
        "  esac\n"
        "done\n",
        encoding="utf-8",
    )
    curl_path.chmod(curl_path.stat().st_mode | stat.S_IXUSR)

    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"
    notify_line = (
        f"notify_needs_human {str(report_path)!r} demo-session /tmp/ws "
        ".megaplan/initiatives/demo/briefs/demo.md chain stopped 'manual_review halt'"
    )
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            f"LOG={str(log_path)!r}",
            f"DISCORD_DM_BIN={str(dm_helper)!r}",
            "REPORT_WEBHOOK='https://example.test/watchdog'",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
PLAN_STATUS_PLAN_NAME='demo-plan'
PLAN_STATUS_CURRENT_STATE='blocked'
PLAN_STATUS_RETRY_STRATEGY='manual_review'
PLAN_STATUS_FAILURE_KIND='iteration_cap'
PLAN_STATUS_FAILURE_MESSAGE='exceeded max_iterations=200'
PLAN_STATUS_FAILURE_PHASE='recover-blocked'
PLAN_STATUS_FAILURE_RECORDED_AT='2026-06-28T11:29:34Z'
PLAN_STATUS_TIERS_TRIED='codex:gpt-5.4, codex:gpt-5.5'
PLAN_STATUS_PUSHED_COMMITS='abc123def456'
""".strip(),
            notify_line,
        ]
    )
    result = _run_watchdog_shell(script, path_prefix=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "curl-calls.txt").read_text(encoding="utf-8").strip().splitlines() == ["called"]
    payload = json.loads((tmp_path / "webhook-payload.json").read_text(encoding="utf-8"))
    assert payload["session"] == "demo-session"
    assert payload["plan"]["name"] == "demo-plan"
    assert payload["plan"]["tiers_tried"] == ["codex:gpt-5.4", "codex:gpt-5.5"]
    assert payload["plan"]["pushed_commit_shas"] == ["abc123def456"]
    report = report_path.read_text(encoding="utf-8")
    assert "\tnotify\twebhook_sent\tneeds-human webhook delivered\t" in report


def test_watchdog_log_redacts_stdout_and_log_file(tmp_path: Path) -> None:
    log_path = tmp_path / "watchdog.log"
    script = "\n\n".join(
        [
            _extract_wrapper_function("redact_inline_text"),
            _extract_wrapper_function("log"),
            f"SRC_DIR={shlex.quote(str(REPO_ROOT))}",
            f"LOG={shlex.quote(str(log_path))}",
            "log 'Authorization: Bearer bearer-secret-token-value'",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert "bearer-secret-token-value" not in result.stdout
    assert f"Authorization: Bearer {REDACTION}" in result.stdout
    assert "bearer-secret-token-value" not in log_path.read_text(encoding="utf-8")


def test_watchdog_needs_human_launches_resident_diagnostic_instead_of_bare_dm(
    tmp_path: Path,
) -> None:
    diagnostic_helper = tmp_path / "arnold-human-review-diagnostic"
    diagnostic_helper.write_text(
        "#!/usr/bin/env bash\n"
        "payload=''\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  if [[ \"$1\" == --payload-file ]]; then payload=\"$2\"; shift 2; else shift; fi\n"
        "done\n"
        f"cp \"$payload\" {str(tmp_path / 'diagnostic-payload.json')!r}\n"
        "printf '%s\\n' '{\"ok\":true,\"status\":\"launched\",\"run_id\":\"subagent-20260714-120000-abcdef12\",\"manifest_path\":\"/tmp/manifest.json\",\"state_path\":\"/tmp/state.json\",\"fallback_delivery_required\":false}'\n",
        encoding="utf-8",
    )
    diagnostic_helper.chmod(diagnostic_helper.stat().st_mode | stat.S_IXUSR)
    dm_helper = tmp_path / "arnold-discord-dm"
    dm_helper.write_text(
        "#!/usr/bin/env bash\n"
        f"cat > {str(tmp_path / 'dm-called.json')!r}\n"
        "printf '%s\\n' '{\"ok\": true, \"message_count\": 1}'\n",
        encoding="utf-8",
    )
    dm_helper.chmod(dm_helper.stat().st_mode | stat.S_IXUSR)

    curl_path = tmp_path / "curl"
    curl_path.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
    curl_path.chmod(curl_path.stat().st_mode | stat.S_IXUSR)

    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            f"LOG={str(log_path)!r}",
            f"MARKER_DIR={str(tmp_path / 'markers')!r}",
            f"REPAIR_DATA_DIR={str(tmp_path / 'repair-data')!r}",
            f"DISCORD_DM_BIN={str(dm_helper)!r}",
            f"HUMAN_REVIEW_DIAGNOSTIC_BIN={str(diagnostic_helper)!r}",
            "REPORT_WEBHOOK='https://example.test/watchdog'",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
PLAN_STATUS_PLAN_NAME='demo-plan'
PLAN_STATUS_CURRENT_STATE='manual_review'
PLAN_STATUS_RETRY_STRATEGY='manual_review'
PLAN_STATUS_FAILURE_KIND='iteration_cap'
PLAN_STATUS_FAILURE_MESSAGE='exceeded max_iterations=200'
PLAN_STATUS_FAILURE_PHASE='recover-blocked'
PLAN_STATUS_FAILURE_RECORDED_AT='2026-06-28T11:29:34Z'
PLAN_STATUS_TIERS_TRIED='deepseek:flash, codex:gpt-5.4, codex:gpt-5.5'
PLAN_STATUS_PUSHED_COMMITS='abc123def456, fedcba654321'
""".strip(),
            f"notify_needs_human {str(report_path)!r} demo-session /tmp/ws .megaplan/initiatives/demo/briefs/demo.md chain stopped 'manual_review halt'",
        ]
    )

    result = _run_watchdog_shell(script, path_prefix=tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads((tmp_path / "diagnostic-payload.json").read_text(encoding="utf-8"))
    assert payload["title"] == "Megaplan needs human review - demo-session"
    assert payload["plan"]["tiers_tried"] == ["deepseek:flash", "codex:gpt-5.4", "codex:gpt-5.5"]
    assert payload["plan"]["pushed_commit_shas"] == ["abc123def456", "fedcba654321"]
    assert any(field["label"] == "Tiers tried" and field["joiner"] == " -> " for field in payload["fields"])
    assert not (tmp_path / "dm-called.json").exists()
    report = report_path.read_text(encoding="utf-8")
    assert "\tnotify\tdiagnostic_agent_launched\t" in report
    assert "needs-human webhook delivered" not in log_path.read_text(encoding="utf-8")


def test_watchdog_needs_human_launch_failure_sends_truthful_actionable_fallback(
    tmp_path: Path,
) -> None:
    diagnostic_helper = tmp_path / "arnold-human-review-diagnostic"
    diagnostic_helper.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' '{\"ok\":false,\"status\":\"launch_failed\",\"error\":\"resident supervisor unavailable\",\"state_path\":\"\",\"fallback_delivery_required\":true}'\n"
        "exit 1\n",
        encoding="utf-8",
    )
    diagnostic_helper.chmod(diagnostic_helper.stat().st_mode | stat.S_IXUSR)
    dm_helper = tmp_path / "arnold-discord-dm"
    dm_helper.write_text(
        "#!/usr/bin/env bash\n"
        f"cat > {str(tmp_path / 'dm-payload.json')!r}\n"
        "printf '%s\\n' '{\"ok\":true,\"channel_id\":\"34\",\"message_ids\":[\"999\"],\"message_count\":1}'\n",
        encoding="utf-8",
    )
    dm_helper.chmod(dm_helper.stat().st_mode | stat.S_IXUSR)
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            f"LOG={str(log_path)!r}",
            f"MARKER_DIR={str(tmp_path / 'markers')!r}",
            f"REPAIR_DATA_DIR={str(tmp_path / 'repair-data')!r}",
            f"DISCORD_DM_BIN={str(dm_helper)!r}",
            f"HUMAN_REVIEW_DIAGNOSTIC_BIN={str(diagnostic_helper)!r}",
            "REPORT_WEBHOOK=''",
            "report_item() { printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' \"$1\" \"$2\" \"$3\" \"$4\" \"$5\" \"$6\" \"$7\" >> \"$1\"; }",
            "log() { printf '%s\\n' \"$*\" >> \"$LOG\"; }",
            "PLAN_STATUS_PLAN_NAME='demo-plan'",
            "PLAN_STATUS_FAILURE_KIND='iteration_cap'",
            "PLAN_STATUS_FAILURE_MESSAGE='bounded repair exhausted'",
            f"notify_needs_human {str(report_path)!r} demo-session /tmp/ws /tmp/spec.yaml chain stopped 'manual_review halt'",
        ]
    )

    result = _run_watchdog_shell(script, path_prefix=tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads((tmp_path / "dm-payload.json").read_text(encoding="utf-8"))
    assert payload["diagnostic_launch"] == {
        "status": "failed",
        "error": "resident supervisor unavailable",
    }
    assert "diagnostic launch failed" in payload["title"].lower()
    assert "do not assume an agent exists" in payload["next_action"]
    assert "discord_dm_sent" in report_path.read_text(encoding="utf-8")


def test_watchdog_needs_human_fixture_workspace_cannot_reach_delivery(tmp_path: Path) -> None:
    dm_helper = tmp_path / "arnold-discord-dm"
    dm_helper.write_text(
        "#!/usr/bin/env bash\n"
        f"echo called > {str(tmp_path / 'dm-called')!r}\n",
        encoding="utf-8",
    )
    dm_helper.chmod(dm_helper.stat().st_mode | stat.S_IXUSR)
    curl_path = tmp_path / "curl"
    curl_path.write_text(
        "#!/usr/bin/env bash\n"
        f"echo called > {str(tmp_path / 'webhook-called')!r}\n",
        encoding="utf-8",
    )
    curl_path.chmod(curl_path.stat().st_mode | stat.S_IXUSR)
    fixture_workspace = tmp_path / "ws"
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"LOG={str(log_path)!r}",
            f"DISCORD_DM_BIN={str(dm_helper)!r}",
            "REPORT_WEBHOOK='https://example.test/watchdog'",
            "report_item() { printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' \"$1\" \"$2\" \"$3\" \"$4\" \"$5\" \"$6\" \"$7\" >> \"$1\"; }",
            "log() { printf '%s\\n' \"$*\" >> \"$LOG\"; }",
            (
                f"notify_needs_human {str(report_path)!r} demo-chain "
                f"{str(fixture_workspace)!r} /tmp/spec.yaml chain stopped 'manual review'"
            ),
        ]
    )

    result = _run_watchdog_shell(script, path_prefix=tmp_path)

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "dm-called").exists()
    assert not (tmp_path / "webhook-called").exists()
    assert "test_notification_suppressed" in report_path.read_text(encoding="utf-8")
    assert "pytest_workspace" in log_path.read_text(encoding="utf-8")


def test_repair_escalation_fixture_workspace_cannot_reach_discord(tmp_path: Path) -> None:
    fixture_workspace = tmp_path / "ws"
    fixture_workspace.mkdir()
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps({"session": "demo-chain", "workspace": str(fixture_workspace)}),
        encoding="utf-8",
    )
    dm_helper = tmp_path / "arnold-discord-dm"
    dm_helper.write_text(
        "#!/usr/bin/env bash\n"
        f"echo called > {str(tmp_path / 'dm-called')!r}\n",
        encoding="utf-8",
    )
    dm_helper.chmod(dm_helper.stat().st_mode | stat.S_IXUSR)
    log_path = tmp_path / "repair.log"
    repair_text = _repair_wrapper()
    function_start = repair_text.index("send_discord_escalation() {")
    function_end = repair_text.index('\n}\n\nlog "starting session=', function_start) + 3
    script = "\n\n".join(
        [
            repair_text[function_start:function_end],
            "require_repair_lock_held() { :; }",
            "ensure_repair_budget_available() { :; }",
            "log() { printf '%s\\n' \"$*\" >> \"$LOG\"; }",
            f"ARNOLD_SRC={str(REPO_ROOT)!r}",
            f"DATA_FILE={str(data_path)!r}",
            f"WORKSPACE={str(fixture_workspace)!r}",
            "SESSION=demo-chain",
            f"MARKER_PATH={str(tmp_path / 'missing-marker.json')!r}",
            f"RUN_DIR={str(tmp_path)!r}",
            f"LOG={str(log_path)!r}",
            f"DISCORD_DM_BIN={str(dm_helper)!r}",
            "send_discord_escalation",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "test_execution_suppressed"
    assert not (tmp_path / "dm-called").exists()
    assert "pytest_workspace" in log_path.read_text(encoding="utf-8")


def test_watchdog_needs_human_missing_discord_config_skips_webhook_fallback(tmp_path: Path) -> None:
    dm_helper = tmp_path / "arnold-discord-dm"
    dm_helper.write_text(
        "#!/usr/bin/env bash\n"
        "cat >/dev/null\n"
        "printf '%s\\n' '{\"ok\": false, \"reason\": \"missing_config\", \"missing\": [\"DISCORD_BOT_TOKEN\", \"DISCORD_DM_USER_ID\"]}'\n",
        encoding="utf-8",
    )
    dm_helper.chmod(dm_helper.stat().st_mode | stat.S_IXUSR)

    curl_path = tmp_path / "curl"
    curl_path.write_text(
        "#!/usr/bin/env bash\n"
        f"echo called >> {str(tmp_path / 'curl-calls.txt')!r}\n",
        encoding="utf-8",
    )
    curl_path.chmod(curl_path.stat().st_mode | stat.S_IXUSR)

    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            f"LOG={str(log_path)!r}",
            f"DISCORD_DM_BIN={str(dm_helper)!r}",
            "REPORT_WEBHOOK='https://example.test/watchdog'",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
PLAN_STATUS_PLAN_NAME='demo-plan'
""".strip(),
            f"notify_needs_human {str(report_path)!r} demo-session /tmp/ws .megaplan/initiatives/demo/briefs/demo.md chain stopped 'manual_review halt'",
        ]
    )

    result = _run_watchdog_shell(script, path_prefix=tmp_path)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "curl-calls.txt").exists()
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tneeds_human\tmanual_review halt\t" in report
    assert "discord dm skipped; DISCORD_BOT_TOKEN or DISCORD_DM_USER_ID unset" in log_path.read_text(encoding="utf-8")


def test_arnold_discord_dm_wrapper_redacts_payload_before_rendering(tmp_path: Path) -> None:
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(
        json.dumps(
            {
                "title": "Megaplan needs human review - demo-session",
                "summary": "Authorization: Bearer bearer-secret-token-value",
                "fields": [{"label": "Token", "value": "export API_TOKEN=supersecret"}],
            }
        ),
        encoding="utf-8",
    )

    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    env.pop("DISCORD_BOT_TOKEN", None)
    env.pop("DISCORD_DM_USER_ID", None)
    env.pop("PYTEST_CURRENT_TEST", None)
    result = subprocess.run(
        ["python3", str(WRAPPER_DIR / "arnold-discord-dm")],
        stdin=payload_path.open("r", encoding="utf-8"),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    wrapper_result = json.loads(result.stdout)
    assert wrapper_result["ok"] is False
    assert wrapper_result["reason"] == "missing_config"
    assert "bearer-secret-token-value" not in result.stderr
    assert "supersecret" not in result.stderr


def test_watchdog_resolves_relative_chain_specs_against_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    report_path = tmp_path / "report.tsv"

    script = "\n\n".join(
        [
            _extract_wrapper_function("launch_chain_tick"),
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo alive; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_dispatch_marker_clear() { :; }
""".strip(),
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/initiatives/demo-chain/chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "alive" in report
    assert "spec_missing" not in report


def test_watchdog_scan_ignores_progress_snapshot_markers() -> None:
    text = _wrapper("arnold-watchdog")

    assert "*.progress.json|*.reap-progress.json|*.repair-progress.json|*.chain-health.progress.json" in text


def test_watchdog_enforces_single_instance_and_reexecs_after_hot_update() -> None:
    text = _wrapper("arnold-watchdog")
    scan_once = _extract_wrapper_function("scan_once_unlocked")

    assert 'LOCK_FILE="${CLOUD_WATCHDOG_LOCK_FILE:-/workspace/.megaplan/watchdog.lock}"' in text
    assert 'LOCK_HELD="${CLOUD_WATCHDOG_LOCK_HELD:-0}"' in text
    assert 'exec flock -n "$LOCK_FILE" bash "$SELF_PATH" "${WATCHDOG_ARGS[@]}"' in text
    assert "maybe_reexec_updated_watchdog()" in text
    assert 'source_wrapper="$SRC_DIR/arnold_pipelines/megaplan/cloud/wrappers/$(basename "$SELF_PATH")"' in text
    assert 'log "watchdog wrapper updated on disk; re-execing $reexec_reason"' in text
    assert 'exec bash "$reexec_path" "${WATCHDOG_ARGS[@]}"' in text
    assert 'log "scan start marker_dir=$MARKER_DIR"' in scan_once
    assert 'sync_editable_source_branch "$report_items" || true' in scan_once
    assert scan_once.count("maybe_reexec_updated_watchdog") == 2
    assert scan_once.index('log "scan start marker_dir=$MARKER_DIR"') < scan_once.index("maybe_reexec_updated_watchdog")
    assert scan_once.index('sync_editable_source_branch "$report_items" || true') < scan_once.rindex("maybe_reexec_updated_watchdog")


def test_watchdog_refresh_syncs_cloud_runtime_wrappers() -> None:
    text = _wrapper("arnold-watchdog")

    assert "sync_cloud_runtime_wrappers()" in text
    assert 'local wrapper_src_dir="$SRC_DIR/arnold_pipelines/megaplan/cloud/wrappers"' in text
    assert 'local wrapper_dest_dir="/usr/local/bin"' in text
    assert 'local support_dest_dir="/usr/local/share/arnold-watchdog"' in text
    assert 'if [[ -f "$dest" ]] && cmp -s "$wrapper" "$dest"; then' in text
    assert 'install -m 0755 "$wrapper" "$dest"' in text
    assert 'if [[ ! -f "$dest" ]] || ! cmp -s "$wrapper_src_dir/principles.md" "$dest"; then' in text
    assert 'install -m 0644 "$wrapper_src_dir/principles.md" "$dest"' in text
    assert 'sync_cloud_runtime_wrappers >> "$LOG" 2>&1 || return 1' in text


def test_watchdog_hot_update_prefers_newer_editable_source_wrapper(tmp_path: Path) -> None:
    wrapper = tmp_path / "installed" / "arnold-watchdog"
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    src_dir = tmp_path / "src"
    source_wrapper = src_dir / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers" / "arnold-watchdog"
    source_wrapper.parent.mkdir(parents=True, exist_ok=True)
    source_wrapper.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    stale = time.time() - 300
    fresh = time.time()
    os.utime(wrapper, (stale, stale))
    os.utime(source_wrapper, (fresh, fresh))

    fake_bash = tmp_path / "bash"
    fake_bash.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "print('\\n'.join(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    fake_bash.chmod(fake_bash.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("maybe_reexec_updated_watchdog"),
            "log() { :; }",
            f"SELF_PATH={str(wrapper)!r}",
            f"SRC_DIR={str(src_dir)!r}",
            "WATCHDOG_ARGS=(once)",
            f"WATCHDOG_STARTED_AT={int(stale)}",
            "maybe_reexec_updated_watchdog",
        ]
    )

    env = dict(os.environ)
    env["PATH"] = f"{tmp_path}:{env.get('PATH', '')}"
    result = subprocess.run(
        ["/bin/bash", "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [str(source_wrapper), "once"]


def test_arnold_chain_wrapper_reloads_hot_env_before_launch() -> None:
    text = _wrapper("arnold-chain")

    assert "if [[ -f /workspace/.cloud-hot-env ]]; then set -a; . /workspace/.cloud-hot-env; set +a; fi;" in text
    assert "python -P -m arnold_pipelines.megaplan chain start" in text


def test_watchdog_syncs_extra_skills_to_agent_skill_dirs() -> None:
    text = _wrapper("arnold-watchdog")

    assert '"$HOME/.claude/skills"' in text
    assert '"$HOME/.codex/skills"' in text
    assert '"$HOME/.agents/skills"' in text
    assert '"$HOME/.hermes/skills"' in text


def test_kimi_goal_operator_runs_from_editable_install_checkout() -> None:
    text = _wrapper("arnold-kimi-goal-operator")

    assert 'ARNOLD_SRC="${KIMI_GOAL_ARNOLD_SRC:-/workspace/arnold}"' in text
    assert 'SYNC_BRANCH="${KIMI_GOAL_SYNC_BRANCH:-${CLOUD_WATCHDOG_SYNC_BRANCH:-editible-install}}"' in text
    assert 'PRINCIPLES_PATH="${KIMI_GOAL_PRINCIPLES_PATH:-/usr/local/share/arnold-watchdog/principles.md}"' in text
    assert 'MAX_TURNS="${KIMI_GOAL_MAX_TURNS:-120}"' in text
    assert 'CODEX_TIMEOUT="${KIMI_GOAL_CODEX_TIMEOUT_SECS:-7200}"' in text
    assert '--max_turns="$MAX_TURNS"' in text
    assert 'CODEX_PROMPT="$RUN_DIR/codex-repair-prompt.md"' in text
    assert 'CODEX_LOG="$RUN_DIR/codex-repair.log"' in text
    assert 'capture "subagent launcher skill"' in text
    assert 'RUN_CWD="$ARNOLD_SRC"' in text
    assert 'cd "$RUN_CWD"' in text
    assert 'PYTHONSAFEPATH=1 PYTHONPATH="$ARNOLD_SRC:${PYTHONPATH:-}"' in text
    assert 'timeout "$TIMEOUT" python3 -P -m arnold.agent.run_agent \\' in text
    assert '--stdin-file "$PROMPT"' in text
    assert '--query_file=@managed-stdin@' in text
    assert '--query="$(cat "$PROMPT")"' not in text
    assert "Do not let MEGAPLAN_REF or the active workflow workspace branch" in text
    assert "Your Codex brief should contain the core issue, evidence, constraints, and plausible hypotheses only" in text
    assert "do not prescribe the implementation" in text
    assert "First read the \\$subagent-launcher SKILL.md" in text
    assert "then dispatch Codex through that skill" in text
    assert "If \\$subagent-launcher or Codex cannot be launched" in text
    assert "launching Codex repair subagent" in text
    assert 'python3 -m arnold_pipelines.megaplan.managed_agent run \\' in text
    assert '--stdin-file "$CODEX_PROMPT"' in text
    assert 'timeout "$CODEX_TIMEOUT" codex exec --sandbox danger-full-access \\' in text
    assert 'capture "codex repair subagent result"' in text
    assert "launching Kimi goal operator" in text
    assert text.index("launching Codex repair subagent") < text.index("launching Kimi goal operator")


def test_kimi_goal_operator_reaps_run_agent_child_on_exit() -> None:
    text = _wrapper("arnold-kimi-goal-operator")

    assert "set -m" in text
    assert "CHILD_PIDS=()" in text
    assert "cleanup_children()" in text
    assert "trap cleanup_children EXIT INT TERM HUP" in text
    assert 'kill -- -"$pgid"' in text
    assert 'kill -9 "$pid"' in text
    assert ') >> "$LOG" 2>&1 &' in text
    assert 'wait "$AGENT_PID"' in text


def test_watchdog_repair_principles_are_general_and_loaded_into_kimi_prompt() -> None:
    wrapper = _wrapper("arnold-kimi-goal-operator")
    principles = _wrapper("principles.md")

    assert "$PRINCIPLES_TEXT" in wrapper
    assert "# Repair Principles" in wrapper
    assert "Codex phases must run through the Codex plan/CLI path" in principles
    assert "DeepSeek phases must run through the direct DeepSeek API credentials" in principles
    assert "read the launcher skill instructions" in principles
    assert "brief Codex through `$subagent-launcher`" in principles


def test_repair_loop_wrapper_records_accumulated_data_and_escalates_models() -> None:
    text = _wrapper("arnold-repair-loop")

    assert 'DATA_FILE="$DATA_DIR/${SAFE_SESSION}.repair-data.json"' in text
    assert 'PROGRESS_FILE="$MARKER_DIR/${SAFE_SESSION}.repair-progress.json"' in text
    assert 'NEEDS_HUMAN_FILE="$DATA_DIR/${SAFE_SESSION}.needs-human.json"' in text
    assert 'FINDINGS_DIR="${CLOUD_WATCHDOG_REPAIR_FINDINGS_DIR:-/workspace/repair-findings}"' in text
    assert 'FINDINGS_DOC="${CLOUD_WATCHDOG_REPAIR_FINDINGS_DOC:-$FINDINGS_DIR/persistent-problems.md}"' in text
    assert 'REPAIR_PID_FILE="${CLOUD_WATCHDOG_REPAIR_PID_FILE:-$MARKER_DIR/${SAFE_SESSION}.repair-loop.pid}"' in text
    assert 'REPAIR_LOCK_DIR="${CLOUD_WATCHDOG_REPAIR_LOCK_DIR:-$MARKER_DIR/${SAFE_SESSION}.repair-loop.lock}"' in text
    assert "acquire_repair_lock()" in text
    assert "repair_loop_pid_matches_session()" in text
    assert "find_live_repair_loop_for_session()" in text
    assert "set -o noclobber" in text
    assert "from arnold_pipelines.megaplan.cloud.repair_lock import acquire_repair_lock" in text
    assert "from arnold_pipelines.megaplan.cloud.repair_lock import release_repair_lock" in text
    assert 'log "repair pid claimed session=$SESSION pid=$$ pidfile=$REPAIR_PID_FILE"' in text
    assert 'log "stale repair lock detected; leaving evidence in place session=$SESSION lock_dir=$REPAIR_LOCK_DIR"' in text
    assert 'log "stale repair lock reclaimed session=$SESSION lock_dir=$REPAIR_LOCK_DIR"' in text
    assert 'another repair loop is already active after stale lock recovery' in text
    assert 'log "stale repair pidfile detected; reclaiming session=$SESSION stale_pid=$existing_pid pidfile=$REPAIR_PID_FILE"' in text
    assert "guard_against_recursive_repair_loop()" in text
    assert 'export CLOUD_WATCHDOG_REPAIR_LOOP_ACTIVE=1' in text
    assert 'log "repair loop recursion blocked; parent repair loop already active' in text
    assert "acquire_repair_lock || exit 75" in text
    assert 'exit_if_repair_target_complete "start"' in text
    assert 'exit_if_repair_target_complete "iteration-$iteration-start"' in text
    assert 'exit_if_repair_target_complete "iteration-$iteration-post-kimi"' in text
    assert 'exit_if_repair_target_complete "post-iterations"' in text
    assert "repair_data_init()" in text
    assert "repair_data_record_dev()" in text
    assert "append_repair_finding_if_reported()" in text
    assert 'append_repair_finding_if_reported "$iteration" "$report_path" "$dispatch_model"' in text
    assert "repair_data_record_mechanical()" in text
    assert 'PYTHONPATH="$ARNOLD_SRC:${PYTHONPATH:-}" python3 - "$DATA_FILE" "$PROGRESS_FILE"' in text
    assert 'PYTHONPATH="$ARNOLD_SRC:${PYTHONPATH:-}" python3 - "$DATA_FILE" "$iteration" "$attempt_id" "$requested_model"' in text
    assert 'PYTHONPATH="$ARNOLD_SRC:${PYTHONPATH:-}" python3 - "$DATA_FILE" "$iteration" "$attempt_id" "$status" "$detail"' in text
    assert 'PYTHONPATH="$ARNOLD_SRC:${PYTHONPATH:-}" python3 - "$DATA_FILE" "$iteration" "$attempt_id" "$status" "$report_path" "$turn_rc" "$failure_context_file"' in text
    assert 'PYTHONPATH="$ARNOLD_SRC:${PYTHONPATH:-}" python3 - "$DATA_FILE" "$outcome"' in text
    assert 'failure_context_file="$(mktemp)"' in text
    assert 'PYTHONPATH="$ARNOLD_SRC:${PYTHONPATH:-}" python3 - "$DATA_FILE" "$failure_context_file"' in text
    assert "repair_data_record_kimi()" in text
    assert "from arnold_pipelines.megaplan.cloud.human_blockers import write_needs_human_marker_payload" in text
    assert "write_needs_human_marker_payload(" in text
    assert "repair_recurrence_prepare_attempt()" in text
    assert "render_recurrence_block()" in text
    assert "repair_exhausted_should_retry_without_human()" in text
    assert "collect_failure_context_json()" in text
    assert "PLAN_STATUS_STATE_MISMATCH" in _wrapper("arnold-watchdog")
    assert "render_failure_summary()" in text
    assert '"failure_context"' in text
    assert '"raw_failure_signals"' in text
    assert '"failure_classification"' in text
    assert '"chain_log_tail"' in text
    assert '"plan_events_tail"' in text
    assert '"mechanical_log_tail"' in text
    assert '"plan_latest_failure"' in text
    assert '"chain_state_summary"' in text
    assert '"pr_number": chain_state.get("pr_number")' in text
    assert '"target_base_ref": chain_state.get("target_base_ref")' in text
    assert '"workspace": str(workspace)' in text
    assert "workspace=str(payload.get(\"workspace\") or failure_context.get(\"workspace\") or \"\")" in text
    assert 'logger=lambda message: print(f"repair_recurrence: {message}", file=sys.stderr)' in text
    assert "repair_recurrence.atomic_write_json(data_path, payload)" in text
    assert "repair_recurrence.atomic_write_json(progress_path, session_snapshot)" in text
    assert "save_repair_data(pathlib.Path(path), payload)" in text
    assert "atomic_write_json(state_path, state)" in text
    assert '"plan_runtime_state"' in text
    assert '"last_gate"' in text
    assert "for iteration in 1 2 3; do" in text
    assert 'DEV_REQUESTED_MODEL="glm-5.2"' in text
    assert 'DEV_REQUESTED_MODEL="codex:gpt-5.4"' in text
    assert 'DEV_REQUESTED_MODEL="codex:gpt-5.5"' in text
    assert 'CLOUD_WATCHDOG_DEV_FIX_ENABLE_GLM:-0' in text
    assert 'GLM_FALLBACK="zhipu:glm-5.2 disabled by default for watchdog repair; using gpt-5.4 for iteration 1"' in text
    assert 'repair_data_set_outcome "progressed" "$status"' in text
    assert 'repair_data_set_outcome "true_human_blocker" "$status"' in text
    assert 'repair_data_set_outcome "recovery_not_verified"' in text
    assert 'repair_data_set_outcome "recurring_retry_pending"' in text
    assert text.index('exit_if_repair_target_complete "post-iterations"') < text.rindex('repair_data_set_outcome "recurring_retry_pending"')
    assert "write_needs_human_marker" in text
    assert "send_discord_escalation" in text
    assert "## Incident Snapshot" in text
    assert "## RECURRENCE EVIDENCE" in text
    assert "This is attempt " in text
    assert "for the same controlled-field symptom (recurrence detected)." in text
    assert "The symptom came back despite these prior fixes:" in text
    assert "primary failure signal(s)" in text
    assert "current run narrative (plan log tail when present)" in text
    assert "## Prior repair attempts" in text
    assert "Repair data file: $DATA_FILE" in text
    assert "Persistent findings doc: $FINDINGS_DOC" in text
    assert "Go to the deepest structural level" in text
    assert "Do not just fix the one symptom that caused this stop" in text
    assert "Do NOT pick the likely fix" in text
    assert "Trace the actual mechanism end-to-end" in text
    assert "Use the extra time in this root-cause attempt" in text
    assert "append it to the findings doc at $FINDINGS_DOC" in text
    assert "structural_pattern, other_instantiations, human_review_recommendation" in text
    assert "findings_doc_path, findings_doc_appended" in text
    assert 'entry["structural_pattern"] = report.get("structural_pattern") or ""' in text
    assert "do not relaunch the run yourself" in text.lower()


def test_repair_loop_wrapper_bounds_mechanical_and_kimi_launch_steps() -> None:
    text = _wrapper("arnold-repair-loop")

    assert 'DEV_TIMEOUT="${CLOUD_WATCHDOG_DEV_FIX_TIMEOUT_SECS:-600}"' in text
    assert 'DEV_ROOT_CAUSE_TIMEOUT="${CLOUD_WATCHDOG_DEV_FIX_ROOT_CAUSE_TIMEOUT_SECS:-3600}"' in text
    assert 'REPAIR_BUDGET_SECS="${CLOUD_WATCHDOG_REPAIR_BUDGET_SECS:-7200}"' in text
    assert 'KIMI_TIMEOUT="${CLOUD_WATCHDOG_KIMI_TIMEOUT_SECS:-600}"' in text
    assert 'KIMI_MAX_TURNS="${CLOUD_WATCHDOG_KIMI_MAX_TURNS:-40}"' in text
    assert "verify_started_and_holding()" in text
    assert "mechanical_launch_step()" in text
    assert "kill_matching_runner_processes()" in text
    assert 'kill_matching_runner_processes "$session" "$remote_spec" "$run_kind" "$plan_name"' not in text
    assert 'kill_tmux_session_if_present "$session"' not in text
    assert 'failed:existing_tmux_custody_unverified' in text
    assert 'preserved:existing_runner' in text
    assert "runner cleanup refused without an exact managed-run lifecycle receipt" in text
    assert "tmux cleanup refused without an exact managed-run lifecycle receipt" in text
    assert "tmux kill-session" not in text
    assert "os.killpg" not in text
    assert "SIGKILL" not in text
    assert "marker_requires_repair_despite_alive()" in text
    assert 'python3 - "$MARKER_PATH" "$DATA_FILE"' in text
    assert 'repair_payload.get("current_failure_context")' in text
    assert "live_plan_failure:" in text
    assert "state_mismatch" in text
    assert "repair target is alive but marker requires repair" in text
    assert "workspace_drift:" in text
    assert "sandbox_refused_outside_project_root" in text
    assert "run_kimi_launch_turn()" in text
    assert 'timeout "$dev_timeout"' in text
    assert '--stdin-file "$prompt_path"' in text
    assert 'PYTHONSAFEPATH=1 timeout "$KIMI_TIMEOUT" "$MEGAPLAN_SUPERVISOR_PYTHON" -P -m arnold.agent.run_agent' in text
    assert "--query_file=@managed-stdin@" in text
    assert '--query="$(cat "$prompt_path")"' not in text
    assert "prepare_repair_agent_exec_env()" in text
    assert "set +a" in text
    assert "export -n failure_summary chain_health_block recurrence_block mode_tasks relaunch_command" in text
    assert text.index("prepare_repair_agent_exec_env") < text.index('timeout "$dev_timeout"')
    assert text.index("prepare_repair_agent_exec_env", text.index("run_kimi_launch_turn()")) < text.index(
        'PYTHONSAFEPATH=1 timeout "$KIMI_TIMEOUT" "$MEGAPLAN_SUPERVISOR_PYTHON" -P -m arnold.agent.run_agent'
    )
    assert 'tmux new-session -d -s "$session"' in text
    assert 'launch_receipt="$RUN_DIR/mechanical-launch-$iteration-receipt.json"' in text
    assert '"schema_version": "arnold-mechanical-launch-receipt-v1"' in text
    assert 'export ARNOLD_AUTONOMY=$(printf \'%q\' "${ARNOLD_AUTONOMY:-}")' in text
    assert 'export ARNOLD_REPAIR_TRIGGER_ENABLED=$(printf \'%q\' "${ARNOLD_REPAIR_TRIGGER_ENABLED:-}")' in text
    assert "l1_mutation_authorized()" in text
    assert "observed: L1 mutation blocked before $mutation_label" in text
    assert "investigation custody check failed closed before mutation" in text
    assert '"started_at": started_at' in text
    assert 'echo "terminal:$post_status:receipt=$launch_receipt"' in text
    assert '"authorized-recovery-launch-failed"' in text
    assert text.index('if [[ "${INVESTIGATOR_RECOMMENDED_ACTION:-}" == "recover_state" ]]') < text.index(
        'GLM_MODEL=""'
    )
    assert r'rm -f -- "\${BASH_SOURCE[0]}"' in text
    launch_start = text.index('if ! tmux new-session -d -s "$session"')
    verify_start = text.index('health="$(verify_started_and_holding', launch_start)
    assert text[launch_start:verify_start].rstrip().endswith("fi")
    assert 'repair_data_record_kimi "$iteration" "$CURRENT_ATTEMPT_ID" "running"' in text


def test_meta_replan_effects_require_l2_mutation_authority() -> None:
    text = _wrapper("arnold-meta-repair-loop")

    branch = text.index('if [[ "$META_INVESTIGATION_ACTION" == "replan" ]]')
    authority = text.index("if ! l2_mutation_authorized; then", branch)
    reconciliation = text.index('REPLAN_RECONCILIATION="$', branch)
    retrigger = text.index('log "accepted L2 replan handoff; retriggering ordinary repair', branch)

    assert branch < authority < reconciliation < retrigger
    assert "observed: L2 replan effects blocked by master-plus-path authorization gate" in text


@pytest.mark.parametrize(
    ("authorized", "supervisor_python", "expected_rc", "expected_log"),
    [
        (False, "/bin/true", 77, "L1 mutation blocked before test-mutation"),
        (True, "/bin/false", 76, "investigation custody check failed closed"),
    ],
)
def test_repair_mutation_guard_cannot_be_ignored(
    tmp_path: Path,
    authorized: bool,
    supervisor_python: str,
    expected_rc: int,
    expected_log: str,
) -> None:
    effect = tmp_path / "effect"
    script = "\n\n".join(
        [
            _extract_repair_function("require_investigation_before_mutation"),
            f"""
require_repair_lock_held() {{ :; }}
l1_mutation_authorized() {{ return {0 if authorized else 1}; }}
log() {{ printf '%s\\n' "$*"; }}
MEGAPLAN_SUPERVISOR_PYTHON={supervisor_python}
WRAPPER_REPO_ROOT=/workspace/unused
ARNOLD_SRC=/workspace/unused
INVESTIGATION_CONTEXT_PATH=/workspace/unused-context
INVESTIGATOR_RECEIPT_PATH=/workspace/unused-receipt
INVESTIGATION_CONTEXT_DIGEST=unused
SESSION=test-session
require_investigation_before_mutation test-mutation
touch {effect}
""".strip(),
        ]
    )

    result = subprocess.run(
        ["bash", "-lc", script], capture_output=True, text=True, check=False
    )

    assert result.returncode == expected_rc
    assert expected_log in result.stdout
    assert not effect.exists()


def test_repair_loop_health_treats_orphaned_chain_process_as_alive(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".megaplan" / "plans").mkdir(parents=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")

    script = "\n\n".join(
        [
            _extract_repair_function("chain_wait_status"),
            _extract_repair_function("plan_process_is_alive"),
            _extract_repair_function("chain_process_is_alive"),
            _extract_repair_function("session_health_status"),
            f"""
tmux() {{ return 1; }}
ps() {{
  cat <<'EOF'
python3 -P -m arnold_pipelines.megaplan chain start --spec {spec_path} --project-dir {workspace}
EOF
}}
session_health_status demo-session {workspace} {spec_path} chain ""
""",
        ]
    )
    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "alive"


def test_watchdog_health_treats_orphaned_chain_process_as_alive(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".megaplan" / "plans").mkdir(parents=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")

    script = "\n\n".join(
        [
            _extract_wrapper_function("chain_wait_status"),
            _extract_wrapper_function("plan_process_is_alive"),
            _extract_wrapper_function("chain_process_is_alive"),
            _extract_wrapper_function("epic_chain_process_is_alive"),
            _extract_wrapper_function("session_health_status"),
            f"""
tmux() {{ return 1; }}
ps() {{
  cat <<'EOF'
python3 -P -m arnold_pipelines.megaplan chain start --spec {spec_path} --project-dir {workspace}
EOF
}}
session_health_status demo-session {workspace} {spec_path} chain ""
""",
        ]
    )
    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "alive"


def test_watchdog_repair_loop_needs_human_sidecar_short_circuits_relaunch(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    report_path = tmp_path / "report.tsv"
    (repair_data_dir / "demo-session.needs-human.json").write_text(
        json.dumps(
            {
                "summary": "i1 dev=zhipu:glm-5.2 sha=abc mechanical=failed:stopped kimi=failed:bad-creds",
                "repair_data_path": str(repair_data_dir / "demo-session.repair-data.json"),
                "discord_status": "delivered",
            }
        ),
        encoding="utf-8",
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("repair_needs_human_path"),
            _extract_wrapper_function("repair_needs_human_summary"),
            _extract_wrapper_function("repair_needs_human_matches_current_plan"),
            _extract_wrapper_function("workspace_has_other_alive_session"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo stopped; }
plan_attention_status_env() { return 0; }
kimi_operator_running() { return 1; }
mechanical_relaunch_attempted_previously() { return 1; }
kimi_dispatch_failed_previously() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
chain_current_pr_merged() { echo none; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tneeds_human\t" in report
    assert "repair_data=" in report
    assert "discord=delivered" in report
    assert "DISPATCH" not in result.stderr
    assert "TMUX" not in result.stderr


def test_write_needs_human_marker_preserves_legacy_keys_and_adds_current_pointer_fields(tmp_path: Path) -> None:
    data_path = tmp_path / "demo-session.repair-data.json"
    out_path = tmp_path / "demo-session.needs-human.json"
    payload = {
        "session": "demo-session",
        "workspace": "/tmp/workspace",
        "spec": "/tmp/workspace/.megaplan/initiatives/demo/chain.yaml",
        "run_kind": "chain",
        "plan_name": "m2-current-plan",
        "target": {
            "target_id": "demo-session:m2-current-plan",
            "authoritative_source": "marker",
        },
        "current_failure_context": {
            "resolver_output": {
                "target_id": "demo-session:m2-current-plan",
                "authoritative_source": "chain_state",
                "current_refs": {
                    "current_plan_name": "m2-current-plan",
                    "chain_current_plan_name": "m2-current-plan",
                },
            }
        },
        "iterations": [
            {
                "i": 1,
                "dev_model": "gpt-5.5",
                "dev_fix_sha": "abc1234",
                "mechanical_launch": "running",
                "kimi_launch": "failed:bad-creds",
                "why": "blocked by follow-up",
                "chain_state_summary": {"current_plan_name": "m2-current-plan"},
            }
        ],
    }
    data_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_write_needs_human_marker(data_path, out_path)

    assert result.returncode == 0, result.stderr
    marker = json.loads(out_path.read_text(encoding="utf-8"))
    legacy_keys = {
        "session",
        "workspace",
        "spec",
        "plan_name",
        "chain_current_plan_name",
        "summary",
        "repair_data_path",
        "discord_status",
        "recorded_at",
    }
    assert legacy_keys <= set(marker)
    assert marker["session"] == payload["session"]
    assert marker["workspace"] == payload["workspace"]
    assert marker["spec"] == payload["spec"]
    assert marker["plan_name"] == "m2-current-plan"
    assert marker["chain_current_plan_name"] == "m2-current-plan"
    assert marker["repair_data_path"] == str(data_path)
    assert marker["discord_status"] == "delivered"
    assert marker["summary"] == (
        "i1 dev=gpt-5.5 sha=abc1234 mechanical=running kimi=failed:bad-creds why=blocked by follow-up"
    )
    assert marker["current_plan_name"] == "m2-current-plan"
    assert marker["target_id"] == "demo-session:m2-current-plan"
    assert marker["authoritative_source"] == "chain_state"
    assert marker["current"] == {
        "session": "demo-session",
        "workspace": "/tmp/workspace",
        "spec": "/tmp/workspace/.megaplan/initiatives/demo/chain.yaml",
        "repair_data_path": str(data_path),
        "target_id": "demo-session:m2-current-plan",
        "authoritative_source": "chain_state",
        "current_plan_name": "m2-current-plan",
        "chain_current_plan_name": "m2-current-plan",
        "plan_name": "m2-current-plan",
        "run_kind": "chain",
    }


def test_write_needs_human_marker_output_remains_watchdog_reader_compatible(tmp_path: Path) -> None:
    repair_data_dir = tmp_path / "repair-data"
    repair_data_dir.mkdir()
    data_path = repair_data_dir / "demo-session.repair-data.json"
    sidecar_path = repair_data_dir / "demo-session.needs-human.json"
    payload = {
        "session": "demo-session",
        "workspace": str(tmp_path / "ws"),
        "spec": str(tmp_path / "spec.yaml"),
        "plan_name": "m3-current-plan",
        "current_failure_context": {
            "resolver_output": {
                "target_id": "demo-session:m3-current-plan",
                "authoritative_source": "plan_state",
                "current_refs": {
                    "current_plan_name": "m3-current-plan",
                    "chain_current_plan_name": "m3-current-plan",
                },
            }
        },
        "iterations": [
            {
                "i": 1,
                "dev_model": "gpt-5.5",
                "dev_fix_sha": "abc1234",
                "mechanical_launch": "n/a",
                "kimi_launch": "n/a",
                "why": "operator review required",
                "chain_state_summary": {"current_plan_name": "m3-current-plan"},
            }
        ],
    }
    data_path.write_text(json.dumps(payload), encoding="utf-8")
    marker_result = _run_write_needs_human_marker(data_path, sidecar_path, discord_status="queued")
    assert marker_result.returncode == 0, marker_result.stderr

    summary_script = "\n\n".join(
        [
            _extract_wrapper_function("repair_needs_human_path"),
            _extract_wrapper_function("repair_needs_human_summary"),
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            'repair_needs_human_summary "demo-session"',
        ]
    )
    summary_result = _run_watchdog_shell(f"{summary_script}\n", path_prefix=None)
    assert summary_result.returncode == 0, summary_result.stderr
    assert "repair_data=" in summary_result.stdout
    assert "discord=queued" in summary_result.stdout

    matches_script = "\n\n".join(
        [
            _extract_wrapper_function("repair_needs_human_path"),
            _extract_wrapper_function("repair_needs_human_matches_current_plan"),
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            'repair_needs_human_matches_current_plan "demo-session" "m3-current-plan"',
        ]
    )
    matches_result = _run_watchdog_shell(f"{matches_script}\n", path_prefix=None)
    assert matches_result.returncode == 0, matches_result.stderr


def test_write_needs_human_marker_redacts_persisted_summary(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    out_path = tmp_path / "demo-session.needs-human.json"
    payload = {
        "session": "demo-session",
        "workspace": "/tmp/workspace",
        "spec": "/tmp/workspace/.megaplan/initiatives/demo/chain.yaml",
        "plan_name": "m2-current-plan",
        "current_failure_context": {
            "resolver_output": {
                "target_id": "demo-session:m2-current-plan",
                "authoritative_source": "chain_state",
                "current_refs": {
                    "current_plan_name": "m2-current-plan",
                    "chain_current_plan_name": "m2-current-plan",
                },
            }
        },
        "iterations": [
            {
                "i": 1,
                "dev_model": "gpt-5.5",
                "dev_fix_sha": "abc1234",
                "mechanical_launch": "running",
                "kimi_launch": "failed",
                "why": "Authorization: Bearer bearer-secret-token-value",
                "chain_state_summary": {"current_plan_name": "m2-current-plan"},
            }
        ],
    }
    data_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_write_needs_human_marker(data_path, out_path)

    assert result.returncode == 0, result.stderr
    marker = json.loads(out_path.read_text(encoding="utf-8"))
    assert "bearer-secret-token-value" not in marker["summary"]
    assert marker["summary"].endswith(f"why=Authorization: Bearer {REDACTION}")






def test_watchdog_checks_terminal_status_before_current_needs_human() -> None:
    text = _wrapper("arnold-watchdog")
    launch_start = text.index("launch_chain_tick() {")
    sidecar_check = text.index("emit_current_needs_human_sidecar", launch_start)
    terminal_check = text.index("session_terminal_status", launch_start)

    assert terminal_check < sidecar_check


def test_watchdog_checks_plan_status_terminal_done_before_current_needs_human() -> None:
    text = _wrapper("arnold-watchdog")
    plan_status_eval = text.index('eval "$plan_status_env"')
    complete_check = text.index('PLAN_STATUS_CURRENT_STATE:-}" == "done"', plan_status_eval)
    sidecar_check = text.index("emit_current_needs_human_sidecar", plan_status_eval)

    assert complete_check < sidecar_check


def test_watchdog_current_needs_human_sidecar_reports_every_tick_without_renotify(tmp_path: Path) -> None:
    report_path = tmp_path / "items.jsonl"
    repair_data_dir = tmp_path / "repair-data"
    repair_data_dir.mkdir()
    marker_path = repair_data_dir / "demo-session.needs-human.json"
    marker_path.write_text(
        json.dumps(
            {
                "session": "demo-session",
                "summary": "repair loop exhausted",
                "current_plan_name": "m6-current-plan",
                "discord_status": "delivered",
            }
        ),
        encoding="utf-8",
    )
    script = "\n\n".join(
        [
            "LOG=/dev/null",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            "log() { :; }",
            "compare_needs_human_to_resolver() { :; }",
            _extract_wrapper_function_until("report_item", "plan_attention_status_env"),
            _extract_wrapper_function("repair_needs_human_path"),
            _extract_wrapper_function("repair_needs_human_summary"),
            _extract_wrapper_function("repair_needs_human_matches_current_plan"),
            _extract_wrapper_function("emit_current_needs_human_sidecar"),
            f"emit_current_needs_human_sidecar {str(report_path)!r} demo-session /tmp/ws /tmp/spec m6-current-plan",
            f"emit_current_needs_human_sidecar {str(report_path)!r} demo-session /tmp/ws /tmp/spec m6-current-plan",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    lines = [json.loads(line) for line in report_path.read_text(encoding="utf-8").splitlines()]
    assert [item["status"] for item in lines] == ["needs_human", "needs_human"]
    assert all(item["action"] == "observe" for item in lines)
    assert all("repair loop exhausted" in item["message"] for item in lines)
    assert all(item["status"] not in {"discord_dm_sent", "webhook_sent"} for item in lines)


def test_watchdog_report_item_redacts_persisted_lines(tmp_path: Path) -> None:
    items_path = tmp_path / "items.jsonl"
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("report_item", "plan_attention_status_env"),
            (
                f"report_item {str(items_path)!r} demo-session observe needs_human "
                "'Authorization: Bearer bearer-secret-token-value' /tmp/ws demo-spec"
            ),
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    payload = json.loads(items_path.read_text(encoding="utf-8").strip())
    assert payload["message"] == f"Authorization: Bearer {REDACTION}"


def test_watchdog_emit_report_redacts_persisted_report_json(tmp_path: Path) -> None:
    items_path = tmp_path / "items.jsonl"
    items_path.write_text(
        json.dumps(
            {
                "session": "demo-session",
                "action": "observe",
                "status": "needs_human",
                "message": "Authorization: Bearer bearer-secret-token-value",
                "workspace": "/tmp/ws",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report_path = tmp_path / "watchdog-report.json"
    archive_dir = tmp_path / "archive"
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("emit_report", "sync_cloud_runtime_wrappers"),
            f"REPORT_PATH={str(report_path)!r}",
            f"REPORT_ARCHIVE_DIR={str(archive_dir)!r}",
            'emit_report ' + shlex.quote(str(items_path)) + " 1",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["items"][0]["message"] == f"Authorization: Bearer {REDACTION}"
    assert payload["issues"][0]["message"] == f"Authorization: Bearer {REDACTION}"


def test_watchdog_clears_stale_parent_sidecar_when_child_session_alive(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    parent_spec = workspace / ".megaplan" / "initiatives" / "demo" / "assets" / "epic-chain.yaml"
    child_spec = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    parent_spec.parent.mkdir(parents=True)
    child_spec.parent.mkdir(parents=True, exist_ok=True)
    parent_spec.write_text("chains: []\n", encoding="utf-8")
    child_spec.write_text("milestones: []\n", encoding="utf-8")
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"
    sidecar_path = repair_data_dir / "parent-session.needs-human.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "summary": "old parent repair exhaustion",
                "repair_data_path": str(repair_data_dir / "parent-session.repair-data.json"),
                "discord_status": "delivered",
            }
        ),
        encoding="utf-8",
    )
    (marker_dir / "child-session.json").write_text(
        json.dumps(
            {
                "session": "child-session",
                "workspace": str(workspace),
                "remote_spec": str(child_spec),
                "run_kind": "chain",
            }
        ),
        encoding="utf-8",
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("repair_needs_human_path"),
            _extract_wrapper_function("repair_needs_human_summary"),
            _extract_wrapper_function("repair_needs_human_matches_current_plan"),
            _extract_wrapper_function("workspace_has_other_alive_session"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() {
  if [[ "$1" == "child-session" ]]; then
    echo alive
  else
    echo stopped
  fi
}
plan_attention_status_env() { return 0; }
chain_health_status() {
  CHAIN_HEALTH_STATUS=ok
  CHAIN_HEALTH_SUMMARY=
  CHAIN_HEALTH_ARTIFACT_PATH=
  CHAIN_HEALTH_LOG_MESSAGE=
}
chain_current_pr_merged() { echo none; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
mechanical_relaunch_attempted_previously() { return 0; }
kimi_dispatch_failed_previously() { return 1; }
kimi_dispatch_marker_set() { :; }
kimi_dispatch_marker_clear() { :; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick parent-session {str(workspace)!r} {str(parent_spec)!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    log = log_path.read_text(encoding="utf-8")
    assert "\tobserve\tneeds_human\told parent repair exhaustion" not in report
    assert "\tobserve\tsuperseded\tlive sibling session owns workspace: child-session:alive\t" in report
    assert "stale repair needs-human marker cleared; sibling session is alive" in log
    assert "stopped session superseded by live sibling" in log
    assert not sidecar_path.exists()
    assert "DISPATCH" not in result.stderr


def test_watchdog_clears_stale_needs_human_sidecar_for_superseded_plan(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "m3-current-plan"
    old_plan_name = "m1-old-plan"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    _write_chain_state(
        workspace / ".megaplan" / "plans" / ".chains" / f"chain-{digest}.json",
        {"current_plan_name": plan_name, "last_state": "awaiting_human"},
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "name": plan_name,
            "current_state": "awaiting_human",
            "latest_failure": {
                "kind": "blocked_by_prereq",
                "message": "execute reported blocked tasks awaiting user action: T1",
            },
        },
        events_body="{}\n",
    )
    repair_data_path = repair_data_dir / "demo-session.repair-data.json"
    repair_data_path.write_text(
        json.dumps(
            {
                "session": "demo-session",
                "iterations": [
                    {
                        "i": 1,
                        "chain_state_summary": {"current_plan_name": old_plan_name},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    sidecar_path = repair_data_dir / "demo-session.needs-human.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "summary": "old repair exhaustion",
                "repair_data_path": str(repair_data_path),
                "chain_current_plan_name": old_plan_name,
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("repair_needs_human_path"),
            _extract_wrapper_function("repair_needs_human_summary"),
            _extract_wrapper_function("repair_needs_human_matches_current_plan"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
chain_health_status() {
  CHAIN_HEALTH_STATUS=ok
  CHAIN_HEALTH_SUMMARY=
  CHAIN_HEALTH_ARTIFACT_PATH=
  CHAIN_HEALTH_LOG_MESSAGE=
}
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    log = log_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\tawaiting_human repair loop dispatched before needs_human\t" in report
    assert "\tobserve\tneeds_human\told repair exhaustion" not in report
    assert "stale repair needs-human marker cleared" in log
    assert not sidecar_path.exists()
    assert "DISPATCH" in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr


def test_watchdog_logs_needs_human_comparison_agreement(tmp_path: Path) -> None:
    """Resolver-backed comparison diagnostic is logged without altering legacy behavior."""
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "m3-current-plan"
    old_plan_name = "m1-old-plan"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    _write_chain_state(
        workspace / ".megaplan" / "plans" / ".chains" / f"chain-{digest}.json",
        {"current_plan_name": plan_name, "last_state": "awaiting_human"},
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "name": plan_name,
            "current_state": "awaiting_human",
            "latest_failure": {
                "kind": "blocked_by_prereq",
                "message": "execute reported blocked tasks awaiting user action: T1",
            },
        },
        events_body="{}\n",
    )
    repair_data_path = repair_data_dir / "demo-session.repair-data.json"
    repair_data_path.write_text(
        json.dumps(
            {
                "session": "demo-session",
                "iterations": [
                    {"i": 1, "chain_state_summary": {"current_plan_name": old_plan_name}}
                ],
            }
        ),
        encoding="utf-8",
    )
    sidecar_path = repair_data_dir / "demo-session.needs-human.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "summary": "old repair exhaustion",
                "repair_data_path": str(repair_data_path),
                "chain_current_plan_name": old_plan_name,
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("repair_needs_human_path"),
            _extract_wrapper_function("repair_needs_human_summary"),
            _extract_wrapper_function("repair_needs_human_matches_current_plan"),
            _extract_wrapper_function("compare_needs_human_to_resolver"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
chain_health_status() {
  CHAIN_HEALTH_STATUS=ok
  CHAIN_HEALTH_SUMMARY=
  CHAIN_HEALTH_ARTIFACT_PATH=
  CHAIN_HEALTH_LOG_MESSAGE=
}
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    log = log_path.read_text(encoding="utf-8")
    report = report_path.read_text(encoding="utf-8")
    # Legacy clears the stale sidecar (old plan != current plan)
    assert "stale repair needs-human marker cleared" in log
    assert not sidecar_path.exists()
    # Comparison diagnostic is logged
    assert "AGREEMENT needs_human_comparison" in log or "DISCREPANCY needs_human_comparison" in log
    # Legacy behavior is authoritative: sidecar cleared, dispatch proceeds
    assert "\trepair\trepair_dispatched\tawaiting_human repair loop dispatched before needs_human\t" in report
    assert "\tobserve\tneeds_human\told repair exhaustion" not in report


def test_watchdog_comparison_diagnostic_does_not_alter_stale_clear(tmp_path: Path) -> None:
    """Resolver diagnostic logged even when needs-human sidecar kept (plan match)."""
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "m3-current-plan"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    _write_chain_state(
        workspace / ".megaplan" / "plans" / ".chains" / f"chain-{digest}.json",
        {"current_plan_name": plan_name, "last_state": "awaiting_human"},
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "name": plan_name,
            "current_state": "awaiting_human",
            "latest_failure": {
                "kind": "blocked_by_prereq",
                "message": "execute reported blocked tasks awaiting user action: T1",
            },
        },
        events_body="{}\n",
    )
    repair_data_path = repair_data_dir / "demo-session.repair-data.json"
    repair_data_path.write_text(
        json.dumps(
            {
                "session": "demo-session",
                "iterations": [
                    {"i": 1, "chain_state_summary": {"current_plan_name": plan_name}}
                ],
            }
        ),
        encoding="utf-8",
    )
    sidecar_path = repair_data_dir / "demo-session.needs-human.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "summary": "repair exhausted for current plan",
                "repair_data_path": str(repair_data_path),
                "chain_current_plan_name": plan_name,
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("repair_needs_human_path"),
            _extract_wrapper_function("repair_needs_human_summary"),
            _extract_wrapper_function("repair_needs_human_matches_current_plan"),
            _extract_wrapper_function("compare_needs_human_to_resolver"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
chain_health_status() {
  CHAIN_HEALTH_STATUS=ok
  CHAIN_HEALTH_SUMMARY=
  CHAIN_HEALTH_ARTIFACT_PATH=
  CHAIN_HEALTH_LOG_MESSAGE=
}
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    log = log_path.read_text(encoding="utf-8")
    # Comparison diagnostic is logged
    assert "AGREEMENT needs_human_comparison" in log or "DISCREPANCY needs_human_comparison" in log
    # Legacy behavior is authoritative: sidecar kept (plan matches), needs_human reported
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tneeds_human\t" in report
    assert sidecar_path.exists()


def _prepare_meta_repair_launch_chain_tick_fixture(
    tmp_path: Path,
    *,
    payload_overrides: dict[str, object] | None = None,
    partial_liveness_ticks: int = 0,
    discord_status: str | None = None,
    true_blocker_plan: str | None = None,
) -> dict[str, Path]:
    marker_dir = tmp_path / "markers"
    repair_data_dir = tmp_path / "repair-data"
    workspace = tmp_path / "ws"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")

    payload: dict[str, object] = {
        "session": "demo-session",
        "workspace": str(workspace),
        "spec": str(spec_path),
        "run_kind": "chain",
        "plan_name": true_blocker_plan or "demo-plan",
        "outcome": "repairing",
        "attempts": [],
        "iterations": [],
        "current_failure_context": {},
        "discord_escalation": {},
    }
    if payload_overrides:
        payload.update(payload_overrides)

    repair_data_path = repair_data_dir / "demo-session.repair-data.json"
    repair_data_path.write_text(json.dumps(payload), encoding="utf-8")
    (marker_dir / "demo-session.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "workspace": str(workspace),
                "remote_spec": str(spec_path),
                "run_kind": "chain",
                "plan_name": payload["plan_name"],
            }
        ),
        encoding="utf-8",
    )

    if partial_liveness_ticks:
        events_dir = tmp_path / "repair-data.d" / "events"
        events_dir.mkdir(parents=True)
        records = [
            {
                "session": "demo-session",
                "outcome": "partial_liveness",
                "health": "alive",
                "recorded_at": f"2026-07-02T00:00:0{i}Z",
                "run_kind": "chain",
                "plan_name": payload["plan_name"],
            }
            for i in range(partial_liveness_ticks)
        ]
        (events_dir / "events.jsonl").write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )

    if discord_status is not None:
        plan_name = str(payload.get("plan_name") or "")
        digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
        _write_chain_state(
            workspace / ".megaplan" / "plans" / ".chains" / f"chain-{digest}.json",
            {"current_plan_name": plan_name, "last_state": "awaiting_human"},
        )
        _write_plan(
            workspace / ".megaplan" / "plans" / plan_name,
            {
                "name": plan_name,
                "current_state": "awaiting_human",
                "latest_failure": {
                    "kind": "blocked_by_prereq",
                    "message": "awaiting human decision",
                },
            },
            events_body="{}\n",
        )
        escalations_dir = tmp_path / "repair-data.d" / "escalations"
        escalations_dir.mkdir(parents=True, exist_ok=True)
        escalation_id = "esc-001"
        records = [
            {
                "session": "demo-session",
                "event": "opened",
                "escalation_id": escalation_id,
                "current_plan": plan_name,
                "target_id": f"demo-session:{plan_name}",
                "blocker_verdict": "TRUE_BLOCKER" if true_blocker_plan else "AMBIGUOUS_BLOCKER",
                "authoritative_source": "chain_state",
            }
        ]
        if discord_status == "delivered":
            records.append(
                {
                    "session": "demo-session",
                    "event": "delivered",
                    "escalation_id": escalation_id,
                    "message_count": 1,
                }
            )
        else:
            records.append(
                {
                    "session": "demo-session",
                    "event": "unavailable",
                    "escalation_id": escalation_id,
                    "reason": discord_status,
                }
            )
        (escalations_dir / "escalations.jsonl").write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )

    return {
        "marker_dir": marker_dir,
        "repair_data_dir": repair_data_dir,
        "workspace": workspace,
        "spec_path": spec_path,
        "report_path": report_path,
        "log_path": log_path,
    }


def _run_launch_chain_tick_meta_repair_script(paths: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    script = "\n\n".join(
        [
            _extract_wrapper_function("json_field"),
            _extract_wrapper_function_until("compute_meta_repair_trigger", "dispatch_meta_repair"),
            _extract_wrapper_function_until("write_partial_liveness_tick", "clear_session_tracking_artifacts"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(paths['marker_dir'])!r}",
            f"REPAIR_DATA_DIR={str(paths['repair_data_dir'])!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"LOG={str(paths['log_path'])!r}",
            """
report_item() {
  printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\\n' "$*" >> "$LOG"; }
plan_attention_status_env() { return 0; }
plan_terminal_status() { return 1; }
emit_current_needs_human_sidecar() { return 1; }
emit_watchdog_incident_bridge_event() { :; }
repair_needs_human_path() { printf '%s\\n' "$REPAIR_DATA_DIR/$1.needs-human.json"; }
session_health_status() { echo "${WATCHDOG_TEST_HEALTH:-dead}"; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
chain_health_status() {
  CHAIN_HEALTH_STATUS=ok
  CHAIN_HEALTH_SUMMARY=
  CHAIN_HEALTH_ARTIFACT_PATH=
  CHAIN_HEALTH_LOG_MESSAGE=
}
repair_loop_busy_state() { echo none; }
repair_unhealthy_session() { echo REPAIR >&2; return 1; }
dispatch_meta_repair() { echo META_DISPATCH >&2; REPAIR_DISPATCH_RESULT=dispatched; return 0; }
dispatch_kimi_repair() { echo SHOULD_NOT_DISPATCH_KIMI >&2; return 0; }
mechanical_relaunch_attempted_previously() { return 0; }
kimi_dispatch_failed_previously() { return 1; }
kimi_dispatch_marker_set() { :; }
kimi_dispatch_marker_clear() { :; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo "echo relaunched"; }
safe_name() { printf '%s\\n' "$1"; }
tmux() {
  if [[ "${1:-}" == "has-session" ]]; then
    return 1
  fi
  echo "TMUX $*" >&2
  return 0
}
""".strip(),
            (
                f"launch_chain_tick demo-session {str(paths['workspace'])!r} "
                f"{str(paths['spec_path'])!r} {str(paths['report_path'])!r} chain '' ''"
            ),
        ]
    )
    return _run_watchdog_shell(script)


def test_launch_chain_tick_dispatches_meta_repair_on_timeout_trigger(tmp_path: Path) -> None:
    paths = _prepare_meta_repair_launch_chain_tick_fixture(
        tmp_path,
        payload_overrides={"outcome": "repair_timeout"},
    )
    result = _run_launch_chain_tick_meta_repair_script(paths)
    assert result.returncode == 0, result.stderr
    assert "META_DISPATCH" in result.stderr
    assert "TMUX" not in result.stderr
    assert "trigger=repair_timeout" in paths["log_path"].read_text(encoding="utf-8")


def test_launch_chain_tick_dispatches_meta_repair_on_recurring_retry_trigger(tmp_path: Path) -> None:
    paths = _prepare_meta_repair_launch_chain_tick_fixture(
        tmp_path,
        payload_overrides={
            "attempts": [
                {"attempt_id": 1, "failure_classification": "phase_failed"},
                {"attempt_id": 2, "failure_classification": "phase_failed"},
                {"attempt_id": 3, "failure_classification": "phase_failed"},
            ],
        },
    )
    result = _run_launch_chain_tick_meta_repair_script(paths)
    assert result.returncode == 0, result.stderr
    assert "META_DISPATCH" in result.stderr
    assert "TMUX" not in result.stderr
    assert "trigger=persistent_recurring_retry" in paths["log_path"].read_text(encoding="utf-8")


def test_launch_chain_tick_dispatches_meta_repair_on_recurring_retry_when_stopped(tmp_path: Path) -> None:
    paths = _prepare_meta_repair_launch_chain_tick_fixture(
        tmp_path,
        payload_overrides={
            "attempts": [
                {"attempt_id": 1, "failure_classification": "phase_failed"},
                {"attempt_id": 2, "failure_classification": "phase_failed"},
                {"attempt_id": 3, "failure_classification": "phase_failed"},
            ],
        },
    )
    script = "\n\n".join(
        [
            f"WATCHDOG_TEST_HEALTH={shlex.quote('stopped')}",
            _extract_wrapper_function("json_field"),
            _extract_wrapper_function_until("compute_meta_repair_trigger", "dispatch_meta_repair"),
            _extract_wrapper_function_until("write_partial_liveness_tick", "clear_session_tracking_artifacts"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(paths['marker_dir'])!r}",
            f"REPAIR_DATA_DIR={str(paths['repair_data_dir'])!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"LOG={str(paths['log_path'])!r}",
            """
report_item() {
  printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\\n' "$*" >> "$LOG"; }
plan_attention_status_env() { return 0; }
plan_terminal_status() { return 1; }
repair_needs_human_path() { printf '%s\\n' "$REPAIR_DATA_DIR/$1.needs-human.json"; }
session_health_status() { echo "${WATCHDOG_TEST_HEALTH:-dead}"; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
chain_health_status() {
  CHAIN_HEALTH_STATUS=ok
  CHAIN_HEALTH_SUMMARY=
  CHAIN_HEALTH_ARTIFACT_PATH=
  CHAIN_HEALTH_LOG_MESSAGE=
}
repair_loop_busy_state() { echo none; }
repair_unhealthy_session() { echo SHOULD_NOT_REPAIR_UNHEALTHY >&2; return 1; }
dispatch_meta_repair() { echo META_DISPATCH >&2; REPAIR_DISPATCH_RESULT=dispatched; return 0; }
dispatch_kimi_repair() { echo SHOULD_NOT_DISPATCH_KIMI >&2; return 0; }
mechanical_relaunch_attempted_previously() { return 0; }
kimi_dispatch_failed_previously() { return 1; }
kimi_dispatch_marker_set() { :; }
kimi_dispatch_marker_clear() { :; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo "echo relaunched"; }
safe_name() { printf '%s\\n' "$1"; }
tmux() {
  if [[ "${1:-}" == "has-session" ]]; then
    return 1
  fi
  echo "TMUX $*" >&2
  return 0
}
""".strip(),
            (
                f"launch_chain_tick demo-session {str(paths['workspace'])!r} "
                f"{str(paths['spec_path'])!r} {str(paths['report_path'])!r} chain '' ''"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert "META_DISPATCH" in result.stderr
    assert "TMUX" not in result.stderr
    assert "session stopped after repair failure; meta-repair background-dispatched" in paths["log_path"].read_text(
        encoding="utf-8"
    )
    assert "trigger=persistent_recurring_retry" in paths["log_path"].read_text(encoding="utf-8")


def test_launch_chain_tick_dispatches_meta_repair_on_state_inspection_trigger(tmp_path: Path) -> None:
    paths = _prepare_meta_repair_launch_chain_tick_fixture(
        tmp_path,
        payload_overrides={
            "current_failure_context": {
                "state_probe": "failed:state_unreadable: malformed state.json",
            }
        },
    )
    result = _run_launch_chain_tick_meta_repair_script(paths)
    assert result.returncode == 0, result.stderr
    assert "META_DISPATCH" in result.stderr
    assert "TMUX" not in result.stderr
    assert "trigger=state_inspection_failure" in paths["log_path"].read_text(encoding="utf-8")


def test_launch_chain_tick_dispatches_meta_repair_on_model_launch_trigger(tmp_path: Path) -> None:
    paths = _prepare_meta_repair_launch_chain_tick_fixture(
        tmp_path,
        payload_overrides={
            "attempts": [
                {"attempt_id": 1, "mechanical_launch": "failed:tmux_launch_failed"},
            ],
        },
    )
    result = _run_launch_chain_tick_meta_repair_script(paths)
    assert result.returncode == 0, result.stderr
    assert "META_DISPATCH" in result.stderr
    assert "TMUX" not in result.stderr
    assert "trigger=model_tool_launch_failure" in paths["log_path"].read_text(encoding="utf-8")


def test_launch_chain_tick_dispatches_meta_repair_on_l1_context_custody_failure(
    tmp_path: Path,
) -> None:
    paths = _prepare_meta_repair_launch_chain_tick_fixture(
        tmp_path,
        payload_overrides={
            "outcome": "fixer_infrastructure_failure",
            "investigation": {
                "status": "failed",
                "failure_phase": "context_construction",
                "reason": "bounded repair investigation context construction failed",
            },
        },
    )
    result = _run_launch_chain_tick_meta_repair_script(paths)
    assert result.returncode == 0, result.stderr
    assert "META_DISPATCH" in result.stderr
    assert "TMUX" not in result.stderr
    assert "trigger=l1_custody_failure" in paths["log_path"].read_text(encoding="utf-8")


def test_launch_chain_tick_does_not_treat_stopped_health_as_model_launch_failure(tmp_path: Path) -> None:
    paths = _prepare_meta_repair_launch_chain_tick_fixture(
        tmp_path,
        payload_overrides={
            "attempts": [
                {
                    "attempt_id": 1,
                    "mechanical_launch": "failed:stopped",
                    "failure_classification": "blocked_state_or_recovery_error",
                },
            ],
        },
    )
    result = _run_launch_chain_tick_meta_repair_script(paths)
    assert result.returncode == 0, result.stderr
    assert "META_DISPATCH" not in result.stderr
    assert "TMUX new-session" in result.stderr


def test_compute_meta_repair_trigger_skips_stale_launch_failure_after_success(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    repair_data_dir.mkdir(parents=True)
    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "outcome": "live_with_fresh_activity",
                "attempts": [
                    {"attempt_id": 1, "mechanical_launch": "failed:tmux_launch_failed"},
                ],
            }
        ),
        encoding="utf-8",
    )
    observation = json.dumps(
        {
            "authoritative_source": "chain_state",
            "current_refs": {
                "current_plan_name": "demo-plan",
                "chain_current_plan_name": "demo-plan",
                "plan_current_state": "initialized",
                "chain_last_state": "initialized",
            },
            "plan_state": {"present": True},
            "chain_state": {"present": True},
            "active_step_heartbeat": {"active": False},
        }
    )
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("compute_meta_repair_trigger", "dispatch_meta_repair"),
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"MARKER_DIR={str(marker_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            (
                f"compute_meta_repair_trigger demo-session "
                f"{shlex.quote(observation)} alive"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "NO_TRIGGER"


def test_compute_meta_repair_trigger_detects_semantic_fingerprint_recurrence(
    tmp_path: Path,
) -> None:
    """3 unchanged semantic fingerprints should trigger persistent_recurring_retry."""
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    repair_data_dir.mkdir(parents=True)
    unchanged_fp = "abc123def456"  # stable fingerprint across attempts
    (repair_data_dir / "fp-session.repair-data.json").write_text(
        json.dumps(
            {
                "session": "fp-session",
                "outcome": "repairing",
                "initial_facts": {
                    "semantic_health": {"fingerprint": unchanged_fp}
                },
                "attempts": [
                    {
                        "attempt_id": 1,
                        "failure_classification": "semantic_boundary_violation",
                        "failure_context": {
                            "semantic_health": {"fingerprint": unchanged_fp}
                        },
                    },
                    {
                        "attempt_id": 2,
                        "failure_classification": "semantic_boundary_violation",
                        "failure_context": {
                            "semantic_health": {"fingerprint": unchanged_fp}
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    observation = json.dumps(
        {
            "authoritative_source": "chain_state",
            "current_refs": {
                "current_plan_name": "fp-plan",
                "chain_current_plan_name": "fp-plan",
                "plan_current_state": "initialized",
                "chain_last_state": "initialized",
            },
            "plan_state": {"present": True},
            "chain_state": {"present": True},
            "active_step_heartbeat": {"active": False},
        }
    )
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("compute_meta_repair_trigger", "dispatch_meta_repair"),
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"MARKER_DIR={str(marker_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            (
                f"compute_meta_repair_trigger fp-session "
                f"{shlex.quote(observation)} stopped"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "TRIGGER:persistent_recurring_retry"


def test_compute_meta_repair_trigger_skips_when_semantic_fingerprint_changes(
    tmp_path: Path,
) -> None:
    """Changed semantic fingerprints should NOT trigger persistent_recurring_retry on fingerprint recurrence alone."""
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    repair_data_dir.mkdir(parents=True)
    (repair_data_dir / "fp-chg-session.repair-data.json").write_text(
        json.dumps(
            {
                "session": "fp-chg-session",
                "outcome": "repairing",
                "initial_facts": {
                    "semantic_health": {"fingerprint": "fp_v3_different"}
                },
                "attempts": [
                    {
                        "attempt_id": 1,
                        "failure_classification": "semantic_boundary_violation",
                        "failure_context": {
                            "semantic_health": {"fingerprint": "fp_v1_old"}
                        },
                    },
                    {
                        "attempt_id": 2,
                        "failure_classification": "semantic_boundary_violation",
                        "failure_context": {
                            "semantic_health": {"fingerprint": "fp_v2_changed"}
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    observation = json.dumps(
        {
            "authoritative_source": "chain_state",
            "current_refs": {
                "current_plan_name": "fp-chg-plan",
                "chain_current_plan_name": "fp-chg-plan",
                "plan_current_state": "initialized",
                "chain_last_state": "initialized",
            },
            "plan_state": {"present": True},
            "chain_state": {"present": True},
            "active_step_heartbeat": {"active": False},
        }
    )
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("compute_meta_repair_trigger", "dispatch_meta_repair"),
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"MARKER_DIR={str(marker_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            (
                f"compute_meta_repair_trigger fp-chg-session "
                f"{shlex.quote(observation)} stopped"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    # Changed fingerprints: no fingerprint recurrence; failure_kinds only has
    # 2 entries (< 3 threshold) so overall trigger should be NO_TRIGGER.
    assert result.stdout.strip() == "NO_TRIGGER"


def test_launch_chain_tick_dispatches_meta_repair_on_partial_liveness_trigger(tmp_path: Path) -> None:
    paths = _prepare_meta_repair_launch_chain_tick_fixture(
        tmp_path,
        partial_liveness_ticks=2,
    )
    result = _run_launch_chain_tick_meta_repair_script(paths)
    assert result.returncode == 0, result.stderr
    assert "META_DISPATCH" in result.stderr
    assert "TMUX" not in result.stderr
    assert "trigger=partial_liveness_recurrence" in paths["log_path"].read_text(encoding="utf-8")


def test_launch_chain_tick_dispatches_meta_repair_while_session_alive(tmp_path: Path) -> None:
    paths = _prepare_meta_repair_launch_chain_tick_fixture(
        tmp_path,
        payload_overrides={"outcome": "repair_exhausted"},
    )
    result = _run_watchdog_shell(
        "\n\n".join(
                [
                    _extract_wrapper_function("json_field"),
                    _extract_wrapper_function_until("compute_meta_repair_trigger", "dispatch_meta_repair"),
                    _extract_wrapper_function_until("write_partial_liveness_tick", "clear_session_tracking_artifacts"),
                    _extract_wrapper_function("launch_chain_tick"),
                f"MARKER_DIR={str(paths['marker_dir'])!r}",
                f"REPAIR_DATA_DIR={str(paths['repair_data_dir'])!r}",
                f"SRC_DIR={str(REPO_ROOT)!r}",
                f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
                f"LOG={str(paths['log_path'])!r}",
                """
report_item() {
  printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\\n' "$*" >> "$LOG"; }
plan_attention_status_env() { return 0; }
plan_terminal_status() { return 1; }
repair_needs_human_path() { printf '%s\\n' "$REPAIR_DATA_DIR/$1.needs-human.json"; }
session_health_status() { echo alive; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
chain_health_status() {
  CHAIN_HEALTH_STATUS=ok
  CHAIN_HEALTH_SUMMARY=
  CHAIN_HEALTH_ARTIFACT_PATH=
  CHAIN_HEALTH_LOG_MESSAGE=
}
repair_loop_busy_state() { echo none; }
repair_unhealthy_session() { echo SHOULD_NOT_REPAIR_UNHEALTHY >&2; return 1; }
dispatch_meta_repair() { echo META_DISPATCH >&2; REPAIR_DISPATCH_RESULT=dispatched; return 0; }
dispatch_kimi_repair() { echo SHOULD_NOT_DISPATCH_KIMI >&2; return 0; }
kimi_dispatch_marker_set() { :; }
kimi_dispatch_marker_clear() { :; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo "echo relaunched"; }
safe_name() { printf '%s\\n' "$1"; }
tmux() {
  if [[ "${1:-}" == "has-session" ]]; then
    return 1
  fi
  echo "TMUX $*" >&2
  return 0
}
""".strip(),
                (
                    f"launch_chain_tick demo-session {str(paths['workspace'])!r} "
                    f"{str(paths['spec_path'])!r} {str(paths['report_path'])!r} chain '' ''"
                ),
            ]
        )
    )
    assert result.returncode == 0, result.stderr
    assert "META_DISPATCH" in result.stderr
    assert "TMUX" not in result.stderr
    assert "session alive after repair failure; meta-repair background-dispatched" in paths["log_path"].read_text(encoding="utf-8")
    events_path = paths["repair_data_dir"].with_name("repair-data.d") / "events" / "events.jsonl"
    assert not events_path.exists(), "alive-path meta dispatch should short-circuit before writing partial liveness"


def test_compute_meta_repair_trigger_skips_stale_timeout_when_alive_has_heartbeat(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    repair_data_dir.mkdir(parents=True)
    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps({"session": "demo-session", "outcome": "repair_exhausted"}),
        encoding="utf-8",
    )
    observation = json.dumps(
        {
            "authoritative_source": "chain_state",
            "active_step_heartbeat": {
                "active": True,
                "phase": "review",
                "started_at": "2026-07-04T02:31:43Z",
            },
            "current_refs": {
                "current_plan_name": "m3b-live-binding-and-20260703-2358",
            },
        }
    )
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("compute_meta_repair_trigger", "dispatch_meta_repair"),
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"MARKER_DIR={str(marker_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            (
                f"compute_meta_repair_trigger demo-session "
                f"{shlex.quote(observation)} alive"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "NO_TRIGGER"


def test_compute_meta_repair_trigger_skips_stale_recurring_retry_after_plan_recovered(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    repair_data_dir.mkdir(parents=True)
    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "outcome": "running",
                "current_signature": {
                    "milestone_or_plan": "demo-plan",
                    "current_state": "blocked",
                },
                "attempts": [
                    {"failure_classification": "execution_blocked", "outcome": "running"},
                    {"failure_classification": "execution_blocked", "outcome": "running"},
                    {"failure_classification": "execution_blocked", "outcome": "running"},
                ],
            }
        ),
        encoding="utf-8",
    )
    observation = json.dumps(
        {
            "authoritative_source": "chain_state",
            "active_step_heartbeat": {"active": False},
            "current_refs": {
                "current_plan_name": "demo-plan",
                "chain_current_plan_name": "demo-plan",
                "plan_current_state": "finalized",
                "chain_last_state": "finalized",
            },
            "plan_state": {"present": True},
            "chain_state": {"present": True},
        }
    )
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("compute_meta_repair_trigger", "dispatch_meta_repair"),
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"MARKER_DIR={str(marker_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            (
                f"compute_meta_repair_trigger demo-session "
                f"{shlex.quote(observation)} stopped"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "NO_TRIGGER"


def test_marker_requires_repair_despite_alive_ignores_stale_failure_after_finalized_recovery(
    tmp_path: Path,
) -> None:
    marker_path = tmp_path / "demo-session.json"
    data_path = tmp_path / "demo-session.repair-data.json"
    marker_path.write_text(json.dumps({"session": "demo-session"}), encoding="utf-8")
    data_path.write_text(
        json.dumps(
            {
                "current_signature": {
                    "milestone_or_plan": "demo-plan",
                    "current_state": "finalized",
                },
                "current_advancement_snapshot": {
                    "milestone_or_plan": "demo-plan",
                    "current_state": "finalized",
                },
                "current_failure_context": {
                    "plan_latest_failure": {
                        "kind": "execution_blocked",
                        "current_state": "blocked",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    script = "\n\n".join(
        [
            _extract_repair_function("marker_requires_repair_despite_alive"),
            f"MARKER_PATH={str(marker_path)!r}",
            f"DATA_FILE={str(data_path)!r}",
            "marker_requires_repair_despite_alive || true",
        ]
    )
    result = _run_watchdog_shell(script, path_prefix=None)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_compute_meta_repair_trigger_skips_recurring_retry_when_session_alive(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    repair_data_dir.mkdir(parents=True)
    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "outcome": "repairing",
                "attempts": [
                    {"attempt_id": 1, "failure_classification": "phase_failed"},
                    {"attempt_id": 2, "failure_classification": "phase_failed"},
                    {"attempt_id": 3, "failure_classification": "phase_failed"},
                ],
            }
        ),
        encoding="utf-8",
    )
    observation = json.dumps(
        {
            "authoritative_source": "chain_state",
            "current_refs": {
                "current_plan_name": "m4-clip-type-shader-and-20260704-0427",
                "chain_last_state": "finalized",
                "plan_current_state": "finalized",
            },
            "plan_state": {
                "present": True,
                "current_state": "finalized",
            },
            "chain_state": {
                "present": True,
                "last_state": "finalized",
            },
            "active_step_heartbeat": {
                "active": False,
            },
        }
    )
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("compute_meta_repair_trigger", "dispatch_meta_repair"),
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"MARKER_DIR={str(marker_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            (
                f"compute_meta_repair_trigger demo-session "
                f"{shlex.quote(observation)} alive"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "NO_TRIGGER"


def test_compute_meta_repair_trigger_allows_recurring_retry_after_exhausted_repair_handoff(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    repair_data_dir.mkdir(parents=True)
    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "outcome": "discord_escalated",
                "attempts": [
                    {"attempt_id": 1, "failure_classification": "timeout_or_hang"},
                    {"attempt_id": 2, "failure_classification": "timeout_or_hang"},
                    {"attempt_id": 3, "failure_classification": "timeout_or_hang"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (repair_data_dir / "demo-session.needs-human.json").write_text(
        json.dumps(
            {
                "current_plan_name": "demo-plan",
                "discord_status": "delivered",
            }
        ),
        encoding="utf-8",
    )
    observation = json.dumps(
        {
            "authoritative_source": "chain_state",
            "active_step_heartbeat": {
                "active": True,
                "attempt": 3,
                "phase": "execute",
                "started_at": "2026-07-04T21:37:07Z",
            },
            "current_refs": {
                "current_plan_name": "demo-plan",
                "chain_current_plan_name": "demo-plan",
                "plan_current_state": "blocked",
                "chain_last_state": "blocked",
            },
            "plan_state": {"present": True, "current_state": "blocked"},
            "chain_state": {"present": True, "last_state": "blocked"},
            "needs_human": {"plan_refs": ["demo-plan"]},
        }
    )
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("compute_meta_repair_trigger", "dispatch_meta_repair"),
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"MARKER_DIR={str(marker_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            (
                f"compute_meta_repair_trigger demo-session "
                f"{shlex.quote(observation)} alive"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "TRIGGER:persistent_recurring_retry"


def test_compute_meta_repair_trigger_skips_partial_liveness_when_session_alive(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    repair_data_dir.mkdir(parents=True)
    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "outcome": "running",
                "attempts": [
                    {"attempt_id": 1, "failure_classification": "blocked_state_or_recovery_error"},
                ],
            }
        ),
        encoding="utf-8",
    )
    sidecar_dir = marker_dir / "repair-data.d" / "events"
    sidecar_dir.mkdir(parents=True)
    (sidecar_dir / "events.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "session": "demo-session",
                    "outcome": "partial_liveness",
                    "recorded_at": f"2026-07-04T10:1{i}:00Z",
                }
            )
            for i in range(2)
        )
        + "\n",
        encoding="utf-8",
    )
    observation = json.dumps(
        {
            "authoritative_source": "chain_state",
            "current_refs": {
                "current_plan_name": "m4-clip-type-shader-and-20260704-0427",
                "chain_last_state": "finalized",
                "plan_current_state": "finalized",
            },
            "plan_state": {
                "present": True,
                "current_state": "finalized",
            },
            "chain_state": {
                "present": True,
                "last_state": "finalized",
            },
            "active_step_heartbeat": {
                "active": False,
            },
        }
    )
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("compute_meta_repair_trigger", "dispatch_meta_repair"),
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"MARKER_DIR={str(marker_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            (
                f"compute_meta_repair_trigger demo-session "
                f"{shlex.quote(observation)} alive"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "NO_TRIGGER"


def test_launch_chain_tick_dispatches_meta_repair_on_true_blocker_discord_failure(tmp_path: Path) -> None:
    paths = _prepare_meta_repair_launch_chain_tick_fixture(
        tmp_path,
        payload_overrides={"outcome": "discord_escalated", "plan_name": "demo-plan"},
        discord_status="helper_unavailable",
        true_blocker_plan="demo-plan",
    )
    result = _run_launch_chain_tick_meta_repair_script(paths)
    assert result.returncode == 0, result.stderr
    assert "META_DISPATCH" in result.stderr
    assert "TMUX" not in result.stderr
    assert "trigger=discord_delivery_failure" in paths["log_path"].read_text(encoding="utf-8")


def test_launch_chain_tick_skips_meta_repair_when_no_trigger_matches(tmp_path: Path) -> None:
    paths = _prepare_meta_repair_launch_chain_tick_fixture(
        tmp_path,
        payload_overrides={
            "outcome": "discord_escalated",
            "attempts": [{"attempt_id": 1, "failure_classification": "phase_failed"}],
        },
        discord_status="delivered",
    )
    result = _run_launch_chain_tick_meta_repair_script(paths)
    assert result.returncode == 0, result.stderr
    assert "META_DISPATCH" not in result.stderr
    assert "TMUX new-session" in result.stderr


# ---------------------------------------------------------------------------
# Progress-stall detection + progress auditor (new components)
# ---------------------------------------------------------------------------


def _extract_phase_program() -> str:
    """Pull the python body of plan_phase_health_status() out of the wrapper."""
    text = _wrapper("arnold-watchdog")
    start = text.index("plan_phase_health_status() {")
    marker = "python3 - \"$workspace\" \"$run_kind\" \"$plan_name\" <<'PY'"
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    return text[py_start:py_end]


def _run_phase(workspace: Path, run_kind: str = "chain", plan_name: str = "") -> str:
    program = _extract_phase_program()
    prog_path = workspace.parent / "_phase_prog.py"
    prog_path.write_text(program, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(prog_path), str(workspace), run_kind, plan_name],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"phase program failed: {result.stderr}"
    return result.stdout.strip()


def test_plan_phase_health_detects_workspace_drift_without_latest_failure(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    plan = workspace / ".megaplan" / "plans" / "m2-demo"
    plan.mkdir(parents=True)
    (plan / "state.json").write_text(
        json.dumps(
            {
                "current_state": "finalized",
                "active_step": {"phase": "execute", "worker_pid": 1234},
                "history": [],
            }
        ),
        encoding="utf-8",
    )
    (workspace / ".megaplan" / "cloud-chain-demo.log").write_text(
        "sandbox refused terminal: refusing terminal command: leading `cd /workspace/arnold` "
        "targets /workspace/arnold, which is outside the sandbox root/project directory "
        "/workspace/native-composition-followup/Arnold\n",
        encoding="utf-8",
    )

    result = _run_phase(workspace)

    assert result.startswith("workspace_drift:m2-demo:")
    assert "sandbox_refused_outside_project_root" in result


def test_plan_phase_health_ignores_sandbox_refusal_after_later_progress(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    plan = workspace / ".megaplan" / "plans" / "m2-demo"
    plan.mkdir(parents=True)
    (plan / "state.json").write_text(
        json.dumps(
            {
                "current_state": "finalized",
                "active_step": {"phase": "execute", "worker_pid": 1234},
                "history": [],
            }
        ),
        encoding="utf-8",
    )
    (workspace / ".megaplan" / "cloud-chain-demo.log").write_text(
        "\n".join(
            [
                "sandbox refused terminal: refusing terminal command: leading `cd /workspace/arnold` "
                "targets /workspace/arnold, which is outside the sandbox root/project directory "
                "/workspace/native-composition-followup/Arnold. Run commands relative to the project "
                "directory; do not `cd` to an absolute path outside the worktree.",
                "  [done] ┊ 💻 $         cd /workspace/arnold && python -c \"...\"  0.0s (0.0s)",
                "  [tool] (◕ᴗ◕✿) 💻 python -m pytest tests/arnold/pipeline/native/test_decorators.py",
                "  [done] ┊ 💻 $         python -m pytest tests/arnold/pipeline/native/test_decorators.py  1.4s (1.6s)",
                "[auto m2-demo] iter 2 state=critiqued next=gate valid_next=['gate', 'step']",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = _run_phase(workspace)

    assert result == "ok"


def test_plan_phase_health_ignores_sandbox_refusal_with_recent_active_step(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    plan = workspace / ".megaplan" / "plans" / "m2-demo"
    plan.mkdir(parents=True)
    (plan / "state.json").write_text(
        json.dumps(
            {
                "current_state": "finalized",
                "active_step": {
                    "phase": "execute",
                    "worker_pid": 1234,
                    "last_activity_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
                },
                "history": [],
            }
        ),
        encoding="utf-8",
    )
    (workspace / ".megaplan" / "cloud-chain-demo.log").write_text(
        "sandbox refused terminal: refusing terminal command: leading `cd /workspace/arnold` "
        "targets /workspace/arnold, which is outside the sandbox root/project directory "
        "/workspace/native-composition-followup/Arnold\n",
        encoding="utf-8",
    )

    result = _run_phase(workspace)

    assert result == "ok"


def test_plan_phase_health_ignores_sandbox_refusal_with_recent_events_only(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    plan = workspace / ".megaplan" / "plans" / "m2-demo"
    plan.mkdir(parents=True)
    (plan / "state.json").write_text(
        json.dumps(
            {
                "current_state": "finalized",
                "history": [],
            }
        ),
        encoding="utf-8",
    )
    (plan / "events.ndjson").write_text('{"event":"llm_stream"}\n', encoding="utf-8")
    (workspace / ".megaplan" / "cloud-chain-demo.log").write_text(
        "sandbox refused terminal: refusing terminal command: leading `cd /workspace/arnold` "
        "targets /workspace/arnold, which is outside the sandbox root/project directory "
        "/workspace/native-composition-followup/Arnold\n",
        encoding="utf-8",
    )

    result = _run_phase(workspace)

    assert result == "ok"


def _extract_stall_program() -> str:
    """Pull the python body of plan_progress_stall_status() out of the wrapper."""
    text = _wrapper("arnold-watchdog")
    start = text.index("plan_progress_stall_status() {")
    marker = "python3 - \"$workspace\" \"$MARKER_DIR\" \"$run_kind\" \"$plan_name\" <<'PY'"
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    return text[py_start:py_end]


def _run_stall(
    workspace: Path,
    marker: Path,
    env_overrides: dict[str, str] | None = None,
    run_kind: str = "chain",
    plan_name: str = "",
) -> str:
    program = _extract_stall_program()
    prog_path = workspace.parent / "_stall_prog.py"
    prog_path.write_text(program, encoding="utf-8")
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, str(prog_path), str(workspace), str(marker), run_kind, plan_name],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, f"stall program failed: {result.stderr}"
    return result.stdout.strip()


def _extract_chain_health_program() -> str:
    """Pull the python body of chain_health_status() out of the wrapper."""
    text = _wrapper("arnold-watchdog")
    start = text.index("chain_health_status() {")
    marker = 'eval "$(python3 - "$session" "$workspace" "$remote_spec_path" "$health" "$MARKER_DIR" "$REPAIR_DATA_DIR" <<\'PY\''
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    return text[py_start:py_end]


def _parse_shell_assignments(stdout: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in stdout.strip().splitlines():
        name, sep, raw_value = line.partition("=")
        if not sep:
            continue
        values = shlex.split(raw_value)
        parsed[name] = values[0] if values else ""
    return parsed


def _run_chain_health(
    workspace: Path,
    marker: Path,
    repair_data_dir: Path,
    *,
    session: str = "demo",
    remote_spec_path: str = "",
    health: str = "stopped",
    env_overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    program = _extract_chain_health_program()
    prog_path = workspace.parent / "_chain_health_prog.py"
    prog_path.write_text(program, encoding="utf-8")
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [
            sys.executable,
            str(prog_path),
            session,
            str(workspace),
            remote_spec_path,
            health,
            str(marker),
            str(repair_data_dir),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, f"chain health program failed: {result.stderr}"
    return _parse_shell_assignments(result.stdout)


def _write_plan(plan_dir: Path, state: dict, plan_v_bodies: dict[str, str] | None = None,
                events_body: str = "") -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    for name, body in (plan_v_bodies or {}).items():
        (plan_dir / name).write_text(body, encoding="utf-8")
    if events_body:
        (plan_dir / "events.ndjson").write_text(events_body, encoding="utf-8")


def _write_chain_state(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state), encoding="utf-8")


def _init_git_repo(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Watchdog Tests"], cwd=path, check=True)
    (path / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=path, check=True, capture_output=True, text=True)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def test_chain_health_status_is_wired_into_launch_chain_tick() -> None:
    text = _wrapper("arnold-watchdog")

    assert "chain_health_status()" in text
    assert 'chain_health_status "$session" "$workspace" "$remote_spec_path" "$health"' in text
    assert 'repair_unintended_stop "$report_items" "$session" "$workspace" "$remote_spec" "${CHAIN_HEALTH_STATUS:-chain_issue}:' in text


def test_watchdog_scan_once_bootstraps_observation_before_repair_trigger() -> None:
    text = _extract_wrapper_function_until("scan_once_unlocked", "scan_once")

    assert 'bootstrap_watchdog_observation "$report_items"' in text
    assert "repair_trigger_scan" in text
    assert text.index('if ! bootstrap_watchdog_observation "$report_items"; then') < text.index("repair_trigger_scan")


def test_watchdog_retries_transient_repair_trigger_bootstrap_failure() -> None:
    text = _wrapper("arnold-watchdog")
    section = text[text.index("repair_trigger_scan() {"):text.index("kimi_operator_running() {")]
    assert "for attempt in 1 2 3; do" in section
    assert "retrying before watchdog interval sleep" in section
    assert "PYTHONSAFEPATH=1" in section


def test_watchdog_only_reports_dispatch_after_managed_manifest_confirmation() -> None:
    text = _wrapper("arnold-watchdog")
    section = text[text.index("dispatch_kimi_repair() {"):text.index("claim_active_repair_launch() {")]
    assert '--run-id-file "$run_id_file"' in section
    assert 'confirm_managed_agent_dispatch "$workspace" "$run_id_file" "$request_id" "$blocker_id"' in section
    assert 'REPAIR_DISPATCH_RESULT="launch_failed"' in section
    assert section.index('kimi_dispatch_marker_set "$session" managed_agent') < section.index(
        'REPAIR_DISPATCH_RESULT="dispatched"'
    )


def test_repair_trigger_path_unit_fires_immediate_error_queue_scan() -> None:
    path_unit = _systemd_file("megaplan-repair-trigger.path")
    service_unit = _systemd_file("megaplan-repair-trigger.service")

    assert "DirectoryNotEmpty=/workspace/.megaplan/repair-queue/requests" in path_unit
    assert "PathModified=/workspace/.megaplan/repair-queue/requests" in path_unit
    assert "Unit=megaplan-repair-trigger.service" in path_unit
    assert (
        "ExecStart=/workspace/.megaplan/supervisor-python/current/bin/python3 "
        "/workspace/arnold/arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-trigger"
    ) in service_unit
    assert "MEGAPLAN_SUPERVISOR_RUNTIME_REQUIRED=1" in service_unit
    assert "ARNOLD_REPAIR_TRIGGER_ENABLED" in service_unit


def test_watchdog_scan_once_tolerates_repair_trigger_observe_only_without_systemd(tmp_path: Path) -> None:
    trigger = tmp_path / "arnold-repair-trigger"
    trigger.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' '{\"event\":\"repair_trigger\",\"status\":\"busy\"}'\n",
        encoding="utf-8",
    )
    trigger.chmod(trigger.stat().st_mode | stat.S_IXUSR)
    marker_dir = tmp_path / "missing-markers"
    order_path = tmp_path / "order.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function_until("write_watchdog_observation_error", "watchdog_observation_runtime_check"),
            _extract_wrapper_function("bootstrap_watchdog_observation"),
            _extract_wrapper_function("repair_trigger_scan"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(tmp_path / 'repair-data')!r}",
            f"REPAIR_TRIGGER_BIN={str(trigger)!r}",
            f"STATUS_DIR={str(tmp_path / 'status')!r}",
            """
log() { printf '%s\n' "$*" >> "$ORDER_PATH"; }
watchdog_observation_runtime_check() { return 0; }
sync_editable_source_branch() { printf '%s\n' sync >> "$ORDER_PATH"; }
report_item() { :; }
""".strip(),
            f"ORDER_PATH={str(order_path)!r}",
            'report_items="$(mktemp)"',
            'bootstrap_watchdog_observation "$report_items"',
            'printf "%s\n" bootstrap >> "$ORDER_PATH"',
            "repair_trigger_scan",
            'sync_editable_source_branch "$report_items"',
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    lines = order_path.read_text(encoding="utf-8").splitlines()
    assert "bootstrap" in lines
    assert any("repair-trigger {\"event\":\"repair_trigger\",\"status\":\"busy\"}" in line for line in lines)
    assert lines.index("sync") > next(
        idx for idx, line in enumerate(lines) if "repair-trigger" in line
    )


def test_watchdog_scan_once_fails_closed_when_observation_bootstrap_stays_blind(tmp_path: Path) -> None:
    marker_dir = tmp_path / "missing-markers"
    order_path = tmp_path / "order.log"
    status_dir = tmp_path / "status"

    script = "\n\n".join(
        [
            _extract_wrapper_function_until("write_watchdog_observation_error", "watchdog_observation_runtime_check"),
            _extract_wrapper_function("bootstrap_watchdog_observation"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"STATUS_DIR={str(status_dir)!r}",
            """
log() { printf '%s\n' "$*" >> "$ORDER_PATH"; }
watchdog_observation_runtime_check() { printf '%s\n' broken >&2; return 1; }
sync_editable_source_branch() { printf '%s\n' sync >> "$ORDER_PATH"; return 1; }
report_item() { printf '%s\n' "report:$4" >> "$ORDER_PATH"; }
SRC_DIR=/workspace/arnold
SYNC_BRANCH=editible-install
""".strip(),
            f"ORDER_PATH={str(order_path)!r}",
            'report_items="$(mktemp)"',
            'bootstrap_watchdog_observation "$report_items"',
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 1, result.stderr
    lines = order_path.read_text(encoding="utf-8").splitlines()
    assert "report:observation_blind" in lines
    assert "sync" not in lines
    error_payload = json.loads((status_dir / "cloud-status.write-error.json").read_text(encoding="utf-8"))
    assert "observation bootstrap failed" in error_payload["error"]
    atomic_payload = json.loads(
        (status_dir / "watchdog-observation-failure.json").read_text(encoding="utf-8")
    )
    assert atomic_payload["status"] == "failed"


def test_watchdog_session_health_status_treats_live_worker_process_as_alive_without_tmux(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    chain_state_path = workspace / ".megaplan" / "plans" / ".chains" / f"chain-{digest}.json"
    chain_state_path.parent.mkdir(parents=True, exist_ok=True)
    plan_name = "m3-demo-plan"

    worker = subprocess.Popen(["sleep", "30"])
    try:
        chain_state_path.write_text(json.dumps({"current_plan_name": plan_name}), encoding="utf-8")
        plan_dir = workspace / ".megaplan" / "plans" / plan_name
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps({"active_step": {"phase": "execute", "worker_pid": worker.pid}}),
            encoding="utf-8",
        )

        script = "\n\n".join(
            [
                _extract_wrapper_function("matching_runner_process_alive"),
                _extract_wrapper_function("session_health_status"),
                """
tmux() { return 1; }
chain_wait_status() { echo none; }
""".strip(),
                f"session_health_status demo-session {shlex.quote(str(workspace))} {shlex.quote(str(spec_path))} chain ''",
            ]
        )

        result = _run_watchdog_shell(script)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "alive"
    finally:
        worker.terminate()
        worker.wait(timeout=5)


def test_watchdog_chain_health_short_circuits_plan_repair_dispatch(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_dir = tmp_path / "repair-data"
    marker_dir.mkdir()
    repair_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = workspace / "demo-spec.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    report_path = tmp_path / "report.tsv"

    script = "\n\n".join(
        [
            _extract_wrapper_function("launch_chain_tick"),
            _extract_wrapper_function("repair_unintended_stop"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo alive; }
chain_health_status() {
  CHAIN_HEALTH_STATUS=chain_cycle
  CHAIN_HEALTH_SUMMARY='chain cycle detected'
  CHAIN_HEALTH_ARTIFACT_PATH=/tmp/chain-health.json
}
plan_phase_health_status() { echo phase_failure:should-not-run; }
plan_progress_stall_status() { echo progress_stall:should-not-run; }
plan_attention_status_env() { echo SHOULD_NOT_RUN >&2; }
    repair_loop_busy_state() { echo none; }
    dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
    repair_unhealthy_session() { return 0; }
mechanical_relaunch_attempted_previously() { return 1; }
kimi_dispatch_failed_previously() { return 1; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\tchain_cycle: chain cycle detected; artifact=/tmp/chain-health.json\t" in report
    assert "SHOULD_NOT_RUN" not in result.stderr
    assert "TMUX" not in result.stderr


def test_chain_health_status_detects_repeating_merged_pr_completion_guard_cycle() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    spec_path = ws / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    plan_name = "m8-generated-assets-and-merge-20260629-1937"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {"current_state": "blocked", "iteration": 1},
        events_body=json.dumps({"kind": "phase_end", "phase": "execute"}) + "\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / f"chain-{digest}.json",
        {
            "current_milestone_index": 7,
            "current_plan_name": plan_name,
            "last_state": "authority_divergence",
            "pr_number": 128,
            "pr_state": "merged",
            "completed": [{"label": "m1"}, {"label": "m2"}],
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    repeated = "\n".join(
        [
            "[chain] PR #128 merged; advancing past m8-generated-assets-merge-result-conformance",
            "[chain] completion guard blocked m8-generated-assets-merge-result-conformance: plan m8-generated-assets-and-merge-20260629-1937 current_state='blocked' is not terminal-success 'done'",
            '[chain] synced last_state for m8-generated-assets-and-merge-20260629-1937: authority_divergence -> blocked',
        ]
        * 3
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(repeated + "\n", encoding="utf-8")

    payload = _run_chain_health(
        ws,
        marker,
        repair_dir,
        remote_spec_path=str(spec_path),
        env_overrides={"CLOUD_WATCHDOG_CHAIN_CYCLE_REPEATS": "3"},
    )

    assert payload["CHAIN_HEALTH_STATUS"] == "chain_cycle"
    artifact_path = Path(payload["CHAIN_HEALTH_ARTIFACT_PATH"])
    assert artifact_path.exists()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["issue_kind"] == "chain_cycle"
    assert artifact["completion_guard"]["milestone"] == "m8-generated-assets-merge-result-conformance"
    assert artifact["completion_guard"]["repeat_count"] == 3
    assert "## CHAIN HEALTH EVIDENCE" in artifact["evidence_markdown"]
    assert "Route to arnold_pipelines/megaplan/chain/" in artifact["why_chain_layer_issue"]


def test_chain_health_rejects_incomplete_done_state() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    spec_path = ws / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        "milestones:\n"
        "  - label: m1\n"
        "    idea: m1.md\n"
        "  - label: m2\n"
        "    idea: m2.md\n",
        encoding="utf-8",
    )
    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / f"chain-{digest}.json",
        {
            "current_milestone_index": 1,
            "current_plan_name": "",
            "last_state": "done",
            "completed": [{"label": "m1", "status": "done"}],
        },
    )

    payload = _run_chain_health(
        ws,
        marker,
        repair_dir,
        remote_spec_path=str(spec_path),
    )

    assert payload["CHAIN_HEALTH_STATUS"] == "chain_inconsistent_done"
    assert payload["CHAIN_HEALTH_KIND"] == "chain_inconsistent_done"
    assert "1/2 milestones" in payload["CHAIN_HEALTH_SUMMARY"]
    artifact = json.loads(Path(payload["CHAIN_HEALTH_ARTIFACT_PATH"]).read_text(encoding="utf-8"))
    assert artifact["issue_kind"] == "chain_inconsistent_done"
    assert "last_state=done" in artifact["evidence_markdown"]


def test_chain_health_status_leaves_one_off_completion_guard_repair_eligible() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    plan_name = "sprint-1-safe-compiler-20260630-0033"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {"current_state": "blocked", "iteration": 1},
        events_body=json.dumps({"kind": "phase_end", "phase": "execute"}) + "\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 0,
            "current_plan_name": plan_name,
            "last_state": "authority_divergence",
            "pr_state": "",
            "completed": [],
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(
        "[chain] completion guard blocked sprint-01-safe-compiler-foundation: "
        "no semantic diff from milestone_base_sha 9d2d53e to local HEAD; "
        "no typed no-op completion waiver found\n",
        encoding="utf-8",
    )

    payload = _run_chain_health(ws, marker, repair_dir, health="stopped")

    assert payload["CHAIN_HEALTH_STATUS"] == "ok"
    assert payload["CHAIN_HEALTH_ARTIFACT_PATH"] == ""


def test_chain_health_status_escalates_recurring_completion_guard_with_zero_git_advancement() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    base_sha = _init_git_repo(ws)
    plan_name = "sprint-1-safe-compiler-20260630-0033"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {
            "current_state": "blocked",
            "iteration": 3,
            "meta": {"chain_policy": {"milestone_base_sha": base_sha}},
        },
        events_body=json.dumps({"kind": "phase_end", "phase": "execute"}) + "\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 0,
            "current_plan_name": plan_name,
            "last_state": "authority_divergence",
            "pr_state": "",
            "completed": [],
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(
        (
            "[chain] completion guard blocked sprint-01-safe-compiler-foundation: "
            f"no semantic diff from milestone_base_sha {base_sha} to local HEAD; "
            "no typed no-op completion waiver found\n"
        )
        * 3,
        encoding="utf-8",
    )

    payload = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="stopped",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_COMPLETION_GUARD_REPEATS": "3"},
    )

    assert payload["CHAIN_HEALTH_STATUS"] == "needs_human"
    assert "produces NO code changes" in payload["CHAIN_HEALTH_SUMMARY"]
    assert "Not auto-repairable" in payload["CHAIN_HEALTH_SUMMARY"]
    artifact = json.loads(Path(payload["CHAIN_HEALTH_ARTIFACT_PATH"]).read_text(encoding="utf-8"))
    assert artifact["issue_kind"] == "plan_noop_completion_guard"
    assert artifact["completion_guard"]["repeat_count"] == 3
    assert artifact["details"]["completion_guard_advancement"]["available"] is True
    assert artifact["details"]["completion_guard_advancement"]["ahead_count"] == 0
    assert artifact["details"]["completion_guard_worktree"]["dirty"] is False


def test_chain_health_status_classifies_zero_git_advancement_with_dirty_worktree_as_commit_bug() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    base_sha = _init_git_repo(ws)
    (ws / "compiler.py").write_text("print('uncommitted execute output')\n", encoding="utf-8")
    plan_name = "sprint-1-safe-compiler-20260630-0033"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {
            "current_state": "blocked",
            "iteration": 3,
            "meta": {"chain_policy": {"milestone_base_sha": base_sha}},
        },
        events_body=json.dumps({"kind": "phase_end", "phase": "execute"}) + "\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 0,
            "current_plan_name": plan_name,
            "last_state": "authority_divergence",
            "pr_state": "",
            "completed": [],
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(
        (
            "[chain] completion guard blocked sprint-01-safe-compiler-foundation: "
            f"no semantic diff from milestone_base_sha {base_sha} to local HEAD; "
            "no typed no-op completion waiver found\n"
        )
        * 3,
        encoding="utf-8",
    )

    payload = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="stopped",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_COMPLETION_GUARD_REPEATS": "3"},
    )

    assert payload["CHAIN_HEALTH_STATUS"] == "chain_uncommitted_execute_output"
    assert "execute output was not committed" in payload["CHAIN_HEALTH_SUMMARY"]
    assert "no-op waiver" in payload["CHAIN_HEALTH_SUMMARY"]
    assert "CHAIN HEALTH EVIDENCE: working tree has 1 uncommitted files" in payload["CHAIN_HEALTH_LOG_MESSAGE"]
    artifact = json.loads(Path(payload["CHAIN_HEALTH_ARTIFACT_PATH"]).read_text(encoding="utf-8"))
    assert artifact["issue_kind"] == "chain_uncommitted_execute_output"
    worktree = artifact["details"]["completion_guard_worktree"]
    assert worktree["dirty"] is True
    assert worktree["uncommitted_file_count"] == 1
    assert "compiler.py" in "\n".join(worktree["sample"])
    assert "Working tree evidence: 1 uncommitted files" in artifact["evidence_markdown"]
    assert "commit-and-push gating" in artifact["evidence_markdown"]


def test_chain_health_status_classifies_repeated_pr_progression_publish_guard_as_commit_bug() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    base_sha = _init_git_repo(ws)
    (ws / "compiler.py").write_text("print('uncommitted execute output')\n", encoding="utf-8")
    plan_name = "sprint-1-safe-compiler-20260630-0033"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {
            "current_state": "finalized",
            "iteration": 3,
            "meta": {"chain_policy": {"milestone_base_sha": base_sha}},
        },
        events_body=json.dumps({"kind": "phase_end", "phase": "execute"}) + "\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 0,
            "current_plan_name": plan_name,
            "last_state": "authority_divergence",
            "pr_number": 77,
            "pr_state": "merged",
            "completed": [],
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(
        (
            "[chain] PR progression blocked sprint-01-safe-compiler-foundation: "
            "plan sprint-1-safe-compiler-20260630-0033 has unpublished claimed changes after PR merged: compiler.py\n"
        )
        * 3,
        encoding="utf-8",
    )

    payload = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="stopped",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_COMPLETION_GUARD_REPEATS": "3"},
    )

    assert payload["CHAIN_HEALTH_STATUS"] == "chain_uncommitted_execute_output"
    assert "unpublished in a dirty worktree" in payload["CHAIN_HEALTH_SUMMARY"]
    assert "publish guards" in payload["CHAIN_HEALTH_LOG_MESSAGE"]
    artifact = json.loads(Path(payload["CHAIN_HEALTH_ARTIFACT_PATH"]).read_text(encoding="utf-8"))
    assert artifact["issue_kind"] == "chain_uncommitted_execute_output"
    assert artifact["details"]["completion_guard_kind"] == "pr_progression"
    worktree = artifact["details"]["completion_guard_worktree"]
    assert worktree["dirty"] is True
    assert worktree["uncommitted_file_count"] == 1
    assert "compiler.py" in "\n".join(worktree["sample"])
    assert "PR progression guard evidence" in artifact["evidence_markdown"]


def test_chain_health_status_keeps_recurring_completion_guard_repair_eligible_when_git_advanced() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    base_sha = _init_git_repo(ws)
    (ws / "compiler.py").write_text("print('work landed')\n", encoding="utf-8")
    subprocess.run(["git", "add", "compiler.py"], cwd=ws, check=True)
    subprocess.run(["git", "commit", "-m", "land work"], cwd=ws, check=True, capture_output=True, text=True)
    plan_name = "sprint-1-safe-compiler-20260630-0033"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {
            "current_state": "blocked",
            "iteration": 3,
            "meta": {"chain_policy": {"milestone_base_sha": base_sha}},
        },
        events_body=json.dumps({"kind": "phase_end", "phase": "execute"}) + "\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 0,
            "current_plan_name": plan_name,
            "last_state": "authority_divergence",
            "pr_state": "",
            "completed": [],
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(
        (
            "[chain] completion guard blocked sprint-01-safe-compiler-foundation: "
            f"no semantic diff from milestone_base_sha {base_sha} to local HEAD; "
            "no typed no-op completion waiver found\n"
        )
        * 3,
        encoding="utf-8",
    )

    payload = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="stopped",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_COMPLETION_GUARD_REPEATS": "3"},
    )

    assert payload["CHAIN_HEALTH_STATUS"] == "ok"
    assert payload["CHAIN_HEALTH_ARTIFACT_PATH"] == ""


def test_chain_health_status_detects_stuck_nonterminal_across_ticks() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 4,
            "current_plan_name": "demo-plan",
            "last_state": "authority_divergence",
            "pr_state": "merged",
            "completed": [{"label": "m1"}],
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(
        "[chain] completion guard blocked demo: still blocked\n",
        encoding="utf-8",
    )

    first = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="alive",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_STUCK_TICKS": "2"},
    )
    second = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="alive",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_STUCK_TICKS": "2"},
    )

    assert first["CHAIN_HEALTH_STATUS"] == "ok"
    assert second["CHAIN_HEALTH_STATUS"] == "chain_stuck"
    artifact = json.loads(Path(second["CHAIN_HEALTH_ARTIFACT_PATH"]).read_text(encoding="utf-8"))
    assert artifact["issue_kind"] == "chain_stuck_nonterminal"
    assert artifact["details"]["stuck_ticks"] == 2
    assert artifact["chain_state_summary"]["last_state"] == "authority_divergence"


def test_chain_health_status_ignores_stuck_nonterminal_while_plan_step_is_active() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 1,
            "current_plan_name": "m1-demo-plan",
            "last_state": "between_milestones",
            "pr_state": "",
            "completed": [{"label": "m0"}],
        },
    )
    _write_plan(
        ws / ".megaplan" / "plans" / "m1-demo-plan",
        {
            "current_state": "finalized",
            "active_step": {"phase": "execute", "started_at": "2026-07-03T16:31:05Z"},
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(
        "[chain] milestone m1 starting\n",
        encoding="utf-8",
    )

    first = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="alive",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_STUCK_TICKS": "2"},
    )
    second = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="alive",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_STUCK_TICKS": "2"},
    )

    assert first["CHAIN_HEALTH_STATUS"] == "ok"
    assert second["CHAIN_HEALTH_STATUS"] == "ok"
    assert second["CHAIN_HEALTH_ARTIFACT_PATH"] == ""


def test_chain_health_status_ignores_stuck_nonterminal_when_chain_last_state_mirrors_blocked_plan() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 1,
            "current_plan_name": "m1-demo-plan",
            "last_state": "blocked",
            "pr_state": "open",
            "completed": [{"label": "m0"}],
        },
    )
    _write_plan(
        ws / ".megaplan" / "plans" / "m1-demo-plan",
        {
            "current_state": "blocked",
            "latest_failure": {
                "kind": "execution_blocked",
                "phase": "execute",
                "message": "execute blocked by quality gates",
            },
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(
        "[chain] resuming existing plan m1-demo-plan for m1\n",
        encoding="utf-8",
    )

    first = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="alive",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_STUCK_TICKS": "2"},
    )
    second = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="alive",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_STUCK_TICKS": "2"},
    )

    assert first["CHAIN_HEALTH_STATUS"] == "ok"
    assert second["CHAIN_HEALTH_STATUS"] == "ok"
    assert second["CHAIN_HEALTH_ARTIFACT_PATH"] == ""


def test_chain_health_status_classifies_unclean_base_before_generic_stuck() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 1,
            "current_plan_name": "m1-demo-plan",
            "last_state": "blocked",
            "pr_state": "",
            "completed": [{"label": "m0"}],
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(
        "[chain] retrying milestone m1\n"
        '{"error": "unclean_base", "message": "require_clean_base: working base carries uncommitted WIP"}\n',
        encoding="utf-8",
    )

    payload = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="stopped",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_STUCK_TICKS": "2"},
    )

    assert payload["CHAIN_HEALTH_STATUS"] == "chain_unclean_base"
    assert "require_clean_base found carried WIP" in payload["CHAIN_HEALTH_SUMMARY"]
    assert "retry-preservation issue" in payload["CHAIN_HEALTH_LOG_MESSAGE"]
    artifact = json.loads(Path(payload["CHAIN_HEALTH_ARTIFACT_PATH"]).read_text(encoding="utf-8"))
    assert artifact["issue_kind"] == "chain_unclean_base"
    assert artifact["details"]["dirty_base_signal"] is True
    assert "Unclean-base evidence" in artifact["evidence_markdown"]


def test_chain_health_status_detects_github_large_file_push_rejection() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    plan_name = "demo-plan"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {
            "current_state": "failed",
            "latest_failure": {
                "kind": "phase_callback_failed",
                "phase": "review",
                "message": (
                    "phase-complete callback failed after 'review': "
                    "git push --no-verify origin HEAD:demo exited 1"
                ),
            },
        },
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 0,
            "current_plan_name": plan_name,
            "last_state": "failed",
            "completed": [],
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(
        "\n".join(
            [
                "[chain] git push --no-verify origin HEAD:demo -> rc=1",
                "remote: error: GH001: Large files detected.",
                "remote: error: File .megaplan/epics/demo-plan/events.jsonl is 101.74 MB; this exceeds GitHub's file size limit of 100.00 MB",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = _run_chain_health(ws, marker, repair_dir, health="stopped")

    assert payload["CHAIN_HEALTH_STATUS"] == "chain_large_file_push_rejection"
    assert payload["CHAIN_HEALTH_KIND"] == "git_large_file_push_rejection"
    assert "oversized runtime journal" in payload["CHAIN_HEALTH_SUMMARY"]
    assert "large-file limit" in payload["CHAIN_HEALTH_LOG_MESSAGE"]
    artifact = json.loads(Path(payload["CHAIN_HEALTH_ARTIFACT_PATH"]).read_text(encoding="utf-8"))
    assert artifact["issue_kind"] == "git_large_file_push_rejection"
    assert artifact["details"]["runtime_journal_patterns"] == [
        ".megaplan/epics/*/events.jsonl",
        ".megaplan/plans/*/events.ndjson",
        ".megaplan/plans/*/execution_trace.jsonl",
    ]


def test_chain_health_status_detects_busy_no_advance_across_ticks() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    plan_name = "demo-plan"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {"current_state": "planning", "iteration": 1},
        events_body=json.dumps({"kind": "phase_started", "phase": "execute"}) + "\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 2,
            "current_plan_name": plan_name,
            "last_state": "planning",
            "pr_state": "open",
            "completed": [{"label": "m1"}],
        },
    )

    assert _run_chain_health(ws, marker, repair_dir, env_overrides={"CLOUD_WATCHDOG_CHAIN_NO_ADVANCE_TICKS": "2"})["CHAIN_HEALTH_STATUS"] == "ok"
    events_path = ws / ".megaplan" / "plans" / plan_name / "events.ndjson"
    events_path.write_text(
        events_path.read_text(encoding="utf-8") + json.dumps({"kind": "phase_end", "phase": "execute"}) + "\n",
        encoding="utf-8",
    )
    assert _run_chain_health(ws, marker, repair_dir, env_overrides={"CLOUD_WATCHDOG_CHAIN_NO_ADVANCE_TICKS": "2"})["CHAIN_HEALTH_STATUS"] == "ok"
    events_path.write_text(
        events_path.read_text(encoding="utf-8") + json.dumps({"kind": "phase_started", "phase": "review"}) + "\n",
        encoding="utf-8",
    )
    third = _run_chain_health(
        ws,
        marker,
        repair_dir,
        env_overrides={"CLOUD_WATCHDOG_CHAIN_NO_ADVANCE_TICKS": "2"},
    )

    assert third["CHAIN_HEALTH_STATUS"] == "chain_no_advance"
    artifact = json.loads(Path(third["CHAIN_HEALTH_ARTIFACT_PATH"]).read_text(encoding="utf-8"))
    assert artifact["issue_kind"] == "chain_no_advance"
    assert artifact["details"]["no_advance_ticks"] == 2
    assert artifact["chain_state_summary"]["current_milestone_index"] == 2


def test_chain_health_no_advance_ignores_active_plan_step() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    plan_name = "demo-plan"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {
            "current_state": "finalized",
            "iteration": 1,
            "active_step": {"phase": "execute", "worker_pid": 1234},
        },
        events_body=json.dumps({"kind": "phase_started", "phase": "execute"}) + "\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 2,
            "current_plan_name": plan_name,
            "last_state": "prepped",
            "completed": [{"label": "m1"}],
        },
    )

    env = {"CLOUD_WATCHDOG_CHAIN_NO_ADVANCE_TICKS": "2"}
    assert _run_chain_health(ws, marker, repair_dir, env_overrides=env)["CHAIN_HEALTH_STATUS"] == "ok"
    events_path = ws / ".megaplan" / "plans" / plan_name / "events.ndjson"
    for i in range(3):
        events_path.write_text(
            events_path.read_text(encoding="utf-8") + json.dumps({"kind": "stderr", "i": i}) + "\n",
            encoding="utf-8",
        )
        result = _run_chain_health(ws, marker, repair_dir, env_overrides=env)
        assert result["CHAIN_HEALTH_STATUS"] == "ok"


def test_chain_health_no_advance_ignores_existing_counter_after_plan_becomes_live() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    plan_name = "demo-plan"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {
            "current_state": "executing",
            "iteration": 2,
            "active_step": {"phase": "execute", "worker_pid": 1234},
        },
        events_body=json.dumps({"kind": "phase_started", "phase": "execute"}) + "\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 2,
            "current_plan_name": plan_name,
            "last_state": "executing",
            "pr_state": "open",
            "completed": [{"label": "m1"}],
        },
    )
    marker.mkdir(parents=True, exist_ok=True)
    (marker / "demo.chain-health.progress.json").write_text(
        json.dumps(
            {
                "current_milestone_index": 2,
                "completed_count": 1,
                "events_mtime": 1,
                "events_size": 1,
                "last_state": "executing",
                "no_advance_ticks": 3,
            }
        ),
        encoding="utf-8",
    )

    result = _run_chain_health(
        ws,
        marker,
        repair_dir,
        env_overrides={"CLOUD_WATCHDOG_CHAIN_NO_ADVANCE_TICKS": "2"},
    )

    assert result["CHAIN_HEALTH_STATUS"] == "ok"
    assert result["CHAIN_HEALTH_ARTIFACT_PATH"] == ""


def test_chain_health_no_advance_ignores_projected_blocked_plan() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    plan_name = "demo-plan"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {"current_state": "blocked", "iteration": 1},
        events_body=json.dumps({"kind": "phase_started", "phase": "execute"}) + "\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 2,
            "current_plan_name": plan_name,
            "last_state": "blocked",
            "pr_state": "open",
            "completed": [{"label": "m1"}],
        },
    )

    env = {"CLOUD_WATCHDOG_CHAIN_NO_ADVANCE_TICKS": "2"}
    assert _run_chain_health(ws, marker, repair_dir, env_overrides=env)["CHAIN_HEALTH_STATUS"] == "ok"
    events_path = ws / ".megaplan" / "plans" / plan_name / "events.ndjson"
    for i in range(3):
        events_path.write_text(
            events_path.read_text(encoding="utf-8") + json.dumps({"kind": "stderr", "i": i}) + "\n",
            encoding="utf-8",
        )
        result = _run_chain_health(ws, marker, repair_dir, env_overrides=env)
        assert result["CHAIN_HEALTH_STATUS"] == "ok"
        assert result["CHAIN_HEALTH_ARTIFACT_PATH"] == ""


def test_chain_health_no_advance_ignores_progressing_plan_events_without_active_step() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    plan_name = "demo-plan"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {"current_state": "finalized", "iteration": 1},
        events_body="\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 2,
            "current_plan_name": plan_name,
            "last_state": "finalized",
            "pr_state": "open",
            "completed": [{"label": "m1"}],
        },
    )

    env = {"CLOUD_WATCHDOG_CHAIN_NO_ADVANCE_TICKS": "2"}
    assert _run_chain_health(ws, marker, repair_dir, env_overrides=env)["CHAIN_HEALTH_STATUS"] == "ok"
    events_path = ws / ".megaplan" / "plans" / plan_name / "events.ndjson"
    for i in range(3):
        stamp = dt.datetime.now(dt.timezone.utc).isoformat()
        kind = "llm_call_start" if i == 0 else "llm_token_heartbeat"
        payload = {"kind": kind, "ts_utc": stamp}
        if kind == "llm_call_start":
            payload["payload"] = {"request_id": "req-1"}
        events_path.write_text(
            events_path.read_text(encoding="utf-8") + json.dumps(payload) + "\n",
            encoding="utf-8",
        )
        result = _run_chain_health(ws, marker, repair_dir, env_overrides=env)
        assert result["CHAIN_HEALTH_STATUS"] == "ok"
        assert result["CHAIN_HEALTH_ARTIFACT_PATH"] == ""


def test_plan_progress_stall_status_is_wired_into_launch_chain_tick() -> None:
    text = _wrapper("arnold-watchdog")

    assert "plan_progress_stall_status()" in text
    assert 'stall_health="$(plan_progress_stall_status "$workspace" "$run_kind" "$plan_name")"' in text
    # Progress stalls are unintended stops from the operator perspective; they
    # must launch repair instead of only surfacing as passive issues.
    assert 'repair_unintended_stop "$report_items" "$session" "$workspace" "$remote_spec" "$stall_health"' in text
    # The progress_stall status must NOT be in the alive-allowlist so it surfaces
    # in issues[] — the allowlist is the set excluded from issues.
    assert '"progress_stall"' not in text.split('not in {"alive"')[1].split("}")[0]


def test_watchdog_resolves_stale_remote_spec_before_repair_dispatch() -> None:
    text = _wrapper("arnold-watchdog")

    assert "resolve_existing_remote_spec()" in text
    assert 'payload["remote_spec"] = str(selected)' in text
    assert 'resolved_remote_spec="$(resolve_existing_remote_spec "$session" "$workspace" "$remote_spec" "$run_kind"' in text
    assert 'remote_spec="$resolved_remote_spec"' in text
    assert 'remote_spec_path="$resolved_remote_spec"' in text


def test_plan_progress_stall_status_flags_iteration_threshold() -> None:

    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    _write_plan(
        ws / ".megaplan" / "plans" / "m2-x",
        {
            "iteration": 9,
            "current_state": "blocked",
            "active_step": None,
            "latest_failure": {"kind": "stalled", "metadata": {"stall_count": 5, "iteration": 23}},
        },
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="{}\n",
    )
    out = _run_stall(ws, marker)
    assert out.startswith("progress_stall:m2-x")
    # The milestone iteration (23 from latest_failure.metadata) dominates the
    # top-level value and trips the >=8 threshold.
    assert "iteration=23>=8" in out
    assert "stall_count=5" in out


def test_plan_progress_stall_status_flags_attempt_threshold() -> None:

    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    _write_plan(
        ws / ".megaplan" / "plans" / "m1-y",
        {"iteration": 2, "current_state": "planning",
         "active_step": {"phase": "plan", "attempt": 11}},
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="{}\n",
    )
    out = _run_stall(ws, marker)
    assert "progress_stall:m1-y" in out
    assert "active_step.attempt=11>=10" in out


def test_watchdog_plan_helpers_use_named_single_plan_in_mixed_workspace() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    target = ws / ".megaplan" / "plans" / "target-plan"
    unrelated = ws / ".megaplan" / "plans" / "newer-unrelated"
    _write_plan(
        target,
        {
            "iteration": 1,
            "current_state": "planning",
            "active_step": {"phase": "plan", "attempt": 0},
            "history": [],
        },
        plan_v_bodies={"plan_v1.md": "target"},
        events_body="{}\n",
    )
    _write_plan(
        unrelated,
        {
            "iteration": 25,
            "current_state": "blocked",
            "active_step": {"phase": "execute", "attempt": 12},
            "latest_failure": {
                "kind": "phase_failed",
                "phase": "execute",
                "message": "unrelated failure should not be inspected",
            },
            "history": [{"step": "execute", "result": "error"}],
        },
        plan_v_bodies={"plan_v1.md": "unrelated"},
        events_body="{}\n",
    )
    old_ts = time.time() - 600
    new_ts = time.time()
    os.utime(target / "state.json", (old_ts, old_ts))
    os.utime(unrelated / "state.json", (new_ts, new_ts))

    assert _run_phase(ws, "plan", "target-plan") == "ok"
    assert _run_stall(ws, marker, run_kind="plan", plan_name="target-plan") == "ok"
    assert _run_phase(ws).startswith("phase_failure:newer-unrelated")
    assert _run_stall(ws, marker).startswith("progress_stall:newer-unrelated")


def test_plan_progress_stall_status_ok_for_healthy_plan() -> None:

    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    _write_plan(
        ws / ".megaplan" / "plans" / "m1-ok",
        {"iteration": 2, "current_state": "planning",
         "active_step": {"phase": "plan", "attempt": 1}},
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="{}\n",
    )
    assert _run_stall(ws, marker) == "ok"


def test_plan_progress_stall_status_persists_tick_over_tick_snapshot() -> None:

    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    plan_dir = ws / ".megaplan" / "plans" / "m-snap"
    _write_plan(
        plan_dir,
        {"iteration": 4, "current_state": "planning",
         "active_step": {"phase": "plan", "attempt": 0}},
        plan_v_bodies={"plan_v1.md": "v1", "plan_v2.md": "v2"},
        events_body="{}\n",
    )

    # First tick: healthy, snapshot written.
    assert _run_stall(ws, marker) == "ok"
    snap = marker / "m-snap.progress.json"
    assert snap.exists()
    first = json.loads(snap.read_text(encoding="utf-8"))
    assert first["iteration"] == 4
    assert first["plan_v_count"] == 2
    assert "ts" in first

    # Second tick: iteration advances, plan_v count unchanged -> unchanged_ticks
    # increments. With iteration still under threshold this stays ok, but the
    # snapshot must reflect the increment.
    (plan_dir / "state.json").write_text(
        json.dumps({"iteration": 5, "current_state": "planning",
                    "active_step": {"phase": "plan", "attempt": 0}}),
        encoding="utf-8",
    )
    _run_stall(ws, marker)
    second = json.loads(snap.read_text(encoding="utf-8"))
    assert second["unchanged_ticks"] == 1

    # Third tick: still unchanged -> trips the "no growth while iteration
    # advances" signal now that unchanged_ticks >= 2.
    (plan_dir / "state.json").write_text(
        json.dumps({"iteration": 6, "current_state": "planning",
                    "active_step": {"phase": "plan", "attempt": 0}}),
        encoding="utf-8",
    )
    out = _run_stall(ws, marker)
    assert "progress_stall:m-snap" in out
    assert "unchanged-2-ticks" in out


def test_plan_progress_stall_thresholds_are_env_tunable() -> None:

    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    _write_plan(
        ws / ".megaplan" / "plans" / "m-tune",
        {"iteration": 3, "current_state": "planning",
         "active_step": {"phase": "plan", "attempt": 0}},
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="{}\n",
    )
    # iteration=3 is below the default 8 -> ok.
    assert _run_stall(ws, marker) == "ok"
    # Lower the threshold to 2 -> trips.
    out = _run_stall(ws, marker, {"CLOUD_WATCHDOG_STALL_ITERATIONS": "2"})
    assert "progress_stall:m-tune" in out


def test_arnold_progress_auditor_wrapper_has_bash_n_syntax_and_contract() -> None:
    text = _wrapper("arnold-progress-auditor")

    # bash -n on the actual wrapper file.
    wrapper_path = WRAPPER_DIR / "arnold-progress-auditor"
    result = subprocess.run(
        ["bash", "-n", str(wrapper_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr}"

    # Host-side: docker-execs into the container like ensure-megaplan-watchdog.
    assert 'CONTAINER="${MEGAPLAN_CLOUD_CONTAINER:-megaplan-cloud-agent}"' in text
    assert "docker inspect" in text

    # In-container: iterates active markers, 5h window, deepseek dispatch.
    assert 'MARKER_DIR="${MEGAPLAN_AUDIT_MARKER_DIR:-/workspace/.megaplan/cloud-sessions}"' in text
    assert 'REPAIR_DATA_DIR="${MEGAPLAN_AUDIT_REPAIR_DATA_DIR:-$MARKER_DIR/repair-data}"' in text
    assert 'DISCOVER_BIN="${MEGAPLAN_AUDIT_DISCOVER_BIN:-$ARNOLD_SRC/arnold_pipelines/megaplan/cloud/wrappers/arnold-cloud-discover}"' in text
    assert 'AUDIT_WINDOW_HOURS="${MEGAPLAN_AUDIT_WINDOW_HOURS:-6}"' in text
    assert 'DEEPSEEK_MODEL="${MEGAPLAN_AUDIT_MODEL:-deepseek:deepseek-v4-pro}"' in text
    assert 'AUDIT_CODEX_MODEL="gpt-5.6-sol"' in text
    assert 'python3 -m arnold_pipelines.megaplan.managed_agent run \\' in text
    assert '-c model="$AUDIT_CODEX_MODEL"' in text
    assert '"$WATCHDOG_BIN" --audit-sweep' in text
    assert 'CLOUD_WATCHDOG_PROVIDER_RETRY_ONCE=1' in text
    assert '"recovery_sweep": recovery_sweep' in text
    assert 'SUBAGENT_PROFILE="${MEGAPLAN_AUDIT_SUBAGENT_PROFILE:-partnered-5}"' in text
    assert "launch_hermes_agent.py" in text
    assert '--model="$DEEPSEEK_MODEL"' in text
    # Report paths.
    assert 'REPORT_DIR="${MEGAPLAN_AUDIT_REPORT_DIR:-/workspace/audit-reports}"' in text
    assert 'REPORT_LOG="${MEGAPLAN_AUDIT_REPORT_LOG:-/workspace/audit-report.log}"' in text
    assert 'JSON_OUT="$REPORT_DIR/${TS}-audit.json"' in text
    assert 'MD_OUT="$REPORT_DIR/${TS}-audit.md"' in text
    # Evidence-citing required output shape.
    assert "hypothesis" in text
    assert "recommendation" in text
    assert "You are reconciling a cloud megaplan SESSION, not just one plan." in text
    assert "Reconciler findings:" in text
    assert "Primary evidence contract:" in text
    assert "Treat bounded incident brief and projection records as the source of truth." in text
    assert "Use live-process discovery, repair-data sidecars, tmux state, and watchdog archives only as corroboration." in text
    assert "Reconcile contradictions explicitly instead of letting corroboration override the ledger." in text
    assert "Superfixer health / repair-the-repairer" in text
    assert "pipeline friction map" in text
    assert "Treat all repair/autofix systems as intended to be enabled by default" in text
    assert "$REPAIR_DATA_DIR/<session>.repair-data.json" in text
    assert "$REPAIR_DATA_DIR/meta" in text
    assert "/workspace/.megaplan/meta-runs" in text
    assert "/root/.codex" in text
    assert "META_REPAIR_FAILURE" in text
    assert "arnold-meta-repair-loop actually launched" in text
    assert "periodic audit reviewer is read-only" in text
    assert "Return a typed repair request" in text
    assert "Fix the watchdog/repair-trigger/auditor source" in text
    assert "dead provider/auth path" in text
    assert "argument-size crash" in text
    assert "Do not patch the running workspace merely to" in text
    assert "make this one session green when the repairer is the broken component" in text
    assert "chain log line numbers" in text
    assert "Live failure vs stale state" in text
    assert "Gate resolvability" in text
    assert "stale_state_evidence" in text
    assert "latest_failure_is_stale" in text
    assert "stale_block_replay" in text
    assert "between_milestone_cycling" in text
    assert "STALE" in text
    assert "INEFFICIENT" in text


def test_progress_auditor_rejects_degenerate_dispatch_windows() -> None:
    text = _wrapper("arnold-progress-auditor")

    assert "math.isfinite(hours) and hours > 0" in text
    assert "a non-positive or non-finite window is a probe" in text
    assert "cannot establish health or suppress active repair custody" in text
    assert "exit 64" in text


def test_watchdog_exposes_serialized_audit_recovery_and_paused_guard() -> None:
    text = _wrapper("arnold-watchdog")

    assert 'if [[ "${1:-}" == "--audit-sweep" ]]' in text
    assert 'SCAN_LOCK_FILE="${CLOUD_WATCHDOG_SCAN_LOCK_FILE:-/workspace/.megaplan/watchdog-scan.lock}"' in text
    assert 'flock -w "$SCAN_LOCK_WAIT_SECS" "$scan_lock_fd"' in text
    assert 'CLOUD_WATCHDOG_PROVIDER_RETRY_ONCE' in text
    assert '"QUOTA", "CREDENTIAL_ACCOUNT"' in text
    assert '"${PLAN_STATUS_CURRENT_STATE:-}" == "paused"' in text
    assert '"paused" "durable plan state is paused; no runner expected until explicit resume"' in text


def test_all_recovery_wrappers_fail_closed_for_durable_operator_pause() -> None:
    repair = _wrapper("arnold-repair-loop")
    meta = _wrapper("arnold-meta-repair-loop")
    auditor = _wrapper("arnold-progress-auditor")
    assert "durable operator pause active; automatic repair skipped" in repair
    assert "durable operator pause active; superfixer skipped" in meta
    assert 'decision = "skip_paused"' in auditor


def test_watchdog_audit_recovery_does_not_invent_human_quota_gate() -> None:
    target = {
        "tmux_process": {"live_status": "stopped"},
        "plan_state": {
            "current_state": "executing",
            "resume_cursor": {"changed_file_count": 0},
            "fingerprint": "plan-quota",
            "mtime": 1.0,
        },
        "chain_state": {
            "last_state": "awaiting_human",
            "fingerprint": "chain-quota",
            "mtime": 1.0,
        },
        "needs_human": {
            "present": True,
            "summary": "provider rate limit",
            "gate_type": "quota",
        },
        "current_refs": {
            "current_plan_name": "demo-plan",
            "plan_current_state": "blocked",
        },
        "authoritative_source": "plan_state",
    }
    script = "\n".join(
        [
            _extract_wrapper_function_until(
                "resolver_needs_human_verdict", "route_resolver_machine_repair"
            ),
            f"SRC_DIR={str(REPO_ROOT)!r}",
            "LOG=/dev/null",
            "CLOUD_WATCHDOG_PROVIDER_RETRY_ONCE=1",
            "export CLOUD_WATCHDOG_PROVIDER_RETRY_ONCE",
            f"resolver_needs_human_verdict demo {json.dumps(target)!r}",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def _extract_auditor_worklist_program() -> str:
    text = _wrapper("arnold-progress-auditor")
    marker = (
        "python3 - \"$MARKER_DIR\" \"$WORKLIST\" \"$AUDIT_WINDOW_HOURS\" "
        "\"$DISCOVER_BIN\" \"$AUDIT_WORKSPACE_ROOT\" \"$ARNOLD_SRC\" <<'PY'"
    )
    start = text.index(marker)
    start = text.index("\n", start) + 1
    end = text.index("\nPY\n", start)
    return text[start:end]


def _extract_auditor_gather_program() -> str:
    text = _wrapper("arnold-progress-auditor")
    marker = "python3 - \"$WORKLIST\" \"$GATHER_DIR\" \"$AUDIT_WINDOW_HOURS\" \"$ARNOLD_SRC\" \"$stall_summary\" <<'PY'"
    start = text.index(marker)
    start = text.index("\n", start) + 1
    end = text.index("\nPY\n", start)
    return text[start:end]


def _run_auditor_worklist_builder(
    tmp_path: Path,
    *,
    marker_dir: Path,
    worklist: Path,
    window_hours: float,
    discover_bin: Path,
    workspace_root: Path,
    arnold_src: Path,
) -> list[dict]:
    program = _extract_auditor_worklist_program()
    prog_path = tmp_path / "_auditor_worklist.py"
    prog_path.write_text(program, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(prog_path),
            str(marker_dir),
            str(worklist),
            str(window_hours),
            str(discover_bin),
            str(workspace_root),
            str(arnold_src),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return [
        json.loads(line)
        for line in worklist.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_repair_runner_defaults_meta_loop_repairs_to_partnered_5() -> None:
    from arnold_pipelines.megaplan.watchdog.repair_runner import RepairRunner

    runner = RepairRunner(executable_search_path=[])
    assert runner._is_dry_run() is True
    # The megaplan-subcommand env pins partnered-5 as the default profile.
    env = runner._megaplan_subcommand_env({"PATH": "/bin"})
    assert env.get("MEGAPLAN_DEFAULT_PROFILE") == "partnered-5"
    assert env.get("MEGAPLAN_REPAIR_PROFILE") == "partnered-5"
    assert env.get("PYTHONSAFEPATH") == "1"
    # A caller-supplied default must win (setdefault semantics).
    env2 = runner._megaplan_subcommand_env(
        {"PATH": "/bin", "MEGAPLAN_DEFAULT_PROFILE": "apex"}
    )
    assert env2.get("MEGAPLAN_DEFAULT_PROFILE") == "apex"


def test_kimi_goal_operator_defaults_meta_loop_to_partnered_5_profile() -> None:
    text = _wrapper("arnold-kimi-goal-operator")

    assert 'DEFAULT_PROFILE="${KIMI_GOAL_DEFAULT_PROFILE:-partnered-5}"' in text
    assert 'export MEGAPLAN_DEFAULT_PROFILE="$DEFAULT_PROFILE"' in text
    assert 'export MEGAPLAN_REPAIR_PROFILE="$DEFAULT_PROFILE"' in text


def _run_auditor_with_mocked_deepseek(tmp_path: Path) -> dict:
    """Drive the in-container auditor python with a stubbed launcher.

    We synthesize a marker + a stalled plan, then call the auditor's gather +
    dispatch python in isolation by stubbing the hermes launcher with a script
    that emits a canned hypothesis. This proves the report path end-to-end
    without needing real DeepSeek credentials.
    """
    workspace = tmp_path / "ws"
    plans = workspace / ".megaplan" / "plans" / "m2-mock"
    plans.mkdir(parents=True)
    state = {
        "name": "m2-mock",
        "iteration": 8,
        "current_state": "blocked",
        "active_step": None,
        "latest_failure": {"kind": "stalled",
                           "message": "stalled at 'blocked' for 5 iterations",
                           "metadata": {"stall_count": 5, "iteration": 23}},
        "last_gate": {"recommendation": "ITERATE",
                      "rationale": "score regression 13.5 -> 3.0"},
        "meta": {"weighted_scores": [12.0, 7.0, 14.0, 13.5, 3.0],
                 "plan_deltas": [54.0, 9.0, 9.0, 43.0, 9.0],
                 "significant_counts": [8, 4, 9, 11, 2]},
        "history": [
            {"step": "gate", "result": "iterate", "timestamp": _iso_hours_ago(0.5)},
            {"step": "gate", "result": "iterate", "timestamp": _iso_hours_ago(1.5)},
            {"step": "gate", "result": "blocked", "timestamp": _iso_hours_ago(2.5)},
            {"step": "revise", "result": "success", "timestamp": _iso_hours_ago(0.2)},
        ],
    }
    (plans / "state.json").write_text(json.dumps(state), encoding="utf-8")
    for i, body in enumerate(["v1", "v2longer", "v3different", "v4", "v5"], start=1):
        (plans / f"plan_v{i}.md").write_text(body * (i * 100), encoding="utf-8")
    (plans / "events.ndjson").write_text("{}\n" * 10, encoding="utf-8")

    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    (marker_dir / "m2-mock.json").write_text(json.dumps({
        "session": "m2-mock", "workspace": str(workspace), "updated_at": _iso_hours_ago(0.1),
    }), encoding="utf-8")

    # Stub launcher that returns a canned hypothesis referencing the evidence.
    launcher = tmp_path / "launch_hermes_agent.py"
    canned = (
        "hypothesis: critique loop oscillating over cosmetic import wording; "
        "gate evaluator too strict for phase-0. recommend: tighten gate cosmetic flag."
    )
    launcher.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"print({canned!r})\n",
        encoding="utf-8",
    )
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # Reuse the auditor's python by extracting the gather + dispatch steps is
    # fragile; instead invoke the actual wrapper's inner python via a trimmed
    # copy that points at our tmp paths. We assert the report-construction
    # python produces the cited finding by running it against our gather dir.
    gather_dir = tmp_path / "gather"
    gather_dir.mkdir()
    worklist = tmp_path / "worklist"
    worklist.write_text(json.dumps({
        "name": "m2-mock", "plan": "m2-mock", "session": "m2-mock",
        "workspace": str(workspace), "updated": _iso_hours_ago(0.1), "sources": ["marker"],
    }) + "\n", encoding="utf-8")

    wrapper_text = _wrapper("arnold-progress-auditor")
    gather_prog = _extract_auditor_gather_program()
    (gather_dir / "gather.py").write_text(gather_prog, encoding="utf-8")

    env = dict(os.environ)
    r = subprocess.run(
        [sys.executable, str(gather_dir / "gather.py"), str(worklist),
         str(gather_dir), "5", str(workspace.parent), "none"],
        capture_output=True, text=True, env=env, check=False,
    )
    assert r.returncode == 0, f"gather failed: {r.stderr}"
    findings = json.loads((gather_dir / "findings.json").read_text(encoding="utf-8"))
    assert findings["findings"], "expected at least one suspicious finding"
    finding = findings["findings"][0]
    assert finding["plan"] == "m2-mock"
    reasons = " ".join(finding["reasons"])
    # Evidence-cited: plan churn + gate regression both present.
    assert "plan_v refreshed" in reasons
    assert "gate=ITERATE/blocked" in reasons

    # Now drive the report-assembly python against this finding with a canned
    # hypothesis (simulating the DeepSeek dispatch output).
    finding["deepseek_model"] = "deepseek:deepseek-v4-pro"
    finding["hypothesis"] = (
        "hypothesis: critique loop oscillating over cosmetic import wording; "
        "gate evaluator too strict for phase-0. recommend: tighten gate cosmetic flag."
    )
    (gather_dir / "findings.json").write_text(
        json.dumps({"window_hours": 5, "stall_summary": "none",
                    "findings": [finding]}),
        encoding="utf-8",
    )

    # Extract report-assembly python.
    a_marker = "python3 - \"$GATHER_DIR/findings.json\" \"$JSON_OUT\" \"$MD_OUT\" \"$REPORT_LOG\" \"$TS\""
    a_start = wrapper_text.index(a_marker)
    a_start = wrapper_text.index("\n", a_start) + 1
    a_end = wrapper_text.index("\nPY\n", a_start)
    asm_prog = wrapper_text[a_start:a_end]
    json_out = tmp_path / "out.json"
    md_out = tmp_path / "out.md"
    log_path = tmp_path / "audit.log"
    recovery_evidence = tmp_path / "recovery-evidence.json"
    recovery_evidence.write_text(
        json.dumps({"enabled": False, "decisions": []}), encoding="utf-8"
    )
    asm = gather_dir / "asm.py"
    asm.write_text(asm_prog, encoding="utf-8")
    r2 = subprocess.run(
        [sys.executable, str(asm), str(gather_dir / "findings.json"),
         str(json_out), str(md_out), str(log_path), "TESTTS", "0", "0",
         str(recovery_evidence), "gpt-test"],
        capture_output=True, text=True, env=env, check=False,
    )
    assert r2.returncode == 0, f"report asm failed: {r2.stderr}"
    report = json.loads(json_out.read_text(encoding="utf-8"))
    assert report["finding_count"] == 1
    assert report["deepseek_model"] == "deepseek:deepseek-v4-pro"
    md = md_out.read_text(encoding="utf-8")
    assert "m2-mock" in md
    assert "hypothesis:" in md
    assert "tighten gate cosmetic flag" in md
    # Log append is a single greppable line.
    log_line = log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    assert "findings=1" in log_line
    assert "m2-mock" in log_line
    return report


def _iso_hours_ago(hours: float) -> str:
    when = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    return when.isoformat().replace("+00:00", "Z")


def test_auditor_worklist_unions_marker_tmux_and_workspace_activity_and_skips_arnold(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    arnold_src = workspace_root / "arnold"
    (arnold_src / ".megaplan" / "plans" / "should-not-scan").mkdir(parents=True)

    chain_ws = workspace_root / "vibecomfy-god-file-splits"
    bootstrap_ws = workspace_root / "vibecomfy-per-workflow-window-chat-20260628"
    done_ws = workspace_root / "python-shaped-workflow-authoring"
    plan_marker_ws = workspace_root / "single-plan-marker-workspace"
    for ws in (chain_ws, bootstrap_ws, done_ws, plan_marker_ws):
        (ws / ".megaplan" / "plans").mkdir(parents=True)

    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    (marker_dir / "chain-session.json").write_text(
        json.dumps({"session": "chain-session", "workspace": str(chain_ws), "updated_at": _iso_hours_ago(0.2)}),
        encoding="utf-8",
    )
    (marker_dir / "single-plan-session.json").write_text(
        json.dumps(
            {
                "session": "single-plan-session",
                "workspace": str(plan_marker_ws),
                "run_kind": "plan",
                "plan_name": "target-plan",
                "updated_at": _iso_hours_ago(0.2),
            }
        ),
        encoding="utf-8",
    )

    def write_recent_plan(workspace: Path, name: str, *, state_recent: bool = True, events_recent: bool = False) -> None:
        plan_dir = workspace / ".megaplan" / "plans" / name
        state = {"name": name, "current_state": "done", "history": [], "meta": {}}
        _write_plan(plan_dir, state, plan_v_bodies={"plan_v1.md": "v1"}, events_body="{}\n" if events_recent else "")
        recent_ts = time.time() - 300
        stale_ts = time.time() - (9 * 3600)
        state_path = plan_dir / "state.json"
        events_path = plan_dir / "events.ndjson"
        os.utime(state_path, (recent_ts if state_recent else stale_ts, recent_ts if state_recent else stale_ts))
        if events_path.exists():
            os.utime(events_path, (recent_ts if events_recent else stale_ts, recent_ts if events_recent else stale_ts))

    write_recent_plan(chain_ws, "m2-chain", state_recent=True)
    write_recent_plan(bootstrap_ws, "m1-bootstrap", state_recent=False, events_recent=True)
    write_recent_plan(done_ws, "m5-done", state_recent=False, events_recent=True)
    write_recent_plan(done_ws, "m6-done", state_recent=True, events_recent=False)
    write_recent_plan(plan_marker_ws, "target-plan", state_recent=False, events_recent=False)
    write_recent_plan(plan_marker_ws, "stale-unrelated", state_recent=False, events_recent=False)
    write_recent_plan(arnold_src, "should-not-scan", state_recent=True)

    discover_bin = tmp_path / "discover_stub.sh"
    discover_bin.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        f"bootstrap-session\t{bootstrap_ws}\t.megaplan/initiatives/bootstrap/briefs/bootstrap.md\tplan\tm1-bootstrap\tignored\n"
        f"chain-session-live\t{chain_ws}\t/tmp/spec.yaml\tchain\t\tignored\n"
        "EOF\n",
        encoding="utf-8",
    )
    discover_bin.chmod(discover_bin.stat().st_mode | stat.S_IXUSR)

    worklist = tmp_path / "worklist.jsonl"
    entries = _run_auditor_worklist_builder(
        tmp_path,
        marker_dir=marker_dir,
        worklist=worklist,
        window_hours=6,
        discover_bin=discover_bin,
        workspace_root=workspace_root,
        arnold_src=arnold_src,
    )

    observed = {(entry["workspace"], entry["plan"]): set(entry["sources"]) for entry in entries}
    assert (str(chain_ws), "m2-chain") in observed
    assert observed[(str(chain_ws), "m2-chain")] == {"marker", "tmux", "workspace_activity"}
    assert (str(bootstrap_ws), "m1-bootstrap") in observed
    assert observed[(str(bootstrap_ws), "m1-bootstrap")] == {"tmux", "workspace_activity"}
    assert (str(done_ws), "m5-done") in observed
    assert observed[(str(done_ws), "m5-done")] == {"workspace_activity"}
    assert (str(done_ws), "m6-done") in observed
    assert observed[(str(done_ws), "m6-done")] == {"workspace_activity"}
    assert (str(plan_marker_ws), "target-plan") in observed
    assert observed[(str(plan_marker_ws), "target-plan")] == {"marker"}
    assert (str(plan_marker_ws), "stale-unrelated") not in observed
    assert all(entry["workspace"] != str(arnold_src) for entry in entries)


def test_auditor_gather_includes_done_plan_with_recent_events_mtime(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    plan_dir = workspace / ".megaplan" / "plans" / "m6-done"
    state = {
        "name": "m6-done",
        "iteration": 1,
        "current_state": "done",
        "active_step": {"phase": "review", "attempt": 8},
        "latest_failure": {"kind": "stalled", "message": "stale failure record"},
        "last_gate": {"recommendation": "PASS"},
        "meta": {"weighted_scores": [7.0, 6.0, 4.0], "plan_deltas": [1.0, 1.0, 1.0], "significant_counts": [1, 1, 1]},
        "history": [
            {"step": "gate", "result": "iterate", "timestamp": _iso_hours_ago(1.0)},
            {"step": "gate", "result": "iterate", "timestamp": _iso_hours_ago(2.0)},
            {"step": "gate", "result": "blocked", "timestamp": _iso_hours_ago(3.0)},
        ],
    }
    _write_plan(plan_dir, state, plan_v_bodies={"plan_v1.md": "v1"}, events_body="{}\n{}\n")
    stale_ts = time.time() - (9 * 3600)
    recent_ts = time.time() - 120
    os.utime(plan_dir / "state.json", (stale_ts, stale_ts))
    os.utime(plan_dir / "events.ndjson", (recent_ts, recent_ts))

    gather_dir = tmp_path / "gather"
    gather_dir.mkdir()
    worklist = tmp_path / "worklist.jsonl"
    worklist.write_text(
        json.dumps(
            {
                "workspace": str(workspace),
                "plan": "m6-done",
                "session": "done-session",
                "sources": ["workspace_activity"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    gather_prog = _extract_auditor_gather_program()
    gather_path = gather_dir / "gather.py"
    gather_path.write_text(gather_prog, encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(gather_path),
            str(worklist),
            str(gather_dir),
            "6",
            str(tmp_path),
            "none",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    findings = json.loads((gather_dir / "findings.json").read_text(encoding="utf-8"))["findings"]
    assert findings, "expected done plan with recent events mtime to be included"
    assert findings[0]["plan"] == "m6-done"
    assert findings[0]["session"] == "done-session"
    assert findings[0]["sources"] == ["workspace_activity"]


def test_auditor_gather_includes_chain_repair_stderr_and_user_action_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    plan_name = "m7-demo"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    state = {
        "name": plan_name,
        "iteration": 21,
        "current_state": "finalized",
        "active_step": {"phase": "execute", "attempt": 2},
        "latest_failure": {
            "kind": "phase_failed",
            "message": "phase 'execute' internal_error",
            "phase": "execute",
            "recorded_at": _iso_hours_ago(2.0),
            "metadata": {
                "exit_code": 2,
                "stderr": "__main__.py: error: unrecognized arguments: --confirm-destructive --user-approved",
            },
        },
        "last_gate": {"recommendation": "PASS"},
        "meta": {
            "weighted_scores": [8.0],
            "plan_deltas": [1.0],
            "significant_counts": [1],
            "user_action_resolutions": {
                "ua-02-cleanup-policy": {"state": "satisfied", "decision": "proceed"}
            },
        },
        "history": [
            {
                "step": "execute",
                "result": "blocked",
                "timestamp": _iso_hours_ago(1.0),
                "duration_ms": 0,
                "artifact_hash": "sha256:stale-block",
                "output_file": "execution.json",
            },
            {
                "step": "execute",
                "result": "blocked",
                "timestamp": _iso_hours_ago(0.5),
                "duration_ms": 0,
                "artifact_hash": "sha256:stale-block",
                "output_file": "execution.json",
            },
        ],
    }
    _write_plan(
        plan_dir,
        state,
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="\n".join(
            [
                json.dumps(
                    {
                        "seq": 1,
                        "kind": "phase_end",
                        "phase": "execute",
                        "ts_utc": _iso_hours_ago(1.5),
                        "payload": {"phase": "execute", "exit_kind": "success"},
                    }
                ),
                json.dumps(
                    {
                        "seq": 2,
                        "kind": "gate",
                        "phase": "gate",
                        "ts_utc": _iso_hours_ago(1.0),
                        "payload": {"recommendation": "PROCEED"},
                    }
                ),
            ]
        )
        + "\n",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "user_actions": [
                    {
                        "id": "ua-01-reclassify-deletion-targets",
                        "phase": "before_execute",
                        "blocks_task_ids": ["m7-06-runtime-deletion-target-purge"],
                        "rationale": "Maintainer must confirm authoritative deletion targets.",
                    },
                    {
                        "id": "ua-02-cleanup-policy",
                        "phase": "before_execute",
                        "blocks_task_ids": ["m7-07-pipeline-deletion-target-purge"],
                        "rationale": "Cleanup policy choice.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "user_actions.md").write_text(
        "# User Actions\n\n"
        "- **ua-01-reclassify-deletion-targets**: Confirm deletion targets.\n"
        "- **ua-02-cleanup-policy**: Cleanup policy.\n",
        encoding="utf-8",
    )

    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    (chain_dir / "chain-demo.json").write_text(
        json.dumps(
            {
                "current_milestone_index": 6,
                "current_plan_name": plan_name,
                "last_state": "awaiting_human",
                "pr_number": 122,
                "pr_state": "open",
                "completed": [
                    {
                        "label": "m6-installed-artifacts",
                        "plan": "m6-demo",
                        "status": "done",
                        "pr_number": 121,
                        "pr_state": "merged",
                        "full_suite_backstop": {
                            "status": "failed",
                            "blocks": False,
                            "failed": 3,
                            "delta_computed": True,
                        },
                    }
                ],
                "events": [{"msg": "milestone m7 starting"}, {"msg": "awaiting_human"}],
            }
        ),
        encoding="utf-8",
    )
    (workspace / ".megaplan" / "cloud-chain-demo-session.log").write_text(
        "\n".join(
            [
                "[chain] milestone m7 starting",
                "[chain] terminal state reached: done",
                "[chain] status: stopped reason=milestone m7 ended awaiting_human",
                "[chain] milestone m7 starting",
                "[chain] terminal state reached: done",
                "[chain] status: stopped reason=milestone m7 ended awaiting_human",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    repair_data_dir = tmp_path / "repair-data"
    repair_data_dir.mkdir()
    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "outcome": "repairing",
                "iterations": [
                    {
                        "i": 1,
                        "mechanical_launch": "failed:awaiting_human",
                        "chain_state_summary": {"current_plan_name": plan_name, "last_state": "awaiting_human"},
                        "plan_latest_failure": {
                            "kind": "phase_failed",
                            "message": "phase 'execute' internal_error",
                            "metadata": {"stderr": "__main__.py: error: unrecognized arguments: --confirm-destructive"},
                        },
                    },
                    {
                        "i": 2,
                        "mechanical_launch": "failed:awaiting_human",
                        "chain_state_summary": {"current_plan_name": plan_name, "last_state": "awaiting_human"},
                        "plan_latest_failure": {
                            "kind": "phase_failed",
                            "message": "phase 'execute' internal_error",
                            "metadata": {"stderr": "__main__.py: error: unrecognized arguments: --confirm-destructive"},
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    gather_dir = tmp_path / "gather"
    gather_dir.mkdir()
    worklist = tmp_path / "worklist.jsonl"
    worklist.write_text(
        json.dumps(
            {
                "workspace": str(workspace),
                "plan": plan_name,
                "session": "demo-session",
                "kind": "chain",
                "remote_spec": str(workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"),
                "launch_command": "python3 -P -m arnold_pipelines.megaplan chain start --spec demo",
                "log": str(workspace / ".megaplan" / "cloud-chain-demo-session.log"),
                "sources": ["marker"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    gather_path = gather_dir / "gather.py"
    gather_path.write_text(_extract_auditor_gather_program(), encoding="utf-8")
    env = dict(os.environ)
    env["MEGAPLAN_AUDIT_REPAIR_DATA_DIR"] = str(repair_data_dir)
    result = subprocess.run(
        [sys.executable, str(gather_path), str(worklist), str(gather_dir), "6", str(tmp_path), "none"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    findings = json.loads((gather_dir / "findings.json").read_text(encoding="utf-8"))["findings"]
    assert findings, "expected chain-level signals to produce a suspicious finding"
    finding = findings[0]
    assert finding["session_header"]["kind"] == "chain"
    assert finding["chain_log"]["path"].endswith("cloud-chain-demo-session.log")
    assert "L6: [chain] status: stopped" in finding["chain_log"]["tail"]
    assert any(item["signature"] == "awaiting_human" and item["count"] == 2 for item in finding["chain_log"]["repetition_summary"])
    assert finding["chain_state_summary"]["current"]["last_state"] == "awaiting_human"
    assert finding["chain_state_summary"]["current"]["completed_count"] == 1
    assert finding["repair_data_summary"]["iteration_count"] == 2
    assert finding["repair_data_summary"]["repeated_failure_signatures"][0]["count"] == 2
    assert "unrecognized arguments" in finding["plan_latest_failure"]["metadata"]["stderr"]
    stale = finding["stale_state_evidence"]
    assert stale["latest_failure_is_stale"] is True
    assert stale["last_success_after_failure"]
    assert stale["last_success_after_failure_event"]["kind"] == "gate"
    assert stale["stale_block_replay"] is True
    assert stale["stale_block_replay_hash"] == "sha256:stale-block"
    assert finding["latest_failure_is_stale"] is True
    assert finding["stale_block_replay"] is True
    user_action_context = finding["user_action_context"]
    assert "ua-01-reclassify-deletion-targets" in user_action_context["user_actions_md"]
    assert [item["id"] for item in user_action_context["unresolved_user_actions"]] == ["ua-01-reclassify-deletion-targets"]
    reasons = " ".join(finding["reasons"])
    assert "chain last_state=awaiting_human" in reasons
    assert "chain log repeats" in reasons
    assert "repair data has 2 repair iterations" in reasons
    assert "unresolved user actions" in reasons
    assert "latest_failure is stale" in reasons
    assert "stale block replay" in reasons


def test_auditor_gather_flags_dead_active_step_worker_pid(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    plan_name = "ghost-worker-demo"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    _write_plan(
        plan_dir,
        {
            "name": plan_name,
            "iteration": 0,
            "current_state": "initialized",
            "created_at": _iso_hours_ago(0.25),
            "active_step": {
                "phase": "prep",
                "attempt": 1,
                "worker_pid": 99999999,
            },
        },
        events_body=json.dumps({"kind": "llm_token_heartbeat", "phase": "prep"}) + "\n",
    )

    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    (chain_dir / "chain-demo.json").write_text(
        json.dumps(
            {
                "current_milestone_index": 0,
                "current_plan_name": plan_name,
                "last_state": "initialized",
                "pr_state": "open",
                "completed": [],
            }
        ),
        encoding="utf-8",
    )

    gather_dir = tmp_path / "gather"
    gather_dir.mkdir()
    worklist = tmp_path / "worklist.jsonl"
    worklist.write_text(
        json.dumps(
            {
                "workspace": str(workspace),
                "plan": plan_name,
                "session": "ghost-worker-session",
                "kind": "chain",
                "remote_spec": str(workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"),
                "launch_command": "python3 -P -m arnold_pipelines.megaplan chain start --spec demo",
                "log": str(workspace / ".megaplan" / "cloud-chain-ghost-worker-session.log"),
                "sources": ["marker"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    gather_path = gather_dir / "gather.py"
    gather_path.write_text(_extract_auditor_gather_program(), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(gather_path), str(worklist), str(gather_dir), "6", str(tmp_path), "none"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    findings = json.loads((gather_dir / "findings.json").read_text(encoding="utf-8"))["findings"]
    assert findings, "expected dead active_step worker pid to produce a finding"
    finding = findings[0]
    assert finding["active_step_liveness"]["worker_pid"] == "99999999"
    assert finding["active_step_liveness"]["worker_pid_alive"] is False
    assert "plan_active_step_ghost_worker" in " ".join(finding["reasons"])


def test_progress_auditor_dispatch_redacts_brief_and_codex_response_files(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    gather_dir = tmp_path / "gather"
    gather_dir.mkdir()
    gather_file = gather_dir / "finding.json"
    gather_file.write_text(
        json.dumps(
            {
                "plan": "m7-demo",
                "workspace": str(workspace),
                "reasons": ["Authorization: Bearer bearer-secret-token-value"],
                "session_header": {"kind": "chain"},
                "plan_latest_failure": {
                    "kind": "phase_failed",
                    "metadata": {"stderr": "Authorization: Bearer bearer-secret-token-value"},
                },
            }
        ),
        encoding="utf-8",
    )

    codex = tmp_path / "codex"
    codex.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\"\n"
        "cat\n"
        "printf '%s\\n' 'stderr Authorization: Bearer bearer-secret-token-value' >&2\n",
        encoding="utf-8",
    )
    codex.chmod(codex.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_auditor_function("redact_inline_text"),
            _extract_auditor_function("redact_file_in_place"),
            _extract_auditor_function("log"),
            _extract_auditor_function("dispatch_one"),
            f"ARNOLD_SRC={shlex.quote(str(REPO_ROOT))}",
            f"GATHER_DIR={shlex.quote(str(gather_dir))}",
            "DEEPSEEK_MODEL=deepseek:deepseek-v4-pro",
            "SUBAGENT_PROFILE=partnered-5",
            "AUDIT_CODEX_MODEL=gpt-5.6-sol",
            "AUDIT_REVIEW_BRIEF_MAX_BYTES=131072",
            "AUDIT_REVIEW_EVIDENCE_MAX_BYTES=65536",
            "CODEX_TIMEOUT=30",
            "dispatch_one " + shlex.quote(str(gather_file)),
        ]
    )
    env = dict(os.environ)
    env["PATH"] = f"{tmp_path}:{env.get('PATH', '')}"
    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, env=env, check=False)

    assert result.returncode == 0, result.stderr
    brief = (gather_dir / "brief-m7-demo.md").read_text(encoding="utf-8")
    resp = (gather_dir / "resp-m7-demo.txt").read_text(encoding="utf-8")
    err = (gather_dir / "resp-m7-demo.err").read_text(encoding="utf-8")
    assert "bearer-secret-token-value" not in brief
    assert "bearer-secret-token-value" not in resp
    assert "bearer-secret-token-value" not in err
    assert REDACTION in brief


def test_repair_loop_stops_recurring_retry_for_prep_clarification_gate(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps(
            {
                "run_recurrence_detected": True,
                "current_recurrence": {"detected": True},
                "current_failure_context": {
                    "plan_runtime_state": {
                        "current_state": "awaiting_human_verify",
                        "clarification_source": "prep",
                        "clarification_question_count": 3,
                    },
                    "user_action_context": {"unresolved_user_actions": []},
                },
            }
        ),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "repair_exhausted_should_retry_without_human",
        "python3 - \"$DATA_FILE\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0"


def test_repair_loop_stops_recurring_retry_for_stale_awaiting_human_context(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps(
            {
                "run_recurrence_detected": True,
                "current_recurrence": {"detected": True},
                "current_failure_context": {
                    "failure_classification": "timeout_or_hang",
                    "plan_runtime_state": {"current_state": "awaiting_human_verify"},
                    "user_action_context": {"unresolved_user_actions": []},
                },
            }
        ),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "repair_exhausted_should_retry_without_human",
        "python3 - \"$DATA_FILE\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0"


def test_auditor_gather_flags_plan_stale_block_without_chain_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    plan_name = "single-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    _write_plan(
        plan_dir,
        {
            "name": plan_name,
            "iteration": 4,
            "current_state": "blocked",
            "active_step": None,
            "latest_failure": {
                "kind": "execution_blocked",
                "message": "blocked replay",
                "phase": "execute",
            },
            "last_gate": {"recommendation": "PASS"},
            "meta": {"weighted_scores": [8.0], "plan_deltas": [1.0], "significant_counts": [1]},
            "history": [
                {
                    "step": "execute",
                    "result": "blocked",
                    "timestamp": _iso_hours_ago(1.0),
                    "duration_ms": 0,
                    "artifact_hash": "sha256:plan-stale",
                    "output_file": "execution.json",
                },
                {
                    "step": "execute",
                    "result": "blocked",
                    "timestamp": _iso_hours_ago(0.5),
                    "duration_ms": 0,
                    "artifact_hash": "sha256:plan-stale",
                    "output_file": "execution.json",
                },
            ],
        },
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="{}\n",
    )

    gather_dir = tmp_path / "gather"
    gather_dir.mkdir()
    worklist = tmp_path / "worklist.jsonl"
    worklist.write_text(
        json.dumps(
            {
                "workspace": str(workspace),
                "plan": plan_name,
                "session": "single-plan-session",
                "kind": "plan",
                "plan_name": plan_name,
                "sources": ["marker"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    gather_path = gather_dir / "gather.py"
    gather_path.write_text(_extract_auditor_gather_program(), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(gather_path), str(worklist), str(gather_dir), "6", str(tmp_path), "none"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    findings = json.loads((gather_dir / "findings.json").read_text(encoding="utf-8"))["findings"]
    assert findings, "expected plan-level stale block replay to produce a finding"
    finding = findings[0]
    assert finding["session_header"]["kind"] == "plan"
    assert finding["chain_log"]["path"] == ""
    assert finding["chain_state_summary"]["current"] == {}
    stale = finding["stale_state_evidence"]
    assert stale["stale_block_replay"] is True
    assert stale["stale_block_replay_hash"] == "sha256:plan-stale"
    assert stale["between_milestone_cycling"] is False
    assert "stale block replay" in " ".join(finding["reasons"])


def test_auditor_gather_flags_between_milestone_cycling(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    plan_name = "m3-demo"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    _write_plan(
        plan_dir,
        {
            "name": plan_name,
            "iteration": 3,
            "current_state": "finalized",
            "active_step": None,
            "last_gate": {"recommendation": "PASS"},
            "meta": {"weighted_scores": [8.0], "plan_deltas": [1.0], "significant_counts": [1]},
            "history": [],
        },
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="{}\n",
    )

    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    (chain_dir / "chain-demo.json").write_text(
        json.dumps(
            {
                "current_milestone_index": 2,
                "current_plan_name": plan_name,
                "last_state": "stopped",
                "completed": [
                    {"label": "m1", "plan": "m1-demo", "status": "done"},
                    {"label": "m2", "plan": "m2-demo", "status": "done"},
                ],
                "milestones": [{"label": "m1"}, {"label": "m2"}, {"label": "m3"}],
                "events": [{"msg": "m1 done"}, {"msg": "m2 done"}],
            }
        ),
        encoding="utf-8",
    )
    log_path = workspace / ".megaplan" / "cloud-chain-demo-session.log"
    log_path.write_text(
        "\n".join(
            [
                "[chain] milestone m1 starting",
                "[chain] terminal state reached: done",
                "[chain] status: stopped reason=completed one milestone: m1",
                "[chain] milestone m2 starting",
                "[chain] terminal state reached: done",
                "[chain] status: stopped reason=completed one milestone: m2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    gather_dir = tmp_path / "gather"
    gather_dir.mkdir()
    worklist = tmp_path / "worklist.jsonl"
    worklist.write_text(
        json.dumps(
            {
                "workspace": str(workspace),
                "plan": plan_name,
                "session": "demo-session",
                "kind": "chain",
                "log": str(log_path),
                "sources": ["marker"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    gather_path = gather_dir / "gather.py"
    gather_path.write_text(_extract_auditor_gather_program(), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(gather_path), str(worklist), str(gather_dir), "6", str(tmp_path), "none"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    findings = json.loads((gather_dir / "findings.json").read_text(encoding="utf-8"))["findings"]
    assert findings, "expected between-milestone cycling to produce a finding"
    finding = findings[0]
    stale = finding["stale_state_evidence"]
    assert stale["between_milestone_cycling"] is True
    assert stale["one_milestone_stop_cycle_count"] == 2
    assert finding["between_milestone_cycling"] is True
    assert "between-milestone cycling" in " ".join(finding["reasons"])


def test_auditor_gather_surfaces_missing_meta_repair_run_for_triggered_session(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    plan_name = "m4-demo"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    _write_plan(
        plan_dir,
        {
            "name": plan_name,
            "iteration": 4,
            "current_state": "blocked",
            "active_step": None,
            "latest_failure": {
                "kind": "stalled",
                "message": "stalled at blocked",
                "recorded_at": _iso_hours_ago(1.0),
            },
            "last_gate": {"recommendation": "ITERATE"},
            "meta": {"weighted_scores": [5.0, 4.0, 3.0], "plan_deltas": [1.0], "significant_counts": [1]},
            "history": [
                {"step": "gate", "result": "iterate", "timestamp": _iso_hours_ago(1.0)},
                {"step": "gate", "result": "iterate", "timestamp": _iso_hours_ago(2.0)},
                {"step": "gate", "result": "blocked", "timestamp": _iso_hours_ago(3.0)},
            ],
        },
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="{}\n",
    )

    repair_data_dir = tmp_path / "repair-data"
    repair_data_dir.mkdir()
    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "outcome": "repair_exhausted",
                "attempts": [
                    {"attempt_id": 1, "failure_classification": "timeout_or_hang"},
                    {"attempt_id": 2, "failure_classification": "timeout_or_hang"},
                    {"attempt_id": 3, "failure_classification": "timeout_or_hang"},
                ],
                "iterations": [],
            }
        ),
        encoding="utf-8",
    )

    gather_dir = tmp_path / "gather"
    gather_dir.mkdir()
    worklist = tmp_path / "worklist.jsonl"
    worklist.write_text(
        json.dumps(
            {
                "workspace": str(workspace),
                "plan": plan_name,
                "session": "demo-session",
                "kind": "chain",
                "sources": ["marker"],
                "session_evidence_scope": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    gather_path = gather_dir / "gather.py"
    gather_path.write_text(_extract_auditor_gather_program(), encoding="utf-8")
    env = dict(os.environ)
    env["MEGAPLAN_AUDIT_REPAIR_DATA_DIR"] = str(repair_data_dir)
    env["MEGAPLAN_AUDIT_META_RUN_DIR"] = str(tmp_path / "meta-runs")
    result = subprocess.run(
        [sys.executable, str(gather_path), str(worklist), str(gather_dir), "6", str(tmp_path), "none"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    findings = json.loads((gather_dir / "findings.json").read_text(encoding="utf-8"))["findings"]
    assert findings, "expected missing meta-repair run to produce a finding"
    finding = findings[0]
    meta_summary = finding["meta_repair_summary"]
    assert meta_summary["should_dispatch"] is True
    assert meta_summary["trigger"] in {"repair_timeout", "persistent_recurring_retry"}
    assert meta_summary["missing_meta_run_evidence"] is True
    assert meta_summary["meta_record_count"] == 0
    assert meta_summary["meta_run_log_count"] == 0
    assert "meta-repair trigger" in " ".join(finding["reasons"])


def test_auditor_gather_retains_recent_l2_sandbox_failure_after_later_runs(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    plan_name = "m4-sandbox-retro"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    _write_plan(
        plan_dir,
        {
            "name": plan_name,
            "iteration": 4,
            "current_state": "blocked",
            "active_step": None,
            "latest_failure": {
                "kind": "stalled",
                "message": "ordinary repair exhausted",
                "recorded_at": _iso_hours_ago(1.0),
            },
        },
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="{}\n",
    )
    repair_data_dir = tmp_path / "repair-data"
    repair_data_dir.mkdir()
    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "outcome": "repair_exhausted",
                "attempts": [
                    {"attempt_id": index, "failure_classification": "timeout_or_hang"}
                    for index in range(1, 4)
                ],
            }
        ),
        encoding="utf-8",
    )
    meta_runs = tmp_path / "meta-runs"
    meta_runs.mkdir()
    failed = meta_runs / "20260715T010000Z-demo-session-investigator-receipt.json"
    failed.write_text(
        json.dumps(
            {
                "failure_code": "investigator_read_sandbox_unavailable",
                "observed_error": "bwrap: No permissions to create new namespace",
            }
        ),
        encoding="utf-8",
    )
    for index in range(6):
        path = meta_runs / f"20260715T02{index:02d}00Z-demo-session-success-{index}.log"
        path.write_text("accepted L2 verdict\n", encoding="utf-8")
        advanced_mtime = failed.stat().st_mtime + index + 1
        os.utime(path, (advanced_mtime, advanced_mtime))
    for index in range(2):
        path = meta_runs / f"20260715T030{index}00Z-demo-session-invalid-{index}.log"
        path.write_text(
            (
                "[meta-repair 2026-07-15T03:00:00+00:00] "
                "L2 investigation failed or returned no valid receipt; "
                "refusing all repair mutation\n"
                if index == 0
                else (
                    "[meta-repair 2026-07-15T03:01:00+00:00] "
                    "L2 investigator failed or returned no valid receipt\n"
                )
            ),
            encoding="utf-8",
        )
        advanced_mtime = failed.stat().st_mtime + 10 + index
        os.utime(path, (advanced_mtime, advanced_mtime))
    authority_blocked = meta_runs / "20260715T031000Z-demo-session-authority.log"
    authority_blocked.write_text(
        "[meta-repair 2026-07-15T03:10:00+00:00] observed: "
        "L2 Codex dispatch blocked by master-plus-path authorization gate\n",
        encoding="utf-8",
    )
    advanced_mtime = failed.stat().st_mtime + 20
    os.utime(authority_blocked, (advanced_mtime, advanced_mtime))

    gather_dir = tmp_path / "gather"
    gather_dir.mkdir()
    worklist = tmp_path / "worklist.jsonl"
    worklist.write_text(
        json.dumps(
            {
                "workspace": str(workspace),
                "plan": plan_name,
                "session": "demo-session",
                "kind": "chain",
                "sources": ["marker"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    gather_path = gather_dir / "gather.py"
    gather_path.write_text(_extract_auditor_gather_program(), encoding="utf-8")
    env = dict(os.environ)
    env["MEGAPLAN_AUDIT_REPAIR_DATA_DIR"] = str(repair_data_dir)
    env["MEGAPLAN_AUDIT_META_RUN_DIR"] = str(meta_runs)
    result = subprocess.run(
        [sys.executable, str(gather_path), str(worklist), str(gather_dir), "6", str(tmp_path), "none"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    finding = json.loads(
        (gather_dir / "findings.json").read_text(encoding="utf-8")
    )["findings"][0]
    meta_summary = finding["meta_repair_summary"]
    failure_refs = [
        item for item in meta_summary["meta_run_refs"] if item.get("failure_code")
    ]
    assert {item["failure_code"] for item in failure_refs} == {
        "investigator_invalid_or_missing_receipt",
        "investigator_read_sandbox_unavailable",
        "meta_repair_authority_blocked",
    }
    assert meta_summary["failed_meta_run_count"] == 1
    assert meta_summary["meta_run_refs"][0]["failure_code"] == (
        "meta_repair_authority_blocked"
    )


def test_auditor_gather_flags_running_repair_without_attempt_context(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    plan_name = "m1-demo"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    _write_plan(
        plan_dir,
        {
            "name": plan_name,
            "iteration": 0,
            "current_state": "initialized",
            "active_step": None,
            "latest_failure": {
                "kind": "phase_failed",
                "message": "worker_structural_audit_failed: type_mismatch at /suggested_approach",
                "recorded_at": _iso_hours_ago(1.0),
            },
            "history": [{"step": "init", "result": "success", "timestamp": _iso_hours_ago(7.0)}],
        },
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="{}\n",
    )

    repair_data_dir = tmp_path / "repair-data"
    repair_data_dir.mkdir()
    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "outcome": "running",
                "repair_run_count": 6,
                "attempt_counter": 0,
                "current_attempt_id": None,
                "current_signature": {},
                "current_recurrence": {},
                "attempts": [],
                "iterations": [],
            }
        ),
        encoding="utf-8",
    )

    gather_dir = tmp_path / "gather"
    gather_dir.mkdir()
    worklist = tmp_path / "worklist.jsonl"
    worklist.write_text(
        json.dumps(
            {
                "workspace": str(workspace),
                "plan": plan_name,
                "session": "demo-session",
                "kind": "chain",
                "sources": ["marker"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    gather_path = gather_dir / "gather.py"
    gather_path.write_text(_extract_auditor_gather_program(), encoding="utf-8")
    env = dict(os.environ)
    env["MEGAPLAN_AUDIT_REPAIR_DATA_DIR"] = str(repair_data_dir)
    env["MEGAPLAN_AUDIT_META_RUN_DIR"] = str(tmp_path / "meta-runs")
    result = subprocess.run(
        [sys.executable, str(gather_path), str(worklist), str(gather_dir), "6", str(tmp_path), "none"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    findings = json.loads((gather_dir / "findings.json").read_text(encoding="utf-8"))["findings"]
    assert findings, "expected running repair without attempt context to produce a finding"
    meta_summary = findings[0]["meta_repair_summary"]
    assert meta_summary["should_dispatch"] is True
    assert meta_summary["trigger"] == "repair_running_without_attempt_context"
    assert meta_summary["missing_meta_run_evidence"] is True
    assert "artifact-quality gap" in " ".join(meta_summary["rationale"])


def test_arnold_progress_auditor_produces_evidence_cited_report_via_mocked_deepseek(tmp_path) -> None:
    report = _run_auditor_with_mocked_deepseek(tmp_path)
    finding = report["findings"][0]
    # The finding cites specific plan_v + gate evidence.
    combined = " ".join(finding["reasons"]) + " " + finding.get("hypothesis", "")
    assert "plan_v refreshed" in combined
    assert "gate=ITERATE/blocked" in combined
    assert "hypothesis:" in finding["hypothesis"]


# ── T9: repair-trigger / watchdog integration tests ──────────────────────


def test_watchdog_scan_once_disabled_dispatch_observe_only_non_fatal(
    tmp_path: Path,
) -> None:
    """The trigger's disabled-by-default observe-only path must not abort the scan."""
    trigger = tmp_path / "arnold-repair-trigger"
    trigger.write_text(
        "#!/usr/bin/env bash\n"
        "echo '{\"event\":\"repair_trigger\",\"status\":\"empty\",\"enabled\":false}'\n",
        encoding="utf-8",
    )
    trigger.chmod(trigger.stat().st_mode | stat.S_IXUSR)
    marker_dir = tmp_path / "empty-markers"
    marker_dir.mkdir()

    script = "\n\n".join(
            [
                _extract_wrapper_function("repair_trigger_scan"),
                _extract_wrapper_function("scan_once_unlocked"),
                _extract_wrapper_function("scan_once"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(tmp_path / 'repair-data')!r}",
            f"REPAIR_TRIGGER_BIN={str(trigger)!r}",
            f"SCAN_LOCK_FILE={str(tmp_path / 'watchdog-scan.lock')!r}",
            "SCAN_LOCK_WAIT_SECS=0",
            "COOPERATIVE_ONCE=0",
            "WATCHDOG_BOOTSTRAP_RECOVERED=0",
            """
log() { printf '%s\\n' \"$*\" >> \"$LOG_PATH\"; }
bootstrap_watchdog_observation() { return 0; }
write_watchdog_sweep_health() { return 0; }
write_watchdog_heartbeat() { :; }
write_status_snapshot() { :; }
run_repair_data_maintenance() { :; }
maybe_reexec_updated_watchdog() { :; }
sync_editable_source_branch() { return 0; }
adopt_unmarked_tmux_sessions() { :; }
emit_report() { echo \"emit:$2\" >> \"$LOG_PATH\"; }
reap_stale_repairs() { :; }
""".strip(),
            f"LOG_PATH={str(tmp_path / 'scan.log')!r}",
            "scan_once",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    log_text = (tmp_path / "scan.log").read_text(encoding="utf-8")
    # Observe-only trigger output logged but scan completes normally.
    assert "repair-trigger" in log_text
    assert '"event":"repair_trigger"' in log_text
    assert '"status":"empty"' in log_text
    assert '"enabled":false' in log_text
    assert "scan complete markers=0" in log_text


def test_watchdog_scan_once_lock_contention_is_non_fatal(tmp_path: Path) -> None:
    """When the trigger reports lock contention (busy), the watchdog scan must continue."""
    trigger = tmp_path / "arnold-repair-trigger"
    trigger.write_text(
        "#!/usr/bin/env bash\n"
        "echo '{\"event\":\"repair_trigger\",\"status\":\"busy\",\"lock_status\":\"contended\"}'\n"
        "exit 0\n",
        encoding="utf-8",
    )
    trigger.chmod(trigger.stat().st_mode | stat.S_IXUSR)
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()

    script = "\n\n".join(
            [
                _extract_wrapper_function("repair_trigger_scan"),
                _extract_wrapper_function("scan_once_unlocked"),
                _extract_wrapper_function("scan_once"),
            f"MARKER_DIR={str(marker_dir)!r}",
                f"REPAIR_DATA_DIR={str(tmp_path / 'repair-data')!r}",
                f"REPAIR_TRIGGER_BIN={str(trigger)!r}",
                f"SCAN_LOCK_FILE={str(tmp_path / 'watchdog-scan.lock')!r}",
                "SCAN_LOCK_WAIT_SECS=0",
                "COOPERATIVE_ONCE=0",
                "WATCHDOG_BOOTSTRAP_RECOVERED=0",
                """
log() { printf '%s\\n' \"$*\" >> \"$LOG_PATH\"; }
bootstrap_watchdog_observation() { return 0; }
write_watchdog_sweep_health() { return 0; }
write_watchdog_heartbeat() { :; }
write_status_snapshot() { :; }
run_repair_data_maintenance() { :; }
maybe_reexec_updated_watchdog() { :; }
sync_editable_source_branch() { return 0; }
adopt_unmarked_tmux_sessions() { :; }
emit_report() { echo \"emit:$2\" >> \"$LOG_PATH\"; }
reap_stale_repairs() { :; }
""".strip(),
            f"LOG_PATH={str(tmp_path / 'scan.log')!r}",
            "scan_once",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    log_text = (tmp_path / "scan.log").read_text(encoding="utf-8")
    # Lock contention is logged but scan finishes — it is never fatal.
    assert "busy" in log_text
    assert "scan complete markers=0" in log_text


def test_watchdog_scan_once_queued_request_triggers_observe_then_continues(
    tmp_path: Path,
) -> None:
    """A queued repair request produces observe-only trigger output; the scan proceeds."""
    trigger = tmp_path / "arnold-repair-trigger"
    trigger.write_text(
        "#!/usr/bin/env bash\n"
        "echo '{\"event\":\"repair_trigger_observe\",\"status\":\"would_dispatch\","
        "\"request_id\":\"req-1\",\"enabled\":false}'\n"
        "echo '{\"event\":\"repair_trigger\",\"status\":\"no_actionable_requests\",\"enabled\":false}'\n",
        encoding="utf-8",
    )
    trigger.chmod(trigger.stat().st_mode | stat.S_IXUSR)
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()

    script = "\n\n".join(
            [
                _extract_wrapper_function("repair_trigger_scan"),
                _extract_wrapper_function("scan_once_unlocked"),
                _extract_wrapper_function("scan_once"),
            f"MARKER_DIR={str(marker_dir)!r}",
                f"REPAIR_DATA_DIR={str(tmp_path / 'repair-data')!r}",
                f"REPAIR_TRIGGER_BIN={str(trigger)!r}",
                f"SCAN_LOCK_FILE={str(tmp_path / 'watchdog-scan.lock')!r}",
                "SCAN_LOCK_WAIT_SECS=0",
                "COOPERATIVE_ONCE=0",
                "WATCHDOG_BOOTSTRAP_RECOVERED=0",
                """
log() { printf '%s\\n' \"$*\" >> \"$LOG_PATH\"; }
bootstrap_watchdog_observation() { return 0; }
write_watchdog_sweep_health() { return 0; }
write_watchdog_heartbeat() { :; }
write_status_snapshot() { :; }
run_repair_data_maintenance() { :; }
maybe_reexec_updated_watchdog() { :; }
sync_editable_source_branch() { return 0; }
adopt_unmarked_tmux_sessions() { :; }
emit_report() { echo \"emit:$2\" >> \"$LOG_PATH\"; }
reap_stale_repairs() { :; }
""".strip(),
            f"LOG_PATH={str(tmp_path / 'scan.log')!r}",
            "scan_once",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    log_text = (tmp_path / "scan.log").read_text(encoding="utf-8")
    assert "would_dispatch" in log_text
    assert "no_actionable_requests" in log_text
    assert "scan complete markers=0" in log_text


def test_watchdog_chain_runner_detected_as_alive_without_tmux(
    tmp_path: Path,
) -> None:
    """When ``matching_runner_process_alive`` confirms a live chain runner,
    ``session_health_status`` returns *alive* even without tmux."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")

    script = "\n\n".join(
        [
            _extract_wrapper_function("session_health_status"),
            """
matching_runner_process_alive() { return 0; }
chain_wait_status() { echo none; }
tmux() {
  if [[ "$1" == "has-session" ]]; then
    return 1
  fi
  return 0
}
""".strip(),
            f"session_health_status demo-session {str(workspace)!r} {str(spec_path)!r} chain ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "alive"


def test_watchdog_epic_chain_runner_detected_as_alive_without_tmux(
    tmp_path: Path,
) -> None:
    """When ``matching_runner_process_alive`` confirms a live epic-chain runner,
    ``session_health_status`` returns *alive* even without tmux."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "epic-demo" / "epic-chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")

    script = "\n\n".join(
        [
            _extract_wrapper_function("session_health_status"),
            """
matching_runner_process_alive() { return 0; }
chain_wait_status() { echo none; }
tmux() {
  if [[ "$1" == "has-session" ]]; then
    return 1
  fi
  return 0
}
""".strip(),
            f"session_health_status epic-session {str(workspace)!r} {str(spec_path)!r} epic_chain ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "alive"


def test_watchdog_alive_by_process_prevents_relaunch(
    tmp_path: Path,
) -> None:
    """When ``session_health_status`` returns *alive* via process detection the
    watchdog must skip relaunch for that session."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    (marker_dir / "alive-session.json").write_text(
        json.dumps(
            {
                "session": "alive-session",
                "workspace": str(workspace),
                "remote_spec": str(spec_path),
                "run_kind": "chain",
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("json_field"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(tmp_path / 'repair-data')!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' \"$1\" \"$2\" \"$3\" \"$4\" \"$5\" \"$6\" \"$7\" >> \"$1\"
}
log() { printf '%s\\n' \"$*\" >> \"$LOG\"; }
maybe_reexec_updated_watchdog() { :; }
sync_editable_source_branch() { return 0; }
adopt_unmarked_tmux_sessions() { :; }
reap_stale_repairs() { :; }
emit_report() { cp \"$1\" REPORT_PATH_PLACEHOLDER; }
# session is alive via process detection (no tmux needed).
session_health_status() { echo alive; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
chain_health_status() { CHAIN_HEALTH_STATUS=ok; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo SHOULD_NOT_DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo SHOULD_NOT_REPAIR >&2; return 0; }
mechanical_relaunch_attempted_previously() { return 0; }
kimi_dispatch_failed_previously() { return 1; }
kimi_dispatch_marker_set() { :; }
kimi_dispatch_marker_clear() { :; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\\n' \"$1\"; }
tmux() { return 1; }
""".replace("REPORT_PATH_PLACEHOLDER", str(report_path)).strip(),
            f"launch_chain_tick alive-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    # Alive sessions get an observe report, not a relaunch.
    assert "alive" in report
    assert "restart" not in report
    assert "SHOULD_NOT_DISPATCH" not in result.stderr
    assert "SHOULD_NOT_REPAIR" not in result.stderr


def test_watchdog_marker_only_live_worker_session_prevents_duplicate_repair(
    tmp_path: Path,
) -> None:
    """A session with only a marker (no tmux) whose live worker PID is found
    must be classified alive, preventing duplicate repair dispatch."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    chain_state_path = workspace / ".megaplan" / "plans" / ".chains" / f"chain-{digest}.json"
    chain_state_path.parent.mkdir(parents=True, exist_ok=True)
    plan_name = "m3-demo-plan"
    chain_state_path.write_text(
        json.dumps({"current_plan_name": plan_name}),
        encoding="utf-8",
    )
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)

    worker = subprocess.Popen(["sleep", "30"])
    try:
        (plan_dir / "state.json").write_text(
            json.dumps({"active_step": {"phase": "execute", "worker_pid": worker.pid}}),
            encoding="utf-8",
        )
        marker_dir = tmp_path / "markers"
        marker_dir.mkdir()
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
        report_path = tmp_path / "report.tsv"
        log_path = tmp_path / "watchdog.log"

        script = "\n\n".join(
            [
                _extract_wrapper_function("json_field"),
                _extract_wrapper_function("matching_runner_process_alive"),
                _extract_wrapper_function("session_health_status"),
                _extract_wrapper_function("launch_chain_tick"),
                f"MARKER_DIR={str(marker_dir)!r}",
                f"REPAIR_DATA_DIR={str(tmp_path / 'repair-data')!r}",
                f"LOG={str(log_path)!r}",
                """
report_item() {
  printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' \"$1\" \"$2\" \"$3\" \"$4\" \"$5\" \"$6\" \"$7\" >> \"$1\"
}
log() { printf '%s\\n' \"$*\" >> \"$LOG\"; }
maybe_reexec_updated_watchdog() { :; }
sync_editable_source_branch() { return 0; }
adopt_unmarked_tmux_sessions() { :; }
reap_stale_repairs() { :; }
emit_report() { cp \"$1\" REPORT_PATH_PLACEHOLDER; }
chain_wait_status() { echo none; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
chain_health_status() { CHAIN_HEALTH_STATUS=ok; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo SHOULD_NOT_DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo SHOULD_NOT_REPAIR >&2; return 0; }
mechanical_relaunch_attempted_previously() { return 0; }
kimi_dispatch_failed_previously() { return 1; }
kimi_dispatch_marker_set() { :; }
kimi_dispatch_marker_clear() { :; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\\n' \"$1\"; }
tmux() {
  if [[ \"$1\" == \"has-session\" ]]; then
    return 1
  fi
  return 0
}
""".replace("REPORT_PATH_PLACEHOLDER", str(report_path)).strip(),
                f"launch_chain_tick demo-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
            ]
        )

        result = _run_watchdog_shell(script)
        assert result.returncode == 0, result.stderr
        report = report_path.read_text(encoding="utf-8")
        # The worker is alive, so session is alive — no relaunch, no repair.
        assert "alive" in report
        assert "restart" not in report
        assert "SHOULD_NOT_DISPATCH" not in result.stderr
        assert "SHOULD_NOT_REPAIR" not in result.stderr
    finally:
        worker.terminate()
        worker.wait(timeout=5)


# ── T11: scan_once session-marker sidecar filtering ─────────────────────


def test_watchdog_scan_once_filters_canonical_sidecar_jsons(tmp_path: Path) -> None:
    """``scan_once`` must use ``is_canonical_session_marker_path`` to exclude
    canonical sidecar JSONs, scanning only real session markers."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    (marker_dir / "real-session.json").write_text(
        json.dumps(
            {
                "session": "real-session",
                "workspace": str(tmp_path / "ws"),
                "remote_spec": str(tmp_path / "ws" / "chain.yaml"),
                "run_kind": "chain",
            }
        ),
        encoding="utf-8",
    )
    # Canonical sidecars that must be skipped
    for suffix in (
        ".repair-progress.json",
        ".reap-progress.json",
        ".chain-health.progress.json",
        ".progress.json",
    ):
        (marker_dir / f"real-session{suffix}").write_text("{}", encoding="utf-8")
        (marker_dir / f"other{suffix}").write_text("{}", encoding="utf-8")

    trigger = tmp_path / "fake-trigger"
    trigger.write_text(
        "#!/usr/bin/env bash\n"
        "echo '{\"event\":\"repair_trigger\",\"status\":\"empty\",\"enabled\":false}'\n",
        encoding="utf-8",
    )
    trigger.chmod(trigger.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
            [
                _extract_wrapper_function("repair_trigger_scan"),
                _extract_wrapper_function("scan_once_unlocked"),
                _extract_wrapper_function("scan_once"),
            f"MARKER_DIR={shlex.quote(str(marker_dir))}",
                f"REPAIR_DATA_DIR={shlex.quote(str(tmp_path / 'repair-data'))}",
                f"REPAIR_TRIGGER_BIN={shlex.quote(str(trigger))}",
                f"SCAN_LOCK_FILE={shlex.quote(str(tmp_path / 'watchdog-scan.lock'))}",
                "SCAN_LOCK_WAIT_SECS=0",
                "COOPERATIVE_ONCE=0",
                "WATCHDOG_BOOTSTRAP_RECOVERED=0",
                (
                    "log() { printf '%s\\n' \"$*\" >> \"$LOG_PATH\"; }\n"
                    "bootstrap_watchdog_observation() { return 0; }\n"
                    "write_watchdog_sweep_health() { return 0; }\n"
                    "write_watchdog_heartbeat() { :; }\n"
                    "write_status_snapshot() { :; }\n"
                    "run_repair_data_maintenance() { :; }\n"
                "maybe_reexec_updated_watchdog() { :; }\n"
                "sync_editable_source_branch() { return 0; }\n"
                "adopt_unmarked_tmux_sessions() { :; }\n"
                "emit_report() { echo \"emit:$2\" >> \"$LOG_PATH\"; }\n"
                "reap_stale_repairs() { :; }\n"
                "json_field() { python3 -c \"import json,sys; d=json.load(open(sys.argv[1])); print(d.get(sys.argv[2],''))\" \"$1\" \"$2\"; }\n"
                "launch_chain_tick() { echo \"tick:$1\" >> \"$LOG_PATH\"; }\n"
            ),
            f"LOG_PATH={shlex.quote(str(tmp_path / 'scan.log'))}",
            "scan_once",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    log_text = (tmp_path / "scan.log").read_text(encoding="utf-8")
    # Only the real session should be ticked
    assert "tick:real-session" in log_text
    # Should report exactly 1 marker found (only the canonical session marker)
    assert "scan complete markers=1" in log_text


def test_watchdog_scan_once_excludes_sidecar_only_entries(tmp_path: Path) -> None:
    """When only canonical sidecar files exist (no real session markers),
    the scan must report 0 markers."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    # Only sidecar files, no real session markers
    for suffix in (".repair-progress.json", ".progress.json"):
        (marker_dir / f"phantom{suffix}").write_text("{}", encoding="utf-8")

    trigger = tmp_path / "fake-trigger"
    trigger.write_text(
        "#!/usr/bin/env bash\n"
        "echo '{\"event\":\"repair_trigger\",\"status\":\"empty\",\"enabled\":false}'\n",
        encoding="utf-8",
    )
    trigger.chmod(trigger.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("repair_trigger_scan"),
            _extract_wrapper_function("scan_once_unlocked"),
            _extract_wrapper_function("scan_once"),
            f"MARKER_DIR={shlex.quote(str(marker_dir))}",
            f"REPAIR_DATA_DIR={shlex.quote(str(tmp_path / 'repair-data'))}",
            f"REPAIR_TRIGGER_BIN={shlex.quote(str(trigger))}",
            f"SCAN_LOCK_FILE={shlex.quote(str(tmp_path / 'watchdog-scan.lock'))}",
            "SCAN_LOCK_WAIT_SECS=0",
            "COOPERATIVE_ONCE=0",
            "WATCHDOG_BOOTSTRAP_RECOVERED=0",
            (
                "log() { printf '%s\\n' \"$*\" >> \"$LOG_PATH\"; }\n"
                "bootstrap_watchdog_observation() { return 0; }\n"
                "write_watchdog_sweep_health() { return 0; }\n"
                "write_watchdog_heartbeat() { :; }\n"
                "write_status_snapshot() { :; }\n"
                "run_repair_data_maintenance() { :; }\n"
                "maybe_reexec_updated_watchdog() { :; }\n"
                "sync_editable_source_branch() { return 0; }\n"
                "adopt_unmarked_tmux_sessions() { :; }\n"
                "emit_report() { echo \"emit:$2\" >> \"$LOG_PATH\"; }\n"
                "reap_stale_repairs() { :; }\n"
                "json_field() { python3 -c \"import json,sys; d=json.load(open(sys.argv[1])); print(d.get(sys.argv[2],''))\" \"$1\" \"$2\"; }\n"
                "launch_chain_tick() { echo \"tick:$1\" >> \"$LOG_PATH\"; }\n"
            ),
            f"LOG_PATH={shlex.quote(str(tmp_path / 'scan.log'))}",
            "scan_once",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    log_text = (tmp_path / "scan.log").read_text(encoding="utf-8")
    assert "scan complete markers=0" in log_text


# ---------------------------------------------------------------------------
# Meta-repair wrapper extraction helpers + tests
# ---------------------------------------------------------------------------


def _meta_repair_wrapper() -> str:
    return _wrapper("arnold-meta-repair-loop")


def _extract_meta_repair_function(name: str) -> str:
    text = _meta_repair_wrapper()
    start = text.index(f"{name}() {{")
    end = text.index("\n}\n", start) + 3
    return text[start:end]


def _extract_meta_repair_embedded_python(marker: str) -> str:
    text = _meta_repair_wrapper()
    start = text.index(marker)
    start = text.index("\n", start) + 1
    end = text.index("\nPY\n", start)
    return text[start:end]


def _run_meta_embedded_python(program: str, *args: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        prog_path = Path(tmpdir) / "_meta_embedded.py"
        prog_path.write_text(program, encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
        return subprocess.run(
            [sys.executable, str(prog_path), *args],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )


def test_arnold_meta_repair_loop_wrapper_bash_n_syntax() -> None:
    """The meta-repair wrapper must pass bash -n."""
    wrapper_path = WRAPPER_DIR / "arnold-meta-repair-loop"
    result = subprocess.run(
        ["bash", "-n", str(wrapper_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr}"


def test_meta_repair_wrapper_has_env_setup_and_redaction() -> None:
    """Wrapper must source cloud-hot-env, define redaction helpers."""
    text = _meta_repair_wrapper()

    assert '. /workspace/.cloud-hot-env' in text
    assert 'redact_inline_text() {' in text
    assert 'redact_file_in_place() {' in text
    assert 'from arnold_pipelines.megaplan.cloud.redact import redact_text' in text


def test_meta_repair_wrapper_has_feature_flag_gating() -> None:
    """Wrapper must gate on META_REPAIR_ENABLED and exit early when off."""
    text = _meta_repair_wrapper()

    assert 'META_REPAIR_ENABLED_VAR="${ARNOLD_META_REPAIR_ENABLED:-1}"' in text
    assert 'meta-repair disabled' in text
    assert 'META_REPAIR_COMMIT_ENABLED_VAR="${ARNOLD_META_REPAIR_COMMIT_ENABLED:-1}"' in text
    assert '0|false|False|FALSE|no|No|NO|off|Off|OFF' in text


def test_meta_repair_wrapper_has_recursion_guard() -> None:
    """Wrapper must have a recursion guard that checks repair-data/meta/."""
    text = _meta_repair_wrapper()

    assert 'recursion_check() {' in text
    assert 'check_meta_repair_recursion' in text
    assert 'RECURSION:' in text
    assert 'NEEDS_HUMAN' in text
    assert 'escalating to NEEDS_HUMAN instead of recursing' in text


def test_meta_repair_wrapper_has_codex_dispatch() -> None:
    """Wrapper must dispatch Codex with danger-full-access sandbox."""
    text = _meta_repair_wrapper()

    assert 'cd "$ARNOLD_SRC" || exit 1' in text
    assert 'codex exec --skip-git-repo-check --sandbox danger-full-access' in text
    assert "--run-kind automatic_meta_repair_worker" in text
    assert '--stdin-file "$BRIEF_PATH"' in text
    assert '$(cat "$BRIEF_PATH")' not in text
    assert 'CODEX_TIMEOUT="${MEGAPLAN_META_CODEX_TIMEOUT_SECS:-5400}"' in text
    assert 'BRIEF_PREFLIGHT_MAX_CHARS="${MEGAPLAN_META_BRIEF_PREFLIGHT_MAX_CHARS:-900000}"' in text
    assert 'meta-repair brief exceeded preflight char budget; rebuilding emergency brief' in text
    assert 'classification_and_prompt 1' in text
    assert 'codex CLI missing' in text


def test_repair_loop_carries_terminal_goal_evaluation_into_verdict_write() -> None:
    text = _wrapper("arnold-repair-loop")

    assert 'repair_data_set_outcome "progressed" "$status"' in text
    assert 'repair_data_set_outcome "true_human_blocker" "$status"' in text
    assert 'repair_save_verdict_evidence "$repair_goal_status_override"' in text
    assert "repair_goal_status_override=repair_goal_status_override" in text


def test_watchdog_observes_unowned_preserve_live_goal_without_dispatch(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    report_path = tmp_path / "report.tsv"
    dispatch_path = tmp_path / "dispatch.log"
    log_path = tmp_path / "watchdog.log"
    script = "\n\n".join(
        [
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"MEGAPLAN_SUPERVISOR_PYTHON={sys.executable!r}",
            f"LOG={str(log_path)!r}",
            f"DISPATCH_PATH={str(dispatch_path)!r}",
            """
log() { printf '%s\n' "$*" >> "$LOG"; }
report_item() { printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"; }
repair_goal_watchdog_status() { printf 'active_unowned\tgoal-healthy\tfresh execute worker is still progressing\tpreserve_live\n'; }
repair_unintended_stop() { printf 'dispatch\n' >> "$DISPATCH_PATH"; }
""".strip(),
            f"launch_chain_tick custody-control-plane {str(tmp_path / 'workspace')!r} {str(tmp_path / 'chain.yaml')!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert not dispatch_path.exists()
    assert "\tobserve\trecovery_observation\tpreserve fresh matching worker" in report_path.read_text(encoding="utf-8")
    assert "observing without repair launch" in log_path.read_text(encoding="utf-8")


def test_watchdog_suppresses_unowned_goal_redispatch_for_authoritative_live_worker(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    report_path = tmp_path / "report.tsv"
    dispatch_path = tmp_path / "dispatch.log"
    log_path = tmp_path / "watchdog.log"
    script = "\n\n".join(
        [
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"MEGAPLAN_SUPERVISOR_PYTHON={sys.executable!r}",
            f"LOG={str(log_path)!r}",
            f"DISPATCH_PATH={str(dispatch_path)!r}",
            """
log() { printf '%s\n' "$*" >> "$LOG"; }
report_item() { printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"; }
repair_goal_watchdog_status() { printf 'active_unowned\tgoal-live\towner terminalized before review finished\tinvestigate\n'; }
current_target_has_live_worker() { return 0; }
dispatch_meta_repair() { printf 'l2\n' >> "$DISPATCH_PATH"; }
repair_unintended_stop() { printf 'l1\n' >> "$DISPATCH_PATH"; }
""".strip(),
            f"launch_chain_tick custody-control-plane {str(tmp_path / 'workspace')!r} {str(tmp_path / 'chain.yaml')!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert not dispatch_path.exists()
    assert "preserve authoritative live target worker" in report_path.read_text(encoding="utf-8")
    assert "suppressing replacement-owner dispatch" in log_path.read_text(encoding="utf-8")


def test_watchdog_suppresses_unowned_goal_while_runner_finishes_backstop(
    tmp_path: Path,
) -> None:
    """A live canonical runner remains authoritative after active_step clears."""

    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    report_path = tmp_path / "report.tsv"
    dispatch_path = tmp_path / "dispatch.log"
    log_path = tmp_path / "watchdog.log"
    script = "\n\n".join(
        [
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"MEGAPLAN_SUPERVISOR_PYTHON={sys.executable!r}",
            f"LOG={str(log_path)!r}",
            f"DISPATCH_PATH={str(dispatch_path)!r}",
            """
log() { printf '%s\n' "$*" >> "$LOG"; }
report_item() { printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"; }
repair_goal_watchdog_status() { printf 'active_unowned\tgoal-live\tcited fix missing from target history\tinvestigate\ttrue\n'; }
current_target_has_live_worker() { return 1; }
dispatch_meta_repair() { printf 'l2\n' >> "$DISPATCH_PATH"; }
repair_unintended_stop() { printf 'l1\n' >> "$DISPATCH_PATH"; }
""".strip(),
            f"launch_chain_tick custody-control-plane {str(tmp_path / 'workspace')!r} {str(tmp_path / 'chain.yaml')!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert not dispatch_path.exists()
    assert "preserve authoritative live target worker" in report_path.read_text(encoding="utf-8")
    assert "suppressing replacement-owner dispatch" in log_path.read_text(encoding="utf-8")


def test_current_target_live_worker_requires_active_pid_bound_heartbeat() -> None:
    function = _extract_wrapper_function("current_target_has_live_worker")
    live = json.dumps(
        {
            "active_step_heartbeat": {
                "active": True,
                "pid_live": True,
                "worker_pid": "1179344",
            }
        }
    )
    stale = json.dumps(
        {
            "active_step_heartbeat": {
                "active": True,
                "pid_live": False,
                "worker_pid": "1179344",
            }
        }
    )

    accepted = _run_watchdog_shell(f"{function}\ncurrent_target_has_live_worker {shlex.quote(live)}")
    rejected = _run_watchdog_shell(f"{function}\ncurrent_target_has_live_worker {shlex.quote(stale)}")

    assert accepted.returncode == 0, accepted.stderr
    assert rejected.returncode == 1, rejected.stderr


def test_watchdog_unowned_genuinely_stuck_goal_still_dispatches_one_l1_owner(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    goal_dir = marker_dir / "repair-goals" / "custody-control-plane"
    goal_dir.mkdir(parents=True)
    repair_data_dir.mkdir()
    goal_path = goal_dir / "goal-stuck.json"
    goal_path.write_text(json.dumps({"goal_id": "goal-stuck", "status": "active"}), encoding="utf-8")
    report_path = tmp_path / "report.tsv"
    dispatch_path = tmp_path / "dispatch.log"
    log_path = tmp_path / "watchdog.log"
    script = "\n\n".join(
        [
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"MEGAPLAN_SUPERVISOR_PYTHON={sys.executable!r}",
            f"LOG={str(log_path)!r}",
            f"DISPATCH_PATH={str(dispatch_path)!r}",
            """
log() { printf '%s\n' "$*" >> "$LOG"; }
report_item() { :; }
repair_goal_watchdog_status() { printf 'active_unowned\tgoal-stuck\tworker is absent and checkpoint is frozen\tinvestigate\n'; }
session_health_status() { printf 'stopped\n'; }
compute_meta_repair_trigger() { printf 'NO_TRIGGER\n'; }
repair_unintended_stop() {
  printf '%s\t%s\t%s\n' "$ARNOLD_REPAIR_RETRY_GOAL_ID" "$ARNOLD_REPAIR_RETRY_GOAL_PATH" "$ARNOLD_REPAIR_LAUNCH_DESCRIPTION" >> "$DISPATCH_PATH"
}
""".strip(),
            f"launch_chain_tick custody-control-plane {str(tmp_path / 'workspace')!r} {str(tmp_path / 'chain.yaml')!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    dispatches = dispatch_path.read_text(encoding="utf-8").splitlines()
    assert len(dispatches) == 1
    assert dispatches[0].startswith(f"goal-stuck\t{goal_path}\tInvestigate then repair unowned goal goal-stuck")


def test_watchdog_routes_unowned_goal_with_l1_custody_failure_to_l2(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    report_path = tmp_path / "report.tsv"
    dispatch_path = tmp_path / "dispatch.log"
    log_path = tmp_path / "watchdog.log"
    script = "\n\n".join(
        [
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"MEGAPLAN_SUPERVISOR_PYTHON={sys.executable!r}",
            f"LOG={str(log_path)!r}",
            f"DISPATCH_PATH={str(dispatch_path)!r}",
            """
log() { printf '%s\n' "$*" >> "$LOG"; }
report_item() { :; }
repair_goal_watchdog_status() { printf 'active_unowned\tgoal-stuck\tcontext constructor failed\tinvestigate\n'; }
session_health_status() { printf 'stopped\n'; }
compute_meta_repair_trigger() { printf 'TRIGGER:l1_custody_failure\n'; }
dispatch_meta_repair() { REPAIR_DISPATCH_RESULT=dispatched; printf 'l2\n' >> "$DISPATCH_PATH"; return 0; }
repair_unintended_stop() { printf 'l1\n' >> "$DISPATCH_PATH"; }
""".strip(),
            f"launch_chain_tick custody-control-plane {str(tmp_path / 'workspace')!r} {str(tmp_path / 'chain.yaml')!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert dispatch_path.read_text(encoding="utf-8").splitlines() == ["l2"]
    assert "L2 now has custody" in log_path.read_text(encoding="utf-8")


def test_l2_pathological_evidence_builds_minimal_envelope_and_launches_investigator(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_dir = marker_dir / "repair-data"
    goal_path = marker_dir / "repair-goals" / "demo" / "goal.json"
    goal_path.parent.mkdir(parents=True)
    repair_dir.mkdir(parents=True)
    goal_path.write_text(
        json.dumps(
            {
                "goal_id": "repair-goal-pathological",
                "checkpoint_digest": "c" * 64,
                "target": {"blocker_id": "blocker-pathological"},
            }
        ),
        encoding="utf-8",
    )
    huge = "status-history-log" * 150_000
    repair_path = repair_dir / "demo.repair-data.json"
    repair_path.write_text(
        json.dumps(
            {
                "outcome": "deterministic_failure",
                "attempts": [
                    {
                        "attempt_id": index,
                        "failure_context": huge,
                        "post_launch_failure_context": huge,
                    }
                    for index in range(4)
                ],
                "repair_goal": {
                    "goal_id": "repair-goal-pathological",
                    "goal_path": str(goal_path),
                    "checkpoint_digest": "c" * 64,
                },
            }
        ),
        encoding="utf-8",
    )
    (marker_dir / "demo.json").write_text(
        json.dumps({"workspace": str(tmp_path), "history": huge}), encoding="utf-8"
    )
    receipt = {
        "schema_version": "arnold-repair-investigator-receipt-v2",
        "context_digest": "filled-by-launch-stub",
        "target_kind": "l2_repair_system",
        "actual_failure": {
            "classification": "custody_failure",
            "mechanism": "repair evidence and launch custody disagree",
            "error": "pathological evidence remained reference-only",
        },
        "evidence_sources": [
            {
                "kind": "repair_data",
                "path": str(repair_path),
                "authority": 7,
                "observed": "authoritative artifact was read by reference",
            }
        ],
        "custody_status": "consistent",
        "custody_contradictions": [],
        "intended_recovery": {
            "predicate": "repair ordinary custody and retrigger L1",
            "blocker_cleared_required": True,
            "fresh_progress_required": True,
            "beyond_stage_required": True,
        },
        "safe_repair_target": {
            "kind": "arnold_source",
            "scope": str(REPO_ROOT),
            "rationale": "failure is in the repair launch contract",
        },
        "handoff": {
            "action": "repair_source",
            "allowed_mutations": ["repair investigation source"],
            "forbidden_mutations": ["audited workspace"],
        },
        "four_axis": {
            "TRACKED": "pass",
            "FIXED": "fail",
            "INTENT": "pass",
            "CONTEXT": "fail",
        },
        "prior_repairs_considered": ["pathological repair data"],
        "preserve_live": False,
        "recommended_action": "repair_source",
        "guard_weakening_risk": "none",
    }
    receipt_template = tmp_path / "receipt-template.json"
    receipt_template.write_text(json.dumps(receipt), encoding="utf-8")
    context_path = tmp_path / "context.json"
    prompt_path = tmp_path / "prompt.md"
    receipt_path = tmp_path / "receipt.json"
    observation_path = tmp_path / "observations.json"
    run_id_path = tmp_path / "run-id"
    launch_log = tmp_path / "launch.log"
    run_log = tmp_path / "run.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_codex = fake_bin / "codex"
    fake_codex.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_codex.chmod(0o755)
    supervisor = tmp_path / "supervisor-python"
    supervisor.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$*\" == *'arnold_pipelines.megaplan.cloud.repair_investigation'* ]]; then\n"
        f"  exec {shlex.quote(sys.executable)} \"$@\"\n"
        "fi\n"
        "cat >/dev/null\n",
        encoding="utf-8",
    )
    supervisor.chmod(0o755)
    wrapper = _meta_repair_wrapper()
    start = wrapper.index("run_meta_repair_investigation() {")
    end = wrapper.index("\nrequire_meta_investigation_before_mutation()", start)
    function = wrapper[start:end]
    script = "\n\n".join(
        [
            function,
            f"REAL_PYTHON={shlex.quote(sys.executable)}",
            f"PATH={shlex.quote(str(fake_bin))}:$PATH",
            f"WRAPPER_REPO_ROOT={shlex.quote(str(REPO_ROOT))}",
            f"ARNOLD_SRC={shlex.quote(str(REPO_ROOT))}",
            f"MEGAPLAN_SUPERVISOR_PYTHON={shlex.quote(str(supervisor))}",
            f"MARKER_DIR={shlex.quote(str(marker_dir))}",
            f"REPAIR_DATA_DIR={shlex.quote(str(repair_dir))}",
            f"REPAIR_DATA_PATH={shlex.quote(str(repair_path))}",
            f"META_INVESTIGATION_CONTEXT_PATH={shlex.quote(str(context_path))}",
            f"META_INVESTIGATION_PROMPT_PATH={shlex.quote(str(prompt_path))}",
            f"META_INVESTIGATION_RECEIPT_PATH={shlex.quote(str(receipt_path))}",
            f"META_INVESTIGATION_OBSERVATION_PATH={shlex.quote(str(observation_path))}",
            f"META_INVESTIGATION_RUN_ID_PATH={shlex.quote(str(run_id_path))}",
            f"RECEIPT_TEMPLATE={shlex.quote(str(receipt_template))}",
            f"LAUNCH_LOG={shlex.quote(str(launch_log))}",
            f"RUN_LOG={shlex.quote(str(run_log))}",
            "SESSION=demo",
            "TRIGGER_TYPE=l1_custody_failure",
            "META_CODEX_MODEL=test-model",
            "DEEPSEEK_MODEL=test-deepseek",
            "MEGAPLAN_META_FORCE_INVESTIGATOR_MODE=codex_read_only",
            "SUBAGENT_TIMEOUT=30",
            "META_INVESTIGATION_MAX_BYTES=65536",
            "META_INVESTIGATION_CONTEXT_DIGEST=",
            "META_INVESTIGATION_RUN_ID=",
            "CLOUD_WATCHDOG_REPAIR_REQUEST_ID=request-1",
            "CLOUD_WATCHDOG_REPAIR_BLOCKER_ID=blocker-1",
            "ARNOLD_MANAGED_AGENT_RUN_ID=parent-1",
            "redact_file_in_place() { :; }",
            "log() { :; }",
            r'''python3() {
  if [[ "$1" == "-m" && "$2" == "arnold_pipelines.megaplan.managed_agent" ]]; then
    printf '%s\n' 'managed-investigator-pathological' > "$META_INVESTIGATION_RUN_ID_PATH"
    printf '%s\n' "$*" > "$LAUNCH_LOG"
    "$REAL_PYTHON" - "$META_INVESTIGATION_CONTEXT_PATH" "$RECEIPT_TEMPLATE" "$META_INVESTIGATION_RECEIPT_PATH" <<'PY'
import json, sys
context = json.load(open(sys.argv[1], encoding="utf-8"))
receipt = json.load(open(sys.argv[2], encoding="utf-8"))
receipt["context_digest"] = context["context_digest"]
json.dump(receipt, open(sys.argv[3], "w", encoding="utf-8"))
PY
    return 0
  fi
  "$REAL_PYTHON" "$@"
}''',
            "run_meta_repair_investigation",
        ]
    )

    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    envelope = json.loads(context_path.read_text(encoding="utf-8"))
    assert context_path.stat().st_size < 16 * 1024
    assert prompt_path.stat().st_size <= 65536
    assert envelope["identity"]["repair_request_id"] == "request-1"
    assert envelope["identity"]["blocker_id"] == "blocker-pathological"
    assert envelope["identity"]["dispatch_blocker_id"] == "blocker-1"
    assert envelope["identity"]["blocker_identity_drift"] is True
    assert set(envelope) == {
        "schema_version",
        "target_kind",
        "generated_at",
        "objective",
        "identity",
        "provenance_ref",
        "source_custody",
        "evidence_refs",
        "authorization",
        "receipt_contract_ref",
        "context_digest",
    }
    assert run_id_path.read_text(encoding="utf-8").strip() == "managed-investigator-pathological"
    assert "--route-class meta_repair_read_only_investigator" in launch_log.read_text(encoding="utf-8")
    assert "status-history-log" not in prompt_path.read_text(encoding="utf-8")


def test_two_stage_repair_fails_closed_before_mutating_fixer_and_is_described() -> None:
    watchdog = _wrapper("arnold-watchdog")
    repair = _wrapper("arnold-repair-loop")

    assert '--description "${ARNOLD_REPAIR_LAUNCH_DESCRIPTION:-Investigate then repair watchdog blocker' in watchdog
    assert '--description "Read-only investigation of ${CLOUD_WATCHDOG_REPAIR_BLOCKER_ID:-repair blocker}' in repair
    assert '--description "Mutating fixer for ${CLOUD_WATCHDOG_REPAIR_BLOCKER_ID:-repair blocker}' in repair

    investigator_call = repair.index("run_repair_investigator_turn || investigator_rc=$?")
    mutating_loop = repair.index("for iteration in 1 2 3; do", investigator_call)
    fail_closed = repair[investigator_call:mutating_loop]
    assert 'if [[ "$investigator_rc" == "2" ]]' in fail_closed
    assert 'elif [[ "$investigator_rc" != "0" ]]' in fail_closed
    assert fail_closed.count("exit 1") >= 2
    assert repair.index('run_dev_fix_turn "$iteration"', mutating_loop) > investigator_call


def test_repair_investigator_prompts_preserve_receipt_field_contracts() -> None:
    repair = _wrapper("arnold-repair-loop")

    assert "historical_failure_recovery is analysis embedded in the authoritative plan_state context, not an evidence kind" in repair
    assert "prior_repairs_considered must remain a non-empty JSON array of non-empty strings" in repair
    assert 'use ["none"] when there are no prior repairs, never the string "none"' in repair
    assert "Preserve every already-valid field, JSON container type" in repair
    assert "Change only the validator-named contract defect" in repair
    assert repair.count("live_process, session_marker, chain_state, plan_state, phase_result") == 2


def test_meta_repair_wrapper_has_deepseek_hermes_subagent_instructions() -> None:
    """Wrapper must instruct Codex to delegate to DeepSeek/Hermes subagents."""
    text = _meta_repair_wrapper()

    assert 'DEEPSEEK_MODEL="${MEGAPLAN_META_MODEL:-deepseek:deepseek-v4-pro}"' in text
    assert 'SUBAGENT_PROFILE="${MEGAPLAN_META_SUBAGENT_PROFILE:-partnered-5}"' in text
    assert 'launch_hermes_agent.py' in text
    assert 'SUBAGENT_SKILL' in text
    assert 'deepseek:deepseek-v4-pro' in text
    assert 'partnered-5' in text
    assert 'DeepSeek/Hermes' in text


def test_meta_repair_wrapper_has_default_commit_policy() -> None:
    """Wrapper must allow commit/push by default while preserving explicit opt-out."""
    text = _meta_repair_wrapper()

    assert 'Commit/push policy' in text
    assert 'not explicitly\n  disabled.' in text
    assert 'ARNOLD_META_REPAIR_COMMIT_ENABLED=0/false/no/off' in text
    assert 'can_commit_changes' in text
    assert 'can_push_changes' in text
    assert 'commit_allowed=' in text
    assert 'push_allowed=' in text


def test_meta_repair_wrapper_has_python_handoff() -> None:
    """Wrapper must hand off to meta_repair.py for classification and prompt."""
    text = _meta_repair_wrapper()

    assert 'evaluate_meta_repair_triggers' in text
    assert 'classification_and_prompt() {' in text
    assert 'NO_TRIGGER' in text
    assert 'TRIGGER:' in text


def test_meta_repair_wrapper_has_retrigger_verification_policy() -> None:
    """Wrapper must include retrigger + verification contract text."""
    text = _meta_repair_wrapper()

    assert 'retrigger the ordinary repair loop' in text
    assert 'REPAIR_LOOP_BIN' in text
    assert 'SUCCESS outcome' in text
    assert 'partial_liveness' in text
    assert 'not terminal success' in text


def test_meta_repair_wrapper_has_record_persistence() -> None:
    """Wrapper must persist redacted meta-repair records."""
    text = _meta_repair_wrapper()

    assert 'persist_meta_repair_record' in text
    assert 'MetaRepairRecord' in text
    assert 'MetaRepairTrigger' in text
    assert 'META_REPAIR_ID' in text
    assert 'leaving recursion guard unpoisoned' in text
    assert 'Codex meta-repair prompt exceeded input limit; see meta-repair log.' in text


def test_meta_repair_wrapper_accepts_valid_verdict_before_launch_failure_grep() -> None:
    """A valid verdict on stdout must not be discarded because stderr is noisy."""
    text = _meta_repair_wrapper()
    verdict_parse = 'VERDICT="$(echo "$RESP_TEXT" | head -1 | tr -d'
    guarded_launch_failure = (
        'if [[ "$VERDICT" != FIXED* && "$VERDICT" != ESCALATE* && "$VERDICT" != NO_FIX* ]] '
        '&& grep -qE'
    )

    assert text.index(verdict_parse) < text.index(guarded_launch_failure)
    assert guarded_launch_failure in text


def test_meta_repair_recursion_check_embedded_python_matches_contract(
    tmp_path: Path,
) -> None:
    """The recursion_check embedded Python must match the meta_repair_policy API."""
    marker = (
        'python3 - "$SESSION" "$REPAIR_DATA_DIR" '
        '"${CLOUD_WATCHDOG_REPAIR_BLOCKER_ID:-}" <<'
    )
    text = _meta_repair_wrapper()

    # Find the recursion_check function body
    start = text.index("recursion_check() {")
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    program = text[py_start:py_end]

    prog_path = tmp_path / "_recursion_check.py"
    prog_path.write_text(program, encoding="utf-8")

    # Create fake repair-data/meta directory with no prior records
    repair_data = tmp_path / "repair-data"
    repair_data.mkdir()
    (repair_data / "meta").mkdir()

    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    result = subprocess.run(
        [sys.executable, str(prog_path), "test-session", str(repair_data), "blocker-1"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "OK:" in result.stdout
    assert "safe to proceed" in result.stdout

    # Now create a prior meta-repair record for the same session
    record = {
        "meta_repair_id": "existing-001",
        "session": "test-session",
        "blocker_id": "blocker-1",
        "trigger": "repair_timeout",
        "outcome": "FIXED",
    }
    import json as _json

    (repair_data / "meta" / "existing-001.json").write_text(
        _json.dumps(record), encoding="utf-8"
    )

    result2 = subprocess.run(
        [sys.executable, str(prog_path), "test-session", str(repair_data), "blocker-1"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    # With max_meta_repair_attempts=1, one existing record should trigger recursion
    assert result2.returncode == 1, result2.stdout
    assert "RECURSION:" in result2.stdout


def test_meta_repair_classification_embedded_python_matches_contract(
    tmp_path: Path,
) -> None:
    """The classification_and_prompt embedded Python must call evaluate_meta_repair_triggers."""
    marker = (
        'python3 - "$SESSION" "$REPAIR_DATA_DIR" "$REPAIR_DATA_PATH" '
        '"$MARKER_DIR" "$META_REPAIR_ENABLED_VAR" "$WATCHDOG_TRIGGER" <<'
    )
    text = _meta_repair_wrapper()

    start = text.index("classification_and_prompt() {")
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    program = text[py_start:py_end]

    # Verify the embedded Python compiles
    prog_path = tmp_path / "_classify.py"
    prog_path.write_text(program, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(prog_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"py_compile failed: {result.stderr}"

    # Verify the embedded program imports evaluate_meta_repair_triggers correctly
    assert "evaluate_meta_repair_triggers" in program
    assert "MetaRepairClassification" in program
    assert "watchdog preclassified trigger" in program
    assert "NO_TRIGGER" in program
    assert "PROMPT_START" in program
    assert "PROMPT_END" in program


def test_meta_repair_commit_gate_embedded_python_matches_contract(
    tmp_path: Path,
) -> None:
    """The commit_gate_check embedded Python must call can_commit_changes/can_push_changes."""
    marker = 'python3 - "$SESSION" <<'
    text = _meta_repair_wrapper()

    start = text.index("commit_gate_check() {")
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    program = text[py_start:py_end]

    prog_path = tmp_path / "_commit_gate.py"
    prog_path.write_text(program, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(prog_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"py_compile failed: {result.stderr}"

    # Verify the embedded program imports the right policy functions
    assert "can_commit_changes" in program
    assert "can_push_changes" in program
    assert "COMMIT_ALLOWED=" in program
    assert "PUSH_ALLOWED=" in program


def test_meta_repair_record_persistence_embedded_python_matches_contract(
    tmp_path: Path,
) -> None:
    """The persist_record embedded Python must call persist_meta_repair_record."""
    marker = (
        'python3 - "$SESSION" "$TRIGGER_TYPE" "$VERDICT" "$RESP_PATH" '
        '"$BRIEF_PATH" "$REPAIR_DATA_DIR" "$META_WORKER_RUN_ID" '
        '"$META_WORKER_MANIFEST" "${CLOUD_WATCHDOG_REPAIR_BLOCKER_ID:-}" <<'
    )
    text = _meta_repair_wrapper()

    start = text.index("persist_record() {")
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    program = text[py_start:py_end]

    prog_path = tmp_path / "_persist.py"
    prog_path.write_text(program, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(prog_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"py_compile failed: {result.stderr}"

    assert "persist_meta_repair_record" in program
    assert "MetaRepairRecord" in program
    assert "MetaRepairTrigger" in program


def test_meta_repair_wrapper_has_safe_session_and_logging() -> None:
    """Wrapper must have safe session naming and log scaffolding."""
    text = _meta_repair_wrapper()

    assert "SAFE_SESSION=" in text
    assert "tr -c 'A-Za-z0-9_.-'" in text
    assert 'log() {' in text
    assert 'RUN_LOG=' in text
    assert 'tee -a "$RUN_LOG"' in text


def test_meta_repair_wrapper_has_verdict_parsing() -> None:
    """Wrapper must parse FIXED/ESCALATE/NO_FIX from Codex first line."""
    text = _meta_repair_wrapper()

    assert 'verdict=FIXED' in text
    assert 'verdict=ESCALATE' in text
    assert 'verdict=NO_FIX' in text
    assert 'verdict=UNKNOWN' in text


# ---------------------------------------------------------------------------
# Meta-repair dispatch primitives (T9)
# ---------------------------------------------------------------------------


def _extract_watchdog_function_by_name(text: str, name: str) -> str:
    """Extract a function body from watchdog text by function name."""
    start = text.index(f"{name}() {{")
    end = text.index("\n}\n", start) + 3
    return text[start:end]


_REPORT_ITEM_STUB = """\
report_item() {
  local path="$1"
  local session="$2"
  local action="$3"
  local status="$4"
  local message="$5"
  local workspace="${6:-}"
  local remote_spec="${7:-}"
  printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' "$session" "$action" "$status" "$message" "$workspace" "$remote_spec" >> "$path"
}"""

_LOG_STUB = """\
log() {
  echo "[watchdog $(date -Iseconds)] $*" | tee -a "${LOG:-/dev/null}"
}"""

_REDACT_INLINE_STUB = """\
redact_inline_text() {
  printf '%s' "$1"
}"""


def _build_meta_dispatch_script(
    marker_dir: Path,
    report_path: Path,
    *,
    meta_repair_bin: str,
    meta_repair_enabled: str = "1",
    extra_lines: list[str] | None = None,
    log_path: str | None = None,
    override_kimi_operator: str | None = None,
) -> str:
    """Build a shell script exercising dispatch_meta_repair with stubbed dependencies."""
    source_dir = marker_dir.parent / "managed-source"
    source_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        _LOG_STUB,
        _REDACT_INLINE_STUB,
        _REPORT_ITEM_STUB,
        _extract_wrapper_function("meta_dispatch_marker_path"),
        _extract_wrapper_function("meta_pgid_path"),
        _extract_wrapper_function("meta_dispatch_marker_set"),
        _extract_wrapper_function("meta_dispatch_marker_clear"),
        _extract_wrapper_function("repair_loop_busy_state"),
        _extract_wrapper_function("check_meta_repair_recursion_guard"),
        _extract_wrapper_function("emit_watchdog_incident_bridge_event"),
        _extract_wrapper_function("confirm_managed_agent_dispatch"),
        _extract_wrapper_function("dispatch_meta_repair"),
        _extract_wrapper_function("kimi_dispatch_marker_path"),
        _extract_wrapper_function("kimi_pgid_path"),
        _extract_wrapper_function("repair_pidfile_path"),
        _extract_wrapper_function("repair_loop_pid_matches_session"),
        _extract_wrapper_function("safe_name"),
        "repair_loop_busy_state() { echo none; }",
    ]
    if override_kimi_operator is not None:
        lines.append(override_kimi_operator)
    else:
        lines.append(_extract_wrapper_function("kimi_operator_running"))

    lines += [
        f"MARKER_DIR={str(marker_dir)!r}",
        f"SRC_DIR={str(source_dir)!r}",
        f"""LOG={str(log_path) if log_path else '/dev/null'}""",
        f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
        f"META_REPAIR_BIN={meta_repair_bin!r}",
        f"META_REPAIR_ENABLED_FLAG={meta_repair_enabled}",
        f"REPAIR_DATA_DIR={str(marker_dir)!r}/repair-data",
        f"PYTHONPATH={str(REPO_ROOT)!r}",
    ]
    if extra_lines:
        lines.extend(extra_lines)
    return "\n\n".join(lines)


def test_meta_repair_dispatch_missing_binary(tmp_path: Path) -> None:
    """dispatch_meta_repair returns 1 when META_REPAIR_BIN is missing/unexecutable."""
    watchdog_text = _wrapper("arnold-watchdog")
    assert "META_REPAIR_BIN=" in watchdog_text
    assert "dispatch_meta_repair() {" in watchdog_text
    assert "meta_dispatch_marker_path() {" in watchdog_text
    assert "meta_pgid_path() {" in watchdog_text
    assert "meta_dispatch_marker_set() {" in watchdog_text
    assert "check_meta_repair_recursion_guard() {" in watchdog_text

    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    report_path = tmp_path / "report.jsonl"

    script = _build_meta_dispatch_script(
        marker_dir,
        report_path,
        meta_repair_bin="/nonexistent/meta-repair-loop",
        extra_lines=[
            f"dispatch_meta_repair demo-session /tmp/ws /tmp/ws/spec.yaml {str(report_path)!r} test_trigger",
            'DISPATCH_EXIT=$?',
            'echo "RESULT=$REPAIR_DISPATCH_RESULT"',
            'echo "EXIT=$DISPATCH_EXIT"',
        ],
    )

    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "RESULT=unavailable" in result.stdout, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    # dispatch_meta_repair returns 1 for missing binary
    assert "EXIT=1" in result.stdout, f"stdout: {result.stdout}"


def test_meta_repair_dispatch_disabled_flag(tmp_path: Path) -> None:
    """dispatch_meta_repair returns 0 with disabled when META_REPAIR_ENABLED_FLAG != 1."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    report_path = tmp_path / "report.jsonl"

    fake_bin = tmp_path / "arnold-meta-repair-loop"
    fake_bin.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_bin.chmod(0o755)

    script = _build_meta_dispatch_script(
        marker_dir,
        report_path,
        meta_repair_bin=str(fake_bin),
        meta_repair_enabled="0",
        extra_lines=[
            f"dispatch_meta_repair demo-session /tmp/ws /tmp/ws/spec.yaml {str(report_path)!r} test_trigger",
            'echo "RESULT=$REPAIR_DISPATCH_RESULT"',
        ],
    )

    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "RESULT=disabled" in result.stdout, f"stdout: {result.stdout}"


def test_meta_repair_dispatch_enabled_success(tmp_path: Path) -> None:
    """dispatch_meta_repair returns 0 with dispatched when enabled and binary exists."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    report_path = tmp_path / "report.jsonl"

    fake_bin = tmp_path / "arnold-meta-repair-loop"
    fake_bin.write_text("#!/usr/bin/env bash\necho meta-repair ran\nexit 0\n", encoding="utf-8")
    fake_bin.chmod(0o755)

    script = _build_meta_dispatch_script(
        marker_dir,
        report_path,
        meta_repair_bin=str(fake_bin),
        extra_lines=[
            f"dispatch_meta_repair demo-session /tmp/ws /tmp/ws/spec.yaml {str(report_path)!r} test_trigger",
            'echo "RESULT=$REPAIR_DISPATCH_RESULT"',
        ],
    )

    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "RESULT=dispatched" in result.stdout, f"stdout: {result.stdout}"
    # The background dispatch writes pgid asynchronously; wait briefly
    import time as _time

    for _ in range(10):
        if (marker_dir / "demo-session.meta-pgid").exists():
            break
        _time.sleep(0.1)
    pgid_path = marker_dir / "demo-session.meta-pgid"
    assert pgid_path.exists(), f"pgid marker not created at {pgid_path}"
    # Verify the dispatch marker was written
    dispatch_path = marker_dir / "demo-session.meta-dispatch"
    assert dispatch_path.exists(), f"dispatch marker not created at {dispatch_path}"
    marker_fields = dispatch_path.read_text().rstrip("\n").split("\t")
    assert marker_fields[:2] == ["arnold-dispatch-marker-v2", "managed_agent"]
    managed = json.loads(Path(marker_fields[4]).read_text(encoding="utf-8"))
    assert managed["run_id"] == marker_fields[3]
    assert managed["launch_provenance"]["origin_kind"] == "watchdog_meta_repair"
    # Verify report was emitted
    assert report_path.exists(), f"report not created"
    report_content = report_path.read_text(encoding="utf-8")
    assert "dispatched" in report_content, f"report missing dispatched: {report_content}"


def test_meta_repair_dispatch_passes_trigger_to_wrapper(tmp_path: Path) -> None:
    """dispatch_meta_repair passes the watchdog trigger to arnold-meta-repair-loop."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    report_path = tmp_path / "report.jsonl"
    args_path = tmp_path / "args.txt"

    fake_bin = tmp_path / "arnold-meta-repair-loop"
    fake_bin.write_text(
        f"#!/usr/bin/env bash\nprintf '%s\\n' \"$@\" > {str(args_path)!r}\nexit 0\n",
        encoding="utf-8",
    )
    fake_bin.chmod(0o755)

    script = _build_meta_dispatch_script(
        marker_dir,
        report_path,
        meta_repair_bin=str(fake_bin),
        extra_lines=[
            f"dispatch_meta_repair demo-session /tmp/ws /tmp/ws/spec.yaml {str(report_path)!r} repair_timeout",
            'echo "RESULT=$REPAIR_DISPATCH_RESULT"',
        ],
    )

    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "RESULT=dispatched" in result.stdout

    import time as _time

    for _ in range(20):
        if args_path.exists():
            break
        _time.sleep(0.05)
    assert args_path.read_text(encoding="utf-8").splitlines() == [
        "demo-session",
        "repair_timeout",
    ]


def test_meta_repair_dispatch_busy_skip(tmp_path: Path) -> None:
    """dispatch_meta_repair returns 0 with busy when repair loop already active."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    report_path = tmp_path / "report.jsonl"

    fake_bin = tmp_path / "arnold-meta-repair-loop"
    fake_bin.write_text("#!/usr/bin/env bash\necho should not run\nexit 0\n", encoding="utf-8")
    fake_bin.chmod(0o755)

    script = _build_meta_dispatch_script(
        marker_dir,
        report_path,
        meta_repair_bin=str(fake_bin),
        override_kimi_operator="""
kimi_operator_running() { return 0; }
repair_loop_busy_state() { echo same_session; }
""",
        extra_lines=[
            f"dispatch_meta_repair demo-session /tmp/ws /tmp/ws/spec.yaml {str(report_path)!r} test_trigger",
            'echo "RESULT=$REPAIR_DISPATCH_RESULT"',
        ],
    )

    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "RESULT=busy" in result.stdout, f"stdout: {result.stdout}"
    # Verify report was emitted with busy status
    if report_path.exists():
        report_content = report_path.read_text(encoding="utf-8")
        assert "busy" in report_content, f"report missing busy: {report_content}"


def test_meta_repair_dispatch_recursive_skip(tmp_path: Path) -> None:
    """dispatch_meta_repair returns 0 with recursive when meta-repair already exists."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    report_path = tmp_path / "report.jsonl"

    fake_bin = tmp_path / "arnold-meta-repair-loop"
    fake_bin.write_text("#!/usr/bin/env bash\necho should not run\nexit 0\n", encoding="utf-8")
    fake_bin.chmod(0o755)

    # Pre-create a meta-repair record for the same session
    repair_data = marker_dir / "repair-data" / "meta"
    repair_data.mkdir(parents=True)
    (repair_data / "existing-001.json").write_text(
        json.dumps(
            {
                "meta_repair_id": "existing-001",
                "session": "demo-session",
                "trigger": "repair_timeout",
                "outcome": "FIXED",
            }
        ),
        encoding="utf-8",
    )

    script = _build_meta_dispatch_script(
        marker_dir,
        report_path,
        meta_repair_bin=str(fake_bin),
        extra_lines=[
            f"dispatch_meta_repair demo-session /tmp/ws /tmp/ws/spec.yaml {str(report_path)!r} test_trigger",
            'echo "RESULT=$REPAIR_DISPATCH_RESULT"',
        ],
    )

    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "RESULT=recursive" in result.stdout, f"stdout: {result.stdout}"
    # Verify report was emitted with recursive status
    if report_path.exists():
        report_content = report_path.read_text(encoding="utf-8")
        assert "recursive" in report_content, f"report missing recursive: {report_content}"


def test_meta_repair_dispatch_ignores_launch_failure_record(tmp_path: Path) -> None:
    """dispatch_meta_repair should not treat launch-failure meta records as recursion."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    report_path = tmp_path / "report.jsonl"

    fake_bin = tmp_path / "arnold-meta-repair-loop"
    fake_bin.write_text("#!/usr/bin/env bash\necho meta-repair ran\nexit 0\n", encoding="utf-8")
    fake_bin.chmod(0o755)

    repair_data = marker_dir / "repair-data" / "meta"
    repair_data.mkdir(parents=True)
    (repair_data / "launch-failed.json").write_text(
        json.dumps(
            {
                "meta_repair_id": "launch-failed",
                "session": "demo-session",
                "trigger": "partial_liveness_recurrence",
                "diagnosis": "Codex meta-repair orchestrator returned no output (timed out or failed to launch DeepSeek/Hermes subagents); see meta-repair log.",
                "subagent_results": {
                    "codex_response": "Not inside a trusted directory and --skip-git-repo-check was not specified."
                },
                "outcome": "Codex meta-repair orchestrator returned no output (timed out or failed to launch DeepSeek/Hermes subagents); see meta-repair log.",
            }
        ),
        encoding="utf-8",
    )

    script = _build_meta_dispatch_script(
        marker_dir,
        report_path,
        meta_repair_bin=str(fake_bin),
        extra_lines=[
            f"dispatch_meta_repair demo-session /tmp/ws /tmp/ws/spec.yaml {str(report_path)!r} test_trigger",
            'echo "RESULT=$REPAIR_DISPATCH_RESULT"',
        ],
    )

    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "RESULT=dispatched" in result.stdout, f"stdout: {result.stdout}"


def test_meta_repair_dispatch_report_output(tmp_path: Path) -> None:
    """dispatch_meta_repair emits report items for dispatched, disabled, and unavailable cases."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    report_path = tmp_path / "report.jsonl"

    fake_bin = tmp_path / "arnold-meta-repair-loop"
    fake_bin.write_text("#!/usr/bin/env bash\necho ran\nexit 0\n", encoding="utf-8")
    fake_bin.chmod(0o755)

    # Test disabled dispatch
    script_disabled = _build_meta_dispatch_script(
        marker_dir,
        report_path,
        meta_repair_bin=str(fake_bin),
        meta_repair_enabled="0",
        extra_lines=[
            f"dispatch_meta_repair sess-1 /tmp/ws /tmp/ws/spec.yaml {str(report_path)!r}",
        ],
    )
    result = subprocess.run(
        ["bash", "-lc", script_disabled],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0

    # Test missing binary
    script_missing = _build_meta_dispatch_script(
        marker_dir,
        report_path,
        meta_repair_bin="/nonexistent/meta-repair-loop",
        extra_lines=[
            f"dispatch_meta_repair sess-2 /tmp/ws /tmp/ws/spec.yaml {str(report_path)!r} || true",
        ],
    )
    result2 = subprocess.run(
        ["bash", "-lc", script_missing],
        capture_output=True, text=True, check=False,
    )

    # Verify report was emitted
    if report_path.exists():
        report_content = report_path.read_text(encoding="utf-8")
        assert "disabled" in report_content, f"report missing disabled: {report_content}"


def test_meta_repair_marker_and_pgid_helpers(tmp_path: Path) -> None:
    """meta_dispatch_marker_path, meta_pgid_path, meta_dispatch_marker_set/clear work correctly."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()

    script = "\n\n".join(
        [
            _extract_wrapper_function("meta_dispatch_marker_path"),
            _extract_wrapper_function("meta_pgid_path"),
            _extract_wrapper_function("meta_dispatch_marker_set"),
            _extract_wrapper_function("meta_dispatch_marker_clear"),
            f"MARKER_DIR={str(marker_dir)!r}",
            "META_PATH=$(meta_dispatch_marker_path demo)",
            'echo "MARKER=$META_PATH"',
            "PGID_PATH=$(meta_pgid_path demo)",
            'echo "PGID=$PGID_PATH"',
            "meta_dispatch_marker_set demo managed-run /tmp/manifest.json",
            "test -f \"$META_PATH\" && echo MARKER_EXISTS",
            "meta_dispatch_marker_clear demo",
            "test ! -f \"$META_PATH\" && echo MARKER_CLEARED",
        ]
    )

    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    lines = result.stdout.strip().splitlines()
    assert any("MARKER=" in line and ".meta-dispatch" in line for line in lines), f"stdout: {result.stdout}"
    assert any("PGID=" in line and ".meta-pgid" in line for line in lines), f"stdout: {result.stdout}"
    assert "MARKER_EXISTS" in lines, f"stdout: {result.stdout}"
    assert "MARKER_CLEARED" in lines, f"stdout: {result.stdout}"


def test_meta_repair_dispatch_logs_are_redacted(tmp_path: Path) -> None:
    """dispatch_meta_repair log output passes through redaction."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    log_path = tmp_path / "watchdog.log"
    report_path = tmp_path / "report.jsonl"

    fake_bin = tmp_path / "arnold-meta-repair-loop"
    fake_bin.write_text("#!/usr/bin/env bash\necho ran\nexit 0\n", encoding="utf-8")
    fake_bin.chmod(0o755)

    script = _build_meta_dispatch_script(
        marker_dir,
        report_path,
        meta_repair_bin=str(fake_bin),
        log_path=str(log_path),
        extra_lines=[
            f"dispatch_meta_repair demo-session /tmp/ws /tmp/ws/spec.yaml {str(report_path)!r} test_trigger",
        ],
    )

    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    if log_path.exists():
        log_content = log_path.read_text(encoding="utf-8")
        assert "meta-repair background-dispatched" in log_content, f"log: {log_content}"
        assert "session=demo-session" in log_content, f"log: {log_content}"


def test_meta_repair_dispatch_defaults_structural() -> None:
    """Verify META_REPAIR_BIN default and dispatch_meta_repair function exist in watchdog."""
    watchdog_text = _wrapper("arnold-watchdog")

    # Local repair authority must not silently expand into remote publication.
    assert 'PUSH_REPAIRS="${CLOUD_WATCHDOG_PUSH_REPAIRS:-0}"' in watchdog_text
    assert "set CLOUD_WATCHDOG_PUSH_REPAIRS=1" in watchdog_text

    # META_REPAIR_BIN default
    assert 'META_REPAIR_SOURCE_BIN="$SRC_DIR/arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop"' in watchdog_text
    assert 'META_REPAIR_BIN="${CLOUD_WATCHDOG_META_REPAIR_BIN:-$META_REPAIR_SOURCE_BIN}"' in watchdog_text
    assert 'META_REPAIR_FALLBACK_BIN="/usr/local/bin/arnold-meta-repair-loop"' in watchdog_text

    # dispatch_meta_repair function
    assert "dispatch_meta_repair() {" in watchdog_text

    # Helper functions
    assert "check_meta_repair_recursion_guard() {" in watchdog_text
    assert "meta_dispatch_marker_path() {" in watchdog_text
    assert "meta_pgid_path() {" in watchdog_text
    assert "meta_dispatch_marker_set() {" in watchdog_text
    assert "meta_dispatch_marker_clear() {" in watchdog_text

    # Key behaviors
    assert "META_REPAIR_ENABLED_FLAG" in watchdog_text
    assert "meta-repair disabled by feature flag" in watchdog_text
    assert "meta-repair binary missing" in watchdog_text
    assert "meta-repair skipped; repair loop already active" in watchdog_text
    assert "meta-repair recursion guard blocked dispatch" in watchdog_text
    assert "meta-repair background-dispatched" in watchdog_text

    # Partial-liveness tick tracking
    assert "write_partial_liveness_tick() {" in watchdog_text
    assert "run_repair_data_maintenance() {" in watchdog_text


def test_repair_data_maintenance_runs_cleanup_once_and_updates_index(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_dir = marker_dir / "repair-data"
    sidecar_dir = marker_dir / "repair-data.d"
    marker_dir.mkdir(parents=True)
    repair_dir.mkdir(parents=True)

    active_marker = marker_dir / "active-session.json"
    active_marker.write_text(
        json.dumps(
            {
                "session": "active-session",
                "workspace": "/tmp/ws",
                "remote_spec": "/tmp/ws/spec.yaml",
            }
        ),
        encoding="utf-8",
    )
    (repair_dir / "active-session.repair-data.json").write_text(
        json.dumps({"session": "active-session", "outcome": "repairing"}),
        encoding="utf-8",
    )
    stale_snapshot = repair_dir / "stale-session.repair-data.json"
    stale_snapshot.write_text(
        json.dumps({"session": "stale-session", "outcome": "complete"}),
        encoding="utf-8",
    )
    stale_ts = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc).timestamp()
    os.utime(stale_snapshot, (stale_ts, stale_ts))

    (repair_dir / "meta").mkdir()
    stale_meta = repair_dir / "meta" / "meta-old.json"
    stale_meta.write_text(json.dumps({"meta_repair_id": "meta-old"}), encoding="utf-8")
    os.utime(stale_meta, (stale_ts, stale_ts))

    from arnold_pipelines.megaplan.cloud import repair_contract

    repair_contract.update_session_index(
        repair_dir / "index.json",
        "active-session",
        {
            "status": "active",
            "latest_meta_repair_id": "meta-old",
            "latest_meta_outcome": "fixed",
            "latest_meta_record_path": str(stale_meta),
            "latest_meta_recorded_at": "2026-01-01T00:00:00+00:00",
            "refs": {"latest-outcome": {"outcome": "repairing"}},
        },
    )
    repair_contract.update_session_index(
        repair_dir / "index.json",
        "stale-session",
        {"status": "complete", "refs": {"latest-outcome": {"outcome": "complete"}}},
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function_until("run_repair_data_maintenance", "reap_stale_repair_candidates"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_dir)!r}",
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"PYTHONPATH={str(REPO_ROOT)!r}",
            "REPAIR_DATA_RETENTION_INTERVAL_SECS=21600",
            'run_repair_data_maintenance; echo "FIRST=$?"',
            'run_repair_data_maintenance; echo "SECOND=$?"',
        ]
    )

    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "RAN:cleanup-" in result.stdout, f"stdout: {result.stdout}"
    assert "THROTTLED" in result.stdout, f"stdout: {result.stdout}"
    assert not stale_snapshot.exists()
    persisted_index = repair_contract.read_repair_index(repair_dir / "index.json")
    assert "stale-session" not in persisted_index["sessions"]
    assert persisted_index["sessions"]["active-session"]["latest_meta_repair_id"] == ""
    assert (sidecar_dir / "cleanup" / "retention-maintenance.json").exists()


def test_repair_data_maintenance_skips_when_repair_lock_is_busy(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_dir = marker_dir / "repair-data"
    lock_dir = marker_dir / "demo.repair-loop.lock"
    marker_dir.mkdir(parents=True)
    repair_dir.mkdir(parents=True)
    lock_dir.mkdir()
    started_at = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=60)).isoformat()
    (lock_dir / "owner.json").write_text(
        json.dumps(
            {
                "session": "demo",
                "pid": os.getpid(),
                "started_at": started_at,
                "timeout_seconds": 3600,
                    "command": "pytest maintenance lock fixture",
                "cwd": str(tmp_path),
                "hostname": "localhost",
            }
        ),
        encoding="utf-8",
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function_until("run_repair_data_maintenance", "reap_stale_repair_candidates"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_dir)!r}",
            f"WRAPPER_REPO_ROOT={str(REPO_ROOT)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"PYTHONPATH={str(REPO_ROOT)!r}",
            "REPAIR_DATA_RETENTION_INTERVAL_SECS=21600",
            "run_repair_data_maintenance",
        ]
    )

    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "LOCK_BUSY" in result.stdout, f"stdout: {result.stdout}"
    assert not (repair_dir / "index.json").exists()


def test_partial_liveness_tick_writes_sidecar_record(tmp_path: Path) -> None:
    """write_partial_liveness_tick appends a correctly-shaped JSONL record."""
    events_dir = tmp_path / "repair-data.d" / "events"
    events_dir.mkdir(parents=True)
    events_path = events_dir / "events.jsonl"

    # Extract write_partial_liveness_tick via _extract_wrapper_function_until
    # because _extract_wrapper_function cannot handle nested braces in heredocs.
    func_body = _extract_wrapper_function_until(
        "write_partial_liveness_tick", "clear_session_tracking_artifacts"
    )

    script = "\n\n".join(
        [
            func_body,
            f"MARKER_DIR={str(tmp_path)!r}",
            f"REPAIR_DATA_DIR={str(tmp_path)!r}/repair-data",
            "SRC_DIR=/workspace/arnold",
            "WRAPPER_REPO_ROOT=/workspace/arnold",
            "PYTHONPATH=/workspace/arnold",
            f"CLOUD_WATCHDOG_REPAIR_SIDECAR_DIR={str(tmp_path)!r}/repair-data.d",
            "write_partial_liveness_tick demo-session /tmp/ws /tmp/ws/spec.yaml chain demo-plan alive",
        ]
    )

    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    assert events_path.exists(), f"events.jsonl not created at {events_path}"
    lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1, f"expected at least 1 line, got {len(lines)}"

    record = json.loads(lines[0])
    assert record["session"] == "demo-session"
    assert record["outcome"] == "partial_liveness"
    assert record["health"] == "alive"
    assert "recorded_at" in record
    assert record["run_kind"] == "chain"
    assert record["plan_name"] == "demo-plan"


def test_partial_liveness_tick_bounded_history(tmp_path: Path) -> None:
    """write_partial_liveness_tick keeps at most 20 records per sidecar."""
    events_dir = tmp_path / "repair-data.d" / "events"
    events_dir.mkdir(parents=True)
    events_path = events_dir / "events.jsonl"

    # Pre-seed with 25 existing records
    existing = [
        {
            "session": "demo-session",
            "outcome": "partial_liveness",
            "health": "alive",
            "recorded_at": f"2026-07-02T00:{i:02d}:00Z",
            "run_kind": "chain",
            "plan_name": "demo-plan",
        }
        for i in range(25)
    ]
    events_path.write_text(
        "\n".join(json.dumps(e, sort_keys=True) for e in existing) + "\n",
        encoding="utf-8",
    )

    func_body = _extract_wrapper_function_until(
        "write_partial_liveness_tick", "clear_session_tracking_artifacts"
    )

    script = "\n\n".join(
        [
            func_body,
            f"MARKER_DIR={str(tmp_path)!r}",
            f"REPAIR_DATA_DIR={str(tmp_path)!r}/repair-data",
            "SRC_DIR=/workspace/arnold",
            "WRAPPER_REPO_ROOT=/workspace/arnold",
            "PYTHONPATH=/workspace/arnold",
            f"CLOUD_WATCHDOG_REPAIR_SIDECAR_DIR={str(tmp_path)!r}/repair-data.d",
            "write_partial_liveness_tick demo-session /tmp/ws /tmp/ws/spec.yaml chain demo-plan alive",
        ]
    )

    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 20, f"expected 20 lines (25 pre-seeded + 1 new, bounded to 20), got {len(lines)}"


def test_partial_liveness_isolated_does_not_trigger_condition_5() -> None:
    """Isolated partial liveness (1 tick) does NOT trigger condition 5."""
    from arnold_pipelines.megaplan.cloud.meta_repair import classify_repair_system_failure

    classification = classify_repair_system_failure(
        "test-session",
        partial_liveness_ticks=1,
    )
    assert not classification.should_dispatch, (
        "Isolated partial liveness (1 tick) should NOT trigger condition 5"
    )
    assert classification.trigger is None


def test_partial_liveness_repeated_triggers_condition_5() -> None:
    """Repeated partial liveness (2 ticks) DOES trigger condition 5."""
    from arnold_pipelines.megaplan.cloud.meta_repair import (
        MetaRepairTrigger,
        classify_repair_system_failure,
    )

    classification = classify_repair_system_failure(
        "test-session",
        partial_liveness_ticks=2,
    )
    assert classification.should_dispatch, (
        "Repeated partial liveness (2 ticks) SHOULD trigger condition 5"
    )
    assert classification.trigger == MetaRepairTrigger.PARTIAL_LIVENESS_RECURRENCE


def test_partial_liveness_three_ticks_triggers_condition_5() -> None:
    """Three partial liveness ticks also trigger condition 5 (>=2 threshold)."""
    from arnold_pipelines.megaplan.cloud.meta_repair import (
        MetaRepairTrigger,
        classify_repair_system_failure,
    )

    classification = classify_repair_system_failure(
        "test-session",
        partial_liveness_ticks=3,
    )
    assert classification.should_dispatch
    assert classification.trigger == MetaRepairTrigger.PARTIAL_LIVENESS_RECURRENCE
