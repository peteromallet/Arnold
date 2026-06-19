from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from vibecomfy.registry import models_loader


BASELINE_MODEL_IDS = ("sd15_v1_5_pruned_emaonly_fp16",)
BASELINE_PYTHON_DEPS = ("glfw", "PyOpenGL")
BASELINE_PARKED_NODE_PACKS = ("ComfyUI-ResAdapter",)


@dataclass(frozen=True)
class ParkedNodePack:
    name: str
    source: Path
    target: Path
    changed: bool


def stage_baseline_models(
    *,
    models_root: Path,
    registry: Path | None = None,
    dry_run: bool = False,
) -> None:
    entries = models_loader.load_registry(registry)
    selected = models_loader._filter_entries(entries, ids=BASELINE_MODEL_IDS, select_phase=None)
    if dry_run:
        models_loader._print_dry_run(selected, models_root=models_root)
        return
    models_loader.stage_many(selected, models_root=models_root, ids=BASELINE_MODEL_IDS)


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
