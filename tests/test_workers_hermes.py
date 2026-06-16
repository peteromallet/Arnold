"""Direct Hermes worker tests for megaplan.workers."""

from __future__ import annotations

from argparse import Namespace
from contextlib import nullcontext
from dataclasses import replace
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

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


def test_hermes_high_token_streaming_matches_fireworks_for_direct_providers() -> None:
    from arnold.pipelines.megaplan.workers.hermes import _streaming_run_kwargs

    assert _streaming_run_kwargs("fireworks:accounts/fireworks/models/deepseek-v4-pro", 32768)
    assert _streaming_run_kwargs("deepseek:deepseek-v4-pro", 32768)
    assert _streaming_run_kwargs("kimi:kimi-k2.7-code", 32768)
    assert not _streaming_run_kwargs("deepseek:deepseek-v4-pro", 4096)


def test_hermes_template_and_defaults_prefer_non_null_union_type() -> None:
    from arnold.pipelines.megaplan.workers.hermes import (
        _fill_schema_defaults,
        _schema_template,
    )

    schema = {
        "type": "object",
        "required": ["flag_verifications"],
        "properties": {
            "flag_verifications": {
                "type": ["array", "null"],
                "items": {"type": "object"},
            },
        },
    }

    template = json.loads(_schema_template(schema))
    payload: dict[str, object] = {}
    _fill_schema_defaults(payload, schema)

    assert template["flag_verifications"] == []
    assert payload["flag_verifications"] == []


def test_hermes_plan_cleaner_normalizes_flattened_success_criterion() -> None:
    from arnold.pipelines.megaplan.workers.hermes import clean_parsed_payload

    schema = {
        "type": "object",
        "required": ["plan", "questions", "success_criteria", "assumptions"],
        "additionalProperties": False,
        "properties": {
            "plan": {"type": "string"},
            "questions": {"type": "array", "items": {"type": "string"}},
            "success_criteria": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["criterion", "priority", "requires"],
                    "additionalProperties": False,
                    "properties": {
                        "criterion": {"type": "string"},
                        "priority": {"type": "string", "enum": ["must", "should", "info"]},
                        "requires": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "assumptions": {"type": "array", "items": {"type": "string"}},
        },
    }
    payload = {
        "plan": "# Implementation Plan\n\nDo the work.",
        "questions": [],
        "assumptions": [],
        "criterion": "Audio resumes after trimming while playing",
        "priority": "must",
        "requires": ["run_tests"],
    }

    clean_parsed_payload(payload, schema, "plan")

    assert "criterion" not in payload
    assert "priority" not in payload
    assert "requires" not in payload
    assert payload["success_criteria"] == [
        {
            "criterion": "Audio resumes after trimming while playing",
            "priority": "must",
            "requires": ["run_tests"],
        }
    ]


def test_hermes_execute_cleaner_strips_batch_bookkeeping_fields() -> None:
    from arnold.pipelines.megaplan.workers.hermes import clean_parsed_payload

    payload = {
        "batch_id": "batch-5",
        "status": "completed",
        "batch_status": "complete",
        "tasks": [],
        "summary": "done",
    }
    schema = {
        "type": "object",
        "properties": {
            "tasks": {"type": "array", "items": {"type": "object"}},
            "summary": {"type": "string"},
        },
    }

    clean_parsed_payload(payload, schema, "execute")

    assert payload == {"tasks": [], "summary": "done"}


def test_hermes_defaults_fill_nested_required_array_items() -> None:
    from arnold.pipelines.megaplan.workers.hermes import _fill_schema_defaults

    schema = {
        "type": "object",
        "required": ["tasks", "sense_checks", "validation"],
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "id",
                        "kind",
                        "files_changed",
                        "commands_run",
                        "auto_attributed_files",
                        "stance",
                        "stop_signal",
                    ],
                    "properties": {
                        "id": {"type": "string"},
                        "kind": {
                            "type": ["string", "null"],
                            "enum": ["code", "audit", "test"],
                        },
                        "files_changed": {"type": "array", "items": {"type": "string"}},
                        "commands_run": {"type": "array", "items": {"type": "string"}},
                        "auto_attributed_files": {"type": ["boolean", "null"]},
                        "stance": {
                            "type": ["object", "null"],
                            "properties": {"what_changed": {"type": "string"}},
                            "required": ["what_changed"],
                        },
                        "stop_signal": {
                            "type": ["object", "null"],
                            "properties": {"requested": {"type": "boolean"}},
                            "required": ["requested"],
                        },
                    },
                },
            },
            "sense_checks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "executor_note", "verdict"],
                    "properties": {
                        "id": {"type": "string"},
                        "executor_note": {"type": "string"},
                        "verdict": {"type": "string"},
                    },
                },
            },
            "validation": {
                "type": "object",
                "required": ["plan_steps_covered", "coverage_complete"],
                "properties": {
                    "plan_steps_covered": {"type": "array", "items": {"type": "object"}},
                    "coverage_complete": {"type": "boolean"},
                },
            },
        },
    }
    payload = {
        "tasks": [{"id": "T1"}],
        "sense_checks": [{"id": "SC1"}],
        "validation": {},
    }

    _fill_schema_defaults(payload, schema)

    task = payload["tasks"][0]
    assert task["kind"] == "code"
    assert task["files_changed"] == []
    assert task["commands_run"] == []
    assert task["auto_attributed_files"] is False
    assert task["stance"] is None
    assert task["stop_signal"] is None
    assert payload["sense_checks"][0]["executor_note"] == ""
    assert payload["sense_checks"][0]["verdict"] == ""
    assert payload["validation"] == {
        "plan_steps_covered": [],
        "coverage_complete": False,
    }


def test_hermes_schema_template_shows_nested_required_item_shape() -> None:
    from arnold.pipelines.megaplan.workers.hermes import _schema_template

    schema = {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "kind": {"type": "string", "enum": ["code", "test"]},
                        "files_changed": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "validation": {
                "type": "object",
                "properties": {
                    "coverage_complete": {"type": "boolean"},
                },
            },
        },
    }

    template = json.loads(_schema_template(schema))

    assert template["tasks"] == [
        {"id": "...", "kind": "code", "files_changed": ["..."]}
    ]
    assert template["validation"] == {"coverage_complete": True}


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

        def set_response_format(self, *_args, **_kwargs):
            return None

        def set_response_format(self, *_args, **_kwargs):
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


# ── T7: Registry-based template dispatch regression tests ────────────────


def test_hermes_template_dispatch_uses_registry_for_file_fill_phases(
    tmp_path: Path,
) -> None:
    """All file_fill phases dispatch via registry lookup, not hardcoded sets."""
    from arnold.pipelines.megaplan.template_registry import (
        get_phases_by_mode,
        get_template_registration,
    )
    from arnold.pipelines.megaplan.workers.hermes import _toolsets_for_phase

    file_fill_phases = get_phases_by_mode("file_fill")
    # Sanity: all expected T7 phases are registered
    assert file_fill_phases >= {"critique", "review", "gate", "finalize", "critique_evaluator"}

    for phase in file_fill_phases:
        reg = get_template_registration(phase)
        assert reg is not None, f"Missing registration for {phase}"
        assert reg.mode == "file_fill", f"Wrong mode for {phase}: {reg.mode}"
        assert reg.scratch_filename, f"Missing scratch filename for {phase}"
        # Verify toolsets returns something (or None) for every phase
        toolsets = _toolsets_for_phase(phase)
        if toolsets is not None:
            assert isinstance(toolsets, list), f"toolsets for {phase} should be list or None"


def test_hermes_template_dispatch_preserves_deferred_phases(
    tmp_path: Path,
) -> None:
    """Prep and other deferred phases still resolve via registry with mode=deferred."""
    from arnold.pipelines.megaplan.template_registry import get_template_registration

    for phase in ("prep", "prep-triage", "prep-distill", "prep-research", "feedback", "loop_plan", "loop_execute"):
        reg = get_template_registration(phase)
        assert reg is not None, f"Missing registration for {phase}"
        assert reg.mode == "deferred", f"Expected deferred mode for {phase}, got {reg.mode}"


def test_hermes_template_dispatch_skips_markdown_and_subloop(
    tmp_path: Path,
) -> None:
    """Markdown-exempt and subloop-exempt phases have no structured-output template."""
    from arnold.pipelines.megaplan.template_registry import get_template_registration

    for phase in ("plan", "revise"):
        reg = get_template_registration(phase)
        assert reg is not None, f"Missing registration for {phase}"
        assert reg.mode == "markdown_exempt", f"Expected markdown_exempt for {phase}, got {reg.mode}"
        assert not reg.scratch_filename, f"{phase} should have no scratch filename"

    for phase in ("tiebreaker_researcher", "tiebreaker_challenger"):
        reg = get_template_registration(phase)
        assert reg is not None, f"Missing registration for {phase}"
        assert reg.mode == "subloop_exempt", f"Expected subloop_exempt for {phase}, got {reg.mode}"
        assert not reg.scratch_filename, f"{phase} should have no scratch filename"


def test_hermes_template_dispatch_execute_is_batch_assembly(tmp_path: Path) -> None:
    """Execute phase uses batch_assembly mode, not file_fill."""
    from arnold.pipelines.megaplan.template_registry import get_template_registration

    reg = get_template_registration("execute")
    assert reg is not None
    assert reg.mode == "batch_assembly", f"Expected batch_assembly for execute, got {reg.mode}"


def test_hermes_file_fill_scratch_created_for_all_phases(tmp_path: Path) -> None:
    """Every file_fill phase has a scratch filename in the registry."""
    from arnold.pipelines.megaplan.template_registry import get_template_registration
    from arnold.pipelines.megaplan.template_registry import get_phases_by_mode

    file_fill = get_phases_by_mode("file_fill")
    for phase in sorted(file_fill):
        reg = get_template_registration(phase)
        assert reg.scratch_filename.endswith(".json"), (
            f"{phase} scratch filename should be .json, got {reg.scratch_filename!r}"
        )


def test_hermes_finalize_has_file_fill_registry_but_no_file_tools(tmp_path: Path) -> None:
    """Finalize is file_fill but _toolsets_for_phase returns None (no file tools).
    Registry-based dispatch must still create the scratch file; only
    instructions differ (inline JSON vs OUTPUT FILE)."""
    from arnold.pipelines.megaplan.workers.hermes import _toolsets_for_phase
    from arnold.pipelines.megaplan.template_registry import get_template_registration

    reg = get_template_registration("finalize")
    assert reg is not None
    assert reg.mode == "file_fill"
    assert reg.scratch_filename == "finalize_output.json"

    toolsets = _toolsets_for_phase("finalize")
    assert toolsets is None, "finalize must have no toolsets so file_fill dispatch uses inline instructions"


def test_hermes_gate_and_critique_evaluator_are_file_fill_with_file_tools(
    tmp_path: Path,
) -> None:
    """Gate and critique_evaluator are file_fill phases with file tools,
    so registry-based dispatch must append OUTPUT FILE instructions."""
    from arnold.pipelines.megaplan.workers.hermes import _toolsets_for_phase
    from arnold.pipelines.megaplan.template_registry import get_template_registration

    for phase in ("gate", "critique_evaluator"):
        reg = get_template_registration(phase)
        assert reg.mode == "file_fill", f"{phase} should be file_fill"
        toolsets = _toolsets_for_phase(phase)
        assert "file" in (toolsets or []), (
            f"{phase} must have 'file' in toolsets to trigger OUTPUT FILE instructions"
        )


def test_hermes_run_step_scratch_file_created_for_gate(
    tmp_path: Path,
) -> None:
    """run_hermes_step for 'gate' (file_fill, has file tools) creates the scratch
    template and appends OUTPUT FILE instructions."""
    from arnold.pipelines.megaplan.workers.hermes import run_hermes_step

    repo_root = Path(__file__).resolve().parents[1]
    plan_dir, state = _mock_state(tmp_path)
    prompt_texts: list[str] = []

    class FakeSessionDB:
        def __init__(self, db_path=None):
            self.db_path = db_path

    class FakeAIAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self._print_fn = None
            self.reasoning_callback = None
            self._executing_tools = False

        def run_conversation(self, **run_kwargs):
            prompt_texts.append(str(run_kwargs.get("user_message", "")))
            return {
                "final_response": '{"verdict": "approved", "justification": "ok"}',
                "messages": [{"role": "assistant", "content": '{"verdict": "approved", "justification": "ok"}'}],
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "model": self.kwargs["model"],
            }

        def clear_interrupt(self):
            return None

        def interrupt(self, _reason=None):
            return None

    def _fake_parse_agent_output(_agent, result, output_path=None, **kwargs):
        # Assert the scratch file was written
        if output_path and output_path.exists():
            assert "gate_output.json" in str(output_path)
            content = output_path.read_text(encoding="utf-8")
            import json as _json
            parsed = _json.loads(content)
            assert isinstance(parsed, dict)
        return {"verdict": "approved", "justification": "ok"}, result.get("final_response", "")

    def _capture_spy(invocation, output):
        return type("Capture", (), {"legacy_payload": output})()

    def _render_prompt_spy(*args, **kwargs):
        return type("RenderedStep", (), {"prompt": kwargs.get("prompt_override") or "rendered prompt"})()

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
            "gate",
            state,
            plan_dir,
            root=repo_root,
            fresh=True,
            model="qwen3-32b",
        )

    # Verify gate scratch file was created in plan_dir
    gate_scratch = plan_dir / "gate_output.json"
    assert gate_scratch.exists(), "gate_output.json scratch file must be created by dispatch"
    content = gate_scratch.read_text(encoding="utf-8")
    assert content.strip(), "scratch file must not be empty"

    # Verify OUTPUT FILE instructions were appended to the prompt
    prompt_used = prompt_texts[0] if prompt_texts else ""
    assert "OUTPUT FILE:" in prompt_used, (
        "file_fill phase with file tools must append OUTPUT FILE instructions"
    )
    assert "gate_output.json" in prompt_used

    assert result.payload["verdict"] == "approved"


def test_hermes_file_fill_uses_registered_builder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """file_fill dispatch must call TemplateRegistration.builder."""
    from arnold.pipelines.megaplan import template_registry
    from arnold.pipelines.megaplan.workers.hermes import run_hermes_step

    repo_root = Path(__file__).resolve().parents[1]
    plan_dir, state = _mock_state(tmp_path)
    builder_calls: list[tuple[Path, dict]] = []
    prompt_texts: list[str] = []

    original = template_registry.get_template_registration("gate")
    assert original is not None

    def fake_builder(builder_plan_dir: Path, builder_state: dict) -> Path:
        builder_calls.append((builder_plan_dir, builder_state))
        path = builder_plan_dir / "gate_output.json"
        path.write_text('{"verdict": "", "justification": ""}', encoding="utf-8")
        return path

    monkeypatch.setitem(
        template_registry._TEMPLATE_REGISTRY,
        "gate",
        replace(original, builder=fake_builder),
    )

    class FakeSessionDB:
        def __init__(self, db_path=None):
            self.db_path = db_path

    class FakeAIAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self._print_fn = None
            self.reasoning_callback = None
            self._executing_tools = False

        def run_conversation(self, **run_kwargs):
            prompt_texts.append(str(run_kwargs.get("user_message", "")))
            return {
                "final_response": '{"verdict": "approved", "justification": "ok"}',
                "messages": [{"role": "assistant", "content": '{"verdict": "approved", "justification": "ok"}'}],
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "model": self.kwargs["model"],
            }

        def clear_interrupt(self):
            return None

        def interrupt(self, _reason=None):
            return None

    def _fake_parse_agent_output(_agent, result, output_path=None, **kwargs):
        return {"verdict": "approved", "justification": "ok"}, result.get("final_response", "")

    def _capture_spy(invocation, output):
        return type("Capture", (), {"legacy_payload": output})()

    def _render_prompt_spy(*args, **kwargs):
        return type("RenderedStep", (), {"prompt": kwargs.get("prompt_override") or "rendered prompt"})()

    with (
        patch("arnold.pipelines.megaplan.workers.hermes._import_hermes_runtime", return_value=(FakeAIAgent, FakeSessionDB)),
        patch("arnold.pipelines.megaplan.workers.hermes.parse_agent_output", side_effect=_fake_parse_agent_output),
        patch("arnold.pipelines.megaplan.workers.hermes.clean_parsed_payload", return_value=None),
        patch("arnold.pipelines.megaplan.workers.hermes.capture_step_output", side_effect=_capture_spy),
        patch("arnold.pipelines.megaplan.workers.hermes.render_prompt_for_dispatch", side_effect=_render_prompt_spy),
        patch("arnold.pipelines.megaplan.runtime.key_pool.resolve_model", return_value=("qwen3-32b", {})),
        patch("arnold.pipelines.megaplan.runtime.sandbox.install_sandbox", return_value=nullcontext()),
    ):
        run_hermes_step(
            "gate",
            state,
            plan_dir,
            root=repo_root,
            fresh=True,
            model="qwen3-32b",
        )

    assert builder_calls == [(plan_dir, state)]
    assert "gate_output.json" in prompt_texts[0]


def test_hermes_run_step_finalize_scratch_created_no_file_tools(
    tmp_path: Path,
) -> None:
    """run_hermes_step for 'finalize' (file_fill, NO file tools) creates the scratch
    template but appends inline JSON instructions (since no file tools)."""
    from arnold.pipelines.megaplan.workers.hermes import run_hermes_step

    repo_root = Path(__file__).resolve().parents[1]
    plan_dir, state = _mock_state(tmp_path)
    prompt_texts: list[str] = []

    class FakeSessionDB:
        def __init__(self, db_path=None):
            self.db_path = db_path

    class FakeAIAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self._print_fn = None
            self.reasoning_callback = None
            self._executing_tools = False

        def run_conversation(self, **run_kwargs):
            prompt_texts.append(str(run_kwargs.get("user_message", "")))
            return {
                "final_response": '{"plan_steps": [], "tasks": []}',
                "messages": [{"role": "assistant", "content": '{"plan_steps": [], "tasks": []}'}],
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "model": self.kwargs["model"],
            }

        def clear_interrupt(self):
            return None

        def interrupt(self, _reason=None):
            return None

        def set_response_format(self, *_args, **_kwargs):
            return None

    def _fake_parse_agent_output(_agent, result, output_path=None, **kwargs):
        return {"plan_steps": [], "tasks": []}, result.get("final_response", "")

    def _capture_spy(invocation, output):
        return type("Capture", (), {"legacy_payload": output})()

    def _render_prompt_spy(*args, **kwargs):
        return type("RenderedStep", (), {"prompt": kwargs.get("prompt_override") or "rendered prompt"})()

    with (
        patch("arnold.pipelines.megaplan.workers.hermes._import_hermes_runtime", return_value=(FakeAIAgent, FakeSessionDB)),
        patch("arnold.pipelines.megaplan.workers.hermes.parse_agent_output", side_effect=_fake_parse_agent_output),
        patch("arnold.pipelines.megaplan.workers.hermes.clean_parsed_payload", return_value=None),
        patch("arnold.pipelines.megaplan.workers.hermes.capture_step_output", side_effect=_capture_spy),
        patch("arnold.pipelines.megaplan.workers.hermes.render_prompt_for_dispatch", side_effect=_render_prompt_spy),
        patch("arnold.pipelines.megaplan.runtime.key_pool.resolve_model", return_value=("deepseek-v4-pro", {})),
        patch("arnold.pipelines.megaplan.runtime.sandbox.install_sandbox", return_value=nullcontext()),
        # _pre_dispatch_budget_check calls render_step_message which needs a
        # recognized model family; deepseek-v4-pro is a recognized normalized name.
    ):
        run_hermes_step(
            "finalize",
            state,
            plan_dir,
            root=repo_root,
            fresh=True,
            model="deepseek-v4-pro",
        )

    # Verify scratch file was created
    scratch = plan_dir / "finalize_output.json"
    assert scratch.exists(), "finalize_output.json scratch file must be created by dispatch"
    content = scratch.read_text(encoding="utf-8")
    assert content.strip(), "scratch file must not be empty"

    # Verify inline JSON instructions (NOT OUTPUT FILE since no file tools)
    prompt_used = prompt_texts[0] if prompt_texts else ""
    assert "OUTPUT FILE:" not in prompt_used, (
        "file_fill phase WITHOUT file tools must NOT have OUTPUT FILE instructions"
    )
    assert "raw JSON" in prompt_used, (
        "file_fill phase without file tools must have inline JSON instructions"
    )


def test_hermes_run_step_prep_preserves_deferred_behaviour(
    tmp_path: Path,
) -> None:
    """run_hermes_step for 'prep' (deferred mode) preserves pre-T7 generic template
    behaviour — scratch file with OUTPUT FILE instructions when toolsets present."""
    from arnold.pipelines.megaplan.workers.hermes import run_hermes_step

    repo_root = Path(__file__).resolve().parents[1]
    plan_dir, state = _mock_state(tmp_path)
    prompt_texts: list[str] = []

    class FakeSessionDB:
        def __init__(self, db_path=None):
            self.db_path = db_path

    class FakeAIAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self._print_fn = None
            self.reasoning_callback = None
            self._executing_tools = False

        def run_conversation(self, **run_kwargs):
            prompt_texts.append(str(run_kwargs.get("user_message", "")))
            return {
                "final_response": '{"plan": "# P"}',
                "messages": [{"role": "assistant", "content": '{"plan": "# P"}'}],
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "model": self.kwargs["model"],
            }

        def clear_interrupt(self):
            return None

        def interrupt(self, _reason=None):
            return None

    def _fake_parse_agent_output(_agent, result, output_path=None, **kwargs):
        return {"plan": "# P"}, result.get("final_response", "")

    def _capture_spy(invocation, output):
        return type("Capture", (), {"legacy_payload": output})()

    def _render_prompt_spy(*args, **kwargs):
        return type("RenderedStep", (), {"prompt": kwargs.get("prompt_override") or "rendered prompt"})()

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
            "prep",
            state,
            plan_dir,
            root=repo_root,
            fresh=True,
            model="qwen3-32b",
        )

    # Prep (deferred, file-readonly tools) gets generic template + OUTPUT FILE
    prep_scratch = plan_dir / "prep_output.json"
    assert prep_scratch.exists(), "prep must still write generic template in deferred mode"

    prompt_used = prompt_texts[0] if prompt_texts else ""
    assert "OUTPUT FILE:" in prompt_used, (
        "deferred phase with toolsets must append OUTPUT FILE instructions"
    )


# ── T7: Shannon pass-through regression ──────────────────────────────────


def test_shannon_pass_through_does_not_import_hermes_registry() -> None:
    """Shannon workers (run_claude_step) should NOT import or depend on
    hermes-specific template registry dispatch.  The registry is only used
    inside workers/hermes.py, never leaked into _impl.py or shannon paths."""
    import importlib
    import sys

    # Ensure template_registry isn't transitively imported by _impl
    # (it should only be in hermes.py)
    impl_mod = sys.modules.get("arnold.pipelines.megaplan.workers._impl")
    if impl_mod is None:
        impl_mod = importlib.import_module("arnold.pipelines.megaplan.workers._impl")

    # Check that template_registry is NOT in the module's namespace or imports
    reg_in_impl = "template_registry" in dir(impl_mod)
    assert not reg_in_impl, (
        "_impl.py must NOT import template_registry — it is a hermes-only concern"
    )


def test_shannon_pass_through_step_schema_filenames_unchanged() -> None:
    """STEP_SCHEMA_FILENAMES in _impl.py is built from StepContract registry and
    must still produce the same keys for Shannon-compatible phases."""
    from arnold.pipelines.megaplan.workers._impl import STEP_SCHEMA_FILENAMES

    # Shannon handles these phases; their schema filenames must be present
    for step in ("prep", "execute", "review", "plan", "critique", "finalize", "gate"):
        assert step in STEP_SCHEMA_FILENAMES, (
            f"STEP_SCHEMA_FILENAMES must contain {step!r} for Shannon pass-through"
        )
        assert STEP_SCHEMA_FILENAMES[step].endswith(".json"), (
            f"Schema filename for {step!r} must be a .json path"
        )
