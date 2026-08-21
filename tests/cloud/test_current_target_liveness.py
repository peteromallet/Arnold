from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.current_target import resolve_current_target
from arnold_pipelines.megaplan.cloud.current_target_liveness import (
    SCHEMA,
    control_liveness_from_current_target,
    observe_current_target_liveness,
)
from arnold_pipelines.megaplan.cloud.liveness_lease import LivenessLeasePublisher
from arnold_pipelines.megaplan.cloud.meta_repair import classify_repair_system_failure
from arnold_pipelines.megaplan.cloud.progress_auditor_liveness import (
    classify_runner_liveness,
)
from arnold_pipelines.megaplan.cloud.repair_goal import (
    _fence_unknown_liveness_control,
)


def _marker(tmp_path: Path, **extra: object) -> dict[str, object]:
    marker = {
        "session": "demo",
        "workspace": str(tmp_path / "workspace"),
        "remote_spec": str(tmp_path / "workspace" / "chain.yaml"),
        "run_kind": "chain",
        "identity_digest": "launch-1",
        "started_at": "2026-08-03T18:00:00Z",
        "run_id": "run-1",
        **extra,
    }
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "demo.json").write_text(json.dumps(marker), encoding="utf-8")
    return marker


def test_foreign_namespace_pid_collision_is_unknown(tmp_path: Path) -> None:
    marker = _marker(
        tmp_path,
        pid=4242,
        pid_namespace_id="pid:[foreign]",
        process_start_identity="boot-a:10",
    )
    start_probe_called = False

    def start_probe(_pid: int) -> str:
        nonlocal start_probe_called
        start_probe_called = True
        return "boot-a:10"

    observed = observe_current_target_liveness(
        marker,
        marker_dir=tmp_path,
        observer_pid_namespace_id="pid:[resident]",
        pid_is_live=lambda _pid: True,
        process_start_identity=start_probe,
    )

    assert observed["state"] == "unknown"
    assert observed["control_permitted"] is False
    assert start_probe_called is False


def test_same_namespace_and_start_identity_establish_live(tmp_path: Path) -> None:
    marker = _marker(
        tmp_path,
        pid=4242,
        pid_namespace_id="pid:[same]",
        process_start_identity="boot-a:10",
    )
    observed = observe_current_target_liveness(
        marker,
        marker_dir=tmp_path,
        observer_pid_namespace_id="pid:[same]",
        pid_is_live=lambda _pid: True,
        process_start_identity=lambda _pid: "boot-a:10",
    )

    assert observed["state"] == "live"
    assert observed["source"] == "matched_local_process_identity"


def test_complete_active_step_binding_beats_unbound_marker_pid(tmp_path: Path) -> None:
    marker = _marker(tmp_path, pid=111)
    observed = observe_current_target_liveness(
        marker,
        marker_dir=tmp_path,
        active_step={
            "worker_pid": 222,
            "worker_pid_namespace_id": "pid:[same]",
            "worker_process_start_identity": "boot-a:20",
        },
        observer_pid_namespace_id="pid:[same]",
        pid_is_live=lambda pid: pid == 222,
        process_start_identity=lambda pid: "boot-a:20" if pid == 222 else None,
    )

    assert observed["state"] == "live"
    assert observed["identity"]["source"] == "active_step"


def test_local_active_step_binding_beats_foreign_marker_pid(tmp_path: Path) -> None:
    """A marker PID bound to a foreign namespace must not blind the observer to
    a live active-step worker bound to this observer's namespace.

    Regression: the launch (marker) identity was preferred whenever it was
    complete, so a stale runner-container PID in the marker collapsed the
    canonical liveness to ``unknown`` and fenced every repair/retrigger
    decision even while the plan's own active worker was provably live in the
    observer's namespace.
    """
    marker = _marker(
        tmp_path,
        pid=4242,
        pid_namespace_id="pid:[foreign]",
        process_start_identity="boot-a:10",
    )
    observed = observe_current_target_liveness(
        marker,
        marker_dir=tmp_path,
        active_step={
            "worker_pid": 222,
            "worker_pid_namespace_id": "pid:[same]",
            "worker_process_start_identity": "boot-a:20",
        },
        observer_pid_namespace_id="pid:[same]",
        pid_is_live=lambda pid: pid == 222,
        process_start_identity=lambda pid: "boot-a:20" if pid == 222 else None,
    )

    assert observed["state"] == "live"
    assert observed["identity"]["source"] == "active_step"
    assert observed["identity"]["namespace_matches"] is True


def test_local_active_step_nested_runner_incarnation_beats_foreign_marker(
    tmp_path: Path,
) -> None:
    """The plan engine writes the active-worker binding inside
    ``active_step.runner_incarnation``; the observer must read it there."""
    marker = _marker(
        tmp_path,
        pid=4242,
        pid_namespace_id="pid:[foreign]",
        process_start_identity="boot-a:10",
    )
    observed = observe_current_target_liveness(
        marker,
        marker_dir=tmp_path,
        active_step={
            "worker_pid": 222,
            "runner_incarnation": {
                "schema": "arnold.megaplan.runner_incarnation.v1",
                "host_id": "host-1",
                "pid_namespace_id": "pid:[same]",
                "worker_pid": 222,
                "worker_process_start_identity": "boot-a:20",
            },
        },
        observer_pid_namespace_id="pid:[same]",
        pid_is_live=lambda pid: pid == 222,
        process_start_identity=lambda pid: "boot-a:20" if pid == 222 else None,
    )

    assert observed["state"] == "live"
    assert observed["source"] == "matched_local_process_identity"
    assert observed["identity"]["source"] == "active_step"
    assert observed["identity"]["pid"] == 222


def test_same_pid_with_different_start_identity_proves_old_target_dead(
    tmp_path: Path,
) -> None:
    marker = _marker(
        tmp_path,
        pid=4242,
        pid_namespace_id="pid:[same]",
        process_start_identity="boot-a:10",
    )
    observed = observe_current_target_liveness(
        marker,
        marker_dir=tmp_path,
        observer_pid_namespace_id="pid:[same]",
        pid_is_live=lambda _pid: True,
        process_start_identity=lambda _pid: "boot-a:11",
    )

    assert observed["state"] == "dead"
    assert "reused" in observed["reason"]


def test_bound_absent_pid_proves_dead_but_bare_pid_does_not(tmp_path: Path) -> None:
    bound = _marker(
        tmp_path,
        pid=4242,
        pid_namespace_id="pid:[same]",
        process_start_identity="boot-a:10",
    )
    dead = observe_current_target_liveness(
        bound,
        marker_dir=tmp_path,
        observer_pid_namespace_id="pid:[same]",
        pid_is_live=lambda _pid: False,
    )
    bare = observe_current_target_liveness(
        {**bound, "pid_namespace_id": "", "process_start_identity": ""},
        marker_dir=tmp_path,
        observer_pid_namespace_id="pid:[same]",
        pid_is_live=lambda _pid: False,
    )

    assert dead["state"] == "dead"
    assert bare["state"] == "unknown"


def test_fresh_owner_lease_establishes_live_across_namespace(tmp_path: Path) -> None:
    marker = _marker(tmp_path)
    publisher = LivenessLeasePublisher(
        "demo", marker_dir=tmp_path, target_pid=os.getpid()
    )
    publisher.publish_once()
    marker = json.loads((tmp_path / "demo.json").read_text(encoding="utf-8"))

    observed = observe_current_target_liveness(
        marker,
        marker_dir=tmp_path,
        observer_pid_namespace_id="pid:[different]",
    )

    assert observed["state"] == "live"
    assert observed["source"] == "fresh_owner_lease"


def test_resolver_uses_injected_bound_probes_without_shadowing(tmp_path: Path) -> None:
    _marker(
        tmp_path,
        pid=4242,
        pid_namespace_id="pid:[same]",
        process_start_identity="boot-a:10",
    )
    calls: list[tuple[str, int]] = []

    record = resolve_current_target(
        "demo",
        marker_dir=tmp_path,
        pid_is_live=lambda pid: calls.append(("pid", pid)) or True,
        process_start_identity=lambda pid: calls.append(("start", pid)) or "boot-a:10",
        observer_pid_namespace_id="pid:[same]",
    )

    assert record["current_target_liveness"]["state"] == "live"
    assert calls == [("pid", 4242), ("start", 4242)]


def test_unknown_current_target_blocks_meta_repair_dispatch() -> None:
    classification = classify_repair_system_failure(
        "demo",
        current_target_observation={
            "current_target_liveness": {
                "schema": SCHEMA,
                "state": "unknown",
                "known": False,
            }
        },
        repair_budget_exhausted=True,
        repair_outcome="repair_timeout",
    )

    assert classification.should_dispatch is False
    assert "UNKNOWN" in classification.rationale[0]


def test_progress_auditor_cannot_upgrade_bound_unknown_from_legacy_dead_signal() -> (
    None
):
    result = classify_runner_liveness(
        {"live_status": "dead"},
        {},
        ["terminal_repair_failure"],
        bound_observation={"schema": SCHEMA, "state": "unknown"},
    )

    assert result["state"] == "unknown"
    assert result["control_permitted"] is False


def test_repair_goal_unknown_liveness_fences_escalation() -> None:
    observation = {
        "session_identity": {"identity_matches": True},
        "current_target_liveness": {
            "schema": SCHEMA,
            "state": "unknown",
            "known": False,
        },
        "chain_completed_count": 0,
        "chain_current_milestone_index": 0,
        "chain_current_plan_name": "p1",
    }
    result = _fence_unknown_liveness_control(
        {"status": "active", "control_action": "meta_repair", "reason": "retry"},
        observation,
    )

    assert result["control_action"] == "observe"
    assert result["status"] == "active"


def _canonical(state: str) -> dict[str, object]:
    known = state in {"live", "dead"}
    return {
        "schema": SCHEMA,
        "state": state,
        "live": state == "live",
        "dead": state == "dead",
        "known": known,
        "source": "test_bound_identity",
        "identity": {"source": "marker", "pid": 42},
        "lease": {},
        "diagnostics": [],
        "control_permitted": known,
        "mutation_permitted": known,
        "escalation_permitted": known,
        "retrigger_permitted": known,
    }


@pytest.mark.parametrize("state", ["live", "dead", "unknown"])
def test_wrapper_control_adapter_is_strict_tri_state(state: str) -> None:
    result = control_liveness_from_current_target(
        {"current_target_liveness": _canonical(state)}, action="mutation"
    )

    assert result["state"] == state
    assert result.get("action_permitted", False) is False
    assert result.get("mutation_permitted") is False
    assert result.get("authorizes_mutation") is False


@pytest.mark.parametrize(
    "target",
    [
        None,
        {},
        {"current_target_liveness": {"schema": SCHEMA, "state": "dead"}},
        {
            "current_target_liveness": {
                **_canonical("dead"),
                "mutation_permitted": False,
            }
        },
        {
            "current_target_liveness": {
                **_canonical("live"),
                "state": "dead",
            },
            "active_step_heartbeat": {
                "worker_pid": 42,
                "pid_live": True,
                "active": True,
            },
            "tmux_process": {"session_live": True, "live_status": "alive"},
        },
    ],
)
def test_missing_or_corrupt_canonical_record_blocks_legacy_control(
    target: dict[str, object] | None,
) -> None:
    result = control_liveness_from_current_target(target, action="mutation")

    raw = (target or {}).get("current_target_liveness") if isinstance(target, dict) else None
    tri_state_ok = (
        isinstance(raw, dict)
        and raw.get("schema") == SCHEMA
        and raw.get("state") in {"live", "dead", "unknown"}
        and raw.get("known") is (raw.get("state") in {"live", "dead"})
        and raw.get("live") is (raw.get("state") == "live")
        and raw.get("dead") is (raw.get("state") == "dead")
    )
    if tri_state_ok:
        assert result["state"] == raw["state"]
    else:
        assert result["state"] == "unknown"
    assert result["action_permitted"] is False
    assert result["mutation_permitted"] is False


def test_legacy_classifier_is_explicitly_diagnostic_only() -> None:
    result = classify_runner_liveness(
        {"pid": 42, "pid_live": True, "session": "legacy", "session_live": True},
        {"present": True, "worker_pid": 42, "worker_pid_alive": True},
        [],
    )

    assert result["state"] == "alive"
    assert result["diagnostic_only"] is True
    assert result["authoritative"] is False
    assert result["control_permitted"] is False


def test_watchdog_wrapper_requires_minted_capability() -> None:
    wrapper = Path(__file__).resolve().parents[2] / (
        "arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog"
    )
    source = wrapper.read_text(encoding="utf-8")
    assert "canonical_mutation_permitted=1" not in source
    assert "canonical_liveness_known" in source
    assert "babysitter/relaunch/drive require a minted MutationCapability" in source
    assert "canonical MutationCapability absent; observe-only" in source
    assert source.count("canonical_mutation_fenced \"parked pre-execute drive\"") >= 2
    assert "canonical_mutation_fenced \"driveable leftover-worker drive\"" in source
    assert "if [[ \"$canonical_mutation_permitted\" == \"1\" ]]; then" not in source
    assert "environment gone observed; retirement fenced without minted MutationCapability" in source
    assert "alive-path marker-clear observe-only without minted MutationCapability" in source
    assert "stale repair needs-human marker preserved; observe-only without minted MutationCapability" in source
    assert "if [[ \"$MUTATION_CAPABILITY_PRESENT\" == \"1\" ]]; then" in source
    persist = source[source.index("persist_environment_gone_outcome() {"):]
    persist = persist[: persist.index("clear_session_tracking_artifacts() {")]
    assert 'MUTATION_CAPABILITY_PRESENT:-0}" != "1"' in persist
    clear = source[source.index("clear_session_tracking_artifacts() {"):]
    clear = clear[: clear.index("plan_terminal_status() {")]
    assert 'MUTATION_CAPABILITY_PRESENT:-0}" != "1"' in clear
    kimi = source[source.index("kimi_dispatch_marker_clear() {"):]
    kimi = kimi[: kimi.index("meta_dispatch_marker_set() {")]
    assert 'MUTATION_CAPABILITY_PRESENT:-0}" != "1"' in kimi
    sidecar = source[source.index("emit_current_needs_human_sidecar() {"):]
    sidecar = sidecar[: sidecar.index("current_target_plan_name_from_observation() {")]
    assert 'MUTATION_CAPABILITY_PRESENT:-0}" != "1"' in sidecar


def test_liveness_fired_paths_are_observe_only_without_minted_capability(
    tmp_path: Path,
) -> None:
    """Known live/dead without a minted capability must not effect.

    With a minted capability the same three paths may write/delete.
    """

    import subprocess
    import textwrap

    from arnold_pipelines.megaplan.cloud.current_target_liveness import (
        attach_mutation_capability,
        mint_mutation_capability,
    )
    from arnold_pipelines.megaplan.cloud.repair_contract import ENVIRONMENT_GONE

    wrapper = Path(__file__).resolve().parents[2] / (
        "arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog"
    )
    source = wrapper.read_text(encoding="utf-8")

    def _extract(name: str, until: str) -> str:
        start = source.index(f"{name}() {{")
        end = source.index(f"{until}() {{", start)
        return source[start:end]

    root = tmp_path / "t41-liveness-effects"
    root.mkdir()
    session = "demo-session"
    marker_dir = root / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    log_path = root / "watchdog.log"
    data_file = repair_data_dir / f"{session}.repair-data.json"
    kimi_marker = marker_dir / f"{session}.kimi-dispatch"
    kimi_pgid = marker_dir / f"{session}.kimi-pgid"
    needs_human = repair_data_dir / f"{session}.needs-human.json"
    session_marker = marker_dir / f"{session}.json"
    for path, body in (
        (kimi_marker, "dispatch\n"),
        (kimi_pgid, "123\n"),
        (needs_human, '{"plan":"demo"}\n'),
        (session_marker, '{"session":"demo-session"}\n'),
    ):
        path.write_text(body, encoding="utf-8")
    data_file.write_text('{"session": "demo-session"}\n', encoding="utf-8")

    helpers = "\n".join(
        [
            _extract("kimi_dispatch_marker_path", "kimi_pgid_path"),
            _extract("kimi_pgid_path", "meta_dispatch_marker_path"),
            _extract("kimi_dispatch_marker_clear", "meta_dispatch_marker_set"),
            _extract("repair_needs_human_path", "chain_health_snapshot_path"),
            _extract("session_marker_path", "repair_progress_snapshot_path"),
            _extract("persist_environment_gone_outcome", "clear_session_tracking_artifacts"),
            _extract("clear_session_tracking_artifacts", "plan_terminal_status"),
        ]
    )

    repo_root = Path(__file__).resolve().parents[2]
    script_observe = textwrap.dedent(
        f"""
        set -euo pipefail
        SRC_DIR={str(repo_root)!r}
        MARKER_DIR={str(marker_dir)!r}
        REPAIR_DATA_DIR={str(repair_data_dir)!r}
        LOG={str(log_path)!r}
        MUTATION_CAPABILITY_PRESENT=0
        log() {{ printf '%s\\n' "$*" >>"$LOG"; }}
        authority_gap_continue() {{ return 0; }}
        chain_health_snapshot_path() {{ printf '%s/%s.chain-health.json' "$MARKER_DIR" "$1"; }}
        chain_health_artifact_path() {{ printf '%s/%s.chain-health.artifact' "$MARKER_DIR" "$1"; }}
        {helpers}
        persist_environment_gone_outcome {session!r} /tmp/ws /tmp/spec chain demo-plan
        clear_session_tracking_artifacts {session!r} demo-plan
        kimi_dispatch_marker_clear {session!r}
        """
    )
    subprocess.run(["bash", "-c", script_observe], check=True, cwd=str(root))
    assert ENVIRONMENT_GONE not in data_file.read_text(encoding="utf-8")
    assert kimi_marker.exists()
    assert kimi_pgid.exists()
    assert needs_human.exists()
    assert session_marker.exists()

    evidence_root = root / "live-import-root"
    evidence_root.mkdir()
    interpreter = root / "generation" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
    evidence = {
        "occurrence": "occ-liveness",
        "target": "target-liveness",
        "cursor": "cursor-liveness",
        "fence_epoch": 1,
        "evidence_digest": "e" * 64,
        "scope": "repair",
        "custody": "custody:occ-liveness",
        "import_root": str(evidence_root),
        "interpreter": str(interpreter),
        "runtime_manifest": {
            "epic": {
                "runtime_root": str(evidence_root),
                "dependency_generation": {"interpreter_path": str(interpreter)},
            }
        },
    }
    cap = mint_mutation_capability(
        action="repair",
        evidence=evidence,
        process_root=evidence_root,
        process_python=interpreter,
    )
    attach_mutation_capability(cap, identity="occ-liveness")
    assert cap.custody

    script_effect = textwrap.dedent(
        f"""
        set -euo pipefail
        SRC_DIR={str(repo_root)!r}
        MARKER_DIR={str(marker_dir)!r}
        REPAIR_DATA_DIR={str(repair_data_dir)!r}
        LOG={str(log_path)!r}
        MUTATION_CAPABILITY_PRESENT=1
        PYTHONPATH="$SRC_DIR:${{PYTHONPATH:-}}"
        export PYTHONPATH
        log() {{ printf '%s\\n' "$*" >>"$LOG"; }}
        authority_gap_continue() {{ return 0; }}
        chain_health_snapshot_path() {{ printf '%s/%s.chain-health.json' "$MARKER_DIR" "$1"; }}
        chain_health_artifact_path() {{ printf '%s/%s.chain-health.artifact' "$MARKER_DIR" "$1"; }}
        {helpers}
        persist_environment_gone_outcome {session!r} /tmp/ws /tmp/spec chain demo-plan
        clear_session_tracking_artifacts {session!r} demo-plan
        """
    )
    subprocess.run(["bash", "-c", script_effect], check=True, cwd=str(root))
    assert ENVIRONMENT_GONE in data_file.read_text(encoding="utf-8")
    assert not kimi_marker.exists()
    assert not needs_human.exists()
