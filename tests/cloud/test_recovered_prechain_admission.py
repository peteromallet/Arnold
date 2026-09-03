from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import recovered_prechain_admission as admission


def _write(path: Path, value: object) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    path.write_bytes(raw)
    return raw


def _fixture(tmp_path: Path) -> dict[str, object]:
    session = "native-build-forward-c2-test"
    slug = "native-build-forward-continuation-test"
    workspace = tmp_path / "workspace"
    runtime = tmp_path / "runtime"
    marker = tmp_path / "cloud-sessions" / f"{session}.json"
    manifest = tmp_path / "manifests" / f"{slug}.json"
    state = tmp_path / "chain-state.json"
    spec = "/workspace/runtime-candidates/test/.megaplan/initiatives/test/chain.yaml"
    new_sha = "a" * 40
    operation = "b" * 64
    manifest_raw = _write(
        manifest,
        {
            "schema": "1", "epic_id": slug, "generation": 2,
            "epic": {"runtime_root": str(runtime), "expected_head": new_sha},
        },
    )
    archive = tmp_path / "custody" / operation / "manifest.json"
    archive_raw = _write(archive, {"operation_id": operation, "files": []})
    marker_value = {
        "session": session, "workspace": str(workspace), "remote_spec": spec,
        "should_run": True, "operator_pause": None,
        "launch_outcome": {"status": "failed", "code": "launch_not_advanced"},
        "failed_prechain_recovery": {
            "schema": "arnold.megaplan.failed-prechain-recovery.v1",
            "operation_id": operation, "old_sha": "c" * 40, "new_sha": new_sha,
            "chain_workspace": str(workspace),
            "engine_runtime_after": str(runtime), "manifest_generation": 2,
            "archive_manifest": {"path": str(archive), "sha256": hashlib.sha256(archive_raw).hexdigest()},
        },
    }
    marker_raw = _write(marker, marker_value)
    marker_sha = hashlib.sha256(marker_raw).hexdigest()
    receipt = {
        "operation_id": operation, "outcome": "recovered", "workspace": str(workspace),
        "engine_runtime": {"new_path": str(runtime)},
        "marker": {"path": str(marker), "after_sha256": marker_sha},
        "manifest": {"path": str(manifest), "after_sha256": hashlib.sha256(manifest_raw).hexdigest(), "generation": 2},
        "source": {"new_sha": new_sha},
    }
    _write(archive.parent / "recovery-receipt.json", receipt)
    ledger = workspace / ".megaplan" / "incident-ledger" / "events.jsonl"
    _write(
        ledger,
        {
            "operation_id": operation, "event_kind": "chain_control.committed",
            "payload": {
                "outcome": "committed",
                "effect": {"source_new_sha": new_sha, "manifest_generation": 2,
                           "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
                           "marker_sha256": marker_sha},
            },
        },
    )
    lease = marker.parent / f"{session}.liveness-lease.json"
    _write(lease, {
        "session": session, "status": "stopped", "workspace": str(workspace),
        "remote_spec": spec, "expires_at": "2000-01-01T00:00:00Z",
        "target_pid": 999999,
    })
    _write(marker.parent / f".{session}.liveness-fence.json", {"session": session, "runner_fence": 1})
    return {"manifest": manifest, "marker": marker, "state": state, "runtime": runtime,
            "workspace": workspace, "session": session, "slug": slug, "spec": spec,
            "lease": lease, "new_sha": new_sha}


def _run_admit(fixture: dict[str, object]) -> None:
    admission._admit(
        manifest_path=fixture["manifest"], marker_path=fixture["marker"],
        state_path=fixture["state"], runtime_src=str(fixture["runtime"]),
        session=str(fixture["session"]), slug=str(fixture["slug"]),
        expected_spec=str(fixture["spec"]), expected_workspace=str(fixture["workspace"]),
    )


def _mock_authorities(monkeypatch: pytest.MonkeyPatch, fixture: dict[str, object]) -> None:
    operation = "b" * 64
    manifest = Path(fixture["manifest"])
    marker = Path(fixture["marker"])
    archive = manifest.parent.parent / "custody" / operation / "manifest.json"
    event = {
        "event_kind": "chain_control.committed", "operation_id": operation,
        "chain_id": "chain-" + hashlib.sha256(str(Path(fixture["spec"]).resolve()).encode()).hexdigest()[:16],
        "spec_identity": str(fixture["spec"]), "outcome": "committed",
        "source_identity": {"new_sha": fixture["new_sha"], "chain_workspace": str(fixture["workspace"]), "engine_runtime": str(fixture["runtime"])},
        "linked_receipts": [str(archive)],
        "payload": {
            "intent_kind": "failed_prechain_recovery",
            "effect": {
                "source_new_sha": fixture["new_sha"], "manifest_generation": 2,
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "marker_sha256": hashlib.sha256(marker.read_bytes()).hexdigest(),
                "staged_runtime": str(fixture["runtime"]),
            },
        },
    }
    monkeypatch.setattr(admission, "journal_for", lambda _root: type("J", (), {"replay_strict": lambda self: {"accepted": [event]}})())
    monkeypatch.setattr(admission, "_git_identity", lambda *a, **k: (fixture["new_sha"], "d" * 40, "https://github.com/example/Arnold.git", ""))


def test_recovered_prechain_marker_is_admitted_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(admission.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 1, "", ""))
    _mock_authorities(monkeypatch, fixture)
    before = {p: p.read_bytes() for p in (fixture["marker"], fixture["lease"])}
    _run_admit(fixture)
    assert {p: p.read_bytes() for p in before} == before


def test_ordinary_existing_marker_is_not_admitted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path)
    marker = json.loads(fixture["marker"].read_text())
    marker.pop("failed_prechain_recovery")
    fixture["marker"].write_text(json.dumps(marker), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _run_admit(fixture)
    assert exc.value.code == 77


def test_strict_replay_and_receipt_marker_binding_are_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(admission, "journal_for", lambda _root: type("J", (), {"replay_strict": lambda self: {"accepted": [{}]}})())
    with pytest.raises(SystemExit) as exc:
        _run_admit(fixture)
    assert exc.value.code == 78

    fixture = _fixture(tmp_path / "tampered")
    _mock_authorities(monkeypatch, fixture)
    receipt = next(Path(tmp_path / "tampered").glob("custody/*/recovery-receipt.json"))
    value = json.loads(receipt.read_text())
    value["marker"]["after_sha256"] = "0" * 64
    receipt.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _run_admit(fixture)
    assert exc.value.code == 78


def test_non_git_runtime_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        admission._git_identity(tmp_path / "missing-runtime", expected_head="a" * 40, expected_branch="", canonical_origin=None)
    assert exc.value.code == 78


@pytest.mark.parametrize("change", ["pid", "lease", "fence", "state", "receipt"])
def test_recovered_prechain_rejects_live_or_mismatched_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str) -> None:
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(admission.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 1, "", ""))
    _mock_authorities(monkeypatch, fixture)
    if change == "pid":
        marker = json.loads(fixture["marker"].read_text())
        marker["pid"] = 1
        fixture["marker"].write_text(json.dumps(marker), encoding="utf-8")
    elif change == "lease":
        lease = json.loads(fixture["lease"].read_text())
        lease["status"] = "running"
        fixture["lease"].write_text(json.dumps(lease), encoding="utf-8")
    elif change == "fence":
        fence = fixture["marker"].parent / f".{fixture['session']}.liveness-fence.json"
        fence.write_text(json.dumps({"session": fixture["session"], "owner_pid": 1}), encoding="utf-8")
    elif change == "state":
        fixture["state"].write_text("{}", encoding="utf-8")
    else:
        receipt = fixture["marker"].parent.parent / "custody" / ("b" * 64) / "recovery-receipt.json"
        receipt.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _run_admit(fixture)
    assert exc.value.code == 78
