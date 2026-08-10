from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.pricing.codex import (
    cost_from_codex_usage_dict,
    cost_from_usage,
)
from arnold_pipelines.megaplan.cloud.spec import (
    CodexSpec,
    VALID_CODEX_REASONING,
    load_spec as load_cloud_spec,
)
from arnold_pipelines.megaplan._core.state import make_history_entry
from arnold_pipelines.megaplan.workers import WorkerResult
from arnold_pipelines.megaplan.workers import _impl


def test_all_codex_pins_effort_on_every_phase_and_uses_same_family_fallbacks() -> None:
    profile_path = (
        Path(__file__).resolve().parents[3]
        / "arnold_pipelines/megaplan/profiles/all-codex.toml"
    )
    profile = tomllib.loads(profile_path.read_text(encoding="utf-8"))["profiles"]["all-codex"]

    phase_names = {
        "plan",
        "prep",
        "critique",
        "critique_evaluator",
        "revise",
        "gate",
        "finalize",
        "execute",
        "feedback",
        "loop_plan",
        "loop_execute",
        "review",
        "tiebreaker_researcher",
        "tiebreaker_challenger",
    }
    for phase in phase_names:
        specs = profile[phase] if isinstance(profile[phase], list) else [profile[phase]]
        assert all(len(spec.split(":")) == 3 for spec in specs), (phase, specs)
        assert all(spec.startswith("codex:gpt-5.6-") for spec in specs), (phase, specs)

    assert profile["critique"] == [
        "codex:gpt-5.6-sol:high",
        "codex:gpt-5.6-terra:high",
    ]
    assert profile["gate"] == [
        "codex:gpt-5.6-terra:low",
        "codex:gpt-5.6-luna:low",
    ]
    assert profile["tier_models"]["critique"]["9"] == [
        "codex:gpt-5.6-sol:xhigh",
        "codex:gpt-5.6-terra:high",
    ]
    assert isinstance(profile["tier_models"]["execute"]["9"], str)


@pytest.mark.parametrize("effort", ["xhigh", "max"])
def test_codex_xhigh_and_max_are_not_clamped(effort: str) -> None:
    assert _impl._normalize_codex_effort(effort) == effort
    assert effort in _impl._VALID_CODEX_EFFORTS
    assert _impl._codex_effort_flag(effort) == [
        "-c",
        f"model_reasoning_effort={effort}",
    ]


@pytest.mark.parametrize("failure_class", ["availability", "rate_limit", "unsupported_model"])
def test_sequential_same_family_fallback_is_non_writing_and_operational_only(
    failure_class: str,
) -> None:
    metadata = {
        "configured_specs": (
            "codex:gpt-5.6-sol:high",
            "codex:gpt-5.6-terra:high",
        ),
        "attempt_index": 0,
        "attempted_specs": ("codex:gpt-5.6-sol:high",),
        "failed_attempt_reasons": (),
        "fallback_trigger": None,
    }

    advanced = _impl._advance_configured_spec_fallback(
        metadata,
        failure_class,
        mode="persistent",
        step="critique",
        read_only=True,
    )

    assert advanced is not None
    mode, next_metadata = advanced
    assert mode.model == "gpt-5.6-terra"
    assert next_metadata["attempt_index"] == 1


def test_sequential_same_family_fallback_rejects_semantic_and_writing_failures() -> None:
    metadata = {
        "configured_specs": (
            "codex:gpt-5.6-sol:high",
            "codex:gpt-5.6-terra:high",
        ),
        "attempt_index": 0,
        "attempted_specs": ("codex:gpt-5.6-sol:high",),
        "failed_attempt_reasons": (),
        "fallback_trigger": None,
    }

    assert _impl._advance_configured_spec_fallback(
        metadata,
        "semantic",
        mode="persistent",
        step="critique",
        read_only=True,
    ) is None
    assert _impl._advance_configured_spec_fallback(
        metadata,
        "availability",
        mode="persistent",
        step="execute",
        read_only=False,
    ) is None


def test_unknown_codex_model_is_explicitly_unpriced() -> None:
    usage = {
        "input_tokens": 1000,
        "cached_input_tokens": 100,
        "output_tokens": 250,
        "reasoning_output_tokens": 50,
    }

    assert cost_from_usage(1000, 300, "gpt-5.6-sol", cached_prompt_tokens=100) is None
    assert cost_from_codex_usage_dict(usage, "gpt-5.6-sol") is None
    assert cost_from_usage(1000, 300, "gpt-5.5", cached_prompt_tokens=100) is not None


def test_cloud_codex_defaults_align_and_allow_full_effort_ladder() -> None:
    assert CodexSpec() == CodexSpec(model="gpt-5.6-sol", reasoning="medium")
    assert VALID_CODEX_REASONING == (
        "minimal",
        "low",
        "medium",
        "high",
        "xhigh",
        "max",
    )


def test_cloud_spec_accepts_max_without_clamping(tmp_path: Path) -> None:
    path = tmp_path / "cloud.yaml"
    path.write_text(
        "provider: ssh\n"
        "repo:\n"
        "  url: https://example.com/repo.git\n"
        "codex:\n"
        "  model: gpt-5.6-sol\n"
        "  reasoning: max\n"
        "ssh:\n"
        "  host: agentbox.example.com\n",
        encoding="utf-8",
    )

    assert load_cloud_spec(path).codex.reasoning == "max"


def test_unpriced_status_survives_worker_and_history_compatibility_surfaces() -> None:
    worker = WorkerResult(
        payload={"ok": True},
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
        cost_pricing="unpriced",
    )

    assert WorkerResult.from_agent_result(worker.to_agent_result()).cost_pricing == "unpriced"
    entry = make_history_entry(
        "critique",
        duration_ms=1,
        cost_usd=0.0,
        result="ok",
        worker=worker,
        agent="codex",
        mode="oneshot",
    )
    assert entry["cost_pricing"] == "unpriced"
