"""RecoveryPolicy.classify — M4 T16 (Step 11a) + M8A T13 normalized failure signatures.

Pure classifier extracted from ``megaplan.auto`` so any orchestration
consumer can ask "what should I do with this error?" without importing
the planning driver.

Contract
--------
:class:`RecoveryPolicy` exposes one method,
:meth:`RecoveryPolicy.classify(error, layer) -> RecoveryDecision`, which
returns a target-agnostic decision plus a *budget delta* — never a state
mutation.  The caller (``auto.py`` today) still owns counter bumps,
event emissions, and state machine transitions.

Decision actions
~~~~~~~~~~~~~~~~
* ``retry_fresh``     — start a clean attempt at the same phase
* ``retry_transient`` — replay after a transient external failure (provider stall)
* ``escalate``        — bubble up; caller decides target (target-agnostic)
* ``halt``            — terminal; ``halt_kind`` carries the reason category

``halt(kind)`` / ``escalate`` deliberately stay target-agnostic — no
``STATE_*`` literal escapes this module.  The caller maps the
``halt_kind`` to its own state machine.

Per-class budgets
~~~~~~~~~~~~~~~~~
* context-exhaustion (mirrors ``DEFAULT_MAX_CONTEXT_RETRIES``)
* transient external (mirrors ``DEFAULT_MAX_EXTERNAL_RETRIES``)
* blocked-task (mirrors ``DEFAULT_MAX_BLOCKED_RETRIES`` at auto.py:117)

The classifier returns ``budget_delta`` as the *increment* the caller
should apply to its corresponding counter (always ``+1`` for now, or ``0``
for ``halt``/``escalate``).  Counter bumps and event emits remain in
``auto.py`` so this module stays a pure decision function.

M8A T13 — Normalized failure signatures & per-class circuit counters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module-level helpers for deterministic failure classification with
circuit-breaking:

* :func:`classify_failure_class` — maps an error shape to a typed
  :data:`FailureClass` (worker_budget_exhausted, timeout_300s,
  provider_failover_exhaustion, compaction_failure, invalid_ref,
  invalid_model, invalid_import, invalid_provenance,
  review_quality_block, or unknown).

* :func:`normalize_failure_signature` — produces a content-addressed
  sha256 signature from failure_class + normalized error attributes +
  task_id + attempt_id.  Transient tokens (timestamps, PIDs, hex
  fragments, paths) are stripped so two semantically-equivalent
  failures produce the same digest.

* :func:`circuit_transition` — pure state transition: given a
  :class:`CircuitState` and a new signature, returns the next
  :class:`CircuitState` and an optional :class:`RecoveryDecision`
  when the circuit opens.

All circuit state stays caller-owned; this module only provides pure
decision functions.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Final, Literal, Optional

# ---------------------------------------------------------------------------
# Lazy imports — keep this module importable from non-planning consumers.
# auto.py is intentionally NOT imported at module load.
# ---------------------------------------------------------------------------

from arnold_pipelines.megaplan.orchestration.phase_result import ExitKind

# Mirror the budget caps lifted from auto.py (DEFAULT_MAX_BLOCKED_RETRIES :117).
DEFAULT_MAX_CONTEXT_RETRIES: Final[int] = 2
DEFAULT_MAX_EXTERNAL_RETRIES: Final[int] = 1
DEFAULT_MAX_BLOCKED_RETRIES: Final[int] = 1

# Pulled inline from auto.py:86,104 so non-planning consumers don't have to
# import auto.py to classify a transient. Keep in sync.
EXTERNAL_RETRYABLE_PHASES: Final[frozenset[str]] = frozenset(
    {"plan", "prep", "critique", "revise", "gate", "finalize", "review"}
)
EXTERNAL_RETRYABLE_LAYERS: Final[frozenset[str]] = frozenset(
    {
        "stream_content_stall",
        "stream_first_content_timeout",
        "stream_read_timeout",
        "transport_timeout",
        "worker_stream_stall",
    }
)
EXTERNAL_PERMANENT_ERROR_KINDS: Final[frozenset[str]] = frozenset(
    {
        "auth", "balance", "quota", "billing", "config",
        "bad_request", "invalid_request", "unsupported_model",
        "context_exhausted", "context_length", "rate_limit",
    }
)

Action = Literal["retry_fresh", "retry_transient", "escalate", "halt"]

# Target-agnostic halt categories. The caller maps these to its own state.
HaltKind = Literal[
    "context_retry_exhausted",
    "external_retry_exhausted",
    "blocked_retry_exhausted",
    "permanent_external",
    "unclassified",
    # M8A T13 — per-class circuit-opened halt kinds
    "worker_budget_circuit_open",
    "timeout_circuit_open",
    "provider_failover_circuit_open",
    "compaction_circuit_open",
    "invalid_ref_circuit_open",
    "invalid_model_circuit_open",
    "invalid_import_circuit_open",
    "invalid_provenance_circuit_open",
    "review_quality_circuit_open",
]

# M8A T13 — typed failure classes for normalized circuit-breaking.
FailureClass = Literal[
    "worker_budget_exhausted",
    "timeout_300s",
    "provider_failover_exhaustion",
    "compaction_failure",
    "invalid_ref",
    "invalid_model",
    "invalid_import",
    "invalid_provenance",
    "review_quality_block",
    "unknown",
]

# Default circuit-open threshold: two equivalent failures open the circuit
# before the third retry (per success criterion 8).
CIRCUIT_OPEN_THRESHOLD: Final[int] = 2

# Map FailureClass → HaltKind when circuit opens.
_FAILURE_CLASS_TO_HALT: Final[dict[FailureClass, HaltKind]] = {
    "worker_budget_exhausted": "worker_budget_circuit_open",
    "timeout_300s": "timeout_circuit_open",
    "provider_failover_exhaustion": "provider_failover_circuit_open",
    "compaction_failure": "compaction_circuit_open",
    "invalid_ref": "invalid_ref_circuit_open",
    "invalid_model": "invalid_model_circuit_open",
    "invalid_import": "invalid_import_circuit_open",
    "invalid_provenance": "invalid_provenance_circuit_open",
    "review_quality_block": "review_quality_circuit_open",
    "unknown": "unclassified",
}

# ---------------------------------------------------------------------------
# M8A T13 — Normalized failure signature helpers
# ---------------------------------------------------------------------------

# Regex patterns for stripping transient tokens from error messages.
# These are intentionally conservative: they only target well-known
# transient shapes (timestamps, hex IDs, PIDs, absolute paths) that
# would otherwise cause deterministic failures to produce different
# signatures on every occurrence.

_ISO_TIMESTAMP_RE: Final = re.compile(
    r"\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:?\d{2})?"
)
_DATE_ONLY_RE: Final = re.compile(r"\d{4}-\d{2}-\d{2}")
_HEXISH_TOKEN_RE: Final = re.compile(r"\b[0-9a-fA-F]{8,64}\b")
_UUID_RE: Final = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_PID_TOKEN_RE: Final = re.compile(r"\bpid[=: ]?\d+\b")
_ATTEMPT_TOKEN_RE: Final = re.compile(r"\battempt[=: ]?\d+\b")
_ABSOLUTE_PATH_RE: Final = re.compile(r"(?:/[a-zA-Z0-9_.-]+)+/[a-zA-Z0-9_.-]+")
_DURATION_RE: Final = re.compile(r"\b\d+\.\d{2,}s\b")
_BARE_NUMBER_RE: Final = re.compile(r"\b\d+\b")

def _normalize_message(text: str) -> str:
    """Normalize an error message by stripping transient tokens.

    Timestamps, hex IDs, UUIDs, PIDs, attempt counters, absolute paths,
    durations, and bare numbers are replaced with stable placeholders
    so that two semantically-equivalent failures produce the same
    normalized message.

    Regex application order matters: more-specific patterns
    (full ISO timestamps, UUIDs) must be applied before less-specific
    ones (bare dates, bare numbers) to prevent partial matches from
    consuming tokens needed for full matches.
    """
    text = str(text or "").strip().lower()
    # Apply most-specific patterns first.
    text = _ISO_TIMESTAMP_RE.sub(" <ts> ", text)
    text = _UUID_RE.sub(" <uuid> ", text)
    text = _HEXISH_TOKEN_RE.sub(" <hex> ", text)
    text = _PID_TOKEN_RE.sub(" <pid> ", text)
    text = _ATTEMPT_TOKEN_RE.sub(" <attempt> ", text)
    text = _ABSOLUTE_PATH_RE.sub(" <path> ", text)
    text = _DURATION_RE.sub(" <duration> ", text)
    # Date-only after ISO timestamps — only bare dates remain.
    text = _DATE_ONLY_RE.sub(" <date> ", text)
    # Bare numbers last — after all structured tokens are replaced.
    text = _BARE_NUMBER_RE.sub(" <n> ", text)
    # Collapse whitespace.
    text = re.sub(r"\s+", " ", text).strip()
    # Truncate to a reasonable length floor.
    return text[:1000]


def normalize_failure_signature(
    failure_class: FailureClass,
    error: Any,
    *,
    task_id: str = "",
    attempt_id: str = "",
) -> str:
    """Produce a deterministic, content-addressed sha256 signature for a failure.

    The signature incorporates:
    * ``failure_class`` — the typed failure class
    * ``task_id`` — scoped per-task (empty string means unscoped)
    * ``attempt_id`` — scoped per-attempt (empty string means unscoped)
    * Normalized error attributes: message, error_kind, error_layer,
      exit_kind (if present), and a shallow shape fingerprint.

    Transient tokens (timestamps, hex IDs, PIDs, absolute paths, etc.)
    are stripped from the message before hashing, so two semantically-
    equivalent failures produce the same signature regardless of when
    or where they occurred.

    Returns a 64-character lowercase hex digest.
    """
    # Normalize the message.
    raw_message = str(getattr(error, "message", "") or "")
    message = _normalize_message(raw_message)

    # Extract stable error attributes.
    error_kind = str(getattr(error, "error_kind", "") or "").strip().lower()
    error_layer = str(getattr(error, "error_layer", "") or "").strip().lower()
    exit_kind_raw = getattr(error, "exit_kind", None)
    exit_kind = ""
    if isinstance(exit_kind_raw, ExitKind):
        exit_kind = exit_kind_raw.value
    elif isinstance(exit_kind_raw, str):
        exit_kind = exit_kind_raw.strip().lower()

    # Provider/status — only include if present (minimal shape).
    provider = str(getattr(error, "provider", "") or "").strip().lower()
    status_code = getattr(error, "status_code", None)
    status_code_str = str(status_code) if status_code is not None else ""

    # Build a canonical payload for hashing.
    payload: dict[str, Any] = {
        "failure_class": failure_class,
        "task_id": str(task_id or ""),
        "attempt_id": str(attempt_id or ""),
    }
    # Only include non-empty message (the normalized version).
    if message:
        payload["message"] = message
    if error_kind:
        payload["error_kind"] = error_kind
    if error_layer:
        payload["error_layer"] = error_layer
    if exit_kind:
        payload["exit_kind"] = exit_kind
    if provider:
        payload["provider"] = provider
    if status_code_str:
        payload["status_code"] = status_code_str

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# M8A T13 — Failure class classification
# ---------------------------------------------------------------------------

def classify_failure_class(error: Any) -> FailureClass:
    """Map an error shape to a typed :data:`FailureClass`.

    Classification is shape-driven (``getattr``), not isinstance-based.
    The classifier checks for well-known error shapes in priority order:

    1. worker_budget_exhausted — error indicates worker run budget spent
    2. timeout_300s — 300-second timeout or stall timeout
    3. provider_failover_exhaustion — provider failover chain exhausted
    4. compaction_failure — evidence compaction failed
    5. invalid_ref — source ref mismatch or invalid
    6. invalid_model — model mismatch or invalid model reference
    7. invalid_import — import path mismatch or missing
    8. invalid_provenance — provenance mismatch or invalid
    9. review_quality_block — review quality gate blocked with unresolved items
    10. unknown — does not match any known class (typed, not silently collapsed)

    Returns ``"unknown"`` when no known class matches — the caller must
    handle unknown explicitly rather than defaulting to a retry.
    """
    message = str(getattr(error, "message", "") or "").lower()
    error_kind = str(getattr(error, "error_kind", "") or "").lower()
    error_code = str(getattr(error, "code", "") or "").lower()
    kind = str(getattr(error, "kind", "") or "").lower()

    # Classification order matters: more-specific patterns that contain
    # tokens shared with other classes (e.g. "budget exhausted" appears in
    # both worker_budget_exhausted and review_quality_block messages) must
    # be checked before less-specific ones.

    # 1) review_quality_block — must precede worker_budget_exhausted
    #    because "review rework budget exhausted" contains "budget exhausted".
    if kind in {"quality_gate_blocked", "review_quality_blocked_unknown"}:
        return "review_quality_block"
    if error_kind in {"review_quality_block", "quality_gate_blocked"}:
        return "review_quality_block"
    if error_code in {"review_quality_block", "quality_gate_blocked"}:
        return "review_quality_block"
    if _matches_any(
        message,
        [
            "review quality",
            "quality gate blocked",
            "review rework budget exhausted",
            "unresolved quality blockers",
            "review quality block",
            "quality_gate_blocked",
            "review_quality_blocked",
        ],
    ):
        return "review_quality_block"

    # 2) worker_budget_exhausted — worker run budget specifically (not review rework)
    if error_kind in {"worker_budget_exhausted", "run_budget_exhausted"}:
        return "worker_budget_exhausted"
    if error_code in {"worker_budget_exhausted", "budget_exhausted"}:
        return "worker_budget_exhausted"
    if _matches_any(
        message,
        [
            "worker budget exhausted",
            "worker run budget",
            "run budget exhausted",
        ],
    ):
        return "worker_budget_exhausted"
    # "budget exhausted" alone is too broad (matches review rework too),
    # so only match it when review-related tokens are absent.
    if "budget exhausted" in message and "review" not in message and "rework" not in message:
        return "worker_budget_exhausted"

    # 3) timeout_300s
    if error_kind == "timeout_300s":
        return "timeout_300s"
    if error_code == "timeout_300s":
        return "timeout_300s"
    if _matches_any(
        message,
        ["300s timeout", "300 second timeout", "timed out after 300", "phase timeout 300"],
    ):
        return "timeout_300s"
    # 300s phase_timeout or idle_timeout signals.
    if "timeout" in message and "300" in message:
        return "timeout_300s"

    # 4) provider_failover_exhaustion
    if error_kind in {"provider_failover_exhaustion", "failover_exhausted"}:
        return "provider_failover_exhaustion"
    if error_code == "provider_failover_exhaustion":
        return "provider_failover_exhaustion"
    if _matches_any(
        message,
        [
            "provider failover exhausted",
            "failover chain exhausted",
            "all providers exhausted",
            "no more providers",
            "provider failover",
        ],
    ):
        return "provider_failover_exhaustion"

    # 5) compaction_failure
    if error_kind in {"compaction_failure", "compaction_failed"}:
        return "compaction_failure"
    if error_code in {"compaction_failure", "compaction_failed"}:
        return "compaction_failure"
    if _matches_any(
        message,
        [
            "compaction failed",
            "evidence compaction",
            "compaction error",
            "cannot compact",
        ],
    ):
        return "compaction_failure"

    # 6) invalid_ref — check before generic invalid_model/import/provenance
    if error_kind in {"invalid_ref", "invalid_source_ref", "source_ref_mismatch"}:
        return "invalid_ref"
    if error_code in {
        "invalid_ref",
        "invalid_source_ref",
        "source_ref_mismatch",
        "canonical_source_unavailable",
        "invalid_worktree_ref",
    }:
        return "invalid_ref"
    if _matches_any(
        message,
        [
            "invalid ref",
            "invalid source ref",
            "source ref mismatch",
            "invalid git ref",
            "invalid worktree ref",
            "canonical_source_unavailable",
        ],
    ):
        return "invalid_ref"
    # worker_launch_preflight_mismatch with ref field
    if error_code == "worker_launch_preflight_mismatch":
        mismatches = getattr(error, "extra", {}) or {}
        if isinstance(mismatches, dict):
            mismatch_list = mismatches.get("mismatches", [])
        else:
            mismatch_list = []
        if isinstance(mismatch_list, list):
            for m in mismatch_list:
                if isinstance(m, dict) and m.get("field") in {
                    "source_ref", "ref",
                }:
                    return "invalid_ref"
                if isinstance(m, dict) and m.get("field") in {
                    "installed_package_path", "import_path",
                }:
                    return "invalid_import"
                if isinstance(m, dict) and m.get("field") in {
                    "runtime_revision", "provenance",
                }:
                    return "invalid_provenance"
                if isinstance(m, dict) and m.get("field") in {
                    "selected_model", "model",
                }:
                    return "invalid_model"

    # 7) invalid_model
    if error_kind in {"invalid_model", "model_mismatch", "unsupported_model"}:
        return "invalid_model"
    if error_code in {"invalid_model", "model_mismatch", "invalid_codex_model"}:
        return "invalid_model"
    if _matches_any(
        message,
        [
            "invalid model",
            "model mismatch",
            "unknown model",
            "unsupported model",
            "invalid_codex_model",
        ],
    ):
        return "invalid_model"

    # 8) invalid_import
    if error_kind in {"invalid_import", "import_mismatch", "import_path_mismatch"}:
        return "invalid_import"
    if error_code in {"invalid_import", "import_mismatch"}:
        return "invalid_import"
    if _matches_any(
        message,
        [
            "invalid import",
            "import path mismatch",
            "installed package path mismatch",
            "cannot import",
            "module not found",
        ],
    ):
        return "invalid_import"

    # 9) invalid_provenance
    if error_kind in {"invalid_provenance", "provenance_mismatch"}:
        return "invalid_provenance"
    if error_code in {"invalid_provenance", "provenance_mismatch"}:
        return "invalid_provenance"
    if _matches_any(
        message,
        [
            "invalid provenance",
            "provenance mismatch",
            "invalid parent provenance",
            "invalid self-parent provenance",
            "managed-agent provenance",
        ],
    ):
        return "invalid_provenance"

    # 10) unknown — typed, not silently collapsed.
    return "unknown"


def _matches_any(text: str, needles: list[str]) -> bool:
    """Return True if *text* contains any of *needles* (case-insensitive)."""
    text_lower = text.lower()
    return any(needle.lower() in text_lower for needle in needles)


# ---------------------------------------------------------------------------
# M8A T13 — Circuit state & transition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CircuitState:
    """Caller-owned per-class circuit breaker state.

    The caller (``auto.py``) tracks one :class:`CircuitState` per
    :data:`FailureClass` (or per task/attempt scope).  This module only
    provides the pure :func:`circuit_transition` function to compute
    the next state.
    """

    failure_class: FailureClass = "unknown"
    # The last observed signature (sha256 hex digest).
    last_signature: str = ""
    # How many times the current signature has been observed consecutively.
    count: int = 0
    # Whether the circuit is currently open (terminal for this class).
    circuit_open: bool = False


def circuit_transition(
    state: CircuitState,
    new_signature: str,
    *,
    threshold: int = CIRCUIT_OPEN_THRESHOLD,
) -> tuple[CircuitState, Optional[RecoveryDecision]]:
    """Pure circuit state transition.

    Given the current *state* and a new failure *signature*, return the
    next :class:`CircuitState` and an optional :class:`RecoveryDecision`
    when the circuit opens.

    Rules:
    * If the circuit is already open, return unchanged state (no-op).
    * If *new_signature* matches *state.last_signature*, increment count.
    * If *new_signature* differs, reset count to 1 and update last_signature.
    * When count reaches *threshold*, open the circuit and return a
      ``halt`` decision with the appropriate ``halt_kind`` for the class.

    This is a pure function — no side effects, no mutation of the input
    state (returns a new :class:`CircuitState`).
    """
    if state.circuit_open:
        return (state, None)

    if new_signature == state.last_signature and state.last_signature:
        new_count = state.count + 1
    else:
        new_count = 1

    next_state = CircuitState(
        failure_class=state.failure_class,
        last_signature=new_signature,
        count=new_count,
        circuit_open=False,
    )

    if new_count >= threshold and threshold > 0:
        halt_kind = _FAILURE_CLASS_TO_HALT.get(state.failure_class, "unclassified")
        next_state = CircuitState(
            failure_class=state.failure_class,
            last_signature=new_signature,
            count=new_count,
            circuit_open=True,
        )
        decision = RecoveryDecision(
            action="halt",
            halt_kind=halt_kind,
            reason=f"{state.failure_class} circuit open after {new_count} equivalent failures",
        )
        return (next_state, decision)

    return (next_state, None)


# ---------------------------------------------------------------------------
# RecoveryDecision dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RecoveryDecision:
    """Pure decision returned by :meth:`RecoveryPolicy.classify`."""

    action: Action
    # +1 against the matched budget when retrying; 0 for halt/escalate.
    budget_delta: int = 0
    # Which counter the delta targets (or which budget was exhausted on halt).
    budget_kind: Optional[Literal["context", "external", "blocked"]] = None
    # Populated only when action == "halt".
    halt_kind: Optional[HaltKind] = None
    # Optional human-readable reason for event emission.
    reason: str = ""


def _is_retryable_external_error(phase: str, external_error: Any) -> bool:
    """Mirror of auto._is_retryable_external_error (auto.py:221).

    Kept in sync deliberately; lifting it here lets non-planning consumers
    classify without importing auto.py.
    """
    if phase not in EXTERNAL_RETRYABLE_PHASES:
        return False
    if external_error is None:
        return False

    error_kind = str(getattr(external_error, "error_kind", "") or "").lower()
    status_code = getattr(external_error, "status_code", None)
    retry_after_s = getattr(external_error, "retry_after_s", None)
    provider_error_code = str(
        getattr(external_error, "provider_error_code", "") or ""
    ).lower()
    error_layer = str(getattr(external_error, "error_layer", "") or "").lower()
    message = str(getattr(external_error, "message", "") or "").lower()

    if error_kind in EXTERNAL_PERMANENT_ERROR_KINDS:
        return False
    if retry_after_s is not None:
        return False
    if isinstance(status_code, int) and 400 <= status_code < 500 and status_code != 408:
        return False

    if error_layer in EXTERNAL_RETRYABLE_LAYERS:
        return True
    if error_kind in {"stream_content_stall", "stalled_stream"}:
        return True
    if (
        error_kind == "network"
        and (provider_error_code == "timeout" or "timeout" in message or "timed out" in message)
        and (status_code is None or status_code in {408, 500, 502, 503, 504})
    ):
        return True
    return False


@dataclass(frozen=True)
class RecoveryPolicy:
    """Classify recovery errors without touching state.

    All caps default to the values lifted from ``auto.py``; callers can
    construct an alternate policy for tests by overriding the caps.
    """

    max_context_retries: int = DEFAULT_MAX_CONTEXT_RETRIES
    max_external_retries: int = DEFAULT_MAX_EXTERNAL_RETRIES
    max_blocked_retries: int = DEFAULT_MAX_BLOCKED_RETRIES

    # ------------------------------------------------------------------
    # The single public surface.
    # ------------------------------------------------------------------

    def classify(
        self,
        error: Any,
        layer: str,
        *,
        context_retries_used: int = 0,
        external_retries_used: int = 0,
        blocked_retries_used: int = 0,
        phase: str = "",
    ) -> RecoveryDecision:
        """Classify ``error`` observed at ``layer`` (phase / orchestration / etc.).

        Parameters
        ----------
        error
            The error or PhaseResult-like object. May have ``exit_kind``,
            ``error_kind``, ``error_layer``, etc.
        layer
            Where the error surfaced (``"phase"``, ``"orchestration"``, ...).
            Used for diagnostics only; classification is shape-driven.
        context_retries_used / external_retries_used / blocked_retries_used
            Current usage counters (caller-owned). The classifier uses these
            to decide whether the budget is still available.
        phase
            Phase name (e.g. ``"plan"``, ``"execute"``); needed for the
            external-retryable filter.
        """
        exit_kind = self._read_exit_kind(error)

        # 1) Context exhaustion — caller decides retry_fresh vs halt by budget.
        if exit_kind == ExitKind.context_exhausted or self._mentions_context_exhaustion(error):
            if context_retries_used < self.max_context_retries:
                return RecoveryDecision(
                    action="retry_fresh",
                    budget_delta=1,
                    budget_kind="context",
                    reason="context_exhausted",
                )
            return RecoveryDecision(
                action="halt",
                halt_kind="context_retry_exhausted",
                budget_kind="context",
                reason="context budget exhausted",
            )

        # 2) Transient external — provider stalls / transport timeouts.
        # Extract nested external_error sub-object if present (PhaseResult carries
        # error attributes one level down); fall back to error itself for bare objects.
        _ext_obj = getattr(error, "external_error", None) or error
        if exit_kind == ExitKind.external_error or self._looks_external(_ext_obj):
            if _is_retryable_external_error(phase, _ext_obj):
                if external_retries_used < self.max_external_retries:
                    return RecoveryDecision(
                        action="retry_transient",
                        budget_delta=1,
                        budget_kind="external",
                        reason="transient external",
                    )
                return RecoveryDecision(
                    action="halt",
                    halt_kind="external_retry_exhausted",
                    budget_kind="external",
                    reason="external budget exhausted",
                )
            # Non-retryable external (auth/billing/etc) — terminal.
            return RecoveryDecision(
                action="halt",
                halt_kind="permanent_external",
                reason="permanent external error",
            )

        # 3) Blocked-by-prereq / blocked-by-quality — caller may retry.
        if exit_kind in (ExitKind.blocked_by_quality, ExitKind.blocked_by_prereq):
            if blocked_retries_used < self.max_blocked_retries:
                return RecoveryDecision(
                    action="retry_fresh",
                    budget_delta=1,
                    budget_kind="blocked",
                    reason="blocked retry",
                )
            return RecoveryDecision(
                action="halt",
                halt_kind="blocked_retry_exhausted",
                budget_kind="blocked",
                reason="blocked budget exhausted",
            )

        # 4) Timeout / internal_error — escalate (caller picks next step).
        if exit_kind in (ExitKind.timeout, ExitKind.internal_error):
            return RecoveryDecision(
                action="escalate",
                reason=f"escalate {exit_kind.value if exit_kind else 'unknown'}",
            )

        # 5) Default — unclassified, halt to be safe.
        return RecoveryDecision(
            action="halt",
            halt_kind="unclassified",
            reason="unclassified error",
        )

    # ------------------------------------------------------------------
    # Helpers — shape-driven, no isinstance gymnastics.
    # ------------------------------------------------------------------

    def _read_exit_kind(self, error: Any) -> Optional[ExitKind]:
        raw = getattr(error, "exit_kind", None)
        if isinstance(raw, ExitKind):
            return raw
        if isinstance(raw, str):
            try:
                return ExitKind(raw)
            except ValueError:
                return None
        return None

    def _mentions_context_exhaustion(self, error: Any) -> bool:
        text = str(getattr(error, "message", "") or "")
        return "ran out of room in the model" in text.lower()

    def _looks_external(self, error: Any) -> bool:
        # Has any of the external-error markers.
        for attr in ("error_kind", "error_layer", "provider_error_code", "status_code", "retry_after_s"):
            if getattr(error, attr, None) is not None:
                return True
        return False

    # ------------------------------------------------------------------
    # Arnold adapter — bridges the Arnold RecoveryPolicy Protocol
    # ------------------------------------------------------------------

    def classify_arnold(
        self,
        error: Any,
        context: Any,  # arnold.runtime.recovery.RecoveryContext (Protocol)
    ) -> Any:  # arnold.runtime.recovery.RecoveryDecision
        """Arnold :class:`~arnold.runtime.recovery.ArnoldRecoveryPolicy` adapter.

        Maps the Arnold ``classify(error, RecoveryContext)`` Protocol onto
        the source-compatible ``classify(error, layer, *, …)`` signature.

        ``RecoveryContext.metadata`` carries the Megaplan keyword arguments:
        ``layer`` (default ``"phase"``), ``context_retries_used``,
        ``external_retries_used``, ``blocked_retries_used``, and ``phase``.

        The Megaplan :class:`RecoveryDecision` is translated into an Arnold
        :class:`~arnold.runtime.recovery.RecoveryDecision` with
        ``status="decided"``, opaque ``action`` / ``reason``, and
        ``budget_consumed`` carrying the budget kind, delta, and halt kind.
        """
        from arnold_pipelines.megaplan.orchestration.recovery import RecoveryDecision as ArnoldDecision

        meta = getattr(context, "metadata", {}) or {}
        layer = meta.get("layer", "phase")
        ctx_used = meta.get("context_retries_used", 0)
        ext_used = meta.get("external_retries_used", 0)
        blk_used = meta.get("blocked_retries_used", 0)
        phase = meta.get("phase", "")

        megaplan_decision = self.classify(
            error,
            layer,
            context_retries_used=ctx_used,
            external_retries_used=ext_used,
            blocked_retries_used=blk_used,
            phase=phase,
        )

        budget_consumed: dict[str, Any] = {}
        if megaplan_decision.budget_kind:
            budget_consumed["budget_kind"] = megaplan_decision.budget_kind
        if megaplan_decision.budget_delta:
            budget_consumed["budget_delta"] = megaplan_decision.budget_delta
        if megaplan_decision.halt_kind:
            budget_consumed["halt_kind"] = megaplan_decision.halt_kind

        return ArnoldDecision(
            status="decided",
            action=megaplan_decision.action,
            reason=megaplan_decision.reason,
            budget_consumed=budget_consumed,
        )


__all__ = [
    "Action",
    "HaltKind",
    "FailureClass",
    "RecoveryDecision",
    "RecoveryPolicy",
    "CircuitState",
    "DEFAULT_MAX_CONTEXT_RETRIES",
    "DEFAULT_MAX_EXTERNAL_RETRIES",
    "DEFAULT_MAX_BLOCKED_RETRIES",
    "CIRCUIT_OPEN_THRESHOLD",
    "EXTERNAL_RETRYABLE_PHASES",
    "EXTERNAL_RETRYABLE_LAYERS",
    "EXTERNAL_PERMANENT_ERROR_KINDS",
    "classify_failure_class",
    "normalize_failure_signature",
    "circuit_transition",
]
