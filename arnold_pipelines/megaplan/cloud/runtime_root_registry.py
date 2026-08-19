"""Exclusive mutable-runtime-root ownership (occurrence 0a0ce24c3510).

The shared-runtime wedge: two epics' manifests may declare the same
``epic.runtime_root`` (e.g. astrid-first gen 79 and megaplan-maintenance
gen 123 both pinned ``/workspace/runtime-candidates/arnold-4a830c6ac9a0``).
The launch-seed attestation reads the candidate worktree HEAD at every worker
dispatch (runtime_attestation.py:_git_revision), so whichever epic moves that
checkout kills the other's in-flight drive with
``runtime root HEAD does not match the manifest pin`` (observed: astrid-first
drive2 02:58:33Z, drive3 03:13:17Z).

The engine's designed topology is one worktree per epic (arnold-runtime-create:
``git worktree add runtime-candidates/<slug>``). This module enforces that
design at the root-changing seam: a manifest cutover into a runtime root
already claimed by ANOTHER ACTIVE epic is refused fail-closed
(``runtime_root_ownership_conflict``). Existing shared bindings (legacy state)
are reported as inventory warnings and remain recoverable: the owner may
cutover to a dedicated root, after which the shared root is freed.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Mapping

log = logging.getLogger(__name__)

OWNERSHIP_SCHEMA = "arnold.megaplan.runtime_root_ownership.v1"


def _load_manifest_epic(manifest_path: Path) -> dict[str, Any] | None:
    """Return the epic block of a sibling manifest, or None when unreadable."""
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    epic = data.get("epic")
    return epic if isinstance(epic, dict) else None


def runtime_root_ownership(
    manifests_dir: Path,
    *,
    exclude_manifest: Path | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Map canonical runtime_root -> list of owning manifests.

    Legacy inventory detection: every ``*.json`` sibling manifest's
    ``epic.runtime_root``/``epic.branch``/``state`` is recorded. Roots claimed
    by more than one ACTIVE epic are the legacy shared-root state this guard
    exists to prevent going forward.
    """
    manifests_dir = Path(manifests_dir).expanduser().resolve(strict=False)
    if not manifests_dir.is_dir():
        return {}
    owners: dict[str, list[dict[str, Any]]] = {}
    for manifest_path in sorted(manifests_dir.glob("*.json")):
        if manifest_path.name.endswith((".lock", ".previous")):
            continue
        if exclude_manifest is not None and manifest_path.resolve() == Path(
            exclude_manifest
        ).resolve():
            continue
        epic = _load_manifest_epic(manifest_path)
        if epic is None:
            continue
        root = epic.get("runtime_root")
        branch = epic.get("branch")
        if not isinstance(root, str) or not root.strip():
            continue
        canonical = str(Path(root).expanduser().resolve(strict=False))
        owners.setdefault(canonical, []).append(
            {
                "manifest": manifest_path.name,
                "epic_branch": branch if isinstance(branch, str) else "",
                "state": epic.get("state"),
                "generation": epic.get("generation"),
            }
        )
    return owners


def assert_runtime_root_claimable(
    to_runtime_root: str,
    epic_branch: str,
    manifests_dir: Path,
    *,
    exclude_manifest: Path | None = None,
) -> dict[str, Any]:
    """Refuse a cutover into a root claimed by another ACTIVE epic.

    Returns the ownership map on success (callers may persist it as
    inventory evidence). Raises a typed :class:`CliError` with code
    ``runtime_root_ownership_conflict`` when the target root is claimed by an
    active manifest with a DIFFERENT epic.branch.
    """
    from arnold_pipelines.megaplan.types import CliError

    canonical_target = str(Path(to_runtime_root).expanduser().resolve(strict=False))
    owners = runtime_root_ownership(
        manifests_dir, exclude_manifest=exclude_manifest
    )
    conflicts: list[dict[str, Any]] = []
    for owner in owners.get(canonical_target, []):
        owner_branch = str(owner.get("epic_branch") or "")
        if owner_branch == epic_branch:
            # Same epic rebinding onto its own root — always allowed.
            continue
        if str(owner.get("state") or "") not in ("active", ""):
            # Inactive/completed epics do not hold the mutable root.
            continue
        conflicts.append(owner)
    if conflicts:
        raise CliError(
            "runtime_root_ownership_conflict",
            "runtime root "
            f"{to_runtime_root} is already owned by another active epic "
            f"({', '.join(str(c.get('manifest')) for c in conflicts)}); "
            "use a dedicated per-epic worktree "
            "(`git worktree add runtime-candidates/<slug>`) and cut over to it. "
            "The shared-root wedge (occurrence 0a0ce24c3510) kills worker "
            "dispatch on the shared checkout's HEAD drift.",
        )
    return owners