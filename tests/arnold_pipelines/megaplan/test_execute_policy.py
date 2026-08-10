"""Focused unit coverage for execute policy helpers.

Covers every pure helper and typed outcome in
``arnold_pipelines.megaplan.execute.policy`` without requiring runtime
setup or persistence fixtures.
"""

from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.execute.policy import (
    # Enums
    ApprovalOutcome,
    BlockedRetryOutcome,
    ExecuteEntryRoute,
    FutureParallelMarker,
    NextExecuteTransition,
    NoReviewTerminalOutcome,
    TierRouteOutcome,
    # Dataclass decisions
    ApprovalDecision,
    BlockedRetryDecision,
    ExecuteEntryDecision,
    NextStepDecision,
    NoReviewTerminalDecision,
    TierRouteDecision,
    # Pure helpers
    evaluate_destructive_approval,
    evaluate_no_review_terminal,
    resolve_batch_tier,
    resolve_execute_entry_route,
    resolve_single_batch_next_step,
)


# ============================================================================
# ExecuteEntryRoute / resolve_execute_entry_route
# ============================================================================

class TestResolveExecuteEntryRoute:
    """resolve_execute_entry_route maps plan state to a typed route."""

    # -- Proceed path --------------------------------------------------------

    def test_proceed_from_finalized(self) -> None:
        decision = resolve_execute_entry_route("finalized")
        assert decision.route == ExecuteEntryRoute.PROCEED
        assert decision.may_proceed is True
        assert "finalized" in decision.reason

    def test_proceed_from_custom_allowed_state(self) -> None:
        decision = resolve_execute_entry_route(
            "reviewing",
            allowed_entry_states=frozenset({"reviewing"}),
        )
        assert decision.route == ExecuteEntryRoute.PROCEED
        assert decision.may_proceed is True

    # -- Blocked path --------------------------------------------------------

    def test_blocked_from_blocked_state(self) -> None:
        decision = resolve_execute_entry_route("blocked")
        assert decision.route == ExecuteEntryRoute.BLOCKED
        assert decision.may_proceed is False
        assert "blocked" in decision.reason.lower()

    # -- Failed path ---------------------------------------------------------

    def test_failed_from_failed_state(self) -> None:
        decision = resolve_execute_entry_route("failed")
        assert decision.route == ExecuteEntryRoute.FAILED
        assert decision.may_proceed is False
        assert "failed" in decision.reason.lower()

    # -- Invalid path --------------------------------------------------------

    def test_invalid_state_returns_invalid(self) -> None:
        decision = resolve_execute_entry_route("nonexistent")
        assert decision.route == ExecuteEntryRoute.INVALID
        assert decision.may_proceed is False
        assert "nonexistent" in decision.reason

    def test_invalid_with_custom_allowed_set(self) -> None:
        decision = resolve_execute_entry_route(
            "blocked",
            allowed_entry_states=frozenset({"finalized"}),
        )
        assert decision.route == ExecuteEntryRoute.INVALID
        assert "blocked" in decision.reason

    def test_invalid_with_empty_allowed_set(self) -> None:
        decision = resolve_execute_entry_route(
            "finalized",
            allowed_entry_states=frozenset(),
        )
        assert decision.route == ExecuteEntryRoute.INVALID

    # -- Default allowed set -------------------------------------------------

    def test_default_allowed_states_are_finalized_blocked_failed(self) -> None:
        # verify the default set treats finalized as proceed
        assert resolve_execute_entry_route("finalized").may_proceed is True
        assert resolve_execute_entry_route("blocked").route == ExecuteEntryRoute.BLOCKED
        assert resolve_execute_entry_route("failed").route == ExecuteEntryRoute.FAILED
        assert resolve_execute_entry_route("unknown").route == ExecuteEntryRoute.INVALID


# ============================================================================
# ApprovalOutcome / evaluate_destructive_approval
# ============================================================================

class TestEvaluateDestructiveApproval:
    """Evaluate the destructive-confirmation and user-approval gates."""

    # -- Approved ------------------------------------------------------------

    def test_approved_when_all_clear(self) -> None:
        decision = evaluate_destructive_approval(
            confirm_destructive=True,
            auto_approve=True,
            user_approved_gate=False,
            is_prose_mode=False,
        )
        assert decision.outcome == ApprovalOutcome.APPROVED
        assert decision.is_approved is True

    def test_approved_with_auto_approve_and_confirm(self) -> None:
        decision = evaluate_destructive_approval(
            confirm_destructive=True,
            auto_approve=True,
            user_approved_gate=False,
            is_prose_mode=False,
        )
        assert decision.outcome == ApprovalOutcome.APPROVED

    def test_approved_with_user_gate_when_auto_approve_false(self) -> None:
        decision = evaluate_destructive_approval(
            confirm_destructive=True,
            auto_approve=False,
            user_approved_gate=True,
            is_prose_mode=False,
        )
        assert decision.outcome == ApprovalOutcome.APPROVED
        assert decision.is_approved is True

    # -- Prose mode skips destructive confirmation ---------------------------

    def test_prose_mode_skips_destructive_confirm(self) -> None:
        decision = evaluate_destructive_approval(
            confirm_destructive=False,
            auto_approve=True,
            user_approved_gate=False,
            is_prose_mode=True,
        )
        assert decision.outcome == ApprovalOutcome.APPROVED
        assert decision.is_approved is True

    def test_prose_mode_still_requires_approval(self) -> None:
        decision = evaluate_destructive_approval(
            confirm_destructive=False,
            auto_approve=False,
            user_approved_gate=False,
            is_prose_mode=True,
        )
        assert decision.outcome == ApprovalOutcome.DENIED_MISSING_APPROVAL
        assert decision.is_approved is False

    # -- Denied: missing destructive confirmation ----------------------------

    def test_denied_missing_confirm(self) -> None:
        decision = evaluate_destructive_approval(
            confirm_destructive=False,
            auto_approve=True,
            user_approved_gate=False,
            is_prose_mode=False,
        )
        assert decision.outcome == ApprovalOutcome.DENIED_MISSING_CONFIRM
        assert decision.is_approved is False
        assert "confirm-destructive" in decision.reason

    def test_denied_missing_confirm_even_with_approval(self) -> None:
        decision = evaluate_destructive_approval(
            confirm_destructive=False,
            auto_approve=False,
            user_approved_gate=True,
            is_prose_mode=False,
        )
        assert decision.outcome == ApprovalOutcome.DENIED_MISSING_CONFIRM

    # -- Denied: missing user approval ---------------------------------------

    def test_denied_missing_approval(self) -> None:
        decision = evaluate_destructive_approval(
            confirm_destructive=True,
            auto_approve=False,
            user_approved_gate=False,
            is_prose_mode=False,
        )
        assert decision.outcome == ApprovalOutcome.DENIED_MISSING_APPROVAL
        assert decision.is_approved is False
        assert "user" in decision.reason.lower()

    # -- Enum exhaustiveness -------------------------------------------------

    def test_approval_outcome_enum_values(self) -> None:
        assert set(ApprovalOutcome) == {
            ApprovalOutcome.APPROVED,
            ApprovalOutcome.DENIED_MISSING_CONFIRM,
            ApprovalOutcome.DENIED_MISSING_APPROVAL,
        }

    def test_approval_decision_defaults(self) -> None:
        d = ApprovalDecision(ApprovalOutcome.APPROVED)
        assert d.reason == ""
        assert d.is_approved is True

    def test_approval_decision_frozen(self) -> None:
        d = ApprovalDecision(ApprovalOutcome.APPROVED, reason="ok")
        with pytest.raises(Exception):
            d.outcome = ApprovalOutcome.DENIED_MISSING_CONFIRM  # type: ignore[misc]


# ============================================================================
# NoReviewTerminalOutcome / evaluate_no_review_terminal
# ============================================================================

class TestEvaluateNoReviewTerminal:
    """Evaluate no-review terminal routing across robustness levels."""

    # -- Bare robustness -----------------------------------------------------

    def test_bare_robustness_terminates_done(self) -> None:
        decision = evaluate_no_review_terminal(robustness="bare")
        assert decision.outcome == NoReviewTerminalOutcome.TERMINATE_DONE
        assert decision.target_state == "done"
        assert decision.should_terminate is True
        assert "bare" in decision.reason.lower()

    def test_bare_robustness_with_deferred_must_still_terminates_done(self) -> None:
        decision = evaluate_no_review_terminal(
            robustness="bare", has_deferred_must=True
        )
        # bare always terminates to done regardless of deferred must
        assert decision.outcome == NoReviewTerminalOutcome.TERMINATE_DONE
        assert decision.target_state == "done"

    # -- Light robustness ----------------------------------------------------

    def test_light_without_deferred_must_terminates_done(self) -> None:
        decision = evaluate_no_review_terminal(robustness="light")
        assert decision.outcome == NoReviewTerminalOutcome.TERMINATE_DONE
        assert decision.target_state == "done"
        assert decision.should_terminate is True

    def test_light_with_deferred_must_terminates_awaiting_human(self) -> None:
        decision = evaluate_no_review_terminal(
            robustness="light", has_deferred_must=True
        )
        assert decision.outcome == NoReviewTerminalOutcome.TERMINATE_AWAITING_HUMAN
        assert decision.target_state == "awaiting_human_verify"
        assert decision.should_terminate is True
        assert "human" in decision.reason.lower()

    # -- Standard robustness -------------------------------------------------

    def test_standard_without_deferred_must_not_applicable(self) -> None:
        decision = evaluate_no_review_terminal(robustness="standard")
        assert decision.outcome == NoReviewTerminalOutcome.NOT_APPLICABLE
        assert decision.target_state is None
        assert decision.should_terminate is False

    def test_standard_with_deferred_must_terminates_awaiting_human(self) -> None:
        decision = evaluate_no_review_terminal(
            robustness="standard", has_deferred_must=True
        )
        assert decision.outcome == NoReviewTerminalOutcome.TERMINATE_AWAITING_HUMAN
        assert decision.target_state == "awaiting_human_verify"
        assert decision.should_terminate is True

    # -- Thorough robustness -------------------------------------------------

    def test_thorough_not_applicable(self) -> None:
        decision = evaluate_no_review_terminal(robustness="thorough")
        assert decision.outcome == NoReviewTerminalOutcome.NOT_APPLICABLE
        assert decision.should_terminate is False

    def test_thorough_with_deferred_must_not_applicable(self) -> None:
        decision = evaluate_no_review_terminal(
            robustness="thorough", has_deferred_must=True
        )
        assert decision.outcome == NoReviewTerminalOutcome.NOT_APPLICABLE

    # -- Unknown robustness --------------------------------------------------

    def test_unknown_robustness_not_applicable(self) -> None:
        decision = evaluate_no_review_terminal(robustness="ultra")
        assert decision.outcome == NoReviewTerminalOutcome.NOT_APPLICABLE
        assert decision.should_terminate is False

    # -- Enum / dataclass ----------------------------------------------------

    def test_no_review_terminal_outcome_enum_values(self) -> None:
        assert set(NoReviewTerminalOutcome) == {
            NoReviewTerminalOutcome.TERMINATE_DONE,
            NoReviewTerminalOutcome.TERMINATE_AWAITING_HUMAN,
            NoReviewTerminalOutcome.NOT_APPLICABLE,
        }

    def test_no_review_terminal_defaults(self) -> None:
        d = NoReviewTerminalDecision(NoReviewTerminalOutcome.NOT_APPLICABLE)
        assert d.target_state is None
        assert d.reason == ""
        assert d.should_terminate is False

    def test_no_review_decision_frozen(self) -> None:
        d = NoReviewTerminalDecision(NoReviewTerminalOutcome.NOT_APPLICABLE)
        with pytest.raises(Exception):
            d.target_state = "done"  # type: ignore[misc]


# ============================================================================
# BlockedRetryOutcome / BlockedRetryDecision
# ============================================================================

class TestBlockedRetry:
    """Typed outcomes and decision for blocked-task retry evaluation."""

    def test_enum_values(self) -> None:
        assert set(BlockedRetryOutcome) == {
            BlockedRetryOutcome.RETRY_FRESH,
            BlockedRetryOutcome.NO_RETRY,
            BlockedRetryOutcome.RETRY,
        }

    def test_retry_should_retry(self) -> None:
        d = BlockedRetryDecision(BlockedRetryOutcome.RETRY)
        assert d.should_retry is True

    def test_retry_fresh_should_retry(self) -> None:
        d = BlockedRetryDecision(BlockedRetryOutcome.RETRY_FRESH)
        assert d.should_retry is True

    def test_no_retry_should_not_retry(self) -> None:
        d = BlockedRetryDecision(BlockedRetryOutcome.NO_RETRY)
        assert d.should_retry is False

    def test_decision_defaults(self) -> None:
        d = BlockedRetryDecision(BlockedRetryOutcome.NO_RETRY)
        assert d.reason == ""

    def test_decision_frozen(self) -> None:
        d = BlockedRetryDecision(BlockedRetryOutcome.NO_RETRY, reason="stale")
        with pytest.raises(Exception):
            d.outcome = BlockedRetryOutcome.RETRY  # type: ignore[misc]

    def test_string_values(self) -> None:
        assert BlockedRetryOutcome.RETRY_FRESH.value == "retry_fresh"
        assert BlockedRetryOutcome.NO_RETRY.value == "no_retry"
        assert BlockedRetryOutcome.RETRY.value == "retry"


# ============================================================================
# TierRouteOutcome / resolve_batch_tier
# ============================================================================

class TestResolveBatchTier:
    """Resolve tier spec from batch complexity and tier map."""

    # -- No tier map ---------------------------------------------------------

    def test_no_tier_map_none(self) -> None:
        decision = resolve_batch_tier(tier_map=None, batch_complexity=3)
        assert decision.outcome == TierRouteOutcome.NO_TIER_MAP
        assert decision.spec is None
        assert decision.selected_tier is None
        assert decision.has_spec is False

    def test_no_tier_map_empty(self) -> None:
        decision = resolve_batch_tier(tier_map={}, batch_complexity=3)
        assert decision.outcome == TierRouteOutcome.NO_TIER_MAP
        assert decision.has_spec is False

    # -- Exact match ---------------------------------------------------------

    def test_exact_match(self) -> None:
        tier_map = {1: "haiku", 3: "sonnet", 5: "opus"}
        decision = resolve_batch_tier(tier_map=tier_map, batch_complexity=3)
        assert decision.outcome == TierRouteOutcome.ROUTED
        assert decision.spec == "sonnet"
        assert decision.selected_tier == 3
        assert decision.has_spec is True

    def test_exact_match_tier_1(self) -> None:
        tier_map = {1: "haiku", 3: "sonnet"}
        decision = resolve_batch_tier(tier_map=tier_map, batch_complexity=1)
        assert decision.outcome == TierRouteOutcome.ROUTED
        assert decision.spec == "haiku"
        assert decision.selected_tier == 1

    def test_exact_match_tier_5(self) -> None:
        tier_map = {5: "opus"}
        decision = resolve_batch_tier(tier_map=tier_map, batch_complexity=5)
        assert decision.outcome == TierRouteOutcome.ROUTED
        assert decision.spec == "opus"
        assert decision.selected_tier == 5

    # -- Fallback ------------------------------------------------------------

    def test_fallback_to_highest_lower_tier(self) -> None:
        tier_map = {1: "haiku", 3: "sonnet", 5: "opus"}
        decision = resolve_batch_tier(tier_map=tier_map, batch_complexity=4)
        assert decision.outcome == TierRouteOutcome.ROUTED
        assert decision.spec == "sonnet"
        assert decision.selected_tier == 3
        assert decision.has_spec is True

    def test_fallback_multiple_lower_tiers_chooses_highest(self) -> None:
        tier_map = {1: "haiku", 2: "tiny", 3: "sonnet"}
        decision = resolve_batch_tier(tier_map=tier_map, batch_complexity=4)
        assert decision.outcome == TierRouteOutcome.ROUTED
        assert decision.spec == "sonnet"
        assert decision.selected_tier == 3

    def test_fallback_when_exact_is_empty_string(self) -> None:
        tier_map = {1: "haiku", 3: ""}
        decision = resolve_batch_tier(tier_map=tier_map, batch_complexity=3)
        # exact match should be skipped because empty string is falsy
        assert decision.outcome == TierRouteOutcome.ROUTED
        assert decision.spec == "haiku"
        assert decision.selected_tier == 1

    # -- Default (no usable tier) --------------------------------------------

    def test_default_when_no_tier_below(self) -> None:
        tier_map = {3: "sonnet", 5: "opus"}
        decision = resolve_batch_tier(tier_map=tier_map, batch_complexity=2)
        assert decision.outcome == TierRouteOutcome.DEFAULT
        assert decision.spec is None
        assert decision.selected_tier is None
        assert decision.has_spec is False
        assert "sonnet" in decision.reason  # available tiers listed

    def test_default_when_tier_map_has_only_higher_keys(self) -> None:
        tier_map = {4: "sonnet", 5: "opus"}
        decision = resolve_batch_tier(tier_map=tier_map, batch_complexity=2)
        assert decision.outcome == TierRouteOutcome.DEFAULT

    # -- Empty/blank spec in tier map doesn't count as match -----------------

    def test_blank_spec_without_fallback_is_default(self) -> None:
        tier_map = {3: ""}
        decision = resolve_batch_tier(tier_map=tier_map, batch_complexity=3)
        # exact match is empty string -> falsy; no lower tiers
        assert decision.outcome == TierRouteOutcome.DEFAULT

    # -- Enum / dataclass ----------------------------------------------------

    def test_tier_route_outcome_enum_values(self) -> None:
        assert set(TierRouteOutcome) == {
            TierRouteOutcome.ROUTED,
            TierRouteOutcome.DEFAULT,
            TierRouteOutcome.NO_TIER_MAP,
        }

    def test_tier_route_decision_defaults(self) -> None:
        d = TierRouteDecision(TierRouteOutcome.NO_TIER_MAP)
        assert d.spec is None
        assert d.selected_tier is None
        assert d.reason == ""
        assert d.has_spec is False

    def test_has_spec_requires_non_empty_string(self) -> None:
        d = TierRouteDecision(
            TierRouteOutcome.ROUTED, spec="", selected_tier=3, reason="x"
        )
        assert d.has_spec is False

    def test_decision_frozen(self) -> None:
        d = TierRouteDecision(TierRouteOutcome.ROUTED, spec="sonnet")
        with pytest.raises(Exception):
            d.spec = "opus"  # type: ignore[misc]


# ============================================================================
# NextExecuteTransition / resolve_single_batch_next_step
# ============================================================================

class TestResolveSingleBatchNextStep:
    """Resolve what comes after a single batch executes."""

    # -- Blocked takes precedence --------------------------------------------

    def test_blocked_takes_precedence_over_final(self) -> None:
        decision = resolve_single_batch_next_step(
            is_final_batch=True, all_tracked=True, blocked=True
        )
        assert decision.transition == NextExecuteTransition.BLOCKED
        assert decision.is_final_batch is True
        assert decision.all_tracked is True
        assert "blocked" in decision.reason.lower()

    def test_blocked_mid_batch(self) -> None:
        decision = resolve_single_batch_next_step(
            is_final_batch=False, all_tracked=False, blocked=True
        )
        assert decision.transition == NextExecuteTransition.BLOCKED
        assert decision.is_final_batch is False
        assert decision.all_tracked is False

    # -- Final batch + fully tracked → review --------------------------------

    def test_final_batch_all_tracked_review(self) -> None:
        decision = resolve_single_batch_next_step(
            is_final_batch=True, all_tracked=True, blocked=False
        )
        assert decision.transition == NextExecuteTransition.REVIEW
        assert decision.is_final_batch is True
        assert decision.all_tracked is True
        assert "review" in decision.reason.lower()

    # -- More batches remain → execute ---------------------------------------

    def test_not_final_batch_continues_execute(self) -> None:
        decision = resolve_single_batch_next_step(
            is_final_batch=False, all_tracked=False, blocked=False
        )
        assert decision.transition == NextExecuteTransition.EXECUTE
        assert "remain" in decision.reason.lower()

    def test_final_batch_not_all_tracked_continues_execute(self) -> None:
        decision = resolve_single_batch_next_step(
            is_final_batch=True, all_tracked=False, blocked=False
        )
        assert decision.transition == NextExecuteTransition.EXECUTE

    def test_not_final_but_all_tracked_continues_execute(self) -> None:
        # Unusual combination but policy says: if blocked=False and (not final or not tracked)
        decision = resolve_single_batch_next_step(
            is_final_batch=False, all_tracked=True, blocked=False
        )
        assert decision.transition == NextExecuteTransition.EXECUTE

    # -- Enum / dataclass ----------------------------------------------------

    def test_next_execute_transition_enum_values(self) -> None:
        assert set(NextExecuteTransition) == {
            NextExecuteTransition.EXECUTE,
            NextExecuteTransition.REVIEW,
            NextExecuteTransition.BLOCKED,
            NextExecuteTransition.DONE,
            NextExecuteTransition.AWAITING_HUMAN,
        }

    def test_next_step_decision_defaults(self) -> None:
        d = NextStepDecision(NextExecuteTransition.EXECUTE)
        assert d.is_final_batch is False
        assert d.all_tracked is False
        assert d.reason == ""

    def test_next_step_decision_frozen(self) -> None:
        d = NextStepDecision(NextExecuteTransition.EXECUTE)
        with pytest.raises(Exception):
            d.is_final_batch = True  # type: ignore[misc]


# ============================================================================
# FutureParallelMarker — reserved CANCEL / AWAIT / ORPHAN markers
# ============================================================================

class TestFutureParallelMarker:
    """Reserved markers for future parallel execute branches."""

    def test_enum_values_present(self) -> None:
        assert set(FutureParallelMarker) == {
            FutureParallelMarker.CANCEL,
            FutureParallelMarker.AWAIT,
            FutureParallelMarker.ORPHAN,
        }

    def test_cancel_value(self) -> None:
        assert FutureParallelMarker.CANCEL.value == "CANCEL"

    def test_await_value(self) -> None:
        assert FutureParallelMarker.AWAIT.value == "AWAIT"

    def test_orphan_value(self) -> None:
        assert FutureParallelMarker.ORPHAN.value == "ORPHAN"

    def test_marker_is_str_enum(self) -> None:
        assert isinstance(FutureParallelMarker.CANCEL, str)

    def test_cancel_not_in_transition_enum(self) -> None:
        # Ensure CANCEL/AWAIT/ORPHAN are only in FutureParallelMarker,
        # not accidentally in NextExecuteTransition.
        next_values = {e.value for e in NextExecuteTransition}
        assert "CANCEL" not in next_values
        assert "AWAIT" not in next_values
        assert "ORPHAN" not in next_values


# ============================================================================
# ExecuteEntryDecision dataclass edge cases
# ============================================================================

class TestExecuteEntryDecisionEdgeCases:
    """Additional edge cases for ExecuteEntryDecision not covered above."""

    def test_default_reason_empty(self) -> None:
        d = ExecuteEntryDecision(ExecuteEntryRoute.PROCEED)
        assert d.reason == ""

    def test_frozen(self) -> None:
        d = ExecuteEntryDecision(ExecuteEntryRoute.PROCEED)
        with pytest.raises(Exception):
            d.route = ExecuteEntryRoute.BLOCKED  # type: ignore[misc]

    def test_all_routes_map_to_correct_may_proceed(self) -> None:
        assert ExecuteEntryDecision(ExecuteEntryRoute.PROCEED).may_proceed is True
        assert ExecuteEntryDecision(ExecuteEntryRoute.BLOCKED).may_proceed is False
        assert ExecuteEntryDecision(ExecuteEntryRoute.FAILED).may_proceed is False
        assert ExecuteEntryDecision(ExecuteEntryRoute.INVALID).may_proceed is False


# ============================================================================
# Cross-cutting: import purity (no handler / batch / runtime imports)
# ============================================================================

class TestImportPurity:
    """Verify the policy module imports no handler, batch, or runtime code."""

    def test_policy_module_no_handler_imports(self) -> None:
        import ast
        import inspect
        from arnold_pipelines.megaplan.execute import policy

        source = inspect.getsource(policy)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module_name = (
                    node.module if isinstance(node, ast.ImportFrom) else ""
                )
                names = [
                    (alias.name if isinstance(node, ast.ImportFrom) else alias.name)
                    for alias in node.names
                ]
                # Build a representative string for the import
                full = f"{module_name or ''} {', '.join(names)}"
                lower = full.lower()
                assert "handler" not in lower, f"Handler import found: {full}"
                assert "batch" not in lower, f"Batch import found: {full}"
                assert "runtime" not in lower, f"Runtime import found: {full}"


# ============================================================================
# M8A T9 -- Circuit dispatch and failure evaluation policy tests
# ============================================================================


class TestCircuitDispatchOutcome:
    """CircuitDispatchOutcome enum and CircuitDispatchDecision dataclass."""

    def test_enum_values(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import CircuitDispatchOutcome
        assert set(CircuitDispatchOutcome) == {
            CircuitDispatchOutcome.PROCEED,
            CircuitDispatchOutcome.CIRCUIT_OPEN,
        }

    def test_decision_proceed(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitDispatchDecision,
            CircuitDispatchOutcome,
        )
        d = CircuitDispatchDecision(CircuitDispatchOutcome.PROCEED, reason="ok")
        assert d.may_dispatch is True
        assert d.open_signatures == ()
        assert d.reason == "ok"

    def test_decision_circuit_open(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitDispatchDecision,
            CircuitDispatchOutcome,
        )
        sigs = ({"failure_class": "worker_budget_exhausted", "task_id": "T7"},)
        d = CircuitDispatchDecision(
            CircuitDispatchOutcome.CIRCUIT_OPEN,
            open_signatures=sigs,
            reason="circuit open",
        )
        assert d.may_dispatch is False
        assert len(d.open_signatures) == 1
        assert d.open_signatures[0]["task_id"] == "T7"

    def test_decision_defaults(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitDispatchDecision,
            CircuitDispatchOutcome,
        )
        d = CircuitDispatchDecision(CircuitDispatchOutcome.PROCEED)
        assert d.open_signatures == ()
        assert d.reason == ""

    def test_decision_frozen(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitDispatchDecision,
            CircuitDispatchOutcome,
        )
        d = CircuitDispatchDecision(CircuitDispatchOutcome.PROCEED)
        with pytest.raises(Exception):
            d.outcome = CircuitDispatchOutcome.CIRCUIT_OPEN  # type: ignore[misc]

    def test_string_values(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import CircuitDispatchOutcome
        assert CircuitDispatchOutcome.PROCEED.value == "proceed"
        assert CircuitDispatchOutcome.CIRCUIT_OPEN.value == "circuit_open"


class TestCircuitFailureOutcome:
    """CircuitFailureOutcome enum and CircuitFailureDecision dataclass."""

    def test_enum_values(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import CircuitFailureOutcome
        assert set(CircuitFailureOutcome) == {
            CircuitFailureOutcome.ALLOW_RETRY,
            CircuitFailureOutcome.CIRCUIT_OPEN,
            CircuitFailureOutcome.CIRCUIT_ALREADY_OPEN,
        }

    def test_decision_allow_retry(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitFailureDecision,
            CircuitFailureOutcome,
        )
        d = CircuitFailureDecision(
            CircuitFailureOutcome.ALLOW_RETRY,
            signature={"failure_class": "test"},
            occurrence_count=1,
            reason="first occurrence",
        )
        assert d.may_retry is True
        assert d.is_open is False
        assert d.occurrence_count == 1

    def test_decision_circuit_open(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitFailureDecision,
            CircuitFailureOutcome,
        )
        d = CircuitFailureDecision(
            CircuitFailureOutcome.CIRCUIT_OPEN,
            signature={"failure_class": "test"},
            occurrence_count=2,
            reason="threshold reached",
        )
        assert d.may_retry is False
        assert d.is_open is True

    def test_decision_circuit_already_open(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitFailureDecision,
            CircuitFailureOutcome,
        )
        d = CircuitFailureDecision(
            CircuitFailureOutcome.CIRCUIT_ALREADY_OPEN,
            signature={"failure_class": "test"},
            occurrence_count=2,
            reason="already open",
        )
        assert d.may_retry is False
        assert d.is_open is True

    def test_decision_defaults(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitFailureDecision,
            CircuitFailureOutcome,
        )
        d = CircuitFailureDecision(CircuitFailureOutcome.ALLOW_RETRY, signature={})
        assert d.occurrence_count == 0
        assert d.threshold == 2
        assert d.reason == ""

    def test_decision_frozen(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitFailureDecision,
            CircuitFailureOutcome,
        )
        d = CircuitFailureDecision(CircuitFailureOutcome.ALLOW_RETRY, signature={})
        with pytest.raises(Exception):
            d.outcome = CircuitFailureOutcome.CIRCUIT_OPEN  # type: ignore[misc]

    def test_string_values(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import CircuitFailureOutcome
        assert CircuitFailureOutcome.ALLOW_RETRY.value == "allow_retry"
        assert CircuitFailureOutcome.CIRCUIT_OPEN.value == "circuit_open"
        assert CircuitFailureOutcome.CIRCUIT_ALREADY_OPEN.value == "circuit_already_open"


class TestEvaluateCircuitBeforeDispatch:
    """evaluate_circuit_before_dispatch pure policy function."""

    @staticmethod
    def _circuit():
        from arnold_pipelines.megaplan.orchestration.plan_circuit import PlanCircuit
        return PlanCircuit()

    def test_empty_circuit_allows_dispatch(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitDispatchOutcome,
            evaluate_circuit_before_dispatch,
        )
        d = evaluate_circuit_before_dispatch(self._circuit(), task_ids=["T1", "T2"])
        assert d.outcome == CircuitDispatchOutcome.PROCEED
        assert d.may_dispatch is True
        assert "No open circuits" in d.reason

    def test_open_circuit_blocks_matching_task(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitDispatchOutcome,
            evaluate_circuit_before_dispatch,
        )
        from arnold_pipelines.megaplan.orchestration.plan_circuit import FailureSignature

        c = self._circuit()
        sig = FailureSignature(failure_class="worker_budget_exhausted", task_id="T7")
        c.record_failure(sig)
        c.record_failure(sig)  # opens circuit

        d = evaluate_circuit_before_dispatch(c, task_ids=["T7", "T8"])
        assert d.outcome == CircuitDispatchOutcome.CIRCUIT_OPEN
        assert d.may_dispatch is False
        assert len(d.open_signatures) == 1
        assert d.open_signatures[0]["task_id"] == "T7"
        assert d.open_signatures[0]["failure_class"] == "worker_budget_exhausted"

    def test_open_circuit_does_not_block_unrelated_task(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitDispatchOutcome,
            evaluate_circuit_before_dispatch,
        )
        from arnold_pipelines.megaplan.orchestration.plan_circuit import FailureSignature

        c = self._circuit()
        sig = FailureSignature(failure_class="worker_budget_exhausted", task_id="T7")
        c.record_failure(sig)
        c.record_failure(sig)

        d = evaluate_circuit_before_dispatch(c, task_ids=["T12", "T13"])
        assert d.outcome == CircuitDispatchOutcome.PROCEED
        assert d.may_dispatch is True

    def test_multiple_open_circuits_reported(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitDispatchOutcome,
            evaluate_circuit_before_dispatch,
        )
        from arnold_pipelines.megaplan.orchestration.plan_circuit import FailureSignature

        c = self._circuit()
        for tid in ("T7", "T9"):
            sig = FailureSignature(failure_class="blocked_by_prereq", task_id=tid)
            c.record_failure(sig)
            c.record_failure(sig)

        d = evaluate_circuit_before_dispatch(c, task_ids=["T7", "T8", "T9"])
        assert d.outcome == CircuitDispatchOutcome.CIRCUIT_OPEN
        assert len(d.open_signatures) == 2
        blocked_tasks = {s["task_id"] for s in d.open_signatures}
        assert blocked_tasks == {"T7", "T9"}

    def test_none_circuit_allows_dispatch(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitDispatchOutcome,
            evaluate_circuit_before_dispatch,
        )
        d = evaluate_circuit_before_dispatch(None, task_ids=["T1"])
        assert d.outcome == CircuitDispatchOutcome.PROCEED

    def test_batch_id_in_reason(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitDispatchOutcome,
            evaluate_circuit_before_dispatch,
        )
        from arnold_pipelines.megaplan.orchestration.plan_circuit import FailureSignature

        c = self._circuit()
        sig = FailureSignature(failure_class="test", task_id="T5")
        c.record_failure(sig)
        c.record_failure(sig)

        d = evaluate_circuit_before_dispatch(c, task_ids=["T5"], batch_id="B3")
        assert d.outcome == CircuitDispatchOutcome.CIRCUIT_OPEN
        assert "Batch B3" in d.reason

    def test_empty_task_ids_with_open_circuit_blocks(self) -> None:
        """When no specific task_ids are given, any open circuit blocks dispatch."""
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitDispatchOutcome,
            evaluate_circuit_before_dispatch,
        )
        from arnold_pipelines.megaplan.orchestration.plan_circuit import FailureSignature

        c = self._circuit()
        sig = FailureSignature(failure_class="test", task_id="T1")
        c.record_failure(sig)
        c.record_failure(sig)

        d = evaluate_circuit_before_dispatch(c)
        assert d.outcome == CircuitDispatchOutcome.CIRCUIT_OPEN


class TestEvaluateCircuitAfterFailure:
    """evaluate_circuit_after_failure pure policy function."""

    @staticmethod
    def _circuit():
        from arnold_pipelines.megaplan.orchestration.plan_circuit import PlanCircuit
        return PlanCircuit()

    @staticmethod
    def _err(**kw):
        from types import SimpleNamespace
        return SimpleNamespace(**kw)

    def test_first_failure_allows_retry(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitFailureOutcome,
            evaluate_circuit_after_failure,
        )
        err = self._err(halt_kind="worker_budget_exhausted")
        d = evaluate_circuit_after_failure(self._circuit(), err, task_id="T7")
        assert d.outcome == CircuitFailureOutcome.ALLOW_RETRY
        assert d.may_retry is True
        assert d.is_open is False
        assert d.occurrence_count == 1
        assert d.signature["failure_class"] == "worker_budget_exhausted"
        assert d.signature["task_id"] == "T7"

    def test_second_failure_opens_circuit(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitFailureOutcome,
            evaluate_circuit_after_failure,
        )
        c = self._circuit()
        err = self._err(halt_kind="worker_budget_exhausted")
        evaluate_circuit_after_failure(c, err, task_id="T7")
        d = evaluate_circuit_after_failure(c, err, task_id="T7")
        assert d.outcome == CircuitFailureOutcome.CIRCUIT_OPEN
        assert d.is_open is True
        assert d.may_retry is False
        assert d.occurrence_count == 2

    def test_third_failure_reports_circuit_already_open(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitFailureOutcome,
            evaluate_circuit_after_failure,
        )
        c = self._circuit()
        err = self._err(halt_kind="worker_budget_exhausted")
        evaluate_circuit_after_failure(c, err, task_id="T7")
        evaluate_circuit_after_failure(c, err, task_id="T7")
        d = evaluate_circuit_after_failure(c, err, task_id="T7")
        assert d.outcome == CircuitFailureOutcome.CIRCUIT_ALREADY_OPEN
        assert d.is_open is True
        assert d.may_retry is False

    def test_different_tasks_independent(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitFailureOutcome,
            evaluate_circuit_after_failure,
        )
        c = self._circuit()
        err = self._err(halt_kind="worker_budget_exhausted")

        # T7: two failures, circuit open
        evaluate_circuit_after_failure(c, err, task_id="T7")
        evaluate_circuit_after_failure(c, err, task_id="T7")

        # T12: first failure, still allowed
        d = evaluate_circuit_after_failure(c, err, task_id="T12")
        assert d.outcome == CircuitFailureOutcome.ALLOW_RETRY
        assert d.occurrence_count == 1

    def test_preserves_exact_failure_identity(self) -> None:
        """The signature dict must preserve exact failure identity fields."""
        from arnold_pipelines.megaplan.execute.policy import evaluate_circuit_after_failure
        import hashlib, json

        c = self._circuit()
        err = self._err(halt_kind="worker_budget_exhausted")
        blocker = {"kind": "budget_exhausted", "reason": "test", "iterations": 90}
        digest = hashlib.sha256(json.dumps(blocker, sort_keys=True, default=str).encode()).hexdigest()

        d = evaluate_circuit_after_failure(
            c, err,
            task_id="T7",
            batch_id="B3",
            attempt_id="A2",
            blocker=blocker,
            provider="anthropic",
            ref_metadata="abc123def",
            fence="fence-v1",
        )
        sig = d.signature
        assert sig["failure_class"] == "worker_budget_exhausted"
        assert sig["task_id"] == "T7"
        assert sig["batch_id"] == "B3"
        assert sig["attempt_id"] == "A2"
        assert sig["blocker_digest"] == digest
        assert sig["provider"] == "anthropic"
        assert sig["ref_metadata"] == "abc123def"
        assert sig["fence"] == "fence-v1"

    def test_none_circuit_allows_retry(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitFailureOutcome,
            evaluate_circuit_after_failure,
        )
        err = self._err(halt_kind="worker_budget_exhausted")
        d = evaluate_circuit_after_failure(None, err, task_id="T7")
        assert d.outcome == CircuitFailureOutcome.ALLOW_RETRY

    def test_explicit_failure_class_override(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import evaluate_circuit_after_failure
        err = self._err()  # no known fields, would be unclassified
        d = evaluate_circuit_after_failure(
            self._circuit(), err, task_id="T7", failure_class="blocked_by_prereq"
        )
        assert d.signature["failure_class"] == "blocked_by_prereq"

    def test_reason_includes_count_and_threshold(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import evaluate_circuit_after_failure
        err = self._err(halt_kind="worker_budget_exhausted")
        d = evaluate_circuit_after_failure(self._circuit(), err, task_id="T7")
        assert "occurrence 1/2" in d.reason
        assert "worker_budget_exhausted" in d.reason


class TestBuildCircuitEvidenceProjection:
    """build_circuit_evidence_projection pure policy function."""

    @staticmethod
    def _circuit():
        from arnold_pipelines.megaplan.orchestration.plan_circuit import PlanCircuit
        return PlanCircuit()

    def test_empty_circuit_projection(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import build_circuit_evidence_projection
        p = build_circuit_evidence_projection(self._circuit())
        assert p["circuit_threshold"] == 2
        assert p["open_signatures"] == []
        assert p["occurrence_counts"] == {}
        assert p["total_open_circuits"] == 0

    def test_open_circuit_projection(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import build_circuit_evidence_projection
        from arnold_pipelines.megaplan.orchestration.plan_circuit import FailureSignature

        c = self._circuit()
        sig = FailureSignature(failure_class="blocked_by_prereq", task_id="T7", batch_id="B3")
        c.record_failure(sig)
        c.record_failure(sig)  # opens

        p = build_circuit_evidence_projection(c)
        assert p["total_open_circuits"] == 1
        assert len(p["open_signatures"]) == 1
        assert p["open_signatures"][0]["failure_class"] == "blocked_by_prereq"
        assert p["open_signatures"][0]["task_id"] == "T7"
        assert "blocked_by_prereq" in p["occurrence_counts"]
        assert p["occurrence_counts"]["blocked_by_prereq"]["T7"] == 2

    def test_multiple_classes_projection(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import build_circuit_evidence_projection
        from arnold_pipelines.megaplan.orchestration.plan_circuit import FailureSignature

        c = self._circuit()
        for fc, tid in (("blocked_by_prereq", "T7"), ("context_exhausted", "T9")):
            sig = FailureSignature(failure_class=fc, task_id=tid)
            c.record_failure(sig)
            c.record_failure(sig)

        p = build_circuit_evidence_projection(c)
        assert p["total_open_circuits"] == 2
        assert "blocked_by_prereq" in p["occurrence_counts"]
        assert "context_exhausted" in p["occurrence_counts"]
        assert p["occurrence_counts"]["blocked_by_prereq"]["T7"] == 2
        assert p["occurrence_counts"]["context_exhausted"]["T9"] == 2

    def test_none_circuit_projection(self) -> None:
        from arnold_pipelines.megaplan.execute.policy import build_circuit_evidence_projection
        p = build_circuit_evidence_projection(None)
        assert p["total_open_circuits"] == 0
        assert p["circuit_threshold"] == 2

    def test_projection_is_rebuildable(self) -> None:
        """Projection metadata must be a plain dict with no non-serializable types."""
        from arnold_pipelines.megaplan.execute.policy import build_circuit_evidence_projection
        from arnold_pipelines.megaplan.orchestration.plan_circuit import FailureSignature
        import json

        c = self._circuit()
        sig = FailureSignature(failure_class="test", task_id="T1", blocker_digest="abc123")
        c.record_failure(sig)
        c.record_failure(sig)

        p = build_circuit_evidence_projection(c)
        # Must be JSON-serializable
        serialized = json.dumps(p, default=str)
        assert isinstance(serialized, str)
        # Roundtrip
        restored = json.loads(serialized)
        assert restored["total_open_circuits"] == 1
        assert restored["open_signatures"][0]["task_id"] == "T1"


class TestCircuitIntegration:
    """End-to-end circuit integration: before-dispatch check + after-failure record."""

    @staticmethod
    def _circuit():
        from arnold_pipelines.megaplan.orchestration.plan_circuit import PlanCircuit
        return PlanCircuit()

    @staticmethod
    def _err(**kw):
        from types import SimpleNamespace
        return SimpleNamespace(**kw)

    def test_full_circuit_lifecycle(self) -> None:
        """Simulate the full circuit lifecycle: dispatch, failure, circuit open, blocked."""
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitDispatchOutcome,
            CircuitFailureOutcome,
            evaluate_circuit_before_dispatch,
            evaluate_circuit_after_failure,
        )

        c = self._circuit()
        err = self._err(halt_kind="worker_budget_exhausted")

        # First run: circuit empty, dispatch proceeds
        d1 = evaluate_circuit_before_dispatch(c, task_ids=["T7"])
        assert d1.outcome == CircuitDispatchOutcome.PROCEED

        # After first failure: retry allowed
        f1 = evaluate_circuit_after_failure(c, err, task_id="T7", batch_id="B1")
        assert f1.outcome == CircuitFailureOutcome.ALLOW_RETRY

        # Second run: circuit still not open (1 occurrence), dispatch proceeds
        d2 = evaluate_circuit_before_dispatch(c, task_ids=["T7"])
        assert d2.outcome == CircuitDispatchOutcome.PROCEED

        # Second failure: circuit opens
        f2 = evaluate_circuit_after_failure(c, err, task_id="T7", batch_id="B1")
        assert f2.outcome == CircuitFailureOutcome.CIRCUIT_OPEN

        # Third run: circuit open, dispatch blocked
        d3 = evaluate_circuit_before_dispatch(c, task_ids=["T7"])
        assert d3.outcome == CircuitDispatchOutcome.CIRCUIT_OPEN
        assert not d3.may_dispatch

    def test_circuit_does_not_block_unrelated_tasks(self) -> None:
        """T7 circuit open should not block T12 dispatch."""
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitDispatchOutcome,
            evaluate_circuit_before_dispatch,
            evaluate_circuit_after_failure,
        )

        c = self._circuit()
        err = self._err(halt_kind="worker_budget_exhausted")

        evaluate_circuit_after_failure(c, err, task_id="T7")
        evaluate_circuit_after_failure(c, err, task_id="T7")  # T7 circuit open

        d = evaluate_circuit_before_dispatch(c, task_ids=["T12"])
        assert d.outcome == CircuitDispatchOutcome.PROCEED

    def test_equivalent_failures_preserve_exact_identity(self) -> None:
        """Two failures with same class, task, blocker share the same circuit."""
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitFailureOutcome,
            evaluate_circuit_after_failure,
        )

        c = self._circuit()
        err = self._err(halt_kind="worker_budget_exhausted")
        blocker = {"kind": "budget_exhausted", "task_id": "T7"}

        f1 = evaluate_circuit_after_failure(
            c, err, task_id="T7", batch_id="B3", blocker=blocker
        )
        assert f1.outcome == CircuitFailureOutcome.ALLOW_RETRY

        # Same identity, second occurrence opens circuit
        f2 = evaluate_circuit_after_failure(
            c, err, task_id="T7", batch_id="B3", blocker=blocker
        )
        assert f2.outcome == CircuitFailureOutcome.CIRCUIT_OPEN

    def test_different_blockers_no_collision(self) -> None:
        """Different blocker payloads, different digests, independent circuits."""
        from arnold_pipelines.megaplan.execute.policy import (
            CircuitFailureOutcome,
            evaluate_circuit_after_failure,
        )

        c = self._circuit()
        err = self._err(halt_kind="worker_budget_exhausted")

        f1 = evaluate_circuit_after_failure(
            c, err, task_id="T7", blocker={"kind": "reason_a"}
        )
        assert f1.outcome == CircuitFailureOutcome.ALLOW_RETRY

        f2 = evaluate_circuit_after_failure(
            c, err, task_id="T7", blocker={"kind": "reason_b"}
        )
        # Different blocker means different signature, so still first occurrence
        assert f2.outcome == CircuitFailureOutcome.ALLOW_RETRY
        assert f2.occurrence_count == 1
