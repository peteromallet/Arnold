"""Meta-repair classification, evidence loading, and prompt assembly.

When ordinary repair fails as a system, meta-repair diagnoses the
repair-system failure, builds a redacted Codex/DeepSeek prompt, and
prepares evidence for the meta-repair loop to act on.

Trigger types (six specified + explicit non-trigger):
    1. repair_timeout            – repair took longer than its allotted budget
    2. persistent_recurring_retry – same failure repeats across attempts
    3. state_inspection_failure   – resolver/snapshot failed to read state
    4. model_tool_launch_failure  – model/tool subprocess failed to start
    5. partial_liveness_recurrence – partial-liveness across >=2 watchdog ticks
    6. discord_delivery_failure   – Discord delivery failed for a TRUE_BLOCKER
       human escalation

Non-trigger: healthy repair, non-system error, stale evidence, etc.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping, Sequence

from arnold_pipelines.megaplan.cloud.redact import redact_payload, redact_text
from arnold_pipelines.megaplan.cloud.repair_lock import release_repair_lock
from arnold_pipelines.megaplan.cloud.repair_contract import (
    ALL_OUTCOMES,
    COMPLETE,
    DISCORD_ESCALATED,
    LIVE_WITH_FRESH_ACTIVITY,
    NEEDS_HUMAN,
    PARTIAL_LIVENESS,
    PROGRESSED,
    REPAIR_EXHAUSTED,
    REPAIR_TIMEOUT,
    REPAIRING,
    SUCCESS_OUTCOMES,
    TRUE_HUMAN_BLOCKER,
    atomic_write_json,
    build_verification_record,
    classify_verification_outcome,
    compute_deadline,
    is_budget_exhausted,
    is_success_outcome,
    load_json,
    remaining_budget_secs,
    update_session_index,
)


# ---------------------------------------------------------------------------
# Budget constant
# ---------------------------------------------------------------------------

META_REPAIR_BUDGET_SECS: int = 5400  # 90 minutes, longer than ordinary repair


# ---------------------------------------------------------------------------
# Trigger type enumeration
# ---------------------------------------------------------------------------


class MetaRepairTrigger(str, Enum):
    """The six specified meta-repair trigger types."""

    REPAIR_TIMEOUT = "repair_timeout"
    PERSISTENT_RECURRING_RETRY = "persistent_recurring_retry"
    STATE_INSPECTION_FAILURE = "state_inspection_failure"
    MODEL_TOOL_LAUNCH_FAILURE = "model_tool_launch_failure"
    PARTIAL_LIVENESS_RECURRENCE = "partial_liveness_recurrence"
    DISCORD_DELIVERY_FAILURE = "discord_delivery_failure"


# Canonical ordering for display / prompt ordering
_TRIGGER_ORDER: dict[MetaRepairTrigger, int] = {
    MetaRepairTrigger.REPAIR_TIMEOUT: 1,
    MetaRepairTrigger.PERSISTENT_RECURRING_RETRY: 2,
    MetaRepairTrigger.STATE_INSPECTION_FAILURE: 3,
    MetaRepairTrigger.MODEL_TOOL_LAUNCH_FAILURE: 4,
    MetaRepairTrigger.PARTIAL_LIVENESS_RECURRENCE: 5,
    MetaRepairTrigger.DISCORD_DELIVERY_FAILURE: 6,
}

_META_REPAIR_ACCEPTED_SUCCESS_OUTCOMES = SUCCESS_OUTCOMES | frozenset(
    {LIVE_WITH_FRESH_ACTIVITY}
)


def authoritative_terminal_snapshot_reason(snapshot: Mapping[str, Any] | None) -> str:
    """Explain why a post-retrigger snapshot cannot close repair custody.

    The repair-data outcome is a claim made by L1.  L2 must independently
    preserve enough current state to prove that the claim is safe.  This is
    deliberately strict: a ``finalized`` plan, a past-end milestone index, or
    a dead worker PID are all contradiction evidence, not completion.
    """
    if not isinstance(snapshot, Mapping):
        return "authoritative post-retrigger snapshot missing"
    if not str(snapshot.get("captured_at") or "").strip():
        return "authoritative post-retrigger snapshot has no capture timestamp"
    try:
        total = int(snapshot.get("milestone_total"))
        completed = int(snapshot.get("completed_count"))
    except (TypeError, ValueError):
        return "authoritative post-retrigger snapshot has unknown milestone total"
    if total <= 0:
        return "authoritative post-retrigger snapshot has unknown milestone total"
    if completed < total:
        return f"authoritative post-retrigger snapshot is incomplete ({completed}/{total})"
    if bool(snapshot.get("active_step_present")):
        return "authoritative post-retrigger snapshot still has active_step"
    if snapshot.get("worker_pid_alive") is False:
        return "authoritative post-retrigger snapshot records a dead worker"
    chain_state = str(snapshot.get("chain_last_state") or "").strip().lower()
    plan_state = str(snapshot.get("plan_current_state") or "").strip().lower()
    if chain_state not in {"done", "complete", "completed"}:
        return f"authoritative post-retrigger snapshot has nonterminal chain state {chain_state or 'missing'}"
    if plan_state not in {"done", "complete"}:
        return f"authoritative post-retrigger snapshot has nonterminal plan state {plan_state or 'missing'}"
    return ""


def trigger_priority(trigger: MetaRepairTrigger) -> int:
    """Return the canonical ordering priority for *trigger* (1-6)."""
    return _TRIGGER_ORDER.get(trigger, 99)


# ---------------------------------------------------------------------------
# Classification dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetaRepairClassification:
    """Result of classifying a repair-system failure for meta-repair dispatch.

    When *trigger* is ``None`` the failure does not match any of the six
    specified trigger types and meta-repair should NOT be dispatched.
    """

    session: str
    trigger: MetaRepairTrigger | None
    rationale: Sequence[str] = field(default_factory=tuple)
    evidence: dict[str, Any] = field(default_factory=dict)
    attempted_at: str = ""

    @property
    def should_dispatch(self) -> bool:
        """Return ``True`` when meta-repair dispatch is indicated."""
        return self.trigger is not None

    @property
    def trigger_label(self) -> str:
        """Human-readable trigger label (or 'none' for non-triggers)."""
        return self.trigger.value if self.trigger is not None else "none"


# ---------------------------------------------------------------------------
# Evidence loading
# ---------------------------------------------------------------------------


def load_redacted_evidence(
    session: str,
    *,
    repair_data_dir: str | Path,
    index_path: str | Path | None = None,
    attempt_dir: str | Path | None = None,
    sidecar_dir: str | Path | None = None,
    max_attempts: int = 20,
    secret_names: Sequence[str] = (),
) -> dict[str, Any]:
    """Load and redact repair evidence for meta-repair classification.

    Returns a dict with redacted snapshots of the repair-data record,
    recent attempts, and index state.  All string values are run through
    :func:`redact_payload` before the dict is returned.
    """
    repair_root = Path(repair_data_dir)
    effective_index = Path(index_path) if index_path is not None else repair_root / "index.json"
    effective_attempts = Path(attempt_dir) if attempt_dir is not None else repair_root / "attempts"
    effective_sidecar = Path(sidecar_dir) if sidecar_dir is not None else repair_root.with_name(f"{repair_root.name}.d")

    evidence: dict[str, Any] = {
        "session": session,
        "loaded_at": datetime.now(timezone.utc).isoformat(),
    }

    # --- repair-data snapshot ---------------------------------------------------
    repair_data_path = repair_root / f"{session}.repair-data.json"
    repair_data: dict[str, Any] = {}
    try:
        raw = load_json(repair_data_path, default={})
        # Filter secret-bearing keys and redact
        repair_data = redact_payload(
            raw,
            secret_names=list(secret_names),
        )
    except Exception:
        pass
    evidence["repair_data"] = repair_data
    evidence["repair_data_path"] = str(repair_data_path)

    # --- recent attempt records -------------------------------------------------
    attempts: list[dict[str, Any]] = []
    if effective_attempts.exists():
        for attempt_path in sorted(effective_attempts.glob("*.json"), reverse=True):
            if len(attempts) >= max_attempts:
                break
            raw_attempt = load_json(attempt_path, default={})
            if raw_attempt:
                attempts.append(redact_payload(raw_attempt, secret_names=list(secret_names)))
    evidence["recent_attempts"] = attempts
    evidence["attempt_dir"] = str(effective_attempts)

    # --- index snapshot ---------------------------------------------------------
    index_payload: dict[str, Any] = {}
    try:
        index_payload = load_json(effective_index, default={})
    except Exception:
        pass
    evidence["index"] = redact_payload(index_payload, secret_names=list(secret_names))
    evidence["index_path"] = str(effective_index)

    # --- partial-liveness sidecar -----------------------------------------------
    partial_liveness_history: list[dict[str, Any]] = []
    if effective_sidecar.exists():
        liveness_path = effective_sidecar / "events" / "events.jsonl"
        if liveness_path.exists():
            from arnold_pipelines.megaplan.cloud.repair_contract import read_jsonl_records

            try:
                all_events = read_jsonl_records(liveness_path, skip_parse_errors=True)
                partial_liveness_history = [
                    redact_payload(e, secret_names=list(secret_names))
                    for e in all_events
                    if (
                        isinstance(e, dict)
                        and e.get("outcome") == PARTIAL_LIVENESS
                        and str(e.get("session") or "").strip() == session
                    )
                ][-max_attempts:]
            except Exception:
                pass
    evidence["partial_liveness_history"] = partial_liveness_history

    return evidence


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------

# Minimum number of attempts with the same failure kind before we consider
# it a persistent recurring retry pattern.
_MIN_RECURRING_ATTEMPTS = 3

# Minimum number of partial-liveness ticks before we trigger.
_MIN_PARTIAL_LIVENESS_TICKS = 2

# Meta-repair prompts must stay well under Codex's input limit even when
# repair-data snapshots contain large embedded logs or prompts.
_PROMPT_EVIDENCE_CHAR_BUDGET = 180_000
_PROMPT_MAX_STRING_CHARS = 4_000
_PROMPT_MAX_LIST_ITEMS = 12
_PROMPT_MAX_DICT_ITEMS = 64
_PROMPT_MAX_DEPTH = 6
_PROMPT_TOTAL_CHAR_BUDGET = 900_000

_MODEL_TOOL_LAUNCH_FAILURE_STATUSES = {
    "failed:missing_relaunch_command",
    "failed:tmux_launch_failed",
}


def _summarize_attempt_record(attempt: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact, diagnostic-only attempt summary for prompts."""
    summary: dict[str, Any] = {}
    for key in (
        "attempt_id",
        "recorded_at",
        "session",
        "plan_name",
        "run_kind",
        "health",
        "outcome",
        "failure_kind",
        "failure_classification",
        "dev_classification",
        "kimi_classification",
        "mechanical_launch",
        "mechanical_detail",
        "current_signature",
    ):
        value = attempt.get(key)
        if value not in (None, "", [], {}):
            summary[key] = value

    advancement = attempt.get("advancement_snapshot")
    if isinstance(advancement, Mapping):
        advancement_summary = {
            key: advancement.get(key)
            for key in (
                "completed_count",
                "current_milestone_index",
                "current_state",
                "milestone_or_plan",
                "phase",
                "pr_number",
                "run_kind",
            )
            if advancement.get(key) not in (None, "", [], {})
        }
        if advancement_summary:
            summary["advancement_snapshot"] = advancement_summary

    chain_state = attempt.get("chain_state_summary")
    if isinstance(chain_state, Mapping):
        chain_summary = {
            key: chain_state.get(key)
            for key in (
                "completed_count",
                "current_milestone_index",
                "current_plan_name",
                "current_state",
                "last_state",
                "pr_number",
                "pr_state",
            )
            if chain_state.get(key) not in (None, "", [], {})
        }
        if chain_summary:
            summary["chain_state_summary"] = chain_summary

    return summary


def is_model_tool_launch_failure_status(
    status: str,
    *,
    state_tokens: Sequence[str] = (),
) -> bool:
    """Return True only for genuine model/tool launch setup failures.

    Repair-loop status strings such as ``failed:stopped`` and
    ``failed:retrying_failure`` are emitted after a process launched and then
    died during the initial hold window. Those are post-launch health outcomes,
    not launch failures, and must not drive meta-repair's
    ``model_tool_launch_failure`` trigger.
    """
    normalized = status.strip()
    if not normalized.startswith("failed:"):
        return False
    if any(token in normalized for token in state_tokens):
        return False
    if normalized in _MODEL_TOOL_LAUNCH_FAILURE_STATUSES:
        return True

    lowered = normalized.lower()
    if "missing" in lowered and ("api_key" in lowered or "credentials" in lowered):
        return True
    return False


def _prepare_emergency_prompt_json(
    payload: Mapping[str, Any], *, secret_names: Sequence[str]
) -> str:
    """Serialize a minimal prompt-safe evidence summary."""
    import json as _json

    redacted = redact_payload(payload, secret_names=list(secret_names))
    repair_data = redacted.get("repair_data", {})
    if not isinstance(repair_data, Mapping):
        repair_data = {}
    recent_attempts = redacted.get("recent_attempts", [])
    if not isinstance(recent_attempts, list):
        recent_attempts = []
    partial_liveness_history = redacted.get("partial_liveness_history", [])
    if not isinstance(partial_liveness_history, list):
        partial_liveness_history = []

    repair_attempts = repair_data.get("attempts", [])
    if not isinstance(repair_attempts, list):
        repair_attempts = []

    emergency = {
        "prompt_truncated": True,
        "available_top_level_keys": sorted(str(key) for key in redacted.keys()),
        "session": redacted.get("session", ""),
        "repair_data_path": redacted.get("repair_data_path", ""),
        "attempt_dir": redacted.get("attempt_dir", ""),
        "index_path": redacted.get("index_path", ""),
        "repair_data_summary": {
            key: repair_data.get(key)
            for key in (
                "session",
                "run_kind",
                "plan_name",
                "outcome",
                "repair_run_count",
                "attempt_counter",
                "current_attempt_id",
                "current_signature",
                "current_recurrence",
                "verification",
            )
            if repair_data.get(key) not in (None, "", [], {})
        },
        "repair_attempt_count": len(repair_attempts),
        "repair_attempt_summaries": [
            _summarize_attempt_record(attempt)
            for attempt in repair_attempts[-3:]
            if isinstance(attempt, Mapping)
        ],
        "recent_attempt_count": len(recent_attempts),
        "recent_attempt_summaries": [
            _summarize_attempt_record(attempt)
            for attempt in recent_attempts[-3:]
            if isinstance(attempt, Mapping)
        ],
        "partial_liveness_count": len(partial_liveness_history),
        "partial_liveness_tail": [
            {
                key: item.get(key)
                for key in ("recorded_at", "health", "outcome", "plan_name", "run_kind")
                if item.get(key) not in (None, "", [], {})
            }
            for item in partial_liveness_history[-3:]
            if isinstance(item, Mapping)
        ],
    }

    compact = _compact_prompt_value(
        emergency,
        max_depth=4,
        max_string_chars=400,
        max_list_items=6,
        max_dict_items=24,
    )
    return _json.dumps(compact, indent=2, default=str, ensure_ascii=False)


def classify_repair_system_failure(
    session: str,
    *,
    evidence: Mapping[str, Any] | None = None,
    current_target_observation: Mapping[str, Any] | None = None,
    repair_data_dir: str | Path | None = None,
    repair_outcome: str = "",
    attempt_outcomes: Sequence[str] = (),
    failure_kinds: Sequence[str] = (),
    has_state_inspection_error: bool = False,
    has_model_tool_launch_error: bool = False,
    partial_liveness_ticks: int = 0,
    discord_delivery_failed: bool = False,
    discord_escalation_is_true_blocker: bool = False,
    repair_budget_exhausted: bool = False,
    now: datetime | None = None,
) -> MetaRepairClassification:
    """Classify a repair-system failure into one of the six trigger types.

    The function applies a prioritized decision tree (first match wins):

    1. *discord_delivery_failure* — Discord delivery failed AND the
       escalation is a confirmed TRUE_BLOCKER.
    2. *repair_timeout* — repair budget exhausted with a timeout outcome.
    3. *persistent_recurring_retry* — same failure kind repeats across
       at least *min_recurring_attempts* attempts without progress.
    4. *state_inspection_failure* — resolver or snapshot reported an
       error reading repair state.
    5. *model_tool_launch_failure* — a model or tool subprocess failed
       to start.
    6. *partial_liveness_recurrence* — partial liveness observed across
       at least *min_partial_liveness_ticks* watchdog ticks.

    When none of the six trigger conditions match the evidence, *trigger*
    is ``None`` (non-trigger) and *should_dispatch* returns ``False``.

    Args:
        session: The repair session identifier.
        evidence: Pre-loaded redacted evidence dict (optional).  When
            provided it is attached to the result for prompt assembly.
        repair_data_dir: Optional repair-data directory path — attached
            to the result as context.
        repair_outcome: The current repair verification outcome.
        attempt_outcomes: Recent attempt outcome strings.
        failure_kinds: Failure-kind tags from recent attempts.
        has_state_inspection_error: True when state inspection failed.
        has_model_tool_launch_error: True when model/tool launch failed.
        partial_liveness_ticks: Count of consecutive partial-liveness
            watchdog ticks.
        discord_delivery_failed: True when Discord message delivery failed.
        discord_escalation_is_true_blocker: True when the escalation was
            classified as a TRUE_BLOCKER.
        repair_budget_exhausted: True when the repair budget is exhausted.
        now: Current timestamp (defaults to utcnow).

    Returns:
        A :class:`MetaRepairClassification` with the verdict.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    rationale: list[str] = []

    stale_repair_reason = _repair_evidence_superseded_by_current_target(
        evidence=evidence,
        current_target_observation=current_target_observation,
    )
    if stale_repair_reason:
        rationale.append(stale_repair_reason)
        return MetaRepairClassification(
            session=session,
            trigger=None,
            rationale=tuple(rationale),
            evidence=deepcopy(dict(evidence)) if evidence else {},
            attempted_at=now.isoformat(),
        )

    # --- 1. Discord delivery failure (TRUE_BLOCKER gate) --------------------
    if discord_delivery_failed and discord_escalation_is_true_blocker:
        rationale.append(
            "Discord delivery failed for a TRUE_BLOCKER human escalation "
            f"(session={session})"
        )
        return MetaRepairClassification(
            session=session,
            trigger=MetaRepairTrigger.DISCORD_DELIVERY_FAILURE,
            rationale=tuple(rationale),
            evidence=deepcopy(dict(evidence)) if evidence else {},
            attempted_at=now.isoformat(),
        )

    # Discord delivery failure without TRUE_BLOCKER is NOT a trigger
    if discord_delivery_failed and not discord_escalation_is_true_blocker:
        rationale.append(
            "Discord delivery failed but escalation is NOT a TRUE_BLOCKER; "
            "skipping meta-repair dispatch"
        )
        return MetaRepairClassification(
            session=session,
            trigger=None,
            rationale=tuple(rationale),
            evidence=deepcopy(dict(evidence)) if evidence else {},
            attempted_at=now.isoformat(),
        )

    if repair_outcome and (
        is_success_outcome(repair_outcome)
        or repair_outcome in _META_REPAIR_ACCEPTED_SUCCESS_OUTCOMES
    ):
        rationale.append(
            "ordinary repair already reached a terminal success outcome "
            f"({repair_outcome}); skipping meta-repair dispatch"
        )
        return MetaRepairClassification(
            session=session,
            trigger=None,
            rationale=tuple(rationale),
            evidence=deepcopy(dict(evidence)) if evidence else {},
            attempted_at=now.isoformat(),
        )

    # --- 2. Repair timeout --------------------------------------------------
    if repair_budget_exhausted and repair_outcome in (REPAIR_TIMEOUT, REPAIR_EXHAUSTED):
        rationale.append(
            f"repair budget exhausted with outcome={repair_outcome!r}"
        )
        return MetaRepairClassification(
            session=session,
            trigger=MetaRepairTrigger.REPAIR_TIMEOUT,
            rationale=tuple(rationale),
            evidence=deepcopy(dict(evidence)) if evidence else {},
            attempted_at=now.isoformat(),
        )

    # --- 3. Persistent recurring retry --------------------------------------
    if _is_persistent_recurring_retry(failure_kinds, attempt_outcomes):
        rationale.append(
            f"persistent recurring retry pattern detected "
            f"(failure_kinds={list(failure_kinds)[:5]}, "
            f"attempt_outcomes={list(attempt_outcomes)[:5]})"
        )
        return MetaRepairClassification(
            session=session,
            trigger=MetaRepairTrigger.PERSISTENT_RECURRING_RETRY,
            rationale=tuple(rationale),
            evidence=deepcopy(dict(evidence)) if evidence else {},
            attempted_at=now.isoformat(),
        )

    # --- 4. State inspection failure ----------------------------------------
    if has_state_inspection_error:
        rationale.append(
            "resolver or snapshot reported a state-inspection error"
        )
        return MetaRepairClassification(
            session=session,
            trigger=MetaRepairTrigger.STATE_INSPECTION_FAILURE,
            rationale=tuple(rationale),
            evidence=deepcopy(dict(evidence)) if evidence else {},
            attempted_at=now.isoformat(),
        )

    # --- 5. Model/tool launch failure ---------------------------------------
    if has_model_tool_launch_error:
        rationale.append(
            "model or tool subprocess failed to launch"
        )
        return MetaRepairClassification(
            session=session,
            trigger=MetaRepairTrigger.MODEL_TOOL_LAUNCH_FAILURE,
            rationale=tuple(rationale),
            evidence=deepcopy(dict(evidence)) if evidence else {},
            attempted_at=now.isoformat(),
        )

    # --- 6. Partial-liveness recurrence -------------------------------------
    if partial_liveness_ticks >= _MIN_PARTIAL_LIVENESS_TICKS:
        rationale.append(
            f"partial liveness observed across {partial_liveness_ticks} "
            f"watchdog ticks (threshold={_MIN_PARTIAL_LIVENESS_TICKS})"
        )
        return MetaRepairClassification(
            session=session,
            trigger=MetaRepairTrigger.PARTIAL_LIVENESS_RECURRENCE,
            rationale=tuple(rationale),
            evidence=deepcopy(dict(evidence)) if evidence else {},
            attempted_at=now.isoformat(),
        )

    # --- No trigger matched — non-trigger case ------------------------------
    rationale.append(
        "no meta-repair trigger condition matched: "
        f"outcome={repair_outcome!r}, "
        f"state_error={has_state_inspection_error}, "
        f"launch_error={has_model_tool_launch_error}, "
        f"partial_liveness_ticks={partial_liveness_ticks}, "
        f"budget_exhausted={repair_budget_exhausted}"
    )
    return MetaRepairClassification(
        session=session,
        trigger=None,
        rationale=tuple(rationale),
        evidence=deepcopy(dict(evidence)) if evidence else {},
        attempted_at=now.isoformat(),
    )


def _is_persistent_recurring_retry(
    failure_kinds: Sequence[str],
    attempt_outcomes: Sequence[str],
    min_attempts: int = _MIN_RECURRING_ATTEMPTS,
) -> bool:
    """Return True when the same failure kind repeats without success."""
    if len(failure_kinds) < min_attempts:
        return False

    # Look for the same non-empty failure kind repeating in the most
    # recent attempts.
    recent = list(failure_kinds)[: min(len(failure_kinds), 10)]
    recent_outcomes = list(attempt_outcomes)[: min(len(attempt_outcomes), 10)]

    # Count occurrences of the most common recent failure kind
    kind_counts: dict[str, int] = {}
    for kind in recent:
        if kind and kind.strip():
            kind_counts[kind] = kind_counts.get(kind, 0) + 1

    if not kind_counts:
        return False

    most_common_kind, count = max(kind_counts.items(), key=lambda item: item[1])
    if count < min_attempts:
        return False

    # Also check that none of the recent outcomes are success
    recent_non_empty = [o for o in recent_outcomes if o and o.strip()]
    has_recent_success = any(
        is_success_outcome(o) for o in recent_non_empty
    )
    if has_recent_success:
        return False

    return True


def _repair_evidence_superseded_by_current_target(
    *,
    evidence: Mapping[str, Any] | None,
    current_target_observation: Mapping[str, Any] | None,
) -> str:
    """Return a rationale when current-target proof supersedes stale repair state."""

    if not isinstance(evidence, Mapping) or not isinstance(current_target_observation, Mapping):
        return ""

    repair_data = evidence.get("repair_data")
    if not isinstance(repair_data, Mapping):
        return ""

    authoritative_source = _meta_safe_text(
        current_target_observation.get("authoritative_source")
    )
    if not authoritative_source or authoritative_source == "resolver_observe_disabled":
        return ""

    active_step = current_target_observation.get("active_step_heartbeat")
    if isinstance(active_step, Mapping) and bool(active_step.get("active")):
        return ""

    stale_evidence = current_target_observation.get("stale_evidence")
    stale_kinds = {
        _meta_safe_text(item.get("kind"))
        for item in stale_evidence
        if isinstance(item, Mapping)
    } if isinstance(stale_evidence, Sequence) else set()

    current_refs = current_target_observation.get("current_refs")
    if not isinstance(current_refs, Mapping):
        current_refs = {}
    current_run_kind = _meta_safe_text(current_refs.get("run_kind")).lower()

    has_runtime_proof = _current_target_has_runtime_proof(current_target_observation)
    if "workspace_missing" in stale_kinds:
        return (
            "current-target observation supersedes stale recurring repair evidence: "
            "workspace is missing for the recorded repair target"
        )
    if (
        "spec_missing" in stale_kinds
        and current_run_kind in {"chain", "epic_chain"}
        and not has_runtime_proof
    ):
        return (
            "current-target observation supersedes stale recurring repair evidence: "
            "chain spec is missing and no live chain/plan artifacts remain"
        )
    if not has_runtime_proof:
        return ""

    current_plan_name = _meta_safe_text(
        current_refs.get("current_plan_name")
    ) or _meta_safe_text(current_refs.get("chain_current_plan_name"))
    current_plan_state = _meta_safe_text(current_refs.get("plan_current_state")).lower()
    current_chain_state = _meta_safe_text(current_refs.get("chain_last_state")).lower()

    current_signature = repair_data.get("current_signature")
    if not isinstance(current_signature, Mapping):
        current_signature = {}
    advancement = repair_data.get("current_advancement_snapshot")
    if not isinstance(advancement, Mapping):
        advancement = {}
    failure_context = repair_data.get("current_failure_context")
    if not isinstance(failure_context, Mapping):
        failure_context = {}
    latest_failure = failure_context.get("plan_latest_failure")
    if not isinstance(latest_failure, Mapping):
        latest_failure = {}
    plan_runtime_state = failure_context.get("plan_runtime_state")
    if not isinstance(plan_runtime_state, Mapping):
        plan_runtime_state = {}

    repair_plan_name = _meta_safe_text(
        current_signature.get("milestone_or_plan")
    ) or _meta_safe_text(advancement.get("milestone_or_plan")) or _meta_safe_text(
        latest_failure.get("plan_name")
    ) or _meta_safe_text(
        (failure_context.get("chain_state_summary") or {}).get("current_plan_name")
        if isinstance(failure_context.get("chain_state_summary"), Mapping)
        else ""
    )
    repair_state = _meta_safe_text(
        current_signature.get("current_state")
    ) or _meta_safe_text(advancement.get("current_state")) or _meta_safe_text(
        latest_failure.get("current_state")
    ) or _meta_safe_text(
        plan_runtime_state.get("current_state")
    )
    repair_state = repair_state.lower()
    repair_kind = _meta_safe_text(
        current_signature.get("failure_kind")
    ) or _meta_safe_text(
        failure_context.get("failure_classification")
    )
    repair_phase = _meta_safe_text(
        current_signature.get("phase_or_step")
    ) or _meta_safe_text(
        latest_failure.get("phase")
    )

    if repair_plan_name and current_plan_name and repair_plan_name != current_plan_name:
        return (
            "current-target observation supersedes stale recurring repair evidence: "
            f"repair-data tracked {repair_plan_name}, live state is now {current_plan_name}"
        )

    stale_states = {"blocked", "authority_divergence", "failed", "manual_review", "awaiting_human"}
    recovered_plan_states = {"finalized", "done", "complete", "completed"}
    recovered_chain_states = {"finalized", "awaiting_pr_merge", "done", "complete", "completed"}
    target_has_recovery_shape = (
        current_plan_state in recovered_plan_states
        or current_chain_state in recovered_chain_states
    )
    if repair_state in stale_states:
        if current_plan_state in recovered_plan_states:
            return (
                "current-target observation supersedes stale recurring repair evidence: "
                f"repair-data state={repair_state} but live plan state is {current_plan_state}"
            )
        if current_chain_state in recovered_chain_states:
            return (
                "current-target observation supersedes stale recurring repair evidence: "
                f"repair-data state={repair_state} but live chain state is {current_chain_state}"
            )

    repair_outcome = _meta_safe_text(repair_data.get("outcome")).lower()
    running_outcomes = {"running", "repairing", "recurring_retry_pending"}
    if (
        repair_outcome
        and repair_outcome not in _META_REPAIR_ACCEPTED_SUCCESS_OUTCOMES
        and repair_outcome not in running_outcomes
        and target_has_recovery_shape
        and _failure_context_is_mechanical_redrive_only(failure_context)
    ):
        return (
            "current-target observation supersedes stale recurring repair evidence: "
            f"repair outcome is {repair_outcome} but live target is already recovered "
            "and failure context shows no latest failure"
        )

    observation_plan_state = current_target_observation.get("plan_state")
    live_status = _load_current_target_status(
        observation_plan_state.get("path")
        if isinstance(observation_plan_state, Mapping)
        else None
    )
    if (
        repair_kind == "blocked_state_or_recovery_error"
        and repair_phase == "execute"
        and repair_state == "finalized"
        and current_plan_state == "finalized"
        and _status_proves_terminal_blocker_without_retry(live_status)
    ):
        return (
            "current-target observation supersedes stale recurring repair evidence: "
            "live status is finalized with terminal blockers and no execute retry path"
        )

    repair_outcome = _meta_safe_text(repair_data.get("outcome")).lower()
    running_outcomes = {"running", "repairing", "recurring_retry_pending"}
    if repair_outcome in running_outcomes:
        latest_repair_epoch = _latest_repair_activity_epoch(evidence)
        latest_target_epoch = _latest_current_target_epoch(current_target_observation)
        target_has_recovery_shape = (
            current_plan_state in recovered_plan_states
            or current_chain_state in recovered_chain_states
        )
        if (
            latest_repair_epoch is not None
            and latest_target_epoch is not None
            and latest_target_epoch > latest_repair_epoch
            and target_has_recovery_shape
        ):
            return (
                "current-target observation supersedes stale recurring repair evidence: "
                f"repair outcome is {repair_outcome} but live target activity is newer "
                f"({latest_target_epoch:.3f} > {latest_repair_epoch:.3f})"
            )

    return ""


def stale_repair_evidence_reason(
    *,
    evidence: Mapping[str, Any] | None,
    current_target_observation: Mapping[str, Any] | None,
) -> str:
    """Return a rationale when current-target state makes repair evidence stale."""

    return _repair_evidence_superseded_by_current_target(
        evidence=evidence,
        current_target_observation=current_target_observation,
    )


def _current_target_has_runtime_proof(current_target_observation: Mapping[str, Any]) -> bool:
    active_step = current_target_observation.get("active_step_heartbeat")
    if isinstance(active_step, Mapping) and bool(active_step.get("active")):
        return True

    tmux_process = current_target_observation.get("tmux_process")
    if isinstance(tmux_process, Mapping) and _meta_safe_text(tmux_process.get("live_status")) == "alive":
        return True

    for key in ("plan_state", "chain_state"):
        record = current_target_observation.get(key)
        if isinstance(record, Mapping) and bool(record.get("present")):
            return True

    # Historical logs can survive after the target is gone; do not treat them
    # as proof that another repair/meta-repair attempt is warranted.
    return False


def _failure_context_is_mechanical_redrive_only(
    failure_context: Mapping[str, Any],
) -> bool:
    stale_state = failure_context.get("stale_state")
    if not isinstance(stale_state, Mapping):
        stale_state = {}
    if _meta_safe_text(stale_state.get("classification")) != "NO LATEST FAILURE":
        return False
    if _meta_safe_text(stale_state.get("recommended_action")) != "mechanical re-drive only":
        return False

    latest_failure = failure_context.get("plan_latest_failure")
    if not isinstance(latest_failure, Mapping):
        latest_failure = {}
    return not any(
        _meta_safe_text(latest_failure.get(key))
        for key in ("kind", "message", "state", "recorded_at", "phase")
    )


def _meta_safe_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _parse_meta_timestamp(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _latest_repair_activity_epoch(evidence: Mapping[str, Any]) -> float | None:
    latest: float | None = None

    def consider_timestamp(value: Any) -> None:
        nonlocal latest
        parsed = _parse_meta_timestamp(value)
        if parsed is None:
            return
        if latest is None or parsed > latest:
            latest = parsed

    repair_data = evidence.get("repair_data")
    if isinstance(repair_data, Mapping):
        for key in (
            "recorded_at",
            "attempted_at",
            "updated_at",
            "dispatched_at",
            "completed_at",
            "finished_at",
        ):
            consider_timestamp(repair_data.get(key))
        for collection_key in ("attempts", "iterations"):
            records = repair_data.get(collection_key)
            if not isinstance(records, list):
                continue
            for record in records:
                if not isinstance(record, Mapping):
                    continue
                for key in (
                    "recorded_at",
                    "attempted_at",
                    "updated_at",
                    "dispatched_at",
                    "completed_at",
                    "finished_at",
                ):
                    consider_timestamp(record.get(key))

    if latest is not None:
        return latest

    repair_data_path = evidence.get("repair_data_path")
    if isinstance(repair_data_path, str) and repair_data_path:
        try:
            return Path(repair_data_path).stat().st_mtime
        except OSError:
            return None
    return None


def _latest_current_target_epoch(current_target_observation: Mapping[str, Any]) -> float | None:
    latest: float | None = None
    for key in ("plan_state", "chain_state", "chain_log", "event_cursors"):
        record = current_target_observation.get(key)
        if not isinstance(record, Mapping):
            continue
        raw_mtime = record.get("mtime")
        if isinstance(raw_mtime, (int, float)):
            mtime = float(raw_mtime)
            if latest is None or mtime > latest:
                latest = mtime
    return latest


def _load_current_target_status(plan_state_path: str | Path | None) -> Mapping[str, Any] | None:
    if not isinstance(plan_state_path, (str, Path)) or not str(plan_state_path):
        return None
    try:
        state_path = Path(plan_state_path)
        from arnold_pipelines.megaplan._core import read_json
        from arnold_pipelines.megaplan.cli.status_view import _build_status_payload

        state = read_json(state_path)
        if not isinstance(state, dict):
            return None
        status = _build_status_payload(state_path.parent, state)
        return status if isinstance(status, Mapping) else None
    except Exception:
        return None


def _status_proves_terminal_blocker_without_retry(status: Mapping[str, Any] | None) -> bool:
    if not isinstance(status, Mapping):
        return False
    if status.get("next_step") is not None:
        return False
    valid_next = status.get("valid_next")
    if isinstance(valid_next, Sequence) and any(str(item).strip() for item in valid_next):
        return False
    blocker_recovery = status.get("blocker_recovery")
    if not isinstance(blocker_recovery, Mapping):
        return False
    if blocker_recovery.get("has_terminal_blockers") is not True:
        return False
    active_step = status.get("active_step")
    if isinstance(active_step, Mapping) and bool(active_step.get("active")):
        return False
    return True


def _truncate_prompt_text(text: str, *, max_chars: int) -> str:
    """Clip oversized prompt text while preserving both ends."""
    if len(text) <= max_chars:
        return text
    marker = f"\n... [truncated {len(text) - max_chars} chars] ...\n"
    head_budget = max(32, (max_chars - len(marker)) // 2)
    tail_budget = max(32, max_chars - len(marker) - head_budget)
    return f"{text[:head_budget]}{marker}{text[-tail_budget:]}"


def _compact_prompt_value(
    value: Any,
    *,
    max_depth: int,
    max_string_chars: int,
    max_list_items: int,
    max_dict_items: int,
) -> Any:
    """Reduce oversized JSON-like evidence to a bounded prompt view."""
    if max_depth <= 0:
        if isinstance(value, str):
            return _truncate_prompt_text(value, max_chars=min(max_string_chars, 256))
        if isinstance(value, Mapping):
            return {"__truncated__": "mapping"}
        if isinstance(value, (list, tuple)):
            return ["__truncated_sequence__"]
        return value

    if isinstance(value, str):
        return _truncate_prompt_text(value, max_chars=max_string_chars)

    if isinstance(value, Mapping):
        items = list(value.items())
        compact: dict[str, Any] = {}
        for key, item in items[:max_dict_items]:
            compact[str(key)] = _compact_prompt_value(
                item,
                max_depth=max_depth - 1,
                max_string_chars=max_string_chars,
                max_list_items=max_list_items,
                max_dict_items=max_dict_items,
            )
        if len(items) > max_dict_items:
            compact["__truncated_keys__"] = len(items) - max_dict_items
        return compact

    if isinstance(value, (list, tuple)):
        seq = list(value)
        if len(seq) <= max_list_items:
            return [
                _compact_prompt_value(
                    item,
                    max_depth=max_depth - 1,
                    max_string_chars=max_string_chars,
                    max_list_items=max_list_items,
                    max_dict_items=max_dict_items,
                )
                for item in seq
            ]
        head_count = max(1, max_list_items // 2)
        tail_count = max(1, max_list_items - head_count)
        head = seq[:head_count]
        tail = seq[-tail_count:]
        compact_list = [
            _compact_prompt_value(
                item,
                max_depth=max_depth - 1,
                max_string_chars=max_string_chars,
                max_list_items=max_list_items,
                max_dict_items=max_dict_items,
            )
            for item in head
        ]
        compact_list.append({"__truncated_items__": len(seq) - len(head) - len(tail)})
        compact_list.extend(
            _compact_prompt_value(
                item,
                max_depth=max_depth - 1,
                max_string_chars=max_string_chars,
                max_list_items=max_list_items,
                max_dict_items=max_dict_items,
            )
            for item in tail
        )
        return compact_list

    return value


def _prepare_prompt_json(payload: Mapping[str, Any], *, secret_names: Sequence[str]) -> str:
    """Serialize evidence for prompts within a fixed character budget."""
    import json as _json

    redacted = redact_payload(payload, secret_names=list(secret_names))
    serialized = _json.dumps(redacted, indent=2, default=str, ensure_ascii=False)
    if len(serialized) <= _PROMPT_EVIDENCE_CHAR_BUDGET:
        return serialized

    compact = _compact_prompt_value(
        redacted,
        max_depth=_PROMPT_MAX_DEPTH,
        max_string_chars=_PROMPT_MAX_STRING_CHARS,
        max_list_items=_PROMPT_MAX_LIST_ITEMS,
        max_dict_items=_PROMPT_MAX_DICT_ITEMS,
    )
    serialized = _json.dumps(compact, indent=2, default=str, ensure_ascii=False)
    if len(serialized) <= _PROMPT_EVIDENCE_CHAR_BUDGET:
        return serialized

    emergency = {
        "prompt_truncated": True,
        "available_top_level_keys": sorted(str(key) for key in redacted.keys()),
        "session": redacted.get("session", ""),
        "repair_data_path": redacted.get("repair_data_path", ""),
        "attempt_dir": redacted.get("attempt_dir", ""),
        "index_path": redacted.get("index_path", ""),
        "repair_data": _compact_prompt_value(
            redacted.get("repair_data", {}),
            max_depth=4,
            max_string_chars=800,
            max_list_items=6,
            max_dict_items=24,
        ),
        "recent_attempt_count": len(redacted.get("recent_attempts", []) or []),
        "partial_liveness_count": len(redacted.get("partial_liveness_history", []) or []),
    }
    return _json.dumps(emergency, indent=2, default=str, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def build_meta_repair_prompt(
    classification: MetaRepairClassification,
    *,
    repair_data_dir: str | Path | None = None,
    extra_context: Mapping[str, Any] | None = None,
    secret_names: Sequence[str] = (),
    force_emergency: bool = False,
) -> str:
    """Build a redacted meta-repair prompt for Codex/DeepSeek diagnosis.

    The prompt includes the classification trigger, rationale, redacted
    evidence, and structured instructions for the meta-repair agent.

    All string evidence is redacted via :func:`redact_text` before
    inclusion in the prompt.

    Args:
        classification: The classification result from
            :func:`classify_repair_system_failure`.
        repair_data_dir: Optional repair-data directory for context.
        extra_context: Optional additional context to include.
        secret_names: Secret names for redaction.

    Returns:
        A redacted prompt string suitable for sending to Codex/DeepSeek.
    """
    def _assemble_prompt(
        evidence_json: str | None,
        context_json: str | None,
        *,
        emergency_mode: bool,
    ) -> str:
        parts: list[str] = []

        parts.append("## Meta-Repair Diagnosis Prompt\n")

        trigger_label = classification.trigger_label
        if classification.should_dispatch:
            parts.append(f"**Trigger:** `{trigger_label}`\n")
        else:
            parts.append(f"**Status:** Non-trigger (`{trigger_label}`)\n")

        parts.append(f"**Session:** `{classification.session}`\n")
        if repair_data_dir:
            parts.append(f"**Repair Data Directory:** `{repair_data_dir}`\n")
        parts.append("\n")

        if classification.rationale:
            parts.append("### Rationale\n")
            for line in classification.rationale:
                parts.append(
                    f"- {redact_text(str(line), secret_names=list(secret_names))}\n"
                )
            parts.append("\n")

        if evidence_json is not None:
            parts.append("### Redacted Evidence\n")
            if emergency_mode:
                parts.append(
                    "_Evidence was compacted to stay under Codex input limits._\n\n"
                )
            parts.append("```json\n")
            parts.append(evidence_json)
            parts.append("\n```\n\n")

        if context_json is not None:
            parts.append("### Additional Context\n")
            parts.append("```json\n")
            parts.append(context_json)
            parts.append("\n```\n\n")

        parts.append("### Instructions\n")
        parts.append(
            "Diagnose the root cause of the repair-system failure described above. "
            "Focus on:\n"
            "1. What part of the repair system is broken?\n"
            "2. What evidence supports this diagnosis?\n"
            "3. What concrete change(s) would fix the system?\n"
            "4. What tests should verify the fix?\n\n"
            "Do NOT expose secrets, tokens, or credentials. "
            "All sensitive values in the evidence have been redacted.\n"
        )
        return "".join(parts)

    evidence_json: str | None = None
    if classification.evidence:
        if force_emergency:
            evidence_json = _prepare_emergency_prompt_json(
                classification.evidence,
                secret_names=secret_names,
            )
        else:
            evidence_json = _prepare_prompt_json(
                classification.evidence,
                secret_names=secret_names,
            )
    context_json = (
        _prepare_prompt_json(dict(extra_context), secret_names=secret_names)
        if extra_context
        else None
    )

    prompt = _assemble_prompt(
        evidence_json,
        context_json,
        emergency_mode=force_emergency,
    )
    if len(prompt) <= _PROMPT_TOTAL_CHAR_BUDGET:
        return prompt

    prompt = _assemble_prompt(
        _prepare_emergency_prompt_json(
            classification.evidence,
            secret_names=secret_names,
        )
        if classification.evidence
        else None,
        context_json,
        emergency_mode=True,
    )
    if len(prompt) <= _PROMPT_TOTAL_CHAR_BUDGET:
        return prompt

    return _truncate_prompt_text(prompt, max_chars=_PROMPT_TOTAL_CHAR_BUDGET)


# ---------------------------------------------------------------------------
# Meta-repair record and persistence
# ---------------------------------------------------------------------------


@dataclass
class MetaRepairRecord:
    """Persistable record of a meta-repair execution.

    Captures diagnosis, subagent results, changes, tests, the redacted
    retrigger command, post-retrigger verification, and the final outcome.
    """

    meta_repair_id: str
    session: str
    trigger: MetaRepairTrigger | None
    diagnosis: str = ""
    subagent_results: dict[str, Any] = field(default_factory=dict)
    changes: list[dict[str, Any]] = field(default_factory=list)
    tests: list[dict[str, Any]] = field(default_factory=list)
    retrigger_command: str = ""  # redacted before persistence
    post_retrigger_verification: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            object.__setattr__(
                self, "created_at", datetime.now(timezone.utc).isoformat()
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict suitable for JSON persistence."""
        return {
            "meta_repair_id": self.meta_repair_id,
            "session": self.session,
            "trigger": self.trigger.value if self.trigger is not None else None,
            "diagnosis": self.diagnosis,
            "subagent_results": self.subagent_results,
            "changes": self.changes,
            "tests": self.tests,
            "retrigger_command": self.retrigger_command,
            "post_retrigger_verification": self.post_retrigger_verification,
            "outcome": self.outcome,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MetaRepairRecord:
        """Deserialize from a plain dict."""
        trigger_raw = data.get("trigger")
        trigger: MetaRepairTrigger | None = None
        if trigger_raw is not None:
            try:
                trigger = MetaRepairTrigger(trigger_raw)
            except ValueError:
                pass
        return cls(
            meta_repair_id=str(data.get("meta_repair_id", "")),
            session=str(data.get("session", "")),
            trigger=trigger,
            diagnosis=str(data.get("diagnosis", "")),
            subagent_results=dict(data.get("subagent_results", {})),
            changes=list(data.get("changes", [])),
            tests=list(data.get("tests", [])),
            retrigger_command=str(data.get("retrigger_command", "")),
            post_retrigger_verification=dict(
                data.get("post_retrigger_verification", {})
            ),
            outcome=str(data.get("outcome", "")),
            created_at=str(data.get("created_at", "")),
        )


def persist_meta_repair_record(
    record: MetaRepairRecord,
    *,
    repair_data_dir: str | Path,
    secret_names: Sequence[str] = (),
) -> Path:
    """Persist a meta-repair record to ``repair-data/meta/<meta_repair_id>.json``.

    The retrigger command in the persisted payload is redacted via
    :func:`redact_text` before writing.  The parent ``meta/`` directory
    is created if it does not exist.

    Returns:
        The path to the written JSON file.
    """
    repair_root = Path(repair_data_dir)
    meta_dir = repair_root / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    payload = record.to_dict()

    # Redact the retrigger command in the persisted copy
    if payload["retrigger_command"]:
        payload["retrigger_command"] = redact_text(
            payload["retrigger_command"],
            secret_names=list(secret_names),
        )

    file_path = meta_dir / f"{record.meta_repair_id}.json"
    atomic_write_json(file_path, payload)
    update_session_index(
        repair_root / "index.json",
        record.session,
        {
            "session": record.session,
            "latest_meta_repair_id": record.meta_repair_id,
            "latest_meta_outcome": record.outcome,
            "latest_meta_record_path": str(file_path),
            "latest_meta_recorded_at": record.created_at,
        },
    )
    return file_path


def load_meta_repair_record(
    meta_repair_id: str,
    *,
    repair_data_dir: str | Path,
) -> MetaRepairRecord | None:
    """Load a previously persisted meta-repair record.

    Returns ``None`` when the record file does not exist or cannot be parsed.
    """
    repair_root = Path(repair_data_dir)
    file_path = repair_root / "meta" / f"{meta_repair_id}.json"
    if not file_path.exists():
        return None
    try:
        data = load_json(file_path)
        if not isinstance(data, dict) or not data:
            return None
        return MetaRepairRecord.from_dict(data)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Budget-aware meta-repair helpers
# ---------------------------------------------------------------------------


def compute_meta_deadline(
    start_time: datetime,
    budget_secs: int = META_REPAIR_BUDGET_SECS,
) -> datetime:
    """Return the meta-repair deadline computed with the meta-repair budget."""
    return compute_deadline(start_time, budget_secs)


def remaining_meta_budget_secs(
    deadline: datetime,
    now: datetime | None = None,
) -> float:
    """Return remaining meta-repair budget seconds before *deadline*."""
    return remaining_budget_secs(deadline, now)


def is_meta_budget_exhausted(
    deadline: datetime,
    now: datetime | None = None,
) -> bool:
    """Return ``True`` when the meta-repair budget is exhausted."""
    return is_budget_exhausted(deadline, now)


# ---------------------------------------------------------------------------
# Ordinary repair retrigger verification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetriggerExecutionResult:
    """Result of invoking the ordinary repair loop from meta-repair."""

    command: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    lock_released: bool = False

    @property
    def command_text(self) -> str:
        return " ".join(self.command)


def retrigger_ordinary_repair(
    *,
    command: Sequence[str],
    repair_lock_dir: str | Path | None = None,
    expected_lock_pid: int | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout_secs: float | None = None,
    runner: Callable[..., Any] | None = None,
    release_lock: Callable[..., bool] | None = None,
) -> RetriggerExecutionResult:
    """Release the ordinary repair lock, then invoke the primary repair loop."""
    if not command:
        raise ValueError("command must not be empty")

    effective_release = release_repair_lock if release_lock is None else release_lock
    lock_released = False
    if repair_lock_dir is not None:
        lock_released = bool(
            effective_release(repair_lock_dir, expected_pid=expected_lock_pid)
        )
        if not lock_released:
            raise RuntimeError(
                f"failed to release ordinary repair lock before retrigger: {repair_lock_dir}"
            )

    effective_runner = subprocess.run if runner is None else runner
    completed = effective_runner(
        list(command),
        cwd=None if cwd is None else str(cwd),
        env=None if env is None else dict(env),
        capture_output=True,
        text=True,
        timeout=timeout_secs,
        check=False,
    )
    return RetriggerExecutionResult(
        command=tuple(str(part) for part in command),
        returncode=int(getattr(completed, "returncode", 1)),
        stdout=str(getattr(completed, "stdout", "")),
        stderr=str(getattr(completed, "stderr", "")),
        lock_released=lock_released,
    )


def verify_retrigger_success(
    *,
    retriggered: bool,
    retrigger_result: RetriggerExecutionResult | None = None,
    post_retrigger_verification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify that a retriggered ordinary repair finished with a real success."""
    verification = dict(post_retrigger_verification or {})
    raw_outcome = str(verification.get("outcome", "")).strip().lower()
    normalized_outcome = raw_outcome

    if raw_outcome == "running":
        normalized_outcome = classify_verification_outcome(
            is_complete=bool(verification.get("is_complete")),
            has_progressed=bool(verification.get("has_progressed")),
            has_fresh_activity=bool(verification.get("has_fresh_activity")),
            has_true_human_blocker=bool(verification.get("has_true_human_blocker")),
            is_live=bool(verification.get("is_live")),
            pre_snapshot=verification.get("pre_snapshot"),
            post_snapshot=verification.get("post_snapshot"),
        )

    if not normalized_outcome:
        normalized_outcome = classify_verification_outcome(
            is_complete=bool(verification.get("is_complete")),
            has_progressed=bool(verification.get("has_progressed")),
            has_fresh_activity=bool(verification.get("has_fresh_activity")),
            has_true_human_blocker=bool(verification.get("has_true_human_blocker")),
            is_live=bool(verification.get("is_live")),
            pre_snapshot=verification.get("pre_snapshot"),
            post_snapshot=verification.get("post_snapshot"),
        )

    snapshot_reason = authoritative_terminal_snapshot_reason(
        verification.get("post_snapshot")
    )
    # L2 can hand a genuinely live target back to ordinary supervision.  Only
    # a COMPLETE outcome *closes* custody, and only that terminal claim needs
    # the all-milestones/no-worker authoritative snapshot.
    accepted = (
        retriggered
        and (retrigger_result is None or retrigger_result.returncode == 0)
        and (
            normalized_outcome == LIVE_WITH_FRESH_ACTIVITY
            or (normalized_outcome == COMPLETE and not snapshot_reason)
        )
    )

    rejection_reason = ""
    if not retriggered:
        rejection_reason = "ordinary repair was not retriggered"
    elif retrigger_result is not None and retrigger_result.returncode != 0:
        rejection_reason = (
            "ordinary repair retrigger command failed "
            f"(returncode={retrigger_result.returncode})"
        )
    elif normalized_outcome == COMPLETE and snapshot_reason:
        rejection_reason = snapshot_reason
    elif normalized_outcome == PARTIAL_LIVENESS:
        rejection_reason = "partial_liveness is not a terminal success"
    elif normalized_outcome == REPAIRING:
        rejection_reason = "repairing is not a verified terminal success"
    elif normalized_outcome != COMPLETE:
        rejection_reason = f"outcome {normalized_outcome!r} cannot close repair custody"

    verification_record = build_verification_record(
        normalized_outcome,
        pre_snapshot=verification.get("pre_snapshot"),
        post_snapshot=verification.get("post_snapshot"),
        delta_summary=str(verification.get("delta_summary", "")),
    )
    verification_record.update(
        {
            "raw_outcome": raw_outcome or normalized_outcome,
            "accepted": accepted,
            "retriggered": retriggered,
            "rejection_reason": rejection_reason,
        }
    )
    if raw_outcome == "running":
        verification_record["legacy_running_mapped_to"] = normalized_outcome
    if retrigger_result is not None:
        verification_record["retrigger_command"] = retrigger_result.command_text
        verification_record["retrigger_returncode"] = retrigger_result.returncode
        verification_record["lock_released_before_retrigger"] = (
            retrigger_result.lock_released
        )
    return verification_record


def derive_meta_repair_effective_outcome(
    *,
    verdict: str,
    install_sync_status: str = "",
    post_retrigger_verification: Mapping[str, Any] | None = None,
) -> str:
    """Choose the persisted meta-repair outcome.

    A model verdict of ``FIXED`` is only authoritative after verifier
    acceptance. Rejected verifier results persist as non-success while the
    detailed verdict and rejection evidence stay in
    ``post_retrigger_verification``.
    """

    normalized_verdict = str(verdict or "").strip()
    if not normalized_verdict.startswith("FIXED"):
        return normalized_verdict or "UNKNOWN"

    if str(install_sync_status or "").strip().lower() == "failed":
        return "install_sync_failed"

    verification = dict(post_retrigger_verification or {})
    accepted = bool(verification.get("accepted"))
    outcome = str(verification.get("outcome") or "").strip().lower()

    if accepted:
        return outcome or normalized_verdict
    if outcome and outcome not in _META_REPAIR_ACCEPTED_SUCCESS_OUTCOMES:
        return outcome
    return "verifier_rejected"


# ---------------------------------------------------------------------------
# Convenience: combined load + classify + prompt
# ---------------------------------------------------------------------------


def evaluate_meta_repair_triggers(
    session: str,
    *,
    repair_data_dir: str | Path,
    repair_outcome: str = "",
    attempt_outcomes: Sequence[str] = (),
    failure_kinds: Sequence[str] = (),
    has_state_inspection_error: bool = False,
    has_model_tool_launch_error: bool = False,
    partial_liveness_ticks: int = 0,
    discord_delivery_failed: bool = False,
    discord_escalation_is_true_blocker: bool = False,
    repair_budget_exhausted: bool = False,
    current_target_observation: Mapping[str, Any] | None = None,
    load_evidence: bool = False,
    secret_names: Sequence[str] = (),
    extra_context: Mapping[str, Any] | None = None,
) -> tuple[MetaRepairClassification, str | None]:
    """Evaluate triggers, optionally load evidence, and build a prompt.

    This is the primary entry point for watchdog-meta-repair integration.  It
    classifies the failure, optionally loads redacted evidence, and returns
    both the classification and a redacted prompt when dispatch is indicated.

    Returns:
        A ``(classification, prompt)`` tuple.  *prompt* is ``None`` when
        *classification.should_dispatch* is ``False``.
    """
    evidence: dict[str, Any] | None = None
    if load_evidence:
        evidence = load_redacted_evidence(
            session,
            repair_data_dir=repair_data_dir,
            secret_names=secret_names,
        )

    # Compute partial_liveness_ticks from loaded evidence when available
    # and the caller did not supply an explicit value
    if load_evidence and evidence and not partial_liveness_ticks:
        history = evidence.get("partial_liveness_history", [])
        partial_liveness_ticks = len(history)

    classification = classify_repair_system_failure(
        session,
        evidence=evidence,
        current_target_observation=current_target_observation,
        repair_data_dir=repair_data_dir,
        repair_outcome=repair_outcome,
        attempt_outcomes=attempt_outcomes,
        failure_kinds=failure_kinds,
        has_state_inspection_error=has_state_inspection_error,
        has_model_tool_launch_error=has_model_tool_launch_error,
        partial_liveness_ticks=partial_liveness_ticks,
        discord_delivery_failed=discord_delivery_failed,
        discord_escalation_is_true_blocker=discord_escalation_is_true_blocker,
        repair_budget_exhausted=repair_budget_exhausted,
    )

    if not classification.should_dispatch:
        return classification, None

    prompt = build_meta_repair_prompt(
        classification,
        repair_data_dir=repair_data_dir,
        extra_context=extra_context,
        secret_names=secret_names,
    )
    return classification, prompt


__all__ = [
    "derive_meta_repair_effective_outcome",
    "META_REPAIR_BUDGET_SECS",
    "MetaRepairClassification",
    "MetaRepairRecord",
    "MetaRepairTrigger",
    "RetriggerExecutionResult",
    "build_meta_repair_prompt",
    "classify_repair_system_failure",
    "compute_meta_deadline",
    "evaluate_meta_repair_triggers",
    "is_meta_budget_exhausted",
    "is_model_tool_launch_failure_status",
    "load_meta_repair_record",
    "load_redacted_evidence",
    "persist_meta_repair_record",
    "remaining_meta_budget_secs",
    "retrigger_ordinary_repair",
    "stale_repair_evidence_reason",
    "trigger_priority",
    "verify_retrigger_success",
]
