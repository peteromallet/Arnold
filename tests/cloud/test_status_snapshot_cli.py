"""CLI integration tests: ``cloud status --all`` reads the canonical snapshot.

Covers the plan's contract that inside the trusted container the command builds
the snapshot locally with no SSH, and from a laptop it fetches the same snapshot
from the box rather than reconstructing status via a different algorithm.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import cli as cli_module
from arnold_pipelines.megaplan.cloud import status_snapshot


class _RecordingProvider:
    """Records every SSH-touching call so tests can assert none happened."""

    def __init__(self, *, remote_snapshot: dict | None = None, fail_read: bool = False) -> None:
        self._remote_snapshot = remote_snapshot
        self._fail_read = fail_read
        self.read_remote_file_calls: list[str] = []
        self.ssh_exec_calls: list[str] = []

    def read_remote_file(self, path: str) -> str:
        self.read_remote_file_calls.append(path)
        if self._fail_read:
            raise OSError("boom")
        return json.dumps(self._remote_snapshot or {})

    def ssh_exec(self, command: str):
        self.ssh_exec_calls.append(command)
        raise AssertionError("ssh_exec should not be called in the snapshot path")


def _args() -> argparse.Namespace:
    return argparse.Namespace(all=True, compact=False, since=None)


def test_status_all_in_container_builds_locally_without_ssh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    marker_dir = tmp_path / "cloud-sessions"
    marker_dir.mkdir()
    ws = tmp_path / "demo"
    ws.mkdir()
    (marker_dir / "demo.json").write_text(
        json.dumps(
            {
                "session": "demo",
                "workspace": str(ws),
                "remote_spec": "/spec/demo",
                "started_at": "2026-07-04T20:00:00Z",
                "run_kind": "chain",
            }
        ),
        encoding="utf-8",
    )
    (marker_dir / "demo.chain-health.progress.json").write_text(
        json.dumps(
            {
                "chain_complete": False,
                "completed_count": 1,
                "milestone_count": 4,
                "current_plan_name": "m1",
                "last_state": "executed",
                # Recent relative to the build's real ``now`` so the session
                # classifies as running rather than stale attention.
                "updated_at": (datetime.now(timezone.utc) - timedelta(seconds=30))
                .isoformat()
                .replace("+00:00", "Z"),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", "1")
    monkeypatch.setattr(status_snapshot, "DEFAULT_MARKER_DIR", marker_dir)
    monkeypatch.setattr(
        status_snapshot, "DEFAULT_SNAPSHOT_PATH", tmp_path / "absent-cloud-status.json"
    )
    provider = _RecordingProvider()

    rc = cli_module._run_status_all(spec=None, provider=provider, args=_args())

    assert rc == 0
    # The whole point: no SSH read or exec from inside the container.
    assert provider.read_remote_file_calls == []
    assert provider.ssh_exec_calls == []
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["source"] == "cloud-local-observer"
    assert payload["summary"]["running"] == 1
    sessions = {s["session"]: s for s in payload["sessions"]}
    assert sessions["demo"]["status"] == "running"


def test_status_all_laptop_fetches_snapshot_from_box(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    # No MEGAPLAN_TRUSTED_CONTAINER → laptop path.
    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)
    remote_snapshot = {
        "generated_at": "2026-07-04T22:13:15Z",
        "source": "cloud-local-observer",
        "summary": {"running": 2, "blocked": 0, "repairing": 0, "complete": 1, "attention": 0},
        "sessions": [],
    }
    provider = _RecordingProvider(remote_snapshot=remote_snapshot)

    rc = cli_module._run_status_all(spec=None, provider=provider, args=_args())

    assert rc == 0
    assert provider.read_remote_file_calls == [str(status_snapshot.DEFAULT_SNAPSHOT_PATH)]
    assert provider.ssh_exec_calls == []
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["running"] == 2
    assert payload["generated_at"] == "2026-07-04T22:13:15Z"


def test_status_all_laptop_falls_back_when_box_lacks_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)
    provider = _RecordingProvider(fail_read=True)

    # Force the legacy fallback (_run_cloud_chains) to succeed so we observe the
    # fallback actually engaging rather than erroring on a missing remote script.
    legacy_payload = {"sessions": [], "should_be_running_count": 0}
    monkeypatch.setattr(
        cli_module,
        "_run_cloud_chains",
        lambda spec, provider, args=None: (_ for _ in ()).throw(
            AssertionError("fallback invoked with kwargs")
        )
        if args is None
        else 0,
    )

    rc = cli_module._run_status_all(spec=None, provider=provider, args=_args())
    assert rc == 0
    assert provider.read_remote_file_calls == [str(status_snapshot.DEFAULT_SNAPSHOT_PATH)]
