from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import auto_improve.cron as cron


def _status(
    key: str,
    status: str,
    *,
    detail: str = "detail",
    reset_at: str | None = None,
) -> cron.KeyStatus:
    return cron.KeyStatus(
        key=key,
        provider="zhipu",
        status=status,
        detail=detail,
        reset_at=reset_at,
        masked_key=f"{key[:8]}...{key[-4:]}",
    )


def test_restart_dead_kills_old_loop_pid_before_relaunch(monkeypatch) -> None:
    events: list[str] = []
    alive_checks = {"count": 0}

    monkeypatch.setattr(cron, "_read_iteration_pidfile", lambda: {"loop_pid": 1234})
    monkeypatch.setattr(cron, "_expected_workers", lambda: 4)

    def fake_pid_alive(pid: int) -> bool:
        alive_checks["count"] += 1
        return alive_checks["count"] == 1

    monkeypatch.setattr(cron, "_pid_alive", fake_pid_alive)
    monkeypatch.setattr(cron.time, "sleep", lambda _: None)
    monkeypatch.setattr(cron.os, "kill", lambda pid, sig: events.append(f"kill:{pid}:{sig}"))
    monkeypatch.setattr(
        cron.subprocess,
        "Popen",
        lambda *args, **kwargs: events.append("popen"),
    )

    issues = cron.restart_dead({"workers": 0, "scorers": 1, "dashboard": 1}, fix=True)

    assert any("killed orphan parent PID 1234" in issue for issue in issues)
    assert events[0] == f"kill:1234:{cron.signal.SIGTERM}"
    assert events[1] == "popen"


def test_run_key_probe_cached_uses_cache_when_fresh(monkeypatch) -> None:
    cached = _status("alive-key-1234", "alive")
    now_iso = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(
        cron,
        "_load_state",
        lambda: {"key_probe": {"timestamp": now_iso, "results": [asdict(cached)]}},
    )
    monkeypatch.setattr(
        cron,
        "probe_all_keys",
        lambda: (_ for _ in ()).throw(AssertionError("probe_all_keys should not be called")),
    )

    results = cron.run_key_probe_cached()

    assert results == [cached]


def test_run_key_probe_cached_refreshes_when_stale(monkeypatch) -> None:
    stale_iso = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    refreshed = _status("alive-key-5678", "alive")
    saved: dict = {}

    monkeypatch.setattr(
        cron,
        "_load_state",
        lambda: {"key_probe": {"timestamp": stale_iso, "results": []}},
    )
    monkeypatch.setattr(cron, "probe_all_keys", lambda: [refreshed])
    monkeypatch.setattr(cron, "_save_state", lambda state: saved.update(state))

    results = cron.run_key_probe_cached()

    assert results == [refreshed]
    assert saved["key_probe"]["results"] == [asdict(refreshed)]
    assert datetime.fromisoformat(saved["key_probe"]["timestamp"]) > datetime.fromisoformat(stale_iso)


def test_run_key_probe_cached_returns_empty_on_probe_failure(monkeypatch) -> None:
    stale_iso = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    save_calls = {"count": 0}

    monkeypatch.setattr(
        cron,
        "_load_state",
        lambda: {"key_probe": {"timestamp": stale_iso, "results": []}},
    )
    monkeypatch.setattr(
        cron,
        "probe_all_keys",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(cron, "_save_state", lambda state: save_calls.__setitem__("count", save_calls["count"] + 1))

    results = cron.run_key_probe_cached()

    assert results == []
    assert save_calls["count"] == 0


def test_check_key_capacity_over_provisioned(monkeypatch) -> None:
    monkeypatch.setattr(cron, "_expected_workers", lambda: 4)

    issues = cron.check_key_capacity(
        {"workers": 3},
        [_status("alive-key-1", "alive"), _status("dead-key-1", "invalid")],
    )

    assert issues == [
        "Over-provisioned: 3 workers running but only 1 alive keys. Consider killing 2 workers or waiting for recovery."
    ]


def test_check_key_capacity_under_provisioned(monkeypatch) -> None:
    monkeypatch.setattr(cron, "_expected_workers", lambda: 4)

    issues = cron.check_key_capacity(
        {"workers": 1},
        [_status("alive-key-1", "alive"), _status("alive-key-2", "alive"), _status("alive-key-3", "alive")],
    )

    assert issues == ["Under-provisioned: 3 alive keys but only 1 workers running. Could scale up."]


def test_check_key_capacity_balanced(monkeypatch) -> None:
    monkeypatch.setattr(cron, "_expected_workers", lambda: 4)

    issues = cron.check_key_capacity(
        {"workers": 2},
        [_status("alive-key-1", "alive"), _status("alive-key-2", "alive")],
    )

    assert issues == []


def test_check_key_capacity_empty_probe_silent(monkeypatch) -> None:
    monkeypatch.setattr(cron, "_expected_workers", lambda: 4)

    assert cron.check_key_capacity({"workers": 2}, []) == []


def test_main_calls_run_key_probe_cached_once(monkeypatch, tmp_path, capsys) -> None:
    probe_calls = {"count": 0}
    saved: dict = {}
    key_probe = [_status("alive-key-main", "alive")]

    monkeypatch.setattr(cron, "MANIFEST_PATH", tmp_path / "_task_manifest.json")
    monkeypatch.setattr(cron, "PREDS_DIR", tmp_path / "_preds")
    monkeypatch.setattr(cron.sys, "argv", ["cron.py"])
    monkeypatch.setattr(cron, "_load_state", lambda: {"key_probe": {"timestamp": "cached", "results": ["cached"]}})
    monkeypatch.setattr(cron, "_save_state", lambda state: saved.update(state))
    monkeypatch.setattr(cron, "check_scores", lambda: {"passed": 0, "failed": 0, "scored": 0, "preds": 0, "unscored": 0})
    monkeypatch.setattr(cron, "check_processes", lambda: {"workers": 1, "scorers": 1, "dashboard": 1})
    monkeypatch.setattr(cron, "restart_dead", lambda procs, fix: [])
    monkeypatch.setattr(cron, "check_key_capacity", lambda procs, key_probe: [])
    monkeypatch.setattr(cron, "check_scorer_stuck", lambda scores, fix: None)
    monkeypatch.setattr(cron, "check_worker_quota", lambda fix: [])
    monkeypatch.setattr(cron, "check_review_bug", lambda: [])
    monkeypatch.setattr(cron, "check_worker_staleness", lambda: [])
    monkeypatch.setattr(cron, "check_limbo", lambda fix, prev_state: [])
    monkeypatch.setattr(cron, "check_false_negatives", lambda: [])
    monkeypatch.setattr(cron, "check_unreviewed_infra_failures", lambda: [])
    monkeypatch.setattr(cron, "_detect_stall", lambda scores, prev_state: None)
    monkeypatch.setattr(cron, "_compute_deltas", lambda scores, prev_state: [])

    def fake_run_key_probe_cached() -> list[cron.KeyStatus]:
        probe_calls["count"] += 1
        return key_probe

    monkeypatch.setattr(cron, "run_key_probe_cached", fake_run_key_probe_cached)

    cron.main()
    capsys.readouterr()

    assert probe_calls["count"] == 1
    assert saved["key_probe"] == {"timestamp": "cached", "results": ["cached"]}
