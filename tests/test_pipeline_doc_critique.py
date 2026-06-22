"""M4 negative-absence test: ``_pipeline.demos.doc_critique`` is physically deleted.

After M4 Step 5 deletion the legacy demo module must not be importable.
This replaces the legacy-positive Sprint 2 acceptance test #4.
"""

from __future__ import annotations

import importlib

import pytest


def test_doc_critique_demo_module_absent() -> None:
    """``arnold_pipelines.megaplan._pipeline.demos.doc_critique`` raises ModuleNotFoundError."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("arnold_pipelines.megaplan._pipeline.demos.doc_critique")
