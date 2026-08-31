from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.runtime_manifest import (
    MANIFEST_SCHEMA_VERSION,
    RuntimeManifest,
    write_manifest,
)
from arnold_pipelines.megaplan.incident.authority import resolve_signal_authority


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPERS = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"
SYSTEMD = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "systemd"


def _start_identity(pid: int) -> str:
    from arnold_pipelines.megaplan.watchdog.worker_identity import (
        read_process_start_identity,
    )

    value = read_process_start_identity(pid)
    assert value
    return value


def _signal_cli(ledger: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    marker_dir = str(payload.get("marker_dir", "/workspace/.megaplan/cloud-sessions"))
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "arnold_pipelines.megaplan.incident.disposition",
            "signal-non-worker",
            "--ledger-root",
            str(ledger),
            "--marker-dir",
            marker_dir,
            "--json-stdin",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )


def _bind_authority(ledger: Path, payload: dict[str, object], victim: subprocess.Popen[str]) -> dict[str, object]:
    """Construct the explicit authority envelope used by the CLI probes."""
    marker_dir = ledger / ".megaplan" / "cloud-sessions"
    (ledger / ".megaplan" / "incident-ledger").mkdir(parents=True, exist_ok=True)
    marker_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(ledger)], check=True)
    (ledger / "seed").write_text("watchdog\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(ledger), "add", "seed"], check=True)
    subprocess.run(["git", "-C", str(ledger), "-c", "user.email=test@example.invalid", "-c", "user.name=pytest", "commit", "-qm", "seed"], check=True)
    head = subprocess.check_output(["git", "-C", str(ledger), "rev-parse", "HEAD"], text=True).strip()
    manifest_path = ledger / ".megaplan" / "bootstrap-manifest.json"
    manifest = RuntimeManifest.from_dict({
        "runtime_id": "watchdog-runtime-test", "schema": MANIFEST_SCHEMA_VERSION,
        "generation": 1, "epic_id": "watchdog-epic", "state": "active", "owner": "pytest",
        "base": {"ref": "refs/heads/main", "commit": head, "editable_install_path": str(ledger), "venv_path": str(ledger / "venv")},
        "epic": {"branch": "watchdog-test", "worktree_path": str(ledger), "venv_path": str(ledger / "venv"), "runtime_root": str(ledger), "expected_head": head, "repair_bin": str(ledger / "bin"), "deps_lockfile": str(ledger / "uv.lock")},
        "indirection": {"host_path": str(ledger), "container_path": str(ledger), "mount_table": [], "execution_namespace": "pytest", "verified_head": head, "last_verified_at": "2026-08-31T00:00:00+00:00", "attestation": {"module_file": str(ledger / "module.py"), "module_digest": "b" * 64, "mount_id": "pytest"}},
        "policy": {"policy_sha": "policy", "model_policy_sha": "model", "sync_policy": "sync"},
        "promotions": [], "timestamps": {"created": "2026-08-31T00:00:00+00:00", "updated": "2026-08-31T00:00:00+00:00", "closed": ""},
        "gc_policy": "closed-only", "commands": ["pytest"],
    })
    write_manifest(manifest, manifest_path)
    progress = ledger / "progress.json"
    progress.write_text("progress\n", encoding="utf-8")
    session = f"test-{payload['site_id']}"
    from arnold_pipelines.megaplan.watchdog.worker_identity import current_boot_identity
    marker = {
        "session": session, "workspace": str(ledger), "run_id": f"run-{session}",
        "bootstrap_manifest_path": str(manifest_path), "runtime_id": manifest.runtime_id,
        "generation": manifest.generation, "manifest_sha256": __import__("hashlib").sha256(manifest_path.read_bytes()).hexdigest(),
        "progress_artifact": str(progress), "progress_content_digest": __import__("hashlib").sha256(progress.read_bytes()).hexdigest(), "progress_identity": "progress-test",
        "supervisor_pid": os.getpid(), "supervisor_process_start_identity": _start_identity(os.getpid()), "boot_identity": current_boot_identity(), "container_identity": os.environ.get("ARNOLD_CONTAINER_IDENTITY") or __import__("socket").gethostname(),
        "victim_pid": victim.pid, "victim_process_start_identity": _start_identity(victim.pid),
    }
    marker["content_digest"] = __import__("hashlib").sha256(json.dumps(marker, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    marker_path = marker_dir / f"{session}.json"
    marker_path.write_text(json.dumps(marker, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    context = resolve_signal_authority(site_id=str(payload["site_id"]), session=session, marker_path=marker_path, target_kind="non_worker", victim_pid=victim.pid, marker_dir=marker_dir, victim_process_start_identity=_start_identity(victim.pid))
    result = {**payload, **context.to_dict(), "marker_dir": str(marker_dir)}
    return result


def _events(ledger: Path) -> list[dict[str, object]]:
    path = ledger / ".megaplan" / "incident-ledger" / "events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_non_worker_cli_requires_two_identical_scans_before_signal(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    victim = subprocess.Popen(["/bin/sleep", "30"])
    try:
        payload = {
            "site_id": "watchdog-test",
            "lifecycle_identity": "lifecycle-1",
            "killer_identity": "pytest",
            "victim_pid": victim.pid,
            "victim_process_start_identity": _start_identity(victim.pid),
            "signal": "SIGTERM",
            "ladder_stage": "term",
            "scan_interval_s": 0.05,
            "require_confirmation": True,
            "relevant_progress_identity": "progress-1",
            "supervisor_incarnation_identity": "supervisor-1",
            "evidence": {"reason": "deterministic-shell-probe"},
        }
        payload = _bind_authority(ledger, payload, victim)
        first = _signal_cli(ledger, payload)
        assert first.returncode == 75, first.stderr
        assert victim.poll() is None

        second = _signal_cli(ledger, payload)
        assert second.returncode == 0, second.stderr
        victim.wait(timeout=3)
        assert victim.returncode == -signal.SIGTERM

        events = _events(ledger)
        kinds = [event["payload"]["event_type"] for event in events]
        assert kinds.index("supervision_confirmation_observed") < kinds.index(
            "supervision_confirmation_consumed"
        ) < kinds.index("non_worker_signal_disposition")
        assert kinds.index("non_worker_signal_disposition") < kinds.index(
            "signal_claimed"
        )

        replay = _signal_cli(ledger, payload)
        assert replay.returncode == 0
        assert json.loads(replay.stdout)["replayed"] is True
        assert sum(
            event["payload"]["event_type"] == "non_worker_signal_disposition"
            for event in events
        ) == 1
    finally:
        if victim.poll() is None:
            victim.kill()
            victim.wait(timeout=3)


def test_non_worker_cli_fails_closed_for_stale_process_identity(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    victim = subprocess.Popen(["/bin/sleep", "30"])
    try:
        payload = {
            "site_id": "watchdog-test",
            "lifecycle_identity": "lifecycle-1",
            "killer_identity": "pytest",
            "victim_pid": victim.pid,
            "victim_process_start_identity": "stale-incarnation",
            "signal": "SIGTERM",
            "scan_interval_s": 0.05,
            "require_confirmation": True,
            "relevant_progress_identity": "progress-1",
            "supervisor_incarnation_identity": "supervisor-1",
        }
        payload = _bind_authority(ledger, payload, victim)
        payload["victim_process_start_identity"] = "stale-incarnation"
        result = _signal_cli(ledger, payload)
        assert result.returncode == 5
        assert victim.poll() is None
        assert not (ledger / ".megaplan" / "incident-ledger" / "events.jsonl").exists()
    finally:
        victim.terminate()
        victim.wait(timeout=3)


def test_term_and_kill_use_distinct_confirmations_and_replay_after_restart(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    victim = subprocess.Popen(
        [sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"]
    )
    try:
        base = {
            "site_id": "watchdog-test",
            "lifecycle_identity": "lifecycle-ladder",
            "killer_identity": "pytest",
            "victim_pid": victim.pid,
            "victim_process_start_identity": _start_identity(victim.pid),
            "scan_interval_s": 0.05,
            "require_confirmation": True,
            "relevant_progress_identity": "progress-ladder",
            "supervisor_incarnation_identity": "supervisor-ladder",
        }
        base = _bind_authority(ledger, base, victim)
        term = {**base, "signal": "SIGTERM", "ladder_stage": "term"}
        kill = {**base, "signal": "SIGKILL", "ladder_stage": "kill"}
        assert _signal_cli(ledger, term).returncode == 75
        assert _signal_cli(ledger, term).returncode == 0
        assert victim.poll() is None
        assert _signal_cli(ledger, kill).returncode == 75
        assert _signal_cli(ledger, kill).returncode == 0
        victim.wait(timeout=3)

        events = _events(ledger)
        observed = [
            event["payload"]
            for event in events
            if event["payload"]["event_type"] == "supervision_confirmation_observed"
        ]
        assert len(observed) == 2
        assert {item["ladder_stage"] for item in observed} == {"term", "kill"}
        assert len({item["confirmation_id"] for item in observed}) == 2

        # A fresh CLI process sees the durable records and must not resignal.
        assert _signal_cli(ledger, term).returncode == 0
        assert _signal_cli(ledger, kill).returncode == 0
        assert sum(
            event["payload"]["event_type"] == "non_worker_signal_disposition"
            for event in events
        ) == 2
    finally:
        if victim.poll() is None:
            victim.kill()
            victim.wait(timeout=3)


def test_shell_bridge_requires_bound_authoritative_context(tmp_path: Path) -> None:
    victim = subprocess.Popen(["/bin/sleep", "30"])
    try:
        result = subprocess.run(
            ["bash", "-c", '. "$1"; arnold_supervisor_runtime_init probe "$PWD" >/dev/null 2>&1; MEGAPLAN_NBF_LEDGER_ROOT="$2"; arnold_supervisor_signal_non_worker_pid test life "$3" SIGTERM term probe', "_", str(WRAPPERS / "arnold-supervisor-runtime-lib"), str(tmp_path), str(victim.pid)],
            cwd=REPO_ROOT,
            env={**os.environ, "MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED": "0", "MEGAPLAN_NBF_SCAN_INTERVAL_SECS": "0.05"},
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 78
        assert victim.poll() is None
    finally:
        victim.terminate()
        victim.wait(timeout=3)


def test_shell_bridge_accepts_marker_bound_manifest_context(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    victim = subprocess.Popen(["/bin/sleep", "120"])
    authority_payload = _bind_authority(workspace, {"site_id": "test"}, victim)
    authority = Path(str(authority_payload["marker_path"]))
    try:
        result = subprocess.run(
            [
                "bash",
                "-c",
                '. "$1"; arnold_supervisor_runtime_init probe "$PWD" >/dev/null 2>&1; start="$(arnold_supervisor_process_start "$3")"; arnold_supervisor_bind_signal_context_for_pid "$3" "$(dirname "$2")" non_worker "$3" "$start"; arnold_supervisor_signal_bound_pid test "$3" SIGTERM term probe',
                "_",
                str(WRAPPERS / "arnold-supervisor-runtime-lib"),
                str(authority),
                str(victim.pid),
                str(workspace),
            ],
            cwd=REPO_ROOT,
            env={key: value for key, value in os.environ.items() if key != "MEGAPLAN_NBF_LEDGER_ROOT"} | {"MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED": "0", "MEGAPLAN_NBF_SCAN_INTERVAL_SECS": "0.05"},
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 75, result.stderr
        assert victim.poll() is None
    finally:
        victim.terminate()
        victim.wait(timeout=3)


def test_shell_bridge_rejects_marker_workspace_without_incident_ledger(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    victim = subprocess.Popen(["/bin/sleep", "120"])
    authority_payload = _bind_authority(workspace, {"site_id": "test"}, victim)
    authority = Path(str(authority_payload["marker_path"]))
    ledger_dir = workspace / ".megaplan" / "incident-ledger"
    ledger_dir.rename(workspace / ".megaplan" / "incident-ledger-hidden")
    try:
        result = subprocess.run(
            [
                "bash", "-c",
                '. "$1"; arnold_supervisor_runtime_init probe "$PWD" >/dev/null 2>&1; start="$(arnold_supervisor_process_start "$3")"; arnold_supervisor_bind_signal_context_for_pid "$3" "$(dirname "$2")" non_worker "$3" "$start"',
                "_", str(WRAPPERS / "arnold-supervisor-runtime-lib"), str(authority), str(victim.pid),
            ],
            cwd=REPO_ROOT,
            env={key: value for key, value in os.environ.items() if key != "MEGAPLAN_NBF_LEDGER_ROOT"} | {"MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED": "0"},
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 78
        assert victim.poll() is None
    finally:
        victim.terminate()
        victim.wait(timeout=3)


def test_shell_bridge_rejects_mismatched_ambient_ledger_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    victim = subprocess.Popen(["/bin/sleep", "120"])
    authority_payload = _bind_authority(workspace, {"site_id": "test"}, victim)
    authority = Path(str(authority_payload["marker_path"]))
    other_root = tmp_path / "other"
    (other_root / ".megaplan" / "incident-ledger").mkdir(parents=True)
    try:
        result = subprocess.run(
            [
                "bash", "-c",
                '. "$1"; arnold_supervisor_runtime_init probe "$PWD" >/dev/null 2>&1; export MEGAPLAN_NBF_LEDGER_ROOT="$4"; start="$(arnold_supervisor_process_start "$3")"; arnold_supervisor_bind_signal_context_for_pid "$3" "$(dirname "$2")" non_worker "$3" "$start"',
                "_", str(WRAPPERS / "arnold-supervisor-runtime-lib"), str(authority), str(victim.pid), str(other_root),
            ],
            cwd=REPO_ROOT,
            env={key: value for key, value in os.environ.items() if key != "MEGAPLAN_NBF_LEDGER_ROOT"} | {"MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED": "0"},
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 78
        assert victim.poll() is None
    finally:
        victim.terminate()
        victim.wait(timeout=3)


@pytest.mark.parametrize(
    "path",
    [
        WRAPPERS / "arnold-supervisor-runtime-lib",
        WRAPPERS / "arnold-heartbeat",
        WRAPPERS / "arnold-watchdog",
        WRAPPERS / "arnold-progress-auditor",
        SYSTEMD / "ensure-megaplan-watchdog",
        SYSTEMD / "ensure-megaplan-resident",
    ],
)
def test_nbf05_shell_sites_are_syntax_valid(path: Path) -> None:
    result = subprocess.run(
        ["bash", "-n", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_shell_signal_sites_have_no_raw_delivery_primitives() -> None:
    paths = [
        WRAPPERS / "arnold-heartbeat",
        WRAPPERS / "arnold-watchdog",
        WRAPPERS / "arnold-progress-auditor",
        SYSTEMD / "ensure-megaplan-watchdog",
        SYSTEMD / "ensure-megaplan-resident",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "arnold_supervisor_signal_bound_pid" in text
    assert "xargs -r kill" not in (
        SYSTEMD / "ensure-megaplan-watchdog"
    ).read_text(encoding="utf-8")
    assert 'kill -INT "$pid"' not in (
        WRAPPERS / "arnold-heartbeat"
    ).read_text(encoding="utf-8")


def test_shell_consumers_bind_target_context_and_use_bound_signal_door() -> None:
    runtime = (WRAPPERS / "arnold-supervisor-runtime-lib").read_text(encoding="utf-8")
    heartbeat = (WRAPPERS / "arnold-heartbeat").read_text(encoding="utf-8")
    watchdog = (WRAPPERS / "arnold-watchdog").read_text(encoding="utf-8")
    auditor = (WRAPPERS / "arnold-progress-auditor").read_text(encoding="utf-8")
    resident = (SYSTEMD / "ensure-megaplan-resident").read_text(encoding="utf-8")
    ensure_watchdog = (SYSTEMD / "ensure-megaplan-watchdog").read_text(encoding="utf-8")

    assert "arnold_supervisor_signal_bound_pid()" in runtime
    assert "arnold_supervisor_bind_signal_context_for_session()" in runtime
    assert "arnold_supervisor_bind_signal_context_for_pid()" in runtime
    assert "resolve-signal-context" in runtime
    assert '"marker_path": marker' in runtime
    assert "os.environ.get(\"ARNOLD_RUNTIME_MANIFEST\")" not in runtime
    assert "#{pid}" in runtime and "#{session_id}" in runtime and "#{session_name}" in runtime
    assert "#{pane_id}" in runtime and "command_digest" in runtime
    assert "head -1" not in runtime[runtime.index("arnold_supervisor_tmux_session_snapshot"):runtime.index("arnold_supervisor_tmux_session_revalidate")]
    for text in (heartbeat, watchdog, auditor, resident, ensure_watchdog):
        assert "arnold_supervisor_signal_bound_pid" in text or text is auditor
        assert "arnold_supervisor_signal_non_worker_pid" not in text
    assert 'tmux -S "$tmux_socket" kill-session -t "=$tmux_session_id"' in resident
    assert 'tmux -S "$tmux_socket" kill-session -t "=$tmux_session_id"' in watchdog
    assert 'tmux kill-session -t "$tmux_session_id" 2>/dev/null || true' not in watchdog
    assert 'tmux kill-session -t "$tmux_session_id" 2>/dev/null || true' not in resident


def test_tmux_replacement_and_missing_context_are_fail_closed() -> None:
    runtime = (WRAPPERS / "arnold-supervisor-runtime-lib").read_text(encoding="utf-8")
    watchdog = (WRAPPERS / "arnold-watchdog").read_text(encoding="utf-8")
    resident = (SYSTEMD / "ensure-megaplan-resident").read_text(encoding="utf-8")
    # The requery binds socket inode, server incarnation, exact session name/id,
    # and a digest over every pane; any replacement must fail before teardown.
    for token in ("expected_server_pid", "expected_server_start", "expected_session_id", "expected_session_name", "expected_pane_digest"):
        assert token in runtime
    assert '[[ "$current_fingerprint" == "$expected_socket_fingerprint" ]] || return 78' in runtime
    assert '[[ "$current_server_pid" == "$expected_server_pid" && "$current_server_start" == "$expected_server_start" ]] || return 78' in runtime
    assert '[[ "$current_digest" == "$expected_pane_digest" ]] || return 78' in runtime
    assert 'marker_dir="${MEGAPLAN_WATCHDOG_MARKER_DIR:-/workspace/.megaplan/cloud-sessions}"' in (
        SYSTEMD / "ensure-megaplan-watchdog"
    ).read_text(encoding="utf-8")
    assert 'marker_dir="${MEGAPLAN_RESIDENT_MARKER_DIR:-/workspace/.megaplan/cloud-sessions}"' in resident
    assert 'MEGAPLAN_NBF_AUTHORITY_PATH' not in watchdog
    assert 'MEGAPLAN_NBF_AUTHORITY_PATH' not in resident


def test_tmux_teardown_uses_marker_owned_pane_and_captured_socket() -> None:
    runtime = (WRAPPERS / "arnold-supervisor-runtime-lib").read_text(encoding="utf-8")
    watchdog = (WRAPPERS / "arnold-watchdog").read_text(encoding="utf-8")
    resident = (SYSTEMD / "ensure-megaplan-resident").read_text(encoding="utf-8")
    assert "arnold_supervisor_tmux_owned_pane()" in runtime
    assert "pane_process_start_identity" in runtime
    assert 'tmux -S "$socket" list-panes' in runtime
    assert '[[ "$matches" -eq 1 ]] || return 78' in runtime
    assert 'tmux display-message' not in runtime
    assert "arnold_supervisor_tmux_owned_pane \"$session\"" in watchdog
    assert "arnold_supervisor_tmux_owned_pane megaplan-resident-discord" in resident
    assert "tmux_first_pane" not in watchdog
    assert "tmux_first_pane" not in resident
    assert 'tmux -S "$tmux_socket" has-session -t "=$tmux_session_id"' in watchdog
    assert 'tmux -S "$tmux_socket" has-session -t "=$tmux_session_id"' in resident


def test_socket_and_descendant_contracts_fail_closed() -> None:
    runtime = (WRAPPERS / "arnold-supervisor-runtime-lib").read_text(encoding="utf-8")
    watchdog = (WRAPPERS / "arnold-watchdog").read_text(encoding="utf-8")
    assert 'tmux_keys = ("tmux_socket", "tmux_socket_fingerprint", "tmux_server_pid"' in runtime
    assert 'server_pid = data["tmux_server_pid"]' in runtime
    assert '"tmux_server_process_start_identity"' in runtime
    assert 'socket="/tmp/tmux-' not in runtime
    assert "arnold_supervisor_validate_descendant()" in runtime
    assert 'arnold_supervisor_validate_descendant "$root_pid" "$pid"' in watchdog
    assert 'descendant_starts[$pid]' in watchdog
