"""Retirement conformance for the archived deliberation pipeline.

The M6 deletion inventory moved this product-specific pipeline under
``docs/archive/m5``.  Keep this historical validation selector useful without
reintroducing the deleted runtime package.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_deliberation_pipeline_is_not_importable_from_the_live_runtime() -> None:
    assert importlib.util.find_spec("arnold.pipelines.deliberation") is None


def test_deliberation_pipeline_source_is_preserved_in_the_m5_archive() -> None:
    archive = PROJECT_ROOT / "docs" / "archive" / "m5" / "pipelines" / "deliberation"

    assert (archive / "__init__.py").is_file()
    assert (archive / "pipelines.py").is_file()
    assert (archive / "steps.py").is_file()
