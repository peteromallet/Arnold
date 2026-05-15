"""Sprint 3 — every megaplan mode compiles into a Pipeline.

The brief asserts joke/doc/creative modes are configurations of the
parent abstraction. This test pins that: every mode produces a valid
:class:`Pipeline` whose stage set + edges match what the live
``_workflow_for_robustness`` resolves for the same mode, across every
robustness level. Catches regressions if anyone adds a new mode and
forgets to wire the mode overlay.
"""

from __future__ import annotations

import pytest

from megaplan._core.workflow import _workflow_for_robustness
from megaplan._pipeline.planning import (
    compile_pipeline_for,
    mode_overlay,
)


@pytest.mark.parametrize("mode", ["code", "doc", "metaplan", "joke", "creative"])
@pytest.mark.parametrize(
    "robustness", ["tiny", "light", "standard", "robust", "superrobust"]
)
def test_mode_pipeline_matches_runtime_workflow(mode: str, robustness: str) -> None:
    creative = mode in {"creative", "joke"}
    state_payload = {"config": {"mode": mode}}

    pipeline = compile_pipeline_for(
        robustness=robustness, state_payload=state_payload
    )
    runtime = _workflow_for_robustness(robustness, creative=creative)

    for state_name, transitions in runtime.items():
        compiled = pipeline.stages[state_name]
        actual = [(e.label, e.target) for e in compiled.edges]
        expected = [
            (
                t.next_step if t.condition == "always" else f"{t.condition}:{t.next_step}",
                t.next_state,
            )
            for t in transitions
        ]
        assert actual == expected, (mode, robustness, state_name, actual, expected)

    # mode_overlay name reflects the requested mode.
    overlay_names = [o.name for o in pipeline.overlays]
    assert f"mode:{mode}" in overlay_names


def test_mode_overlay_is_a_noop_at_graph_level() -> None:
    """Mode dispatch happens at prompt resolution time, not graph time.

    The overlay's responsibility is to name the mode so downstream
    introspection works (and so the Sprint-3 follow-up that wires
    prompt-mode dispatch has a hook). It does NOT rewrite stages.
    """

    from megaplan._pipeline.planning import compile_planning_pipeline

    base = compile_planning_pipeline()
    rewritten = mode_overlay("joke").apply(base)
    # Same stages dict.
    assert rewritten.stages is base.stages


@pytest.mark.parametrize("mode", ["code", "doc", "joke", "creative"])
def test_compile_pipeline_for_resolves_mode_from_state(mode: str) -> None:
    pipeline = compile_pipeline_for(
        robustness="standard",
        state_payload={"config": {"mode": mode}},
    )
    overlay_names = [o.name for o in pipeline.overlays]
    assert f"mode:{mode}" in overlay_names


def test_explicit_mode_arg_overrides_state_payload() -> None:
    pipeline = compile_pipeline_for(
        robustness="standard",
        state_payload={"config": {"mode": "code"}},
        mode="joke",
    )
    overlay_names = [o.name for o in pipeline.overlays]
    assert "mode:joke" in overlay_names


def test_default_mode_is_code() -> None:
    pipeline = compile_pipeline_for(robustness="standard")
    overlay_names = [o.name for o in pipeline.overlays]
    assert "mode:code" in overlay_names
