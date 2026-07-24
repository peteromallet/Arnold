"""Evidence normalization over current-target evidence and optional BlockerVerdict.

Provides :class:`NormalizedEvidence`, a frozen dataclass with structured
accessors that consume the raw evidence dict produced by
:func:`~arnold_pipelines.megaplan.cloud.current_target.resolve_current_target`
and an optional :class:`~arnold_pipelines.megaplan.cloud.human_blockers.BlockerVerdict`.

This module is read-only — it does NOT mutate any state, re-classify
evidence, or apply keyword-scanning heuristics.  It only surfaces structured
fields that already exist in the gathered artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan.run_state.model import CanonicalState, TypedHumanGate


_TERMINAL_PLAN_STATES = {"done", "aborted", "cancelled"}


# ---------------------------------------------------------------------------
# Normalized evidence dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedEvidence:
    """Frozen normalization of current-target evidence with structured accessors.

    This consumes the raw evidence dict from ``resolve_current_target()`` and
    an optional ``BlockerVerdict``, then exposes structured accessors for
    liveness, terminal completion, active repair, stale markers, latest
    failure, diagnostic codes, blocked task id, changed-file count, retry
    fingerprints, and explicit human gate records.

    All accessors are purely derived from the provided evidence — no filesystem
    I/O, no mutation, and no keyword-scanning heuristics.
    """

    evidence: Mapping[str, Any]
    blocker_verdict: str = ""  # BlockerVerdict name string (avoids import)

    # Cached derived fields (populated via __post_init__)
    _tmux_process: Mapping[str, Any] = field(default_factory=dict)
    _active_step: Mapping[str, Any] = field(default_factory=dict)
    _plan_state: Mapping[str, Any] = field(default_factory=dict)
    _chain_state: Mapping[str, Any] = field(default_factory=dict)
    _needs_human: Mapping[str, Any] = field(default_factory=dict)
    _repair_progress: Mapping[str, Any] = field(default_factory=dict)
    _event_cursors: Mapping[str, Any] = field(default_factory=dict)
    _current_refs: Mapping[str, Any] = field(default_factory=dict)
    _diagnostic_codes: Mapping[str, Any] = field(default_factory=dict)
    _stale_evidence: Sequence[Mapping[str, Any]] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Cache sub-dicts from evidence for structured accessors."""
        object.__setattr__(self, "_tmux_process", _as_mapping(self.evidence.get("tmux_process")))
        object.__setattr__(self, "_active_step", _as_mapping(self.evidence.get("active_step_heartbeat")))
        object.__setattr__(self, "_plan_state", _as_mapping(self.evidence.get("plan_state")))
        object.__setattr__(self, "_chain_state", _as_mapping(self.evidence.get("chain_state")))
        object.__setattr__(self, "_needs_human", _as_mapping(self.evidence.get("needs_human")))
        object.__setattr__(self, "_repair_progress", _as_mapping(self.evidence.get("repair_progress")))
        object.__setattr__(self, "_event_cursors", _as_mapping(self.evidence.get("event_cursors")))
        object.__setattr__(self, "_current_refs", _as_mapping(self.evidence.get("current_refs")))
        object.__setattr__(self, "_diagnostic_codes", _as_mapping(self.evidence.get("diagnostic_codes")))
        stale = self.evidence.get("stale_evidence")
        object.__setattr__(self, "_stale_evidence", tuple(stale) if isinstance(stale, list) else ())

    # ------------------------------------------------------------------
    # liveness
    # ------------------------------------------------------------------

    @property
    def is_live(self) -> bool:
        """True when tmux/process evidence or active-step heartbeat indicates a live session."""
        if self._tmux_process.get("live_status") == "alive":
            return True
        if self._active_step.get("active") is True:
            return True
        return False

    @property
    def liveness_status(self) -> str:
        """Short liveness summary: ``"alive"``, ``"stopped"``, ``"unknown"``, or ``"heartbeat_only"``."""
        tmux_status = self._tmux_process.get("live_status", "unknown")
        heartbeat_active = self._active_step.get("active") is True
        if tmux_status == "alive":
            return "alive"
        if heartbeat_active:
            return "heartbeat_only"
        if tmux_status == "stopped":
            return "stopped"
        return "unknown"

    @property
    def liveness_detail(self) -> dict[str, Any]:
        """Detailed liveness evidence from tmux_process and active_step_heartbeat."""
        return {
            "tmux_live_status": self._tmux_process.get("live_status", "unknown"),
            "pid": self._tmux_process.get("pid"),
            "pid_live": self._tmux_process.get("pid_live"),
            "session_live": self._tmux_process.get("session_live"),
            "heartbeat_active": self._active_step.get("active", False),
            "heartbeat_phase": self._active_step.get("phase", ""),
            "heartbeat_worker_pid": self._active_step.get("worker_pid", ""),
        }

    # ------------------------------------------------------------------
    # terminal completion
    # ------------------------------------------------------------------

    @property
    def is_terminal(self) -> bool:
        """True when the plan or chain state indicates a terminal run outcome."""
        plan_state = _safe_str(self._plan_state.get("current_state"))
        chain_last_state = _safe_str(self._chain_state.get("last_state"))
        return plan_state.lower() in _TERMINAL_PLAN_STATES or chain_last_state.lower() in _TERMINAL_PLAN_STATES

    @property
    def terminal_state(self) -> str:
        """The terminal state value, or empty string if not terminal."""
        plan_state = _safe_str(self._plan_state.get("current_state"))
        if plan_state.lower() in _TERMINAL_PLAN_STATES:
            return plan_state
        chain_last_state = _safe_str(self._chain_state.get("last_state"))
        if chain_last_state.lower() in _TERMINAL_PLAN_STATES:
            return chain_last_state
        return ""

    @property
    def completion_status(self) -> str:
        """Human-readable completion summary."""
        if not self.is_terminal:
            return "not_completed"
        return self.terminal_state

    # ------------------------------------------------------------------
    # active repair
    # ------------------------------------------------------------------

    @property
    def has_active_repair(self) -> bool:
        """True when repair-progress sidecars are present."""
        return self._repair_progress.get("present", False) is True

    @property
    def active_repair_items(self) -> Sequence[Mapping[str, Any]]:
        """List of active repair-progress items."""
        items = self._repair_progress.get("items")
        return tuple(items) if isinstance(items, list) else ()

    @property
    def active_repair_status(self) -> str | None:
        """The status of the first repair-progress item, or None."""
        items = self.active_repair_items
        if items:
            return _safe_str(items[0].get("status")) or None
        return None

    # ------------------------------------------------------------------
    # stale markers
    # ------------------------------------------------------------------

    @property
    def has_stale_evidence(self) -> bool:
        """True when stale_evidence contains at least one entry."""
        return len(self._stale_evidence) > 0

    @property
    def stale_kinds(self) -> tuple[str, ...]:
        """Set of stale-evidence kinds (deduplicated, sorted)."""
        kinds: set[str] = set()
        for entry in self._stale_evidence:
            kind = _safe_str(entry.get("kind"))
            if kind:
                kinds.add(kind)
        return tuple(sorted(kinds))

    @property
    def stale_details(self) -> Sequence[Mapping[str, Any]]:
        """The raw stale_evidence list as an immutable sequence."""
        return self._stale_evidence

    @property
    def is_stale_needs_human(self) -> bool:
        """True when stale_evidence includes ``stale_needs_human_plan_ref``."""
        return "stale_needs_human_plan_ref" in self.stale_kinds

    @property
    def is_stale_marker_plan_ref(self) -> bool:
        """True when stale_evidence includes ``stale_marker_plan_ref``."""
        return "stale_marker_plan_ref" in self.stale_kinds

    @property
    def is_stale_chain_state(self) -> bool:
        """True when stale_evidence includes ``stale_chain_state_after_terminal_plan``."""
        return "stale_chain_state_after_terminal_plan" in self.stale_kinds

    @property
    def is_missing_workspace(self) -> bool:
        """True when stale_evidence includes ``missing_workspace``."""
        return "missing_workspace" in self.stale_kinds

    # ------------------------------------------------------------------
    # latest failure
    # ------------------------------------------------------------------

    @property
    def latest_failure_kind(self) -> str:
        """The latest gate kind from event cursors, or empty string."""
        return _safe_str(self._event_cursors.get("latest_gate_kind"))

    @property
    def latest_failure_summary(self) -> str:
        """Human-readable failure summary from needs_human sidecar."""
        return _safe_str(self._needs_human.get("summary"))

    @property
    def has_needs_human(self) -> bool:
        """True when a needs-human sidecar is present."""
        return self._needs_human.get("present", False) is True

    # ------------------------------------------------------------------
    # diagnostic codes
    # ------------------------------------------------------------------

    @property
    def diagnostic_codes(self) -> Mapping[str, Any]:
        """Structured diagnostic codes extracted from gathered artifacts."""
        return self._diagnostic_codes

    @property
    def escalation_label(self) -> str:
        """Escalation label from needs-human sidecar (e.g. ``"BROKEN_STATE_MACHINE"``)."""
        return _safe_str(self._diagnostic_codes.get("escalation_label"))

    @property
    def event_signature_labels(self) -> tuple[str, ...]:
        """Event signature labels (e.g. ``"authority_divergence/head_mismatch x293"``)."""
        labels = self._diagnostic_codes.get("event_signature_labels")
        return tuple(labels) if isinstance(labels, list) else ()

    @property
    def discord_status(self) -> str:
        """Discord delivery status from needs-human sidecar."""
        return _safe_str(self._diagnostic_codes.get("discord_status"))

    @property
    def retry_strategy(self) -> str:
        """Retry strategy from event cursors or plan state resume_cursor."""
        return _safe_str(self._diagnostic_codes.get("retry_strategy"))

    # ------------------------------------------------------------------
    # blocked task id
    # ------------------------------------------------------------------

    @property
    def blocked_task_id(self) -> str:
        """Best-effort blocked task id from needs-human evidence.

        The evidence ``needs_human`` dict now carries ``blocked_task_id``
        extracted from the needs-human payload's ``current`` pointer by
        the resolver.
        """
        return _safe_str(self._needs_human.get("blocked_task_id"))

    # ------------------------------------------------------------------
    # changed-file count
    # ------------------------------------------------------------------

    @property
    def changed_file_count(self) -> int | None:
        """Number of changed files from plan_state, or None if unavailable.

        The ``resume_cursor`` in plan_state may carry ``changed_file_count``
        from a milestone finalize snapshot.
        """
        resume_cursor = self._plan_state.get("resume_cursor")
        if isinstance(resume_cursor, Mapping):
            count = resume_cursor.get("changed_file_count")
            if isinstance(count, int):
                return count
        return None

    # ------------------------------------------------------------------
    # retry fingerprints
    # ------------------------------------------------------------------

    @property
    def retry_fingerprints(self) -> Mapping[str, Any]:
        """Retry fingerprint evidence from plan_state and chain_state.

        Returns mtime and fingerprint hashes for plan and chain state files,
        which serve as stable retry dedup keys.
        """
        return {
            "plan_state_fingerprint": _safe_str(self._plan_state.get("fingerprint")),
            "chain_state_fingerprint": _safe_str(self._chain_state.get("fingerprint")),
            "plan_state_mtime": self._plan_state.get("mtime", 0.0),
            "chain_state_mtime": self._chain_state.get("mtime", 0.0),
            "chain_log_fingerprint": _safe_str(self.evidence.get("chain_log", {}).get("fingerprint")),
        }

    @property
    def plan_state_fingerprint(self) -> str:
        """Fingerprint of the plan state file."""
        return _safe_str(self._plan_state.get("fingerprint"))

    @property
    def chain_state_fingerprint(self) -> str:
        """Fingerprint of the chain state file."""
        return _safe_str(self._chain_state.get("fingerprint"))

    # ------------------------------------------------------------------
    # explicit human gate records
    # ------------------------------------------------------------------

    @property
    def has_explicit_human_gate(self) -> bool:
        """True when needs_human is present AND not stale."""
        return self.has_needs_human and not self.is_stale_needs_human

    @property
    def human_gate_record(self) -> Mapping[str, Any]:
        """Structured human-gate record from needs-human sidecar."""
        return {
            "present": self.has_needs_human,
            "path": _safe_str(self._needs_human.get("path")),
            "summary": self.latest_failure_summary,
            "plan_refs": self._needs_human.get("plan_refs", []),
            "recorded_at": _safe_str(self._needs_human.get("recorded_at")),
            "escalation_label": self.escalation_label,
            "discord_status": self.discord_status,
            "blocked_task_id": self.blocked_task_id,
            "blocker_verdict": self.blocker_verdict,
        }

    @property
    def blocker_verdict_value(self) -> str:
        """The BlockerVerdict name string provided at construction."""
        return self.blocker_verdict

    # ------------------------------------------------------------------
    # full projection
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize all structured accessors to a stable dict."""
        return {
            "liveness": {
                "is_live": self.is_live,
                "status": self.liveness_status,
                "detail": self.liveness_detail,
            },
            "terminal_completion": {
                "is_terminal": self.is_terminal,
                "terminal_state": self.terminal_state,
                "completion_status": self.completion_status,
            },
            "active_repair": {
                "has_active_repair": self.has_active_repair,
                "items": list(self.active_repair_items),
                "status": self.active_repair_status,
            },
            "stale_markers": {
                "has_stale_evidence": self.has_stale_evidence,
                "stale_kinds": list(self.stale_kinds),
                "is_stale_needs_human": self.is_stale_needs_human,
                "is_stale_marker_plan_ref": self.is_stale_marker_plan_ref,
                "is_stale_chain_state": self.is_stale_chain_state,
                "is_missing_workspace": self.is_missing_workspace,
            },
            "latest_failure": {
                "failure_kind": self.latest_failure_kind,
                "failure_summary": self.latest_failure_summary,
                "has_needs_human": self.has_needs_human,
            },
            "diagnostic_codes": dict(self.diagnostic_codes),
            "blocked_task_id": self.blocked_task_id,
            "changed_file_count": self.changed_file_count,
            "retry_fingerprints": dict(self.retry_fingerprints),
            "human_gate": dict(self.human_gate_record),
        }


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _as_mapping(value: object) -> Mapping[str, Any]:
    """Return *value* as a dict if it is one, otherwise an empty dict."""
    if isinstance(value, Mapping):
        return value
    return {}


def _safe_str(value: object) -> str:
    """Return a trimmed string, or ``\"\"`` for non-string / None values."""
    if isinstance(value, str):
        return value.strip()
    return ""


def normalize_evidence(
    evidence: Mapping[str, Any],
    *,
    blocker_verdict: str = "",
) -> NormalizedEvidence:
    """Normalize raw resolver evidence into structured accessors.

    Args:
        evidence: Raw evidence dict from
            :func:`~arnold_pipelines.megaplan.cloud.current_target.resolve_current_target`.
        blocker_verdict: Optional ``BlockerVerdict`` name string (e.g.
            ``\"TRUE_BLOCKER\"``, ``\"STALE_MISMATCH\"``).  Callers should
            pass ``classification.verdict.name`` from
            :class:`~arnold_pipelines.megaplan.cloud.human_blockers.HumanBlockerClassification`.

    Returns:
        A frozen :class:`NormalizedEvidence` with structured accessors.
    """
    return NormalizedEvidence(evidence=evidence, blocker_verdict=blocker_verdict)
