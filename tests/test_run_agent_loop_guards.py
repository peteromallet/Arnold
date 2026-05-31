from __future__ import annotations

import json
import time
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

import megaplan.agent  # noqa: F401  (side-effect: makes top-level run_agent importable)
from megaplan.handlers.critique import _apply_adaptive_critique_routing
from run_agent import AIAgent, DEFAULT_API_TIMEOUT_SECONDS


def _minimal_agent() -> AIAgent:
    agent = AIAgent.__new__(AIAgent)
    agent._interrupt_requested = False
    agent._checkpoint_mgr = SimpleNamespace(enabled=False)
    agent.quiet_mode = True
    agent.verbose_logging = False
    agent.tool_progress_callback = None
    agent._honcho = None
    agent._honcho_session_key = None
    agent.valid_tool_names = set()
    agent.log_prefix = ""
    agent.log_prefix_chars = 120
    agent._output_stream = None
    agent.tool_delay = 0
    agent.max_iterations = 100
    agent._tool_dedup_cache = {}
    agent._file_read_counts = {}
    agent._get_budget_warning = lambda _api_call_count: None
    return agent


def _init_args(**overrides):
    base = {
        "project_dir": "/tmp/proj",
        "hermes": None,
        "profile": None,
        "vendor": None,
        "critic": None,
        "critic_model": None,
        "depth": None,
        "deepseek_provider": None,
        "with_prep": False,
        "with_feedback": False,
        "prep_direction": None,
        "phase_model": None,
    }
    base.update(overrides)
    return Namespace(**base)


def test_init_records_critic_model_provenance(monkeypatch):
    import megaplan.handlers.init as init_mod

    defaults = {
        "robustness": "full",
        "auto_approve": False,
        "adaptive_critique": False,
        "critic_model": "",
        "strict_notes": False,
        "strict_adaptive_critique": False,
        "max_tasks_per_batch": 3,
        "completion_contract_mode": "off",
        "test_command": "pytest",
        "test_baseline_timeout": 900,
    }

    monkeypatch.setattr(init_mod, "get_effective", lambda _section, key: defaults[key])
    monkeypatch.setattr(init_mod, "load_profile_metadata", lambda project_dir: {})

    monkeypatch.setattr(init_mod, "setting_is_explicit", lambda section, key: False)
    config, *_ = init_mod._build_state_config(
        _init_args(critic_model="deepseek-v4-pro"),
        project_dir=Path("/tmp/proj"),
        pipeline=None,
        mode="code",
        raw_form=None,
        normalized_output_path=None,
        normalized_primary_criterion=None,
        from_doc_rel=None,
    )
    assert config["critic_model"] == "deepseek-v4-pro"
    assert config["critic_model_explicit"] is True

    monkeypatch.setattr(
        init_mod,
        "setting_is_explicit",
        lambda section, key: section == "execution" and key == "critic_model",
    )
    defaults["critic_model"] = "config-pin"
    config, *_ = init_mod._build_state_config(
        _init_args(),
        project_dir=Path("/tmp/proj"),
        pipeline=None,
        mode="code",
        raw_form=None,
        normalized_output_path=None,
        normalized_primary_criterion=None,
        from_doc_rel=None,
    )
    assert config["critic_model"] == "config-pin"
    assert config["critic_model_explicit"] is True

    monkeypatch.setattr(init_mod, "setting_is_explicit", lambda section, key: False)
    monkeypatch.setattr(
        init_mod,
        "load_profile_metadata",
        lambda project_dir: {"partnered": {"critic_model": "profile-pin"}},
    )
    config, *_ = init_mod._build_state_config(
        _init_args(profile="partnered"),
        project_dir=Path("/tmp/proj"),
        pipeline=None,
        mode="code",
        raw_form=None,
        normalized_output_path=None,
        normalized_primary_criterion=None,
        from_doc_rel=None,
    )
    assert config["critic_model"] == "profile-pin"
    assert config["critic_model_explicit"] is False


def test_stale_critic_model_without_provenance_uses_per_lens_tier(monkeypatch, capsys):
    state = {
        "config": {
            "critic_model": "deepseek-v4-pro",
            "critic_model_explicit": False,
        }
    }
    checks = [{"id": "correctness", "complexity": 4}]
    args = Namespace(tier_models={"critique": {4: "claude:claude-opus-4-7"}})

    def fake_resolve_tier_spec(args, spec, *, phase="execute"):
        assert phase == "critique"
        assert spec == "claude:claude-opus-4-7"
        return ("claude", "persistent", "claude-opus-4-7")

    monkeypatch.setattr("megaplan.execute.batch._resolve_tier_spec", fake_resolve_tier_spec)

    pin = _apply_adaptive_critique_routing(state, args, checks)

    assert pin is None
    assert checks[0]["_resolved_agent_mode"].model == "claude-opus-4-7"
    assert "WARNING" not in capsys.readouterr().err


def test_explicit_critic_model_pin_is_honored_and_warns_for_high_complexity(
    monkeypatch, capsys
):
    state = {
        "config": {
            "critic_model": "deepseek-v4-pro",
            "critic_model_explicit": True,
        }
    }
    checks = [{"id": "correctness", "complexity": 4}]
    args = Namespace(tier_models={"critique": {4: "claude:claude-opus-4-7"}})

    def fail_resolve(*_args, **_kwargs):
        raise AssertionError("explicit critic_model pin must bypass tier routing")

    monkeypatch.setattr("megaplan.execute.batch._resolve_tier_spec", fail_resolve)

    pin = _apply_adaptive_critique_routing(state, args, checks)

    assert pin == "deepseek-v4-pro"
    err = capsys.readouterr().err
    assert "WARNING" in err
    assert "deepseek-v4-pro" in err
    assert "disables per-lens critique escalation" in err


def test_repeated_file_read_breaker_persists_across_turns(monkeypatch, tmp_path):
    import run_agent

    monkeypatch.setenv("HERMES_MAX_SAME_FILE_READS", "5")
    monkeypatch.setenv("HERMES_HARD_MAX_SAME_FILE_READS", "10")
    calls = {"count": 0}

    def fake_handle_function_call(function_name, function_args, effective_task_id, **kwargs):
        calls["count"] += 1
        return "file content"

    monkeypatch.setattr(run_agent, "handle_function_call", fake_handle_function_call)

    agent = _minimal_agent()
    path = tmp_path / "session.py"
    path.write_text("file content", encoding="utf-8")

    class _ToolCall:
        def __init__(self, call_id: str) -> None:
            self.id = call_id
            self.function = SimpleNamespace(
                name="read_file",
                arguments=json.dumps({"path": str(path)}),
            )

    messages: list[dict] = []
    for i in range(7):
        agent._tool_dedup_cache.clear()  # run_conversation clears this per turn.
        assistant_message = SimpleNamespace(tool_calls=[_ToolCall(f"call-{i}")])
        agent._execute_tool_calls_sequential(
            assistant_message, messages, effective_task_id="task", api_call_count=i
        )

    assert calls["count"] == 5
    assert agent._file_read_counts[str(path.resolve())] == 7
    assert "already read 6 times" in messages[5]["content"]
    assert "already read 7 times" in messages[6]["content"]


def test_repeated_file_read_hard_ceiling_refuses(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_MAX_SAME_FILE_READS", "2")
    monkeypatch.setenv("HERMES_HARD_MAX_SAME_FILE_READS", "3")
    agent = _minimal_agent()
    path = tmp_path / "session.py"
    path.write_text("file content", encoding="utf-8")

    results = [
        agent._maybe_short_circuit_file_read("read_file", {"path": str(path)})
        for _ in range(4)
    ]

    assert results[:2] == [None, None]
    assert "already read 3 times" in results[2]
    assert "REFUSED read_file" in results[3]


def test_streaming_timeout_growing_prompt_aborts_without_escalation(monkeypatch):
    monkeypatch.setenv("HERMES_STREAMING_TIMEOUT_HARD_CEILING_SECONDS", "3600")
    agent = _minimal_agent()
    agent._streaming_timeout_streak = 0
    agent._last_streaming_timeout_tokens = None
    agent._streaming_timeout_wall_start_monotonic = time.monotonic()
    agent._last_streaming_request_started_at = time.monotonic()

    assert agent._record_streaming_timeout_or_abort(
        approx_tokens=1000, message_count=10, elapsed_seconds=300
    ) is None
    abort = agent._record_streaming_timeout_or_abort(
        approx_tokens=1300, message_count=14, elapsed_seconds=320
    )

    assert abort is not None
    assert "prompt grew from ~1,000 to ~1,300 tokens" in abort
    assert agent._streaming_timeout_streak == 1


def test_streaming_timeout_static_prompt_still_escalates(monkeypatch):
    monkeypatch.delenv("HERMES_API_TIMEOUT", raising=False)
    monkeypatch.delenv("HERMES_STREAMING_TIMEOUT_HARD_CEILING_SECONDS", raising=False)
    agent = _minimal_agent()
    agent.provider = "openrouter"
    agent._base_url_lower = "https://openrouter.ai/api/v1"
    agent._streaming_timeout_streak = 0
    agent._last_streaming_timeout_tokens = None
    agent._streaming_timeout_wall_start_monotonic = time.monotonic()
    agent._last_streaming_request_started_at = time.monotonic()

    assert agent._record_streaming_timeout_or_abort(
        approx_tokens=1000, message_count=10, elapsed_seconds=300
    ) is None
    assert agent._api_timeout_seconds() == pytest.approx(DEFAULT_API_TIMEOUT_SECONDS * 1.5)
    assert agent._record_streaming_timeout_or_abort(
        approx_tokens=1100, message_count=10, elapsed_seconds=450
    ) is None
    assert agent._api_timeout_seconds() == pytest.approx(DEFAULT_API_TIMEOUT_SECONDS * 2.25)


def test_streaming_timeout_hard_wall_clock_ceiling_aborts(monkeypatch):
    monkeypatch.setenv("HERMES_STREAMING_TIMEOUT_HARD_CEILING_SECONDS", "10")
    agent = _minimal_agent()
    agent._streaming_timeout_streak = 1
    agent._last_streaming_timeout_tokens = 1000
    agent._streaming_timeout_wall_start_monotonic = time.monotonic() - 11
    agent._last_streaming_request_started_at = time.monotonic() - 11

    abort = agent._record_streaming_timeout_or_abort(
        approx_tokens=1000, message_count=10, elapsed_seconds=11
    )

    assert abort is not None
    assert "retry ceiling reached" in abort
