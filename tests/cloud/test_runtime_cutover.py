from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import runtime_cutover
from arnold_pipelines.megaplan.cloud.runtime_cutover import (
    marker_runtime_identity,
    normalize_runtime_identity,
    update_marker_runtime,
)
from arnold_pipelines.megaplan.types import CliError


def _write_marker(path: Path) -> dict:
    marker = {
        "session": "custody",
        "workspace": "/workspace/project",
        "remote_spec": "/workspace/project/chain.yaml",
        "editable_source_head": "a" * 40,
        "editable_source_branch": "legacy",
        "editable_install_sync": {
            "status": "private-venv-editable",
            "source": "/workspace/runtime-a",
        },
        "engine_ref_check": {"status": "stale"},
        "launch_command": "old launch",
        "relaunch_command": "old relaunch",
    }
    path.write_text(json.dumps(marker, sort_keys=True) + "\n", encoding="utf-8")
    return marker


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runtime_b() -> dict:
    return normalize_runtime_identity(
        {
            "import_root": "/workspace/runtime-b",
            "source_revision": "b" * 40,
            "editable_root": "/workspace/runtime-b",
            "editable_revision": "b" * 40,
            "direct_url": {
                "dir_info": {"editable": True},
                "url": "file:///workspace/runtime-b",
            },
            "pth": [
                {
                    "path": "/venv/site-packages/_editable_impl_arnold.pth",
                    "entries": ["/workspace/runtime-b"],
                    "readable": True,
                }
            ],
            "imports": {
                "arnold": "/workspace/runtime-b/arnold/__init__.py",
                "arnold_pipelines": "/workspace/runtime-b/arnold_pipelines/__init__.py",
                "megaplan": "/workspace/runtime-b/arnold_pipelines/megaplan/__init__.py",
            },
        }
    )


def test_marker_runtime_update_is_cas_guarded_and_clears_obsolete_fields(
    tmp_path: Path,
) -> None:
    marker_path = tmp_path / "custody.json"
    marker = _write_marker(marker_path)
    previous = marker_runtime_identity(marker)
    assert previous is not None

    result = update_marker_runtime(
        marker_path,
        expected_marker_sha256=_sha(marker_path),
        expected_previous_runtime_sha256=previous["content_sha256"],
        active_runtime_identity=_runtime_b(),
        relaunch_command="exec /workspace/runtime-b/bin/chain",
        source_branch="archive/runtime-b",
        reason="verified runtime cutover",
    )

    updated = json.loads(marker_path.read_text())
    assert updated["editable_source_head"] == "b" * 40
    assert updated["runtime_binding"]["current_identity"]["content_sha256"] == _runtime_b()[
        "content_sha256"
    ]
    assert updated["runtime_binding"]["rebind_events"][0]["direction"] == "cutover"
    assert "engine_ref_check" not in updated
    assert "launch_command" not in updated
    assert result["marker_after_sha256"] == _sha(marker_path)

    with pytest.raises(CliError, match="marker changed"):
        update_marker_runtime(
            marker_path,
            expected_marker_sha256=result["marker_before_sha256"],
            expected_previous_runtime_sha256=previous["content_sha256"],
            active_runtime_identity=_runtime_b(),
            relaunch_command="unused",
            reason="stale writer",
        )


def test_marker_runtime_update_failure_before_replace_leaves_original(
    tmp_path: Path,
    monkeypatch,
) -> None:
    marker_path = tmp_path / "custody.json"
    marker = _write_marker(marker_path)
    before = marker_path.read_bytes()
    previous = marker_runtime_identity(marker)
    assert previous is not None
    monkeypatch.setattr(
        runtime_cutover.os,
        "replace",
        lambda *_args: (_ for _ in ()).throw(OSError("injected replace failure")),
    )

    with pytest.raises(OSError, match="injected"):
        update_marker_runtime(
            marker_path,
            expected_marker_sha256=_sha(marker_path),
            expected_previous_runtime_sha256=previous["content_sha256"],
            active_runtime_identity=_runtime_b(),
            relaunch_command="exec runtime b",
            reason="failure injection",
        )

    assert marker_path.read_bytes() == before
    assert [
        path.name for path in tmp_path.glob("custody.json.*")
    ] == ["custody.json.runtime-cutover.lock"]
