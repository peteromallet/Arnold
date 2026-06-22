"""M4 negative-absence test: ``_pipeline.patterns`` is physically deleted.

The patterns module was part of the legacy ``_pipeline`` package deleted
in M4 Step 5.  This characterization verifies the module is absent rather
than testing its import surface.
"""

from __future__ import annotations

import importlib

import pytest


def test_patterns_module_absent() -> None:
    """``arnold.pipelines.megaplan._pipeline.patterns`` raises ModuleNotFoundError."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("arnold.pipelines.megaplan._pipeline.patterns")
