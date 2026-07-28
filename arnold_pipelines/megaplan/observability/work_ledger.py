"""Full rebuildable append-only work-ledger for M8A executor observability.

This module is explicitly NON-AUTHORITATIVE.  Events are evidence only — they
do not substitute for any grant, lease, WBC, completion, publication, delivery,
or status authority.  The work ledger records *what happened* for later
telemetry reconciliation; it never drives control flow, admission, or repair
decisions.

Event vocabulary (stable — do not rename without a coordinated migration):
- ``validation``        — deterministic harness validation job completed
- ``repair_verify``     — verify-only repair receipt adoption completed
- ``productive``        — productive work (model inference) completed
- ``unavailable_reason`` — a specific telemetry measure is unavailable and why
- ``review_proof``      — review/proof work (code review, quality assessment)
- ``queue``             — queue wait time before worker dispatch
- ``retry_wait``        — wait time between retry attempts (backoff/cooldown)
- ``compaction``        — context compaction time for budget management
- ``replay``            — deterministic replay of captured fixtures
- ``tool``              — tool execution time (shell, file ops, API calls)
- ``git``               — Git operation time (commits, diffs, status)
- ``transition``        — lifecycle state transition time

Every event carries:
- ``event_id``          — stable sha256 hex digest (deterministic from content)
- ``event_class``       — one of the twelve vocabulary entries above
- ``referenced_identity`` — what this event is about (task_id, batch_id, …)
- ``content_hash``      — sha256 of the canonical JSON payload (integrity check)
- ``timestamp``         — UTC ISO‑8601 at append time
- ``payload``           — event‑specific structured data
- ``_non_authoritative`` — always ``true``; lint/audit marker

Reconciliation primitives
--------------------------
:func:`aggregate_by_class` groups and sums ledger events by event class.
:func:`aggregate_by_task` groups events by referenced identity.
:func:`build_work_class_summary` produces a rebuildable aggregate summary
with total durations per class, unavailable measure catalogue, and cost
attribution gaps.  Every summary field that cannot be computed is explicitly
``null`` (UNKNOWN), never defaulted to zero or labelled as success evidence.

Storage
-------
Each plan directory gets one ``work_ledger.ndjson`` file.  Every call to
:func:`append_work_ledger_event` appends exactly one JSON line.  The file is
never truncated and never used for control flow.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

# ═══════════════════════════════════════════════════════════════════════════
# Stable event vocabulary
# ═══════════════════════════════════════════════════════════════════════════

WORK_LEDGER_EVENT_CLASSES: FrozenSet[str] = frozenset(
    {
        "validation",
        "repair_verify",
        "productive",
        "unavailable_reason",
        "review_proof",
        "queue",
        "retry_wait",
        "compaction",
        "replay",
        "tool",
        "git",
        "transition",
    }
)

# ── Per‑event‑class required payload keys ──────────────────────────────────

_VALIDATION_REQUIRED = frozenset({"task_id", "job_id", "command", "exit_code", "duration_ms"})
_REPAIR_VERIFY_REQUIRED = frozenset({"task_id", "receipt_hash", "outcome", "duration_ms"})
_PRODUCTIVE_REQUIRED = frozenset({"task_id", "work_class", "duration_ms"})
_UNAVAILABLE_REASON_REQUIRED = frozenset({"task_id", "measure", "reason"})
_REVIEW_PROOF_REQUIRED = frozenset({"task_id", "review_kind", "duration_ms"})
_QUEUE_REQUIRED = frozenset({"task_id", "duration_ms"})
_RETRY_WAIT_REQUIRED = frozenset({"task_id", "duration_ms", "attempt_number"})
_COMPACTION_REQUIRED = frozenset({"task_id", "duration_ms"})
_REPLAY_REQUIRED = frozenset({"task_id", "duration_ms"})
_TOOL_REQUIRED = frozenset({"task_id", "tool_name", "duration_ms"})
_GIT_REQUIRED = frozenset({"task_id", "operation", "duration_ms"})
_TRANSITION_REQUIRED = frozenset({"task_id", "from_state", "to_state", "duration_ms"})

_REQUIRED_BY_CLASS: Dict[str, FrozenSet[str]] = {
    "validation": _VALIDATION_REQUIRED,
    "repair_verify": _REPAIR_VERIFY_REQUIRED,
    "productive": _PRODUCTIVE_REQUIRED,
    "unavailable_reason": _UNAVAILABLE_REASON_REQUIRED,
    "review_proof": _REVIEW_PROOF_REQUIRED,
    "queue": _QUEUE_REQUIRED,
    "retry_wait": _RETRY_WAIT_REQUIRED,
    "compaction": _COMPACTION_REQUIRED,
    "replay": _REPLAY_REQUIRED,
    "tool": _TOOL_REQUIRED,
    "git": _GIT_REQUIRED,
    "transition": _TRANSITION_REQUIRED,
}

# ── Work‑class category mapping (for aggregation) ───────────────────────────

# Legitimate value-producing work — never waste.
_VALUE_WORK_CLASSES: FrozenSet[str] = frozenset({
    "productive",
    "replay",
    "tool",
    "validation",
    "repair_verify",
    "review_proof",  # code review, quality check, proof generation are all legitimate
})

# Non-value work (retry, queue, compaction, git, transition overhead).
_NON_VALUE_WORK_CLASSES: FrozenSet[str] = frozenset({
    "retry_wait",
    "queue",
    "compaction",
    "git",
    "transition",
})

# Gap — telemetry that is explicitly unavailable (not waste, just missing data).
_GAP_CLASSES: FrozenSet[str] = frozenset({
    "unavailable_reason",
})

# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

_WORK_LEDGER_FILE = "work_ledger.ndjson"


def _ledger_path(plan_dir: Path) -> Path:
    return Path(plan_dir) / _WORK_LEDGER_FILE


def _canonical_json_bytes(payload: Dict[str, Any]) -> bytes:
    """Deterministic JSON serialisation used for both event- and content-hash."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")


def _content_hash(payload: Dict[str, Any]) -> str:
    """sha256 of the canonical JSON payload (integrity verification)."""
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _stable_event_id(
    event_class: str,
    referenced_identity: str,
    payload_bytes: bytes,
) -> str:
    """Content‑addressed event id — same inputs ⇒ same id (deterministic)."""
    raw = f"{event_class}\x00{referenced_identity}\x00"
    return hashlib.sha256(raw.encode("utf-8") + payload_bytes).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════


def append_work_ledger_event(
    plan_dir: Path,
    *,
    event_class: str,
    referenced_identity: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Append one non‑authoritative work‑ledger event.

    Args:
        plan_dir: Plan directory (ledger file written as ``work_ledger.ndjson``).
        event_class: One of ``validation``, ``repair_verify``, ``productive``,
                     ``unavailable_reason``.
        referenced_identity: What this event is about (``task_id``, ``batch_id``, …).
        payload: Event‑specific structured data.  Required keys depend on
                 ``event_class`` (see event‑class docstrings).

    Returns:
        The full event dict (evidence only; never authority).

    Raises:
        ValueError: If *event_class* is unknown or required payload keys are missing.
    """
    if event_class not in WORK_LEDGER_EVENT_CLASSES:
        raise ValueError(
            f"Unknown work-ledger event class: {event_class!r}. "
            f"Must be one of: {', '.join(sorted(WORK_LEDGER_EVENT_CLASSES))}"
        )

    # Fail loudly when a required key is missing — the vocabulary is the
    # contract and callers must satisfy it.
    required = _REQUIRED_BY_CLASS[event_class]
    missing = required - payload.keys()
    if missing:
        raise ValueError(
            f"work-ledger event_class={event_class!r} missing required payload "
            f"keys: {sorted(missing)}"
        )

    timestamp = datetime.now(timezone.utc).isoformat()
    payload_bytes = _canonical_json_bytes(payload)
    content_hash = _content_hash(payload)
    event_id = _stable_event_id(event_class, referenced_identity, payload_bytes)

    event: Dict[str, Any] = {
        "event_id": event_id,
        "event_class": event_class,
        "referenced_identity": referenced_identity,
        "content_hash": content_hash,
        "timestamp": timestamp,
        "payload": payload,
        "_non_authoritative": True,
    }

    # Append‑only write — no locking needed for the minimal vocabulary
    # because this file is evidence‑only and concurrent write interleaving
    # is acceptable (each line is self‑contained JSON).
    path = _ledger_path(plan_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    return event


def read_work_ledger(plan_dir: Path) -> List[Dict[str, Any]]:
    """Read all work‑ledger events (read‑only, non‑authoritative)."""
    path = _ledger_path(plan_dir)
    if not path.exists():
        return []
    events: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


# ═══════════════════════════════════════════════════════════════════════════
# Convenience emitters (one per event class)
# ═══════════════════════════════════════════════════════════════════════════


def emit_validation(
    plan_dir: Path,
    *,
    task_id: str,
    job_id: str,
    command: str,
    exit_code: int,
    duration_ms: int,
    evidence_hash: str = "",
    **extra: Any,
) -> Dict[str, Any]:
    """Emit a ``validation`` work‑ledger event.

    Records the outcome of a deterministic harness validation job — no model
    call was consumed.  The *evidence_hash* should be the content hash of the
    validation output artifact.
    """
    payload: Dict[str, Any] = {
        "task_id": task_id,
        "job_id": job_id,
        "command": command,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "evidence_hash": evidence_hash,
    }
    payload.update(extra)
    return append_work_ledger_event(
        plan_dir,
        event_class="validation",
        referenced_identity=task_id,
        payload=payload,
    )


def emit_repair_verify(
    plan_dir: Path,
    *,
    task_id: str,
    receipt_hash: str,
    outcome: str,
    duration_ms: int,
    grant_match: bool = True,
    fence_match: bool = True,
    **extra: Any,
) -> Dict[str, Any]:
    """Emit a ``repair_verify`` work‑ledger event.

    Records verify‑only repair receipt adoption.  *grant_match* and
    *fence_match* indicate whether the current Run Authority grant / fence
    matched the receipt's expectations.  Mismatch quarantines the receipt
    without adopting it.
    """
    payload: Dict[str, Any] = {
        "task_id": task_id,
        "receipt_hash": receipt_hash,
        "outcome": outcome,
        "duration_ms": duration_ms,
        "grant_match": grant_match,
        "fence_match": fence_match,
    }
    payload.update(extra)
    return append_work_ledger_event(
        plan_dir,
        event_class="repair_verify",
        referenced_identity=task_id,
        payload=payload,
    )


def emit_productive(
    plan_dir: Path,
    *,
    task_id: str,
    work_class: str,
    duration_ms: int,
    tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
    model_calls: Optional[int] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Emit a ``productive`` work‑ledger event.

    Records productive implementation work (model inference, tool execution,
    or other value‑generating activity).  Optional *tokens*, *cost_usd*, and
    *model_calls* provide per‑event cost attribution.
    """
    payload: Dict[str, Any] = {
        "task_id": task_id,
        "work_class": work_class,
        "duration_ms": duration_ms,
    }
    if tokens is not None:
        payload["tokens"] = tokens
    if cost_usd is not None:
        payload["cost_usd"] = cost_usd
    if model_calls is not None:
        payload["model_calls"] = model_calls
    payload.update(extra)
    return append_work_ledger_event(
        plan_dir,
        event_class="productive",
        referenced_identity=task_id,
        payload=payload,
    )


def emit_unavailable_reason(
    plan_dir: Path,
    *,
    task_id: str,
    measure: str,
    reason: str,
    **extra: Any,
) -> Dict[str, Any]:
    """Emit an ``unavailable_reason`` work‑ledger event.

    Records *why* a specific telemetry measure is unavailable.  The absence
    is explicit — never defaulted to zero or labelled as success evidence.

    Example *measure* values: ``"tokens"``, ``"cost_usd"``, ``"duration_ms"``,
    ``"model_calls"``.
    """
    payload: Dict[str, Any] = {
        "task_id": task_id,
        "measure": measure,
        "reason": reason,
    }
    payload.update(extra)
    return append_work_ledger_event(
        plan_dir,
        event_class="unavailable_reason",
        referenced_identity=task_id,
        payload=payload,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Extended event‑class emitters (review_proof, queue, retry_wait, compaction,
# replay, tool, git, transition)
# ═══════════════════════════════════════════════════════════════════════════


def emit_review_proof(
    plan_dir: Path,
    *,
    task_id: str,
    review_kind: str,
    duration_ms: int,
    verdict: str = "",
    reviewer_id: str = "",
    **extra: Any,
) -> Dict[str, Any]:
    """Emit a ``review_proof`` work‑ledger event.

    Records time spent on review/proof work — code review, quality
    assessment, or proof generation.  *review_kind* should be one of
    ``"code_review"``, ``"quality_check"``, or ``"proof_generation"``.
    """
    payload: Dict[str, Any] = {
        "task_id": task_id,
        "review_kind": review_kind,
        "duration_ms": duration_ms,
    }
    if verdict:
        payload["verdict"] = verdict
    if reviewer_id:
        payload["reviewer_id"] = reviewer_id
    payload.update(extra)
    return append_work_ledger_event(
        plan_dir,
        event_class="review_proof",
        referenced_identity=task_id,
        payload=payload,
    )


def emit_queue(
    plan_dir: Path,
    *,
    task_id: str,
    duration_ms: int,
    queue_reason: str = "",
    **extra: Any,
) -> Dict[str, Any]:
    """Emit a ``queue`` work‑ledger event.

    Records time spent waiting for a worker slot after admission.
    *queue_reason* describes why the task was queued (e.g. ``"slot_wait"``,
    ``"worker_unavailable"``, ``"scheduling"``).
    """
    payload: Dict[str, Any] = {
        "task_id": task_id,
        "duration_ms": duration_ms,
    }
    if queue_reason:
        payload["queue_reason"] = queue_reason
    payload.update(extra)
    return append_work_ledger_event(
        plan_dir,
        event_class="queue",
        referenced_identity=task_id,
        payload=payload,
    )


def emit_retry_wait(
    plan_dir: Path,
    *,
    task_id: str,
    duration_ms: int,
    attempt_number: int,
    wait_reason: str = "",
    **extra: Any,
) -> Dict[str, Any]:
    """Emit a ``retry_wait`` work‑ledger event.

    Records time spent waiting between retry attempts (backoff, provider
    cooldown, circuit delay).  *attempt_number* is the retry attempt that
    was waiting (1‑indexed).
    """
    payload: Dict[str, Any] = {
        "task_id": task_id,
        "duration_ms": duration_ms,
        "attempt_number": attempt_number,
    }
    if wait_reason:
        payload["wait_reason"] = wait_reason
    payload.update(extra)
    return append_work_ledger_event(
        plan_dir,
        event_class="retry_wait",
        referenced_identity=task_id,
        payload=payload,
    )


def emit_compaction(
    plan_dir: Path,
    *,
    task_id: str,
    duration_ms: int,
    compacted_tokens: Optional[int] = None,
    strategy: str = "",
    **extra: Any,
) -> Dict[str, Any]:
    """Emit a ``compaction`` work‑ledger event.

    Records time spent compacting conversation context for budget
    management.  *compacted_tokens* is the number of tokens removed;
    *strategy* describes the compaction method (e.g. ``"summary"``,
    ``"truncation"``).
    """
    payload: Dict[str, Any] = {
        "task_id": task_id,
        "duration_ms": duration_ms,
    }
    if compacted_tokens is not None:
        payload["compacted_tokens"] = compacted_tokens
    if strategy:
        payload["strategy"] = strategy
    payload.update(extra)
    return append_work_ledger_event(
        plan_dir,
        event_class="compaction",
        referenced_identity=task_id,
        payload=payload,
    )


def emit_replay(
    plan_dir: Path,
    *,
    task_id: str,
    duration_ms: int,
    fixture_path: str = "",
    exit_code: Optional[int] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Emit a ``replay`` work‑ledger event.

    Records time spent on deterministic replay of captured fixtures for
    proof generation.  *fixture_path* identifies the replayed fixture;
    *exit_code* is the replay subprocess exit code.
    """
    payload: Dict[str, Any] = {
        "task_id": task_id,
        "duration_ms": duration_ms,
    }
    if fixture_path:
        payload["fixture_path"] = fixture_path
    if exit_code is not None:
        payload["exit_code"] = exit_code
    payload.update(extra)
    return append_work_ledger_event(
        plan_dir,
        event_class="replay",
        referenced_identity=task_id,
        payload=payload,
    )


def emit_tool(
    plan_dir: Path,
    *,
    task_id: str,
    tool_name: str,
    duration_ms: int,
    exit_code: Optional[int] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Emit a ``tool`` work‑ledger event.

    Records time spent executing tool calls (shell, file operations,
    API calls).  *tool_name* identifies the tool (e.g. ``"terminal"``,
    ``"read_file"``, ``"search_files"``).
    """
    payload: Dict[str, Any] = {
        "task_id": task_id,
        "tool_name": tool_name,
        "duration_ms": duration_ms,
    }
    if exit_code is not None:
        payload["exit_code"] = exit_code
    payload.update(extra)
    return append_work_ledger_event(
        plan_dir,
        event_class="tool",
        referenced_identity=task_id,
        payload=payload,
    )


def emit_git(
    plan_dir: Path,
    *,
    task_id: str,
    operation: str,
    duration_ms: int,
    exit_code: Optional[int] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Emit a ``git`` work‑ledger event.

    Records time spent on Git operations (commits, diffs, status checks).
    *operation* identifies the Git command (e.g. ``"commit"``, ``"diff"``,
    ``"status"``, ``"checkout"``).
    """
    payload: Dict[str, Any] = {
        "task_id": task_id,
        "operation": operation,
        "duration_ms": duration_ms,
    }
    if exit_code is not None:
        payload["exit_code"] = exit_code
    payload.update(extra)
    return append_work_ledger_event(
        plan_dir,
        event_class="git",
        referenced_identity=task_id,
        payload=payload,
    )


def emit_transition(
    plan_dir: Path,
    *,
    task_id: str,
    from_state: str,
    to_state: str,
    duration_ms: int,
    **extra: Any,
) -> Dict[str, Any]:
    """Emit a ``transition`` work‑ledger event.

    Records time spent on lifecycle state transitions (plan/chain/task
    phase changes).  *from_state* and *to_state* capture the transition
    endpoints.
    """
    payload: Dict[str, Any] = {
        "task_id": task_id,
        "from_state": from_state,
        "to_state": to_state,
        "duration_ms": duration_ms,
    }
    payload.update(extra)
    return append_work_ledger_event(
        plan_dir,
        event_class="transition",
        referenced_identity=task_id,
        payload=payload,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Reconciliation primitives — rebuildable aggregation from ledger events
# ═══════════════════════════════════════════════════════════════════════════
# These functions read the ledger and produce aggregate summaries.  Every
# measure that cannot be computed is explicitly ``null`` (UNKNOWN), never
# defaulted to zero or labelled as success evidence.


def _safe_sum_duration_ms(events: List[Dict[str, Any]]) -> Optional[int]:
    """Sum ``duration_ms`` across events, returning None if no event has it."""
    total = 0
    found = False
    for e in events:
        d = e.get("payload", {}).get("duration_ms")
        if isinstance(d, (int, float)):
            total += int(d)
            found = True
    return total if found else None


def aggregate_by_class(
    plan_dir: Path,
) -> Dict[str, Dict[str, Any]]:
    """Group ledger events by event class with aggregated statistics.

    Returns a dict mapping each event class to:
    - ``count``: number of events
    - ``total_duration_ms``: summed duration (null when unavailable)
    - ``task_ids``: deduplicated set of referenced identities
    - ``category``: ``"productive"`` or ``"overhead"``

    This is a rebuildable function — same ledger → same output (deterministic
    aside from timestamp-dependent fields, which are excluded from the
    aggregate).
    """
    events = read_work_ledger(plan_dir)
    by_class: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in events:
        by_class[e["event_class"]].append(e)

    result: Dict[str, Dict[str, Any]] = {}
    for cls in sorted(WORK_LEDGER_EVENT_CLASSES):
        group = by_class.get(cls, [])
        task_ids = sorted({e["referenced_identity"] for e in group})
        total_duration = _safe_sum_duration_ms(group)
        category = (
            "value_work" if cls in _VALUE_WORK_CLASSES
            else "non_value_work" if cls in _NON_VALUE_WORK_CLASSES
            else "gap" if cls in _GAP_CLASSES
            else "other"
        )
        result[cls] = {
            "count": len(group),
            "total_duration_ms": total_duration,
            "task_ids": task_ids,
            "category": category,
        }
    return result


def aggregate_by_task(
    plan_dir: Path,
) -> Dict[str, Dict[str, Any]]:
    """Group ledger events by referenced identity with per‑class breakdown.

    Returns a dict mapping each referenced identity to:
    - ``event_classes``: dict of event_class → count
    - ``total_duration_ms``: summed duration (null when unavailable)
    - ``unavailable_measures``: list of (measure, reason) pairs

    This is a rebuildable function — same ledger → same output.
    """
    events = read_work_ledger(plan_dir)
    by_task: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in events:
        by_task[e["referenced_identity"]].append(e)

    result: Dict[str, Dict[str, Any]] = {}
    for task_id in sorted(by_task):
        group = by_task[task_id]
        class_counts: Dict[str, int] = defaultdict(int)
        unavailable: List[Tuple[str, str]] = []
        for e in group:
            class_counts[e["event_class"]] += 1
            if e["event_class"] == "unavailable_reason":
                m = e.get("payload", {}).get("measure", "")
                r = e.get("payload", {}).get("reason", "")
                unavailable.append((m, r))

        total_duration = _safe_sum_duration_ms(group)
        result[task_id] = {
            "event_classes": dict(sorted(class_counts.items())),
            "total_duration_ms": total_duration,
            "unavailable_measures": unavailable,
        }
    return result


def reconcile_unavailable_measures(
    plan_dir: Path,
) -> List[Dict[str, str]]:
    """Return every unavailable measure with its reason from the ledger.

    Each entry: ``{"task_id": …, "measure": …, "reason": …}``.
    The absence of a measure is explicit; missing cost/tokens/calls are
    never defaulted to zero.
    """
    events = read_work_ledger(plan_dir)
    result: List[Dict[str, str]] = []
    for e in events:
        if e["event_class"] != "unavailable_reason":
            continue
        result.append({
            "task_id": e["referenced_identity"],
            "measure": e.get("payload", {}).get("measure", ""),
            "reason": e.get("payload", {}).get("reason", ""),
        })
    return result


# ── M9: Fine-grained projection categories ──────────────────────────────────


# Base category mapping (static — event classes that map without inspection).
_CATEGORY_MAP: Dict[str, str] = {
    "productive": "productive",
    "replay": "replayed",
    "validation": "validation_only",
    "repair_verify": "repair_verify",
    "retry_wait": "retry_rework",
    "compaction": "queue_compaction",
    "git": "git",
    "transition": "transition",
    "unavailable_reason": "unavailable",
    "tool": "legitimate_implementation",
    "queue": "queue_compaction",
    # review_proof is resolved dynamically based on review_kind
}


def _resolve_category(event: Dict[str, Any]) -> str:
    """Resolve the M9 projection category for a single ledger event.

    Most event classes map statically via ``_CATEGORY_MAP``.
    ``review_proof`` events are split dynamically based on
    ``review_kind`` to distinguish review from proof work.
    """
    cls = event["event_class"]

    if cls == "review_proof":
        review_kind = event.get("payload", {}).get("review_kind", "")
        if review_kind == "proof_generation":
            return "proof"
        # code_review, quality_check, or unknown → review
        return "review"

    return _CATEGORY_MAP.get(cls, cls)


# All M9 projection categories (deterministic sorted order for rebuild stability).
_PROJECTION_CATEGORIES: FrozenSet[str] = frozenset({
    "productive",
    "replayed",
    "retry_rework",
    "queue_compaction",
    "validation_only",
    "unavailable",
    "legitimate_implementation",
    "review",
    "proof",
})

# Categories that represent legitimate value-producing work.
_VALUE_CATEGORIES: FrozenSet[str] = frozenset({
    "productive",
    "replayed",
    "validation_only",
    "repair_verify",
    "legitimate_implementation",
    "review",
    "proof",
})

# Categories that represent non-value overhead.
_NON_VALUE_CATEGORIES: FrozenSet[str] = frozenset({
    "retry_rework",
    "queue_compaction",
    "git",
    "transition",
})


def aggregate_by_category(
    plan_dir: Path,
) -> Dict[str, Dict[str, Any]]:
    """Group ledger events by M9 projection category with exact identity joins.

    Maps the 12 event classes into 9 projection categories:
    productive, replayed, retry_rework, queue_compaction, validation_only,
    unavailable, legitimate_implementation, review, proof.

    ``review_proof`` events are split dynamically:
    - ``code_review`` / ``quality_check`` → ``review``
    - ``proof_generation`` → ``proof``

    Each category entry carries:
    - ``count``: total events in this category
    - ``total_duration_ms``: summed duration (null when unavailable)
    - ``event_ids``: exact event IDs contributing to this category
    - ``task_ids``: deduplicated referenced identities
    - ``source_classes``: which event classes feed this category
    - ``classification``: ``value_work``, ``non_value_work``, or ``gap``
    - ``_non_authoritative``: always True

    This is a rebuildable function — same ledger → same output.
    """
    events = read_work_ledger(plan_dir)
    by_category: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in events:
        cat = _resolve_category(e)
        by_category[cat].append(e)

    result: Dict[str, Dict[str, Any]] = {}
    for cat in sorted(_PROJECTION_CATEGORIES):
        group = by_category.get(cat, [])
        event_ids = sorted({e["event_id"] for e in group})
        task_ids = sorted({e["referenced_identity"] for e in group})
        source_classes = sorted({e["event_class"] for e in group})
        total_duration = _safe_sum_duration_ms(group)
        classification = (
            "value_work" if cat in _VALUE_CATEGORIES
            else "non_value_work" if cat in _NON_VALUE_CATEGORIES
            else "gap"
        )
        result[cat] = {
            "count": len(group),
            "total_duration_ms": total_duration,
            "event_ids": event_ids,
            "task_ids": task_ids,
            "source_classes": source_classes,
            "classification": classification,
            "_non_authoritative": True,
        }
    return result


def build_category_identity_joins(
    plan_dir: Path,
) -> Dict[str, Dict[str, Any]]:
    """Expose exact identity joins per category: which event IDs belong where.

    Returns a dict mapping each category to:
    - ``event_ids``: exact event IDs in this category
    - ``event_id_count``: cardinality
    - ``by_class``: event IDs grouped by source event class
    - ``unavailable_denominator``: (unavailable_count, total_event_count)
      indicating what fraction of category-relevant events lack telemetry

    The unavailable denominator is computed per category: for each category,
    ``unavailable_count`` is the number of ``unavailable_reason`` events that
    reference tasks appearing in that category.  It is never defaulted to
    zero when no unavailable events exist — it is simply zero for categories
    with no unavailable evidence.
    """
    events = read_work_ledger(plan_dir)
    by_category: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    unavailable_events: List[Dict[str, Any]] = []
    for e in events:
        if e["event_class"] == "unavailable_reason":
            unavailable_events.append(e)
        cat = _resolve_category(e)
        by_category[cat].append(e)

    # Build task_id → category mapping for unavailable denominator
    task_categories: Dict[str, set] = defaultdict(set)
    for cat, group in by_category.items():
        if cat == "unavailable":
            continue
        for e in group:
            task_categories[e["referenced_identity"]].add(cat)

    total_events = len(events)
    result: Dict[str, Dict[str, Any]] = {}
    for cat in sorted(_PROJECTION_CATEGORIES):
        group = by_category.get(cat, [])
        event_ids = sorted({e["event_id"] for e in group})

        # Group by source class
        by_class: Dict[str, List[str]] = defaultdict(list)
        for e in group:
            by_class[e["event_class"]].append(e["event_id"])

        # Unavailable denominator: for non-unavailable categories,
        # count how many unavailable_reason events reference tasks in this category
        unavailable_count = 0
        if cat != "unavailable":
            cat_task_ids = {e["referenced_identity"] for e in group}
            for ue in unavailable_events:
                if ue["referenced_identity"] in cat_task_ids:
                    unavailable_count += 1

        classification = (
            "value_work" if cat in _VALUE_CATEGORIES
            else "non_value_work" if cat in _NON_VALUE_CATEGORIES
            else "gap"
        )

        result[cat] = {
            "event_ids": event_ids,
            "event_id_count": len(event_ids),
            "by_class": {cls: sorted(ids) for cls, ids in sorted(by_class.items())},
            "unavailable_denominator": {
                "unavailable_count": unavailable_count,
                "category_event_count": len(group),
                "total_event_count": total_events,
            },
            "classification": classification,
            "_non_authoritative": True,
        }
    return result


def serialize_work_ledger_summary(
    plan_dir: Path,
    *,
    indent: Optional[int] = None,
) -> str:
    """Serialize the full work-ledger summary to deterministic JSON.

    This is a consumer-facing serializer that produces a deterministic,
    rebuildable JSON representation of the work ledger.  The output
    includes category breakdown, identity joins, per-task aggregation,
    and totals with explicit classification so consumers can distinguish:

    - ``productive`` — model inference work
    - ``replayed`` — deterministic fixture replay
    - ``retry_rework`` — retry wait and rework overhead
    - ``queue_compaction`` — queue latency and context compaction
    - ``validation_only`` — harness validation (not review)
    - ``unavailable`` — telemetry gaps (not waste)
    - ``legitimate_implementation`` — tool execution (not waste)
    - ``review`` — code review and quality check (required, not waste)
    - ``proof`` — proof generation work

    Args:
        plan_dir: Plan directory with ``work_ledger.ndjson``.
        indent: JSON indentation (None = compact).

    Returns:
        Deterministic JSON string (sorted keys, stable ordering).
    """
    summary = build_work_class_summary(plan_dir)
    return json.dumps(summary, sort_keys=True, indent=indent, ensure_ascii=False)


def build_work_class_summary(
    plan_dir: Path,
) -> Dict[str, Any]:
    """Produce a rebuildable aggregate summary from the work ledger.

    The summary includes:
    - ``by_class``: per‑event‑class aggregation (count, total_duration_ms,
      category)
    - ``by_category``: fine-grained M9 projection categories with exact
      identity joins (event_ids, task_ids, source_classes, classification)
    - ``identity_joins``: exact event-id-to-category mapping with unavailable
      denominators
    - ``by_task``: per‑task aggregation with class breakdown and unavailable
      measures
    - ``totals``: value_work duration, non_value_work duration, gap count
    - ``_non_authoritative``: always ``true``
    - ``_rebuildable``: always ``true`` (deterministic from ledger)

    Every measure that cannot be computed is ``null``, never zero.
    """
    by_class = aggregate_by_class(plan_dir)
    by_category = aggregate_by_category(plan_dir)
    identity_joins = build_category_identity_joins(plan_dir)
    by_task = aggregate_by_task(plan_dir)
    unavailable = reconcile_unavailable_measures(plan_dir)

    value_work_duration_ms: Optional[int] = None
    non_value_work_duration_ms: Optional[int] = None

    value_total = 0
    value_found = False
    non_value_total = 0
    non_value_found = False
    for cls, agg in by_class.items():
        d = agg.get("total_duration_ms")
        if d is None:
            continue
        if cls in _VALUE_WORK_CLASSES:
            value_total += d
            value_found = True
        elif cls in _NON_VALUE_WORK_CLASSES:
            non_value_total += d
            non_value_found = True

    if value_found:
        value_work_duration_ms = value_total
    if non_value_found:
        non_value_work_duration_ms = non_value_total

    return {
        "by_class": by_class,
        "by_category": by_category,
        "identity_joins": identity_joins,
        "by_task": by_task,
        "totals": {
            "value_work_duration_ms": value_work_duration_ms,
            "non_value_work_duration_ms": non_value_work_duration_ms,
            "gap_count": len(unavailable),
        },
        "unavailable_measures": unavailable,
        "_non_authoritative": True,
        "_rebuildable": True,
    }


__all__ = [
    "WORK_LEDGER_EVENT_CLASSES",
    "append_work_ledger_event",
    "read_work_ledger",
    "emit_validation",
    "emit_repair_verify",
    "emit_productive",
    "emit_unavailable_reason",
    "emit_review_proof",
    "emit_queue",
    "emit_retry_wait",
    "emit_compaction",
    "emit_replay",
    "emit_tool",
    "emit_git",
    "emit_transition",
    "aggregate_by_class",
    "aggregate_by_category",
    "build_category_identity_joins",
    "aggregate_by_task",
    "reconcile_unavailable_measures",
    "build_work_class_summary",
    "serialize_work_ledger_summary",
    "_resolve_category",
]
