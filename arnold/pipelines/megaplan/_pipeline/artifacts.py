"""Versioned-artifact helpers — one consistent layout for every Step.

Solves the discrepancy that doc-critique uses
``critique_versions/critique_v<n>.json``, judges uses
``judges/<name>/verdict.json``, planning uses ``plan_v<n>.md``,
etc — each Step picking its own scheme. With the helpers here, any
Step can write a versioned artifact via one call:

    path = next_version_path(ctx, kind="plan", extension="md")
    path.write_text(body)
    return StepResult(outputs={"plan": path}, ...)

Layout: ``<plan_dir>/<kind>/v<n>.<ext>`` where ``<n>`` is the next
unused integer in that directory. The auto-increment happens by
scanning existing ``v*.<ext>`` files.

Older code paths that pick custom layouts keep working — these
helpers are opt-in conveniences, not enforced.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from arnold.pipelines.megaplan._pipeline.types import StepContext


_VERSION_PATTERN = re.compile(r"^v(\d+)\.([a-z0-9]+)$")


def artifact_dir(ctx: StepContext, kind: str) -> Path:
    """Return ``<plan_dir>/<kind>/``, creating parents if needed."""
    out = Path(ctx.plan_dir) / kind
    out.mkdir(parents=True, exist_ok=True)
    return out


def latest_version(ctx: StepContext, kind: str, extension: str) -> int:
    """Return the highest existing version integer for ``<kind>/v<n>.<ext>``.

    Returns 0 when no versions exist yet.
    """
    directory = artifact_dir(ctx, kind)
    highest = 0
    for path in directory.glob(f"v*.{extension}"):
        m = _VERSION_PATTERN.match(path.name)
        if m and m.group(2) == extension:
            highest = max(highest, int(m.group(1)))
    return highest


def next_version_path(ctx: StepContext, kind: str, extension: str = "md") -> Path:
    """Return ``<plan_dir>/<kind>/v<latest+1>.<ext>`` — a fresh, unused path.

    Caller is responsible for writing the content. The path's parent
    directory is created if absent.
    """

    n = latest_version(ctx, kind, extension) + 1
    return artifact_dir(ctx, kind) / f"v{n}.{extension}"


def versioned_artifacts(ctx: StepContext, kind: str, extension: str) -> Iterator[Path]:
    """Yield existing versioned artifacts in ascending version order."""

    directory = Path(ctx.plan_dir) / kind
    if not directory.exists():
        return
    items: list[tuple[int, Path]] = []
    for path in directory.glob(f"v*.{extension}"):
        m = _VERSION_PATTERN.match(path.name)
        if m and m.group(2) == extension:
            items.append((int(m.group(1)), path))
    for _, path in sorted(items):
        yield path


def latest_artifact_path(ctx: StepContext, kind: str, extension: str) -> Path | None:
    """Return the highest-version artifact path, or None if none exist."""

    paths = list(versioned_artifacts(ctx, kind, extension))
    return paths[-1] if paths else None
