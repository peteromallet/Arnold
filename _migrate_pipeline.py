#!/usr/bin/env python3
"""Helper script to migrate a legacy pipeline.py to canonical."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def migrate_pipeline(pkg: str) -> None:
    src = Path(f"arnold/pipelines/megaplan/pipelines/{pkg}/pipeline.py")
    dst = Path(f"arnold_pipelines/megaplan/pipelines/{pkg}/pipeline.py")
    if not src.exists():
        raise FileNotFoundError(src)

    text = src.read_text(encoding="utf-8")

    # Remove module-level docstring compatibility references
    text = re.sub(
        r'"""Compatibility mirror for ``arnold\.pipelines\.megaplan\.pipelines\..*?``\."""',
        f'"""Canonical native-backed implementation for the ``{pkg}`` pipeline."""',
        text,
        count=1,
    )

    # _pipeline.types -> split StepContext/StepResult
    text = text.replace(
        "from arnold.pipelines.megaplan._pipeline.types import StepContext, StepResult",
        "from arnold.pipeline import StepContext\nfrom arnold_pipelines.megaplan.step_types import StepResult",
    )
    text = text.replace(
        "from arnold.pipelines.megaplan._pipeline.types import Pipeline, StepResult",
        "from arnold.pipeline import Pipeline as ArnoldPipeline\nfrom arnold_pipelines.megaplan.step_types import StepResult",
    )
    text = text.replace(
        "from arnold.pipelines.megaplan._pipeline.types import (\n    StepContext,\n    StepResult,\n)",
        "from arnold.pipeline import StepContext\nfrom arnold_pipelines.megaplan.step_types import StepResult",
    )
    text = text.replace(
        "from arnold.pipelines.megaplan._pipeline.types import (\n    Pipeline,\n    StepResult,\n)",
        "from arnold.pipeline import Pipeline as ArnoldPipeline\nfrom arnold_pipelines.megaplan.step_types import StepResult",
    )

    # _pipeline.types -> only StepContext
    text = text.replace(
        "from arnold.pipelines.megaplan._pipeline.types import StepContext",
        "from arnold.pipeline import StepContext",
    )

    # _pipeline.patterns -> canonical pattern_dynamic (we will create this)
    text = text.replace(
        "from arnold.pipelines.megaplan._pipeline.patterns import dynamic_fanout",
        "from arnold_pipelines.megaplan.pattern_dynamic import dynamic_fanout",
    )

    # generic arnold.pipelines.megaplan. -> arnold_pipelines.megaplan.
    text = text.replace(
        "from arnold.pipelines.megaplan.",
        "from arnold_pipelines.megaplan.",
    )

    dst.write_text(text, encoding="utf-8")
    print(f"migrated {src} -> {dst}")


if __name__ == "__main__":
    for pkg in sys.argv[1:]:
        migrate_pipeline(pkg)
