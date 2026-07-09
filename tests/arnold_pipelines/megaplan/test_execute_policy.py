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
