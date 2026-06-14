"""Probe: _render_execute_prompt_for_dispatch routes through registry.invoke."""
from unittest.mock import MagicMock, patch

from arnold.pipeline import get_default_adapter_registry
from arnold.pipeline.model_seam import RenderedStepMessage
from arnold.pipelines.megaplan.execute.batch import _render_execute_prompt_for_dispatch


def _make_rendered(prompt: str) -> RenderedStepMessage:
    r = MagicMock(spec=RenderedStepMessage)
    r.prompt = prompt
    return r


def test_render_returns_none_when_no_override():
    result = _render_execute_prompt_for_dispatch(
        agent="execute",
        state=MagicMock(),
        plan_dir=MagicMock(),
        root=MagicMock(),
        model=None,
        resolved_model=None,
        prompt_override=None,
    )
    assert result is None


def test_registry_invoke_called_for_dispatch():
    """registry.invoke(kind='model') must be called from _render_execute_prompt_for_dispatch."""
    expected_prompt = "test-prompt-content"
    fake_rendered = _make_rendered(expected_prompt)

    registry = get_default_adapter_registry()
    with patch.object(registry, "invoke", return_value=fake_rendered) as mock_invoke:
        with patch(
            "arnold.pipelines.megaplan.execute.batch.get_default_adapter_registry",
            return_value=registry,
        ):
            result = _render_execute_prompt_for_dispatch(
                agent="execute",
                state=MagicMock(),
                plan_dir=MagicMock(),
                root=MagicMock(),
                model="claude-sonnet",
                resolved_model="claude-sonnet-4-6",
                prompt_override="hello world",
            )

    mock_invoke.assert_called_once()
    invocation_arg = mock_invoke.call_args[0][0]
    assert invocation_arg.kind == "model"
    assert result == expected_prompt
