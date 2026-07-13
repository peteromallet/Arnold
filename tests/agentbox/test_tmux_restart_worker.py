from __future__ import annotations

import subprocess

from agentbox.reset_notifications import (
    list_reset_notifications,
    prepare_reset_notification,
)
from agentbox.tmux_restart_worker import complete_tmux_restart


def test_detached_worker_finalizes_success_after_replacement_health(
    monkeypatch, tmp_path
) -> None:
    reservation = prepare_reset_notification(notification_root=tmp_path)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        "agentbox.tmux_restart_worker._wait_for_tmux_resident",
        lambda pane_id, *, old_pane_pid: {
            "ok": True,
            "pane_id": pane_id,
            "old_pane_pid": old_pane_pid,
            "pane_pid": 2000001,
            "resident_pid": 2000002,
        },
    )

    result = complete_tmux_restart(
        pane_id="%39",
        old_pane_pid=1989952,
        reservation=reservation,
        service_name="agentbox-discord-resident",
        unit="agentbox-discord-resident.service",
        grace_seconds=0,
    )

    assert result["ok"] is True
    state = list_reset_notifications(notification_root=tmp_path)
    assert state["delivery_status_counts"] == {"pending": 1}
    assert state["records"][0]["restart"]["status"] == "succeeded"


def test_detached_worker_finalizes_failed_respawn(monkeypatch, tmp_path) -> None:
    reservation = prepare_reset_notification(notification_root=tmp_path)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(
            argv, 1, stdout="", stderr="tmux refused"
        ),
    )

    result = complete_tmux_restart(
        pane_id="%39",
        old_pane_pid=1989952,
        reservation=reservation,
        service_name="agentbox-discord-resident",
        unit="agentbox-discord-resident.service",
        grace_seconds=0,
    )

    assert result["ok"] is False
    state = list_reset_notifications(notification_root=tmp_path)
    assert state["delivery_status_counts"] == {"restart_failed": 1}
    assert state["records"][0]["restart"]["status"] == "failed"
