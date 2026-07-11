"""Pure ordered classifiers for the canonical run-state resolver.

Each classifier is a small, independent, read-only function that inspects a
:class:`ResolverContext` (built once from normalized evidence) and returns
either a fully-populated :class:`CanonicalRunState` or ``None`` when it does
not apply.

The classifiers are applied in a fixed order that encodes the North Star
evidence priority:

1. **Live/active evidence beats stale labels.**  A live worker (tmux alive or
   an active-step heartbeat) overrides stale ``failed`` / ``manual_review`` /
   ``needs_human`` / ``no_next_step`` labels projected by legacy layers.
2. **Explicit typed human gates become** :attr:`CanonicalState.HUMAN_ACTION_REQUIRED`
   — but only when the worker is *not* live and the evidence is not a
   machine-actionable implementation block.
3. **Authority completion beats stale** ``failed`` / ``no_next_step``
   **labels.**  A terminal plan ``done`` (or real work complete with only a
   deferred baseline remaining) wins over a stale non-success chain label.
4. **Repair-data, watchdog markers, and retry fingerprints remain advisory.**
5. **Fallbacks stay conservative** (:attr:`CanonicalState.UNKNOWN`).

Per SD3, machine-actionable implementation blockers (route-binding gaps,
fixture refreshes, stale assertions, budget exhaustion) are *never* human
gates.

This module MUST NOT import from watchdog, status, repair-loop,
feature_flags, or any other consumer or env-dependent module — it is part of
the pure resolver contract.  Consumer gating (``resolver_observe_enabled`` /
``resolver_enforcement_enabled``) lives in the consumers, not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan.run_state.evidence import (
    NormalizedEvidence,
    normalize_evidence,
)
from arnold_pipelines.megaplan.run_state.model import (
    CanonicalRunState,
    CanonicalState,
    TypedHumanGate,
)
from arnold_pipelines.megaplan.run_state.decision_contract import typed_human_gate


# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

# Terminal plan/chain states that represent authoritative SUCCESS.
_SUCCESS_TERMINAL_STATES = frozenset({"done"})

# Stale derived labels projected by legacy layers.  These are *labels*, not
# decisions — a live worker or authority completion overrides them.
_STALE_DERIVED_LABELS = frozenset(
    {
        "manual_review",
        "blocked",
        "failed",
        "no_next_step",
        "execution_blocked",
        "needs_human",
    }
)

# Chain/plan labels that specifically indicate the authority layer reached a
# non-success terminal projection while the real work actually completed.
_STALE_FAILED_CHAIN_LABELS = frozenset({"failed", "no_next_step"})

# Diagnostic-code / retry-strategy tokens that indicate a machine-actionable
# *implementation* block rather than a human gate.  Matching these structured
# tokens is evidence-based consumption of diagnostic codes (enum-like labels),
# NOT free-text keyword scanning of prose summaries.
_IMPLEMENTATION_BLOCK_TOKENS = (
    "awf018",
    "route_metadata_mismatch",
    "route_metadata",
    "route_binding",
    "missing_route",
    "missing_fallthrough_route",
    "stale_assertion",
    "fixture_refresh",
    "quality_gate_blocked",
    "deterministic_quality_blocked",
    "blocked_recovery_not_resolved",
)

# Tokens that indicate a retryable *execution* block (transient / budget).
_RETRYABLE_EXECUTION_TOKENS = (
    "execution_blocked",
    "budget_exhausted",
    "budget",
    "requeue",
    "retryable",
)

# Minimum number of repeated identical blocker fingerprints (without progress)
# that escalates a run to ``BROKEN_STATE_MACHINE``.
_BROKEN_REPEAT_THRESHOLD = 3

# Structured numeric fields that may report repeated blocker attempts.
_BROKEN_COUNT_FIELDS = (
    "attempt_count",
    "repeated_attempts",
    "identical_fingerprint_count",
    "blocker_repeat_count",
    "repeat_count",
    "repeated_blocker_count",
)

# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def _coerce_verdict(blocker_verdict: object) -> str:
    """Normalize an optional BlockerVerdict (enum member or name string)."""
    if blocker_verdict is None:
        return ""
    name = getattr(blocker_verdict, "name", None)
    if isinstance(name, str):
        return name
    if isinstance(blocker_verdict, str):
        return blocker_verdict.strip()
    return ""


def _safe_lower(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if isinstance(value, str):
        return value.strip().lower()
    return ""


def _has_token(text: str, tokens: Sequence[str]) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(tok in low for tok in tokens)


def _evi(kind: str, path: object = "", summary: object = "") -> dict[str, Any]:
    """Build a single evidence item dict."""
    return {
        "kind": str(kind),
        "path": str(path or ""),
        "summary": str(summary or ""),
    }


def _infer_typed_gate(needs_human: Mapping[str, Any]) -> "TypedHumanGate | None":
    """Infer a typed human gate from a *structured* gate-category field.

    Only structured fields (``gate_type`` / ``human_gate`` / ``gate`` /
    ``category`` / ``gate_kind`` / ``kind``) are consulted — never the
    free-text ``summary``, so this is not keyword scanning of prose.
    """
    return typed_human_gate(needs_human)


def _iter_containers(obj: object, _depth: int = 0):
    """Recursively yield every mapping within JSON-like evidence (depth-bounded).

    JSON evidence has no cycles, but we cap recursion to stay defensive.
    """
    if _depth > 6:
        return
    if isinstance(obj, Mapping):
        yield obj
        for value in obj.values():
            yield from _iter_containers(value, _depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_containers(item, _depth + 1)


def _detect_broken_repeat(evidence: Mapping[str, Any]) -> int:
    """Return the largest structured repeated-attempt count, or 0 if absent."""
    best = 0
    for container in _iter_containers(evidence):
        for field_name in _BROKEN_COUNT_FIELDS:
            value = container.get(field_name)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                best = max(best, int(value))
    return best


# ---------------------------------------------------------------------------
# resolver context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolverContext:
    """Pre-computed evidence context shared by all ordered classifiers.

    Building this once avoids recomputing derived signals across the
    classifier chain and keeps each classifier a tiny, testable predicate.
    """

    norm: NormalizedEvidence
    blocker_verdict: str
    evidence: Mapping[str, Any]
    # liveness / terminal
    is_live: bool
    terminal_state: str
    is_terminal_success: bool
    # stale signals
    has_stale_needs_human: bool
    stale_label: str
    has_stale_derived_label: bool
    stale_source_names: tuple[str, ...]
    # human-gate signals
    has_explicit_gate: bool
    typed_gate: "TypedHumanGate | None"
    # block signals
    is_implementation_block: bool
    is_retryable_execution: bool
    has_needs_human_label: bool
    # broken-state signals
    escalation_label: str
    has_missing_workspace: bool
    broken_repeat_count: int
    # progress signals
    changed_file_count: "int | None"
    has_active_repair: bool
    # shared projections
    root_cause_fingerprint: str
    base_evidence: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, evidence: Mapping[str, Any], blocker_verdict: str) -> "ResolverContext":
        norm = normalize_evidence(evidence, blocker_verdict=blocker_verdict)

        chain_state = norm.evidence.get("chain_state")
        chain_state = chain_state if isinstance(chain_state, Mapping) else {}
        plan_state = norm.evidence.get("plan_state")
        plan_state = plan_state if isinstance(plan_state, Mapping) else {}

        chain_last = _safe_lower(chain_state, "last_state")
        plan_current = _safe_lower(plan_state, "current_state")
        stale_label = next(
            (label for label in (chain_last, plan_current) if label in _STALE_DERIVED_LABELS),
            "",
        )

        diagnostic_blob = " ".join(
            [
                *norm.event_signature_labels,
                norm.escalation_label,
                norm.retry_strategy,
                norm.latest_failure_kind,
            ]
        )
        is_implementation_block = _has_token(diagnostic_blob, _IMPLEMENTATION_BLOCK_TOKENS)
        is_retryable_execution = _has_token(diagnostic_blob, _RETRYABLE_EXECUTION_TOKENS)

        needs_human = norm.evidence.get("needs_human")
        needs_human = needs_human if isinstance(needs_human, Mapping) else {}
        typed_gate = _infer_typed_gate(needs_human)

        stale_source_names = tuple(norm.stale_kinds)

        parts = [
            norm.plan_state_fingerprint,
            norm.chain_state_fingerprint,
            norm.escalation_label,
            *sorted(norm.event_signature_labels),
        ]
        root_cause_fingerprint = "|".join(p for p in parts if p) or "unknown"

        base_evidence = (
            _evi("liveness", "", norm.liveness_status),
            _evi("terminal_state", "", norm.terminal_state or "not_terminal"),
            _evi(
                "diagnostic_codes",
                "",
                diagnostic_blob.strip() or "none",
            ),
            _evi("blocker_verdict", "", blocker_verdict or "none"),
        )

        return cls(
            norm=norm,
            blocker_verdict=blocker_verdict,
            evidence=evidence,
            is_live=norm.is_live,
            terminal_state=norm.terminal_state,
            is_terminal_success=norm.terminal_state.lower() in _SUCCESS_TERMINAL_STATES,
            has_stale_needs_human=norm.is_stale_needs_human,
            stale_label=stale_label,
            has_stale_derived_label=bool(stale_label),
            stale_source_names=stale_source_names,
            has_explicit_gate=norm.has_explicit_human_gate,
            typed_gate=typed_gate,
            is_implementation_block=is_implementation_block,
            is_retryable_execution=is_retryable_execution,
            has_needs_human_label=norm.has_needs_human,
            escalation_label=norm.escalation_label,
            has_missing_workspace=norm.is_missing_workspace,
            broken_repeat_count=_detect_broken_repeat(evidence),
            changed_file_count=norm.changed_file_count,
            has_active_repair=norm.has_active_repair,
            root_cause_fingerprint=root_cause_fingerprint,
            base_evidence=base_evidence,
        )

    def evidence_with_fingerprint(self) -> tuple[Mapping[str, Any], ...]:
        return self.base_evidence + (
            _evi("root_cause_fingerprint", "", self.root_cause_fingerprint),
        )


# ---------------------------------------------------------------------------
# ordered classifiers (first non-None result wins)
# ---------------------------------------------------------------------------


def classify_broken_state_machine(ctx: ResolverContext) -> "CanonicalRunState | None":
    """Explicit BROKEN escalation, missing workspace, or repeated blocker fingerprint.

    Per the North Star, BROKEN is a watchdog-side escalation *marker*: a live
    worker or an authoritative completion always overrides it, because both the
    explicit escalation label and the fingerprint heuristic can go stale.  This
    classifier therefore only fires when the run is neither live nor
    terminal-success.
    """
    explicit = ctx.escalation_label.upper() == "BROKEN_STATE_MACHINE"
    missing_workspace = ctx.has_missing_workspace
    repeated = ctx.broken_repeat_count >= _BROKEN_REPEAT_THRESHOLD
    if not (explicit or missing_workspace or repeated):
        return None
    # Live beats stale: a live worker is always given the chance to clear the
    # escalation, regardless of whether it was explicit or fingerprint-based.
    if ctx.is_live and not ctx.is_terminal_success:
        return None
    # Authority completion beats a stale BROKEN marker.
    if ctx.is_terminal_success:
        return None
    stale = ctx.stale_source_names
    if explicit:
        confidence = "high"
        source_of_truth = ("needs_human", "repair_progress")
        reason = (
            "Explicit BROKEN_STATE_MACHINE escalation label recorded by the "
            "needs-human sidecar and the worker is neither live nor complete."
        )
    elif missing_workspace:
        confidence = "high"
        source_of_truth = ("stale_evidence",)
        reason = (
            "Structured missing_workspace evidence indicates the custody "
            "workspace is gone and the worker is neither live nor complete."
        )
    else:
        confidence = "medium"
        source_of_truth = ("retry_fingerprints", "repair_progress")
        reason = (
            f"Same blocker fingerprint repeated {ctx.broken_repeat_count}x "
            "without progress and the worker is neither live nor complete."
        )
    evidence = ctx.evidence_with_fingerprint() + (
        _evi("broken_repeat_count", "", ctx.broken_repeat_count),
    )
    if missing_workspace:
        evidence = evidence + (_evi("missing_workspace", "", "present"),)
    return CanonicalRunState(
        canonical_state=CanonicalState.BROKEN_STATE_MACHINE,
        confidence=confidence,
        source_of_truth=source_of_truth,
        stale_sources=stale,
        human_required=False,
        human_gate=None,
        repairable=False,
        running=False,
        next_action="escalate_broken_state_machine",
        reason=reason,
        evidence=evidence,
    )


def classify_completed(ctx: ResolverContext) -> "CanonicalRunState | None":
    """Authority completion beats stale failed/no_next_step labels."""
    chain_last = _safe_lower(
        ctx.evidence.get("chain_state") if isinstance(ctx.evidence.get("chain_state"), Mapping) else {},
        "last_state",
    )
    authority_done = ctx.is_terminal_success
    # Secondary branch: real work completed (files changed) while a stale
    # chain layer still projects failed/no_next_step and the worker is not
    # live (i.e. the "deferred baseline with real tasks complete" shape).
    real_work_complete = (
        not authority_done
        and not ctx.is_live
        and chain_last in _STALE_FAILED_CHAIN_LABELS
        and ctx.changed_file_count is not None
        and ctx.changed_file_count > 0
        and not ctx.is_implementation_block
        and not ctx.is_retryable_execution
    )
    if not (authority_done or real_work_complete):
        return None

    stale = ctx.stale_source_names
    if chain_last in _STALE_FAILED_CHAIN_LABELS and "chain_state" not in stale:
        stale = stale + ("chain_state",)
    # A lingering needs-human marker after the plan completed is stale.
    if ctx.has_needs_human_label and "needs_human" not in stale:
        stale = stale + ("needs_human",)

    return CanonicalRunState(
        canonical_state=CanonicalState.COMPLETED,
        confidence="high" if authority_done else "medium",
        source_of_truth=("plan_state", "current_refs"),
        stale_sources=stale,
        human_required=False,
        human_gate=None,
        repairable=False,
        running=False,
        next_action="no_action_run_complete",
        reason=(
            "Authority plan state is terminal-success ('done')."
            if authority_done
            else "Real work complete (changed files present) with only a deferred "
            "baseline remaining; stale chain label overridden."
        ),
        evidence=ctx.evidence_with_fingerprint()
        + (
            _evi("changed_file_count", "", ctx.changed_file_count if ctx.changed_file_count is not None else "unknown"),
            _evi("authority_completion", "", ctx.terminal_state or "real_work_complete"),
        ),
    )


def classify_stale_derived_state(ctx: ResolverContext) -> "CanonicalRunState | None":
    """Live worker + stale manual-review/needs-human/failed label."""
    if not ctx.is_live:
        return None
    # A live worker alongside *any* needs-human marker or stale derived label is
    # the North Star "live beats stale labels" case: the marker is overridden.
    stale_signal = (
        ctx.has_stale_derived_label
        or ctx.has_stale_needs_human
        or ctx.has_needs_human_label
        or ctx.blocker_verdict == "STALE_MISMATCH"
    )
    if not stale_signal:
        return None
    return CanonicalRunState(
        canonical_state=CanonicalState.STALE_DERIVED_STATE,
        confidence="high",
        source_of_truth=("tmux_process", "active_step_heartbeat"),
        stale_sources=ctx.stale_source_names + (("needs_human",) if ctx.has_stale_needs_human else ())
        + ((ctx.stale_label or "derived_label"),),
        human_required=False,
        human_gate=None,
        repairable=False,
        running=True,
        next_action="trust_live_worker_suppress_stale_label",
        reason=(
            f"Live worker present while a stale derived label "
            f"('{ctx.stale_label or 'needs_human'}') was projected; live "
            "evidence overrides the stale label."
        ),
        evidence=ctx.evidence_with_fingerprint(),
    )


def classify_running(ctx: ResolverContext) -> "CanonicalRunState | None":
    """A live worker with no stale/blocked signal is actively running."""
    if not ctx.is_live:
        return None
    return CanonicalRunState(
        canonical_state=CanonicalState.RUNNING,
        confidence="medium",
        source_of_truth=("tmux_process", "active_step_heartbeat", "plan_state"),
        stale_sources=ctx.stale_source_names,
        human_required=False,
        human_gate=None,
        repairable=False,
        running=True,
        next_action="monitor_live_run",
        reason="Live worker / active-step heartbeat present with no blocking signal.",
        evidence=ctx.evidence_with_fingerprint(),
    )


def classify_human_action_required(ctx: ResolverContext) -> "CanonicalRunState | None":
    """Explicit typed human gate (not live, not an implementation block)."""
    # Live beats stale: a live worker cannot be needs-human.
    if ctx.is_live:
        return None
    # SD3: implementation / retryable blocks are machine-actionable, not human.
    if ctx.is_implementation_block or ctx.is_retryable_execution:
        return None
    # SD3: a MECHANICAL_BLOCKER verdict is a liveness/mechanical gate and is
    # never a human gate, even if a stray gate-category field is present.
    if ctx.blocker_verdict == "MECHANICAL_BLOCKER":
        return None
    is_confirmed = ctx.blocker_verdict == "TRUE_BLOCKER" or ctx.has_explicit_gate
    if not is_confirmed:
        return None
    gate = ctx.typed_gate
    if gate is None:
        # Only a confirmed TRUE_BLOCKER justifies a (defaulted) human
        # classification when no explicit typed category is recorded.
        if ctx.blocker_verdict == "TRUE_BLOCKER":
            gate = TypedHumanGate.USER_ACTION
        else:
            return None
    high_confidence = ctx.typed_gate is not None or ctx.blocker_verdict == "TRUE_BLOCKER"
    return CanonicalRunState(
        canonical_state=CanonicalState.HUMAN_ACTION_REQUIRED,
        confidence="high" if high_confidence else "medium",
        source_of_truth=("needs_human", "blocker_verdict")
        if ctx.blocker_verdict == "TRUE_BLOCKER"
        else ("needs_human",),
        stale_sources=ctx.stale_source_names,
        human_required=True,
        human_gate=gate,
        repairable=False,
        running=False,
        next_action="await_human_action",
        reason=(
            f"Explicit typed human gate ({gate.name}) recorded and the worker "
            "is not live; machine-actionable implementation blocks were "
            "excluded."
        ),
        evidence=ctx.evidence_with_fingerprint()
        + (_evi("human_gate", "", gate.name),),
    )


def classify_real_implementation_block(ctx: ResolverContext) -> "CanonicalRunState | None":
    """AWF018 / route-metadata-mismatch style machine-actionable block."""
    if not ctx.is_implementation_block:
        return None
    stale = ctx.stale_source_names
    return CanonicalRunState(
        canonical_state=CanonicalState.REAL_IMPLEMENTATION_BLOCK,
        confidence="high",
        source_of_truth=("diagnostic_codes", "event_signatures"),
        stale_sources=stale,
        human_required=False,
        human_gate=None,
        repairable=False,
        running=False,
        next_action="machine_repair_or_replan",
        reason=(
            "Machine-actionable implementation block diagnosed from structured "
            "diagnostic codes (e.g. AWF018 / route-metadata mismatch); not a "
            "human gate per SD3."
        ),
        evidence=ctx.evidence_with_fingerprint()
        + (
            _evi("event_signatures", "", " ".join(ctx.norm.event_signature_labels) or "none"),
            _evi("advisory_needs_human", "", "present" if ctx.has_needs_human_label else "absent"),
        ),
    )


def classify_retryable_execution_block(ctx: ResolverContext) -> "CanonicalRunState | None":
    """Transient / budget execution block that the machine can retry.

    Also captures a ``MECHANICAL_BLOCKER`` verdict (a liveness/mechanical gate)
    as a machine-actionable, repairable block — never a human gate (SD3).  The
    verdict is only honored when no stronger evidence signal (live worker,
    authority completion, or a more specific implementation-block diagnosis) is
    present, because those classifiers are checked earlier in the ordered chain.
    """
    is_mechanical = (
        ctx.blocker_verdict == "MECHANICAL_BLOCKER"
        and not ctx.is_implementation_block
    )
    if not (ctx.is_retryable_execution or is_mechanical):
        return None
    is_retry = ctx.is_retryable_execution
    return CanonicalRunState(
        canonical_state=CanonicalState.RETRYABLE_EXECUTION_BLOCK,
        confidence="medium",
        source_of_truth=("event_cursors", "plan_state")
        if is_retry
        else ("blocker_verdict",),
        stale_sources=ctx.stale_source_names,
        human_required=False,
        human_gate=None,
        repairable=True,
        running=False,
        next_action="requeue_or_retry",
        reason=(
            "Transient / budget execution block (no human gate, no "
            "implementation-block diagnosis); the machine may retry."
            if is_retry
            else "MECHANICAL_BLOCKER verdict: a machine-actionable mechanical / "
            "liveness gate; not a human gate per SD3."
        ),
        evidence=ctx.evidence_with_fingerprint()
        + (
            _evi("changed_file_count", "", ctx.changed_file_count if ctx.changed_file_count is not None else "unknown"),
            _evi(
                "retry_strategy",
                "",
                ctx.norm.retry_strategy or ("mechanical_blocker" if is_mechanical else "none"),
            ),
        ),
    )


def classify_repairing(ctx: ResolverContext) -> "CanonicalRunState | None":
    """Active repair-progress sidecars with no more-specific diagnosis."""
    if not ctx.has_active_repair:
        return None
    return CanonicalRunState(
        canonical_state=CanonicalState.REPAIRING,
        confidence="medium",
        source_of_truth=("repair_progress",),
        stale_sources=ctx.stale_source_names,
        human_required=False,
        human_gate=None,
        repairable=True,
        running=False,
        next_action="continue_repair",
        reason="Active repair-progress sidecars present (advisory repair data).",
        evidence=ctx.evidence_with_fingerprint()
        + (_evi("repair_status", "", ctx.norm.active_repair_status or "active"),),
    )


def classify_unknown(ctx: ResolverContext) -> CanonicalRunState:
    """Conservative fallback when no classifier matched."""
    return CanonicalRunState(
        canonical_state=CanonicalState.UNKNOWN,
        confidence="low",
        source_of_truth=(),
        stale_sources=ctx.stale_source_names,
        human_required=False,
        human_gate=None,
        repairable=False,
        running=ctx.is_live,
        next_action="inspect_evidence",
        reason=(
            "No authoritative signal matched an ordered classifier; the run is "
            "reported as UNKNOWN so consumers preserve legacy behavior rather "
            "than guessing."
        ),
        evidence=ctx.evidence_with_fingerprint()
        + (_evi("fallback", "", "conservative_unknown"),),
    )


# Ordered chain applied by ``resolve_run_state``.  Order encodes the North
# Star priority; each classifier is mutually exclusive given the evidence.
#
#   1. completed      - authoritative success / real-work-complete (strongest
#                       positive signal; stale watchdog/repair markers defer)
#   2. broken         - genuine BROKEN escalation when neither live nor complete
#   3. stale_derived  - live worker + stale label (live beats stale)
#   4. running        - live worker, no blocking signal (live beats stale)
#   5. human          - explicit typed gate / TRUE_BLOCKER (excludes machine blocks)
#   6. real_impl      - AWF018 / route-metadata machine block (SD3: not human)
#   7. retryable      - transient / budget / MECHANICAL_BLOCKER machine block
#   8. repairing      - advisory repair-progress sidecars
# (classify_unknown is the conservative fallback appended by the resolver.)
ORDERED_CLASSIFIERS = (
    classify_completed,
    classify_broken_state_machine,
    classify_stale_derived_state,
    classify_running,
    classify_human_action_required,
    classify_real_implementation_block,
    classify_retryable_execution_block,
    classify_repairing,
)
