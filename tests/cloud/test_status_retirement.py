from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import status_snapshot
from arnold_pipelines.megaplan.cloud.cli import _register_cloud_subcommands
from arnold_pipelines.megaplan.cloud.status_retirement import (
    StatusRetirementBlocked,
    retire_deleted_workspace_status,
)


def _write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> dict[str, Path | str]:
    marker_dir = tmp_path / "registry"
    workspace = tmp_path / "deleted-workspace" / "Arnold"
    remote_spec = workspace / ".megaplan" / "initiatives" / "workflow-boundary-contracts" / "chain.yaml"
    marker = _write_json(
        marker_dir / "stale-wbc.json",
        {
            "session": "stale-wbc",
            "run_kind": "chain",
            "chain_slug": "workflow-boundary-contracts",
            "workspace": str(workspace),
            "remote_spec": str(remote_spec),
            "current_plan": "unfinished-plan",
            "progress": {"percent": 75},
        },
    )
    sidecar = _write_json(
        marker_dir / "stale-wbc.chain-health.progress.json",
        {"status": "blocked", "completed_count": 3, "milestone_count": 4},
    )
    repair = _write_json(
        marker_dir / "repair-data" / "stale-wbc.repair-data.json",
        {"status": "partial_liveness", "evidence": ["unfinished"]},
    )
    return {
        "marker_dir": marker_dir,
        "workspace": workspace,
        "remote_spec": remote_spec,
        "marker": marker,
        "marker_sha": _sha(marker),
        "sidecar": sidecar,
        "sidecar_sha": _sha(sidecar),
        "repair": repair,
    }


def _retire(fx: dict[str, Path | str], **overrides: object) -> dict[str, object]:
    values = {
        "marker_dir": fx["marker_dir"],
        "session": "stale-wbc",
        "expected_marker_sha256": fx["marker_sha"],
        "reason": "deleted workspace marker is a stale status projection only",
        "actor": "test-operator",
        "tmux_probe": lambda _session: False,
        "process_probe": lambda _session, _workspace, _spec: [],
        "now": datetime(2026, 7, 14, 18, 30, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return retire_deleted_workspace_status(**values)  # type: ignore[arg-type]


def test_deleted_workspace_status_retirement_archives_projection_and_preserves_evidence(
    tmp_path: Path,
) -> None:
    fx = _fixture(tmp_path)
    before = status_snapshot.build_cloud_status_snapshot(
        marker_dir=fx["marker_dir"],  # type: ignore[arg-type]
        watchdog_report_path=tmp_path / "absent-watchdog.json",
        liveness_probe=lambda _marker: {"process": False, "tmux": False},
    )
    assert [row["session"] for row in before["sessions"]] == ["stale-wbc"]

    result = _retire(fx)

    assert result["status"] == "retired"
    assert result["retirement_kind"] == "deleted-workspace-status-only"
    assert result["postcondition"]["target_present"] is False  # type: ignore[index]
    assert result["preservation"]["completion_asserted"] is False  # type: ignore[index]
    assert result["preservation"]["unfinished_work_landed_asserted"] is False  # type: ignore[index]
    record_path = Path(str(result["record_path"]))
    artifacts = record_path.parent / "artifacts"
    assert not fx["marker"].exists()  # type: ignore[union-attr]
    assert not fx["sidecar"].exists()  # type: ignore[union-attr]
    assert _sha(artifacts / "stale-wbc.json") == fx["marker_sha"]
    assert _sha(artifacts / "stale-wbc.chain-health.progress.json") == fx["sidecar_sha"]
    assert fx["repair"].is_file()  # type: ignore[union-attr]

    after = status_snapshot.build_cloud_status_snapshot(
        marker_dir=fx["marker_dir"],  # type: ignore[arg-type]
        watchdog_report_path=tmp_path / "absent-watchdog.json",
        liveness_probe=lambda _marker: {"process": False, "tmux": False},
    )
    assert after["sessions"] == []

    repeated = _retire(fx)
    assert repeated["already_retired"] is True
    assert repeated["fresh_target_present"] is False

    # A new changed marker is not covered by the old identity fence and reappears.
    marker_payload = json.loads((artifacts / "stale-wbc.json").read_text(encoding="utf-8"))
    marker_payload["updated_at"] = "2026-07-14T18:31:00Z"
    _write_json(fx["marker"], marker_payload)  # type: ignore[arg-type]
    changed = status_snapshot.build_cloud_status_snapshot(
        marker_dir=fx["marker_dir"],  # type: ignore[arg-type]
        watchdog_report_path=tmp_path / "absent-watchdog.json",
        liveness_probe=lambda _marker: {"process": False, "tmux": False},
    )
    assert [row["session"] for row in changed["sessions"]] == ["stale-wbc"]


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"expected_marker_sha256": "0" * 64}, "marker_changed"),
        ({"tmux_probe": lambda _session: True}, "active_runner"),
        (
            {"process_probe": lambda _session, _workspace, _spec: [{"pid": 42}]},
            "active_process",
        ),
    ],
)
def test_status_retirement_fails_closed_without_tombstone(
    tmp_path: Path, overrides: dict[str, object], code: str
) -> None:
    fx = _fixture(tmp_path)

    with pytest.raises(StatusRetirementBlocked) as caught:
        _retire(fx, **overrides)

    assert caught.value.code == code
    assert not (fx["marker_dir"] / "retired-status").exists()  # type: ignore[operator]
    assert fx["marker"].is_file()  # type: ignore[union-attr]


def test_status_retirement_rejects_present_workspace(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    fx["workspace"].mkdir(parents=True)  # type: ignore[union-attr]

    with pytest.raises(StatusRetirementBlocked) as caught:
        _retire(fx)

    assert caught.value.code == "workspace_present"
    assert not (fx["marker_dir"] / "retired-status").exists()  # type: ignore[operator]


def test_cloud_cli_registers_deleted_workspace_status_retirement_fences() -> None:
    parser = argparse.ArgumentParser()
    _register_cloud_subcommands(parser)

    args = parser.parse_args(
        [
            "retire-stale-status",
            "--session",
            "stale-wbc",
            "--expect-marker-sha256",
            "a" * 64,
            "--reason",
            "stale status projection",
            "--on-box",
        ]
    )

    assert args.cloud_action == "retire-stale-status"
    assert args.session == "stale-wbc"
    assert args.on_box is True
