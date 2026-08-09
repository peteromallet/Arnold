from __future__ import annotations

import hashlib
import json
import subprocess
import argparse
from datetime import datetime, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.chain.spec import _state_path_candidates_for
from arnold_pipelines.megaplan.cloud.session_retirement import (
    RetirementBlocked,
    retire_session,
)
from arnold_pipelines.megaplan.cloud.cli import _register_cloud_subcommands


def _write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _make_git_repo(path: Path) -> tuple[Path, str]:
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "tests@example.com")
    _git(path, "config", "user.name", "Tests")
    (path / "proof.txt").write_text("landed\n", encoding="utf-8")
    _git(path, "add", "proof.txt")
    _git(path, "commit", "-qm", "landed")
    commit = _git(path, "rev-parse", "HEAD")
    _git(path, "update-ref", "refs/remotes/origin/main", commit)
    return path, commit


def _make_chain(workspace: Path, *, slug: str, state: dict[str, object]) -> tuple[Path, Path]:
    spec = workspace / ".megaplan" / "initiatives" / slug / "chain.yaml"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("schema_version: 1\nname: demo\nmilestones: []\n", encoding="utf-8")
    state_path = _state_path_candidates_for(spec)[0]
    _write_json(state_path, state)
    return spec, state_path


def _fixture(tmp_path: Path) -> dict[str, object]:
    marker_dir = tmp_path / "registry"
    target_workspace = tmp_path / "target"
    canonical_workspace = tmp_path / "canonical"
    target_plan = "target-plan"
    target_spec, target_state = _make_chain(
        target_workspace,
        slug="demo",
        state={
            "current_milestone_index": 0,
            "current_plan_name": target_plan,
            "last_state": "paused",
            "completed": [],
        },
    )
    _write_json(
        target_workspace / ".megaplan" / "plans" / target_plan / "state.json",
        {"name": target_plan, "current_state": "paused"},
    )
    canonical_spec, canonical_state = _make_chain(
        canonical_workspace,
        slug="demo",
        state={
            "current_milestone_index": 1,
            "current_plan_name": None,
            "last_state": "done",
            "completed": [{"label": "m1", "plan": "canonical-plan", "status": "done"}],
        },
    )
    target_marker = _write_json(
        marker_dir / "target.json",
        {
            "session": "target",
            "run_kind": "chain",
            "chain_slug": "demo",
            "workspace": str(target_workspace),
            "remote_spec": str(target_spec),
            "should_run": False,
            "operator_pause": {
                "active": True,
                "paused_at": "2026-07-13T20:00:00Z",
                "reason": "duplicate",
            },
        },
    )
    canonical_marker = _write_json(
        marker_dir / "canonical.json",
        {
            "session": "canonical",
            "run_kind": "chain",
            "chain_slug": "demo",
            "workspace": str(canonical_workspace),
            "remote_spec": str(canonical_spec),
            "should_run": False,
        },
    )
    sidecar = _write_json(marker_dir / "target.chain-health.progress.json", {"status": "paused"})
    manifest = _write_json(
        tmp_path / "evidence" / "completion-manifest.json",
        {
            "schema": "arnold.megaplan.chain_completion_manifest.v1",
            "milestones": [{"label": "m1", "plan": "canonical-plan", "status": "done"}],
        },
    )
    git_repo, commit = _make_git_repo(tmp_path / "git-evidence")
    return {
        "marker_dir": marker_dir,
        "target_workspace": target_workspace,
        "canonical_workspace": canonical_workspace,
        "target_spec": target_spec,
        "canonical_spec": canonical_spec,
        "target_state": target_state,
        "canonical_state": canonical_state,
        "target_marker": target_marker,
        "target_marker_sha": _sha(target_marker),
        "canonical_marker": canonical_marker,
        "canonical_marker_sha": _sha(canonical_marker),
        "sidecar": sidecar,
        "manifest": manifest,
        "git_repo": git_repo,
        "commit": commit,
    }


def _retire(fx: dict[str, object], **overrides: object) -> dict[str, object]:
    values = {
        "marker_dir": fx["marker_dir"],
        "session": "target",
        "expected_marker_sha256": fx["target_marker_sha"],
        "superseded_by": "canonical",
        "expected_superseding_marker_sha256": fx["canonical_marker_sha"],
        "completion_manifest": fx["manifest"],
        "completion_manifest_sha256": _sha(fx["manifest"]),
        "git_repo": fx["git_repo"],
        "base_ref": "origin/main",
        "landed_commits": [fx["commit"]],
        "reason": "redundant completed work",
        "actor": "test-operator",
        "tmux_probe": lambda _session: False,
        "process_probe": lambda _session, _workspace, _spec: [],
        "now": datetime(2026, 7, 13, 20, 30, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return retire_session(**values)  # type: ignore[arg-type]


def test_retirement_archives_only_target_control_plane_artifacts(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)

    result = _retire(fx)

    assert result["status"] == "retired"
    assert result["retirement_id"].startswith("ret-")
    assert result["postcondition"] == {
        "observed_at": "2026-07-13T20:30:00Z",
        "fresh_snapshot_source": "cloud-local-observer",
        "target_present": False,
        "target_actionable_paused": False,
        "target_marker_present": False,
        "superseding_marker_present": True,
        "status_cache_refreshed": False,
        "status_snapshot_path": "",
    }
    assert not fx["target_marker"].exists()
    assert not fx["sidecar"].exists()
    assert fx["canonical_marker"].exists()
    assert fx["target_workspace"].exists()
    assert fx["canonical_workspace"].exists()
    tombstone = Path(result["record_path"])
    assert tombstone.is_file()
    assert _sha(tombstone) == result["tombstone_sha256"]
    assert Path(result["archive_dir"], "artifacts", "target.json").is_file()
    assert Path(result["archive_dir"], "artifacts", "target.chain-health.progress.json").is_file()

    repeated = _retire(fx, expected_marker_sha256=result["identity"]["marker_sha256"])
    assert repeated["already_retired"] is True
    assert repeated["retirement_id"] == result["retirement_id"]


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"tmux_probe": lambda _session: True}, "active_runner"),
        (
            {"process_probe": lambda _session, _workspace, _spec: [{"pid": 42}]},
            "active_process",
        ),
        ({"completion_manifest_sha256": "0" * 64}, "completion_manifest_mismatch"),
        ({"expected_marker_sha256": "0" * 64}, "marker_changed"),
    ],
)
def test_retirement_fails_closed_without_mutation(
    tmp_path: Path, overrides: dict[str, object], code: str
) -> None:
    fx = _fixture(tmp_path)

    with pytest.raises(RetirementBlocked) as caught:
        _retire(fx, **overrides)

    assert caught.value.code == code
    assert fx["target_marker"].exists()
    assert fx["sidecar"].exists()
    assert fx["canonical_marker"].exists()


def test_retirement_rejects_ambiguous_marker_identity(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    marker = json.loads(fx["target_marker"].read_text(encoding="utf-8"))
    marker["session"] = "different"
    _write_json(fx["target_marker"], marker)

    with pytest.raises(RetirementBlocked) as caught:
        _retire(fx, expected_marker_sha256=_sha(fx["target_marker"]))

    assert caught.value.code == "ambiguous_identity"
    assert fx["target_marker"].exists()


def test_retirement_rejects_shared_workspace(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    sibling = _write_json(
        fx["marker_dir"] / "sibling.json",
        {
            "session": "sibling",
            "run_kind": "chain",
            "workspace": str(fx["target_workspace"]),
            "remote_spec": str(fx["target_spec"]),
        },
    )

    with pytest.raises(RetirementBlocked) as caught:
        _retire(fx)

    assert caught.value.code == "shared_asset_risk"
    assert sibling.exists()
    assert fx["target_marker"].exists()


def test_retirement_rejects_shared_repair_index_reference(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    _write_json(
        fx["marker_dir"] / "repair-data" / "index.json",
        {"sessions": {"target": {"status": "paused"}}},
    )

    with pytest.raises(RetirementBlocked) as caught:
        _retire(fx)

    assert caught.value.code == "shared_asset_risk"
    assert fx["target_marker"].exists()


def test_cloud_cli_registers_explicit_retirement_identity_fences() -> None:
    parser = argparse.ArgumentParser()
    _register_cloud_subcommands(parser)

    args = parser.parse_args(
        [
            "retire-chain",
            "--session",
            "target",
            "--expect-marker-sha256",
            "a" * 64,
            "--superseded-by",
            "canonical",
            "--expect-superseding-marker-sha256",
            "b" * 64,
            "--completion-manifest",
            "/evidence/completion.json",
            "--completion-manifest-sha256",
            "c" * 64,
            "--git-repo",
            "/repo",
            "--landed-commit",
            "abc123",
            "--reason",
            "duplicate",
            "--on-box",
        ]
    )

    assert args.cloud_action == "retire-chain"
    assert args.session == "target"
    assert args.superseded_by == "canonical"
    assert args.on_box is True
