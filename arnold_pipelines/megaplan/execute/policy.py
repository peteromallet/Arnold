"""Typed execute policy constructs and pure helpers.

This module is the single source of truth for execute-phase route decisions.
Every outcome is a frozen, typed value — handlers translate these values into
CLI errors, state mutations, or response payloads, but they never *own* the
decision logic.  No handler or batch runtime state is imported here.

S4 constructs
-------------
* :class:`ExecuteEntryRoute` / :func:`resolve_execute_entry_route`
* :class:`ApprovalOutcome` / :func:`evaluate_destructive_approval`
* :class:`NoReviewTerminalOutcome` / :func:`evaluate_no_review_terminal`
* :class:`TierRouteOutcome` / :func:`resolve_batch_tier`
* :class:`BlockedRetryOutcome` — typed outcome for blocked-task retry
* :class:`NextExecuteTransition` / :func:`resolve_single_batch_next_step`
* :class:`FutureParallelMarker` — reserved CANCEL / AWAIT / ORPHAN anchors
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


# ---------------------------------------------------------------------------
# Execute entry route — typed dispatch decision
# ---------------------------------------------------------------------------

class ExecuteEntryRoute(str, Enum):
    """Typed outcomes for the execute entry dispatch decision.

    The handler translates each value into the appropriate action:
    * ``PROCEED`` — continue past the gate into batch execution.
    * ``BLOCKED`` — plan is blocked; may still be recoverable.
    * ``FAILED``  — plan has failed; terminal.
    * ``INVALID`` — state is not recognised as an execute entry point.
    """

    PROCEED = "proceed"
    BLOCKED = "blocked"
    FAILED = "failed"
    INVALID = "invalid"


@dataclass(frozen=True)
class ExecuteEntryDecision:
    """Pure decision for execute entry routing.

    Carries the resolved route and a human-readable reason so that
    callers can emit consistent diagnostics without re-deriving the
    decision.
    """

    route: ExecuteEntryRoute
    reason: str = ""

    @property
    def may_proceed(self) -> bool:
        """True when the decision allows execution to continue."""
        return self.route == ExecuteEntryRoute.PROCEED


# ---------------------------------------------------------------------------
# Approval outcome — destructive / user-approval gate
# ---------------------------------------------------------------------------

class ApprovalOutcome(str, Enum):
    """Typed outcomes of the destructive/approval gate evaluation."""

    APPROVED = "approved"
    DENIED_MISSING_CONFIRM = "denied_missing_confirm"
    DENIED_MISSING_APPROVAL = "denied_missing_approval"


@dataclass(frozen=True)
class ApprovalDecision:
    """Pure decision for the destructive/user-approval gate.

    *outcome* is ``APPROVED`` when both the destructive-confirmation and
    user-approval hurdles are cleared.  The other two values carry the
    specific denial reason so the handler can raise the correct
    :class:`CliError`.
    """

    outcome: ApprovalOutcome
    reason: str = ""

    @property
    def is_approved(self) -> bool:
        """True when execution may proceed past the approval gate."""
        return self.outcome == ApprovalOutcome.APPROVED


# ---------------------------------------------------------------------------
# No-review terminal outcome — bare / light robustness skip
# ---------------------------------------------------------------------------

class NoReviewTerminalOutcome(str, Enum):
    """Typed outcomes for the no-review terminal evaluation.

    Used when the robustness level is ``bare`` or ``light`` and the
    workflow does not include a review step.
    """

    TERMINATE_DONE = "terminate_done"
    TERMINATE_AWAITING_HUMAN = "terminate_awaiting_human"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class NoReviewTerminalDecision:
    """Pure decision for no-review terminal routing.

    *target_state* is the canonical state name (e.g. ``"done"``,
    ``"awaiting_human_verify"``) that the handler should transition to.
    It is ``None`` when *outcome* is ``NOT_APPLICABLE``.
    """

    outcome: NoReviewTerminalOutcome
    target_state: str | None = None
    reason: str = ""

    @property
    def should_terminate(self) -> bool:
        """True when the handler should skip review and terminate."""
        return self.outcome in (
            NoReviewTerminalOutcome.TERMINATE_DONE,
            NoReviewTerminalOutcome.TERMINATE_AWAITING_HUMAN,
        )


# ---------------------------------------------------------------------------
# Tier route — batch complexity → model spec
# ---------------------------------------------------------------------------

class TierRouteOutcome(str, Enum):
    """Typed outcomes for batch tier routing."""

    ROUTED = "routed"
    DEFAULT = "default"
    NO_TIER_MAP = "no_tier_map"


@dataclass(frozen=True)
class TierRouteDecision:
    """Pure decision for batch tier routing.

    *spec* is the selected tier spec string (e.g. ``"opus"``, ``"sonnet"``)
    when *outcome* is ``ROUTED``; ``None`` otherwise.
    """

    outcome: TierRouteOutcome
    spec: str | None = None
    selected_tier: int | None = None
    reason: str = ""

    @property
    def has_spec(self) -> bool:
        """True when a usable tier spec was resolved."""
        return self.outcome == TierRouteOutcome.ROUTED and isinstance(self.spec, str) and bool(self.spec)


# ---------------------------------------------------------------------------
# Blocked / retry outcome
# ---------------------------------------------------------------------------

class BlockedRetryOutcome(str, Enum):
    """Typed outcomes for blocked-task retry evaluation.

    * ``RETRY_FRESH`` — start a clean attempt (force new worker session).
    * ``NO_RETRY``   — do not retry; escalate or halt.
    * ``RETRY``      — simple retry within the same session.
    """

    RETRY_FRESH = "retry_fresh"
    NO_RETRY = "no_retry"
    RETRY = "retry"


@dataclass(frozen=True)
class BlockedRetryDecision:
    """Pure decision for blocked-task retry evaluation.

    The handler uses *outcome* to decide whether to re-enter the execute
    loop, force a fresh session, or escalate.
    """

    outcome: BlockedRetryOutcome
    reason: str = ""

    @property
    def should_retry(self) -> bool:
        """True when the handler should attempt a retry."""
        return self.outcome in (BlockedRetryOutcome.RETRY, BlockedRetryOutcome.RETRY_FRESH)


# ---------------------------------------------------------------------------
# Next execute transition — what comes after the current batch
# ---------------------------------------------------------------------------

class NextExecuteTransition(str, Enum):
    """Typed transitions for what step follows the current execute batch.

    The handler maps each value to a ``next_step`` response field and
    optionally a ``guidance`` hint.
    """

    EXECUTE = "execute"
    REVIEW = "review"
    BLOCKED = "blocked"
    DONE = "done"
    AWAITING_HUMAN = "awaiting_human"


@dataclass(frozen=True)
class NextStepDecision:
    """Pure decision for the next execute transition.

    *is_final_batch* and *all_tracked* are informational fields that the
    handler may use for summary text; the decision itself is carried by
    *transition*.
    """

    transition: NextExecuteTransition
    is_final_batch: bool = False
    all_tracked: bool = False
    reason: str = ""


# ---------------------------------------------------------------------------
# Reserved future parallel transition markers
# ---------------------------------------------------------------------------

class FutureParallelMarker(str, Enum):
    """Reserved markers for future parallel execute branches.

    These are **not** implemented in S4 — they exist as explicit,
    source-visible policy anchors so that future concurrency work has
    stable branch points and linters can detect when a handler introduces
    an ad-hoc parallel branch without going through the policy surface.

    * ``CANCEL`` — cancel parallel children when a sibling fails.
    * ``AWAIT``  — await completion of all parallel children before
      aggregating.
    * ``ORPHAN`` — orphan a parallel child (fire-and-forget; results
      are never collected).
    """

    CANCEL = "CANCEL"
    AWAIT = "AWAIT"
    ORPHAN = "ORPHAN"


# ===========================================================================
# Pure helper functions
# ===========================================================================


def resolve_execute_entry_route(
    current_state: str,
    *,
    allowed_entry_states: frozenset[str] | None = None,
) -> ExecuteEntryDecision:
    """Determine the execute entry route from the plan's current state.

    Parameters
    ----------
    current_state:
        The ``state["current_state"]`` value.
    allowed_entry_states:
        The set of states that the caller considers valid entry points.
        Defaults to ``{"finalized", "blocked", "failed"}``, matching the
        historical ``require_state`` whitelist in the execute handler.

    Returns
    -------
    ExecuteEntryDecision
        A typed decision whose ``.may_proceed`` is ``True`` only when
        *current_state* is a recognised allowed entry state and the
        caller should continue into batch execution.
    """
    if allowed_entry_states is None:
        allowed_entry_states = frozenset({"finalized", "blocked", "failed"})

    if current_state not in allowed_entry_states:
        return ExecuteEntryDecision(
            ExecuteEntryRoute.INVALID,
            f"State '{current_state}' is not a valid execute entry point; "
            f"allowed: {sorted(allowed_entry_states)}",
        )

    if current_state == "blocked":
        return ExecuteEntryDecision(
            ExecuteEntryRoute.BLOCKED,
            "Plan is blocked — execution may proceed for recovery/retry",
        )
    if current_state == "failed":
        return ExecuteEntryDecision(
            ExecuteEntryRoute.FAILED,
            "Plan has failed — execution may proceed for diagnostics",
        )
    # current_state == "finalized" (or any other allowed state)
    return ExecuteEntryDecision(
        ExecuteEntryRoute.PROCEED,
        f"Plan state '{current_state}' allows execution to proceed",
    )


def evaluate_destructive_approval(
    *,
    confirm_destructive: bool,
    auto_approve: bool,
    user_approved_gate: bool,
    is_prose_mode: bool,
) -> ApprovalDecision:
    """Evaluate the destructive-confirmation and user-approval gates.

    This is a pure translation of the two inline checks at the top of
    ``handle_execute``.  The handler is responsible for raising the
    appropriate ``CliError`` when the decision is not approved.

    Parameters
    ----------
    confirm_destructive:
        ``args.confirm_destructive`` (or the equivalent flag).
    auto_approve:
        ``state["config"].get("auto_approve", False)``.
    user_approved_gate:
        ``state["meta"].get("user_approved_gate", False)``.
    is_prose_mode:
        ``is_prose_mode(state)`` — prose mode skips the destructive
        confirmation check.

    Returns
    -------
    ApprovalDecision
    """
    if not is_prose_mode and not confirm_destructive:
        return ApprovalDecision(
            ApprovalOutcome.DENIED_MISSING_CONFIRM,
            "Execute requires --confirm-destructive",
        )

    if not auto_approve and not user_approved_gate:
        return ApprovalDecision(
            ApprovalOutcome.DENIED_MISSING_APPROVAL,
            "Execute requires explicit user approval (--user-approved) when "
            "auto-approve is not set. The orchestrator must confirm with the "
            "user at the gate checkpoint before proceeding.",
        )

    return ApprovalDecision(
        ApprovalOutcome.APPROVED,
        "Approval gate passed",
    )


def evaluate_no_review_terminal(
    *,
    robustness: str,
    has_deferred_must: bool = False,
) -> NoReviewTerminalDecision:
    """Evaluate whether the no-review terminal route applies.

    Called after execute completes when the robustness level may skip
    the review step.  This is a pure function over the robustness string
    and the deferred-must flag — it does not inspect review artifacts.

    Parameters
    ----------
    robustness:
        One of ``"bare"``, ``"light"``, ``"standard"``, ``"thorough"``.
    has_deferred_must:
        ``True`` when at least one success criterion with priority
        ``"must"`` requires human verification that cannot be automated.

    Returns
    -------
    NoReviewTerminalDecision
    """
    if robustness == "bare":
        return NoReviewTerminalDecision(
            NoReviewTerminalOutcome.TERMINATE_DONE,
            target_state="done",
            reason="Bare robustness skips review entirely",
        )

    if robustness in ("light", "standard") and has_deferred_must:
        return NoReviewTerminalDecision(
            NoReviewTerminalOutcome.TERMINATE_AWAITING_HUMAN,
            target_state="awaiting_human_verify",
            reason="Deferred must-have criteria require human verification",
        )

    if robustness in ("light",):
        return NoReviewTerminalDecision(
            NoReviewTerminalOutcome.TERMINATE_DONE,
            target_state="done",
            reason="Light robustness auto-approves without deferred must criteria",
        )

    # standard, thorough, or any unrecognised robustness level includes review
    return NoReviewTerminalDecision(
        NoReviewTerminalOutcome.NOT_APPLICABLE,
        reason=f"Robustness '{robustness}' includes a review step",
    )


def resolve_single_batch_next_step(
    *,
    is_final_batch: bool,
    all_tracked: bool,
    blocked: bool,
) -> NextStepDecision:
    """Resolve the next-step transition after a single batch executes.

    This is the pure policy mirror of the three-way branch in
    ``handle_execute_one_batch`` that assigns ``next_step``.

    Parameters
    ----------
    is_final_batch:
        ``True`` when the current batch is the last batch.
    all_tracked:
        ``True`` when every task/sense-check in the plan has been
        acknowledged (no remaining tracking work).
    blocked:
        ``True`` when the batch was blocked by quality gates.

    Returns
    -------
    NextStepDecision
    """
    if blocked:
        return NextStepDecision(
            NextExecuteTransition.BLOCKED,
            is_final_batch=is_final_batch,
            all_tracked=all_tracked,
            reason="Batch blocked by quality gates",
        )

    if is_final_batch and all_tracked:
        return NextStepDecision(
            NextExecuteTransition.REVIEW,
            is_final_batch=True,
            all_tracked=True,
            reason="All batches complete and fully tracked — ready for review",
        )

    return NextStepDecision(
        NextExecuteTransition.EXECUTE,
        is_final_batch=is_final_batch,
        all_tracked=all_tracked,
        reason="More batches remain",
    )


def resolve_batch_tier(
    *,
    tier_map: Mapping[int, str] | None,
    batch_complexity: int,
) -> TierRouteDecision:
    """Resolve the tier spec for a batch from its complexity score.

    Parameters
    ----------
    tier_map:
        Normalized ``{tier_ordinal: spec_string}`` mapping (may be
        ``None`` or empty).  Keys are 1..5 integers.
    batch_complexity:
        The computed complexity ordinal for the batch (1..5).

    Returns
    -------
    TierRouteDecision
    """
    if tier_map is None or not tier_map:
        return TierRouteDecision(
            TierRouteOutcome.NO_TIER_MAP,
            reason="No tier map configured",
        )

    # Exact match
    spec = tier_map.get(batch_complexity)
    if isinstance(spec, str) and spec:
        return TierRouteDecision(
            TierRouteOutcome.ROUTED,
            spec=spec,
            selected_tier=batch_complexity,
            reason=f"Tier {batch_complexity} matched spec '{spec}'",
        )

    # Fallback: highest tier <= batch_complexity
    available = sorted(k for k in tier_map if k <= batch_complexity)
    if available:
        fallback_tier = available[-1]
        fallback_spec = tier_map[fallback_tier]
        return TierRouteDecision(
            TierRouteOutcome.ROUTED,
            spec=fallback_spec,
            selected_tier=fallback_tier,
            reason=(
                f"Tier {batch_complexity} had no exact match; "
                f"fell back to tier {fallback_tier} -> '{fallback_spec}'"
            ),
        )

    return TierRouteDecision(
        TierRouteOutcome.DEFAULT,
        reason=f"No tier spec for complexity {batch_complexity} (available: {sorted(tier_map)})",
    )
