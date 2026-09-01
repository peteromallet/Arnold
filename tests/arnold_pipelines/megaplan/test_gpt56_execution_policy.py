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


def test_partnered_codex_routing_contract() -> None:
    profile_path = (
        Path(__file__).resolve().parents[3]
        / "arnold_pipelines/megaplan/profiles/partnered-codex.toml"
    )
    profile = tomllib.loads(profile_path.read_text(encoding="utf-8"))["profiles"][
        "partnered-codex"
    ]

    expected_phases = {
        "plan": "codex:gpt-5.6-sol:high",
        "prep": "codex:gpt-5.6-terra:medium",
        "critique": "codex:gpt-5.6-terra:medium",
        "critique_evaluator": "codex:gpt-5.6-sol:high",
        "revise": "codex:gpt-5.6-luna:medium",
        "gate": "codex:gpt-5.6-terra:medium",
        "finalize": "codex:gpt-5.6-sol:high",
        "execute": "codex:gpt-5.6-sol:medium",
        "feedback": "codex:gpt-5.6-sol:medium",
        "loop_plan": "codex:gpt-5.6-sol:high",
        "loop_execute": "codex:gpt-5.6-sol:medium",
        "review": "codex:gpt-5.6-sol:medium",
        "tiebreaker_researcher": "codex:gpt-5.6-sol:high",
        "tiebreaker_challenger": "codex:gpt-5.6-sol:high",
    }
    assert {phase: profile[phase] for phase in expected_phases} == expected_phases
    assert profile["adaptive_critique"] is True
    assert profile["vendor_locked"] is True
    assert profile["prep_models"] == {
        "triage": "codex:gpt-5.6-terra:medium",
        "fanout": "codex:gpt-5.6-terra:medium",
        "distill": "codex:gpt-5.6-terra:medium",
    }

    execute_tiers = profile["tier_models"]["execute"]
    assert [execute_tiers[str(tier)] for tier in range(1, 7)] == [
        "codex:gpt-5.6-luna:low",
        "codex:gpt-5.6-luna:medium",
        "codex:gpt-5.6-luna:high",
        "codex:gpt-5.6-luna:high",
        "codex:gpt-5.6-luna:xhigh",
        "codex:gpt-5.6-luna:max",
    ]
    assert [execute_tiers[str(tier)] for tier in (7, 8)] == [
        "codex:gpt-5.6-terra:xhigh",
        "codex:gpt-5.6-terra:max",
    ]
    assert execute_tiers["9"] == "codex:gpt-5.6-sol:xhigh"
    assert execute_tiers["10"] == "codex:gpt-5.6-sol:max"

    critique_tiers = profile["tier_models"]["critique"]
    assert critique_tiers == {
        "1": "codex:gpt-5.6-luna:low",
        "2": "codex:gpt-5.6-terra:medium",
        "3": "codex:gpt-5.6-terra:high",
        "4": "codex:gpt-5.6-terra:xhigh",
        "5": "codex:gpt-5.6-sol:max",
    }

    retired_path = profile_path.with_name("all-codex.toml")
    assert not retired_path.exists()


@pytest.mark.parametrize("effort", ["xhigh", "max"])
def test_codex_xhigh_and_max_are_not_clamped(effort: str) -> None:
    assert _impl._normalize_codex_effort(effort) == effort
    assert effort in _impl._VALID_CODEX_EFFORTS
    assert _impl._codex_effort_flag(effort) == [
        "-c",
        f"model_reasoning_effort={effort}",
    ]


@pytest.mark.parametrize("failure_class", ["availability", "infrastructure"])
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


_CROSS_FAMILY_METADATA = {
    "configured_specs": (
        "omp:zai/glm-5.2",
        "omp:fireworks/glm-5.2",
        "codex:gpt-5.5:high",
    ),
    "attempt_index": 0,
    "attempted_specs": ("omp:zai/glm-5.2",),
    "failed_attempt_reasons": (),
    "fallback_trigger": None,
}


def test_launch_time_quota_does_not_advance_non_read_only_plan() -> None:
    assert _impl._advance_configured_spec_fallback(
        _CROSS_FAMILY_METADATA,
        "quota",
        mode="persistent",
        step="plan",
        read_only=False,
        pre_tool=True,
    ) is None


def test_launch_time_availability_advances_non_read_only_plan() -> None:
    advanced = _impl._advance_configured_spec_fallback(
        _CROSS_FAMILY_METADATA,
        "availability",
        mode="persistent",
        step="plan",
        read_only=False,
        pre_tool=True,
    )
    assert advanced is not None


def test_mid_tool_quota_stays_fail_closed() -> None:
    assert _impl._advance_configured_spec_fallback(
        _CROSS_FAMILY_METADATA,
        "quota",
        mode="persistent",
        step="plan",
        read_only=False,
        pre_tool=False,
    ) is None


def test_semantic_never_advances_even_when_pre_tool() -> None:
    assert _impl._advance_configured_spec_fallback(
        _CROSS_FAMILY_METADATA,
        "semantic",
        mode="persistent",
        step="plan",
        read_only=False,
        pre_tool=True,
    ) is None


def test_execute_never_advances_even_when_pre_tool() -> None:
    assert _impl._advance_configured_spec_fallback(
        _CROSS_FAMILY_METADATA,
        "quota",
        mode="persistent",
        step="execute",
        read_only=False,
        pre_tool=True,
    ) is None


def test_read_only_quota_does_not_advance_without_pre_tool() -> None:
    assert _impl._advance_configured_spec_fallback(
        _CROSS_FAMILY_METADATA,
        "quota",
        mode="persistent",
        step="critique",
        read_only=True,
        pre_tool=False,
    ) is None


def test_missing_attestation_defaults_fail_closed_for_non_read_only() -> None:
    # pre_tool defaults False when the caller omits it.
    assert _impl._advance_configured_spec_fallback(
        _CROSS_FAMILY_METADATA,
        "quota",
        mode="persistent",
        step="plan",
        read_only=False,
    ) is None


def test_only_literal_true_is_accepted() -> None:
    assert _impl._advance_configured_spec_fallback(
        _CROSS_FAMILY_METADATA,
        "quota",
        mode="persistent",
        step="plan",
        read_only=False,
        pre_tool="true",  # type: ignore[arg-type]
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


def test_diagnose_codex_failure_no_credits_is_quota_not_connection() -> None:
    """The real codex no-credits transport text must diagnose as quota_exceeded,
    not connection_error.

    Codex surfaces billing exhaustion wrapped inside
    "stream disconnected before completion: You have no credits remaining..."
    (astrid-first m6 finalize_v1_raw.txt, occurrence fc98376b2f10). The
    _CODEX_ERROR_PATTERNS row for "no credits remaining" is placed BEFORE the
    generic "stream disconnected before completion" connection row
    (workers/_impl.py:3171-3180), so first-match-wins returns quota_exceeded
    and routes to _codex_hard_quota_guidance instead of the transient
    "re-run once" guidance.
    """
    raw = (
        '{"type":"thread.started","thread_id":"01a01ad6-9bad-7743-ba98-13c9f02d0e00"}\n'
        '{"type":"turn.started"}\n'
        '{"type":"error","message":"Reconnecting... 2/5 (stream disconnected before '
        'completion: You have no credits remaining. Add credits to continue using the '
        'API at https://platform.openai.com/settings/organization/billing/.)"}\n'
        '{"type":"error","message":"Reconnecting... 5/5 (stream disconnected before '
        'completion: You have no credits remaining. Add credits to continue using the '
        'API at https://platform.openai.com/settings/organization/billing/.)"}\n'
        '{"type":"item.completed","item":{"id":"item_0","type":"error","message":"Falling '
        'back from WebSockets to HTTPS transport. stream disconnected before completion: '
        'You have no credits remaining. Add credits to continue using the API at '
        'https://platform.openai.com/settings/organization/billing/."}}\n'
    )
    code, message = _impl._diagnose_codex_failure(raw, returncode=1)
    assert code == "quota_exceeded"
    assert "Codex quota exceeded" in message
    assert "Do not retry immediately" in message
    assert "Re-run the same step" not in message

    # A genuine transport drop (no billing text) still diagnoses as
    # connection_error — the new row must not shadow unrelated drops.
    code2, _message2 = _impl._diagnose_codex_failure(
        "stream disconnected before completion: peer closed the connection", returncode=1
    )
    assert code2 == "connection_error"
