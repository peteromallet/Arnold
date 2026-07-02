"""End-to-end tests for the native-first ``arnold_pipelines/_template`` package.

Covers three concerns:

1. **Scanner exclusion** — the legacy megaplan-side pipeline discovery scanner
   must skip ``_template`` because its leading-underscore directory name
   triggers the skip rule.
2. **Native-first build** — the skeleton ``build_pipeline()`` returns an
   :class:`arnold.pipeline.Pipeline` with a non-null ``native_program``
   built from a projected native shell.
3. **Determinism** — repeated builds produce equivalent native programs.
"""

from __future__ import annotations

from pathlib import Path

from arnold.pipeline.types import Pipeline
from arnold_pipelines._template import build_pipeline
from arnold_pipelines.megaplan.runtime.discovery import _scan_dir_for_pipeline_modules


def test_template_excluded_by_legacy_scanner() -> None:
    """The legacy scanner must NOT return ``_template`` as a discovered pipeline."""

    registry_file = Path(__file__).resolve().parent.parent.parent / (
        "arnold_pipelines/megaplan/runtime/discovery.py"
    )
    pipelines_dir = registry_file.resolve().parent.parent.parent  # arnold_pipelines/

    results = _scan_dir_for_pipeline_modules(
        pipelines_dir, package_prefix="arnold.pipelines"
    )
    found_names = [cli_name for cli_name, _ in results]
    found_paths = [str(mod_path) for _, mod_path in results]

    assert "_template" not in found_names
    assert not any("_template" in p for p in found_paths)


def test_template_builds_native_pipeline() -> None:
    """``build_pipeline()`` returns a native-first :class:`Pipeline` shell."""
    pipeline = build_pipeline()
    assert isinstance(pipeline, Pipeline)
    assert pipeline.entry is not None
    assert len(pipeline.stages) >= 1


def test_template_pipeline_has_non_null_native_program() -> None:
    """The returned pipeline has a non-null ``native_program``."""
    pipeline = build_pipeline()
    assert pipeline.native_program is not None


def test_template_native_program_is_deterministic() -> None:
    """Repeated builds produce equivalent native programs."""
    p1 = build_pipeline()
    p2 = build_pipeline()
    assert p1.native_program is not None
    assert p2.native_program is not None
    # The native programs should reference equivalent phases
    assert len(p1.native_program.phases) == len(p2.native_program.phases)


def test_template_pipeline_passes_authoring_validation() -> None:
    """The template package passes :func:`validate_package_module`."""
    import importlib
    from arnold.pipelines._authoring import validate_package_module

    pkg = importlib.import_module("arnold_pipelines._template")
    validate_package_module(pkg)  # raises on failure
