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
from pathlib import Path
from typing import Any, Iterable, Mapping


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
        ``None`` or empty).  Keys are 1..10 integers.
    batch_complexity:
        The computed complexity ordinal for the batch (1..10).

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
    available = sorted(
        k
        for k, value in tier_map.items()
        if k <= batch_complexity and isinstance(value, str) and bool(value)
    )
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
        reason=(
            f"No tier spec for complexity {batch_complexity} "
            f"(available: {sorted(tier_map.items())})"
        ),
    )


# ---------------------------------------------------------------------------
# Blocker recovery policy — translate blocker evaluation into typed outcome
# ---------------------------------------------------------------------------


def evaluate_blocker_recovery_policy(
    finalize_data: dict[str, Any],
    state: dict[str, Any],
    *,
    plan_dir: Path | None = None,
    blocked_tasks: Iterable[Any] = (),
    deviations: Iterable[Any] = (),
    cross_session: bool = False,
) -> BlockedRetryDecision:
    """Evaluate blocked-task recovery through typed policy outcomes.

    Wraps :func:`~arnold_pipelines.megaplan.blocker_recovery.evaluate_blocker_recovery`
    and translates the raw ``BlockerRecoveryEvaluation`` into a
    :class:`BlockedRetryDecision` so callers never re-derive the
    decision from raw blocker lists.

    Parameters
    ----------
    finalize_data:
        The deserialized ``finalize.json`` payload.
    state:
        The plan state dict (``state.json`` / ``PlanState``).
    plan_dir:
        The plan directory path, used to discover phase-coverage
        deviations.  May be ``None`` when the caller is a pure test
        that does not need directory scans.
    blocked_tasks:
        ``BlockedTask`` instances (or compatible dicts) registered
        during the current phase.  Passed through to the prerequisite
        blocker evaluator.
    deviations:
        ``Deviation`` instances (or compatible dicts/strings) detected
        during the current phase.  Passed through to the quality
        blocker evaluator.
    cross_session:
        When ``True`` the evaluation is happening across invocation
        boundaries (fresh session).  The policy unconditionally returns
        ``RETRY_FRESH`` because the caller already determined a
        cross-session retry is appropriate.

    Returns
    -------
    BlockedRetryDecision
        A typed policy outcome that the handler / batch dispatcher uses
        to decide whether to retry, force a fresh session, or escalate.
    """
    from arnold_pipelines.megaplan.blocker_recovery import evaluate_blocker_recovery

    if cross_session:
        return BlockedRetryDecision(
            BlockedRetryOutcome.RETRY_FRESH,
            reason="Cross-session retry detected — forcing fresh worker session",
        )

    evaluation = evaluate_blocker_recovery(
        finalize_data,
        state,
        plan_dir=plan_dir,
        blocked_tasks=blocked_tasks,
        deviations=deviations,
    )

    if not evaluation.blockers:
        return BlockedRetryDecision(
            BlockedRetryOutcome.RETRY,
            reason="No blockers remain — safe to retry",
        )

    if evaluation.has_terminal_blockers:
        terminal_ids = [
            b.blocker_id for b in evaluation.blockers if b.is_terminal
        ]
        return BlockedRetryDecision(
            BlockedRetryOutcome.NO_RETRY,
            reason=(
                "Terminal blockers prevent retry: "
                + ", ".join(terminal_ids)
            ),
        )

    if evaluation.requires_rerun:
        return BlockedRetryDecision(
            BlockedRetryOutcome.RETRY_FRESH,
            reason="Blockers require fresh rerun (quality or prerequisite)",
        )

    if evaluation.can_continue:
        return BlockedRetryDecision(
            BlockedRetryOutcome.RETRY,
            reason="Non-terminal blockers — safe to retry within session",
        )

    return BlockedRetryDecision(
        BlockedRetryOutcome.NO_RETRY,
        reason="Blockers prevent retry",
    )


# ---------------------------------------------------------------------------#
# Partial-failure resume — only failed task IDs rerun while succeeded
# artifacts, debt records, checkpoint artifacts, and partial-failure/resume
# receipts remain intact.
# ---------------------------------------------------------------------------#
#
# ``resolve_partial_failure_resume`` is the *explicit*, source-visible decision
# that answers "which tasks must rerun and what is preserved?" after a partial
# batch failure.  The handler/batch dispatcher reads the typed
# :class:`PartialFailureResumeDecision` and performs the reset, but the
# *partition* of task IDs (rerun vs preserved) is owned by this pure helper so
# it cannot drift handler-local.


class ResumeOutcome(str, Enum):
    """Typed outcomes for partial-failure resume evaluation.

    * ``RESUME``     — at least one task failed and will be rerun; some
                        tasks may be preserved.
    * ``NOT_NEEDED`` — no failed tasks; nothing to resume.
    """

    RESUME = "resume"
    NOT_NEEDED = "not_needed"


# Statuses whose durable outputs (files_changed, commands_run, evidence) are
# preserved on resume.  These tasks are *not* rerun.
_RESUME_PRESERVED_STATUSES: frozenset[str] = frozenset({"done", "skipped"})

# The failure status that marks a task for rerun on resume.
_RESUME_RERUN_STATUS: str = "blocked"


@dataclass(frozen=True)
class PartialFailureResumeDecision:
    """Pure decision for partial-failure resume.

    *outcome* tells the caller whether any rerun is required.
    *rerun_task_ids* is the canonical (sorted) set of failed task IDs that the
    dispatcher must flip back to ``pending`` and re-execute.
    *preserved_task_ids* is the canonical set of succeeded task IDs whose
    artifacts, debt records, checkpoint artifacts, and receipt evidence must
    remain intact.
    *preserved_artifact_refs* names the durable checkpoint/batch artifacts that
    must not be overwritten or deleted by the resume write.
    *debt_registry_preserved* is always ``True`` — the execute resume never
    mutates the debt registry, which lives outside ``finalize.json``.
    *preserved_receipt_ids* names the partial-failure/resume boundary receipts
    that must survive the rerun so the evidence trail stays complete.
    """

    outcome: ResumeOutcome
    rerun_task_ids: tuple[str, ...] = ()
    preserved_task_ids: tuple[str, ...] = ()
    preserved_artifact_refs: tuple[str, ...] = ()
    debt_registry_preserved: bool = True
    preserved_receipt_ids: tuple[str, ...] = ()

    @property
    def should_resume(self) -> bool:
        """True when at least one failed task must be rerun."""
        return self.outcome is ResumeOutcome.RESUME and bool(self.rerun_task_ids)


def resolve_partial_failure_resume(
    tasks: Iterable[Mapping[str, Any]],
    *,
    completed_task_ids: Iterable[str] | None = None,
    preserved_artifact_refs: Iterable[str] | None = None,
    preserved_receipt_ids: Iterable[str] | None = None,
) -> PartialFailureResumeDecision:
    """Partition tasks into rerun (failed) vs preserved (succeeded) sets.

    This is the *explicit* partial-failure resume partitioner.  Only tasks at
    status ``"blocked"`` (the canonical failure status) are selected for rerun;
    tasks at ``"done"`` / ``"skipped"`` are preserved with all of their
    artifacts.  The dispatcher is responsible for flipping the rerun set back
    to ``"pending"``; this helper never mutates inputs.

    Parameters
    ----------
    tasks:
        The finalized task records (mappings with ``id`` and ``status``).
    completed_task_ids:
        Optional authoritative completed-ID set.  When supplied, any task whose
        ID is in this set is treated as preserved even if its persisted status
        is stale, because the scheduler's authority reader is the source of
        truth for completion.
    preserved_artifact_refs:
        Artifact references (batch/checkpoint paths) that must survive the
        resume.  Echoed back verbatim so the dispatcher and receipt layer can
        assert they are intact.
    preserved_receipt_ids:
        Boundary receipt IDs (e.g. ``execute_partial_failure``,
        ``execute_resume_anchor``) that must survive the rerun.

    Returns
    -------
    PartialFailureResumeDecision
    """
    completed = (
        {str(tid) for tid in completed_task_ids}
        if completed_task_ids is not None
        else set()
    )
    rerun_ids: list[str] = []
    preserved_ids: list[str] = []
    for task in tasks:
        if not isinstance(task, Mapping):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str):
            continue
        status = task.get("status")
        # Authority-completed tasks are always preserved regardless of their
        # persisted status field.
        if task_id in completed:
            preserved_ids.append(task_id)
            continue
        if status == _RESUME_RERUN_STATUS:
            rerun_ids.append(task_id)
        elif status in _RESUME_PRESERVED_STATUSES:
            preserved_ids.append(task_id)
        # Any other status (e.g. "pending", "completed", missing) is neither
        # rerun nor explicitly preserved by *this* resume decision — those are
        # handled by the normal scheduler/batching path.
    rerun_sorted = tuple(sorted(set(rerun_ids)))
    preserved_sorted = tuple(sorted(set(preserved_ids)))
    artifacts_sorted = tuple(
        sorted({str(ref) for ref in preserved_artifact_refs or ()})
    )
    receipts_sorted = tuple(
        sorted({str(rid) for rid in preserved_receipt_ids or ()})
    )
    if rerun_sorted:
        outcome = ResumeOutcome.RESUME
    else:
        outcome = ResumeOutcome.NOT_NEEDED
    return PartialFailureResumeDecision(
        outcome=outcome,
        rerun_task_ids=rerun_sorted,
        preserved_task_ids=preserved_sorted,
        preserved_artifact_refs=artifacts_sorted,
        debt_registry_preserved=True,
        preserved_receipt_ids=receipts_sorted,
    )


# ===========================================================================
# Execute branch surface — explicit, source-visible execute routing topology
# ===========================================================================
#
# ``EXECUTE_BRANCH_SURFACE`` is the named policy construct that makes every
# execute-phase branch point visible *without* inspecting the handler.  It is
# a *declaration* of the routing topology: each entry names the route signal
# that selects the branch, the next step or terminal state it targets, the
# pure helper (or policy authority) that resolves the decision, and the typed
# outcome enum member that carries it.
#
# This surface deliberately does NOT implement true parallel execution.  The
# reserved ``CANCEL`` / ``AWAIT`` / ``ORPHAN`` markers
# (:class:`FutureParallelMarker`) are explicit anchors for future concurrency
# work so that linters can detect ad-hoc parallel branches that bypass the
# policy surface.
#
# The workflow policy component references this surface through
# ``EXECUTE_POLICY.metadata["route_surface"]["branch_surface_ref"]`` so a
# reviewer following workflow source -> policy component -> policy authority
# can read the *full* execute routing topology end to end.


@dataclass(frozen=True)
class ExecuteBranchPoint:
    """One explicit, source-visible execute branch point.

    Attributes
    ----------
    branch_id:
        Stable identifier for the branch (``"execute:<category>-<detail>"``).
    category:
        Routing category — one of :data:`EXECUTE_BRANCH_CATEGORIES`, or
        ``"reserved_parallel"`` for the future-parallel anchors.
    route_signal:
        The signal value that selects this branch.
    target_ref:
        The next step id (e.g. ``"execute-batches"``, ``"override"``,
        ``"review-fan-in"``) or terminal target (``"halt"``, ``"done"``,
        ``"awaiting_human_verify"``).
    outcome_ref:
        Dotted qualname of the typed outcome enum member that carries the
        decision, or the structural signal/reducer when no enum applies.
    resolved_by:
        Dotted qualname of the pure helper that resolves the branch, or the
        policy authority (config / reducer) that governs it.
    description:
        Human-readable explanation of when the branch is taken.
    reserved_parallel:
        ``True`` only for the reserved CANCEL / AWAIT / ORPHAN anchors.
    """

    branch_id: str
    category: str
    route_signal: str
    target_ref: str
    outcome_ref: str
    resolved_by: str
    description: str
    reserved_parallel: bool = False


#: The seven execute branch categories that MUST be represented in the
#: execute routing topology.  ``reserved_parallel`` is additional, not part
#: of this required set.
EXECUTE_BRANCH_CATEGORIES: frozenset[str] = frozenset(
    {
        "approval",
        "batch_continuation",
        "blocked_recovery",
        "timeout_retry",
        "aggregate_promotion",
        "review_handoff",
        "no_review_terminal",
    }
)

_POLICY_MODULE = __name__


def _outcome_qual(member: Enum) -> str:
    """Build the dotted qualname for an execute-policy enum member."""
    return f"{_POLICY_MODULE}:{type(member).__name__}.{member.name}"


EXECUTE_BRANCH_SURFACE: tuple[ExecuteBranchPoint, ...] = (
    # --------------------------------------------------------- 1. approval gate
    ExecuteBranchPoint(
        branch_id="execute:approval-approved",
        category="approval",
        route_signal=ApprovalOutcome.APPROVED.value,
        target_ref="execute-batches",
        outcome_ref=_outcome_qual(ApprovalOutcome.APPROVED),
        resolved_by=f"{_POLICY_MODULE}:evaluate_destructive_approval",
        description=(
            "Both the destructive-confirmation and operator-approval gates "
            "are cleared — proceed into batch execution."
        ),
    ),
    ExecuteBranchPoint(
        branch_id="execute:approval-denied-missing-confirm",
        category="approval",
        route_signal=ApprovalOutcome.DENIED_MISSING_CONFIRM.value,
        target_ref="halt",
        outcome_ref=_outcome_qual(ApprovalOutcome.DENIED_MISSING_CONFIRM),
        resolved_by=f"{_POLICY_MODULE}:evaluate_destructive_approval",
        description=(
            "Destructive confirmation missing (and not prose mode) — halt "
            "with a missing_confirmation error before any batch runs."
        ),
    ),
    ExecuteBranchPoint(
        branch_id="execute:approval-denied-missing-approval",
        category="approval",
        route_signal=ApprovalOutcome.DENIED_MISSING_APPROVAL.value,
        target_ref="halt",
        outcome_ref=_outcome_qual(ApprovalOutcome.DENIED_MISSING_APPROVAL),
        resolved_by=f"{_POLICY_MODULE}:evaluate_destructive_approval",
        description=(
            "Operator approval missing and auto-approve not set — halt at "
            "the gate checkpoint with a missing_approval error."
        ),
    ),
    # ----------------------------------------------- 2. batch continuation (next)
    ExecuteBranchPoint(
        branch_id="execute:batch-continuation",
        category="batch_continuation",
        route_signal=NextExecuteTransition.EXECUTE.value,
        target_ref="execute-batches",
        outcome_ref=_outcome_qual(NextExecuteTransition.EXECUTE),
        resolved_by=f"{_POLICY_MODULE}:resolve_single_batch_next_step",
        description=(
            "The current batch completed successfully but additional batches "
            "remain — re-enter the execute loop for the next batch."
        ),
    ),
    # --------------------------------------------- 3. blocked recovery (quality)
    ExecuteBranchPoint(
        branch_id="execute:blocked-recovery",
        category="blocked_recovery",
        route_signal=NextExecuteTransition.BLOCKED.value,
        target_ref="override",
        outcome_ref=_outcome_qual(NextExecuteTransition.BLOCKED),
        resolved_by=f"{_POLICY_MODULE}:resolve_single_batch_next_step",
        description=(
            "A batch was blocked by quality gates — route to override for "
            "recovery and set the plan state to 'blocked'."
        ),
    ),
    # ------------------------------------------- 4. timeout retry (retry budget)
    ExecuteBranchPoint(
        branch_id="execute:timeout-retry",
        category="timeout_retry",
        route_signal=BlockedRetryOutcome.RETRY.value,
        target_ref="execute-batches",
        outcome_ref=_outcome_qual(BlockedRetryOutcome.RETRY),
        resolved_by="EXECUTE_POLICY.config.retry",
        description=(
            "A worker/transient timeout occurred within the retry budget "
            "(max_attempts=2, retry_on={timeout, worker_transient}) — retry "
            "the batch; escalate to override once the budget is exhausted."
        ),
    ),
    ExecuteBranchPoint(
        branch_id="execute:timeout-retry-fresh",
        category="timeout_retry",
        route_signal=BlockedRetryOutcome.RETRY_FRESH.value,
        target_ref="execute-batches",
        outcome_ref=_outcome_qual(BlockedRetryOutcome.RETRY_FRESH),
        resolved_by="EXECUTE_POLICY.config.retry",
        description=(
            "Retry requires a fresh worker session (review-rework or blocked "
            "retry detected) — force a new execute session."
        ),
    ),
    # -------------------------------------- 5. aggregate promotion (reducer fan-in)
    ExecuteBranchPoint(
        branch_id="execute:aggregate-promotion",
        category="aggregate_promotion",
        route_signal="execute_payload",
        target_ref="review-fan-in",
        outcome_ref="execute_payload",
        resolved_by="AUTHORING_EXECUTE reducer",
        description=(
            "The execute reducer (AUTHORING_EXECUTE) aggregates every batch "
            "payload into a single execute_payload, which is promoted to the "
            "review fan-in as its items source."
        ),
    ),
    # ----------------------------------------- 6. review handoff (final + tracked)
    ExecuteBranchPoint(
        branch_id="execute:review-handoff",
        category="review_handoff",
        route_signal=NextExecuteTransition.REVIEW.value,
        target_ref="review-fan-in",
        outcome_ref=_outcome_qual(NextExecuteTransition.REVIEW),
        resolved_by=f"{_POLICY_MODULE}:resolve_single_batch_next_step",
        description=(
            "The final batch completed and every task / sense-check is "
            "tracked — hand the aggregated payload to the review fan-in."
        ),
    ),
    # ------------------------------------- 7. no-review terminal (skip review)
    ExecuteBranchPoint(
        branch_id="execute:no-review-terminal-done",
        category="no_review_terminal",
        route_signal=NoReviewTerminalOutcome.TERMINATE_DONE.value,
        target_ref="done",
        outcome_ref=_outcome_qual(NoReviewTerminalOutcome.TERMINATE_DONE),
        resolved_by=f"{_POLICY_MODULE}:evaluate_no_review_terminal",
        description=(
            "Robustness skips review (bare, or light without deferred must "
            "criteria) — terminate directly in the 'done' state."
        ),
    ),
    ExecuteBranchPoint(
        branch_id="execute:no-review-terminal-awaiting-human",
        category="no_review_terminal",
        route_signal=NoReviewTerminalOutcome.TERMINATE_AWAITING_HUMAN.value,
        target_ref="awaiting_human_verify",
        outcome_ref=_outcome_qual(NoReviewTerminalOutcome.TERMINATE_AWAITING_HUMAN),
        resolved_by=f"{_POLICY_MODULE}:evaluate_no_review_terminal",
        description=(
            "Deferred must-have criteria require human verification that "
            "cannot be automated — terminate in 'awaiting_human_verify'."
        ),
    ),
    # ------------------------------- reserved future-parallel anchors (S4 N/A)
    ExecuteBranchPoint(
        branch_id="execute:reserved-cancel",
        category="reserved_parallel",
        route_signal=FutureParallelMarker.CANCEL.value,
        target_ref="",
        outcome_ref=_outcome_qual(FutureParallelMarker.CANCEL),
        resolved_by="",
        description=(
            "RESERVED (not implemented in S4): cancel parallel children when "
            "a sibling batch fails. Explicit anchor only."
        ),
        reserved_parallel=True,
    ),
    ExecuteBranchPoint(
        branch_id="execute:reserved-await",
        category="reserved_parallel",
        route_signal=FutureParallelMarker.AWAIT.value,
        target_ref="",
        outcome_ref=_outcome_qual(FutureParallelMarker.AWAIT),
        resolved_by="",
        description=(
            "RESERVED (not implemented in S4): await completion of all "
            "parallel children before aggregating. Explicit anchor only."
        ),
        reserved_parallel=True,
    ),
    ExecuteBranchPoint(
        branch_id="execute:reserved-orphan",
        category="reserved_parallel",
        route_signal=FutureParallelMarker.ORPHAN.value,
        target_ref="",
        outcome_ref=_outcome_qual(FutureParallelMarker.ORPHAN),
        resolved_by="",
        description=(
            "RESERVED (not implemented in S4): orphan a parallel child "
            "(fire-and-forget; results never collected). Explicit anchor only."
        ),
        reserved_parallel=True,
    ),
)


def execute_branch_categories_present() -> frozenset[str]:
    """Return the set of categories that have at least one declared branch.

    Lets linters / tests assert that every required execute branch category
    (see :data:`EXECUTE_BRANCH_CATEGORIES`) is represented in
    :data:`EXECUTE_BRANCH_SURFACE`.
    """
    return frozenset(branch.category for branch in EXECUTE_BRANCH_SURFACE)


def execute_branches_for_category(category: str) -> tuple[ExecuteBranchPoint, ...]:
    """Return every declared execute branch point for *category*.

    Parameters
    ----------
    category:
        One of the values in :data:`EXECUTE_BRANCH_CATEGORIES`, or
        ``"reserved_parallel"``.

    Returns
    -------
    tuple[ExecuteBranchPoint, ...]
    """
    return tuple(
        branch for branch in EXECUTE_BRANCH_SURFACE if branch.category == category
    )


def execute_branch_ids() -> tuple[str, ...]:
    """Return the stable ``branch_id`` for every declared branch, in order."""
    return tuple(branch.branch_id for branch in EXECUTE_BRANCH_SURFACE)


# Invariant self-check: the surface must cover every required category.  This
# runs at import time and fails loudly if a future edit drops a branch.
assert EXECUTE_BRANCH_CATEGORIES <= execute_branch_categories_present(), (
    "EXECUTE_BRANCH_SURFACE is missing required execute branch categories: "
    + ", ".join(
        sorted(EXECUTE_BRANCH_CATEGORIES - execute_branch_categories_present())
    )
)
