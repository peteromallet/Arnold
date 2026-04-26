from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, Sequence
from urllib.parse import urlparse

from vibecomfy.node_packs import CustomNodePack, KNOWN_NODE_PACKS, resolve_node_packs, unresolved_class_types
from vibecomfy.node_packs_lockfile import LockEntry, upsert_lockfile_entry
from vibecomfy.workflow import VibeWorkflow


InstallStatus = Literal["installed", "refreshed", "skipped_dirty", "failed"]


class Runner(Protocol):
    def __call__(
        self,
        args: Sequence[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        ...


@dataclass(frozen=True)
class InstallResult:
    name: str
    status: InstallStatus
    git_commit_sha: str | None
    error: str | None


def install_pack(
    *,
    name: str | None = None,
    repo: str | None = None,
    force: bool = False,
    install_root: Path = Path("custom_nodes"),
    lockfile_path: Path = Path("custom_nodes.lock"),
    runner: Runner = subprocess.run,
) -> InstallResult:
    if name is None and repo is None:
        raise ValueError("install_pack requires either name or repo")

    pack = _pack_by_name(name) if name is not None else None
    if pack is None and repo is None:
        raise ValueError(f"unknown custom node pack {name!r}; pass repo to install an uncatalogued pack")

    pack_name = name or _pack_name_from_repo(repo or "")
    if not pack_name:
        raise ValueError(f"could not infer custom node pack name from repo {repo!r}")
    repo_url = repo or (pack.repo if pack is not None else None)
    if repo_url is None:
        raise ValueError(f"missing repo URL for custom node pack {pack_name!r}")

    install_dir = install_root / pack_name
    if install_dir.exists():
        dirty = _git_porcelain(install_dir, runner)
        if dirty is None:
            return InstallResult(pack_name, "failed", None, f"failed to inspect git status for {install_dir}")
        if dirty and not force:
            return InstallResult(pack_name, "skipped_dirty", None, f"{install_dir} has uncommitted changes; pass --force to refresh the lockfile pin")
        sha = _git_head(install_dir, runner)
        if sha is None:
            return InstallResult(pack_name, "failed", None, f"failed to read git HEAD for {install_dir}")
        upsert_lockfile_entry(LockEntry(name=pack_name, git_commit_sha=sha, url=repo_url), lockfile_path)
        return InstallResult(pack_name, "refreshed", sha, None)

    try:
        runner(["git", "clone", repo_url, str(install_dir)], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        return InstallResult(pack_name, "failed", None, _error_text(exc) or f"failed to clone {repo_url}")

    pip_packages = pack.pip_packages if pack is not None else ()
    if pip_packages:
        try:
            runner(
                [sys.executable, "-m", "pip", "install", *pip_packages],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            return InstallResult(pack_name, "failed", None, _error_text(exc) or "failed to install pip packages")

    sha = _git_head(install_dir, runner)
    if sha is None:
        return InstallResult(pack_name, "failed", None, f"failed to read git HEAD for {install_dir}")
    upsert_lockfile_entry(LockEntry(name=pack_name, git_commit_sha=sha, url=repo_url), lockfile_path)
    return InstallResult(pack_name, "installed", sha, None)


def missing_packs_for_workflow(workflow: VibeWorkflow) -> tuple[list[CustomNodePack], list[str]]:
    missing_classes = missing_class_types_for_workflow(workflow)
    return resolve_node_packs(missing_classes), unresolved_class_types(missing_classes)


def missing_class_types_for_workflow(workflow: VibeWorkflow) -> set[str]:
    class_types = {node.class_type for node in workflow.nodes.values()}
    return class_types - _known_schema_classes()


def _pack_by_name(name: str | None) -> CustomNodePack | None:
    if name is None:
        return None
    for pack in KNOWN_NODE_PACKS:
        if pack.name == name:
            return pack
    return None


def _pack_name_from_repo(repo: str) -> str:
    parsed = urlparse(repo)
    path = parsed.path or repo
    name = Path(path.rstrip("/")).name
    if name.endswith(".git"):
        name = name[:-4]
    return name


def _git_porcelain(pack_dir: Path, runner: Runner) -> str | None:
    try:
        result = runner(
            ["git", "-C", str(pack_dir), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout


def _git_head(pack_dir: Path, runner: Runner) -> str | None:
    try:
        result = runner(
            ["git", "-C", str(pack_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _known_schema_classes(path: Path = Path("node_index.json")) -> set[str]:
    if not path.exists():
        return set()
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(rows, list):
        return set()
    return {str(row.get("class_type")) for row in rows if isinstance(row, dict) and row.get("class_type")}


def _error_text(exc: BaseException) -> str | None:
    stderr = getattr(exc, "stderr", None)
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")
    if isinstance(stderr, str) and stderr.strip():
        return stderr.strip()
    stdout = getattr(exc, "stdout", None)
    if isinstance(stdout, bytes):
        stdout = stdout.decode(errors="replace")
    if isinstance(stdout, str) and stdout.strip():
        return stdout.strip()
    return str(exc) or None
