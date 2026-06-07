"""Direct Hermes worker tests for megaplan.workers."""

from __future__ import annotations

from argparse import Namespace
from contextlib import nullcontext
import json
import sys
from pathlib import Path
from unittest.mock import patch

from arnold.pipelines.megaplan.types import AgentMode
from arnold.pipelines.megaplan.workers import WorkerResult
from tests._workers_helpers import _mock_state


def test_is_agent_available_hermes_when_runtime_importable() -> None:
    """_is_agent_available('hermes') is True when megaplan.agent + run_agent + hermes_state import.

    Regression for a path-mismatch bug where the legacy filesystem probe
    pointed at megaplan/workers/agent/run_agent.py — which never existed
    (run_agent.py lives at megaplan/agent/run_agent.py). The probe therefore
    always returned False on every install and the downstream phase wrongly
    raised agent_deps_missing even when the agent runtime was fully present.
    """
    from arnold.pipelines.megaplan.workers import _is_agent_available

    assert _is_agent_available("hermes") is True


def test_is_agent_available_hermes_when_runtime_missing() -> None:
    """_is_agent_available('hermes') is False if the runtime can't be imported.

    Simulates the case where megaplan was installed without the agent runtime
    (e.g. a slim wheel that excludes megaplan/agent/). Patches the import via
    sys.modules to force ImportError on run_agent.
    """
    from arnold.pipelines.megaplan.workers import _is_agent_available

    saved_run_agent = sys.modules.pop("run_agent", None)
    sys.modules["run_agent"] = None  # type: ignore[assignment]  # sentinel: forces ImportError
    try:
        assert _is_agent_available("hermes") is False
    finally:
        if saved_run_agent is not None:
            sys.modules["run_agent"] = saved_run_agent
        else:
            sys.modules.pop("run_agent", None)


def test_hermes_high_token_streaming_matches_fireworks_for_direct_deepseek() -> None:
    from arnold.pipelines.megaplan.workers.hermes import _streaming_run_kwargs

    assert _streaming_run_kwargs("fireworks:accounts/fireworks/models/deepseek-v4-pro", 32768)
    assert _streaming_run_kwargs("deepseek:deepseek-v4-pro", 32768)
    assert not _streaming_run_kwargs("deepseek:deepseek-v4-pro", 4096)

def test_hermes_deepseek_v4_does_not_force_reasoning_disabled() -> None:
    from arnold.pipelines.megaplan.workers.hermes import _reasoning_config_for_model

    assert _reasoning_config_for_model("deepseek-v4-pro") is None
    assert _reasoning_config_for_model("accounts/fireworks/models/deepseek-v4-pro") is None
    assert _reasoning_config_for_model("deepseek/deepseek-r1") == {"enabled": False}

def test_hermes_reasoning_config_maps_profile_depth() -> None:
    from arnold.pipelines.megaplan.workers.hermes import _reasoning_config_for_model

    # Effort maps onto a route-safe reasoning budget.
    assert _reasoning_config_for_model("deepseek-v4-pro", "low") == {
        "enabled": True,
        "effort": "low",
    }
    assert _reasoning_config_for_model("deepseek-v4-pro", "high") == {
        "enabled": True,
        "effort": "high",
    }
    # xhigh/max pass through unchanged — DeepSeek-direct accepts max and maps
    # xhigh→max itself; the OpenRouter-only clamp lives in the request builder.
    assert _reasoning_config_for_model("deepseek-v4-pro", "xhigh") == {
        "enabled": True,
        "effort": "xhigh",
    }
    assert _reasoning_config_for_model("deepseek-v4-pro", "max") == {
        "enabled": True,
        "effort": "max",
    }
    # minimal disables thinking entirely.
    assert _reasoning_config_for_model("deepseek-v4-pro", "minimal") == {"enabled": False}
    # Unknown token leaves the provider default untouched.
    assert _reasoning_config_for_model("deepseek-v4-pro", "bogus") is None
    # Family override wins over requested depth.
    assert _reasoning_config_for_model("deepseek/deepseek-r1", "high") == {"enabled": False}


def test_run_step_with_worker_forwards_output_path_and_worker_options_to_hermes(
    tmp_path: Path,
) -> None:
    from arnold.pipelines.megaplan.workers import run_step_with_worker

    plan_dir, state = _mock_state(tmp_path)
    args = Namespace(
        agent=None,
        ephemeral=False,
        fresh=False,
        persist=False,
        confirm_self_review=False,
        hermes=None,
        phase_model=[],
    )
    worker_options = {
        "template_path": str(plan_dir / "review_template.json"),
        "session_db_path": str(plan_dir / ".hermes_state" / "review.db"),
        "max_tokens": 40000,
        "resolved_model": "qwen/qwen3-32b",
        "reasoning_config": {"enabled": False},
    }
    output_path = plan_dir / "review_output.json"
    worker = WorkerResult(
        payload={"checks": []},
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
        session_id="hermes-session",
    )

    with patch("arnold.pipelines.megaplan.workers.hermes.run_hermes_step", return_value=worker) as mocked_hermes:
        result, agent, _mode, _refreshed = run_step_with_worker(
            "review",
            state,
            plan_dir,
            args,
            root=tmp_path,
            resolved=AgentMode(
                agent="hermes",
                mode="persistent",
                refreshed=False,
                model="minimax:MiniMax-M2",
            ),
            output_path=output_path,
            worker_options=worker_options,
            read_only=True,
        )

    assert result == worker
    assert agent == "hermes"
    assert mocked_hermes.call_args.kwargs["output_path"] == output_path
    assert mocked_hermes.call_args.kwargs["worker_options"] == worker_options


def test_parse_agent_output_repairs_malformed_json_once(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.workers.hermes import parse_agent_output

    plan_dir, state = _mock_state(tmp_path)
    project_dir = Path(state["config"]["project_dir"])
    invalid_raw = (
        '{"plan":"Use regex clarify\\s*\\(","changes_summary":"x",'
        '"flags_addressed":[],"assumptions":[],"success_criteria":[],"questions":[]}'
    )
    valid_payload = {
        "plan": "Use regex clarify\\\\s*\\\\( safely.",
        "changes_summary": "Escaped regex backslashes.",
        "flags_addressed": [],
        "assumptions": [],
        "success_criteria": [],
        "questions": [],
    }

    class FakeAgent:
        def __init__(self) -> None:
            self.repair_prompts: list[str] = []

        def run_conversation(self, **kwargs):
            self.repair_prompts.append(str(kwargs["user_message"]))
            return {
                "final_response": json.dumps(valid_payload),
                "messages": [{"role": "assistant", "content": json.dumps(valid_payload)}],
            }

    agent = FakeAgent()
    payload, raw_output = parse_agent_output(
        agent,
        {"final_response": invalid_raw, "messages": [{"role": "assistant", "content": invalid_raw}]},
        output_path=None,
        schema={},
        step="revise",
        project_dir=project_dir,
        plan_dir=plan_dir,
    )

    assert payload == valid_payload
    assert json.loads(raw_output) == valid_payload
    assert len(agent.repair_prompts) == 1
    assert "No prose, no code fences." in agent.repair_prompts[0]


def test_run_hermes_step_uses_worker_options_and_preserves_minimax_fallback(
    tmp_path: Path,
) -> None:
    from arnold.pipelines.megaplan.workers.hermes import run_hermes_step

    repo_root = Path(__file__).resolve().parents[1]
    plan_dir, state = _mock_state(tmp_path)
    template_path = plan_dir / "review_template.json"
    template_path.write_text('{"checks": []}', encoding="utf-8")
    output_path = plan_dir / "review_output.json"
    session_db_path = plan_dir / ".hermes_state" / "review.db"
    worker_options = {
        "template_path": str(template_path),
        "session_db_path": str(session_db_path),
        "max_tokens": 40000,
        "resolved_model": "qwen/qwen3-32b",
    }
    parse_calls: list[Path | None] = []
    render_prompt_calls: list[str | None] = []

    class FakeSessionDB:
        def __init__(self, db_path=None):
            self.db_path = db_path

    class FakeAIAgent:
        instances: list["FakeAIAgent"] = []

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self._print_fn = None
            self.reasoning_callback = None
            self._executing_tools = False
            self.__class__.instances.append(self)

        def run_conversation(self, **kwargs):
            self.last_run_kwargs = kwargs
            if self.kwargs["model"] == "MiniMax-M2":
                raise RuntimeError("429 rate limit")
            return {
                "final_response": '{"checks": []}',
                "messages": [{"role": "assistant", "content": '{"checks": []}'}],
                "estimated_cost_usd": 0.25,
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
                "model": self.kwargs["model"],
            }

        def clear_interrupt(self):
            return None

        def interrupt(self, _reason=None):
            return None

    def _fake_parse_agent_output(agent, result, **kwargs):
        parse_calls.append(kwargs.get("output_path"))
        return {"checks": []}, result.get("final_response", "")

    capture_calls: list[dict] = []

    def _capture_spy(invocation, output):
        capture_calls.append(dict(invocation.metadata))
        return type("Capture", (), {"legacy_payload": output})()

    def _render_prompt_spy(*args, **kwargs):
        render_prompt_calls.append(kwargs.get("prompt_override"))
        return type("RenderedStep", (), {"prompt": kwargs.get("prompt_override") or "rendered prompt"})()

    with (
        patch("arnold.pipelines.megaplan.workers.hermes._import_hermes_runtime", return_value=(FakeAIAgent, FakeSessionDB)),
        patch("arnold.pipelines.megaplan.workers.hermes.parse_agent_output", side_effect=_fake_parse_agent_output),
        patch("arnold.pipelines.megaplan.workers.hermes.clean_parsed_payload", return_value=None),
        patch("arnold.pipelines.megaplan.workers.hermes.capture_step_output", side_effect=_capture_spy),
        patch("arnold.pipelines.megaplan.workers.hermes.render_prompt_for_dispatch", side_effect=_render_prompt_spy),
        patch("arnold.pipelines.megaplan.runtime.key_pool.resolve_model", return_value=("MiniMax-M2", {"api_key": "mm-key"})),
        patch("arnold.pipelines.megaplan.runtime.key_pool.acquire_key", return_value="or-key"),
        patch("arnold.pipelines.megaplan.runtime.key_pool.report_429", return_value=None),
        patch("arnold.pipelines.megaplan.runtime.key_pool.minimax_openrouter_model", return_value="openrouter/minimax"),
        patch("arnold.pipelines.megaplan.runtime.sandbox.install_sandbox", return_value=nullcontext()),
    ):
        result = run_hermes_step(
            "review",
            state,
            plan_dir,
            root=repo_root,
            fresh=True,
            model="minimax:MiniMax-M2",
            prompt_override="fill the review template",
            output_path=output_path,
            worker_options=worker_options,
        )

    assert output_path.read_text(encoding="utf-8") == '{"checks": []}'
    assert parse_calls == [output_path]
    assert len(FakeAIAgent.instances) == 2
    primary, fallback = FakeAIAgent.instances
    assert primary.kwargs["session_db"].db_path == session_db_path
    assert primary.kwargs["max_tokens"] == 40000
    assert primary.kwargs["reasoning_config"] == {"enabled": False}
    assert fallback.kwargs["model"] == "openrouter/minimax"
    assert fallback.kwargs["session_db"].db_path == session_db_path
    assert render_prompt_calls == ["fill the review template"]
    assert result.payload == {"checks": []}
    assert result.model_actual == "openrouter/minimax"
    assert capture_calls[-1]["worker"] == "hermes"
    assert capture_calls[-1]["tier"] == "non_enforced"


def test_run_hermes_step_passes_none_prompt_override_into_model_seam(
    tmp_path: Path,
) -> None:
    from arnold.pipelines.megaplan.workers.hermes import run_hermes_step

    repo_root = Path(__file__).resolve().parents[1]
    plan_dir, state = _mock_state(tmp_path)
    render_prompt_calls: list[str | None] = []

    class FakeSessionDB:
        def __init__(self, db_path=None):
            self.db_path = db_path

    class FakeAIAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self._print_fn = None
            self.reasoning_callback = None
            self._executing_tools = False

        def run_conversation(self, **_kwargs):
            return {
                "final_response": '{"checks": []}',
                "messages": [{"role": "assistant", "content": '{"checks": []}'}],
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
                "model": self.kwargs["model"],
            }

        def clear_interrupt(self):
            return None

        def interrupt(self, _reason=None):
            return None

    def _fake_parse_agent_output(_agent, result, **_kwargs):
        return {"checks": []}, result.get("final_response", "")

    def _render_prompt_spy(*args, **kwargs):
        render_prompt_calls.append(kwargs.get("prompt_override"))
        return type("RenderedStep", (), {"prompt": "rendered prompt"})()

    def _capture_spy(_invocation, output):
        return type("Capture", (), {"legacy_payload": output})()

    with (
        patch("arnold.pipelines.megaplan.workers.hermes._import_hermes_runtime", return_value=(FakeAIAgent, FakeSessionDB)),
        patch("arnold.pipelines.megaplan.workers.hermes.parse_agent_output", side_effect=_fake_parse_agent_output),
        patch("arnold.pipelines.megaplan.workers.hermes.clean_parsed_payload", return_value=None),
        patch("arnold.pipelines.megaplan.workers.hermes.capture_step_output", side_effect=_capture_spy),
        patch("arnold.pipelines.megaplan.workers.hermes.render_prompt_for_dispatch", side_effect=_render_prompt_spy),
        patch("arnold.pipelines.megaplan.runtime.key_pool.resolve_model", return_value=("qwen3-32b", {})),
        patch("arnold.pipelines.megaplan.runtime.sandbox.install_sandbox", return_value=nullcontext()),
    ):
        result = run_hermes_step(
            "review",
            state,
            plan_dir,
            root=repo_root,
            fresh=True,
            model="qwen3-32b",
        )

    assert render_prompt_calls == [None]
    assert result.payload == {"checks": []}


def test_run_hermes_step_does_not_set_response_format_when_tools_enabled(
    tmp_path: Path,
) -> None:
    from arnold.pipelines.megaplan.workers.hermes import run_hermes_step

    repo_root = Path(__file__).resolve().parents[1]
    plan_dir, state = _mock_state(tmp_path)

    class FakeSessionDB:
        def __init__(self, db_path=None):
            self.db_path = db_path

    class FakeAIAgent:
        response_format_calls = 0

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self._print_fn = None
            self.reasoning_callback = None

        def set_response_format(self, *_args, **_kwargs):
            self.__class__.response_format_calls += 1

        def run_conversation(self, **_kwargs):
            return {
                "final_response": "{}",
                "messages": [{"role": "assistant", "content": "{}"}],
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
                "model": self.kwargs["model"],
            }

        def clear_interrupt(self):
            return None

        def interrupt(self, _reason=None):
            return None

    capture_calls: list[dict] = []

    def _fake_parse_agent_output(_agent, result, **_kwargs):
        return {
            "plan": "# P",
            "questions": [],
            "success_criteria": [{"criterion": "c", "priority": "must", "requires": []}],
            "assumptions": [],
        }, result.get("final_response", "")

    def _capture_spy(invocation, output):
        capture_calls.append(dict(invocation.metadata))
        return type("Capture", (), {"legacy_payload": output})()

    with (
        patch("arnold.pipelines.megaplan.workers.hermes._import_hermes_runtime", return_value=(FakeAIAgent, FakeSessionDB)),
        patch("arnold.pipelines.megaplan.workers.hermes.parse_agent_output", side_effect=_fake_parse_agent_output),
        patch("arnold.pipelines.megaplan.workers.hermes.clean_parsed_payload", return_value=None),
        patch("arnold.pipelines.megaplan.workers.hermes.capture_step_output", side_effect=_capture_spy),
        patch("arnold.pipelines.megaplan.runtime.key_pool.resolve_model", return_value=("qwen3-32b", {})),
        patch("arnold.pipelines.megaplan.runtime.sandbox.install_sandbox", return_value=nullcontext()),
    ):
        run_hermes_step(
            "plan",
            state,
            plan_dir,
            root=repo_root,
            fresh=True,
            model="qwen3-32b",
        )

    assert FakeAIAgent.response_format_calls == 0
    assert capture_calls[-1]["tier"] == "non_enforced"
