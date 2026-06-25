"""End-to-end tests for the native-first ``arnold_pipelines/_template`` package.

Covers three concerns from the M6 native-first scaffold plan:

1. **Scanner exclusion** — the legacy megaplan-side pipeline discovery scanner
   must skip ``_template`` because its leading-underscore directory name
   triggers the skip rule.
2. **Native-first build** — the skeleton ``build_pipeline()`` returns an
   :class:`arnold.pipeline.Pipeline` with a compiled :class:`NativeProgram`
   attached.
3. **Determinism** — repeated builds produce the same native program identity.
"""

from __future__ import annotations

from pathlib import Path

import arnold.pipeline as native_pipeline
from arnold.pipeline.native import NativeProgram
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
    pipeline = build_pipeline()
    assert isinstance(pipeline, native_pipeline.Pipeline)
    assert pipeline.native_program is not None
    assert isinstance(pipeline.native_program, NativeProgram)


def test_template_native_program_has_expected_phases() -> None:
    pipeline = build_pipeline()
    assert pipeline.native_program is not None
    phase_names = {phase.name for phase in pipeline.native_program.phases}
    assert "start" in phase_names
    assert "finish" in phase_names


def test_template_manifest_identity_is_deterministic() -> None:
    p1 = build_pipeline()
    p2 = build_pipeline()
    assert p1.native_program is not None
    assert p2.native_program is not None
    assert p1.native_program.name == p2.native_program.name
