from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.orchestration.gate_checks import (
    has_high_complexity_unverifiable_checks,
    is_operational_unverifiable_check,
)


def test_high_complexity_rate_limit_unverifiable_does_not_block_proceed() -> None:
    check = {
        "id": "correctness",
        "reason": "parallel critique worker failed for check 'correctness': provider rate limit",
        "cause": "provider_rate_limit",
        "retryable": True,
        "error_kind": "rate_limit",
        "attention": "high_complexity_unverifiable",
        "complexity": 5,
    }

    assert is_operational_unverifiable_check(check)
    assert has_high_complexity_unverifiable_checks({"unverifiable_checks": [check]}) == []


def test_legacy_provider_capacity_reason_unverifiable_does_not_block_proceed() -> None:
    check = {
        "id": "correctness",
        "reason": "provider capacity unavailable",
        "attention": "high_complexity_unverifiable",
        "complexity": 5,
    }

    assert is_operational_unverifiable_check(check)
    assert has_high_complexity_unverifiable_checks({"unverifiable_checks": [check]}) == []


def test_high_complexity_sandbox_namespace_unverifiable_does_not_block_proceed() -> None:
    check = {
        "id": "correctness",
        "reason": (
            "Attempts to inspect /workspace/tmp via local commands failed with "
            "a sandbox namespace error."
        ),
        "cause": "sandbox_namespace",
        "retryable": False,
        "error_kind": "sandbox_namespace",
        "attention": "high_complexity_unverifiable",
        "complexity": 5,
    }

    assert is_operational_unverifiable_check(check)
    assert has_high_complexity_unverifiable_checks({"unverifiable_checks": [check]}) == []


def test_high_complexity_missing_repo_unverifiable_still_blocks_proceed() -> None:
    check = {
        "id": "correctness",
        "reason": "cannot access ../sibling-repo to inspect the integration contract",
        "attention": "high_complexity_unverifiable",
        "complexity": 5,
    }

    assert not is_operational_unverifiable_check(check)
    assert has_high_complexity_unverifiable_checks({"unverifiable_checks": [check]}) == [
        check
    ]


def test_annotate_unverifiable_preserves_machine_readable_cause() -> None:
    from arnold_pipelines.megaplan.orchestration.critique_status import (
        annotate_unverifiable_checks,
    )

    payload = {
        "checks": [
            {
                "id": "correctness",
                "question": "Correct?",
                "status": "unverifiable",
                "unverifiable_reason": "worker unavailable",
                "unverifiable_cause": "provider_rate_limit",
                "unverifiable_retryable": True,
                "unverifiable_error_kind": "rate_limit",
                "findings": [
                    {"detail": "unverifiable: worker unavailable", "flagged": False}
                ],
            }
        ]
    }

    records = annotate_unverifiable_checks(
        payload,
        check_specs=[{"id": "correctness", "complexity": 4}],
    )

    assert records == [
        {
            "id": "correctness",
            "question": "Correct?",
            "reason": "worker unavailable",
            "cause": "provider_rate_limit",
            "retryable": True,
            "error_kind": "rate_limit",
            "complexity": 4,
            "attention": "high_complexity_unverifiable",
        }
    ]


def test_parallel_critique_unverifiable_payload_carries_retryable_cause() -> None:
    from arnold_pipelines.megaplan.orchestration.parallel_critique import (
        _unverifiable_check_payload,
    )

    payload = _unverifiable_check_payload(
        "correctness",
        "Correct?",
        "worker unavailable",
        cause="provider_rate_limit",
        retryable=True,
        error_kind="rate_limit",
    )

    assert payload["unverifiable_cause"] == "provider_rate_limit"
    assert payload["unverifiable_retryable"] is True
    assert payload["unverifiable_error_kind"] == "rate_limit"


def test_synthetic_verifiability_flags_are_evidence_complete() -> None:
    from arnold_pipelines.megaplan.handlers.plan import _build_verifiability_flags

    flags = _build_verifiability_flags(
        [
            {
                "criterion": "Prove the contract.",
                "priority": "must",
                "requires": ["not_a_registered_capability"],
            }
        ],
        {},
    )

    assert len(flags) == 2
    assert all(flag["evidence"] == flag["concern"] for flag in flags)
    assert all(flag["evidence"].strip() for flag in flags)


def test_historical_provider_capacity_downgrade_is_recoverable_from_blocked_state() -> None:
    from arnold_pipelines.megaplan.handlers.override import (
        _last_gate_is_operational_unverifiable_block,
    )

    state = {
        "current_state": "blocked",
        "last_gate": {
            "recommendation": "ITERATE",
            "passed": False,
        },
        "meta": {
            "critique_unverifiable_checks": [
                {
                    "checks": [
                        {
                            "id": "correctness",
                            "reason": (
                                "parallel critique worker failed for check "
                                "'correctness': provider capacity unavailable."
                            ),
                            "attention": "high_complexity_unverifiable",
                            "complexity": 4,
                        }
                    ],
                    "iteration": 3,
                }
            ]
        },
    }

    assert _last_gate_is_operational_unverifiable_block(state)


def test_missing_repo_downgrade_is_not_recoverable_from_blocked_state() -> None:
    from arnold_pipelines.megaplan.handlers.override import (
        _last_gate_is_operational_unverifiable_block,
    )

    state = {
        "current_state": "blocked",
        "last_gate": {
            "recommendation": "ITERATE",
            "passed": False,
            "signals": {
                "unverifiable_checks": [
                    {
                        "id": "correctness",
                        "reason": "cannot access ../sibling-repo for contract evidence",
                        "attention": "high_complexity_unverifiable",
                        "complexity": 4,
                    }
                ]
            },
        },
        "meta": {},
    }

    assert not _last_gate_is_operational_unverifiable_block(state)


def test_historical_sandbox_raw_artifact_recovers_blocked_state(tmp_path) -> None:
    from arnold_pipelines.megaplan.handlers.override import (
        _blocked_plan_has_operational_unverifiable_evidence,
    )

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "critique_check_correctness_raw.txt").write_text(
        "bwrap: No permissions to create new namespace.",
        encoding="utf-8",
    )

    state = {
        "current_state": "blocked",
        "last_gate": {
            "recommendation": "ITERATE",
            "passed": False,
        },
        "meta": {
            "critique_unverifiable_checks": [
                {
                    "checks": [
                        {
                            "id": "correctness",
                            "reason": (
                                "parallel critique worker output did not contain a usable "
                                "check object for this lens after retry; operator review "
                                "may be needed"
                            ),
                            "attention": "high_complexity_unverifiable",
                            "complexity": 4,
                        }
                    ],
                    "iteration": 7,
                }
            ]
        },
    }

    assert _blocked_plan_has_operational_unverifiable_evidence(plan_dir, state)


def test_build_gate_signals_routes_unverifiable_checks_to_execute_contract(
    tmp_path: Path,
) -> None:
    from arnold_pipelines.megaplan.orchestration.gate_signals import build_gate_signals
    from arnold_pipelines.megaplan.prompts.gate import _gate_signals_for_prompt

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "plan_v1.md").write_text("# Plan\n", encoding="utf-8")
    (plan_dir / "faults.json").write_text(
        json.dumps({"flags": []}),
        encoding="utf-8",
    )
    required_checks = [
        {
            "id": "route-metadata",
            "question": "Are product route metadata exports complete?",
            "reason": "execute-only property; requires test-backed verification",
            "attention": "high_complexity_unverifiable",
            "complexity": 5,
        }
    ]
    (plan_dir / "critique_v1.json").write_text(
        json.dumps({"unverifiable_checks": required_checks}),
        encoding="utf-8",
    )
    state = {
        "iteration": 1,
        "idea": "Ship control flow policy support",
        "plan_versions": [{"version": 1, "file": "plan_v1.md"}],
        "meta": {"weighted_scores": []},
        "config": {"project_dir": str(tmp_path), "robustness": "full"},
    }

    gate_signals = build_gate_signals(plan_dir, state, root=tmp_path)

    assert gate_signals["signals"]["weighted_score"] == 0
    assert gate_signals["signals"]["unverifiable_checks"] == required_checks
    assert gate_signals["signals"]["execution_acceptance_contract"] == {
        "scope": "execute",
        "verification_mode": "verification_suite",
        "required_checks": required_checks,
    }
    assert not any(
        "critique degraded:" in warning for warning in gate_signals["warnings"]
    )

    projected = _gate_signals_for_prompt(gate_signals)
    prompt_signals = projected["signals"]
    assert prompt_signals["unverifiable_checks"] == required_checks
    assert prompt_signals["execution_acceptance_contract"]["required_checks"] == required_checks


def test_gate_prompt_hides_only_operational_unverifiable_checks() -> None:
    from arnold_pipelines.megaplan.prompts.gate import _gate_signals_for_prompt

    operational = {
        "id": "provider",
        "reason": "provider rate limit",
        "attention": "high_complexity_unverifiable",
    }
    projected = _gate_signals_for_prompt(
        {
            "signals": {
                "unverifiable_checks": [operational],
                "execution_acceptance_contract": {"required_checks": [operational]},
            }
        }
    )

    assert "unverifiable_checks" not in projected["signals"]
    assert "execution_acceptance_contract" not in projected["signals"]
