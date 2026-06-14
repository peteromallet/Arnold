from __future__ import annotations

import json
from pathlib import Path

import fcntl
import pytest

from arnold.pipelines.megaplan.types import CliError
from arnold.pipelines.megaplan.workers.turn_cap import (
    DEFAULT_TURN_CAP,
    HOST_TURN_CAP_SOURCE,
    acquire_turn_slot,
)


def _metadata(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_default_cap_is_three() -> None:
    assert DEFAULT_TURN_CAP == 3


def test_admits_exactly_configured_live_slots_and_refuses_next(tmp_path: Path) -> None:
    lock_dir = tmp_path / "turn-cap"
    with (
        acquire_turn_slot(
            engine="claude",
            channel="stream",
            step="plan",
            plan=tmp_path,
            cap=2,
            lock_dir=lock_dir,
        ),
        acquire_turn_slot(
            engine="codex",
            channel="cli",
            step="execute",
            plan=tmp_path,
            cap=2,
            lock_dir=lock_dir,
        ),
    ):
        with pytest.raises(CliError) as exc_info:
            with acquire_turn_slot(
                engine="shannon",
                channel="api",
                step="critique",
                plan=tmp_path,
                cap=2,
                lock_dir=lock_dir,
            ):
                pass

    error = exc_info.value
    assert error.code == "rate_limit"
    assert error.extra["source"] == HOST_TURN_CAP_SOURCE
    assert error.extra["retryable"] is True
    assert error.extra["cap"] == 2
    assert len(error.extra["active_slots"]) == 2


def test_nonblocking_fcntl_refuses_locked_slot_without_waiting(tmp_path: Path) -> None:
    lock_dir = tmp_path / "turn-cap"
    lock_dir.mkdir()
    slot_path = lock_dir / "slot-0.json"
    with slot_path.open("a+", encoding="utf-8") as locked:
        fcntl.flock(locked.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(CliError) as exc_info:
            with acquire_turn_slot(engine="claude", cap=1, lock_dir=lock_dir):
                pass
        assert exc_info.value.code == "rate_limit"
        assert exc_info.value.extra["source"] == HOST_TURN_CAP_SOURCE
        fcntl.flock(locked.fileno(), fcntl.LOCK_UN)


def test_disable_cap_with_zero_env_does_not_create_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEGAPLAN_WORKER_TURN_CAP", "0")
    lock_dir = tmp_path / "turn-cap"
    with acquire_turn_slot(engine="claude", lock_dir=lock_dir) as slot:
        assert slot.enabled is False
        assert slot.index is None
        assert slot.path is None
    assert not lock_dir.exists()


def test_reclaims_stale_dead_pid_slot_and_rewrites_metadata(tmp_path: Path) -> None:
    lock_dir = tmp_path / "turn-cap"
    lock_dir.mkdir()
    slot_path = lock_dir / "slot-0.json"
    slot_path.write_text(
        json.dumps(
            {
                "pid": 999_999_999,
                "engine": "claude",
                "channel": "stream",
                "step": "old",
                "plan": "old-plan",
                "acquired": 1.0,
            }
        ),
        encoding="utf-8",
    )

    with acquire_turn_slot(
        engine="codex",
        channel="cli",
        step="execute",
        plan=tmp_path,
        cap=1,
        lock_dir=lock_dir,
    ) as slot:
        assert slot.index == 0
        metadata = _metadata(slot_path)
        assert metadata["engine"] == "codex"
        assert metadata["channel"] == "cli"
        assert metadata["step"] == "execute"
        assert metadata["plan"] == str(tmp_path)
        assert isinstance(metadata["pid"], int)
        assert isinstance(metadata["acquired"], float)


def test_release_on_exception_allows_later_acquire(tmp_path: Path) -> None:
    lock_dir = tmp_path / "turn-cap"
    with pytest.raises(RuntimeError):
        with acquire_turn_slot(engine="claude", cap=1, lock_dir=lock_dir):
            raise RuntimeError("boom")

    with acquire_turn_slot(engine="claude", cap=1, lock_dir=lock_dir) as slot:
        assert slot.index == 0
