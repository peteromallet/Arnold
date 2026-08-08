from __future__ import annotations

import json
from pathlib import Path

import pytest

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
    assert any(
        "verdict='unverifiable_no_worker'" in flag["evidence"]
        and (
            "rationale='Required capabilities not satisfiable by any known worker.'"
            in flag["evidence"]
        )
        and "missing_capabilities=['not_a_registered_capability']" in flag["evidence"]
        and "success_criteria[0]" in flag["evidence"]
        and "criterion='Prove the contract.'" in flag["evidence"]
        and "requires=['not_a_registered_capability']" in flag["evidence"]
        for flag in flags
    )


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


# ══════════════════════════════════════════════════════════════════════
# CL4 (Step 8): gate-signal adjacency / recurrence / bridge split (T9)
# ══════════════════════════════════════════════════════════════════════


def _cl4_gate_signals_plan(
    tmp_path: Path,
    *,
    iteration: int = 2,
    critique_flags_by_iteration: dict[int, list[dict]] | None = None,
    reconciliation_events: list[dict] | None = None,
    reconciliation_artifact: bool = False,
):
    """Build a minimal plan_dir + state and return build_gate_signals output.

    critique_flags_by_iteration maps iteration -> list of flag dicts written
    to ``critique_v{iteration}.json``. When reconciliation_events is provided
    they are written either to a dedicated ``reconciliation_v{iteration}.json``
    (reconciliation_artifact=True) or embedded in the critique artifact under
    ``reconciliation_events``.
    """
    from arnold_pipelines.megaplan.orchestration.gate_signals import build_gate_signals

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    critique_flags_by_iteration = critique_flags_by_iteration or {}

    plan_file = f"plan_v{iteration}.md"
    (plan_dir / plan_file).write_text(f"# Plan iteration {iteration}\n", encoding="utf-8")
    (plan_dir / "faults.json").write_text(json.dumps({"flags": []}), encoding="utf-8")
    for it, flags in critique_flags_by_iteration.items():
        payload: dict = {"flags": flags}
        if reconciliation_events and it == iteration and not reconciliation_artifact:
            payload["reconciliation_events"] = reconciliation_events
        (plan_dir / f"critique_v{it}.json").write_text(
            json.dumps(payload), encoding="utf-8",
        )
    if reconciliation_events and reconciliation_artifact:
        (plan_dir / f"reconciliation_v{iteration}.json").write_text(
            json.dumps({"reconciliation_events": reconciliation_events}),
            encoding="utf-8",
        )

    state = {
        "iteration": iteration,
        "idea": "CL4 adjacency/recurrence split",
        "plan_versions": [{"version": iteration, "file": plan_file}],
        "meta": {"weighted_scores": []},
        "config": {"project_dir": str(tmp_path), "robustness": "full"},
    }
    return build_gate_signals(plan_dir, state, root=tmp_path)


def test_adjacent_text_matches_is_exact_text_overlap(tmp_path: Path) -> None:
    signals = _cl4_gate_signals_plan(
        tmp_path,
        critique_flags_by_iteration={
            1: [{"concern": "Gate allows stale evidence"}],
            2: [
                {"concern": "Gate allows stale evidence"},
                {"concern": "New unrelated concern"},
            ],
        },
    )
    s = signals["signals"]
    # The overlapping concern (normalized to lower-case) is the only match.
    assert s["adjacent_text_matches"] == ["gate allows stale evidence"]
    # Informational list is non-empty.
    assert len(s["adjacent_text_matches"]) == 1


def test_no_adjacent_text_match_is_exact_complement(tmp_path: Path) -> None:
    signals = _cl4_gate_signals_plan(
        tmp_path,
        critique_flags_by_iteration={
            1: [{"concern": "Gate allows stale evidence"}],
            2: [{"concern": "Gate allows stale evidence"}],
        },
    )
    s = signals["signals"]
    # Complement invariant: non-empty matches ⟺ no_adjacent_text_match False.
    assert s["no_adjacent_text_match"] is False
    assert s["no_adjacent_text_match"] == (len(s["adjacent_text_matches"]) == 0)


def test_no_adjacency_when_no_overlap(tmp_path: Path) -> None:
    signals = _cl4_gate_signals_plan(
        tmp_path,
        critique_flags_by_iteration={
            1: [{"concern": "Concern alpha"}],
            2: [{"concern": "Concern beta"}],
        },
    )
    s = signals["signals"]
    assert s["adjacent_text_matches"] == []
    assert s["no_adjacent_text_match"] is True
    assert s["no_adjacent_text_match"] == (len(s["adjacent_text_matches"]) == 0)


def test_adjacency_empty_at_first_iteration(tmp_path: Path) -> None:
    signals = _cl4_gate_signals_plan(
        tmp_path,
        iteration=1,
        critique_flags_by_iteration={1: [{"concern": "Lone concern"}]},
    )
    s = signals["signals"]
    assert s["adjacent_text_matches"] == []
    assert s["no_adjacent_text_match"] is True


def test_recurring_critiques_alias_equals_adjacent_text_matches(tmp_path: Path) -> None:
    signals = _cl4_gate_signals_plan(
        tmp_path,
        critique_flags_by_iteration={
            1: [{"concern": "Shared concern"}],
            2: [{"concern": "Shared concern"}],
        },
    )
    s = signals["signals"]
    # Deprecated alias is populated from adjacent_text_matches unchanged.
    assert s["recurring_critiques"] == s["adjacent_text_matches"]
    assert s["recurring_critiques"] == ["shared concern"]


def test_semantic_recurrence_false_without_reconciliation(tmp_path: Path) -> None:
    signals = _cl4_gate_signals_plan(
        tmp_path,
        critique_flags_by_iteration={
            1: [{"concern": "Shared concern"}],
            2: [{"concern": "Shared concern"}],
        },
    )
    s = signals["signals"]
    # Exact-text overlap exists, but no reconciliation evidence -> False.
    assert s["semantic_recurrence"] is False
    # adjacency is independent of recurrence.
    assert s["adjacent_text_matches"] == ["shared concern"]


@pytest.mark.parametrize("relationship", ["DUPLICATE", "REFINEMENT", "MERGE"])
def test_semantic_recurrence_true_with_sameness_relationship(
    tmp_path: Path, relationship: str,
) -> None:
    signals = _cl4_gate_signals_plan(
        tmp_path,
        critique_flags_by_iteration={
            1: [{"concern": "Concern one"}],
            2: [{"concern": "Concern two"}],
        },
        reconciliation_events=[{"relationship": relationship}],
    )
    s = signals["signals"]
    # Reconciliation evidence grounds recurrence even without text overlap.
    assert s["semantic_recurrence"] is True
    # adjacency is empty (different text) — recurrence is NOT text-derived.
    assert s["adjacent_text_matches"] == []


@pytest.mark.parametrize("relationship", ["UNRELATED", "UNCERTAIN", "NEW"])
def test_semantic_recurrence_false_with_non_sameness_relationship(
    tmp_path: Path, relationship: str,
) -> None:
    signals = _cl4_gate_signals_plan(
        tmp_path,
        critique_flags_by_iteration={
            1: [{"concern": "Concern one"}],
            2: [{"concern": "Concern two"}],
        },
        reconciliation_events=[{"relationship": relationship}],
    )
    s = signals["signals"]
    assert s["semantic_recurrence"] is False


def test_semantic_recurrence_reads_dedicated_reconciliation_artifact(
    tmp_path: Path,
) -> None:
    signals = _cl4_gate_signals_plan(
        tmp_path,
        critique_flags_by_iteration={1: [{"concern": "x"}], 2: [{"concern": "y"}]},
        reconciliation_events=[{"relationship": "MERGE"}],
        reconciliation_artifact=True,
    )
    assert signals["signals"]["semantic_recurrence"] is True


def test_gate_signal_carries_bridge_mode_and_carried_blockers(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.orchestration.gate_signals import (
        CL4_BRIDGE_MODE,
        CL4_CARRIED_BLOCKERS,
    )

    signals = _cl4_gate_signals_plan(
        tmp_path,
        iteration=1,
        critique_flags_by_iteration={1: [{"concern": "x"}]},
    )
    s = signals["signals"]
    assert s["bridge_mode"] is CL4_BRIDGE_MODE is True
    assert s["carried_blockers"] == list(CL4_CARRIED_BLOCKERS)
    assert len(s["carried_blockers"]) == 5


def test_adjacent_text_matches_complement_holds_with_disputed_merge(
    tmp_path: Path,
) -> None:
    """The complement invariant (adjacent_text_matches ⟺ ¬no_adjacent_text_match)
    holds even when disputed MERGE reconciliation evidence is present for the
    same iteration. semantic_recurrence may be True, but it must not corrupt
    the adjacency complement."""
    signals = _cl4_gate_signals_plan(
        tmp_path,
        critique_flags_by_iteration={
            1: [{"concern": "Overlapping concern"}],
            2: [{"concern": "Overlapping concern"}],
        },
        # Disputed MERGE: one evaluator asserts MERGE, another disputes with
        # UNRELATED — both reconciliation events present for iteration 2.
        reconciliation_events=[
            {"relationship": "MERGE", "reason": "same root cause"},
            {"relationship": "UNRELATED", "reason": "evaluator B disagrees"},
        ],
    )
    s = signals["signals"]
    # Adjacency complement still holds.
    assert s["adjacent_text_matches"] == ["overlapping concern"]
    assert s["no_adjacent_text_match"] is False
    assert s["no_adjacent_text_match"] == (len(s["adjacent_text_matches"]) == 0)
    # MERGE grounds semantic recurrence despite the dispute.
    assert s["semantic_recurrence"] is True
    # Deprecated alias still mirrors adjacency.
    assert s["recurring_critiques"] == s["adjacent_text_matches"]
