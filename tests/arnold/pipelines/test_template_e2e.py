"""End-to-end tests for the _template pipeline package.

Covers two concerns from the M2 package-authoring surface plan:

1. **Scanner exclusion** — the megaplan-side pipeline discovery scanner
   (``_scan_dir_for_pipeline_modules``) must skip ``_template`` because
   its leading-underscore directory name triggers the skip rule at
   ``arnold/pipelines/megaplan/_pipeline/registry.py:904``.

2. **E2E execution** — the skeleton pipeline built by the template's
   ``build_pipeline()`` must be runnable through
   :func:`arnold.pipeline.runner.run_pipeline` without errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arnold.pipeline.runner import run_pipeline
from arnold.pipelines._template import build_pipeline
from arnold.pipelines.megaplan._pipeline.registry import _scan_dir_for_pipeline_modules
from arnold.runtime.envelope import RuntimeEnvelope


# ── Scanner exclusion ──────────────────────────────────────────────────────

def test_template_excluded_by_scanner() -> None:
    """The scanner must NOT return ``_template`` as a discovered pipeline.

    ``_scan_dir_for_pipeline_modules`` at ``registry.py:904`` skips any
    file or directory whose name starts with ``_`` or ``.``.  Because the
    template directory is named ``_template``, it must be invisible to
    the scanner.
    """
    # Locate the parent packages directory that contains _template.
    # registry.py resolves the scan root relative to its own location.
    registry_file = Path(__file__).resolve().parent.parent.parent.parent / (
        "arnold/pipelines/megaplan/_pipeline/registry.py"
    )
    pipelines_dir = (
        registry_file.resolve().parent.parent.parent
    )  # arnold/pipelines/

    results = _scan_dir_for_pipeline_modules(
        pipelines_dir, package_prefix="arnold.pipelines"
    )

    # Collect the discovered CLI names and file paths.
    found_names = [cli_name for cli_name, _ in results]
    found_paths = [str(mod_path) for _, mod_path in results]

    assert "_template" not in found_names, (
        f"Scanner returned _template in CLI names: {found_names}"
    )
    assert not any("_template" in p for p in found_paths), (
        f"Scanner returned a _template path: {found_paths}"
    )


# ── E2E run_pipeline ───────────────────────────────────────────────────────

def test_template_pipeline_runs_end_to_end() -> None:
    """Build the template pipeline and execute it through run_pipeline.

    The skeleton pipeline built by ``build_skeleton_pipeline`` contains a
    single no-op stage that immediately halts.  Running it through the
    canonical executor must complete without raising an exception.
    """
    pipeline = build_pipeline()
    assert pipeline is not None, "build_pipeline() returned None"

    envelope = RuntimeEnvelope()
    initial_state: dict[str, object] = {}

    # The skeleton's no-op step returns StepResult(next="halt"), so the
    # run terminates immediately.  We assert it does not raise.
    result = run_pipeline(pipeline, initial_state, envelope)
    assert result is not None, "run_pipeline returned None"
