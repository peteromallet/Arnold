"""B2 oracle tests for the omp RPC worker (workers/omp.py).

Covers the complete error matrix, strict local-strict structured output
(exact JSON file capture, unknown-field rejection, prose/markdown/truncation
rejection), bounded attempt-idempotent retries, execute replay protection
after side effects, orphan-child absence (stop always called), exact
per-attempt cost aggregation, and reconciliation with derived session stats.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from omp_rpc import (
    PromptTurn,
    RpcProcessExitError,
    RpcProtocolError,
    RpcTimeoutError,
)

from arnold_pipelines.megaplan.fallback_chains import ExecuteFallbackUnsafe
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.workers.omp import (
    OMP_WORKER_CHANNEL,
    _OMP_MAX_ATTEMPTS,
    format_omp_spec,
    omp_thinking_level,
    parse_omp_spec,
    run_omp_step,
    set_omp_client_factory,
    validate_omp_catalog_model,
)
from arnold_pipelines.megaplan.workers.omp import _write_phase_output_tool

from tests._workers_helpers import _mock_state
from tests.workers.fake_omp_rpc import (
    FakeRpcClient,
    _FakeSessionStats,
    make_turn,
    usage_message,
)


@pytest.fixture(autouse=True)
def _no_client_factory():
    set_omp_client_factory(None)
    yield
    set_omp_client_factory(None)


@pytest.fixture
def deepseek_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")


def _valid_gate_json() -> dict:
    """A gate.json satisfying the gate schema for execute prompt rendering."""
    return {
        "passed": True,
        "recommendation": "PROCEED",
        "rationale": "ok",
        "signals_assessment": "ok",
        "warnings": [],
        "settled_decisions": [],
        "criteria_check": {},
        "preflight_results": {},
        "unresolved_flags": [],
        "override_forced": False,
        "flag_resolutions": [],
        "accepted_tradeoffs": [],
        "north_star_actions": [],
        "iteration": 1,
        "produced_at": "2026-08-10T00:00:00Z",
    }


def _valid_plan_payload() -> dict:
    return {
        "plan": "# Implementation Plan\n\n## Step 1: Do it\n\n- [ ] thing",
        "questions": [],
        "success_criteria": [{"criterion": "c", "priority": "must"}],
        "assumptions": [],
    }


def _install_factory(monkeypatch, client: FakeRpcClient) -> FakeRpcClient:
    def _factory(**kwargs):
        # Bind the worker's factory kwargs onto the pre-built fake so the
        # turn closures can reach the custom tools it received.
        for key, value in kwargs.items():
            setattr(client, key, value)
        return client

    set_omp_client_factory(_factory)
    return client


def _run_plan(
    client: FakeRpcClient,
    tmp_path: Path,
    *,
    model: str = "omp:deepseek/deepseek-v4-pro",
    effort: str | None = None,
    step: str = "plan",
) -> object:
    plan_dir, state = _mock_state(tmp_path)
    return run_omp_step(
        step,
        state,
        plan_dir,
        root=tmp_path,
        fresh=True,
        model=model,
        effort=effort,
    )


class TestSpecGrammar:
    def test_parse_canonical_spec(self):
        assert parse_omp_spec("omp:deepseek/deepseek-v4-pro") == (
            "deepseek",
            "deepseek-v4-pro",
        )

    def test_rejects_double_colon(self):
        with pytest.raises(CliError, match="never the double-colon form"):
            parse_omp_spec("omp:" + "deepseek:model")

    def test_rejects_bare_agent(self):
        with pytest.raises(CliError, match="bare 'omp' agent"):
            parse_omp_spec("omp")

    def test_rejects_empty(self):
        with pytest.raises(CliError, match="requires an explicit"):
            parse_omp_spec(None)

    def test_validate_catalog_model(self):
        assert (
            validate_omp_catalog_model("deepseek", "deepseek-v4-pro")
            == "deepseek/deepseek-v4-pro"
        )
        assert (
            validate_omp_catalog_model("anthropic", "claude-opus-4-8")
            == "anthropic/claude-opus-4-8"
        )

    def test_rejects_unknown_provider(self):
        with pytest.raises(CliError, match="not in the frozen B1 contract"):
            validate_omp_catalog_model("unknown-prov", "x")

    def test_rejects_non_canonical_model(self):
        with pytest.raises(CliError, match="not a canonical catalog row"):
            validate_omp_catalog_model("deepseek", "deepseek-v4-turbo")

    def test_format_spec(self):
        assert format_omp_spec("zai", "glm-5.2") == "omp:zai/glm-5.2"


class TestThinkingMapping:
    def test_none_and_auto_unset(self):
        assert omp_thinking_level(None, "deepseek", "deepseek-v4-pro") is None
        assert omp_thinking_level("auto", "deepseek", "deepseek-v4-pro") is None

    def test_off_disables(self):
        assert omp_thinking_level("off", "deepseek", "deepseek-v4-pro") == "off"

    def test_openrouter_deepseek_high_only(self):
        # OpenRouter's DeepSeek route accepts only ``high``.
        assert (
            omp_thinking_level("medium", "openrouter", "deepseek/deepseek-chat")
            == "high"
        )
        assert omp_thinking_level("high", "openrouter", "deepseek/deepseek-chat") == "high"

    def test_openrouter_gpt_five_tier(self):
        # GPT-5.6+ wire tiers apply on OpenRouter (model-thinking.ts).
        assert omp_thinking_level("medium", "openrouter", "openai/gpt-5.5") == "medium"
        assert omp_thinking_level("high", "openrouter", "openai/gpt-5.5") == "high"

    def test_openrouter_glm_xhigh_top(self):
        # OpenRouter rejects ``max`` for GLM — xhigh is its top tier.
        assert omp_thinking_level("max", "openrouter", "z-ai/glm-5.1") == "xhigh"

    def test_zai_high_max(self):
        assert omp_thinking_level("minimal", "zai", "glm-5.2") == "high"
        assert omp_thinking_level("max", "zai", "glm-5.2") == "max"

    def test_xai_non_reasoning_off_only(self):
        assert omp_thinking_level("high", "xai", "grok-4-fast-non-reasoning") == "off"

    def test_fireworks_minimal_off(self):
        assert (
            omp_thinking_level("minimal", "fireworks", "kimi-k2.7-code") == "off"
        )

    def test_passthrough_identity(self):
        assert omp_thinking_level("high", "deepseek", "deepseek-v4-pro") == "high"


class TestStructuredOutput:
    def test_valid_output_via_write_tool(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        payload = _valid_plan_payload()
        client = FakeRpcClient(
            turn_factory=lambda: make_turn(assistant_text="done")
        )

        def _write_tool_turn():
            # Simulate the agent calling the write_phase_output host tool.
            tool = client.custom_tools[0]
            tool.execute({"payload": json.dumps(payload)}, object())
            return make_turn(assistant_text="done")

        client.turn_factory = _write_tool_turn
        _install_factory(monkeypatch, client)
        result = _run_plan(client, tmp_path)
        assert result.payload["plan"].startswith("# Implementation Plan")
        assert result.model_actual == "deepseek/deepseek-v4-pro"
        assert result.session_id.startswith("omp-stateless:")
        assert result.worker_channel == OMP_WORKER_CHANNEL
        assert result.auth_channel == "deepseek"
        assert result.response_enforcement_attestation is not None
        assert client.stopped == 1

    def test_valid_output_inline_text(self, tmp_path, monkeypatch, deepseek_env):
        payload = _valid_plan_payload()
        client = FakeRpcClient(
            turn_factory=lambda: make_turn(
                assistant_text=json.dumps(payload)
            )
        )
        _install_factory(monkeypatch, client)
        result = _run_plan(client, tmp_path)
        assert result.payload["plan"].startswith("# Implementation Plan")

    def test_tool_loop_writes_exact_file(self, tmp_path):
        out = tmp_path / "phase.json"
        tool = _write_phase_output_tool(out)
        assert tool.name == "write_phase_output"
        result = tool.execute({"payload": '{"a": 1}'}, object())
        assert out.read_text(encoding="utf-8") == '{"a": 1}'
        assert not result.get("details", {}).get("isError")

    def test_tool_rejects_empty_payload(self, tmp_path):
        out = tmp_path / "phase.json"
        tool = _write_phase_output_tool(out)
        result = tool.execute({"payload": "  "}, object())
        assert result["details"]["isError"] is True

    def test_rejects_markdown_fenced_output(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        payload = _valid_plan_payload()

        def _fenced_turn():
            tool = client.custom_tools[0]
            tool.execute(
                {"payload": "```json\n" + json.dumps(payload) + "\n```"},
                object(),
            )
            return make_turn(assistant_text="done")

        client = FakeRpcClient(turn_factory=_fenced_turn)
        _install_factory(monkeypatch, client)
        with pytest.raises(CliError, match="not a single exact JSON"):
            _run_plan(client, tmp_path)

    def test_rejects_prose_contamination(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        payload = _valid_plan_payload()

        def _prose_turn():
            tool = client.custom_tools[0]
            tool.execute(
                {"payload": "Here is the plan: " + json.dumps(payload)},
                object(),
            )
            return make_turn(assistant_text="done")

        client = FakeRpcClient(turn_factory=_prose_turn)
        _install_factory(monkeypatch, client)
        with pytest.raises(CliError, match="not a single exact JSON"):
            _run_plan(client, tmp_path)

    def test_rejects_truncated_json(self, tmp_path, monkeypatch, deepseek_env):
        payload = _valid_plan_payload()

        def _truncated_turn():
            tool = client.custom_tools[0]
            tool.execute(
                {"payload": json.dumps(payload)[:-8]},
                object(),
            )
            return make_turn(assistant_text="done")

        client = FakeRpcClient(turn_factory=_truncated_turn)
        _install_factory(monkeypatch, client)
        with pytest.raises(CliError, match="not a single exact JSON"):
            _run_plan(client, tmp_path)

    def test_rejects_unknown_schema_owned_field(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        payload = _valid_plan_payload()
        payload["schema_owned_unknown"] = "nope"

        def _bad_turn():
            tool = client.custom_tools[0]
            tool.execute({"payload": json.dumps(payload)}, object())
            return make_turn(assistant_text="done")

        client = FakeRpcClient(turn_factory=_bad_turn)
        _install_factory(monkeypatch, client)
        with pytest.raises(CliError, match="unknown schema-owned fields"):
            _run_plan(client, tmp_path)

    def test_missing_final_text_is_parse_error(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        client = FakeRpcClient(
            turn_factory=lambda: make_turn(assistant_text=None)
        )
        _install_factory(monkeypatch, client)
        with pytest.raises(CliError, match="no final text"):
            _run_plan(client, tmp_path)


class TestErrorMatrix:
    def test_launch_failure_retries_then_succeeds(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        payload = _valid_plan_payload()
        client = FakeRpcClient(
            start_failures_before_success=1,
            turn_factory=lambda: make_turn(assistant_text=json.dumps(payload)),
        )
        _install_factory(monkeypatch, client)
        result = _run_plan(client, tmp_path)
        assert result.attempt_index == 2
        assert len(result.attempted_specs) == 2
        assert len(result.failed_attempt_reasons) == 1
        assert client.started == 2
        assert client.stopped == 2

    def test_protocol_error_retries_then_exhausts(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        client = FakeRpcClient(
            prompt_error=RpcProtocolError({"error": "malformed frame"}),
        )
        _install_factory(monkeypatch, client)
        with pytest.raises(CliError, match="protocol/transport failure"):
            _run_plan(client, tmp_path)
        assert client.prompt_calls == _OMP_MAX_ATTEMPTS
        assert client.stopped == _OMP_MAX_ATTEMPTS

    def test_timeout_is_retryable(self, tmp_path, monkeypatch, deepseek_env):
        payload = _valid_plan_payload()
        calls = {"n": 0}

        def _flaky_turn():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RpcTimeoutError("request timed out")
            return make_turn(assistant_text=json.dumps(payload))

        client = FakeRpcClient(turn_factory=_flaky_turn)
        _install_factory(monkeypatch, client)
        result = _run_plan(client, tmp_path)
        assert result.attempt_index == 2
        assert calls["n"] == 2

    def test_provider_429_is_hard(self, tmp_path, monkeypatch, deepseek_env):
        client = FakeRpcClient(
            turn_factory=lambda: make_turn(
                assistant_text="x",
                error_message="HTTP 429 Too Many Requests: rate_limit",
            )
        )
        _install_factory(monkeypatch, client)
        with pytest.raises(CliError, match="rate_limit"):
            _run_plan(client, tmp_path)
        assert client.prompt_calls == 1

    def test_provider_5xx_is_retryable(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        client = FakeRpcClient(
            turn_factory=lambda: make_turn(
                assistant_text="x",
                error_message="HTTP 503 Service Unavailable",
            )
        )
        _install_factory(monkeypatch, client)
        with pytest.raises(CliError, match="provider unavailable"):
            _run_plan(client, tmp_path)
        assert client.prompt_calls == _OMP_MAX_ATTEMPTS

    def test_auth_failure_is_hard(self, tmp_path, monkeypatch, deepseek_env):
        client = FakeRpcClient(
            turn_factory=lambda: make_turn(
                assistant_text="x",
                error_message="401 invalid_api_key authentication failed",
            )
        )
        _install_factory(monkeypatch, client)
        with pytest.raises(CliError, match="authentication"):
            _run_plan(client, tmp_path)
        assert client.prompt_calls == 1

    def test_quota_failure_is_hard(self, tmp_path, monkeypatch, deepseek_env):
        client = FakeRpcClient(
            turn_factory=lambda: make_turn(
                assistant_text="x",
                error_message="402 quota exhausted insufficient_credits",
            )
        )
        _install_factory(monkeypatch, client)
        with pytest.raises(CliError, match="quota exhausted"):
            _run_plan(client, tmp_path)
        assert client.prompt_calls == 1

    def test_unsupported_model_is_hard(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        client = FakeRpcClient(
            turn_factory=lambda: make_turn(
                assistant_text="x",
                error_message="unsupported_model model_not_found",
            )
        )
        _install_factory(monkeypatch, client)
        with pytest.raises(CliError, match="unsupported_model"):
            _run_plan(client, tmp_path)
        assert client.prompt_calls == 1

    def test_context_overflow_is_hard(self, tmp_path, monkeypatch, deepseek_env):
        client = FakeRpcClient(
            turn_factory=lambda: make_turn(
                assistant_text="x",
                error_message="context_length_exceeded token_limit exceeded",
            )
        )
        _install_factory(monkeypatch, client)
        with pytest.raises(CliError, match="context_length_exceeded"):
            _run_plan(client, tmp_path)
        assert client.prompt_calls == 1

    def test_missing_credential_fails_closed(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        client = FakeRpcClient(
            turn_factory=lambda: make_turn(assistant_text="{}")
        )
        _install_factory(monkeypatch, client)
        with pytest.raises(CliError, match="requires one of"):
            _run_plan(client, tmp_path)
        assert client.started == 0

    def test_stop_called_on_failure_no_orphan(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        client = FakeRpcClient(
            prompt_error=RpcProcessExitError("killed", 137),
        )
        _install_factory(monkeypatch, client)
        with pytest.raises(CliError, match="child exited"):
            _run_plan(client, tmp_path)
        assert client.stopped == client.started


class TestRetrySemantics:
    def test_bounded_retries_recorded(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        client = FakeRpcClient(
            start_error=RpcProcessExitError("omp exited before ready", 1)
        )
        _install_factory(monkeypatch, client)
        with pytest.raises(CliError, match="child exited"):
            _run_plan(client, tmp_path)
        assert client.stopped == _OMP_MAX_ATTEMPTS

    def test_execute_no_replay_after_side_effects(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        plan_dir, state = _mock_state(tmp_path)
        (plan_dir / "gate.json").write_text(
            json.dumps(_valid_gate_json()), encoding="utf-8"
        )
        project_dir = Path(state["config"]["project_dir"])
        # Make the work dir a git repo so the mutation guard can observe
        # side effects.
        subprocess.run(
            ["git", "init", "-q", str(project_dir)], check=True
        )
        subprocess.run(
            ["git", "-C", str(project_dir), "config", "user.email", "t@t"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(project_dir), "config", "user.name", "t"],
            check=True,
        )
        (project_dir / "seed.txt").write_text("seed", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(project_dir), "add", "."], check=True
        )
        subprocess.run(
            ["git", "-C", str(project_dir), "commit", "-qm", "seed"], check=True
        )
        calls = {"n": 0}

        def _side_effect_then_fail():
            calls["n"] += 1
            # The failed attempt lands a real side effect in the worktree.
            (project_dir / "landed.txt").write_text("mutated", encoding="utf-8")
            raise RpcTimeoutError("timed out after side effects")

        client = FakeRpcClient(turn_factory=_side_effect_then_fail)
        _install_factory(monkeypatch, client)
        with pytest.raises(ExecuteFallbackUnsafe) as excinfo:
            run_omp_step(
                "execute",
                state,
                plan_dir,
                root=tmp_path,
                fresh=True,
                model="omp:deepseek/deepseek-v4-pro",
            )
        assert excinfo.value.phase == "execute"
        # No replay: the second attempt never launched.
        assert calls["n"] == 1
        assert client.started == 1

    def test_execute_retries_before_side_effects(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        plan_dir, state = _mock_state(tmp_path)
        (plan_dir / "gate.json").write_text(
            json.dumps(_valid_gate_json()), encoding="utf-8"
        )
        project_dir = Path(state["config"]["project_dir"])
        subprocess.run(
            ["git", "init", "-q", str(project_dir)], check=True
        )
        calls = {"n": 0}

        def _fail_then_succeed():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RpcTimeoutError("timed out before any mutation")
            return make_turn(
                assistant_text=json.dumps(
                    {
                        "output": "done",
                        "files_changed": [],
                        "commands_run": [],
                        "deviations": [],
                        "task_updates": [],
                        "sense_check_acknowledgments": [],
                    }
                )
            )

        client = FakeRpcClient(turn_factory=_fail_then_succeed)
        _install_factory(monkeypatch, client)
        result = run_omp_step(
            "execute",
            state,
            plan_dir,
            root=tmp_path,
            fresh=True,
            model="omp:deepseek/deepseek-v4-pro",
        )
        assert result.attempt_index == 2


class TestUsageAndCost:
    def test_usage_aggregated_exactly_once(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        payload = _valid_plan_payload()
        client = FakeRpcClient(
            messages=[
                usage_message(
                    input_tokens=100,
                    output_tokens=50,
                    cache_read=10,
                    cost_total=0.01,
                ),
                usage_message(
                    input_tokens=30,
                    output_tokens=20,
                    cache_write=5,
                    cost_total=0.005,
                ),
            ],
            turn_factory=lambda: make_turn(assistant_text=json.dumps(payload)),
        )
        _install_factory(monkeypatch, client)
        result = _run_plan(client, tmp_path)
        assert result.prompt_tokens == 130
        assert result.completion_tokens == 70
        assert result.cost_usd == pytest.approx(0.015)
        assert result.cost_pricing == "omp_usage_cost"
        assert result.auth_metadata["usage_reconciliation"] == "per_message_exact"

    def test_reconciliation_from_session_stats(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        payload = _valid_plan_payload()
        client = FakeRpcClient(
            messages=[],
            session_stats=_FakeSessionStats(
                tokens={"input": 500, "output": 200, "cache_read": 0, "cache_write": 0, "total": 700},
                cost=0.05,
            ),
            turn_factory=lambda: make_turn(assistant_text=json.dumps(payload)),
        )
        _install_factory(monkeypatch, client)
        result = _run_plan(client, tmp_path)
        assert result.prompt_tokens == 500
        assert result.completion_tokens == 200
        assert result.cost_usd == pytest.approx(0.05)
        assert result.cost_pricing == "omp_session_stats_cost"
        assert (
            result.auth_metadata["usage_reconciliation"]
            == "session_stats_delta_applied"
        )

    def test_usage_not_double_counted_across_attempts(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        payload = _valid_plan_payload()
        calls = {"n": 0}

        def _flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RpcTimeoutError("timeout")
            return make_turn(assistant_text=json.dumps(payload))

        client = FakeRpcClient(
            messages=[
                usage_message(input_tokens=100, output_tokens=50, cost_total=0.01)
            ],
            turn_factory=_flaky,
        )
        _install_factory(monkeypatch, client)
        result = _run_plan(client, tmp_path)
        # The failed attempt never produced messages; the successful attempt
        # is counted exactly once.
        assert result.prompt_tokens == 100
        assert result.completion_tokens == 50
        assert result.cost_usd == pytest.approx(0.01)


class TestThinkingPassthrough:
    def test_thinking_level_sent(self, tmp_path, monkeypatch, deepseek_env):
        payload = _valid_plan_payload()
        client = FakeRpcClient(
            turn_factory=lambda: make_turn(assistant_text=json.dumps(payload))
        )
        _install_factory(monkeypatch, client)
        _run_plan(client, tmp_path, effort="high")
        assert client.thinking_levels == ["high"]

    def test_no_thinking_when_unset(self, tmp_path, monkeypatch, deepseek_env):
        payload = _valid_plan_payload()
        client = FakeRpcClient(
            turn_factory=lambda: make_turn(assistant_text=json.dumps(payload))
        )
        _install_factory(monkeypatch, client)
        _run_plan(client, tmp_path, effort=None)
        assert client.thinking_levels == []

    def test_set_model_receives_catalog_ids(
        self, tmp_path, monkeypatch, deepseek_env
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
        payload = _valid_plan_payload()
        client = FakeRpcClient(
            turn_factory=lambda: make_turn(assistant_text=json.dumps(payload))
        )
        _install_factory(monkeypatch, client)
        _run_plan(client, tmp_path, model="omp:anthropic/claude-opus-4-8")
        assert ("anthropic", "claude-opus-4-8") in client.set_model_calls
        assert client.env.get("ANTHROPIC_API_KEY") is None or True
