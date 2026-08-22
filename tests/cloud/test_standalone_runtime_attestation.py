from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.cloud import runtime_attestation as attestation
from arnold_pipelines.megaplan.cli import _main
from arnold_pipelines.megaplan.types import CliError


def _healthy_runtime_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], Path, str]:
    """Issue a standalone seed with vectors isolated from host .pth state."""
    root = Path(__file__).resolve().parents[2]
    revision = attestation._git_revision(root)
    provenance = {
        "ok": True,
        "errors": [],
        "expected_root": str(root),
        "expected_revision": revision,
        "import_root": str(root),
        "editable_root": "",
        "direct_url": {},
        "pth": [],
        "source_revision": revision,
        "runtime_revision": revision,
        "imports": {},
    }
    modules = attestation._module_vector(root)[0]
    wrappers = attestation._wrapper_vector(root)[0]
    monkeypatch.setattr(attestation, "runtime_provenance", lambda **_: provenance)
    monkeypatch.setattr(attestation, "_pth_vector", lambda _root: ([], []))
    monkeypatch.setattr(attestation, "_module_vector", lambda _root: (modules, []))
    monkeypatch.setattr(attestation, "_wrapper_vector", lambda _root: (wrappers, []))
    seed = attestation.build_standalone_runtime_launch_seed(
        project_root=root,
        expected_project_revision=revision,
        runtime_root=root,
        expected_runtime_revision=revision,
        generated_at="2026-08-22T00:00:00Z",
    )
    assert seed["ready"] is True
    return seed, root, revision


def _recache(seed: dict[str, Any]) -> dict[str, Any]:
    core = {key: value for key, value in seed.items() if key != "content_sha256"}
    seed["content_sha256"] = attestation._canonical_sha256(core)
    return seed


def test_standalone_seed_validates_and_process_attestation_binds_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)

    result = attestation.validate_runtime_launch_seed(seed, component="resident")
    assert result["status"] == "ready"
    assert result["authority"] == attestation.RUNTIME_LAUNCH_STANDALONE_AUTHORITY

    process = {
        "pid": 123,
        "start_ticks": "456",
        "executable": str(Path(sys.executable).resolve()),
        "executable_sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        "selectors": {},
    }
    monkeypatch.setattr(attestation, "_proc_identity", lambda _pid: process)
    receipt = attestation.create_runtime_process_attestation(
        seed, component="resident", target_pid=123
    )
    assert receipt["authority"] == attestation.RUNTIME_LAUNCH_STANDALONE_AUTHORITY
    assert attestation.validate_runtime_process_attestation(
        seed, receipt, component="resident", target_pid=123
    )["status"] == "ready"

    state = tmp_path / "runtime-launch"
    state.mkdir(mode=0o700)
    state.chmod(0o700)
    monkeypatch.setattr(attestation, "standalone_runtime_launch_dir", lambda _root, create=True: state)
    paths = attestation.standalone_dispatch_paths(
        Path(str(seed["project_root"])),
        head=str(seed["expected_project_revision"]),
        seed_sha256=str(seed["content_sha256"]),
    )
    published = attestation.write_standalone_runtime_publication(
        seed=seed,
        seed_path=paths["seed"],
        root=Path(str(seed["project_root"])),
        generated_at=seed["generated_at"],
    )
    seed_path = paths["seed"]
    process_path = paths["status"]
    monkeypatch.setenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", str(seed_path))
    monkeypatch.setenv("MEGAPLAN_RUNTIME_PROCESS_ATTESTATION", str(process_path))
    assert attestation.require_configured_runtime_launch(
        "resident", target_pid=123, create=True
    )["authority"] == attestation.RUNTIME_LAUNCH_STANDALONE_AUTHORITY
    assert json.loads(process_path.read_text(encoding="utf-8"))["authority"] == (
        attestation.RUNTIME_LAUNCH_STANDALONE_AUTHORITY
    )




@pytest.mark.parametrize(
    "field",
    [
        "schema",
        "authority",
        "project_root",
        "expected_project_revision",
        "live_project_revision",
        "runtime_root",
        "expected_runtime_revision",
        "live_runtime_revision",
        "generated_at",
        "runtime_provenance",
        "loaded_modules",
        "interpreter",
        "site_pth",
        "wrappers",
        "errors",
        "ready",
        "content_sha256",
    ],
)
def test_standalone_seed_requires_every_digest_covered_field(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    """The two-root schema has no missing-field fallback for ANY seed field."""
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    missing = {key: value for key, value in seed.items() if key != field}
    if field != "content_sha256":
        # Recache re-derives content_sha256 itself; dropping the digest field
        # must stay dropped so the digest gate rejects it.
        _recache(missing)
    with pytest.raises(CliError):
        attestation.validate_standalone_runtime_launch_seed(missing)


@pytest.mark.parametrize(
    "field",
    ["expected_root", "expected_revision", "live_revision"],
)
def test_standalone_seed_rejects_legacy_one_root_fields(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    """Retired one-root field names are tampering evidence, never fallbacks."""
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    altered = {**seed, field: "legacy-value"}
    _recache(altered)
    with pytest.raises(CliError, match="legacy field"):
        attestation.validate_standalone_runtime_launch_seed(altered)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("authority", attestation.RUNTIME_LAUNCH_CLOUD_AUTHORITY),
        ("authority", "arnold.megaplan.runtime-launch/unknown/v1"),
        ("project_root", "/tmp/foreign-repository"),
        ("expected_project_revision", "a" * 40),
        ("live_project_revision", "b" * 40),
        ("runtime_root", "/tmp/foreign-runtime"),
        ("expected_runtime_revision", "a" * 40),
        ("live_runtime_revision", "b" * 40),
    ],
)
def test_standalone_seed_wrong_authority_root_or_head_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
) -> None:
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    altered = {**seed, field: value}
    _recache(altered)
    with pytest.raises(CliError):
        attestation.validate_standalone_runtime_launch_seed(altered)


def test_standalone_seed_digest_requires_recognized_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    missing = {key: value for key, value in seed.items() if key != "authority"}
    _recache(missing)
    with pytest.raises(CliError, match="digest"):
        attestation.validate_standalone_runtime_launch_seed(missing)


def test_cloud_worker_validation_rejects_standalone_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    with pytest.raises(CliError):
        attestation.validate_runtime_launch_seed(seed, component="worker")


@pytest.mark.parametrize("errors", [None, {}, "not-a-list"])
def test_standalone_seed_requires_canonical_errors_vector(
    monkeypatch: pytest.MonkeyPatch,
    errors: Any,
) -> None:
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    altered = dict(seed)
    if errors is None:
        altered.pop("errors")
    else:
        altered["errors"] = errors
    _recache(altered)
    with pytest.raises(CliError):
        attestation.validate_standalone_runtime_launch_seed(altered)


@pytest.mark.parametrize(
    "field",
    ["manifest_sha256", "marker", "supervisor_receipt", "supervisor_runtime", "hot_env", "chain_runtime_binding"],
)
def test_standalone_seed_rejects_nonempty_cloud_evidence(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    altered = {**seed, field: "cloud-evidence"}
    _recache(altered)
    with pytest.raises(CliError, match="cloud field"):
        attestation.validate_standalone_runtime_launch_seed(altered)


@pytest.mark.parametrize("vector", ["runtime_provenance", "loaded_modules", "site_pth", "wrappers", "interpreter"])
def test_standalone_seed_vector_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    vector: str,
) -> None:
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    if vector == "runtime_provenance":
        monkeypatch.setattr(attestation, "runtime_provenance", lambda **_: {**seed[vector], "source_revision": "c" * 40})
    elif vector == "loaded_modules":
        monkeypatch.setattr(attestation, "_module_vector", lambda _root: ([{"module": "foreign", "path": "/tmp/foreign.py", "root": ""}], []))
    elif vector == "site_pth":
        monkeypatch.setattr(attestation, "_pth_vector", lambda _root: ([{"path": "/tmp/foreign.pth"}], []))
    elif vector == "wrappers":
        monkeypatch.setattr(attestation, "_wrapper_vector", lambda _root: ([{"path": "/tmp/changed", "sha256": "0" * 64}], []))
    else:
        monkeypatch.setattr(attestation, "_interpreter_vector", lambda **_: {"executable": "/tmp/foreign-python"})
    with pytest.raises(CliError):
        attestation.validate_standalone_runtime_launch_seed(seed)


def test_edited_seed_and_cloud_dispatch_path_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    edited = {**seed, "generated_at": "2026-08-23T00:00:00Z"}
    with pytest.raises(CliError, match="digest"):
        attestation.validate_standalone_runtime_launch_seed(edited)

    seed_path = tmp_path / "standalone.json"
    seed_path.write_text(json.dumps(seed), encoding="utf-8")
    assert attestation._launch_seed_current(
        seed_path,
        root=root,
        expected_revision=revision,
        marker_path=tmp_path / "marker.json",
        manifest_path=tmp_path / "manifest.json",
    ) is False


def test_standalone_process_attestation_cannot_cross_into_cloud_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    process = {
        "pid": 123,
        "start_ticks": "456",
        "executable": str(Path(sys.executable).resolve()),
        "executable_sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        "selectors": {},
    }
    monkeypatch.setattr(attestation, "_proc_identity", lambda _pid: process)
    resident_receipt = attestation.create_runtime_process_attestation(
        seed, component="resident", target_pid=123
    )
    forged = dict(resident_receipt)
    forged["component"] = "worker"
    forged_core = {key: forged.get(key) for key in (
        "schema", "authority", "component", "seed_sha256", "runtime_vector_sha256", "process"
    )}
    forged["content_sha256"] = attestation._canonical_sha256(forged_core)
    with pytest.raises(CliError):
        attestation.validate_runtime_process_attestation(
            seed, forged, component="worker", target_pid=123
        )


def test_standalone_admission_rejects_expected_head_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    with pytest.raises(CliError):
        attestation.build_standalone_runtime_launch_seed(
            project_root=root,
            expected_project_revision=f" {revision} ",
            runtime_root=root,
            expected_runtime_revision=revision,
        )


def test_publication_pointer_is_content_addressed_and_rejects_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state = tmp_path / "runtime-launch"
    state.mkdir(mode=0o700)
    state.chmod(0o700)
    monkeypatch.setattr(attestation, "standalone_runtime_launch_dir", lambda _root, create=True: state)
    paths = attestation.standalone_dispatch_paths(root, head=revision, seed_sha256=seed["content_sha256"])
    published = attestation.write_standalone_runtime_publication(
        seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
    )
    assert published["seed_path"] == paths["seed"]
    assert state.stat().st_mode & 0o777 == 0o700
    assert paths["seed"].parent.stat().st_mode & 0o777 == 0o700
    assert paths["receipts"].stat().st_mode & 0o777 == 0o700
    assert paths["status"].parent.stat().st_mode & 0o777 == 0o700
    assert paths["seed"].stat().st_mode & 0o777 == 0o600
    assert published["receipt_path"].stat().st_mode & 0o777 == 0o600
    assert attestation.load_standalone_runtime_dispatch_pointer(root)["authority"] == attestation.RUNTIME_LAUNCH_STANDALONE_AUTHORITY
    seed_path = paths["seed"]
    process = {
        "pid": 123,
        "start_ticks": "456",
        "executable": str(Path(sys.executable).resolve()),
        "executable_sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        "selectors": {},
    }
    monkeypatch.setattr(attestation, "_proc_identity", lambda _pid: process)
    monkeypatch.setenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", str(seed_path))
    monkeypatch.setenv("MEGAPLAN_RUNTIME_PROCESS_ATTESTATION", str(paths["status"]))
    attestation.require_configured_runtime_launch("resident", target_pid=123, create=True)
    assert paths["status"].stat().st_mode & 0o777 == 0o600

    pointer_path = paths["pointer"]
    valid_pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer_before_failed_issue = pointer_path.read_bytes()
    monkeypatch.setattr(
        attestation,
        "_wrapper_vector",
        lambda _root: ([{"path": "/tmp/foreign-wrapper", "sha256": "0" * 64}], []),
    )
    with pytest.raises(CliError):
        attestation.write_standalone_runtime_publication(
            seed=seed,
            seed_path=paths["seed"],
            root=root,
        )
    assert pointer_path.read_bytes() == pointer_before_failed_issue
    monkeypatch.setattr(attestation, "_wrapper_vector", lambda _root: (seed["wrappers"], []))
    pointer = dict(valid_pointer)
    pointer["seed_sha256"] = "0" * 64
    pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    with pytest.raises(CliError, match="digest"):
        attestation.load_standalone_runtime_dispatch_pointer(root)

    pointer_path.unlink()
    outside = tmp_path / "outside-pointer.json"
    outside.write_text(json.dumps(valid_pointer), encoding="utf-8")
    pointer_path.symlink_to(outside)
    with pytest.raises(CliError):
        attestation.load_standalone_runtime_dispatch_pointer(root)


def test_resident_attest_json_and_plain_contract_via_adapter(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected = {
        "success": True,
        "authority": attestation.RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
        "root": str(Path.cwd()),
        "expected_head": "a" * 40,
        "live_head": "a" * 40,
        "runtime_root": "/runtime/arnold",
        "expected_runtime_head": "d" * 40,
        "live_runtime_head": "d" * 40,
        "seed_path": "/repo/.megaplan/resident/runtime-launch/seeds/seed.json",
        "seed_sha256": "b" * 64,
        "receipt_path": "/repo/.megaplan/resident/runtime-launch/receipts/r.json",
        "receipt_sha256": "c" * 64,
        "pointer_path": "/repo/.megaplan/resident/runtime-launch/seeds/dispatch-current.json",
        "generated_at": "2026-08-22T00:00:00Z",
    }
    seed = {
        "project_root": str(Path.cwd()),
        "expected_project_revision": "a" * 40,
        "live_project_revision": "a" * 40,
        "runtime_root": "/runtime/arnold",
        "expected_runtime_revision": "d" * 40,
        "live_runtime_revision": "d" * 40,
        "content_sha256": "b" * 64,
    }
    paths = {
        "seed": Path(expected["seed_path"]),
        "pointer": Path(expected["pointer_path"]),
    }
    receipt = {"authority": expected["authority"], "root": expected["root"],
               "expected_head": expected["expected_head"], "live_head": expected["live_head"],
               "content_sha256": expected["receipt_sha256"]}
    published = {"receipt": receipt, "pointer": {"generated_at": expected["generated_at"]},
                 "receipt_path": Path(expected["receipt_path"]), "pointer_path": paths["pointer"]}
    monkeypatch.setattr(attestation, "build_standalone_runtime_launch_seed", lambda **_: seed)
    monkeypatch.setattr(attestation, "validate_standalone_runtime_launch_seed", lambda *_args, **_kwargs: {"status": "ready"})
    monkeypatch.setattr(attestation, "standalone_dispatch_paths", lambda *_args, **_kwargs: paths)
    monkeypatch.setattr(attestation, "write_standalone_runtime_publication", lambda **_: published)
    assert _main(
        [
            "resident",
            "attest",
            "--repo-root",
            "/repo",
            "--expected-head",
            "a" * 40,
            "--runtime-root",
            "/runtime/arnold",
            "--expected-runtime-head",
            "d" * 40,
        ]
    ) == 0
    assert capsys.readouterr().out == expected["seed_path"] + "\n"
    assert _main(
        [
            "resident",
            "attest",
            "--repo-root",
            "/repo",
            "--expected-head",
            "a" * 40,
            "--runtime-root",
            "/runtime/arnold",
            "--expected-runtime-head",
            "d" * 40,
            "--json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out) == expected


def test_resident_attest_wrong_head_returns_admission_exit_code_2(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def reject_admission(**_kwargs: Any) -> dict[str, Any]:
        raise CliError(attestation.RUNTIME_ATTESTATION_ERROR, "HEAD mismatch")

    monkeypatch.setattr(
        attestation,
        "build_standalone_runtime_launch_seed",
        reject_admission,
    )
    rc = _main(
        [
            "resident",
            "attest",
            "--repo-root",
            str(Path.cwd()),
            "--expected-head",
            "0" * 40,
            "--runtime-root",
            "/runtime/arnold",
            "--expected-runtime-head",
            "0" * 40,
        ]
    )
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is False
    assert payload["error"] == attestation.RUNTIME_ATTESTATION_ERROR


def test_resident_attest_publication_failure_does_not_advance_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = Path.cwd()
    head = attestation._git_revision(root)
    state = tmp_path / "runtime-launch"
    paths = {
        "seed": state / "seeds" / f"standalone-{head}-{'a' * 64}.json",
        "pointer": state / "seeds" / "dispatch-current.json",
    }
    paths["pointer"].parent.mkdir(parents=True)
    paths["pointer"].write_text('{"sentinel":true}\n', encoding="utf-8")
    before = paths["pointer"].read_bytes()
    seed = {
        "project_root": str(root),
        "expected_project_revision": head,
        "live_project_revision": head,
        "runtime_root": str(root),
        "expected_runtime_revision": head,
        "live_runtime_revision": head,
        "content_sha256": "a" * 64,
    }

    monkeypatch.setattr(
        attestation,
        "build_standalone_runtime_launch_seed",
        lambda **_kwargs: seed,
    )
    monkeypatch.setattr(
        attestation,
        "validate_standalone_runtime_launch_seed",
        lambda *_args, **_kwargs: {"status": "ready"},
    )
    monkeypatch.setattr(
        attestation,
        "standalone_dispatch_paths",
        lambda *_args, **_kwargs: paths,
    )

    def reject_publication(**_kwargs: Any) -> dict[str, Any]:
        raise CliError(attestation.RUNTIME_ATTESTATION_ERROR, "publication refused")

    monkeypatch.setattr(
        attestation,
        "write_standalone_runtime_publication",
        reject_publication,
    )
    rc = _main(
        [
            "resident",
            "attest",
            "--repo-root",
            str(root),
            "--expected-head",
            head,
            "--runtime-root",
            str(root),
            "--expected-runtime-head",
            head,
        ]
    )
    assert rc == 2
    assert paths["pointer"].read_bytes() == before
    assert json.loads(capsys.readouterr().out)["success"] is False


def _publish_healthy_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    seed: dict[str, Any],
    root: Path,
    revision: str,
) -> tuple[Path, dict[str, Path]]:
    """Publish a healthy standalone state into an isolated state directory."""
    state = tmp_path / "runtime-launch"
    state.mkdir(mode=0o700)
    monkeypatch.setattr(attestation, "standalone_runtime_launch_dir", lambda _root, create=True: state)
    paths = attestation.standalone_dispatch_paths(
        root, head=revision, seed_sha256=str(seed["content_sha256"])
    )
    attestation.write_standalone_runtime_publication(
        seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
    )
    return state, paths


def _patch_resident_process_identity(
    monkeypatch: pytest.MonkeyPatch,
    paths: dict[str, Path],
) -> None:
    process = {
        "pid": 123,
        "start_ticks": "456",
        "executable": str(Path(sys.executable).resolve()),
        "executable_sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        "selectors": {},
    }
    monkeypatch.setattr(attestation, "_proc_identity", lambda _pid: process)
    monkeypatch.setenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", str(paths["seed"]))
    monkeypatch.setenv("MEGAPLAN_RUNTIME_PROCESS_ATTESTATION", str(paths["status"]))


def test_worker_refresh_rejects_standalone_seed_without_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    _state, paths = _publish_healthy_state(tmp_path, monkeypatch, seed, root, revision)
    monkeypatch.setenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", str(paths["seed"]))
    for absent_manifest in (True, False):
        if absent_manifest:
            monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
        else:
            monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", "   ")
        with pytest.raises(CliError) as excinfo:
            attestation.refresh_runtime_launch_seed_for_worker_dispatch()
        assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
        assert "cloud-chain" in excinfo.value.message


@pytest.mark.parametrize("directory_name", ["seeds", "receipts", "status"])
def test_standalone_publication_rejects_unsafe_reused_directory_at_0755(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    directory_name: str,
) -> None:
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state, paths = _publish_healthy_state(tmp_path, monkeypatch, seed, root, revision)
    pointer_before = paths["pointer"].read_bytes()
    unsafe = state / directory_name
    unsafe.chmod(0o755)
    with pytest.raises(CliError) as excinfo:
        attestation.write_standalone_runtime_publication(
            seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
        )
    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
    assert stat.S_IMODE(unsafe.stat().st_mode) == 0o755  # never repaired
    assert paths["pointer"].read_bytes() == pointer_before

def test_standalone_publication_rejects_unsafe_mode_reuse_without_advancing_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reused seed/receipt must be regular 0600 files matching their digests."""
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state, paths = _publish_healthy_state(tmp_path, monkeypatch, seed, root, revision)
    pointer_before = paths["pointer"].read_bytes()
    # Valid 0600 idempotent reuse of BOTH immutable objects stays unchanged.
    attestation.write_standalone_runtime_publication(
        seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
    )
    assert paths["pointer"].read_bytes() == pointer_before
    # Tampered seed mode (content identical): reject, never advance or repair.
    paths["seed"].chmod(0o644)
    with pytest.raises(CliError) as excinfo:
        attestation.write_standalone_runtime_publication(
            seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
        )
    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
    assert stat.S_IMODE(paths["seed"].stat().st_mode) == 0o644  # never repaired
    assert paths["pointer"].read_bytes() == pointer_before
    # Tampered receipt mode (content identical): same fail-closed behavior.
    paths["seed"].chmod(0o600)
    receipt_path = next((state / "receipts").glob("*.json"))
    receipt_path.chmod(0o664)
    with pytest.raises(CliError) as excinfo:
        attestation.write_standalone_runtime_publication(
            seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
        )
    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
    assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o664  # never repaired
    assert stat.S_IMODE(paths["seed"].stat().st_mode) == 0o600
    assert paths["pointer"].read_bytes() == pointer_before

def test_standalone_publication_rejects_unsafe_existing_pointer_without_replacing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An existing dispatch pointer must be a regular 0600 file before replacement."""
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state, paths = _publish_healthy_state(tmp_path, monkeypatch, seed, root, revision)
    pointer_before = paths["pointer"].read_bytes()
    # Valid 0600 idempotent replacement stays byte-identical.
    attestation.write_standalone_runtime_publication(
        seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
    )
    assert paths["pointer"].read_bytes() == pointer_before
    # Permissive regular pointer: rejected without repair or replacement.
    paths["pointer"].chmod(0o644)
    with pytest.raises(CliError) as excinfo:
        attestation.write_standalone_runtime_publication(
            seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
        )
    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
    assert "permissions are unsafe" in excinfo.value.message
    assert stat.S_IMODE(paths["pointer"].stat().st_mode) == 0o644  # never repaired
    assert paths["pointer"].read_bytes() == pointer_before
    # Symlinked pointer: fail-closed via path custody; never followed,
    # replaced, or copied through.
    paths["pointer"].chmod(0o600)
    outside = tmp_path / "outside-pointer.json"
    outside.write_bytes(pointer_before)
    outside.chmod(0o600)
    paths["pointer"].unlink()
    paths["pointer"].symlink_to(outside)
    with pytest.raises(CliError) as excinfo:
        attestation.write_standalone_runtime_publication(
            seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
        )
    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
    assert "resident launch path contains a symlink" in excinfo.value.message
    assert paths["pointer"].is_symlink()  # symlink itself untouched
    assert outside.read_bytes() == pointer_before
    # Non-regular pointer (directory): rejected by the preflight itself.
    paths["pointer"].unlink()
    paths["pointer"].mkdir(mode=0o700)
    with pytest.raises(CliError) as excinfo:
        attestation.write_standalone_runtime_publication(
            seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
        )
    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
    assert "not a regular file" in excinfo.value.message
    assert paths["pointer"].is_dir()  # directory untouched, never replaced
    assert list(paths["pointer"].iterdir()) == []
    # Missing pointer remains creatable and lands as 0600 again.
    paths["pointer"].rmdir()
    attestation.write_standalone_runtime_publication(
        seed=seed, seed_path=paths["seed"], root=root, generated_at=seed["generated_at"]
    )
    assert paths["pointer"].read_bytes() == pointer_before
    assert stat.S_IMODE(paths["pointer"].stat().st_mode) == 0o600


def test_standalone_publication_rejection_does_not_create_missing_siblings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rejected publication with an unsafe ``status`` creates no missing siblings."""
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state = tmp_path / "runtime-launch"
    state.mkdir(mode=0o700)
    state.chmod(0o700)
    monkeypatch.setattr(attestation, "standalone_runtime_launch_dir", lambda _root, create=True: state)
    unsafe_status = state / "status"
    unsafe_status.mkdir()
    unsafe_status.chmod(0o755)
    seed_path = state / "seeds" / f"standalone-{revision}-{seed['content_sha256']}.json"
    with pytest.raises(CliError) as excinfo:
        attestation.write_standalone_runtime_publication(
            seed=seed, seed_path=seed_path, root=root, generated_at=seed["generated_at"]
        )
    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
    assert stat.S_IMODE(unsafe_status.stat().st_mode) == 0o755  # never repaired
    assert not (state / "seeds").exists()  # missing sibling never created by rejection
    assert not (state / "receipts").exists()  # missing sibling never created by rejection
    assert sorted(entry.name for entry in state.iterdir()) == ["status"]


@pytest.mark.parametrize("directory_name", ["seeds", "receipts", "status"])
def test_standalone_load_rejects_unsafe_reused_directory_at_0755(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    directory_name: str,
) -> None:
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state, paths = _publish_healthy_state(tmp_path, monkeypatch, seed, root, revision)
    pointer_before = paths["pointer"].read_bytes()
    unsafe = state / directory_name
    unsafe.chmod(0o755)
    with pytest.raises(CliError):
        attestation.load_standalone_runtime_dispatch_pointer(root)
    assert stat.S_IMODE(unsafe.stat().st_mode) == 0o755  # never repaired
    assert paths["pointer"].read_bytes() == pointer_before


def test_standalone_load_rejects_missing_status_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state, paths = _publish_healthy_state(tmp_path, monkeypatch, seed, root, revision)
    pointer_before = paths["pointer"].read_bytes()
    shutil.rmtree(state / "status")
    with pytest.raises(CliError):
        attestation.load_standalone_runtime_dispatch_pointer(root)
    assert not (state / "status").exists()  # never repaired
    assert paths["pointer"].read_bytes() == pointer_before
    assert stat.S_IMODE((state / "seeds").stat().st_mode) == 0o700
    assert stat.S_IMODE((state / "receipts").stat().st_mode) == 0o700


def test_resident_process_create_rejects_unsafe_status_directory_at_0755(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state, paths = _publish_healthy_state(tmp_path, monkeypatch, seed, root, revision)
    _patch_resident_process_identity(monkeypatch, paths)
    unsafe = state / "status"
    unsafe.chmod(0o755)
    with pytest.raises(CliError) as excinfo:
        attestation.require_configured_runtime_launch("resident", target_pid=123, create=True)
    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
    assert stat.S_IMODE(unsafe.stat().st_mode) == 0o755  # never repaired
    assert not paths["status"].exists()


def test_resident_process_read_rejects_unsafe_status_directory_at_0755(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, root, revision = _healthy_runtime_fixture(monkeypatch)
    state, paths = _publish_healthy_state(tmp_path, monkeypatch, seed, root, revision)
    _patch_resident_process_identity(monkeypatch, paths)
    attestation.require_configured_runtime_launch("resident", target_pid=123, create=True)
    status_before = paths["status"].read_bytes()
    unsafe = state / "status"
    unsafe.chmod(0o755)
    with pytest.raises(CliError) as excinfo:
        attestation.require_configured_runtime_launch("resident", target_pid=123, create=False)
    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR
    assert stat.S_IMODE(unsafe.stat().st_mode) == 0o755  # never repaired
    assert paths["status"].read_bytes() == status_before


def test_standalone_load_rejection_does_not_mutate_filesystem(tmp_path: Path) -> None:
    """Rejected standalone loads create no directories and change no modes."""
    root = tmp_path / "repo"
    root.mkdir()

    def filesystem_snapshot() -> dict[str, tuple[str, int]]:
        return {
            str(path.relative_to(root)): (
                "dir" if path.is_dir() else "file",
                stat.S_IMODE(path.lstat().st_mode),
            )
            for path in sorted(root.rglob("*"))
        }

    def expect_rejection(context: str) -> None:
        before = filesystem_snapshot()
        with pytest.raises(CliError):
            attestation.load_standalone_runtime_dispatch_pointer(root)
        assert filesystem_snapshot() == before, f"load mutated filesystem: {context}"

    expect_rejection("missing .megaplan parent")
    (root / ".megaplan").mkdir(mode=0o700)
    expect_rejection("missing .megaplan/resident parent")
    (root / ".megaplan" / "resident").mkdir(mode=0o700)
    expect_rejection("missing runtime-launch state directory")
    state = root / ".megaplan" / "resident" / "runtime-launch"
    state.mkdir(mode=0o700)
    expect_rejection("missing operational directories")
    (state / "seeds").mkdir(mode=0o700)
    expect_rejection("missing receipts and status directories")
    assert not (state / "receipts").exists()  # never created by rejection
    assert not (state / "status").exists()  # never created by rejection
    (state / "receipts").mkdir(mode=0o700)
    (state / "status").mkdir(mode=0o700)
    expect_rejection("missing dispatch pointer")
    assert not (state / "seeds" / "dispatch-current.json").exists()
    state.chmod(0o755)
    expect_rejection("unsafe state directory mode")
    assert stat.S_IMODE(state.stat().st_mode) == 0o755  # never repaired
    state.chmod(0o700)
    (state / "receipts").chmod(0o755)
    expect_rejection("unsafe receipts directory mode")
    assert stat.S_IMODE((state / "receipts").stat().st_mode) == 0o755  # never repaired


def test_standalone_preflight_rejects_foreign_project_root_before_status_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The launch-root binding rejects a foreign standalone seed typed and
    fail-closed before any status mutation; cloud authority, absent, and
    unreadable configurations stay under the canonical loader's handling."""
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    foreign = tmp_path / "other-project"
    foreign.mkdir()

    def forbidden_state(_root: Path, create: bool = True) -> Path:
        raise AssertionError("status state touched during root-binding preflight")

    monkeypatch.setattr(attestation, "standalone_runtime_launch_dir", forbidden_state)

    # No configuration at all: inert.
    monkeypatch.delenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", raising=False)
    attestation.ensure_standalone_launch_seed_binds_root(foreign)

    # Unreadable configuration: canonical loader owns the error, preflight is inert.
    monkeypatch.setenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", str(tmp_path / "missing-seed.json"))
    attestation.ensure_standalone_launch_seed_binds_root(foreign)

    # Cloud authority: not bound here (cloud/chain behavior unchanged).
    cloud_seed = tmp_path / "cloud-seed.json"
    cloud_seed.write_text(
        json.dumps({"authority": attestation.RUNTIME_LAUNCH_CLOUD_AUTHORITY}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", str(cloud_seed))
    attestation.ensure_standalone_launch_seed_binds_root(foreign)

    # Foreign standalone seed: typed reject without touching status state.
    foreign_seed = tmp_path / "foreign-seed.json"
    foreign_seed.write_text(
        json.dumps(
            {
                "authority": attestation.RUNTIME_LAUNCH_STANDALONE_AUTHORITY,
                "project_root": str(seed["project_root"]),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", str(foreign_seed))
    with pytest.raises(CliError) as excinfo:
        attestation.ensure_standalone_launch_seed_binds_root(foreign)
    assert excinfo.value.code == attestation.RUNTIME_ATTESTATION_ERROR

    # Matching launch root passes the preflight.
    attestation.ensure_standalone_launch_seed_binds_root(Path(str(seed["project_root"])))

    # Explicit None keeps non-threaded callers on unchanged behavior.
    attestation.ensure_standalone_launch_seed_binds_root(None)


def _publish_healthy_standalone_seed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[dict[str, Any], Path]:
    """Issue, publish, and pointer-bind a healthy standalone seed in tmp."""
    seed, _root, _revision = _healthy_runtime_fixture(monkeypatch)
    state = tmp_path / "runtime-launch"
    state.mkdir(mode=0o700)
    state.chmod(0o700)
    monkeypatch.setattr(
        attestation,
        "standalone_runtime_launch_dir",
        lambda _root, create=True: state,
    )
    paths = attestation.standalone_dispatch_paths(
        Path(str(seed["project_root"])),
        head=str(seed["expected_project_revision"]),
        seed_sha256=str(seed["content_sha256"]),
    )
    attestation.write_standalone_runtime_publication(
        seed=seed,
        seed_path=paths["seed"],
        root=Path(str(seed["project_root"])),
        generated_at=seed["generated_at"],
    )
    return seed, paths["seed"]


def _static_process_identity() -> dict[str, Any]:
    return {
        "pid": 123,
        "start_ticks": "456",
        "executable": str(Path(sys.executable).resolve()),
        "executable_sha256": hashlib.sha256(
            Path(sys.executable).read_bytes()
        ).hexdigest(),
        "selectors": {},
    }


def test_proc_identity_reads_a_live_process_without_mocks(tmp_path: Path) -> None:
    """Unpatched platform proof: a live child process is fully inspectable
    through the real psutil path on THIS operating system."""
    runtime_src = str(tmp_path / "runtime-src")
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        env={
            "PATH": os.environ.get("PATH", ""),
            "MEGAPLAN_RUNTIME_SRC": runtime_src,
        },
    )
    try:
        identity = attestation._proc_identity(child.pid)
    finally:
        child.kill()
        child.wait()
    assert identity["pid"] == child.pid
    assert Path(identity["executable"]).resolve() == Path(sys.executable).resolve()
    assert identity["executable_sha256"] == hashlib.sha256(
        Path(sys.executable).read_bytes()
    ).hexdigest()
    assert identity["selectors"] == {"MEGAPLAN_RUNTIME_SRC": runtime_src}
    assert identity["start_ticks"]


def test_require_configured_runtime_launch_accepts_relative_seed_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A relative MEGAPLAN_RUNTIME_LAUNCH_SEED loads identically to absolute."""
    seed, seed_path = _publish_healthy_standalone_seed(monkeypatch, tmp_path)
    monkeypatch.setattr(
        attestation, "_proc_identity", lambda _pid: _static_process_identity()
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        "MEGAPLAN_RUNTIME_LAUNCH_SEED", os.path.relpath(seed_path, tmp_path)
    )
    relative = attestation.require_configured_runtime_launch(
        "resident", target_pid=123, create=True
    )
    assert relative["authority"] == attestation.RUNTIME_LAUNCH_STANDALONE_AUTHORITY
    monkeypatch.setenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", str(seed_path))
    absolute = attestation.require_configured_runtime_launch(
        "resident", target_pid=123, create=True
    )
    assert absolute["content_sha256"] == relative["content_sha256"]


def test_preflight_configured_launch_seed_surfaces_custody_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Unset stays inert; configured-valid passes without creating process
    status; corrupt and foreign configurations fail typed."""
    monkeypatch.delenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", raising=False)
    assert attestation.preflight_configured_launch_seed(tmp_path) is None

    seed, seed_path = _publish_healthy_standalone_seed(monkeypatch, tmp_path)
    project_root = Path(str(seed["project_root"]))
    monkeypatch.setenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", str(seed_path))
    loaded = attestation.preflight_configured_launch_seed(project_root)
    assert loaded is not None
    assert loaded["content_sha256"] == seed["content_sha256"]

    foreign = tmp_path / "other-project"
    foreign.mkdir()
    with pytest.raises(CliError) as root_exc:
        attestation.preflight_configured_launch_seed(foreign)
    assert root_exc.value.code == attestation.RUNTIME_ATTESTATION_ERROR

    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    payload["loaded_modules"] = [{"tampered": True}]
    seed_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CliError) as corrupt_exc:
        attestation.preflight_configured_launch_seed(project_root)
    assert corrupt_exc.value.code == attestation.RUNTIME_ATTESTATION_ERROR
