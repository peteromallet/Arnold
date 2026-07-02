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
                    if isinstance(e, dict) and e.get("outcome") == PARTIAL_LIVENESS
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


def classify_repair_system_failure(
    session: str,
    *,
    evidence: Mapping[str, Any] | None = None,
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


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def build_meta_repair_prompt(
    classification: MetaRepairClassification,
    *,
    repair_data_dir: str | Path | None = None,
    extra_context: Mapping[str, Any] | None = None,
    secret_names: Sequence[str] = (),
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
    import json as _json

    parts: list[str] = []

    # Header
    parts.append("## Meta-Repair Diagnosis Prompt\n")

    trigger_label = classification.trigger_label
    if classification.should_dispatch:
        parts.append(f"**Trigger:** `{trigger_label}`\n")
    else:
        parts.append(f"**Status:** Non-trigger (`{trigger_label}`)\n")

    # Session and context
    parts.append(f"**Session:** `{classification.session}`\n")
    if repair_data_dir:
        parts.append(f"**Repair Data Directory:** `{repair_data_dir}`\n")
    parts.append("\n")

    # Rationale
    if classification.rationale:
        parts.append("### Rationale\n")
        for line in classification.rationale:
            parts.append(f"- {redact_text(str(line), secret_names=list(secret_names))}\n")
        parts.append("\n")

    # Evidence
    if classification.evidence:
        parts.append("### Redacted Evidence\n")
        evidence_redacted = redact_payload(
            classification.evidence,
            secret_names=list(secret_names),
        )
        parts.append("```json\n")
        parts.append(
            _json.dumps(evidence_redacted, indent=2, default=str, ensure_ascii=False)
        )
        parts.append("\n```\n\n")

    # Extra context
    if extra_context:
        parts.append("### Additional Context\n")
        ctx_redacted = redact_payload(
            dict(extra_context),
            secret_names=list(secret_names),
        )
        parts.append("```json\n")
        parts.append(
            _json.dumps(ctx_redacted, indent=2, default=str, ensure_ascii=False)
        )
        parts.append("\n```\n\n")

    # Instructions
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

    accepted = (
        retriggered
        and (retrigger_result is None or retrigger_result.returncode == 0)
        and normalized_outcome in SUCCESS_OUTCOMES
    )

    rejection_reason = ""
    if not retriggered:
        rejection_reason = "ordinary repair was not retriggered"
    elif retrigger_result is not None and retrigger_result.returncode != 0:
        rejection_reason = (
            "ordinary repair retrigger command failed "
            f"(returncode={retrigger_result.returncode})"
        )
    elif normalized_outcome == PARTIAL_LIVENESS:
        rejection_reason = "partial_liveness is not a terminal success"
    elif normalized_outcome == REPAIRING:
        rejection_reason = "repairing is not a verified terminal success"
    elif normalized_outcome not in SUCCESS_OUTCOMES:
        rejection_reason = f"outcome {normalized_outcome!r} is outside SUCCESS_OUTCOMES"

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
    "load_meta_repair_record",
    "load_redacted_evidence",
    "persist_meta_repair_record",
    "remaining_meta_budget_secs",
    "retrigger_ordinary_repair",
    "trigger_priority",
    "verify_retrigger_success",
]
