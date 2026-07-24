from __future__ import annotations

from types import SimpleNamespace

import pytest

from arnold.pipeline.model_seam import ModelBudgetError
from arnold_pipelines.megaplan.model_seam import ModelTier, render_prompt_for_dispatch
from arnold_pipelines.megaplan.workers import shannon
from arnold_pipelines.megaplan.workers.shannon import (
    _selected_claude_model_metadata,
    check_prompt_size,
)


_OBSERVED_GATE_INPUT_TOKENS = 233_094
# The Claude-family conservative estimator sees the section label plus this
# ASCII payload as exactly 233,094 input tokens.
_OBSERVED_GATE_PROMPT = "x" * 559_416


def test_run_shannon_step_propagates_selected_budget_to_dispatch(
    tmp_path,
    monkeypatch,
) -> None:
    class RenderReached(RuntimeError):
        pass

    class FakeTmuxSession:
        def __init__(self, name):
            self.name = name

        def teardown(self):
            return None

        def exists(self):
            return False

    captured = {}

    def capture_render(*args, **kwargs):
        captured.update(kwargs)
        raise RenderReached

    plan_dir = tmp_path / ".megaplan" / "plans" / "budget-propagation"
    plan_dir.mkdir(parents=True)
    state = {
        "name": "budget-propagation",
        "iteration": 1,
        "config": {"project_dir": str(tmp_path), "mode": "code"},
        "sessions": {},
    }

    monkeypatch.setattr(
        shannon.ShannonConfig,
        "load",
        lambda *args, **kwargs: SimpleNamespace(claude_config_mode="native"),
    )
    monkeypatch.setattr(shannon, "_assert_vendored_shannon_sentinel", lambda: None)
    monkeypatch.setattr(shannon, "resolve_execution_environment", lambda **kwargs: None)
    monkeypatch.setattr(shannon, "_ensure_workspace_trusted", lambda *args, **kwargs: None)
    monkeypatch.setattr(shannon, "TmuxSession", FakeTmuxSession)
    monkeypatch.setattr(shannon, "pane_pids", lambda *args, **kwargs: [])
    monkeypatch.setattr(shannon, "_write_tmux_session_ledger", lambda *args, **kwargs: None)
    monkeypatch.setattr(shannon, "render_prompt_for_dispatch", capture_render)

    with pytest.raises(RenderReached):
        shannon.run_shannon_step(
            "gate",
            state,
            plan_dir,
            root=tmp_path,
            fresh=True,
            model="claude-sonnet-4-6",
            prompt_override=_OBSERVED_GATE_PROMPT,
        )

    assert captured["model"] == "claude-sonnet-4-6"
    assert captured["normalized_model"] == "claude-sonnet-4-6"
    assert captured["metadata"]["provider"] == "anthropic"
    assert captured["metadata"]["max_input_tokens"] == 1_000_000


def test_sonnet_46_metadata_admits_observed_gate_prompt(tmp_path) -> None:
    metadata = _selected_claude_model_metadata("claude-sonnet-4-6")
    assert metadata == {
        "provider": "anthropic",
        "max_input_tokens": 1_000_000,
    }

    rendered = render_prompt_for_dispatch(
        "claude",
        "gate",
        {},
        tmp_path,
        model="claude-sonnet-4-6",
        normalized_model="claude-sonnet-4-6",
        tier=ModelTier.NON_ENFORCED,
        prompt_override=_OBSERVED_GATE_PROMPT,
        metadata=metadata,
    )
    check_prompt_size(
        _OBSERVED_GATE_PROMPT,
        phase="gate",
        model="claude-sonnet-4-6",
        max_input_tokens=metadata["max_input_tokens"],
    )

    assert rendered.budget.input_tokens == _OBSERVED_GATE_INPUT_TOKENS
    assert rendered.budget.max_input_tokens == 1_000_000


@pytest.mark.parametrize("phase", ["plan", "critique", "revise", "gate", "finalize"])
def test_lower_context_claude_routes_still_reject_observed_prompt(phase) -> None:
    metadata = _selected_claude_model_metadata("claude-3-5-haiku-latest")
    assert metadata["max_input_tokens"] == 200_000

    with pytest.raises(ModelBudgetError, match=r"233094 tokens > 200000 tokens"):
        check_prompt_size(
            _OBSERVED_GATE_PROMPT,
            phase=phase,
            model="claude-3-5-haiku-latest",
            max_input_tokens=metadata["max_input_tokens"],
        )
