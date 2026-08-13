"""T-0301: the content-addressed dependency generation bound into runtime
manifests — ONE immutable venv per frozen-spec digest, SHARED across every
runtime that resolves to the same spec, with no shared mutable source.

The legacy manifest-driven editable-install sync (``manifest_driven_sync``)
is retired; these tests cover the successor contract: the manifest binds
``epic.dependency_generation`` (id = frozen-spec digest, interpreter =
``<generation>/bin/python``, venv_digest of the built venv), and two
runtimes sharing the spec share the venv WITHOUT sharing mutable source.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.cloud.install_sync import (
    GenerationError,
    ensure_dependency_generation,
    frozen_spec_sha256,
    generation_dir,
    generation_interpreter,
    verify_generation,
)
from arnold_pipelines.megaplan.cloud.runtime_manifest import (
    MANIFEST_SCHEMA_VERSION,
    ManifestError,
    RuntimeManifest,
    dependency_generation_proof,
    load_manifest,
    write_manifest,
)

FROZEN_SPEC = {
    "pyproject.toml": (
        '[project]\nname = "demo"\nversion = "0.1.0"\n'
        'requires-python = ">=3.9"\ndependencies = []\n'
    ),
    "uv.lock": (
        'version = 1\nrequires-python = ">=3.9"\n'
        "\n[[package]]\nname = \"demo\"\nversion = \"0.1.0\"\n"
        'source = { editable = "." }\n'
    ),
}


def _frozen_spec_project(tmp_path: Path, name: str) -> Path:
    project = tmp_path / name
    project.mkdir(parents=True, exist_ok=True)
    for filename, content in FROZEN_SPEC.items():
        (project / filename).write_text(content, encoding="utf-8")
    return project


def _manifest_payload(
    runtime_root: str,
    *,
    spec_digest: str,
    generation_root: Path,
    proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A schema-valid runtime manifest binding the dependency generation.
    *proof* (the REAL built proof when given) is used verbatim; otherwise a
    structurally valid placeholder proof is emitted."""
    gen_dir = generation_dir(generation_root, spec_digest)
    bound_proof = proof or {
        "id": spec_digest,
        "frozen_spec_sha256": spec_digest,
        "interpreter_path": str(generation_interpreter(gen_dir)),
        "venv_digest": "b" * 64,
        "created": "2026-08-12T00:00:00Z",
    }
    return {
        "runtime_id": f"runtime-{Path(runtime_root).name}",
        "schema": MANIFEST_SCHEMA_VERSION,
        "generation": 1,
        "epic_id": Path(runtime_root).name,
        "state": "active",
        "owner": "test",
        "base": {
            "ref": "refs/heads/main",
            "commit": "0" * 40,
            "editable_install_path": "",
            "venv_path": str(gen_dir),
        },
        "epic": {
            "branch": "fixer/demo-20260812",
            "worktree_path": runtime_root,
            "venv_path": str(gen_dir),
            "runtime_root": runtime_root,
            "expected_head": "a" * 40,
            "repair_bin": f"{runtime_root}/arnold_pipelines/megaplan/cloud/wrappers/arnold-babysitter",
            "deps_lockfile": f"{runtime_root}/uv.lock",
            "dependency_generation": bound_proof,
        },
        "indirection": {
            "host_path": runtime_root,
            "container_path": "/workspace/demo",
            "mount_table": [],
            "execution_namespace": "demo-ns",
            "verified_head": "a" * 40,
            "last_verified_at": "2026-08-12T00:00:00Z",
            "attestation": {
                "module_file": f"{runtime_root}/arnold_pipelines/__init__.py",
                "module_digest": "0" * 64,
                "mount_id": "0:0",
            },
        },
        "policy": {
            "policy_sha": "0" * 64,
            "model_policy_sha": "0" * 64,
            "sync_policy": "disabled",
        },
        "promotions": [],
        "timestamps": {
            "created": "2026-08-12T00:00:00Z",
            "updated": "2026-08-12T00:00:00Z",
            "closed": "",
        },
        "gc_policy": "closed-only",
        "commands": [],
    }


def test_two_runtimes_share_one_generation_without_shared_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-0301 acceptance: two runtimes with the same frozen spec resolve to
    ONE immutable generation venv while their source trees stay distinct —
    the venv is shared, the mutable source is not."""
    monkeypatch.setenv("ARNOLD_GENERATION_BUILD_STRATEGY", "pip")
    gen_root = tmp_path / "runtime-venvs"
    spec_a = _frozen_spec_project(tmp_path, "runtime-a")
    spec_b = _frozen_spec_project(tmp_path, "runtime-b")
    # identical spec content -> identical digest -> shared generation
    assert frozen_spec_sha256(spec_a) == frozen_spec_sha256(spec_b)

    proof_a = ensure_dependency_generation(spec_a, gen_root)
    proof_b = ensure_dependency_generation(spec_b, gen_root)
    assert proof_a == proof_b  # SAME immutable generation proof
    gen_dir = generation_dir(gen_root, proof_a["id"])
    assert generation_interpreter(gen_dir).is_file()

    manifest_a = RuntimeManifest.from_dict(
        _manifest_payload(str(spec_a), spec_digest=proof_a["id"], generation_root=gen_root)
    )
    manifest_b = RuntimeManifest.from_dict(
        _manifest_payload(str(spec_b), spec_digest=proof_b["id"], generation_root=gen_root)
    )
    # distinct source trees...
    assert manifest_a.epic["runtime_root"] != manifest_b.epic["runtime_root"]
    assert manifest_a.epic["worktree_path"] != manifest_b.epic["worktree_path"]
    # ...but the SAME shared venv (content-addressed by spec digest)
    assert manifest_a.epic["venv_path"] == manifest_b.epic["venv_path"] == str(gen_dir)
    assert (
        manifest_a.epic["dependency_generation"]
        == manifest_b.epic["dependency_generation"]
    )
    assert dependency_generation_proof(manifest_a) is not None
    assert dependency_generation_proof(manifest_b) is not None


def test_manifest_binds_the_on_disk_generation_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The manifest's proof round-trips through load/write and agrees with
    the on-disk generation it names."""
    monkeypatch.setenv("ARNOLD_GENERATION_BUILD_STRATEGY", "pip")
    gen_root = tmp_path / "runtime-venvs"
    project = _frozen_spec_project(tmp_path, "runtime-demo")
    proof = ensure_dependency_generation(project, gen_root)
    manifest_path = tmp_path / "manifests" / "runtime-demo.json"
    write_manifest(
        RuntimeManifest.from_dict(
            _manifest_payload(
                str(project),
                spec_digest=proof["id"],
                generation_root=gen_root,
                proof=proof,
            )
        ),
        manifest_path,
    )
    loaded = load_manifest(manifest_path)
    assert loaded.epic["dependency_generation"] == proof
    # the bound generation verifies on disk (proof id == dir name, interpreter
    # exists, venv digest matches)
    verdict = verify_generation(
        generation_dir(gen_root, proof["id"]), deep=True
    )
    assert verdict["ok"] is True, verdict["reasons"]


def test_corrupt_bound_generation_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A manifest-bound generation that is present but corrupt is never
    silently rebuilt or reused: ensure_dependency_generation refuses."""
    monkeypatch.setenv("ARNOLD_GENERATION_BUILD_STRATEGY", "pip")
    gen_root = tmp_path / "runtime-venvs"
    project = _frozen_spec_project(tmp_path, "runtime-corrupt")
    proof = ensure_dependency_generation(project, gen_root)
    gen_dir = generation_dir(gen_root, proof["id"])
    (gen_dir / "pyvenv.cfg").write_text("home = /tampered\n", encoding="utf-8")
    with pytest.raises(GenerationError, match="failed verification"):
        ensure_dependency_generation(project, gen_root)


def test_malformed_manifest_proof_is_schema_invalid() -> None:
    payload = _manifest_payload(
        "/workspace/runtime-demo",
        spec_digest="a" * 64,
        generation_root=Path("/tmp/venvs"),
    )
    payload["epic"]["dependency_generation"]["venv_digest"] = "not-hex"
    with pytest.raises(ManifestError, match="dependency_generation"):
        RuntimeManifest.from_dict(payload)


def test_manifest_without_proof_is_legacy_loadable() -> None:
    payload = _manifest_payload(
        "/workspace/runtime-legacy",
        spec_digest="a" * 64,
        generation_root=Path("/tmp/venvs"),
    )
    del payload["epic"]["dependency_generation"]
    manifest = RuntimeManifest.from_dict(payload)
    assert dependency_generation_proof(manifest) is None
    assert manifest.epic.get("dependency_generation") is None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
