"""Focused tests for the disposable canary builder (T7.4a deliverable 1).

The builder is exercised against a REAL candidate tree (git archive of this
repo at HEAD) whose frozen dependency spec is overridden to a zero-dependency
pair so the generation build stays hermetic/offline — proving:

- every redirected path (env list from the reject receipt) lives under ONE
  fresh root inside the system temp dir (path audit);
- containment REFUSES: ambient protected ARNOLD_* vars, any redirected var
  resolving outside the root, non-fresh roots, non-temp roots;
- the promote-adjacent flow (runtime-create -> append_promotion ->
  advance_generation) mutates ONLY the disposable manifest/pointer/store;
- the protected-state assertion uses the honest wording and covers the named
  live roots without a durable delta.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.canary_sandbox import (
    CanaryError,
    REDIRECTED_ENV_VARS,
    build,
    containment_violations,
    sandbox_env_spec,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _git(cwd: Path | None, *args: str) -> str:
    proc = subprocess.run(
        ["git", *(("-C", str(cwd)) if cwd else ()), *args],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return proc.stdout.strip()


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    """REAL candidate tree + zero-dep frozen spec: hermetic canary source."""

    repo = tmp_path / "candidate-src"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _git(repo, "config", "user.name", "Canary Tests")
    _git(repo, "config", "user.email", "canary@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    archive = subprocess.run(
        ["git", "archive", "HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        check=True,
    )
    subprocess.run(["tar", "-x", "-C", str(repo)], input=archive.stdout, check=True)
    # Keep only the runtime package surface: the canary needs the wrappers
    # and modules, not docs/evidence — keeps every sandbox lightweight.
    keep = {"arnold_pipelines", "pyproject.toml", "uv.lock", "README.md"}
    for entry in repo.iterdir():
        if entry.name not in keep and entry.name != ".git":
            subprocess.run(["rm", "-rf", str(entry)], check=True)
    (repo / "pyproject.toml").write_text(
        "[project]\n"
        'name = "sandbox-arnold"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.9"\n'
        "dependencies = []\n",
        encoding="utf-8",
    )
    (repo / "uv.lock").write_text(
        "version = 1\n"
        'requires-python = ">=3.9"\n'
        "\n"
        "[[package]]\n"
        'name = "sandbox-arnold"\n'
        'version = "0.1.0"\n'
        'source = { editable = "." }\n',
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "canary fixture: real candidate tree, zero-dep spec")
    return repo


def do_build(
    tmp_path: Path,
    source_repo: Path,
    *,
    root: Path | None = None,
    allow_non_tmp: bool = False,
) -> tuple[Path, dict]:
    root = root if root is not None else tmp_path / "canary-root"
    report = build(
        source_repo=source_repo,
        root=root,
        slug="canary",
        base_ref="HEAD",
        generation_build_strategy=None,
        allow_non_tmp=allow_non_tmp,
    )
    return root, report


# ── path audit: everything rooted under one fresh tmp dir ───────────────────


@pytest.mark.integration
def test_build_roots_everything_under_one_fresh_tmp_dir(
    tmp_path: Path, source_repo: Path
) -> None:
    root, report = do_build(tmp_path, source_repo)

    assert root.is_dir()
    assert report["path_audit"]["ok"] is True, report["path_audit"]

    # Every redirected var points inside the root AND exists on disk.
    env_spec = json.loads((root / "sandbox-env.json").read_text())
    assert set(env_spec) == set(REDIRECTED_ENV_VARS)
    for var, value in env_spec.items():
        if var == "PYTHONDONTWRITEBYTECODE":
            continue  # flag, not a filesystem path (asserted below)
        resolved = Path(value).resolve(strict=False)
        assert str(resolved).startswith(str(root.resolve())), (
            f"{var}={value} escaped the sandbox root"
        )
    assert env_spec["PYTHONDONTWRITEBYTECODE"] == "1"

    # The named layout exists under the single root.
    for rel in (
        "home",
        "tmp",
        "xdg/cache",
        "xdg/config",
        "xdg/data",
        "xdg/state",
        "cache/pip",
        "cache/uv",
        "base/runtime-candidates/canary",
        "base/runtime-venvs",
        "markers",
        "manifests",
        "journals",
        "chain",
        "remote.git",
        "src",
    ):
        assert (root / rel).exists(), f"missing sandbox element: {rel}"

    # Disposable remote: created locally, origin reference severed, and the
    # source clone's origin IS that remote — never the real origin.
    assert _git(root / "remote.git", "remote", "-v") == ""
    origin = _git(root / "src", "config", "--get", "remote.origin.url")
    assert Path(origin).resolve() == (root / "remote.git").resolve()

    # The flow ran against the DISPOSABLE manifest only.
    slug_manifest = json.loads((root / "manifests" / "canary.json").read_text())
    pointer = json.loads((root / "manifests" / "runtime-manifest.json").read_text())
    assert slug_manifest["generation"] == 2
    assert pointer["generation"] == 2
    assert slug_manifest["epic"]["runtime_root"] == str(
        root / "base" / "runtime-candidates" / "canary"
    )
    retention = sorted(
        (root / "manifests").glob("runtime-manifest.json.previous-*.json")
    )
    assert len(retention) == 1
    # Journals live in the sandbox, populated by the flow.
    creation_lines = (root / "manifests" / "creation-journal.jsonl").read_text().splitlines()
    promotion_lines = (root / "manifests" / "promotion-journal.jsonl").read_text().splitlines()
    assert len(creation_lines) == 1
    assert len(promotion_lines) == 1


@pytest.mark.integration
def test_build_asserts_no_durable_protected_state_delta_with_honest_wording(
    tmp_path: Path, source_repo: Path
) -> None:
    _, report = do_build(tmp_path, source_repo)

    delta = report["protected_state"]
    # EXACT honest wording — never "zero writes".
    assert delta["assertion"] == "no durable protected-state delta in named paths"
    assert delta["ok"] is True, delta["changed_roots"]
    assert delta["changed_roots"] == []
    assert any("zero writes" in claim for claim in delta["does_not_prove"])
    named = set(delta["roots"])
    assert {
        "live-manifest-dir",
        "live-markers",
        "live-generations",
        "source-repo-git-metadata",
        "source-repo-tracked-files",
    } <= named
    # The real source repo was read (--no-local clone) but never mutated —
    # this catches the hardlink/auto-gc cascade class of writes too.
    assert delta["roots"]["source-repo-git-metadata"]["durable_delta"] is False
    assert delta["roots"]["source-repo-tracked-files"]["durable_delta"] is False


# ── containment refusals ────────────────────────────────────────────────────


def test_containment_unit_any_redirected_var_outside_root_is_listed(
    tmp_path: Path,
) -> None:
    spec = sandbox_env_spec(tmp_path / "root")
    spec["ARNOLD_BASE_DIR"] = "/workspace"
    spec["TMPDIR"] = str(tmp_path / "elsewhere")
    violations = containment_violations(spec, tmp_path / "root")
    joined = "\n".join(violations)
    assert "ARNOLD_BASE_DIR" in joined and "/workspace" in joined
    assert "TMPDIR" in joined
    # A clean spec has no violations.
    clean = containment_violations(sandbox_env_spec(tmp_path / "root"), tmp_path / "root")
    assert clean == []


def test_containment_symlink_escape_is_caught(tmp_path: Path) -> None:
    """A redirected path that RESOLVES outside the root is a violation."""

    root = tmp_path / "r"
    (root / "tmp").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "tmp" / "escape").symlink_to(outside)
    spec = sandbox_env_spec(root)
    spec["TMPDIR"] = str(root / "tmp" / "escape")
    violations = containment_violations(spec, root)
    assert any(v.startswith("TMPDIR:") for v in violations), violations


def test_build_refuses_ambient_protected_arnold_env(
    tmp_path: Path, source_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARNOLD_BASE_DIR", "/workspace")
    monkeypatch.setenv(
        "ARNOLD_RUNTIME_MANIFEST", "/workspace/.megaplan/runtime-manifest.json"
    )
    with pytest.raises(CanaryError) as excinfo:
        do_build(tmp_path, source_repo)
    assert excinfo.value.code == "ambient_arnold_env"
    assert "ARNOLD_BASE_DIR" in excinfo.value.message
    # Refusal precedes any sandbox work.
    assert not (tmp_path / "canary-root").exists()


def test_build_refuses_non_fresh_root(tmp_path: Path, source_repo: Path) -> None:
    dirty = tmp_path / "dirty-root"
    dirty.mkdir()
    (dirty / "prior-state.txt").write_text("not empty\n", encoding="utf-8")
    with pytest.raises(CanaryError) as excinfo:
        do_build(tmp_path, source_repo, root=dirty)
    assert excinfo.value.code == "root_not_fresh"


def test_build_refuses_root_outside_system_tmp_dir(
    tmp_path: Path, source_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_tmp = tmp_path / "fake-tmp"
    fake_tmp.mkdir()
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.canary_sandbox.tempfile.gettempdir",
        lambda: str(fake_tmp),
    )
    with pytest.raises(CanaryError) as excinfo:
        do_build(tmp_path, source_repo, root=tmp_path / "elsewhere-root")
    assert excinfo.value.code == "root_not_disposable"
    # Escape hatch permits it explicitly.
    root, _ = do_build(
        tmp_path, source_repo, root=tmp_path / "allowed-root", allow_non_tmp=True
    )
    assert (root / "sandbox-env.json").exists()
