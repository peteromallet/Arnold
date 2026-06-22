"""M4 negative-absence test: legacy golden-characterization dependencies are deleted.

The golden characterization previously depended on ``run_pipeline_with_policy``
(``_pipeline.executor``), ``compile_planning_pipeline`` (``_pipeline.planning``),
``policy_from_cli_args`` (``_pipeline.runtime``), and ``StepContext``
(``_pipeline.types``).  After M4 Step 5 deletion these modules are physically
absent.  The golden fixtures must be re-established against the canonical
``build_pipeline()`` / manifest-backend execution path in a follow-up.

This file preserves the existence of the golden test target and proves the
deleted surfaces are genuinely absent.
"""

from __future__ import annotations

import importlib

import pytest

DELETED_MODULES = (
    "arnold_pipelines.megaplan._pipeline.executor",
    "arnold_pipelines.megaplan._pipeline.planning",
    "arnold_pipelines.megaplan._pipeline.runtime",
)


def test_golden_legacy_executor_module_absent() -> None:
    """``_pipeline.executor`` (containing ``run_pipeline_with_policy``) is deleted."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(DELETED_MODULES[0])


def test_golden_legacy_planning_module_absent() -> None:
    """``_pipeline.planning`` (containing ``compile_planning_pipeline``) is deleted."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(DELETED_MODULES[1])


def test_golden_legacy_runtime_module_absent() -> None:
    """``_pipeline.runtime`` (containing ``policy_from_cli_args``) is deleted."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(DELETED_MODULES[2])


def test_step_context_moved_to_step_types() -> None:
    """``StepContext`` is now importable from ``arnold_pipelines.megaplan.step_types``."""
    from arnold_pipelines.megaplan.step_types import StepContext

    assert StepContext is not None
