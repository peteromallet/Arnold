"""Smoke tests for :mod:`arnold.pipeline.legacy` — graph-era compatibility namespace.

Verifies that all 11 required symbols are importable, identity-delegate to
their canonical implementations, and that the module is a pure re-export
shim with no implementation logic.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import arnold.pipeline.legacy as _legacy


# ---------------------------------------------------------------------------
# Canonical source modules for identity checks
# ---------------------------------------------------------------------------

CANONICAL_SOURCES = {
    "Edge": ("arnold.pipeline.types", "Edge"),
    "Stage": ("arnold.pipeline.types", "Stage"),
    "ParallelStage": ("arnold.pipeline.types", "ParallelStage"),
    "PipelineBuilder": ("arnold.workflow.builder", "PipelineBuilder"),
    "PipelineRegistry": ("arnold.workflow.registry", "PipelineRegistry"),
    "validate": ("arnold.workflow.validator", "validate"),
    "StepInvocation": ("arnold.execution.step_invocation", "StepInvocation"),
    "ExecutorHooks": ("arnold.execution.hooks", "ExecutorHooks"),
    "NullExecutorHooks": ("arnold.execution.hooks", "NullExecutorHooks"),
    "run_pipeline": ("arnold.pipeline.executor", "run_pipeline"),
    "run_pipeline_resume": ("arnold.pipeline.executor", "run_pipeline_resume"),
}


# ---------------------------------------------------------------------------
# Import exposure
# ---------------------------------------------------------------------------


class TestLegacyImportExposure:
    """Every required symbol is importable from arnold.pipeline.legacy."""

    @pytest.mark.parametrize("name", sorted(CANONICAL_SOURCES))
    def test_symbol_in_module_namespace(self, name: str) -> None:
        assert hasattr(_legacy, name), f"{name} not found in arnold.pipeline.legacy"

    def test_all_covers_required_symbols(self) -> None:
        required = set(CANONICAL_SOURCES)
        exposed = set(_legacy.__all__)
        assert required == exposed, (
            f"__all__ mismatch: "
            f"missing={required - exposed}, extra={exposed - required}"
        )


# ---------------------------------------------------------------------------
# Identity delegation
# ---------------------------------------------------------------------------


class TestLegacyIdentityDelegation:
    """Every legacy export is the *same object* as its canonical source."""

    @pytest.mark.parametrize("name, source", CANONICAL_SOURCES.items())
    def test_identity_delegation(self, name: str, source: tuple[str, str]) -> None:
        mod_name, attr = source
        import importlib

        canonical_mod = importlib.import_module(mod_name)
        canonical_obj = getattr(canonical_mod, attr)
        legacy_obj = getattr(_legacy, name)
        assert legacy_obj is canonical_obj, (
            f"{name}: legacy object ({id(legacy_obj)}) "
            f"is not canonical object ({id(canonical_obj)})"
        )


# ---------------------------------------------------------------------------
# Pure shim — no implementation logic
# ---------------------------------------------------------------------------


class TestLegacyIsPureShim:
    """The module contains only imports, docstring, and __all__."""

    def test_no_implementation_statements(self) -> None:
        legacy_path = Path(_legacy.__file__)
        source = legacy_path.read_text()
        tree = ast.parse(source)

        non_shim = []
        for node in tree.body:
            # Allow imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            # Allow the module docstring
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue
            # Allow __all__ assignment
            if isinstance(node, ast.Assign):
                targets = [
                    t.id for t in node.targets if isinstance(t, ast.Name)
                ]
                if targets == ["__all__"]:
                    continue
            # Allow __future__ import
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                continue
            non_shim.append((node.lineno, ast.dump(node)[:120]))

        assert not non_shim, (
            f"Found {len(non_shim)} non-shim statement(s): {non_shim}"
        )
