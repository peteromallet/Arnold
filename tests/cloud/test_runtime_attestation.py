from __future__ import annotations

import json
import importlib.metadata
import os
import shutil
import subprocess
import sys
import types
import venv
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
    monkeypatch.setattr(attestation, "_pth_vector", lambda _root: ([], []))
    monkeypatch.setattr(attestation, "_chain_binding", lambda _path: chain_binding)
    supervisor_modules = [
        {"module": "arnold", "path": str(root / "arnold" / "__init__.py"), "root": str(root)},
        {
            "module": "arnold_pipelines",
            "path": str(root / "arnold_pipelines" / "__init__.py"),
            "root": str(root),
        },
        {
            "module": "arnold_pipelines.megaplan",
            "path": str(root / "arnold_pipelines" / "megaplan" / "__init__.py"),
            "root": str(root),
        },
    ]
    supervisor_vector = {
        "source": str(root),
        "source_revision": revision,
        "source_fingerprint": "supervisor-fingerprint",
        "runtime": sys.prefix,
        "runtime_provenance": {"install_mode": "noneditable", "direct_url": {}},
        "loaded_modules": supervisor_modules,
        "interpreter": {},
        "site_pth": [],
        "errors": [],
        "ready": True,
    }
    supervisor_vector["content_sha256"] = attestation._canonical_sha256(
        supervisor_vector
    )
    monkeypatch.setattr(
        attestation,
        "_module_vector",
        lambda scan_root: (
            supervisor_modules
            if Path(scan_root).resolve(strict=False)
            == Path(sys.prefix).resolve(strict=False)
            else modules,
            [],
        ),
    )
    monkeypatch.setattr(
        attestation,
        "_supervisor_module_vector",
        lambda _root: (supervisor_modules, []),
    )
    monkeypatch.setattr(
        attestation,
        "_probe_supervisor_runtime",
        lambda _receipt: supervisor_vector,
    )
    monkeypatch.setattr(
        attestation,
        "supervisor_runtime_vector",
        lambda **_kwargs: supervisor_vector,
    )
    _write_json(
        receipt,
        {
            "fingerprint": "supervisor-fingerprint",
            "runtime": sys.prefix,
            "source": str(root),
            "source_revision": revision,
            "imports": {
                "arnold": supervisor_modules[0]["path"],
                "arnold_pipelines": supervisor_modules[1]["path"],
                "megaplan": supervisor_modules[2]["path"],
            },
        },
    )
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


def _venv_site(python: Path) -> Path:
    result = subprocess.check_output(
        [
            str(python),
            "-c",
            "import sysconfig; print(sysconfig.get_paths()['purelib'])",
        ],
        text=True,
    )
    return Path(result.strip())


def _install_test_runtime(
    runtime: Path,
    source: Path,
    *,
    editable: bool,
) -> Path:
    venv.EnvBuilder(with_pip=False).create(runtime)
    python = runtime / "bin" / "python3"
    site_dir = _venv_site(python)
    for dependency in (
        "yaml",
        "pydantic",
        "pydantic_core",
        "annotated_types",
        "typing_extensions",
        "typing_inspection",
        "ulid",
        "psutil",
    ):
        module_path = Path(__import__(dependency).__file__).resolve()
        if module_path.name == "__init__.py":
            shutil.copytree(module_path.parent, site_dir / dependency)
        else:
            shutil.copy2(module_path, site_dir / module_path.name)
        for distribution_name in importlib.metadata.packages_distributions().get(
            dependency, []
        ):
            distribution = importlib.metadata.distribution(distribution_name)
            metadata_dir = Path(distribution._path)  # type: ignore[attr-defined]
            destination = site_dir / metadata_dir.name
            if metadata_dir.is_dir() and not destination.exists():
                shutil.copytree(metadata_dir, destination)
    dist = site_dir / "arnold-0.0.dist-info"
    dist.mkdir()
    (dist / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: arnold\nVersion: 0.0\n",
        encoding="utf-8",
    )
    (dist / "direct_url.json").write_text(
        json.dumps(
            {
                "url": source.resolve().as_uri(),
                "dir_info": {"editable": True} if editable else {},
            }
        ),
        encoding="utf-8",
    )
    if editable:
        pth = site_dir / "arnold-editable.pth"
        pth.write_text(str(source.resolve()) + "\n", encoding="utf-8")
        (dist / "RECORD").write_text("arnold-editable.pth,,\n", encoding="utf-8")
    else:
        for package in ("arnold", "arnold_pipelines", "agentbox"):
            shutil.copytree(source / package, site_dir / package)
        (dist / "RECORD").write_text("", encoding="utf-8")
    return python


def test_real_editable_launch_and_noneditable_supervisor_vectors(
    tmp_path: Path,
) -> None:
    source = Path(__file__).resolve().parents[2]
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    launch_python = _install_test_runtime(
        tmp_path / "launch-venv",
        source,
        editable=True,
    )
    supervisor_runtime = tmp_path / "supervisor-venv"
    supervisor_python = _install_test_runtime(
        supervisor_runtime,
        source,
        editable=False,
    )
    receipt_path = tmp_path / "supervisor-receipt.json"
    import_program = (
        "import json,pathlib,arnold,arnold_pipelines,arnold_pipelines.megaplan as m;"
        "print(json.dumps({'arnold':str(pathlib.Path(arnold.__file__).resolve()),"
        "'arnold_pipelines':str(pathlib.Path(arnold_pipelines.__file__).resolve()),"
        "'megaplan':str(pathlib.Path(m.__file__).resolve())}))"
    )
    imports = json.loads(
        subprocess.check_output(
            [str(supervisor_python), "-P", "-c", import_program],
            text=True,
            cwd=tmp_path,
            env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
        )
    )
    _write_json(
        receipt_path,
        {
            "schema_version": "arnold-supervisor-runtime-receipt-v1",
            "fingerprint": "real-two-venv",
            "runtime": str(supervisor_runtime),
            "source": str(source),
            "source_revision": revision,
            "imports": imports,
            "status": "ready",
        },
    )
    runtime_library = (
        source
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "wrappers"
        / "arnold-supervisor-runtime-lib"
    )
    wrapper_check = subprocess.run(
        [
            "bash",
            "-c",
            (
                f"source {str(runtime_library)!r}; "
                f"arnold_supervisor_runtime_init test-component {str(source)!r}; "
                "printf 'isolated=%s\\n' \"$MEGAPLAN_SUPERVISOR_ISOLATED\""
            ),
        ],
        cwd=tmp_path,
        env={
            **{key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
            "MEGAPLAN_SUPERVISOR_PYTHON": str(supervisor_python),
            "MEGAPLAN_SUPERVISOR_RUNTIME_REQUIRED": "1",
            "MEGAPLAN_SUPERVISOR_RUNTIME_RECEIPT": str(receipt_path),
            "MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED": "0",
        },
        text=True,
        capture_output=True,
    )
    assert wrapper_check.returncode == 0, wrapper_check.stderr
    assert "isolated=1" in wrapper_check.stdout
    program = tmp_path / "build-and-validate.py"
    program.write_text(
        """
import json
import pathlib
import sys
from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.cloud.runtime_attestation import (
    build_runtime_launch_seed,
    validate_runtime_launch_seed,
)
from arnold_pipelines.megaplan.cloud.runtime_provenance import (
    normalized_runtime_identity,
    runtime_provenance,
)

source, revision, receipt, output, work = sys.argv[1:]
source = pathlib.Path(source)
work = pathlib.Path(work)
spec = work / "chain.yaml"
spec.write_text("milestones: []\\n")
identity = normalized_runtime_identity(
    runtime_provenance(expected_root=source, expected_revision=revision)
)
state = chain_spec.ChainState(
    metadata={"execution_binding": {"runtime_binding": {"current_identity": identity}}}
)
state_path = chain_spec._state_path_for(spec)
state_path.parent.mkdir(parents=True, exist_ok=True)
state_path.write_text(json.dumps(state.to_dict()))
marker = work / "marker.json"
marker.write_text(json.dumps({"runtime_binding": {"current_identity": identity}}))
hot = work / "hot.env"
hot.write_text("\\n".join([
    f"export MEGAPLAN_RUNTIME_SRC={source}",
    f"export MEGAPLAN_LAUNCH_RUNTIME_SRC={source}",
    f"export MEGAPLAN_SUPERVISOR_SOURCE={source}",
    f"export CLOUD_WATCHDOG_ARNOLD_SRC={source}",
    f"export MEGAPLAN_META_ARNOLD_SRC={source}",
    f"export MEGAPLAN_AUDIT_ARNOLD_SRC={source}",
]) + "\\n")
doc = work / "NORTHSTAR.md"
doc.write_text("# real two venv seed\\n")
seed = build_runtime_launch_seed(
    expected_root=source,
    expected_revision=revision,
    supervisor_receipt_path=pathlib.Path(receipt),
    hot_env_path=hot,
    marker_path=marker,
    chain_spec_path=spec,
    seed_doc_paths=[doc],
)
assert seed["ready"], seed["errors"]
assert validate_runtime_launch_seed(seed, component="worker")["status"] == "ready"
pathlib.Path(output).write_text(json.dumps(seed))
""",
        encoding="utf-8",
    )
    seed_path = tmp_path / "seed.json"
    clean_env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    subprocess.run(
        [
            str(launch_python),
            "-P",
            str(program),
            str(source),
            revision,
            str(receipt_path),
            str(seed_path),
            str(tmp_path),
        ],
        check=True,
        cwd=tmp_path,
        env=clean_env,
    )
    validate_program = (
        "import json,pathlib,sys;"
        "from arnold_pipelines.megaplan.cloud.runtime_attestation import "
        "validate_runtime_launch_seed;"
        "s=json.loads(pathlib.Path(sys.argv[1]).read_text());"
        "assert validate_runtime_launch_seed(s,component='supervisor')['status']=='ready'"
    )
    subprocess.run(
        [str(supervisor_python), "-P", "-c", validate_program, str(seed_path)],
        check=True,
        cwd=tmp_path,
        env=clean_env,
    )
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    assert seed["interpreter"]["venv"] == str(tmp_path / "launch-venv")
    assert seed["runtime_provenance"]["direct_url"]["dir_info"]["editable"] is True
    assert seed["supervisor_runtime"]["interpreter"]["venv"] == str(supervisor_runtime)
    assert (
        seed["supervisor_runtime"]["runtime_provenance"]["direct_url"]["dir_info"]
        == {}
    )


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
