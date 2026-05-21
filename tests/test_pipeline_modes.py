"""Sprint 3 — every megaplan mode compiles into a Pipeline.

Sprint 5 Chunk A retired the byte-for-byte parity contract against the
legacy state-name ``_workflow_for_robustness`` view. The canonical
Pipeline is now keyed by phase names and the mode / robustness / with_*
overlays are identity transforms (mode dispatch happens at prompt
resolution time, robustness customisation moves to the Step layer).
What this module pins now: every mode produces a valid Pipeline whose
canonical phase-node set survives composition, and the mode overlay
correctly names the requested mode for downstream introspection.

T14 (0.23): this module's coverage of ``compile_pipeline_for(mode=…)``
is RETAINED per USER DECISION 2 — the new 0.23 doc/creative pipelines
do NOT flow through ``compile_pipeline_for``; they reach users via
``megaplan run <pipeline>`` and live under ``tests/pipelines/`` (see
``tests/pipelines/test_doc_pipeline.py`` and
``tests/pipelines/test_creative_pipeline.py``). The assertions below
exercise the legacy planning + mode-overlay path used by
``megaplan init --mode <X> --auto-start`` in 0.23, which remains in
place for backward compatibility. Marked ``# TODO(0.24)`` alongside
the source ``compile_pipeline_for`` creative/joke branch.
"""

from __future__ import annotations

import pytest

from megaplan._pipeline.planning import (
    compile_pipeline_for,
    mode_overlay,
)


EXPECTED_PHASE_STAGES = {
    "prep", "plan", "critique", "gate", "revise",
    "finalize", "execute", "review", "tiebreaker",
}


@pytest.mark.parametrize("mode", ["code", "doc", "metaplan", "joke", "creative"])
@pytest.mark.parametrize(
    "robustness", ["tiny", "light", "standard", "robust", "superrobust"]
)
def test_mode_pipeline_preserves_canonical_phase_nodes(mode: str, robustness: str) -> None:
    state_payload = {"config": {"mode": mode}}
    pipeline = compile_pipeline_for(
        robustness=robustness, state_payload=state_payload
    )

    assert set(pipeline.stages.keys()) == EXPECTED_PHASE_STAGES
    assert pipeline.entry == "prep"

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
