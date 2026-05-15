"""Sprint 4 Chunk F — five elegance-property tests.

Pin the structural commitments the brief made. Each test is a
small invariant that would catch regression of the architecture
shape.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent


def test_no_string_packed_gate_labels_in_production() -> None:
    """No more 'gate_iterate:revise'-style string packing in the
    pipeline production code."""
    proc = subprocess.run(
        ["git", "grep", "-E",
         "gate_iterate:|gate_proceed:|gate_tiebreaker:|gate_escalate:",
         "megaplan/_pipeline/"],
        cwd=_REPO_ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 1, f"found packed labels: {proc.stdout}"


def test_subloop_and_override_have_executor_branches() -> None:
    """Both reserved Step kinds have executor branches now."""
    executor_src = (
        _REPO_ROOT / "megaplan/_pipeline/executor.py"
    ).read_text()
    assert "find_override_edge" in executor_src, (
        "executor must import find_override_edge to dispatch kind='override' edges"
    )
    subloop_src = (
        _REPO_ROOT / "megaplan/_pipeline/subloop.py"
    ).read_text()
    assert 'kind: str = "subloop"' in subloop_src or 'kind = "subloop"' in subloop_src
    assert "child_pipeline" in subloop_src


def test_workflow_dict_derived_from_pipeline() -> None:
    """The Pipeline is provably sufficient to reconstruct WORKFLOW."""
    from megaplan._core.workflow_data import WORKFLOW
    from megaplan._pipeline.planning import (
        compile_planning_pipeline,
        workflow_dict_from_pipeline,
    )

    derived = workflow_dict_from_pipeline(compile_planning_pipeline())
    assert set(derived.keys()) == set(WORKFLOW.keys())
    for state_name in WORKFLOW:
        expected = [(t.next_step, t.next_state, t.condition) for t in WORKFLOW[state_name]]
        actual = [(t.next_step, t.next_state, t.condition) for t in derived[state_name]]
        assert actual == expected, state_name


def test_three_extension_axes_are_orthogonal() -> None:
    """Mode (prompts), slot (profile), Overlay (graph) compose without
    touching each other."""
    from megaplan._pipeline.prompts import PromptRegistry
    from megaplan._pipeline.profile import Profile
    from megaplan._pipeline.types import Overlay

    # Each lives in its own module.
    import megaplan._pipeline.prompts as prompts_mod
    import megaplan._pipeline.profile as profile_mod
    import megaplan._pipeline.planning as planning_mod

    # No cross-imports between the three axes.
    profile_src = (
        _REPO_ROOT / "megaplan/_pipeline/profile.py"
    ).read_text()
    prompts_src = (
        _REPO_ROOT / "megaplan/_pipeline/prompts.py"
    ).read_text()

    assert "from megaplan._pipeline.prompts" not in profile_src
    assert "from megaplan._pipeline.profile" not in prompts_src


def test_one_step_type_serves_all_pipelines() -> None:
    """Every shipped pipeline uses the same Step protocol — proving
    the parent abstraction is real, not three parallel taxonomies."""
    from megaplan._pipeline.demos.doc_critique import build_pipeline as build_doc
    from megaplan._pipeline.demo_judges import build_pipeline as build_judges
    from megaplan._pipeline.planning import compile_planning_pipeline
    from megaplan._pipeline.types import Pipeline, Step

    for pipeline in (build_doc(), build_judges(), compile_planning_pipeline()):
        assert isinstance(pipeline, Pipeline)
        for stage in pipeline.stages.values():
            if hasattr(stage, "step"):
                assert isinstance(stage.step, Step), stage.name
            elif hasattr(stage, "steps"):
                for s in stage.steps:
                    assert isinstance(s, Step), stage.name
