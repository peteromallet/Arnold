from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import runtime_cutover
from arnold_pipelines.megaplan.cloud import legacy_marker_runtime_migration
from arnold_pipelines.megaplan.cloud.legacy_marker_runtime_migration import (
    migrate_legacy_marker_runtime,
)
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


def _runtime_b_relaunch() -> str:
    return f"exec /workspace/runtime-b/bin/chain # {'b' * 40}"


def _legacy_runtime() -> dict:
    root = "/workspace/runtime-candidates/arnold-18b279f5ef-live"
    return normalize_runtime_identity(
        {
            "import_root": root,
            "source_revision": "1" * 40,
            "editable_root": root,
            "editable_revision": "1" * 40,
            "direct_url": {
                "dir_info": {"editable": True},
                "url": f"file://{root}",
            },
            "pth": [
                {
                    "path": "/venv/site-packages/_editable_impl_arnold.pth",
                    "entries": [root],
                    "readable": True,
                }
            ],
            "imports": {
                "arnold": f"{root}/arnold/__init__.py",
                "arnold_pipelines": f"{root}/arnold_pipelines/__init__.py",
                "megaplan": f"{root}/arnold_pipelines/megaplan/__init__.py",
            },
        }
    )


def _legacy_migration_fixture(tmp_path: Path) -> dict:
    session = "critique-ledger-r5"
    workspace = "/workspace/critique-ledger-r5/Arnold"
    remote_spec = f"{workspace}/.megaplan/initiatives/critique-ledger/chain.yaml"
    plan = "cl2-wbc-backed-ledger"
    runtime = _legacy_runtime()
    relaunch = (
        f"SRC={runtime['import_root']}; "
        f"PYTHONPATH={runtime['import_root']} python -P -m "
        f"arnold_pipelines.megaplan chain start --spec {remote_spec}"
    )
    marker_path = tmp_path / f"{session}.json"
    marker_path.write_text(
        json.dumps(
            {
                "session": session,
                "workspace": workspace,
                "remote_spec": remote_spec,
                "run_kind": "chain",
                "should_run": False,
                "operator_pause": {"active": True, "plan": plan},
                "editable_source_branch": "editible-install",
                "editable_source_head": None,
                "editable_install_sync": {
                    "status": "skipped",
                    "reason": "disabled_by_flag",
                },
                "relaunch_command": relaunch,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    chain_state_path = tmp_path / "chain-state.json"
    chain_state_path.write_text(
        json.dumps(
            {
                "current_plan_name": plan,
                "last_state": "paused",
                "metadata": {
                    "operator_pause": {"active": True, "plan": plan},
                    "chain_spec_path": remote_spec,
                    "execution_binding": {
                        "launched_identity": {"spec_path": remote_spec},
                        "runtime_binding": {"current_identity": runtime},
                    },
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    identity_path = tmp_path / "runtime-identity.json"
    identity_path.write_text(json.dumps(runtime), encoding="utf-8")
    receipt_path = tmp_path / "runtime-receipt.json"
    receipt_path.write_text("{}\n", encoding="utf-8")
    return {
        "session": session,
        "workspace": workspace,
        "remote_spec": remote_spec,
        "plan": plan,
        "runtime": runtime,
        "relaunch": relaunch,
        "marker_path": marker_path,
        "chain_state_path": chain_state_path,
        "identity_path": identity_path,
        "receipt_path": receipt_path,
    }


def _migrate_legacy(fixture: dict, **overrides):
    marker_path = fixture["marker_path"]
    args = {
        "expected_marker_sha256": _sha(marker_path),
        "expected_relaunch_command_sha256": hashlib.sha256(
            fixture["relaunch"].encode("utf-8")
        ).hexdigest(),
        "expected_legacy_runtime_root": fixture["runtime"]["import_root"],
        "expected_chain_runtime_sha256": fixture["runtime"]["content_sha256"],
        "expected_session": fixture["session"],
        "expected_workspace": fixture["workspace"],
        "expected_remote_spec": fixture["remote_spec"],
        "expected_current_plan": fixture["plan"],
        "chain_state_path": fixture["chain_state_path"],
        "runtime_identity_path": fixture["identity_path"],
        "runtime_provenance_receipt_path": fixture["receipt_path"],
        "reason": "bind exact legacy runtime before cutover",
        "actor": "test-operator",
    }
    args.update(overrides)
    return migrate_legacy_marker_runtime(marker_path, **args)


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
        relaunch_command=_runtime_b_relaunch(),
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
            relaunch_command=_runtime_b_relaunch(),
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
            relaunch_command=_runtime_b_relaunch(),
            reason="failure injection",
        )

    assert marker_path.read_bytes() == before
    assert [
        path.name for path in tmp_path.glob("custody.json.*")
    ] == ["custody.json.runtime-cutover.lock"]


def test_marker_runtime_update_rejects_mismatched_relaunch_before_mutation(
    tmp_path: Path,
) -> None:
    marker_path = tmp_path / "custody.json"
    marker = _write_marker(marker_path)
    before = marker_path.read_bytes()
    previous = marker_runtime_identity(marker)
    assert previous is not None

    with pytest.raises(CliError, match="does not bind"):
        update_marker_runtime(
            marker_path,
            expected_marker_sha256=_sha(marker_path),
            expected_previous_runtime_sha256=previous["content_sha256"],
            active_runtime_identity=_runtime_b(),
            relaunch_command=f"exec /workspace/runtime-a/bin/chain # {'a' * 40}",
            reason="must reject split custody",
        )

    assert marker_path.read_bytes() == before


def test_legacy_marker_migration_binds_exact_chain_runtime_and_immutable_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    fixture = _legacy_migration_fixture(tmp_path)
    verifier_calls: list[tuple[Path, Path]] = []

    def verifier(identity_path: Path, receipt_path: Path) -> dict:
        verifier_calls.append((identity_path, receipt_path))
        return fixture["runtime"]

    monkeypatch.setattr(
        legacy_marker_runtime_migration, "verify_external_runtime_identity", verifier
    )

    result = _migrate_legacy(fixture)

    assert verifier_calls == [
        (fixture["identity_path"].resolve(), fixture["receipt_path"].resolve())
    ]
    marker = json.loads(fixture["marker_path"].read_text(encoding="utf-8"))
    assert marker_runtime_identity(marker) == fixture["runtime"]
    assert marker["should_run"] is False
    assert marker["operator_pause"]["active"] is True
    assert marker["relaunch_command"] == fixture["relaunch"]
    assert marker["run_id"] == result["run_id"]
    assert marker["run_id"]
    assert result["marker_after_sha256"] == _sha(fixture["marker_path"])
    receipt_path = Path(result["receipt_path"])
    commit_path = Path(result["commit_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    commit = json.loads(commit_path.read_text(encoding="utf-8"))
    assert receipt["run_id"] == result["run_id"]
    assert receipt["marker_before_sha256"] == result["marker_before_sha256"]
    assert receipt["marker_after_sha256"] == result["marker_after_sha256"]
    assert commit["receipt_sha256"] == _sha(receipt_path)

    with pytest.raises(FileExistsError):
        receipt_path.open("x").close()
    with pytest.raises(FileExistsError):
        commit_path.open("x").close()


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("marker_sha", "changed before migration"),
        ("relaunch_sha", "relaunch command hash"),
        ("runtime_root", "verified runtime identity"),
        ("session", "identity fields changed"),
        ("chain_plan", "current plan guard"),
        ("chain_pause", "durably paused chain"),
        ("chain_spec_missing", "canonical chain and launched execution bindings"),
        ("chain_spec_conflict", "canonical chain and launched execution bindings"),
        ("launch_spec_missing", "canonical chain and launched execution bindings"),
        ("launch_spec_conflict", "canonical chain and launched execution bindings"),
        ("marker_pause", "marker-side operator-pause"),
        ("should_run", "should_run=false"),
        ("chain_runtime", "chain runtime digest"),
        ("partial_binding", "already has a runtime identity"),
    ],
)
def test_legacy_marker_migration_rejects_stale_or_ambiguous_custody(
    tmp_path: Path, monkeypatch, mutation: str, error: str
) -> None:
    fixture = _legacy_migration_fixture(tmp_path)
    monkeypatch.setattr(
        legacy_marker_runtime_migration,
        "verify_external_runtime_identity",
        lambda *_args: fixture["runtime"],
    )
    overrides = {}
    if mutation == "marker_sha":
        overrides["expected_marker_sha256"] = "f" * 64
    elif mutation == "relaunch_sha":
        overrides["expected_relaunch_command_sha256"] = "f" * 64
    elif mutation == "runtime_root":
        overrides["expected_legacy_runtime_root"] = (
            "/workspace/runtime-candidates/arnold-other"
        )
    elif mutation == "session":
        overrides["expected_session"] = "another-session"
    elif mutation in {
        "chain_plan",
        "chain_pause",
        "chain_spec_missing",
        "chain_spec_conflict",
        "launch_spec_missing",
        "launch_spec_conflict",
        "chain_runtime",
    }:
        state = json.loads(fixture["chain_state_path"].read_text(encoding="utf-8"))
        if mutation == "chain_plan":
            state["current_plan_name"] = "another-plan"
        elif mutation == "chain_pause":
            state["last_state"] = "gated"
        elif mutation == "chain_spec_missing":
            state["metadata"].pop("chain_spec_path")
        elif mutation == "chain_spec_conflict":
            state["metadata"]["chain_spec_path"] = "/workspace/other/chain.yaml"
        elif mutation == "launch_spec_missing":
            state["metadata"]["execution_binding"]["launched_identity"].pop(
                "spec_path"
            )
        elif mutation == "launch_spec_conflict":
            state["metadata"]["execution_binding"]["launched_identity"][
                "spec_path"
            ] = "/workspace/other/chain.yaml"
        else:
            state["metadata"]["execution_binding"]["runtime_binding"][
                "current_identity"
            ]["content_sha256"] = "e" * 64
        fixture["chain_state_path"].write_text(json.dumps(state), encoding="utf-8")
    else:
        marker = json.loads(fixture["marker_path"].read_text(encoding="utf-8"))
        if mutation == "marker_pause":
            marker["operator_pause"] = None
        elif mutation == "should_run":
            marker["should_run"] = True
        elif mutation == "partial_binding":
            marker["runtime_binding"] = {"current_identity": fixture["runtime"]}
        fixture["marker_path"].write_text(json.dumps(marker), encoding="utf-8")

    with pytest.raises(CliError, match=error):
        _migrate_legacy(fixture, **overrides)


def test_legacy_marker_migration_rejects_external_receipt_identity_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    fixture = _legacy_migration_fixture(tmp_path)
    monkeypatch.setattr(
        legacy_marker_runtime_migration,
        "verify_external_runtime_identity",
        lambda *_args: _runtime_b(),
    )

    with pytest.raises(CliError, match="verified runtime identity"):
        _migrate_legacy(fixture)
