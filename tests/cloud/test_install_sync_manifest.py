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
import shutil
import subprocess
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
    advance_generation,
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


# ── T74GENFIX: build must never move the content address it was addressed from


_UV = pytest.mark.skipif(shutil.which("uv") is None, reason="uv not on PATH")


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _directory_source_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    """(origin, clone, candidate worktree) in the REAL promote topology.

    The frozen spec carries a setuptools-backed ``directory`` source under
    ``vendor/`` (the shape that put ``banodoco-timeline-schema`` under the
    content address), so the digest covers EVERY file beneath it — exactly
    what an in-place PEP 517 build used to pollute.
    """
    origin = tmp_path / "origin"
    vendor = origin / "vendor" / "schema"
    (vendor / "pkgfile").mkdir(parents=True)
    (origin / "pyproject.toml").write_text(
        '[project]\n'
        'name = "fixture-root"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.10"\n'
        'dependencies = ["banodoco-fixture-schema"]\n'
        "\n"
        "[tool.uv.sources]\n"
        'banodoco-fixture-schema = { path = "vendor/schema" }\n'
        "\n"
        "[build-system]\n"
        'requires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n',
        encoding="utf-8",
    )
    (vendor / "pyproject.toml").write_text(
        "[project]\n"
        'name = "banodoco-fixture-schema"\n'
        'version = "0.0.1"\n'
        'requires-python = ">=3.10"\n'
        "dependencies = []\n"
        "\n"
        "[build-system]\n"
        'requires = ["setuptools>=68", "wheel"]\n'
        'build-backend = "setuptools.build_meta"\n'
        "\n"
        "[tool.setuptools]\n"
        'packages = ["pkgfile"]\n',
        encoding="utf-8",
    )
    (vendor / "pkgfile" / "__init__.py").write_text("X = 1\n", encoding="utf-8")
    _git(origin, "init", "-q")
    _git(origin, "config", "user.name", "Test")
    _git(origin, "config", "user.email", "test@example.invalid")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-qm", "fixture: directory-source frozen spec")
    lock = subprocess.run(
        ["uv", "lock"], cwd=str(origin), capture_output=True, text=True
    )
    assert lock.returncode == 0, lock.stderr
    assert 'directory = "vendor/schema"' in (origin / "uv.lock").read_text(
        encoding="utf-8"
    )
    _git(origin, "add", "-A")
    _git(origin, "commit", "-qm", "fixture: lock the directory source")
    # clone --no-local + linked worktree: same object store, separate
    # checkouts — the canary/runtime-create topology the refusal fired in.
    src = tmp_path / "src"
    subprocess.run(
        ["git", "clone", "-q", "--no-local", str(origin), str(src)], check=True
    )
    _git(src, "config", "user.name", "Test")
    _git(src, "config", "user.email", "test@example.invalid")
    cand = tmp_path / "cand"
    _git(src, "worktree", "add", "-q", "-b", "fixer/t74genfix", str(cand), "HEAD")
    return origin, src, cand


@_UV
def test_uv_build_never_dirties_the_attested_checkout(tmp_path: Path) -> None:
    """T74GENFIX regression: the uv strategy used to run ``uv sync`` IN the
    attested checkout; setuptools then wrote ``*.egg-info``/``build/`` into
    the directory source AFTER the spec digest was computed, moving the
    content address and refusing every later advance_generation of the
    SAME commit (T74RESUME6: proof 05b40a47… vs recompute 440afcff…).
    The build must leave the checkout byte-identical."""
    _, _, cand = _directory_source_repo(tmp_path)
    gen_root = tmp_path / "runtime-venvs"
    before = frozen_spec_sha256(cand)
    assert _git(cand, "status", "--porcelain") == ""
    proof = ensure_dependency_generation(cand, gen_root, build_strategy="uv")
    assert frozen_spec_sha256(cand) == before
    assert _git(cand, "status", "--porcelain") == ""
    assert proof["id"] == before
    assert verify_generation(generation_dir(gen_root, before))["ok"] is True


@_UV
def test_commit_then_advance_generation_survives_probe_commit(
    tmp_path: Path,
) -> None:
    """The exact T74RESUME6 mutate sequence, end to end: generation built
    and bound at the base commit, THEN the flow's own probe commit lands
    in the clone, THEN advance_generation must SUCCEED — the proof's
    content address still matches the runtime root because the build no
    longer moves it. The fail-closed binding check is exercised untouched.
    """
    _, src, cand = _directory_source_repo(tmp_path)
    gen_root = tmp_path / "runtime-venvs"
    base_head = _git(cand, "rev-parse", "HEAD")
    proof = ensure_dependency_generation(cand, gen_root, build_strategy="uv")
    payload = _manifest_payload(
        str(cand), spec_digest=proof["id"], generation_root=gen_root, proof=proof
    )
    payload["epic"]["expected_head"] = base_head
    payload["indirection"]["verified_head"] = base_head
    manifest = RuntimeManifest.from_dict(payload)

    # canary probe commit: scratch file in the CLONE (not the candidate)
    (src / "canary-probe.txt").write_text("canary probe\n", encoding="utf-8")
    _git(src, "add", "canary-probe.txt")
    _git(src, "commit", "-m", "canary: probe commit (scratch, not promoted code)")
    probe_sha = _git(src, "rev-parse", "HEAD")

    advanced = advance_generation(
        manifest,
        probe_sha,
        reason="canary advance_generation after probe commit",
        generations_root=gen_root,
    )
    assert advanced.generation == manifest.generation + 1
    assert advanced.epic["expected_head"] == probe_sha
    assert advanced.promotions[-1]["previous_commit"] == base_head
    assert advanced.epic["dependency_generation"]["id"] == proof["id"]


def test_advance_still_refuses_genuine_spec_drift(tmp_path: Path) -> None:
    """Fail-closed control: T74GENFIX removes the SPURIOUS digest drift
    (build pollution), never the binding check — a REAL frozen-spec change
    under the runtime root still refuses publication."""
    gen_root = tmp_path / "runtime-venvs"
    project = _frozen_spec_project(tmp_path, "drift")
    proof = ensure_dependency_generation(project, gen_root, build_strategy="pip")
    manifest = RuntimeManifest.from_dict(
        _manifest_payload(
            str(project), spec_digest=proof["id"], generation_root=gen_root, proof=proof
        )
    )
    (project / "pyproject.toml").write_text(
        FROZEN_SPEC["pyproject.toml"] + "# genuine spec drift\n",
        encoding="utf-8",
    )
    with pytest.raises(
        ManifestError,
        match=r"frozen_spec_sha256 '[0-9a-f]{64}' but the new commit's "
        r"frozen spec digest",
    ):
        advance_generation(
            manifest,
            "0" * 40,
            reason="must refuse: spec genuinely changed",
            generations_root=gen_root,
        )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
