from __future__ import annotations

from pathlib import Path
from queue import Queue
from threading import Event, Thread
import time

import pytest

from agentbox.config import AgentBoxConfig
from agentbox.locks import (
    AgentBoxLockError,
    AgentBoxLockTimeout,
    acquire_repo_lock,
    repo_lock_path,
)


def test_same_repo_lock_serializes_acquisition(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    acquired = Event()
    release = Event()
    results: Queue[str] = Queue()

    def contender() -> None:
        acquired.set()
        with acquire_repo_lock(config, "app", timeout_seconds=2):
            results.put("acquired")
            release.wait(timeout=2)

    with acquire_repo_lock(config, "app"):
        thread = Thread(target=contender)
        thread.start()
        assert acquired.wait(timeout=1)
        time.sleep(0.1)
        assert results.empty()

    assert results.get(timeout=1) == "acquired"
    release.set()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert not repo_lock_path(config, "app").exists()


def test_same_repo_lock_reports_timeout(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")

    with acquire_repo_lock(config, "app"):
        with pytest.raises(AgentBoxLockTimeout, match="app"):
            with acquire_repo_lock(config, "app", timeout_seconds=0.01):
                pass


def test_different_repo_locks_are_independent(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")

    with acquire_repo_lock(config, "app"):
        with acquire_repo_lock(config, "infra", timeout_seconds=0.01) as lock:
            assert lock.repo_name == "infra"


def test_repo_lock_rejects_path_like_names(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")

    with pytest.raises(AgentBoxLockError):
        repo_lock_path(config, "../app")
