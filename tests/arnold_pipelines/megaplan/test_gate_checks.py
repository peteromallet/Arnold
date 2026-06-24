from __future__ import annotations

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
