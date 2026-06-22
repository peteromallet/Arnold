"""M4 negative-absence test: ``_pipeline.demo_judges`` is physically deleted.

After M4 Step 5 deletion the legacy demo module must not be importable.
This replaces the legacy-positive acceptance test #3.
"""

from __future__ import annotations

import importlib

import pytest


def test_demo_judges_module_absent() -> None:
    """``arnold.pipelines.megaplan._pipeline.demo_judges`` raises ModuleNotFoundError."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("arnold.pipelines.megaplan._pipeline.demo_judges")
