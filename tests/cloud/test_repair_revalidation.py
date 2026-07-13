from arnold_pipelines.megaplan.cloud.repair_revalidation import revalidate_repair_target


def _target(*, state="critiqued", cursor=10, pid="101", pid_live=True, tmux=True):
    return {
        "target_id": "session:plan",
        "plan_state": {"current_state": state, "fingerprint": f"plan-{state}"},
        "chain_state": {
            "current_plan_name": "plan",
            "last_state": state,
            "fingerprint": f"chain-{state}",
        },
        "event_cursors": {"line_count": cursor, "mtime": float(cursor)},
        "active_step_heartbeat": {
            "active": pid_live,
            "phase": "finalize",
            "attempt": 1,
            "worker_pid": pid,
            "pid_live": pid_live,
        },
        "tmux_process": {"session_live": tmux, "live_status": "alive" if tmux else "stopped"},
    }


def test_stale_pre_gate_evidence_is_superseded_by_current_finalize_target() -> None:
    result = revalidate_repair_target(
        _target(state="critiqued", cursor=10, pid="100"),
        _target(state="gated", cursor=20, pid="200"),
        session_health="alive",
    )
    assert result.superseded is True
    assert "plan_state.current_state" in result.changed_fields
    assert "event_cursors.line_count" in result.changed_fields
    assert result.recovery_verified is True


def test_dead_finalize_worker_is_not_recovered_by_live_tmux_or_stale_activity() -> None:
    before = _target(state="gated", cursor=20, pid="200", pid_live=False)
    result = revalidate_repair_target(before, before, session_health="alive")
    assert result.runner_live is True
    assert result.active_worker_live is False
    assert result.progress_observed is False
    assert result.recovery_verified is False
    assert "active worker is dead" in result.reason


def test_unrelated_process_cannot_supply_recovery_liveness() -> None:
    before = _target(state="gated", cursor=20, pid="200", pid_live=False, tmux=False)
    after = dict(before)
    after["unrelated_processes"] = [{"pid": 999, "cmdline": "pytest tests/cloud"}]
    result = revalidate_repair_target(before, after, session_health="stopped")
    assert result.runner_live is False
    assert result.recovery_verified is False
