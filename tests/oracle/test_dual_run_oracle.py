"""M4 negative-absence test: dual-run oracle legacy dependencies are deleted.

The M6 dual-run oracle previously depended on ``compile_planning_pipeline``
(``_pipeline.planning``) and the legacy ``Pipeline``/``Stage``/``Edge`` types
(``_pipeline.types``).  After M4 Step 5 deletion these modules are physically
absent.  The dual-run comparison must be re-established against the canonical
``build_pipeline()`` / manifest-backend execution path in a follow-up.
"""

from __future__ import annotations

import importlib

import pytest

DELETED_MODULES = (
    "arnold_pipelines.megaplan._pipeline.planning",
    "arnold_pipelines.megaplan._pipeline.types",
)


def test_dual_run_legacy_planning_module_absent() -> None:
    """``_pipeline.planning`` (containing ``compile_planning_pipeline``) is deleted."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(DELETED_MODULES[0])


def test_dual_run_legacy_types_module_absent() -> None:
    """``_pipeline.types`` (containing legacy ``Pipeline``/``Stage``/``Edge``) is deleted."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(DELETED_MODULES[1])


def test_step_context_moved_to_step_types() -> None:
    """``StepContext`` is now importable from ``arnold_pipelines.megaplan.step_types``."""
    from arnold_pipelines.megaplan.step_types import StepContext

    assert StepContext is not None
