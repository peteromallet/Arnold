from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import runtime_attestation as attestation
from arnold_pipelines.megaplan.types import CliError


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _release_seed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], dict[str, Path]]:
    root = tmp_path / "runtime"
    wrapper_dir = root / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"
    wrapper_dir.mkdir(parents=True)
    (wrapper_dir / "arnold-watchdog").write_text("#!/bin/sh\n", encoding="utf-8")
    revision = "a" * 40
    receipt = tmp_path / "supervisor-receipt.json"
    hot_env = tmp_path / "runtime.env"
    marker = tmp_path / "marker.json"
    chain_spec = tmp_path / "chain.yaml"
    seed_doc = tmp_path / "NORTHSTAR.md"
    _write_json(
        receipt,
        {
            "fingerprint": "supervisor-fingerprint",
            "runtime": sys.prefix,
            "source": str(root),
            "source_revision": revision,
            "imports": {"arnold_pipelines": str(root / "arnold_pipelines")},
        },
    )
    hot_env.write_text(
        f"export MEGAPLAN_RUNTIME_SRC={root}\n",
        encoding="utf-8",
    )
    runtime_identity = {
        "import_root": str(root),
        "source_revision": revision,
        "content_sha256": "b" * 64,
    }
    _write_json(marker, {"runtime_binding": {"current_identity": runtime_identity}})
    chain_spec.write_text("milestones: []\n", encoding="utf-8")
    seed_doc.write_text("# North Star\n", encoding="utf-8")
    provenance = {
        "ok": True,
        "ready": True,
        "errors": [],
        "import_root": str(root),
        "source_revision": revision,
    }
    modules = [
        {
            "module": "arnold_pipelines.megaplan.cloud.runtime_attestation",
            "path": str(
                root
                / "arnold_pipelines"
                / "megaplan"
                / "cloud"
                / "runtime_attestation.py"
            ),
            "root": str(root),
        }
    ]
    chain_binding = {
        "spec_path": str(chain_spec),
        "current_milestone_index": 0,
        "current_plan_name": "m10",
        "runtime_identity": runtime_identity,
    }
    chain_binding["content_sha256"] = attestation._canonical_sha256(chain_binding)
    monkeypatch.setattr(attestation, "runtime_provenance", lambda **_kwargs: provenance)
    monkeypatch.setattr(attestation, "_module_vector", lambda _root: (modules, []))
    monkeypatch.setattr(attestation, "_pth_vector", lambda _root: ([], []))
    monkeypatch.setattr(attestation, "_chain_binding", lambda _path: chain_binding)
    seed = attestation.build_runtime_launch_seed(
        expected_root=root,
        expected_revision=revision,
        supervisor_receipt_path=receipt,
        hot_env_path=hot_env,
        marker_path=marker,
        chain_spec_path=chain_spec,
        seed_doc_paths=[seed_doc],
    )
    return seed, {
        "root": root,
        "receipt": receipt,
        "hot_env": hot_env,
        "marker": marker,
        "chain_spec": chain_spec,
        "seed_doc": seed_doc,
        "wrapper": wrapper_dir / "arnold-watchdog",
    }


def test_release_seed_binds_full_runtime_and_seed_document_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, paths = _release_seed(tmp_path, monkeypatch)

    assert seed["ready"] is True
    assert seed["errors"] == []
    assert seed["expected_root"] == str(paths["root"])
    assert seed["loaded_modules"]
    assert seed["interpreter"]["executable"] == str(Path(sys.executable).resolve())
    assert seed["interpreter"]["direct_url"] == {}
    assert seed["supervisor_receipt"]["fingerprint"] == "supervisor-fingerprint"
    assert seed["hot_env"]["selectors"]["MEGAPLAN_RUNTIME_SRC"] == str(paths["root"])
    assert seed["wrappers"][0]["sha256"]
    assert seed["chain_runtime_binding"]["runtime_identity"]["import_root"] == str(
        paths["root"]
    )
    manifest_paths = {
        item["path"] for item in seed["seed_document_manifest"]["entries"]
    }
    assert str(paths["seed_doc"]) in manifest_paths
    assert (
        attestation.validate_runtime_launch_seed(seed, component="worker")["status"]
        == "ready"
    )


def test_complete_loaded_module_vector_rejects_mixed_and_late_modules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, _paths = _release_seed(tmp_path, monkeypatch)
    original = list(seed["loaded_modules"])
    monkeypatch.setattr(
        attestation,
        "_module_vector",
        lambda _root: (
            [
                *original,
                {
                    "module": "arnold_pipelines.late_import",
                    "path": "/other/arnold_pipelines/late_import.py",
                    "root": "",
                },
            ],
            ["mixed_module_root:arnold_pipelines.late_import"],
        ),
    )

    with pytest.raises(CliError, match="escaped the expected root"):
        attestation.validate_runtime_launch_seed(seed, component="worker")


def test_unowned_executable_pth_is_recorded_and_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site_dir = tmp_path / "site-packages"
    site_dir.mkdir()
    pth = site_dir / "unowned.pth"
    pth.write_text(
        "import sys; sys.path.insert(0, '/tmp/ambient')\n../runtime\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(attestation, "_active_site_dirs", lambda: [site_dir])
    monkeypatch.setattr(attestation, "_pth_owners", lambda _path: {})

    vector, errors = attestation._pth_vector(tmp_path / "runtime")

    assert vector[0]["lines"][0] == {
        "kind": "executable",
        "raw": "import sys; sys.path.insert(0, '/tmp/ambient')",
        "resolved": "",
    }
    assert errors == [f"unowned_executable_pth:{pth}"]


@pytest.mark.parametrize("drift_target", ["wrapper", "seed_doc", "hot_env"])
def test_release_seed_rejects_runtime_and_seed_input_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift_target: str,
) -> None:
    seed, paths = _release_seed(tmp_path, monkeypatch)
    paths[drift_target].write_text("changed\n", encoding="utf-8")

    with pytest.raises(CliError):
        attestation.validate_runtime_launch_seed(seed, component="worker")


def test_stale_process_attestation_is_rejected_after_restart_or_selector_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed, paths = _release_seed(tmp_path, monkeypatch)
    original = {
        "pid": 123,
        "start_ticks": "100",
        "executable": "/bin/bash",
        "executable_sha256": "c" * 64,
        "selectors": {"MEGAPLAN_RUNTIME_SRC": str(paths["root"])},
    }
    monkeypatch.setattr(attestation, "_proc_identity", lambda _pid: original)
    process_attestation = attestation.create_runtime_process_attestation(
        seed,
        component="watchdog",
        target_pid=123,
    )
    restarted = {**original, "start_ticks": "101"}
    monkeypatch.setattr(attestation, "_proc_identity", lambda _pid: restarted)

    with pytest.raises(CliError, match="stale or belongs to another process"):
        attestation.validate_runtime_process_attestation(
            seed,
            process_attestation,
            component="watchdog",
            target_pid=123,
        )


def test_real_module_scan_reports_an_import_outside_expected_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = types.ModuleType("arnold_pipelines.foreign_runtime")
    module.__file__ = "/tmp/foreign/arnold_pipelines/foreign_runtime.py"
    monkeypatch.setitem(sys.modules, module.__name__, module)

    _vector, errors = attestation._module_vector(Path(__file__).resolve().parents[2])

    assert "mixed_module_root:arnold_pipelines.foreign_runtime" in errors


def test_long_lived_entrypoints_validate_attestation_before_work() -> None:
    repo = Path(__file__).resolve().parents[2]
    wrappers = repo / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"
    library = (wrappers / "arnold-supervisor-runtime-lib").read_text(encoding="utf-8")
    watchdog = (wrappers / "arnold-watchdog").read_text(encoding="utf-8")
    supervise = (wrappers / "arnold-supervise").read_text(encoding="utf-8")
    resident_cli = (
        repo / "arnold_pipelines" / "megaplan" / "resident" / "cli.py"
    ).read_text(encoding="utf-8")
    resident_runtime = (
        repo / "arnold_pipelines" / "megaplan" / "resident" / "runtime.py"
    ).read_text(encoding="utf-8")

    assert "arnold_runtime_attestation_start" in library
    assert "verify-process" in library
    assert "arnold_runtime_attestation_check watchdog" in watchdog
    assert "arnold_supervisor_runtime_init supervisor" in supervise
    assert "arnold_runtime_attestation_check supervisor" in supervise
    assert 'require_configured_runtime_launch("resident", create=True)' in resident_cli
    assert 'require_configured_runtime_launch("resident")' in resident_runtime
