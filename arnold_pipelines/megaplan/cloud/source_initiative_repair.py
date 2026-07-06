from __future__ import annotations

from pathlib import Path


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
