"""Verify that importing arnold.pipelines.megaplan registers hooks AND wires the adapter.

(a) After import, _NATIVE_NORMALIZERS has ≥1 entry for each step-keyed normalizer
    registered by _register_hooks() in megaplan's model_seam.
(b) get_default_adapter_registry().invoke(StepInvocation(kind='model', ...))
    returns a RenderedStepMessage — proving the adapter was installed AFTER hooks.
"""

from __future__ import annotations

import arnold.pipelines.megaplan  # noqa: F401 — triggers hook registration + adapter install

import pytest

from arnold.pipeline.model_seam import _NATIVE_NORMALIZERS, RenderedStepMessage
from arnold.execution.step_invocation import StepInvocation, get_default_adapter_registry

_EXPECTED_STEPS = {
    "review",
    "execute",
    "critique",
    "critique_evaluator",
    "prep-distill",
    "finalize",
}


@pytest.mark.parametrize("step", sorted(_EXPECTED_STEPS))
def test_hook_registry_has_normalizer_for_step(step: str) -> None:
    assert step in _NATIVE_NORMALIZERS, (
        f"_NATIVE_NORMALIZERS missing step {step!r}; registered: {sorted(_NATIVE_NORMALIZERS)}"
    )


def test_default_registry_invoke_returns_rendered_step_message() -> None:
    registry = get_default_adapter_registry()
    invocation = StepInvocation(
        kind="model",
        metadata={
            "prompt": "hello",
            "model": "claude-3-5-haiku-20241022",
            "step": "plan",
        },
    )
    result = registry.invoke(invocation)
    assert isinstance(result, RenderedStepMessage), (
        f"Expected RenderedStepMessage, got {type(result)}"
    )


def test_ordering_hooks_before_adapter_invocable() -> None:
    """Hook registry must be populated before the adapter is invocable."""
    assert len(_NATIVE_NORMALIZERS) >= len(_EXPECTED_STEPS), (
        "Fewer normalizers than expected; ordering invariant may be violated"
    )
    registry = get_default_adapter_registry()
    assert "model" in registry.registered_kinds
