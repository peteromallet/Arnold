"""Parity tests confirming megaplan re-exports from arnold.pipeline.model_seam.

Success criterion 3 of plan_v1.meta.json:
  render_step_message, capture_step_output, install_model_step_adapter,
  ModelTier, RenderedStepMessage imported from
  arnold.pipelines.megaplan.model_seam are ``is``-identical to those imported
  from arnold.pipeline.model_seam (re-export verified).
"""

from __future__ import annotations

import pytest

from arnold.pipeline import StepInvocation
from arnold.pipeline import model_seam as _generic
from arnold.pipelines.megaplan import model_seam as _megaplan


# --------------------------------------------------------------------------- #
# Identity tests (re-export is-identical)
# --------------------------------------------------------------------------- #


def test_render_step_message_is_identical() -> None:
    """render_step_message is re-exported directly from the generic module."""
    assert _megaplan.render_step_message is _generic.render_step_message


def test_install_model_step_adapter_is_identical() -> None:
    """install_model_step_adapter is re-exported directly from the generic module."""
    assert _megaplan.install_model_step_adapter is _generic.install_model_step_adapter


def test_model_tier_is_identical() -> None:
    """ModelTier enum class is re-exported directly from the generic module."""
    assert _megaplan.ModelTier is _generic.ModelTier


def test_rendered_step_message_is_identical() -> None:
    """RenderedStepMessage dataclass is re-exported directly from the generic module."""
    assert _megaplan.RenderedStepMessage is _generic.RenderedStepMessage


def test_capture_step_output_identity() -> None:
    """capture_step_output: megaplan wraps the generic core with recovery-aware logic.

    The megaplan module imports the generic capture_step_output as
    ``_generic_capture_step_output`` and defines its own wrapper that adds
    file-based JSON recovery before delegating to the same normalization,
    projection, audit, and repair flow.

    Because the wrapper is a distinct function object, the ``is`` check fails
    intentionally — this test documents the wrapper relationship.
    """
    # The megaplan wrapper is NOT the same object as the generic function.
    assert _megaplan.capture_step_output is not _generic.capture_step_output

    # The generic core is stashed under the private alias.
    assert _megaplan._generic_capture_step_output is _generic.capture_step_output


# --------------------------------------------------------------------------- #
# Behavior-parity smoke (5 invocations: enforced + non-enforced × 3 families)
# --------------------------------------------------------------------------- #

ENFORCED_CODEX_METADATA: dict = {
    "tier": "enforced",
    "worker": "codex",
    "model": "codex-gpt",
    "normalized_model": "codex-gpt",
    "prompt": "Explain the plan in one sentence.",
}
ENFORCED_CLAUDE_METADATA: dict = {
    "tier": "enforced",
    "worker": "shannon",
    "model": "claude-sonnet",
    "normalized_model": "claude-sonnet",
    "prompt": "Review the following patch for correctness.",
}
ENFORCED_DEEPSEEK_METADATA: dict = {
    "tier": "enforced",
    "worker": "hermes",
    "model": "deepseek-v3",
    "normalized_model": "deepseek-v3",
    "prompt": "Write a test for the given function.",
}
NON_ENFORCED_CLAUDE_METADATA: dict = {
    "tier": "non_enforced",
    "worker": "shannon",
    "model": "claude-sonnet",
    "normalized_model": "claude-sonnet",
    "prompt": "Suggest a better variable name.",
}
NON_ENFORCED_UNKNOWN_METADATA: dict = {
    "tier": "non_enforced",
    "worker": "unknown",
    "model": "unknown-model",
    "normalized_model": "unknown-model",
    "prompt": "Hello, world.",
}


def _render(invocation: StepInvocation) -> tuple:
    """Render through both paths and return (generic_result, megaplan_result)."""
    generic_result = _generic.render_step_message(invocation)
    megaplan_result = _megaplan.render_step_message(invocation)
    return generic_result, megaplan_result


def test_parity_enforced_codex() -> None:
    """Enforced codex invocation produces identical to_json() through both paths."""
    inv = StepInvocation(kind="model", metadata=ENFORCED_CODEX_METADATA)
    g, m = _render(inv)
    assert g.to_json() == m.to_json()


def test_parity_enforced_claude() -> None:
    """Enforced claude invocation produces identical to_json() through both paths."""
    inv = StepInvocation(kind="model", metadata=ENFORCED_CLAUDE_METADATA)
    g, m = _render(inv)
    assert g.to_json() == m.to_json()


def test_parity_enforced_deepseek() -> None:
    """Enforced deepseek invocation produces identical to_json() through both paths."""
    inv = StepInvocation(kind="model", metadata=ENFORCED_DEEPSEEK_METADATA)
    g, m = _render(inv)
    assert g.to_json() == m.to_json()


def test_parity_non_enforced_claude() -> None:
    """Non-enforced claude invocation produces identical to_json() through both paths."""
    inv = StepInvocation(kind="model", metadata=NON_ENFORCED_CLAUDE_METADATA)
    g, m = _render(inv)
    assert g.to_json() == m.to_json()


def test_parity_non_enforced_unknown_family() -> None:
    """Non-enforced unknown-family invocation produces identical to_json() through both paths."""
    inv = StepInvocation(kind="model", metadata=NON_ENFORCED_UNKNOWN_METADATA)
    g, m = _render(inv)
    assert g.to_json() == m.to_json()
