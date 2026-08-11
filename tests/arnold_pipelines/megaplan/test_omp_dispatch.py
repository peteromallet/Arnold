"""B3 oracle tests — omp dispatch threading, availability, grammar, fallback.

Table-driven parity across every megaplan phase, in BOTH dispatch modes
(direct worker branch and ``MEGAPLAN_USE_AGENT_DISPATCHER=1``), plus
availability detection, double-colon spec rejection at dispatch, and
cross-provider fallback classification for omp routes.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import pytest

from arnold.runtime.agent_contracts import AgentMode, parse_agent_spec
from arnold_pipelines.megaplan._core.io import detect_available_agents
from arnold_pipelines.megaplan.fallback_chains import (
    FallbackSpecChain,
    provider_family,
)
from arnold_pipelines.megaplan.profiles.policy import KNOWN_AGENTS
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.workers import WorkerResult, run_step_with_worker

from tests._workers_helpers import _mock_state

# Every live phase surface from the B3 contract: prep triage/distill, the
# seven core phases, loop phases, tiebreakers, feedback, critique evaluation.
PHASES = [
    "prep",
    "prep-triage",
    "prep-distill",
    "plan",
    "critique",
    "revise",
    "gate",
    "finalize",
    "execute",
    "review",
    "loop_plan",
    "loop_execute",
    "tiebreaker_researcher",
    "tiebreaker_challenger",
    "tiebreaker_synthesis",
    "tiebreaker_orchestrator",
    "feedback",
    "critique_evaluation",
]

OMP_MODEL = "deepseek/deepseek-v4-pro"
OMP_SPEC = "omp:deepseek/deepseek-v4-pro"
OMP_EFFORT = "high"


def _args() -> argparse.Namespace:
    return argparse.Namespace(
        phase_model=[],
        agent=None,
        hermes=None,
        tier_models={},
        profile=None,
        vendor=None,
        critic=None,
        depth=None,
        _profile_applied=True,
    )


def _resolved() -> AgentMode:
    return AgentMode(
        agent="omp",
        mode="ephemeral",
        refreshed=True,
        model=OMP_MODEL,
        effort=OMP_EFFORT,
        resolved_model=OMP_MODEL,
    )


def _record_worker(**overrides: Any) -> WorkerResult:
    return WorkerResult(
        payload={"phase": "ok", **overrides},
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.01,
        model_actual=OMP_MODEL,
        worker_channel="omp_rpc",
    )


@pytest.fixture
def omp_worker_recorder(monkeypatch):
    calls: list[dict[str, Any]] = []

    def _fake_run_omp_step(step, state, plan_dir, *, root, fresh=True, model=None, effort=None, prompt_override=None, output_path=None, worker_options=None, read_only=False, free_text=False, prompt_kwargs=None):
        calls.append(
            {
                "step": step,
                "model": model,
                "effort": effort,
                "fresh": fresh,
                "read_only": read_only,
                "output_path": output_path,
                "worker_options": worker_options,
            }
        )
        return _record_worker(step=step)

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers.omp.run_omp_step",
        _fake_run_omp_step,
    )
    return calls


@pytest.fixture
def state_and_plan(tmp_path):
    plan_dir, state = _mock_state(tmp_path)
    return tmp_path, plan_dir, state


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize("dispatcher", [False, True])
def test_omp_dispatch_parity(
    phase: str,
    dispatcher: bool,
    state_and_plan,
    omp_worker_recorder,
    monkeypatch,
):
    root, plan_dir, state = state_and_plan
    if dispatcher:
        monkeypatch.setenv("MEGAPLAN_USE_AGENT_DISPATCHER", "1")
    else:
        monkeypatch.delenv("MEGAPLAN_USE_AGENT_DISPATCHER", raising=False)

    worker, agent, mode, refreshed = run_step_with_worker(
        phase,
        state,
        plan_dir,
        _args(),
        root=root,
        resolved=_resolved(),
    )
    assert agent == "omp"
    assert worker.payload["step"] == phase
    assert len(omp_worker_recorder) == 1
    recorded = omp_worker_recorder[0]
    assert recorded["step"] == phase
    assert recorded["model"] == OMP_MODEL
    assert recorded["effort"] == OMP_EFFORT


@pytest.mark.parametrize("dispatcher", [False, True])
def test_omp_dispatch_execute_read_only_flag(
    dispatcher: bool, state_and_plan, omp_worker_recorder, monkeypatch
):
    root, plan_dir, state = state_and_plan
    if dispatcher:
        monkeypatch.setenv("MEGAPLAN_USE_AGENT_DISPATCHER", "1")
    else:
        monkeypatch.delenv("MEGAPLAN_USE_AGENT_DISPATCHER", raising=False)
    worker, agent, mode, _refreshed = run_step_with_worker(
        "execute",
        state,
        plan_dir,
        _args(),
        root=root,
        resolved=_resolved(),
        read_only=True,
    )
    assert agent == "omp"
    assert omp_worker_recorder[0]["read_only"] is True


class TestAvailability:
    def test_known_agents_includes_omp(self):
        assert "omp" in KNOWN_AGENTS

    def test_detect_available_agents_includes_omp(self):
        available = detect_available_agents()
        assert "omp" in available

    def test_is_agent_available_omp(self):
        from arnold_pipelines.megaplan.workers._impl import _is_agent_available

        assert _is_agent_available("omp") is True

    def test_resolved_default_model_for_omp_is_none(self):
        from arnold_pipelines.megaplan.types import (
            resolved_default_model_for_agent,
        )

        # omp specs carry their own model; no bare-omp default exists.
        assert resolved_default_model_for_agent("omp") is None


class TestGrammarAtDispatch:
    def test_double_colon_rejected_at_parse(self):
        with pytest.raises(ValueError, match="never valid"):
            parse_agent_spec("omp:" + "deepseek:model")

    def test_effort_suffix_parsed(self):
        parsed = parse_agent_spec("omp:deepseek/deepseek-v4-pro:max")
        assert parsed.agent == "omp"
        assert parsed.model == "deepseek/deepseek-v4-pro"
        assert parsed.effort == "max"

    def test_bad_effort_rejected(self):
        with pytest.raises(ValueError, match="thinking level"):
            parse_agent_spec("omp:deepseek/deepseek-v4-pro:ultra")

    def test_claude_and_codex_compat_preserved(self):
        assert parse_agent_spec("claude:sonnet-4.6:medium").effort == "medium"
        assert parse_agent_spec("codex:gpt-5.3:high").model == "gpt-5.3"
        assert (
            parse_agent_spec("hermes:fireworks:accounts/foo").model
            == "fireworks:accounts/foo"
        )


class TestProviderFamily:
    def test_omp_routes_classified_by_upstream_provider(self):
        assert provider_family("omp:deepseek/deepseek-v4-pro") == "deepseek"
        assert provider_family("omp:zai/glm-5.2") == "zai"
        assert provider_family("omp:anthropic/claude-opus-4-8") == "anthropic"
        assert provider_family("omp:fireworks/kimi-k2.7-code") == "fireworks"
        assert provider_family("omp:xai/grok-4-fast-non-reasoning") == "xai"
        assert provider_family("omp:openrouter/openai/gpt-5.5") == "openrouter"

    def test_omp_and_codex_are_different_families(self):
        assert (
            provider_family("omp:deepseek/deepseek-v4-pro")
            != provider_family("codex:gpt-5.5")
        )

    def test_cross_provider_fallback_chain_advances_between_families(self):
        # A deepseek route falling back to codex crosses the provider family
        # boundary — the fallback chain machinery must treat them as
        # independent providers.
        chain = FallbackSpecChain.from_value(
            ["omp:deepseek/deepseek-v4-pro", "codex:gpt-5.5"],
            path="test.fallback",
        )
        assert len(chain.specs) == 2
        assert provider_family(chain.specs[0]) == "deepseek"
        assert provider_family(chain.specs[1]) == "codex"
        assert chain.selected(0) == "omp:deepseek/deepseek-v4-pro"

    def test_same_family_omp_routes_share_family(self):
        assert provider_family(
            "omp:deepseek/deepseek-v4-pro"
        ) == provider_family("omp:deepseek/deepseek-v4-flash")
