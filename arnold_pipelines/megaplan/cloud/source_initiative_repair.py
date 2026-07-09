from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepairResult:
    repaired: bool
    reason: str
    details: dict[str, object]

    def as_json(self) -> dict[str, object]:
        return {"repaired": self.repaired, "reason": self.reason, "details": self.details}


def source_initiative_restore_available(
    *,
    workspace: Path,
    remote_spec: Path,
    arnold_src: Path,
) -> bool:
    """True when the editable Arnold source still contains the missing initiative spec.

    This lets stale-marker recovery distinguish between:
    - genuinely stale workspace/spec markers that should be retired, and
    - ephemeral target workspaces whose initiative can be re-materialized from
      the editable Arnold source tree.
    """

    try:
        workspace = workspace.resolve()
    except OSError:
        workspace = workspace
    try:
        remote_spec = remote_spec.resolve(strict=False)
    except OSError:
        pass
    try:
        arnold_src = arnold_src.resolve()
    except OSError:
        arnold_src = arnold_src

    if not str(remote_spec).endswith(".yaml"):
        return False

    try:
        relative = remote_spec.relative_to(workspace)
    except ValueError:
        return False

    candidate = arnold_src / relative
    return candidate.exists()


def _canonical_initiative_dir(source_spec: Path) -> Path | None:
    source_root = source_spec.parent
    name = source_root.name
    if not name.endswith(".chain"):
        return None
    return source_root.with_name(name.removesuffix(".chain"))


def _copy_tree_contents(source_root: Path, target_root: Path) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    for item in source_root.iterdir():
        destination = target_root / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


def _overlay_canonical_completion_artifacts(
    *,
    workspace: Path,
    source_spec: Path,
    target_root: Path,
) -> list[str]:
    canonical_dir = _canonical_initiative_dir(source_spec)
    if canonical_dir is None or not canonical_dir.exists():
        return []

    overlay_files: list[str] = []
    for item in sorted(canonical_dir.iterdir(), key=lambda entry: entry.name):
        destination = target_root / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
            for copied in sorted(destination.rglob("*")):
                if copied.is_file():
                    overlay_files.append(copied.relative_to(workspace).as_posix())
        else:
            shutil.copy2(item, destination)
            overlay_files.append(destination.relative_to(workspace).as_posix())
    return overlay_files


def repair_source_initiative(
    *,
    workspace: Path,
    remote_spec: Path,
    arnold_src: Path,
) -> RepairResult:
    if not source_initiative_restore_available(
        workspace=workspace,
        remote_spec=remote_spec,
        arnold_src=arnold_src,
    ):
        return RepairResult(False, "source_initiative_unavailable", {})

    try:
        relative = remote_spec.resolve(strict=False).relative_to(workspace.resolve())
    except (OSError, ValueError):
        return RepairResult(False, "source_initiative_unavailable", {})

    source_spec = arnold_src.resolve() / relative
    source_root = source_spec.parent
    target_root = remote_spec.parent
    _copy_tree_contents(source_root, target_root)
    overlay_files = _overlay_canonical_completion_artifacts(
        workspace=workspace,
        source_spec=source_spec,
        target_root=target_root,
    )
    return RepairResult(
        True,
        "source_initiative_restored",
        {
            "workspace": str(workspace),
            "remote_spec": str(remote_spec),
            "source_spec": str(source_spec),
            "overlay_files": overlay_files,
        },
    )
