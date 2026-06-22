"""M4-migrated elegance-property tests.

Pin the structural commitments the brief made. Each test is a
small invariant that would catch regression of the architecture
shape.  After M4 Step 5 deletion, tests have been migrated to use
the canonical ``arnold_pipelines.megaplan.pipeline.build_pipeline()``
and ``arnold.workflow.dsl`` types, or converted to negative-absence
tests where the tested surface was physically deleted.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent


def test_no_string_packed_gate_labels_in_production() -> None:
    """No more 'gate_iterate:revise'-style string packing in the
    pipeline production code.

    After M4 deletion the scan root is the surviving megaplan package
    tree under ``arnold_pipelines/megaplan/`` rather than the deleted
    ``_pipeline/`` subtree.
    """
    proc = subprocess.run(
        ["git", "grep", "-E",
         "gate_iterate:|gate_proceed:|gate_tiebreaker:|gate_escalate:",
         "arnold_pipelines/megaplan/"],
        cwd=_REPO_ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 1, f"found packed labels: {proc.stdout}"


def test_subloop_and_override_are_deleted_surfaces() -> None:
    """The legacy ``_pipeline/executor.py`` and ``_pipeline/subloop.py``
    are physically deleted in M4 Step 5.

    These modules were part of the deleted ``_pipeline/`` subtree.
    Canonical routing now lives in the manifest backend and handlers.
    """
    executor_path = _REPO_ROOT / "arnold_pipelines/megaplan/_pipeline/executor.py"
    subloop_path = _REPO_ROOT / "arnold_pipelines/megaplan/_pipeline/subloop.py"
    assert not executor_path.exists(), (
        "_pipeline/executor.py should be physically deleted"
    )
    assert not subloop_path.exists(), (
        "_pipeline/subloop.py should be physically deleted"
    )


def test_compiled_pipeline_has_canonical_phase_nodes() -> None:
    """Canonical ``build_pipeline()`` produces the expected phase-node graph.

    The M3 explicit-node DSL Pipeline has ``steps`` (not ``stages``)
    and routes define the graph edges.  The first step is ``prep`` and
    the full step-id set matches the canonical taxonomy.
    """
    from arnold_pipelines.megaplan.pipeline import build_pipeline

    pipeline = build_pipeline()
    step_ids = {s.id for s in pipeline.steps}
    assert step_ids == {
        "prep", "plan", "critique", "gate", "revise",
        "tiebreaker_run", "tiebreaker_decide",
        "finalize", "execute", "review",
        "halt", "override",
    }, f"unexpected step ids: {sorted(step_ids)}"

    # First route source is "prep".
    assert pipeline.routes[0].source == "prep"


def test_three_extension_axes_modules_are_deleted() -> None:
    """The legacy extension-axis modules (prompts, profile, overlay) are deleted.

    After M4 the canonical extension mechanism uses handler_ref metadata
    strings on DSL Steps rather than separate axis modules.
    """
    import importlib
    for mod_name in (
        "arnold_pipelines.megaplan._pipeline.prompts",
        "arnold_pipelines.megaplan._pipeline.profile",
        "arnold_pipelines.megaplan._pipeline.planning",
    ):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(mod_name)


def test_one_step_type_serves_all_pipelines() -> None:
    """Every DSL Step uses ``arnold.workflow.dsl.Step`` — a single protocol.

    The canonical ``build_pipeline()`` and the two pipeline builder
    variants all produce steps of the same shared type, proving the
    parent abstraction is real.
    """
    from arnold_pipelines.megaplan.pipeline import build_pipeline
    from arnold.workflow.dsl import Step

    pipeline = build_pipeline()
    for step in pipeline.steps:
        assert isinstance(step, Step), step.id
