"""Probe: _render_execute_prompt_for_dispatch routes through the model seam."""
from unittest.mock import MagicMock, patch

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


def test_render_step_message_called_for_dispatch():
    """render_step_message must be called from _render_execute_prompt_for_dispatch."""
    expected_prompt = "test-prompt-content"
    fake_rendered = _make_rendered(expected_prompt)

    with patch(
        "arnold.pipelines.megaplan.execute.batch.render_step_message",
        return_value=fake_rendered,
    ) as mock_render:
        result = _render_execute_prompt_for_dispatch(
            agent="execute",
            state=MagicMock(),
            plan_dir=MagicMock(),
            root=MagicMock(),
            model="claude-sonnet",
            resolved_model="claude-sonnet-4-6",
            prompt_override="hello world",
        )

    mock_render.assert_called_once()
    invocation_arg = mock_render.call_args[0][0]
    assert invocation_arg.kind == "model"
    assert result == expected_prompt
