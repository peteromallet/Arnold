from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable, Sequence
import tomllib

from vibecomfy.registry import models_loader


BASELINE_MODEL_IDS = ("sd15_v1_5_pruned_emaonly_fp16",)
LTX_MODEL_PHASE = "ltx"
BASELINE_PYTHON_DEPS = ("glfw", "PyOpenGL")
BASELINE_PARKED_NODE_PACKS = ("ComfyUI-ResAdapter",)
LTX_NODE_PACKS = (
    "ComfyUI-LTXVideo",
    "ComfyUI-KJNodes",
    "ComfyUI-VideoHelperSuite",
    "rgthree-comfy",
)


@dataclass(frozen=True)
class ParkedNodePack:
    name: str
    source: Path
    target: Path
    changed: bool


@dataclass(frozen=True)
class InstalledNodePack:
    name: str
    path: Path
    url: str
    commit: str
    changed: bool


@dataclass(frozen=True)
class LinkedCustomNode:
    source: Path
    target: Path
    changed: bool


def stage_baseline_models(
    *,
    models_root: Path,
    registry: Path | None = None,
    dry_run: bool = False,
) -> None:
    configure_workspace_cache(models_root=models_root)
    entries = models_loader.load_registry(registry)
    selected = models_loader._filter_entries(entries, ids=BASELINE_MODEL_IDS, select_phase=None)
    if dry_run:
        models_loader._print_dry_run(selected, models_root=models_root)
        return
    models_loader.stage_many(selected, models_root=models_root, ids=BASELINE_MODEL_IDS)


def stage_ltx_models(
    *,
    models_root: Path,
    registry: Path | None = None,
    dry_run: bool = False,
) -> None:
    configure_workspace_cache(models_root=models_root)
    entries = models_loader.load_registry(registry)
    selected = models_loader._filter_entries(entries, ids=None, select_phase=LTX_MODEL_PHASE)
    if dry_run:
        models_loader._print_dry_run(selected, models_root=models_root)
        return
    models_loader.stage_many(selected, models_root=models_root)


def configure_workspace_cache(*, models_root: Path) -> Path:
    cache_root = models_root.resolve().parent / "cache"
    hf_home = cache_root / "huggingface"
    os.environ.setdefault("HF_HOME", str(hf_home))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(hf_home / "hub"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(hf_home / "transformers"))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_root / "xdg"))
    hf_home.mkdir(parents=True, exist_ok=True)
    return cache_root


def park_node_packs(
    *,
    custom_nodes: Path,
    disabled_custom_nodes: Path,
    node_packs: Sequence[str] = BASELINE_PARKED_NODE_PACKS,
    dry_run: bool = False,
) -> list[ParkedNodePack]:
    disabled_custom_nodes.mkdir(parents=True, exist_ok=True)
    results: list[ParkedNodePack] = []
    for name in node_packs:
        source = custom_nodes / name
        target = disabled_custom_nodes / name
        if not source.exists():
            results.append(ParkedNodePack(name=name, source=source, target=target, changed=False))
            continue
        if target.exists():
            raise FileExistsError(f"refusing to overwrite existing disabled node pack: {target}")
        if not dry_run:
            source.rename(target)
        results.append(ParkedNodePack(name=name, source=source, target=target, changed=True))
    return results


def unpark_node_packs(
    *,
    custom_nodes: Path,
    disabled_custom_nodes: Path,
    node_packs: Sequence[str] = BASELINE_PARKED_NODE_PACKS,
    dry_run: bool = False,
) -> list[ParkedNodePack]:
    custom_nodes.mkdir(parents=True, exist_ok=True)
    results: list[ParkedNodePack] = []
    for name in node_packs:
        source = disabled_custom_nodes / name
        target = custom_nodes / name
        if not source.exists():
            results.append(ParkedNodePack(name=name, source=source, target=target, changed=False))
            continue
        if target.exists():
            raise FileExistsError(f"refusing to overwrite existing node pack: {target}")
        if not dry_run:
            source.rename(target)
        results.append(ParkedNodePack(name=name, source=source, target=target, changed=True))
    return results


def install_python_deps(
    packages: Iterable[str] = BASELINE_PYTHON_DEPS,
    *,
    python: str = sys.executable,
    dry_run: bool = False,
) -> None:
    packages = tuple(packages)
    if not packages:
        return
    cmd = [python, "-m", "pip", "install", *packages]
    if dry_run:
        print(" ".join(cmd))
        return
    subprocess.check_call(cmd)


def install_node_packs(
    *,
    custom_nodes: Path,
    lockfile: Path,
    node_packs: Sequence[str] = LTX_NODE_PACKS,
    python: str = sys.executable,
    install_requirements: bool = True,
    dry_run: bool = False,
) -> list[InstalledNodePack]:
    lock = _load_node_lock(lockfile)
    custom_nodes.mkdir(parents=True, exist_ok=True)
    installed: list[InstalledNodePack] = []
    for name in node_packs:
        raw = lock.get(name)
        if not raw:
            raise KeyError(f"{name} is not present in {lockfile}")
        url = _required_lock_str(raw, "url", name)
        commit = _required_lock_str(raw, "git_commit_sha", name)
        target = custom_nodes / name
        changed = False
        if not target.exists():
            _run(["git", "clone", url, str(target)], dry_run=dry_run)
            changed = True
        if target.exists() or dry_run:
            _run(["git", "-C", str(target), "fetch", "--depth", "1", "origin", commit], dry_run=dry_run, check=False)
            _run(["git", "-C", str(target), "checkout", "--force", commit], dry_run=dry_run)
        if install_requirements:
            requirements = target / "requirements.txt"
            if requirements.exists() or dry_run:
                _run([python, "-m", "pip", "install", "--no-deps", "-r", str(requirements)], dry_run=dry_run, check=False)
        installed.append(InstalledNodePack(name=name, path=target, url=url, commit=commit, changed=changed))
    return installed


def link_vibecomfy_custom_node(
    *,
    custom_nodes: Path,
    package_root: Path | None = None,
    link_name: str = "vibecomfy",
    dry_run: bool = False,
) -> LinkedCustomNode:
    root = package_root or Path(__file__).resolve().parents[1]
    source = root / "vibecomfy" / "comfy_nodes"
    if not source.exists():
        raise FileNotFoundError(f"VibeComfy custom node source not found: {source}")
    custom_nodes.mkdir(parents=True, exist_ok=True)
    target = custom_nodes / link_name
    if target.is_symlink() and target.resolve() == source.resolve():
        return LinkedCustomNode(source=source, target=target, changed=False)
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing custom node path: {target}")
    if not dry_run:
        target.symlink_to(source, target_is_directory=True)
    return LinkedCustomNode(source=source, target=target, changed=True)


def _load_node_lock(lockfile: Path) -> dict[str, dict[str, object]]:
    with lockfile.open("rb") as handle:
        data = tomllib.load(handle)
    nodepacks = data.get("nodepacks")
    if not isinstance(nodepacks, dict):
        raise ValueError(f"{lockfile}: missing [nodepacks] table")
    return {str(key): value for key, value in nodepacks.items() if isinstance(value, dict)}


def _required_lock_str(raw: dict[str, object], key: str, name: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name}: lockfile field {key!r} must be a non-empty string")
    return value


def _run(cmd: Sequence[str], *, dry_run: bool, check: bool = True) -> subprocess.CompletedProcess[str] | None:
    if dry_run:
        print(" ".join(cmd))
        return None
    return subprocess.run(cmd, check=check, text=True)
