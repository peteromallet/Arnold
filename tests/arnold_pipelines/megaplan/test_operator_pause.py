from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.chain.operator_pause import is_paused, pause_chain, resume_chain
from arnold_pipelines.megaplan.chain.spec import ChainState, load_chain_state, save_chain_state
from arnold_pipelines.megaplan.types import CliError


def _chain(tmp_path: Path, *, complete: bool = False) -> tuple[Path, Path]:
    initiative = tmp_path / ".megaplan" / "initiatives" / "demo"
    initiative.mkdir(parents=True)
    brief = initiative / "brief.md"
    brief.write_text("# brief\n")
    spec = initiative / "chain.yaml"
    spec.write_text(
        "anchors:\n  north_star: brief.md\n"
        "milestones:\n  - label: M1\n    idea: brief.md\n"
    )
    plan = tmp_path / ".megaplan" / "plans" / "demo-plan"
    plan.mkdir(parents=True)
    (plan / "state.json").write_text(
        json.dumps(
            {
                "current_state": "blocked",
                "resume_cursor": {"phase": "execute", "retry_strategy": "rerun_phase"},
                "active_step": {"phase": "execute", "worker_pid": 999999},
                "meta": {"kept": True},
            }
        )
    )
    state = ChainState(
        current_milestone_index=1 if complete else 0,
        current_plan_name=None if complete else "demo-plan",
        last_state="blocked",
        completed=[{"label": "M1", "plan": "demo-plan", "status": "done"}] if complete else [],
    )
    save_chain_state(spec, state)
    return spec, plan


def test_pause_and_resume_preserve_cursor_workspace_and_artifacts(tmp_path: Path) -> None:
    spec, plan = _chain(tmp_path)
    artifact = plan / "result.md"
    artifact.write_text("keep me")
    before = json.loads((plan / "state.json").read_text())

    paused = pause_chain(spec, tmp_path, reason="capacity control")

    after = json.loads((plan / "state.json").read_text())
    chain_state = load_chain_state(spec)
    assert paused["changed"] is True
    assert is_paused(chain_state)
    assert chain_state.last_state == "paused"
    assert after["current_state"] == "paused"
    assert after["resume_cursor"] == before["resume_cursor"]
    assert after["active_step"] == before["active_step"]
    assert artifact.read_text() == "keep me"

    resumed = resume_chain(spec, tmp_path)

    restored = json.loads((plan / "state.json").read_text())
    assert resumed["restored_plan_state"] == "blocked"
    assert restored["current_state"] == "blocked"
    assert restored["resume_cursor"] == before["resume_cursor"]
    assert restored["active_step"] == before["active_step"]
    assert not is_paused(load_chain_state(spec))


def test_pause_is_idempotent_and_completed_chain_is_excluded(tmp_path: Path) -> None:
    spec, _ = _chain(tmp_path)
    pause_chain(spec, tmp_path, reason="first")
    second = pause_chain(spec, tmp_path, reason="second")
    assert second["changed"] is False
    assert second["authority"]["reason"] == "first"

    other = tmp_path / "complete"
    other.mkdir()
    complete_spec, _ = _chain(other, complete=True)
    with pytest.raises(CliError, match="completed chains cannot be paused"):
        pause_chain(complete_spec, other, reason="must refuse")


def test_resume_reconciles_plan_authority_when_exiting_runner_overwrites_chain_pause(
    tmp_path: Path,
) -> None:
    spec, plan = _chain(tmp_path)
    pause_chain(spec, tmp_path, reason="manual repair")

    # Model the exact race: an already-exiting runner saves its stale chain
    # metadata after pause_chain(), while the CAS-written plan authority stays.
    raced = load_chain_state(spec)
    raced.metadata.pop("operator_pause", None)
    save_chain_state(spec, raced)

    resumed = resume_chain(spec, tmp_path, actor="repair-owner")

    restored = json.loads((plan / "state.json").read_text())
    chain_state = load_chain_state(spec)
    assert resumed["changed"] is True
    assert resumed["restored_plan_state"] == "blocked"
    assert restored["current_state"] == "blocked"
    assert "operator_pause" not in restored["meta"]
    assert chain_state.last_state == "blocked"
    assert chain_state.metadata["operator_resume"]["actor"] == "repair-owner"


def test_legacy_authority_cleared_hold_accepts_newer_resumable_plan_state(
    tmp_path: Path,
) -> None:
    spec, plan = _chain(tmp_path)
    pause_chain(spec, tmp_path, reason="legacy direct phase")
    first = resume_chain(spec, tmp_path, actor="legacy-no-start")

    plan_state = json.loads((plan / "state.json").read_text())
    plan_state["current_state"] = "finalized"
    (plan / "state.json").write_text(json.dumps(plan_state))

    resumed = resume_chain(
        spec,
        tmp_path,
        actor="operator",
        allow_legacy_authority_cleared_hold=True,
    )
    assert resumed["changed"] is False
    assert resumed["already_resumed"] is True
    assert resumed["current_plan_state"] == "finalized"
    assert resumed["resume_authority"] == first["resume_authority"]


def test_cloud_session_pause_stops_only_owned_runner_and_repair(tmp_path: Path, monkeypatch) -> None:
    from arnold_pipelines.megaplan.cloud import operator_control

    # The production target runner deliberately exports the managed queue root.
    # This unit test exercises marker-relative defaulting, so isolate it from
    # that ambient runner contract.
    monkeypatch.delenv("ARNOLD_REPAIR_QUEUE_ROOT", raising=False)
    spec, _ = _chain(tmp_path)
    marker = tmp_path / "markers" / "demo.json"
    marker.parent.mkdir()
    marker.write_text(json.dumps({"session": "demo", "relaunch_command": "safe command"}))
    calls = []

    class Completed:
        returncode = 0

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return Completed()

    monkeypatch.setattr(operator_control.subprocess, "run", fake_run)
    monkeypatch.setattr(operator_control, "_stop_tmux_session", lambda *args, **kwargs: True)
    monkeypatch.setattr(operator_control, "_stop_owned_pidfile", lambda *args, **kwargs: True)
    result = operator_control.pause_session(
        spec=spec,
        workspace=tmp_path,
        session="demo",
        marker_path=marker,
        reason="operator",
        actor="test",
    )
    assert calls == []
    assert result["runner_stopped"] is True
    assert result["repair_stopped"] is True
    assert json.loads(marker.read_text())["should_run"] is False

    calls.clear()

    def resume_run(argv, **kwargs):
        calls.append(argv)
        result = Completed()
        if argv[:3] == ["tmux", "has-session", "-t"]:
            has_calls = sum(1 for call in calls if call[:3] == ["tmux", "has-session", "-t"])
            result.returncode = 1 if has_calls == 1 else 0
        return result

    monkeypatch.setattr(operator_control.subprocess, "run", resume_run)
    resumed = operator_control.resume_session(
        spec=spec,
        workspace=tmp_path,
        session="demo",
        marker_path=marker,
        actor="test",
    )
    assert calls == [
        ["tmux", "has-session", "-t", "demo"],
        [
            "tmux",
            "new-session",
            "-d",
            "-s",
            "demo",
            "-c",
            str(tmp_path),
            "-e",
            f"ARNOLD_REPAIR_QUEUE_ROOT={tmp_path / 'repair-queue'}",
            "-e",
            f"ARNOLD_REPAIR_MARKER_DIR={tmp_path / 'markers'}",
            "-e",
            "ARNOLD_REPAIR_SESSION=demo",
            "-e",
            "ARNOLD_REPAIR_RUN_KIND=chain",
            "safe command",
        ],
        ["tmux", "has-session", "-t", "demo"],
        ["tmux", "has-session", "-t", "demo"],
    ]
    assert resumed["runner_started"] is True
    assert json.loads(marker.read_text())["should_run"] is True


def test_tmux_teardown_requires_exact_marker_binding_and_records_ack(tmp_path: Path, monkeypatch) -> None:
    from arnold_pipelines.megaplan.cloud import operator_control

    binding = {
        "tmux_socket": str(tmp_path / "tmux.sock"),
        "tmux_socket_fingerprint": "1:2",
        "tmux_server_pid": 41,
        "tmux_server_process_start_identity": "server-start",
        "tmux_session_id": "$1",
        "tmux_owned_pane_id": "%1",
        "tmux_owned_pane_pid": 42,
        "tmux_owned_pane_process_start_identity": "pane-start",
        "tmux_owned_pane_command": "arnold-supervisor",
        "tmux_all_panes_digest": "a" * 64,
    }
    marker = {"session": "demo", "workspace": str(tmp_path), **binding}
    marker_path = tmp_path / "demo.json"
    marker_path.write_text(json.dumps(marker))
    commands = []
    monkeypatch.setattr(operator_control, "tmux_authority_bindings", lambda _payload: binding)
    monkeypatch.setattr(
        operator_control.subprocess,
        "run",
        lambda argv, **_kwargs: commands.append(argv) or type("R", (), {"returncode": 0})(),
    )

    assert operator_control._stop_tmux_session(
        marker, session="demo", marker_path=marker_path, workspace=tmp_path
    )
    assert commands == [["tmux", "-S", str(tmp_path / "tmux.sock"), "kill-session", "-t", "=$1"]]
    events = (tmp_path / ".megaplan" / "incident-ledger" / "events.jsonl").read_text()
    assert '"event_type":"non_worker_signal_disposition"' in events
    assert '"event_type":"signal_claimed"' in events


def test_tmux_teardown_rejects_missing_or_replaced_binding(tmp_path: Path, monkeypatch) -> None:
    from arnold_pipelines.megaplan.cloud import operator_control

    calls = []
    monkeypatch.setattr(operator_control.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    assert not operator_control._stop_tmux_session(
        {"session": "demo", "workspace": str(tmp_path)},
        session="demo", marker_path=tmp_path / "demo.json", workspace=tmp_path,
    )
    assert calls == []


def test_cloud_pause_reconciles_dead_writer_flush_after_tmux_stop(
    tmp_path: Path, monkeypatch
) -> None:
    from arnold_pipelines.megaplan.cloud import operator_control

    spec, plan = _chain(tmp_path)
    marker = tmp_path / "markers" / "demo.json"
    marker.parent.mkdir()
    marker.write_text(json.dumps({"session": "demo", "relaunch_command": "safe"}))

    class Completed:
        returncode = 0

    def race_after_tmux_proof(*args, **kwargs):
        raced = json.loads((plan / "state.json").read_text())
        raced["current_state"] = "blocked"
        raced.get("meta", {}).pop("operator_pause", None)
        raced["active_step"] = {
            "phase": "execute",
            "worker_pid": 999999,
            "runner_lease": {"session": "demo"},
        }
        (plan / "state.json").write_text(json.dumps(raced))
        return True

    monkeypatch.setattr(operator_control.subprocess, "run", lambda *args, **kwargs: Completed())
    monkeypatch.setattr(operator_control, "_stop_tmux_session", race_after_tmux_proof)
    monkeypatch.setattr(operator_control.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        operator_control, "_stop_owned_pidfile", lambda *args, **kwargs: False
    )

    result = operator_control.pause_session(
        spec=spec,
        workspace=tmp_path,
        session="demo",
        marker_path=marker,
        reason="contain",
        actor="test",
    )

    paused_plan = json.loads((plan / "state.json").read_text())
    assert result["plan_reconciled"] is True
    assert paused_plan["current_state"] == "paused"
    assert "active_step" not in paused_plan
    assert paused_plan["meta"]["operator_pause"]["previous_current_state"] == "blocked"

    resumed = resume_chain(spec, tmp_path)
    assert resumed["restored_plan_state"] == "blocked"


def test_owned_pidfile_uses_workspace_ledger_and_locked_final_fence(
    tmp_path: Path, monkeypatch
) -> None:
    from arnold_pipelines.megaplan.cloud import operator_control

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    marker = workspace / "markers" / "demo.json"
    marker.parent.mkdir()
    marker.write_text(json.dumps({"session": "demo", "workspace": str(workspace)}))
    pidfile = workspace / "demo.repair-loop.pid"
    pidfile.write_text("41\n")
    snapshots = iter([
        (41, 401, "start-a", "python arnold-babysitter demo"),
        (41, 402, "start-a", "python arnold-babysitter demo"),
    ])
    def changing_snapshot(path, **kwargs):
        current = next(snapshots)
        if kwargs.get("expected_group") is not None and current[1] != kwargs["expected_group"]:
            raise operator_control.SignalDispositionError("process group changed")
        return current

    monkeypatch.setattr(operator_control, "_owned_pidfile_snapshot", changing_snapshot)
    roots = []
    monkeypatch.setattr(operator_control, "IncidentLedger", lambda root: roots.append(root) or object())
    signals = []

    def fake_signal(ledger, disposition, *, signal_fn, preflight):
        preflight([])
        signals.append(disposition)
        signal_fn()

    monkeypatch.setattr(operator_control, "signal_non_worker", fake_signal)
    monkeypatch.setattr(operator_control.os, "killpg", lambda group, sig: signals.append((group, sig)))

    assert operator_control._stop_owned_pidfile(
        pidfile, session="demo", workspace=workspace, marker_path=marker
    ) is False
    assert roots == [workspace]
    assert signals == []


def test_owned_pidfile_happy_path_signals_only_workspace_bound_runner(
    tmp_path: Path, monkeypatch
) -> None:
    from arnold_pipelines.megaplan.cloud import operator_control

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    marker = workspace / "markers" / "demo.json"
    marker.parent.mkdir()
    marker.write_text(json.dumps({"session": "demo", "workspace": str(workspace)}))
    pidfile = workspace / "demo.meta-repair.pid"
    pidfile.write_text("41\n")
    snapshot = (41, 401, "start-a", "python arnold-babysitter demo")
    monkeypatch.setattr(operator_control, "_owned_pidfile_snapshot", lambda *a, **k: snapshot)
    roots = []
    monkeypatch.setattr(operator_control, "IncidentLedger", lambda root: roots.append(root) or object())
    calls = []

    def fake_signal(ledger, disposition, *, signal_fn, preflight):
        preflight([])
        signal_fn()
        calls.append(disposition)

    monkeypatch.setattr(operator_control, "signal_non_worker", fake_signal)
    monkeypatch.setattr(operator_control.os, "killpg", lambda group, sig: calls.append((group, sig)))

    assert operator_control._stop_owned_pidfile(
        pidfile, session="demo", workspace=workspace, marker_path=marker
    ) is True
    assert roots == [workspace]
    assert calls


def test_quiesced_pause_reconciliation_rejects_live_or_foreign_runner(
    tmp_path: Path, monkeypatch
) -> None:
    from arnold_pipelines.megaplan.chain.operator_pause import (
        reconcile_quiesced_plan_pause,
    )

    spec, plan = _chain(tmp_path)
    paused = pause_chain(spec, tmp_path, reason="contain")
    raced = json.loads((plan / "state.json").read_text())
    raced["current_state"] = "blocked"
    raced.get("meta", {}).pop("operator_pause", None)
    raced["active_step"] = {
        "worker_pid": 999999,
        "runner_lease": {"session": "other"},
    }
    (plan / "state.json").write_text(json.dumps(raced))

    with pytest.raises(CliError, match="dead owned runner receipt"):
        reconcile_quiesced_plan_pause(
            spec,
            tmp_path,
            session="demo",
            authority=paused["authority"],
        )


@pytest.mark.parametrize("advanced_state", ["gated", "finalized", "executed", "reviewed", "done"])
def test_authority_only_hold_resumes_after_direct_phase_advances_plan(
    tmp_path: Path, monkeypatch, advanced_state: str
) -> None:
    from arnold_pipelines.megaplan.cloud import operator_control

    spec, plan = _chain(tmp_path)
    paused = pause_chain(spec, tmp_path, reason="run one direct phase")
    marker = tmp_path / "markers" / "demo.json"
    marker.parent.mkdir()
    marker.write_text(
        json.dumps(
            {
                "session": "demo",
                "workspace": str(tmp_path.resolve()),
                "remote_spec": str(spec.resolve()),
                "relaunch_command": "python -m demo",
                "operator_pause": paused["authority"],
                "should_run": False,
            }
        )
    )

    operator_control.resume_session(
        spec=spec,
        workspace=tmp_path,
        session="demo",
        marker_path=marker,
        actor="test",
        start_runner=False,
    )
    held = json.loads(marker.read_text())
    assert held["operator_resume_hold"]["active"] is True

    # Model a successful direct phase while the cloud runner remains held.
    plan_state = json.loads((plan / "state.json").read_text())
    plan_state["current_state"] = advanced_state
    (plan / "state.json").write_text(json.dumps(plan_state))

    calls: list[list[str]] = []

    class Completed:
        returncode = 0

    def run(argv, **kwargs):
        calls.append(list(argv))
        result = Completed()
        if argv[:3] == ["tmux", "has-session", "-t"]:
            result.returncode = 1 if len(calls) == 1 else 0
        return result

    monkeypatch.setattr(operator_control.subprocess, "run", run)
    resumed = operator_control.resume_session(
        spec=spec,
        workspace=tmp_path,
        session="demo",
        marker_path=marker,
        actor="test",
    )

    assert resumed["already_resumed"] is True
    assert resumed["current_plan_state"] == advanced_state
    assert json.loads((plan / "state.json").read_text())["current_state"] == advanced_state
    launched = json.loads(marker.read_text())
    assert launched["should_run"] is True
    assert "operator_resume_hold" not in launched
    assert sum(1 for call in calls if call[1] == "new-session") == 1


def test_marker_only_stop_without_resume_authority_fails_closed(
    tmp_path: Path, monkeypatch
) -> None:
    from arnold_pipelines.megaplan.cloud import operator_control

    spec, _ = _chain(tmp_path)
    marker = tmp_path / "markers" / "demo.json"
    marker.parent.mkdir()
    before = {
        "session": "demo",
        "workspace": str(tmp_path.resolve()),
        "remote_spec": str(spec.resolve()),
        "relaunch_command": "python -m demo",
        "should_run": False,
    }
    marker.write_text(json.dumps(before))

    class Completed:
        returncode = 1

    monkeypatch.setattr(operator_control.subprocess, "run", lambda *a, **k: Completed())
    with pytest.raises(CliError, match="authority-cleared hold"):
        operator_control.resume_session(
            spec=spec,
            workspace=tmp_path,
            session="demo",
            marker_path=marker,
            actor="test",
        )
    assert json.loads(marker.read_text()) == before
