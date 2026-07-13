from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.cloud.cli import (
    _megaplan_refresh_command,
    _refresh_then_chain_start_command,
    _sync_launch_head_to_editable_install_branch,
)
from arnold_pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
)


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if check:
        assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc


def _commit(repo: Path, path: str, content: str, message: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def test_cloud_refresh_uses_editible_install_branch() -> None:
    command = _megaplan_refresh_command()

    assert "REF=editible-install" in command
    assert 'git -C "$SRC" fetch origin "$REF"' in command
    assert 'git -C "$SRC" checkout "$REF"' in command
    assert 'refusing editable install refresh: tracked changes in source checkout' in command
    assert 'merge-base --is-ancestor HEAD "origin/$REF"' in command
    assert 'source checkout has local commits not contained in origin/$REF; attempting push' in command
    assert 'git -C "$SRC" push origin "$REF"' in command
    assert 'refusing editable install refresh: $SRC has unpushed local commits' in command
    assert 'git -C "$SRC" pull --ff-only origin "$REF"' in command


def test_cloud_refresh_honors_explicit_megaplan_ref() -> None:
    spec = CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/project.git"),
        agents={},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(
            ref="main",
            repo="https://github.com/example/Arnold.git",
        ),
        resources=ResourcesSpec(),
        secrets=[],
    )

    command = _megaplan_refresh_command(spec)

    assert "REF=main" in command
    assert "REF=editible-install" not in command


def test_cloud_refresh_can_prepare_clean_runtime_mirror() -> None:
    command = _megaplan_refresh_command(
        runtime_src_path="/workspace/project/.megaplan/runtime/editable-engine"
    )

    assert "RUNTIME_SRC=/workspace/project/.megaplan/runtime/editable-engine" in command
    assert 'source checkout dirty; using clean runtime mirror at $RUNTIME_SRC' in command
    assert 'git clone --shared --no-checkout "$SRC" "$RUNTIME_SRC"' in command
    assert 'git -C "$RUNTIME_SRC" remote set-url origin "$MIRROR_REMOTE"' in command
    assert 'git -C "$RUNTIME_SRC" checkout --detach "origin/$REF"' in command
    assert 'export MEGAPLAN_RUNTIME_SRC="$RUNTIME_SRC"' in command
    assert 'pip install -e "$MEGAPLAN_RUNTIME_SRC"' in command
    assert "arnold_pipelines.megaplan.cloud.runtime_provenance" in command
    assert '--expected-root "$MEGAPLAN_RUNTIME_SRC"' in command
    assert '--expected-revision "$RUNTIME_REVISION"' in command


def test_dirty_source_runtime_mirror_executes_configured_upstream_ref(
    tmp_path: Path,
) -> None:
    origin = tmp_path / "origin.git"
    publisher = tmp_path / "publisher"
    source = tmp_path / "source"
    runtime = tmp_path / "runtime"
    fake_bin = tmp_path / "bin"

    _git(tmp_path, "init", "--bare", str(origin))
    _git(tmp_path, "clone", str(origin), str(publisher))
    _git(publisher, "config", "user.email", "test@example.com")
    _git(publisher, "config", "user.name", "Test User")
    old_head = _commit(publisher, "engine.txt", "old\n", "old engine")
    _git(publisher, "branch", "-M", "main")
    _git(publisher, "push", "-u", "origin", "main")
    _git(tmp_path, "clone", "--branch", "main", str(origin), str(source))

    new_head = _commit(publisher, "engine.txt", "new\n", "new engine")
    _git(publisher, "push", "origin", "main")
    (source / "engine.txt").write_text("cloud work in progress\n", encoding="utf-8")

    fake_bin.mkdir()
    for executable in ("pip", "python"):
        shim = fake_bin / executable
        shim.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        shim.chmod(0o755)

    spec = CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/project.git"),
        agents={},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(
            ref="main",
            repo=str(origin),
            src_path=str(source),
        ),
        resources=ResourcesSpec(),
        secrets=[],
    )
    command = _megaplan_refresh_command(spec, runtime_src_path=str(runtime))
    result = subprocess.run(
        ["bash", "-c", command],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}"},
        timeout=60,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert _git(source, "rev-parse", "HEAD").stdout.strip() == old_head
    assert (source / "engine.txt").read_text(encoding="utf-8") == "cloud work in progress\n"
    assert _git(runtime, "rev-parse", "HEAD").stdout.strip() == new_head
    assert (runtime / "engine.txt").read_text(encoding="utf-8") == "new\n"


def test_cloud_refresh_force_clean_resets_only_editable_source() -> None:
    command = _megaplan_refresh_command(force_clean_editable_install=True)

    assert 'SRC=/workspace/arnold' in command
    assert 'force-clean enabled: resetting and cleaning $SRC' in command
    assert 'git -C "$SRC" reset --hard "origin/$REF"' in command
    assert 'git -C "$SRC" clean -fd' in command


def test_cloud_chain_start_requires_successful_editable_refresh() -> None:
    command = _refresh_then_chain_start_command(
        "/workspace/project/.megaplan/initiatives/example/chain.yaml",
        project_dir="/workspace/project",
        log_relative=".megaplan/cloud-chain.log",
    )

    assert "} >> .megaplan/cloud-chain.log 2>&1 && " in command
    assert "} >> .megaplan/cloud-chain.log 2>&1 || true" not in command
    assert 'RUNTIME_SRC=/workspace/project/.megaplan/runtime/editable-engine' in command
    assert 'ENGINE_DIR="${MEGAPLAN_RUNTIME_SRC:-}"' in command
    assert 'PYTHONPATH="$ENGINE_DIR:${PYTHONPATH:-}"' in command


def test_cloud_chain_start_can_force_clean_editable_refresh() -> None:
    command = _refresh_then_chain_start_command(
        "/workspace/project/.megaplan/initiatives/example/chain.yaml",
        project_dir="/workspace/project",
        log_relative=".megaplan/cloud-chain.log",
        force_clean_editable_install=True,
    )

    assert 'git -C "$SRC" reset --hard "origin/$REF"' in command
    assert "python -P -m arnold_pipelines.megaplan chain start" in command


def test_cloud_chain_sync_rejects_divergent_editible_install(
    tmp_path: Path,
) -> None:
    origin = tmp_path / "origin.git"
    repo = tmp_path / "repo"

    _git(tmp_path, "init", "--bare", str(origin))
    _git(tmp_path, "clone", str(origin), str(repo))
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")

    _commit(repo, "README.md", "base\n", "base")
    _git(repo, "branch", "-M", "main")
    _git(repo, "push", "-u", "origin", "main")

    _git(repo, "checkout", "-b", "editible-install")
    editable_only = _commit(repo, "editable.txt", "keep\n", "editable branch work")
    _git(repo, "push", "-u", "origin", "editible-install")

    _git(repo, "checkout", "-b", "feature", "main")
    _commit(repo, "feature.txt", "ship\n", "feature work")

    with pytest.raises(CliError) as exc_info:
        _sync_launch_head_to_editable_install_branch(repo)

    assert exc_info.value.code == "editable_install_sync_diverged"
    assert exc_info.value.extra["editable_head"] == editable_only
    assert exc_info.value.extra["editable_only_commits"] == 1
    assert exc_info.value.extra["launch_only_commits"] == 1


def test_cloud_chain_sync_fast_forwards_editible_install(
    tmp_path: Path,
) -> None:
    origin = tmp_path / "origin.git"
    repo = tmp_path / "repo"
    verify = tmp_path / "verify"

    _git(tmp_path, "init", "--bare", str(origin))
    _git(tmp_path, "clone", str(origin), str(repo))
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")

    _commit(repo, "README.md", "base\n", "base")
    _git(repo, "branch", "-M", "main")
    _git(repo, "push", "-u", "origin", "main")

    _git(repo, "checkout", "-b", "editible-install")
    editable_head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "push", "-u", "origin", "editible-install")

    _git(repo, "checkout", "-b", "feature", "editible-install")
    launch_head = _commit(repo, "feature.txt", "ship\n", "feature work")

    result = _sync_launch_head_to_editable_install_branch(repo)

    assert result["status"] == "pushed"
    assert result["branch"] == "editible-install"
    assert result["launch_head"] == launch_head
    assert result["editable_head_before"] == editable_head

    _git(tmp_path, "clone", "--branch", "editible-install", str(origin), str(verify))
    assert (verify / "feature.txt").read_text(encoding="utf-8") == "ship\n"
    assert (
        _git(verify, "merge-base", "--is-ancestor", launch_head, "HEAD").returncode
        == 0
    )


def test_cloud_chain_sync_ignores_only_explicit_generated_paths(tmp_path: Path) -> None:
    origin = tmp_path / "origin.git"
    repo = tmp_path / "repo"

    _git(tmp_path, "init", "--bare", str(origin))
    _git(tmp_path, "clone", str(origin), str(repo))
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")

    _commit(repo, "README.md", "base\n", "base")
    _git(repo, "branch", "-M", "main")
    _git(repo, "push", "-u", "origin", "main")
    _git(repo, "checkout", "-b", "editible-install")
    _git(repo, "push", "-u", "origin", "editible-install")
    _git(repo, "checkout", "-b", "feature", "editible-install")

    generated = repo / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    generated.parent.mkdir(parents=True)
    generated.write_text("milestones: []\n", encoding="utf-8")

    result = _sync_launch_head_to_editable_install_branch(
        repo,
        ignore_dirty_paths=[generated],
    )

    assert result["status"] == "already_contains"


def test_cloud_chain_sync_still_rejects_other_dirty_paths(tmp_path: Path) -> None:
    origin = tmp_path / "origin.git"
    repo = tmp_path / "repo"

    _git(tmp_path, "init", "--bare", str(origin))
    _git(tmp_path, "clone", str(origin), str(repo))
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")

    _commit(repo, "README.md", "base\n", "base")
    _git(repo, "branch", "-M", "main")
    _git(repo, "push", "-u", "origin", "main")
    _git(repo, "checkout", "-b", "editible-install")
    _git(repo, "push", "-u", "origin", "editible-install")
    _git(repo, "checkout", "-b", "feature", "editible-install")

    generated = repo / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    generated.parent.mkdir(parents=True)
    generated.write_text("milestones: []\n", encoding="utf-8")
    (repo / "README.md").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(CliError) as exc_info:
        _sync_launch_head_to_editable_install_branch(
            repo,
            ignore_dirty_paths=[generated],
        )

    assert exc_info.value.code == "editable_install_sync_dirty"
    assert "README.md" in "\n".join(exc_info.value.extra["dirty"])
