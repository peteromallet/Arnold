"""GENROOT-FIX: default-config promotion-path acceptance tests.

DEEP check-in #4 P0: the watchdog promotion transaction created generations
under ``ARNOLD_GENERATIONS_ROOT`` (default ``/workspace/.megaplan/generations``)
while ``advance_generation``'s trusted-root containment check resolved the
store from ``ARNOLD_REFERENCE_RUNTIME_VENVS_DIR`` (default
``/workspace/runtime-venvs``).  Under DEFAULT configuration the two roots
differ, so verification refused every legitimately built runtime — fail-closed
but operationally broken.

These tests simulate the REAL promote flows (the ``runtime_manifest.main``
CLI action and the actual python transaction extracted from the
``arnold-watchdog`` wrapper) with DEFAULT configuration — no per-surface
store overrides, only the wrappers' shared ``ARNOLD_BASE_DIR`` pointed into a
disposable tmp tree — and require a legitimately built runtime to promote.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.install_sync import (
    ensure_dependency_generation,
    generation_dir,
)
from arnold_pipelines.megaplan.cloud.runtime_manifest import (
    MANIFEST_SCHEMA_VERSION,
    RuntimeManifest,
    load_manifest,
    main,
    write_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = (
    REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers" / "arnold-watchdog"
)


# Every historical per-caller spelling of the generations-store root.  A
# default-config sandbox must have NONE of these set.
STORE_ENV_VARS = (
    "ARNOLD_GENERATIONS_ROOT",
    "ARNOLD_RUNTIME_VENVS_DIR",
    "ARNOLD_REFERENCE_RUNTIME_VENVS_DIR",
)


def _sandbox_default_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    """Default configuration on a disposable root.

    No per-surface store override exists; ONLY the wrappers' shared
    ``ARNOLD_BASE_DIR`` points into the tmp tree, so every caller must agree
    on the derived default ``$ARNOLD_BASE_DIR/runtime-venvs``.
    """
    for var in STORE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    base_dir = tmp_path / "base"
    (base_dir / ".megaplan").mkdir(parents=True)
    monkeypatch.setenv("ARNOLD_BASE_DIR", str(base_dir))
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(base_dir / ".megaplan" / "runtime-manifest.json"))
    monkeypatch.setenv("ARNOLD_GENERATION_BUILD_STRATEGY", "pip")
    return base_dir, base_dir / "runtime-venvs"


def _runtime_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """A real frozen-spec runtime checkout with two commits.

    The candidate commit changes only the README, so the frozen dependency
    spec (and therefore the content address) is IDENTICAL across the
    promotion — the dominant engine-sync case: code moves, deps do not.
    """
    root = tmp_path / "src"
    root.mkdir()

    def git(*args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return proc.stdout.strip()

    git("init", "-q")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    (root / "README.md").write_text("generation 0\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "promotion-default-config"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "generation 0")
    head0 = git("rev-parse", "HEAD")
    (root / "README.md").write_text("generation 1 candidate\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "generation 1 candidate")
    head1 = git("rev-parse", "HEAD")
    return root, head0, head1


def _bound_manifest(repo: Path, head0: str, proof: dict) -> RuntimeManifest:
    """Schema-valid manifest pinned to *head0*, carrying the REAL proof."""
    payload: dict = {
        "runtime_id": "runtime-promo-default",
        "schema": MANIFEST_SCHEMA_VERSION,
        "generation": 4,
        "epic_id": "epic-promo-default",
        "state": "active",
        "owner": "superfixer",
        "base": {
            "ref": "refs/heads/base/editable-install",
            "commit": "87a912beb",
            "editable_install_path": "",
            "venv_path": str(Path(str(proof["interpreter_path"])).parent.parent),
        },
        "epic": {
            "branch": "fixer/epic-promo-default",
            "worktree_path": str(repo),
            "venv_path": str(proof["interpreter_path"]),
            "runtime_root": str(repo),
            "expected_head": head0,
            "repair_bin": str(repo / ".venv" / "bin" / "arnold-babysitter"),
            "deps_lockfile": str(repo / "uv.lock"),
            "dependency_generation": proof,
        },
        "indirection": {
            "host_path": str(repo),
            "container_path": "/workspace/promo-default",
            "mount_table": [],
            "execution_namespace": "promo-default-ns",
            "verified_head": head0,
            "last_verified_at": "2026-08-07T00:00:00+00:00",
            "attestation": {
                "module_file": str(repo / "pyproject.toml"),
                "module_digest": "d41d8cd98f00b204e9800998ecf8427e",
                "mount_id": "0:42",
            },
        },
        "policy": {
            "policy_sha": "policy-sha-1",
            "model_policy_sha": "model-sha-1",
            "sync_policy": "push-on-promote",
        },
        "promotions": [],
        "timestamps": {
            "created": "2026-08-07T00:00:00+00:00",
            "updated": "2026-08-07T00:00:00+00:00",
            "closed": "",
        },
        "gc_policy": "closed-only",
        "commands": ["megaplan chain"],
    }
    return RuntimeManifest.from_dict(payload)


def test_cli_advance_generation_accepts_built_runtime_under_default_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CLI promote flow (runtime_manifest.main advance_generation) must
    verify against the SAME configured store the runtime was built in — with
    DEFAULT configuration and no explicit root threaded by the caller."""
    _sandbox_default_config(tmp_path, monkeypatch)
    repo, head0, head1 = _runtime_repo(tmp_path)
    gen_root = Path(os.environ["ARNOLD_BASE_DIR"]) / "runtime-venvs"
    proof = ensure_dependency_generation(str(repo), str(gen_root))
    manifest = _bound_manifest(repo, head0, proof)
    slug_path = tmp_path / "manifests" / "runtime-promo-default.json"
    write_manifest(manifest, slug_path)
    rc = main(
        [
            "advance_generation",
            str(slug_path),
            head1,
            "--reason",
            "engine sync promotion (default config)",
        ]
    )
    assert rc == 0, "legitimately built runtime refused under default config"
    advanced = load_manifest(slug_path)
    assert advanced.generation == manifest.generation + 1
    assert advanced.epic["expected_head"] == head1
    # the pointer switch happened too (slug != pointer -> both written)
    switched = load_manifest(Path(os.environ["ARNOLD_RUNTIME_MANIFEST"]))
    assert switched.epic["expected_head"] == head1
    # the generation really lives in the ONE derived default store
    assert generation_dir(gen_root, str(proof["id"])).is_dir()


def _watchdog_promotion_script() -> str:
    """Extract the ACTUAL promotion python transaction from the wrapper."""
    text = WRAPPER.read_text(encoding="utf-8")
    anchor = 'python3 - "$ARNOLD_RUNTIME_MANIFEST" "$candidate_full"'
    start = text.index(anchor)
    heredoc = "<<'PY'"
    begin = text.index("\n", text.index(heredoc, start)) + 1
    end = text.index("\nPY\n", begin)
    return text[begin:end]


def test_watchdog_promotion_transaction_accepts_built_runtime_under_default_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The REAL watchdog promotion transaction, run verbatim as a subprocess
    with DEFAULT configuration, must promote a legitimately built runtime:
    creation (ensure_dependency_generation) and trusted-root containment
    verification (advance_generation) must resolve the SAME store."""
    _sandbox_default_config(tmp_path, monkeypatch)
    repo, head0, head1 = _runtime_repo(tmp_path)
    gen_root = Path(os.environ["ARNOLD_BASE_DIR"]) / "runtime-venvs"
    proof = ensure_dependency_generation(str(repo), str(gen_root))
    manifest = _bound_manifest(repo, head0, proof)

    pointer = Path(os.environ["ARNOLD_RUNTIME_MANIFEST"])
    write_manifest(manifest, pointer)  # the active pointer IS the manifest

    script = tmp_path / "watchdog_promotion.py"
    script.write_text(_watchdog_promotion_script(), encoding="utf-8")

    env = {k: v for k, v in os.environ.items() if k not in STORE_ENV_VARS}
    env["PYTHONPATH"] = str(REPO_ROOT)
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            str(pointer),
            head1,
            str(repo),
            head0[:7],
            head1[:7],
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    assert proc.returncode == 0, (
        f"watchdog promotion failed under default config\n"
        f"{proc.stdout}\n{proc.stderr}"
    )
    advanced = load_manifest(pointer)
    assert advanced.generation == manifest.generation + 1
    assert advanced.epic["expected_head"] == head1
    assert advanced.indirection["verified_head"] == head1
    assert generation_dir(gen_root, str(proof["id"])).is_dir()


def test_configured_generations_root_single_source_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ONE resolution chain: creation-store name wins, legacy reference alias
    honored, otherwise the wrappers' derived ``$BASE_DIR/runtime-venvs``."""
    from arnold_pipelines.megaplan.cloud.install_sync import (
        configured_generations_root,
    )

    for var in STORE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ARNOLD_BASE_DIR", str(tmp_path / "base"))
    assert configured_generations_root() == tmp_path / "base" / "runtime-venvs"
    monkeypatch.setenv(
        "ARNOLD_REFERENCE_RUNTIME_VENVS_DIR", str(tmp_path / "ref-store")
    )
    assert configured_generations_root() == tmp_path / "ref-store"
    monkeypatch.setenv("ARNOLD_RUNTIME_VENVS_DIR", str(tmp_path / "creation-store"))
    assert configured_generations_root() == tmp_path / "creation-store"
