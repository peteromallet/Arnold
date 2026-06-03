"""Neutral versioned-artifact helpers for the Arnold pipeline boundary.

Every Step that writes artifacts uses the same layout::

    <artifact_root>/<stage>/<label>/v<n>.<suffix>

where ``<n>`` is an auto-incremented integer.  The helpers below
provide the mechanics — path construction, version scanning, and
atomic writes — without any opinion about what the artifacts mean.

The Megaplan ``plan_dir`` concept is NOT referenced here; neutral
Steps use ``ctx.artifact_root``.  A bridge adapter
(:func:`_artifact_root_as_plan_dir`) exists for Megaplan callers that
still need a ``plan_dir``-compatible path.

Boundary discipline
-------------------

No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from arnold.pipeline.types import StepContext

_VERSION_RE = re.compile(r"^v(\d+)\.([a-z0-9]+)$")


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def artifact_dir(ctx: StepContext, stage: str, label: str) -> Path:
    """Return ``<artifact_root>/<stage>/<label>/``, creating parents.

    Uses *ctx.artifact_root* — the neutral root — instead of any
    opinionated ``plan_dir`` concept.
    """
    out = Path(ctx.artifact_root) / stage / label
    out.mkdir(parents=True, exist_ok=True)
    return out


def artifact_path(
    ctx: StepContext, stage: str, label: str, version: int, suffix: str
) -> Path:
    """Return ``<artifact_root>/<stage>/<label>/v<version>.<suffix>``.

    Does NOT create the file — callers own writing.  The parent
    directory is created if absent.
    """
    return artifact_dir(ctx, stage, label) / f"v{version}.{suffix}"


def next_version(ctx: StepContext, stage: str, label: str, suffix: str) -> int:
    """Return the next unused version integer for *stage*/*label*/*suffix*.

    Scans ``<artifact_root>/<stage>/<label>/v*.<suffix>`` and returns
    ``max(existing) + 1`` (or ``1`` when no versions exist yet).
    """
    directory = Path(ctx.artifact_root) / stage / label
    if not directory.is_dir():
        return 1
    highest = 0
    for path in directory.glob(f"v*.{suffix}"):
        m = _VERSION_RE.match(path.name)
        if m and m.group(2) == suffix:
            highest = max(highest, int(m.group(1)))
    return highest + 1


def latest_artifact(ctx: StepContext, stage: str, label: str, suffix: str) -> Path | None:
    """Return the highest-version artifact path, or ``None`` if none exist.

    Uses *ctx.artifact_root* as the base directory.
    """
    directory = Path(ctx.artifact_root) / stage / label
    if not directory.is_dir():
        return None
    candidates: list[tuple[int, Path]] = []
    for path in directory.glob(f"v*.{suffix}"):
        m = _VERSION_RE.match(path.name)
        if m and m.group(2) == suffix:
            candidates.append((int(m.group(1)), path))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def write_versioned(
    ctx: StepContext,
    stage: str,
    label: str,
    content: str,
    suffix: str,
    *,
    version: int | None = None,
) -> Path:
    """Write *content* to the next versioned artifact path atomically.

    If *version* is ``None``, :func:`next_version` is called to
    auto-increment.  The write uses a ``.tmp`` sibling + ``os.replace``
    for atomicity.

    Returns the final path written.
    """
    v = version if version is not None else next_version(ctx, stage, label, suffix)
    dest = artifact_path(ctx, stage, label, v, suffix)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, dest)
    return dest


# ---------------------------------------------------------------------------
# Megaplan bridge adapter
# ---------------------------------------------------------------------------
# M3a compatibility bridge; delete in M7.
#
# Megaplan callers pass a ``plan_dir`` and expect the legacy
# ``megaplan._pipeline.types.StepContext``.  This adapter extracts
# ``artifact_root`` from the neutral Arnold context so bridge code
# can construct the Megaplan-specific context shape without the
# Arnold module importing megaplan.


def _artifact_root_as_plan_dir(ctx: StepContext) -> str:
    """Return ``ctx.artifact_root`` as a string for Megaplan bridge callers.

    Megaplan code that needs a ``plan_dir`` can call this adapter and
    pass the result as the ``plan_dir`` argument to the legacy
    ``StepContext`` constructor.  Example::

        from megaplan._pipeline.types import StepContext as MegaplanCtx

        plan_dir = _artifact_root_as_plan_dir(arnold_ctx)
        mega_ctx = MegaplanCtx(plan_dir=Path(plan_dir), ...)

    This adapter is deliberately minimal and mechanical — it performs
    NO semantic mapping, only field-name translation.
    """
    return ctx.artifact_root
