"""M2.5 oracle — characterization harness for ``megaplan.auto.drive()``.

Each parametrized branch drives the auto loop with a known seam recipe,
snapshots the normalized ``DriverOutcome`` + exit code, and asserts the
result against a committed JSON golden in ``auto_drive_corpus/``.

Design contracts (settled — do not re-litigate):

* **SD1** — Golden regeneration uses the existing global ``--write-fixture``
  pytest flag (registered in root ``tests/conftest.py:34-39``).  There is no
  ``RECORD=1`` env var and no ``tests/characterization/conftest.py``.

* **SD2** — Volatile values are normalized at snapshot serialization time
  via ``_normalize_scalar`` / ``_normalize_outcome``.  We do NOT patch
  ``auto._phase_result_signature`` (returns ``tuple[int,int]|None``) or
  ``auto._get_review_marker`` (returns ``float|None``) to strings — doing
  so would corrupt phase-result routing at ``auto.py:1389`` and the
  review-marker comparison at ``auto.py:1707``.

* **SD3** — ``resume_cursor`` and ``current_state`` are captured from the
  ``_record_lifecycle_failure`` sidecar, NOT from ``DriverOutcome``
  attributes (the dataclass at ``auto.py:146-166`` carries neither field).
  ``_install_determinism`` monkeypatches ``auto._record_lifecycle_failure``
  to a wrapper that calls the real function AND stashes the failure-record
  dict into a shared sidecar dict.

* **SD4** — The corpus characterizes the 12-step auto-drive loop, not the
  optional git publish epilogue.  Call ``drive(push=False)`` so native-backed
  execution changes do not get obscured by tmpdir-specific git repo setup.

* **SD5** — Intentional trace updates for done-path goldens should be limited
  to semantic verdict metadata (for example the added
  ``execution_acceptance_contract`` provider) or clearer phase-error text, not
  changes to the 12-step canonical routing itself.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan import auto 
from arnold_pipelines.megaplan.auto import DriverOutcome

# ---------------------------------------------------------------------------
# Corpus directory
# ---------------------------------------------------------------------------

CORPUS_DIR = Path(__file__).resolve().parent / "auto_drive_corpus"

# ---------------------------------------------------------------------------
# Regex patterns for volatile-value normalization
# ---------------------------------------------------------------------------

_ISO_8601_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\b"
)

# Normalizes the non-deterministic idle_seconds that appears in the
# terminate_idle_step recovery message (e.g. "182345s without activity >= 1800s").
_IDLE_SECONDS_RE = re.compile(r"\b\d+s without activity >= \d+s\b")

# Pinned review.json mtime values (set via os.utime in recipes).  These
# appear in log messages that quote the marker or in metadata fields that
# record the mtime.  Replacement must run BEFORE _ISO_8601_RE so we don't
# clobber ISO timestamps that happen to contain the pinned float.
_MTIME_RE = re.compile(r"\b1000000000\.0\b")

# Raw float numbers that appear in cost-related log messages (e.g. the
# cost-cap-exceeded reason / msg strings).  None of the other goldens
# embed bare floats in string fields, so this replacement is safe.
_COST_FLOAT_RE = re.compile(r"\b\d+\.\d+\b")

# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _replace_paths(value: str, replacements: list[str]) -> str:
    """Replace every known volatile path prefix with ``{{TMPDIR}}``."""
    for original in replacements:
        if original:
            value = value.replace(original, "{{TMPDIR}}")
    return value


# Known volatile numeric keys — any numeric value under one of these keys
# is replaced with a sentinel string so goldens stay byte-stable across runs.
_VOLATILE_NUMERIC_KEYS: dict[str, str] = {
    "total_cost_usd": "{{COST}}",
    "cost_cap_usd": "{{COST}}",
    "elapsed_s": "{{ELAPSED}}",
}


def _normalize_scalar(value: Any, replacements: list[str]) -> Any:
    """Recursively normalize volatile scalars in *value*.

    * Path strings → ``{{TMPDIR}}`` (longest-first via *replacements*)
    * ISO-8601 timestamps → ``{{NOW}}``
    * Cost / elapsed numeric fields → ``{{COST}}`` / ``{{ELAPSED}}``
    """
    if isinstance(value, str):
        normalized = _replace_paths(value, replacements)
        normalized = _MTIME_RE.sub("{{MTIME}}", normalized)
        normalized = _COST_FLOAT_RE.sub("{{COST}}", normalized)
        normalized = _ISO_8601_RE.sub("{{NOW}}", normalized)
        normalized = _IDLE_SECONDS_RE.sub(
            "{{IDLE_SECONDS}}s without activity >= {{IDLE_THRESHOLD}}s", normalized
        )
        return normalized
    if isinstance(value, list):
        return [_normalize_scalar(item, replacements) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, val in value.items():
            if key in _VOLATILE_NUMERIC_KEYS and isinstance(val, (int, float)):
                result[key] = _VOLATILE_NUMERIC_KEYS[key]
            else:
                result[key] = _normalize_scalar(val, replacements)
        return result
    return value


def _normalize_outcome(
    outcome: DriverOutcome,
    events: list[dict[str, Any]],
    exit_code: int,
    sidecar: dict[str, Any],
    tmp_path: Path,
) -> dict[str, Any]:
    """Build the normalized snapshot dict for a single drive() invocation.

    Volatile fields on the outcome are replaced with sentinel strings so
    golden comparisons stay stable across runs.  ``resume_cursor`` and
    ``current_state`` are sourced from *sidecar* (populated by the
    ``_record_lifecycle_failure`` wrapper installed by
    ``_install_determinism``), never from ``DriverOutcome`` attributes.
    """
    # Build the replacements list for path normalization
    replacements = sorted(
        {
            str(tmp_path),
            str(tmp_path.resolve()),
            str(tmp_path.parent),
            str(tmp_path.parent.resolve()),
        },
        key=len,
        reverse=True,
    )

    outcome_dict: dict[str, Any] = {
        "status": outcome.status,
        "final_state": outcome.final_state,
        "iterations": outcome.iterations,
        "reason": outcome.reason,
        "blocking_reasons": outcome.blocking_reasons,
        "context_retries_used": outcome.context_retries_used,
        "external_retries_used": outcome.external_retries_used,
        "max_blocked_retries_used": outcome.blocked_retries_used,
    }

    # ── SD3: resume_cursor / current_state from sidecar ────────────────
    outcome_dict["resume_cursor"] = sidecar.get("resume_cursor")
    outcome_dict["current_state"] = sidecar.get("current_state")

    snapshot: dict[str, Any] = {
        "exit_code": exit_code,
        "outcome": outcome_dict,
        "events": events,
    }

    return _normalize_scalar(snapshot, replacements)


# ---------------------------------------------------------------------------
# Fixture read / write / assert
# ---------------------------------------------------------------------------


def _read_golden(path: Path) -> dict[str, Any]:
    if not path.exists():
        pytest.fail(
            f"Golden not found: {path}\n"
            f"Generate it with:  pytest tests/characterization/test_auto_drive.py "
            f"--write-fixture"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _write_golden(path: Path, payload: dict[str, Any]) -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _assert_or_write(
    name: str,
    snapshot: dict[str, Any],
    request: pytest.FixtureRequest,
) -> None:
    """Assert *snapshot* matches the committed golden, or (re)write it.

    Uses the global ``--write-fixture`` flag registered in root
    ``tests/conftest.py:34-39`` — the same mechanism every sibling
    characterization test uses.
    """
    fixture_path = CORPUS_DIR / f"{name}.json"

    if request.config.getoption("--write-fixture", default=False):
        _write_golden(fixture_path, snapshot)
        return

    expected = _read_golden(fixture_path)
    current_str = json.dumps(snapshot, indent=2, sort_keys=True)
    expected_str = json.dumps(expected, indent=2, sort_keys=True)
    if current_str != expected_str:
        pytest.fail(
            "Auto-drive golden diverged.\n\n"
            f"Fixture: {fixture_path}\n"
            "If the change is intentional, regenerate with:\n"
            "  pytest tests/characterization/test_auto_drive.py --write-fixture\n"
        )


# ---------------------------------------------------------------------------
# Determinism harness
# ---------------------------------------------------------------------------


def _install_determinism(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Install determinism patches for reproducible auto-drive traces.

    **Only** patches:

    * ``time.sleep`` → no-op
    * ``auto._record_lifecycle_failure`` → wrapper that calls the real
      function AND captures ``resume_cursor`` / ``current_state`` into a
      shared sidecar dict.

    **Leaves untouched** (per SD2):

    * ``auto._phase_result_signature`` — returns ``tuple[int,int]|None``;
      patching it would break phase-result detection at ``auto.py:1389``.
    * ``auto._get_review_marker`` — returns ``float|None``; patching it
      would break the review-marker comparison at ``auto.py:1707``.

    Returns the *sidecar* dict.  Callers should also pass ``poll_sleep=0``
    to ``drive()`` so the poll loop doesn't add real latency.
    """
    import time as time_module

    sidecar: dict[str, Any] = {}

    _real_record = auto._record_lifecycle_failure

    def _capture_wrapper(**kwargs: Any) -> None:
        # Capture resume_cursor and current_state from the keyword args
        rc = kwargs.get("resume_cursor")
        if rc is not None:
            sidecar["resume_cursor"] = rc
        cs = kwargs.get("current_state")
        if cs is not None:
            sidecar["current_state"] = cs
        # Stash the full call for diagnostics
        sidecar.setdefault("_calls", []).append(
            {
                "kind": kwargs.get("kind"),
                "message": kwargs.get("message"),
                "current_state": cs,
                "phase": kwargs.get("phase"),
                "resume_cursor": rc,
            }
        )
        return _real_record(**kwargs)

    monkeypatch.setattr(auto, "_record_lifecycle_failure", _capture_wrapper)
    monkeypatch.setattr(time_module, "sleep", lambda s: None)

    return sidecar


# ---------------------------------------------------------------------------
# Branch registry — every drive() exit branch enumerated from megaplan/auto.py
# ---------------------------------------------------------------------------
#
# Each entry maps one unique ``_outcome(status=…)`` call site to the seam
# parameters downstream golden-authoring tasks need to script the branch.
#
# Columns
# -------
# name : str
#     Unique stable identifier for the branch (used as the golden fixture
#     filename stem).
# auto_py_line : int
#     Current line number of the ``return _outcome(`` statement in
#     ``megaplan/auto.py`` (verified by reading the file, not cited from
#     the brief).
# exit_kind_or_status : str
#     The literal string passed to ``status=`` in the ``_outcome`` call,
#     or the ``ExitKind`` value (``ExitKind.<member>.value``) that routes
#     into this branch via the phase-result dispatch at L2313-2466.
# phase_result_payload : dict | None
#     For branches gated on a ``PhaseResult`` with a specific ``exit_kind``
#     (L2313-2466), a description of the required ``PhaseResult``
#     attributes.  ``None`` for status-driven (non-PhaseResult) branches.
# status_override : tuple[str, str] | None
#     ``(active_step, state)`` that the mocked ``_status()`` dict must
#     carry to reach this branch, or ``None`` when the branch is reached
#     via a ``PhaseResult`` / exception / iteration cap independently of
#     the status dict.
# status_raises : bool
#     When ``True``, the recipe must monkeypatch ``_status()`` to **raise**
#     (``RuntimeError`` or ``json.JSONDecodeError``) rather than return a
#     dict — only used for ``status_lookup_failed`` (per gate
#     ``issue_hints-6``).
# expected_exit_code : int
#     Expected exit code from ``run_auto`` (L2858-2879).  Exit code 1 is
#     the fallthrough for ``awaiting_human``, ``human_required``,
#     ``tiebreaker_pending``, ``tiebreaker_ready``, and every ``failed``
#     variant.
# oracle_role : str
#     Human-readable tag describing what this branch characterizes
#     (terminal arm, recovery path, retry cap, escalation, etc.).
#
# Coverage notes
# --------------
# * The ``_outcome`` call at L1630 multiplexes five terminal states
#   (done / aborted / failed / blocked / cancelled) through the
#   ``terminal_status`` dict at L1599-1605; each is a distinct branch
#   with its own ``status_override`` state and ``expected_exit_code``.
# * ``awaiting_human`` at L1565 has two sub-variants (prep-sourced vs
#   criteria-verification) that share the same call site; the prep
#   variant requires ``awaiting_user.json`` with ``{"source":"prep",…}``
#   in the plan directory.
# * ``blocked_terminal`` (L1630 with state=blocked) only fires when
#   ``valid_next`` is falsy; if ``valid_next`` is non-empty the driver
#   treats ``blocked`` as recoverable (L1543).
#
# R4-addition branches (gated during plan finalize)
# ------------------------------------------------
# These five branches were identified as coverage gaps in the original
# plan and are enumerated here for completeness:
#
#   * ``status_lookup_failed``     – L1487  (``status_raises=True``)
#   * ``no_next_step_no_override`` – L1947
#   * ``phase_callback_failed``    – L2300
#   * ``iteration_cap``            – L2634
#   * ``force_proceed_failed``     – L1886
#
# Non-terminal events (not ``_outcome`` calls — NOT exit branches)
# ---------------------------------------------------------------
# These fire inside the drive loop but do **not** produce a
# ``DriverOutcome`` directly: ``phase_timeout`` (L2153), ``external_error``
# (L2188), ``phase_failed`` – internal_error (L2248), ``phase_failed`` –
# non-zero exit (L2263), ``execution_blocked`` – retry paths (L2376,
# L2430), ``plan_locked`` continue (L2245), ``auto_escalate_up`` continue
# (L2517-2599).  They are covered indirectly by compound golden recipes
# (e.g. idle-timeout → stall) but are **not** exit branches.

_BRANCHES: list[dict[str, Any]] = [
    # ── status_lookup_failed ──────────────────────────────────────────
    {
        "name": "status_lookup_failed",
        "auto_py_line": 1487,
        "exit_kind_or_status": "failed",
        "phase_result_payload": None,
        "status_override": None,
        "status_raises": True,
        "expected_exit_code": 1,
        "oracle_role": "R4-addition: _status() raises RuntimeError / JSONDecodeError",
    },
    # ── cost_cap_exceeded ─────────────────────────────────────────────
    {
        "name": "cost_cap_exceeded",
        "auto_py_line": 1516,
        "exit_kind_or_status": "cost_cap_exceeded",
        "phase_result_payload": None,
        "status_override": ("execute", "executed"),
        "status_raises": False,
        "expected_exit_code": 6,
        "oracle_role": "terminal arm: cumulative cost > max_cost_usd",
    },
    # ── awaiting_human (prep) ─────────────────────────────────────────
    {
        "name": "awaiting_human_prep",
        "auto_py_line": 1565,
        "exit_kind_or_status": "awaiting_human",
        "phase_result_payload": None,
        "status_override": (None, "awaiting_human_verify"),
        "status_raises": False,
        "expected_exit_code": 1,
        "oracle_role": (
            "terminal arm: STATE_AWAITING_HUMAN with prep-sourced "
            "awaiting_user.json (source=prep)"
        ),
    },
    # ── awaiting_human (verify) ───────────────────────────────────────
    {
        "name": "awaiting_human_verify",
        "auto_py_line": 1565,
        "exit_kind_or_status": "awaiting_human",
        "phase_result_payload": None,
        "status_override": (None, "awaiting_human_verify"),
        "status_raises": False,
        "expected_exit_code": 1,
        "oracle_role": (
            "terminal arm: STATE_AWAITING_HUMAN with criteria-verification "
            "(no prep awaiting_user.json)"
        ),
    },
    # ── tiebreaker_pending ────────────────────────────────────────────
    {
        "name": "tiebreaker_pending",
        "auto_py_line": 1574,
        "exit_kind_or_status": "tiebreaker_pending",
        "phase_result_payload": None,
        "status_override": (None, "tiebreaker_pending"),
        "status_raises": False,
        "expected_exit_code": 1,
        "oracle_role": "terminal arm: STATE_TIEBREAKER_PENDING",
    },
    # ── tiebreaker_ready ──────────────────────────────────────────────
    {
        "name": "tiebreaker_ready",
        "auto_py_line": 1583,
        "exit_kind_or_status": "tiebreaker_ready",
        "phase_result_payload": None,
        "status_override": (None, "tiebreaker_ready"),
        "status_raises": False,
        "expected_exit_code": 1,
        "oracle_role": "terminal arm: STATE_TIEBREAKER_READY",
    },
    # ── paused ────────────────────────────────────────────────────────
    {
        "name": "paused",
        "auto_py_line": 1592,
        "exit_kind_or_status": "paused",
        "phase_result_payload": None,
        "status_override": (None, "paused"),
        "status_raises": False,
        "expected_exit_code": 0,
        "oracle_role": "terminal arm: STATE_PAUSED",
    },
    # ── terminal-state multiplex: done ────────────────────────────────
    {
        "name": "done",
        "auto_py_line": 1630,
        "exit_kind_or_status": "done",
        "phase_result_payload": None,
        "status_override": (None, "done"),
        "status_raises": False,
        "expected_exit_code": 0,
        "oracle_role": "terminal arm: STATE_DONE via L1599-1605 mapping",
    },
    # ── terminal-state multiplex: aborted ─────────────────────────────
    {
        "name": "aborted_terminal",
        "auto_py_line": 1630,
        "exit_kind_or_status": "aborted",
        "phase_result_payload": None,
        "status_override": (None, "aborted"),
        "status_raises": False,
        "expected_exit_code": 0,
        "oracle_role": "terminal arm: STATE_ABORTED via L1599-1605 mapping",
    },
    # ── terminal-state multiplex: failed ──────────────────────────────
    {
        "name": "failed_terminal",
        "auto_py_line": 1630,
        "exit_kind_or_status": "failed",
        "phase_result_payload": None,
        "status_override": (None, "failed"),
        "status_raises": False,
        "expected_exit_code": 1,
        "oracle_role": "terminal arm: STATE_FAILED via L1599-1605 mapping",
    },
    # ── terminal-state multiplex: blocked (valid_next falsy) ──────────
    {
        "name": "blocked_terminal",
        "auto_py_line": 1630,
        "exit_kind_or_status": "blocked",
        "phase_result_payload": None,
        "status_override": (None, "blocked"),
        "status_raises": False,
        "expected_exit_code": 5,
        "oracle_role": (
            "terminal arm: STATE_BLOCKED with empty/falsy valid_next "
            "(L1543 guard)"
        ),
    },
    # ── terminal-state multiplex: cancelled ───────────────────────────
    {
        "name": "cancelled",
        "auto_py_line": 1630,
        "exit_kind_or_status": "cancelled",
        "phase_result_payload": None,
        "status_override": (None, "cancelled"),
        "status_raises": False,
        "expected_exit_code": 0,
        "oracle_role": "terminal arm: STATE_CANCELLED via L1599-1605 mapping",
    },
    # ── stalled (review-rework cap) ───────────────────────────────────
    {
        "name": "stalled_review_rework",
        "auto_py_line": 1733,
        "exit_kind_or_status": "stalled",
        "phase_result_payload": None,
        "status_override": (None, "reviewed"),
        "status_raises": False,
        "expected_exit_code": 2,
        "oracle_role": (
            "recovery: review rework cycles > max_review_rework_cycles "
            "(L1720-1744)"
        ),
    },
    # ── blocked (all tasks blocked / poisoned outcome) ────────────────
    {
        "name": "blocked_all_tasks",
        "auto_py_line": 1774,
        "exit_kind_or_status": "blocked",
        "phase_result_payload": None,
        "status_override": (None, "executed"),
        "status_raises": False,
        "expected_exit_code": 5,
        "oracle_role": (
            "recovery: all pending tasks reported status=blocked "
            "(tasks_blocked>0, tasks_pending==0, L1758)"
        ),
    },
    # ── stalled (generic stall detection) ─────────────────────────────
    {
        "name": "stalled",
        "auto_py_line": 1795,
        "exit_kind_or_status": "stalled",
        "phase_result_payload": None,
        "status_override": (None, "executed"),
        "status_raises": False,
        "expected_exit_code": 2,
        "oracle_role": (
            "recovery: same state for stall_threshold+ iterations "
            "(L1747-1804)"
        ),
    },
    # ── human_required (strict-notes block) ───────────────────────────
    {
        "name": "human_required",
        "auto_py_line": 1866,
        "exit_kind_or_status": "human_required",
        "phase_result_payload": None,
        "status_override": (None, "gated"),
        "status_raises": False,
        "expected_exit_code": 1,
        "oracle_role": (
            "escalation: force-proceed blocked by strict-notes invariants "
            "(L1851-1875)"
        ),
    },
    # ── force_proceed_failed (R4-addition) ────────────────────────────
    {
        "name": "force_proceed_failed",
        "auto_py_line": 1886,
        "exit_kind_or_status": "failed",
        "phase_result_payload": None,
        "status_override": (None, "gated"),
        "status_raises": False,
        "expected_exit_code": 1,
        "oracle_role": (
            "R4-addition: override force-proceed exited non-zero without "
            "strict-note signals (L1876-1892)"
        ),
    },
    # ── aborted (escalate → abort) ────────────────────────────────────
    {
        "name": "aborted_escalate",
        "auto_py_line": 1910,
        "exit_kind_or_status": "aborted",
        "phase_result_payload": None,
        "status_override": (None, "gated"),
        "status_raises": False,
        "expected_exit_code": 0,
        "oracle_role": "escalation: on_escalate=abort (L1894-1916)",
    },
    # ── escalated (escalate → fail) ───────────────────────────────────
    {
        "name": "escalated",
        "auto_py_line": 1929,
        "exit_kind_or_status": "escalated",
        "phase_result_payload": None,
        "status_override": (None, "gated"),
        "status_raises": False,
        "expected_exit_code": 3,
        "oracle_role": "escalation: on_escalate=fail (L1917-1935)",
    },
    # ── no_next_step_no_override (R4-addition) ────────────────────────
    {
        "name": "no_next_step_no_override",
        "auto_py_line": 1947,
        "exit_kind_or_status": "failed",
        "phase_result_payload": None,
        "status_override": (None, "gated"),
        "status_raises": False,
        "expected_exit_code": 1,
        "oracle_role": (
            "R4-addition: no next_step and no override available "
            "(L1936-1953)"
        ),
    },
    # ── context_retry_exhausted ───────────────────────────────────────
    {
        "name": "context_retry_exhausted",
        "auto_py_line": 2056,
        "exit_kind_or_status": "context_retry_exhausted",
        "phase_result_payload": {
            "exit_kind": "context_exhausted",
            "note": (
                "PhaseResult with exit_kind=context_exhausted, repeated "
                "until context_retry_count >= max_context_retries "
                "(L2034-2065)"
            ),
        },
        "status_override": (None, "finalized"),
        "status_raises": False,
        "expected_exit_code": 7,
        "oracle_role": "retry-cap: context exhaustion retry cap reached",
    },
    # ── phase_callback_failed (R4-addition) ───────────────────────────
    {
        "name": "phase_callback_failed",
        "auto_py_line": 2300,
        "exit_kind_or_status": "failed",
        "phase_result_payload": None,
        "status_override": (None, "finalized"),
        "status_raises": False,
        "expected_exit_code": 1,
        "oracle_role": (
            "R4-addition: on_phase_complete callback raises exception "
            "(L2275-2306)"
        ),
    },
    # ── awaiting_human (blocked_by_prereq + blocked_tasks) ────────────
    {
        "name": "awaiting_human_blocked_prereq",
        "auto_py_line": 2344,
        "exit_kind_or_status": "awaiting_human",
        "phase_result_payload": {
            "exit_kind": "blocked_by_prereq",
            "note": (
                "PhaseResult with exit_kind=blocked_by_prereq and "
                "non-empty blocked_tasks tuple (L2318-2359)"
            ),
        },
        "status_override": (None, "finalized"),
        "status_raises": False,
        "expected_exit_code": 1,
        "oracle_role": (
            "phase-result routing: execute blocked_by_prereq with "
            "blocked_tasks → awaiting_human"
        ),
    },
    # ── worker_blocked (blocked_by_prereq quality cap) ────────────────
    {
        "name": "worker_blocked_prereq_quality",
        "auto_py_line": 2393,
        "exit_kind_or_status": "worker_blocked",
        "phase_result_payload": {
            "exit_kind": "blocked_by_prereq",
            "note": (
                "PhaseResult with exit_kind=blocked_by_prereq, empty "
                "blocked_tasks, deviations present, "
                "blocked_retry_count >= max_blocked_retries "
                "(L2360-2404)"
            ),
        },
        "status_override": (None, "finalized"),
        "status_raises": False,
        "expected_exit_code": 8,
        "oracle_role": (
            "phase-result routing: blocked_by_prereq quality-gate "
            "retry cap reached → worker_blocked"
        ),
    },
    # ── worker_blocked (blocked_by_quality cap) ───────────────────────
    {
        "name": "worker_blocked_quality",
        "auto_py_line": 2447,
        "exit_kind_or_status": "worker_blocked",
        "phase_result_payload": {
            "exit_kind": "blocked_by_quality",
            "note": (
                "PhaseResult with exit_kind=blocked_by_quality, "
                "deviations present, "
                "blocked_retry_count >= max_blocked_retries "
                "(L2413-2466)"
            ),
        },
        "status_override": (None, "finalized"),
        "status_raises": False,
        "expected_exit_code": 8,
        "oracle_role": (
            "phase-result routing: blocked_by_quality retry cap "
            "reached → worker_blocked"
        ),
    },
    # ── iteration_cap (R4-addition) ───────────────────────────────────
    {
        "name": "iteration_cap",
        "auto_py_line": 2634,
        "exit_kind_or_status": "cap",
        "phase_result_payload": None,
        "status_override": (None, "finalized"),
        "status_raises": False,
        "expected_exit_code": 4,
        "oracle_role": (
            "R4-addition: max_iterations exceeded (L2622-2640)"
        ),
    },
    # ── infrastructure_error ────────────────────────────────────────────
    {
        "name": "infrastructure_error",
        "auto_py_line": 3702,
        "exit_kind_or_status": "infrastructure_error",
        "phase_result_payload": None,
        "status_override": (None, "finalized"),
        "status_raises": False,
        "expected_exit_code": 9,
        "oracle_role": (
            "terminal arm: phase refused by non-retryable infrastructure preflight"
        ),
    },
]


# ---------------------------------------------------------------------------
# Golden recipes — drive() seams for each branch we want to snapshot
# ---------------------------------------------------------------------------
#
# Each recipe entry describes how to mock ``_status`` and ``_run_planning_phase``
# so that ``drive()`` traverses exactly the branch identified by the
# corresponding ``_BRANCHES`` entry.
#
# Keys
# ----
# name : str
#     Golden fixture name (also the parametrize id).
# branch_ref : str
#     ``name`` of the ``_BRANCHES`` entry this recipe targets.
# mode : str
#     ``"immediate_terminal"`` — ``_status`` returns a terminal state on the
#     first call; ``_run_planning_phase`` is never invoked.
#     ``"execute_then_terminal"`` — ``_status`` first returns a non-terminal
#     state with ``next_step="execute"``, then a terminal state; one
#     ``_run_planning_phase`` call writes a successful ``phase_result.json``.
# status_sequence : list[dict[str, Any]]
#     Return values for successive ``_status()`` calls.
# run_exit_kind : str | None
#     ``exit_kind`` fed to ``fake_run_with_phase_result`` (only for
#     ``"execute_then_terminal"`` mode).

_GOLDEN_RECIPES: list[dict[str, Any]] = [
    # ── happy_path_done ────────────────────────────────────────────────
    {
        "name": "happy_path_done",
        "branch_ref": "done",
        "mode": "execute_then_terminal",
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 1,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
            {
                "success": True,
                "step": "status",
                "state": "done",
                "iteration": 2,
                "summary": "Plan is in state 'done'.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_exit_kind": "success",
    },
    # ── done_terminal ──────────────────────────────────────────────────
    {
        "name": "done_terminal",
        "branch_ref": "done",
        "mode": "immediate_terminal",
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "done",
                "iteration": 1,
                "summary": "Plan is in state 'done'.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_exit_kind": None,
    },
    # ── aborted_terminal ───────────────────────────────────────────────
    {
        "name": "aborted_terminal",
        "branch_ref": "aborted_terminal",
        "mode": "immediate_terminal",
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "aborted",
                "iteration": 1,
                "summary": "Plan is in state 'aborted'.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_exit_kind": None,
    },
    # ── failed_terminal ────────────────────────────────────────────────
    {
        "name": "failed_terminal",
        "branch_ref": "failed_terminal",
        "mode": "immediate_terminal",
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "failed",
                "iteration": 1,
                "summary": "Plan is in state 'failed'.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_exit_kind": None,
    },
    # ── cancelled_terminal ─────────────────────────────────────────────
    {
        "name": "cancelled_terminal",
        "branch_ref": "cancelled",
        "mode": "immediate_terminal",
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "cancelled",
                "iteration": 1,
                "summary": "Plan is in state 'cancelled'.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_exit_kind": None,
    },
    # ── awaiting_human_prep ────────────────────────────────────────────
    {
        "name": "awaiting_human_prep",
        "branch_ref": "awaiting_human_prep",
        "mode": "immediate_terminal",
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "awaiting_human_verify",
                "iteration": 1,
                "summary": "Plan is awaiting human clarification (prep).",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_exit_kind": None,
        "state_json_patch": {
            "clarification": {
                "source": "prep",
                "questions": [
                    "Does the plan architecture align with the target repository?",
                    "Are the proposed changes technically sound?",
                ],
            },
        },
    },
    # ── awaiting_human_verify ──────────────────────────────────────────
    {
        "name": "awaiting_human_verify",
        "branch_ref": "awaiting_human_verify",
        "mode": "immediate_terminal",
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "awaiting_human_verify",
                "iteration": 1,
                "summary": "Plan is awaiting human verification.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_exit_kind": None,
    },
    # ── tiebreaker_pending ─────────────────────────────────────────────
    {
        "name": "tiebreaker_pending",
        "branch_ref": "tiebreaker_pending",
        "mode": "immediate_terminal",
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "tiebreaker_pending",
                "iteration": 1,
                "summary": "Tiebreaker pending — run to execute.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_exit_kind": None,
    },
    # ── tiebreaker_ready ───────────────────────────────────────────────
    {
        "name": "tiebreaker_ready",
        "branch_ref": "tiebreaker_ready",
        "mode": "immediate_terminal",
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "tiebreaker_ready",
                "iteration": 1,
                "summary": "Tiebreaker ready — awaiting human decision.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_exit_kind": None,
    },
    # ── paused ─────────────────────────────────────────────────────────
    {
        "name": "paused",
        "branch_ref": "paused",
        "mode": "immediate_terminal",
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "paused",
                "iteration": 1,
                "summary": "Plan is paused.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_exit_kind": None,
    },
    # ── blocked_terminal ───────────────────────────────────────────────
    {
        "name": "blocked_terminal",
        "branch_ref": "blocked_terminal",
        "mode": "immediate_terminal",
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "blocked",
                "iteration": 1,
                "summary": "Plan is blocked with no valid next steps.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_exit_kind": None,
    },
    # ── timeout ────────────────────────────────────────────────────────
    #
    # execute returns exit code 124 (PHASE_TIMEOUT_EXIT_CODE) with no
    # phase_result.json.  _run_phase synthesises ExitKind.timeout →
    # _record_failure(phase_timeout).  stall_threshold=1 fires on the
    # second status() call still in state "executing" → _outcome("stalled").
    {
        "name": "timeout",
        "branch_ref": "stalled",
        "mode": "stateful_run",
        "drive_kwargs": {"stall_threshold": 1},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 1,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 2,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
        ],
        # code=124 == PHASE_TIMEOUT_EXIT_CODE; no phase_result.json written
        "run_side_effects": [
            {"code": 124, "stdout": "", "stderr": "", "write_phase_result": None},
        ],
    },
    # ── idle_timeout ───────────────────────────────────────────────────
    #
    # NON-TERMINAL recovery: active_step has a very old last_activity_at
    # (always > DEFAULT_PHASE_IDLE_TIMEOUT_SECONDS=1800s in the past) →
    # _active_step_last_activity_stale returns True → recommended_action
    # set to "terminate_idle_step" → orphan-clear fires (event captured) →
    # first _run_planning_phase returns "idle timed out" in stderr with no
    # phase_result.json → synthesis ExitKind.timeout → _record_failure
    # (phase_timeout).  Second call writes success; third status "done".
    # _IDLE_SECONDS_RE normalises the non-deterministic idle_seconds value.
    {
        "name": "idle_timeout",
        "branch_ref": "done",
        "mode": "stateful_run",
        "drive_kwargs": {"stall_threshold": 10},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 1,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
                # recommended_action="wait" so the staleness check runs
                # (orphan_actions guard skips entries already marked
                # terminate_idle_step).
                "active_step": {
                    "phase": "execute",
                    "pid": 12345,
                    "last_activity_at": "2020-01-01T00:00:00+00:00",
                    "health": "unknown",
                    "recommended_action": "wait",
                },
            },
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 2,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
            {
                "success": True,
                "step": "status",
                "state": "done",
                "iteration": 3,
                "summary": "Plan is in state 'done'.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_side_effects": [
            # trigger_payload: "idle timed out" in stderr, no phase_result.json
            {"code": 0, "stdout": "", "stderr": "idle timed out after 1800s without output", "write_phase_result": None},
            # terminal_payload: clean execute → status returns done
            {"code": 0, "stdout": "{}", "stderr": "", "write_phase_result": "success"},
        ],
    },
    # ── context_retry_exhausted ────────────────────────────────────────
    #
    # side_effect=[ctx, ctx, ctx]: three context_exhausted PhaseResults.
    # First call from main dispatch.  Context-retry while-loop:
    #   context_retry_count=0 < max_context_retries=2 → retry → call 2
    #   context_retry_count=1 < 2 → retry → call 3
    #   context_retry_count=2 >= 2 → _record_failure + _outcome("context_retry_exhausted")
    # os.utime advances mtime +1s per write so _phase_result_signature
    # always detects a change on each _run_phase call.
    {
        "name": "context_retry_exhausted",
        "branch_ref": "context_retry_exhausted",
        "mode": "stateful_run",
        "drive_kwargs": {"max_context_retries": 2},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "finalized",
                "iteration": 1,
                "summary": "Plan is finalized — ready to execute.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
        ],
        "run_side_effects": [
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "context_exhausted"},
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "context_exhausted"},
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "context_exhausted"},
        ],
    },
    # ── external_retry_then_blocked ────────────────────────────────────
    #
    # One retryable transport_timeout on "finalize" (EXTERNAL_RETRYABLE_PHASES)
    # → PHASE_RETRY event emitted, second call hits cap
    # (phase_retry_count==1 >= DEFAULT_MAX_EXTERNAL_RETRIES=1) → loop breaks →
    # _record_failure(external_error, current_state=STATE_BLOCKED,
    # retry_strategy="check_provider_and_retry") → next status "blocked" →
    # _outcome("blocked", exit_code=5).
    {
        "name": "external_retry_then_blocked",
        "branch_ref": "blocked_terminal",
        "mode": "stateful_run",
        "drive_kwargs": {"max_external_retries": 1},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "executed",
                "iteration": 1,
                "summary": "Plan is in state 'executed'.",
                "next_step": "finalize",
                "valid_next": ["finalize"],
            },
            {
                "success": True,
                "step": "status",
                "state": "blocked",
                "iteration": 2,
                "summary": "Plan is blocked after external provider failure.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_side_effects": [
            # trigger: retryable transport_timeout on finalize → PHASE_RETRY
            {
                "code": 0,
                "stdout": "",
                "stderr": "",
                "write_phase_result": "external_error",
                "phase": "finalize",
                "external_error_kwargs": {
                    "provider": "anthropic",
                    "error_kind": "transport_timeout",
                    "error_layer": "transport_timeout",
                    "message": "stream stalled waiting for first content token",
                },
            },
            # cap hit: phase_retry_count==1 >= max_external_retries=1 → break
            {
                "code": 0,
                "stdout": "",
                "stderr": "",
                "write_phase_result": "external_error",
                "phase": "finalize",
                "external_error_kwargs": {
                    "provider": "anthropic",
                    "error_kind": "transport_timeout",
                    "error_layer": "transport_timeout",
                    "message": "stream stalled waiting for first content token",
                },
            },
        ],
    },
    # ── escalate_force_proceed ─────────────────────────────────────────
    #
    # on_escalate=force-proceed, override subprocess succeeds (code=0) →
    # continue → next status returns done → terminal outcome "done".
    # Characterizes the gate-escalate → force-proceed → continue → done path.
    {
        "name": "escalate_force_proceed",
        "branch_ref": "done",
        "mode": "stateful_run",
        "drive_kwargs": {"on_escalate": "force-proceed"},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "gated",
                "iteration": 1,
                "summary": "Plan is gated — no next step, escalate available.",
                "next_step": None,
                "valid_next": ["override force-proceed"],
            },
            {
                "success": True,
                "step": "status",
                "state": "done",
                "iteration": 2,
                "summary": "Plan is in state 'done'.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_side_effects": [
            # override force-proceed succeeds → continue
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": None},
        ],
    },
    # ── escalate_abort ─────────────────────────────────────────────────
    #
    # on_escalate=abort → override abort subprocess runs → _outcome("aborted").
    {
        "name": "escalate_abort",
        "branch_ref": "aborted_escalate",
        "mode": "stateful_run",
        "drive_kwargs": {"on_escalate": "abort"},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "gated",
                "iteration": 1,
                "summary": "Plan is gated — no next step, escalate available.",
                "next_step": None,
                "valid_next": ["override force-proceed"],
            },
        ],
        "run_side_effects": [
            # override abort subprocess (exit code irrelevant for abort path)
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": None},
        ],
    },
    # ── escalate_fail ──────────────────────────────────────────────────
    #
    # on_escalate=fail — no subprocess call → _outcome("escalated").
    # immediate_terminal because _run_planning_phase is never invoked.
    {
        "name": "escalate_fail",
        "branch_ref": "escalated",
        "mode": "immediate_terminal",
        "drive_kwargs": {"on_escalate": "fail"},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "gated",
                "iteration": 1,
                "summary": "Plan is gated — no next step, escalate available.",
                "next_step": None,
                "valid_next": ["override force-proceed"],
            },
        ],
        "run_exit_kind": None,
    },
    # ── escalate_strict_notes_blocked ───────────────────────────────────
    #
    # on_escalate=force-proceed but the override force-proceed subprocess
    # fails (code=1) with strict-note signal "escalate_requires_user_approval"
    # in stderr → _record_failure(human_required) → _outcome("human_required").
    {
        "name": "escalate_strict_notes_blocked",
        "branch_ref": "human_required",
        "mode": "stateful_run",
        "drive_kwargs": {"on_escalate": "force-proceed"},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "gated",
                "iteration": 1,
                "summary": "Plan is gated — no next step, escalate available.",
                "next_step": None,
                "valid_next": ["override force-proceed"],
            },
        ],
        "run_side_effects": [
            # override force-proceed fails with strict-note signal
            {
                "code": 1,
                "stdout": "",
                "stderr": "escalate_requires_user_approval: strict notes must be addressed before escalating",
                "write_phase_result": None,
            },
        ],
    },
    # ── blocked_retry_prereq ────────────────────────────────────────────
    #
    # PhaseResult(exit_kind=blocked_by_prereq, blocked_tasks=[BlockedTask])
    # at auto.py:2318-2359: non-empty blocked_tasks → awaiting_human outcome.
    # Does NOT consume a retry (blocked_retry_count stays 0).
    {
        "name": "blocked_retry_prereq",
        "branch_ref": "awaiting_human_blocked_prereq",
        "mode": "stateful_run",
        "drive_kwargs": {"max_blocked_retries": 1},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "finalized",
                "iteration": 1,
                "summary": "Plan finalized — ready to execute.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
        ],
        "run_side_effects": [
            {
                "code": 0,
                "stdout": "",
                "stderr": "",
                "write_phase_result": "blocked_by_prereq",
                "blocked_tasks_kwargs": [
                    {
                        "task_id": "task-1",
                        "reason": "prereq not met",
                        "notes": "T4 not yet done",
                    }
                ],
            },
        ],
    },
    # ── blocked_retry_quality_to_cap ────────────────────────────────────
    #
    # CANONICAL M3 ORACLE TRACE (oracle_role=replay+resume in MANIFEST).
    # PhaseResult(exit_kind=blocked_by_quality, deviations=[...]) repeated
    # until DEFAULT_MAX_BLOCKED_RETRIES=1 cap fires → worker_blocked.
    # AS-IS chain-blocked-retry bug per project_chain_blocked_retry_and_resume.
    #
    # Loop trace (max_blocked_retries=1):
    #   iter 1: blocked_retry_count=0 < 1 → retry (blocked_retry_count → 1)
    #   iter 2: blocked_retry_count=1 >= 1 → cap fires → worker_blocked
    #
    # events MUST capture the full retry loop for T11's substrate-swap test.
    {
        "name": "blocked_retry_quality_to_cap",
        "branch_ref": "worker_blocked_quality",
        "mode": "stateful_run",
        "drive_kwargs": {"max_blocked_retries": 1},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "finalized",
                "iteration": 1,
                "summary": "Plan finalized — ready to execute.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
            {
                "success": True,
                "step": "status",
                "state": "finalized",
                "iteration": 2,
                "summary": "Plan finalized — retrying blocked execute.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
        ],
        "run_side_effects": [
            # iter 1: blocked_by_quality → retry (blocked_retry_count → 1)
            {
                "code": 0,
                "stdout": "",
                "stderr": "",
                "write_phase_result": "blocked_by_quality",
                "deviations_kwargs": [
                    {
                        "kind": "quality_gate",
                        "message": "Reviewer identified critical flaw: test coverage insufficient",
                    }
                ],
            },
            # iter 2: blocked_by_quality → cap fires → worker_blocked
            {
                "code": 0,
                "stdout": "",
                "stderr": "",
                "write_phase_result": "blocked_by_quality",
                "deviations_kwargs": [
                    {
                        "kind": "quality_gate",
                        "message": "Reviewer identified critical flaw: test coverage insufficient",
                    }
                ],
            },
        ],
    },
    # ── stall_generic ───────────────────────────────────────────────────
    #
    # Same state for DEFAULT_STALL_THRESHOLD=5 consecutive iterations → stalled.
    # stall_count trace:
    #   iter 1: state!=last_state(None) → stall_count=0, last_state=executing
    #   iter 2-5: state==last_state → stall_count 1→4
    #   iter 6: stall_count=5 >= stall_threshold=5 → stalled (fires before execute)
    {
        "name": "stall_generic",
        "branch_ref": "stalled",
        "mode": "stateful_run",
        "drive_kwargs": {"stall_threshold": 5, "max_iterations": 10},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 1,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 2,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 3,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 4,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 5,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 6,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
        ],
        # 5 execute calls (iters 1-5); iter 6 hits stall cap before execute
        "run_side_effects": [
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "success"},
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "success"},
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "success"},
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "success"},
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "success"},
        ],
    },
    # ── all_tasks_blocked ───────────────────────────────────────────────
    #
    # tasks_blocked>0 and tasks_pending==0 at the stall cap → blocked terminal.
    # Same stall detection as stall_generic but discriminated by the poisoned-
    # outcome branch (tasks_blocked>0, tasks_pending==0) at auto.py:1758.
    # stall_count trace: same as stall_generic — fires on iter 6.
    {
        "name": "all_tasks_blocked",
        "branch_ref": "blocked_all_tasks",
        "mode": "stateful_run",
        "drive_kwargs": {"stall_threshold": 5, "max_iterations": 10},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 1,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
                "progress": {"tasks_blocked": 1, "tasks_pending": 0},
            },
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 2,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
                "progress": {"tasks_blocked": 1, "tasks_pending": 0},
            },
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 3,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
                "progress": {"tasks_blocked": 1, "tasks_pending": 0},
            },
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 4,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
                "progress": {"tasks_blocked": 1, "tasks_pending": 0},
            },
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 5,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
                "progress": {"tasks_blocked": 1, "tasks_pending": 0},
            },
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 6,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
                "progress": {"tasks_blocked": 1, "tasks_pending": 0},
            },
        ],
        # 5 execute calls (iters 1-5); iter 6 hits stall cap before execute
        "run_side_effects": [
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "success"},
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "success"},
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "success"},
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "success"},
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "success"},
        ],
    },
    # ── review_rework ───────────────────────────────────────────────────
    #
    # review.json mtime forward-progress triggers driver rework cap.
    # os.utime pins review.json mtime within the recipe; {{MTIME}}
    # normalization replaces the pinned values in any log output.
    #
    # Trace (max_review_rework_cycles=0):
    #   iter 1: review.json mtime=999999999.0 → last_review_marker set,
    #           rework_cycles_observed stays 0
    #   iter 2: review.json mtime=1000000000.0 → rework_cycles=1
    #           (1 > 0+1? No)
    #   iter 3: review.json mtime=1000000001.0 → rework_cycles=2
    #           (2 > 0+1? Yes) → _outcome("stalled")
    {
        "name": "review_rework",
        "branch_ref": "stalled_review_rework",
        "mode": "stateful_run",
        "drive_kwargs": {
            "max_review_rework_cycles": 0,
            "stall_threshold": 10,
            "max_iterations": 10,
        },
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 1,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 2,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 3,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
        ],
        # review.json is pre-created at plan_dir with mtime=999999999.0.
        # Each run_side_effect advances it by +1s via os.utime.
        "run_side_effects": [
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "success", "review_mtime": 1000000000.0},
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "success", "review_mtime": 1000000001.0},
        ],
        "review_json_initial_mtime": 999999999.0,
    },
    # ── cost_cap_exceeded ───────────────────────────────────────────────
    #
    # state.json history entries sum to > max_cost_usd=0.01 → cap fires
    # before dispatch (L1497-1525).  immediate_terminal: _run_planning_phase
    # never called.
    {
        "name": "cost_cap_exceeded",
        "branch_ref": "cost_cap_exceeded",
        "mode": "immediate_terminal",
        "drive_kwargs": {"max_cost_usd": 0.01},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 1,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
        ],
        "run_exit_kind": None,
        "state_json_patch": {
            "history": [
                {"step": "plan", "cost_usd": 0.05, "result": "success"},
                {"step": "execute", "cost_usd": 0.10, "result": "success"},
            ],
        },
    },
    # ── add_note_force_proceed ──────────────────────────────────────────
    #
    # max_add_note_attempts=0 → add_note_attempts(0) >= 0 fires on first
    # occurrence of next_step="override add-note".  Driver runs override
    # force-proceed (code=0) → continue → next status returns done.
    {
        "name": "add_note_force_proceed",
        "branch_ref": "done",
        "mode": "stateful_run",
        "drive_kwargs": {"max_add_note_attempts": 0},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 1,
                "summary": "Plan is in state 'executing' with add-note pending.",
                "next_step": "override add-note",
                "valid_next": ["override add-note", "override force-proceed"],
            },
            {
                "success": True,
                "step": "status",
                "state": "done",
                "iteration": 2,
                "summary": "Plan is in state 'done'.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_side_effects": [
            # override force-proceed succeeds
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": None},
        ],
    },
    # ── add_note_force_proceed_after_repeats ───────────────────────────
    #
    # Repeated successful `override add-note` dispatches that leave the plan
    # on the same override path should also escalate once the retry budget is
    # exhausted. This mirrors critique loops where note injection succeeds but
    # does not move the state machine forward.
    {
        "name": "add_note_force_proceed_after_repeats",
        "branch_ref": "done",
        "mode": "stateful_run",
        "drive_kwargs": {"max_add_note_attempts": 2},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "critiqued",
                "iteration": 1,
                "summary": "Plan is in state 'critiqued' with add-note pending.",
                "next_step": "override add-note",
                "valid_next": ["override add-note", "override force-proceed"],
            },
            {
                "success": True,
                "step": "status",
                "state": "critiqued",
                "iteration": 2,
                "summary": "Plan is in state 'critiqued' with add-note pending.",
                "next_step": "override add-note",
                "valid_next": ["override add-note", "override force-proceed"],
            },
            {
                "success": True,
                "step": "status",
                "state": "critiqued",
                "iteration": 3,
                "summary": "Plan is in state 'critiqued' with add-note pending.",
                "next_step": "override add-note",
                "valid_next": ["override add-note", "override force-proceed"],
            },
            {
                "success": True,
                "step": "status",
                "state": "done",
                "iteration": 4,
                "summary": "Plan is in state 'done'.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_side_effects": [
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": None},
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": None},
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": None},
        ],
    },
    # ── orphan_recovery ─────────────────────────────────────────────────
    #
    # active_step with recommended_action="resume_or_recover" (in
    # orphan_actions set) → _clear_orphaned_active_step clears it from
    # state.json + _quarantine_phase_outputs (no-op for execute since no
    # quarantine entries).  After clearing, dispatch execute normally →
    # success → terminal done.
    {
        "name": "orphan_recovery",
        "branch_ref": "done",
        "mode": "stateful_run",
        "drive_kwargs": {"stall_threshold": 10, "max_iterations": 10},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 1,
                "summary": "Plan is in state 'executing' with orphaned active step.",
                "next_step": "execute",
                "valid_next": ["execute"],
                "active_step": {
                    "phase": "execute",
                    "pid": 12345,
                    "health": "dead",
                    "recommended_action": "resume_or_recover",
                    "recommended_action_reason": "worker process is dead, must clear before redispatch",
                },
            },
            {
                "success": True,
                "step": "status",
                "state": "done",
                "iteration": 2,
                "summary": "Plan is in state 'done'.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_side_effects": [
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "success"},
        ],
    },
    # ── auto_escalate_up ────────────────────────────────────────────────
    #
    # NON-TERMINAL compound: 2 consecutive internal_error execute failures
    # trigger tier escalation (escalate_after_fails=2, DEFAULT_ESCALATE_AFTER_FAILS).
    # Escalation event fires on iteration 2 (execute_fail_streak=2 >= 2),
    # streak resets to 0; a clean execute on iteration 3 produces done.
    #
    # Tier ladder written into state.json config (tier 1: haiku, tier 2: opus)
    # so _next_escalation_tier returns (2, "claude-opus-4-8") and the
    # "escalating execute UP" log entry appears in outcome.events.
    #
    # side_effect=[internal_error, internal_error, success]:
    #   iter 1 execute: internal_error → streak=1 < 2 → no escalation
    #   iter 2 execute: internal_error → streak=2 >= 2 → escalation fires →
    #                   logs "escalating execute UP: tier None→2" → streak=0
    #   iter 3 execute: success → iter 4 status returns done → terminal
    {
        "name": "auto_escalate_up",
        "branch_ref": "done",
        "mode": "stateful_run",
        "drive_kwargs": {
            "stall_threshold": 5,
            "max_iterations": 5,
            "escalate_after_fails": 2,
        },
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 1,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 2,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 3,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
            {
                "success": True,
                "step": "status",
                "state": "done",
                "iteration": 4,
                "summary": "Plan is in state 'done'.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_side_effects": [
            # iter 1 execute: internal_error → streak=1, no escalation yet
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "internal_error"},
            # iter 2 execute: internal_error → streak=2 >= 2 → escalation fires
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "internal_error"},
            # iter 3 execute: success → iter 4 status returns done → terminal
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "success"},
        ],
        # Tier ladder: _next_escalation_tier(current_tier=None) climbs from
        # the floor (tier 1) to the next distinct model (tier 2 = opus).
        "state_json_patch": {
            "config": {
                "tier_models": {
                    "execute": {
                        "1": "claude-haiku-4-5-20251001",
                        "2": "claude-opus-4-8",
                    }
                }
            }
        },
    },
    # ── plan_locked_skip_continue ───────────────────────────────────────
    #
    # NON-TERMINAL compound: internal_error phase_result with "plan_locked"
    # in stderr is treated as transient contention (no _record_failure call,
    # no streak increment that matters) and the loop retries the next
    # iteration.  A sentinel finalize (DIFFERENT step_name than the trigger
    # "execute") then completes the plan → done.
    #
    # Using step_name "finalize" for the sentinel avoids phase_result.json
    # re-detection: the sentinel writes content with phase="finalize" and
    # exit_kind=success, guaranteeing a distinct signature from the trigger's
    # phase="execute" + exit_kind=internal_error content.
    #
    # side_effect=[plan_locked_internal_error, finalize_success]:
    #   iter 1 execute: internal_error + plan_locked stderr → skip-continue log
    #   iter 2 finalize (sentinel): success → iter 3 status returns done
    {
        "name": "plan_locked_skip_continue",
        "branch_ref": "done",
        "mode": "stateful_run",
        "drive_kwargs": {
            "stall_threshold": 5,
            "max_iterations": 5,
        },
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 1,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
            # After the plan_locked skip, the concurrent lock is released
            # and state advances to executed → finalize is the sentinel step.
            {
                "success": True,
                "step": "status",
                "state": "executed",
                "iteration": 2,
                "summary": "Plan is in state 'executed'.",
                "next_step": "finalize",
                "valid_next": ["finalize"],
            },
            {
                "success": True,
                "step": "status",
                "state": "done",
                "iteration": 3,
                "summary": "Plan is in state 'done'.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_side_effects": [
            # Trigger: internal_error with "plan_locked" in stderr.
            # Driver detects plan_locked → logs skip-continue, NO _record_failure.
            # step_name is "execute" (via default phase="execute").
            {
                "code": 0,
                "stdout": "",
                "stderr": "plan_locked: concurrent plan modification detected",
                "write_phase_result": "internal_error",
            },
            # Sentinel: success for phase="finalize" — DIFFERENT step_name
            # than the trigger ("execute") to guarantee distinct phase_result.json
            # signature and avoid re-detection at the _run_phase before/after
            # signature comparison.
            {
                "code": 0,
                "stdout": "",
                "stderr": "",
                "write_phase_result": "success",
                "phase": "finalize",
            },
        ],
    },
    # ── infrastructure_error ────────────────────────────────────────────
    #
    # Phase subprocess reports internal_error and stderr contains a
    # non-retryable infrastructure CliError (engine_write_isolation_unverified).
    # auto.py:3659-3708 routes this to an infrastructure_error outcome.
    {
        "name": "infrastructure_error",
        "branch_ref": "infrastructure_error",
        "mode": "stateful_run",
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "finalized",
                "iteration": 1,
                "summary": "Plan finalized — ready to execute.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
        ],
        "run_side_effects": [
            {
                "code": 0,
                "stdout": "",
                "stderr": (
                    '{"error": "engine_write_isolation_unverified", '
                    '"message": "engine write isolation is not verified"}'
                ),
                "write_phase_result": "internal_error",
            },
        ],
    },
    # ── execute_callback_failure_recovery ───────────────────────────────
    #
    # _recover_execute_callback_failure_state(L1033-1081) reachable as a
    # distinct trace.  state.json is pre-seeded with current_state=failed,
    # latest_failure.kind=phase_callback_failed with
    # checkpoint_reconciliation.reconciled=True, history has an execute
    # step with result=success, and execution.json exists.  Recovery
    # patches state→executed, clears active_step, and continues → dispatch
    # finalize → done.
    {
        "name": "execute_callback_failure_recovery",
        "branch_ref": "done",
        "mode": "stateful_run",
        "drive_kwargs": {"stall_threshold": 10, "max_iterations": 10},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "failed",
                "iteration": 1,
                "summary": "Plan is in state 'failed' — recovery pending.",
                "next_step": None,
                "valid_next": [],
            },
            {
                "success": True,
                "step": "status",
                "state": "executed",
                "iteration": 2,
                "summary": "Plan is in state 'executed' after recovery.",
                "next_step": "finalize",
                "valid_next": ["finalize"],
            },
            {
                "success": True,
                "step": "status",
                "state": "done",
                "iteration": 3,
                "summary": "Plan is in state 'done'.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_side_effects": [
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "success", "phase": "finalize"},
        ],
        "state_json_patch": {
            "current_state": "failed",
            "latest_failure": {
                "kind": "phase_callback_failed",
                "phase": "execute",
                "message": "phase-complete callback failed after 'execute': test error",
                "metadata": {
                    "checkpoint_reconciliation": {"reconciled": True},
                },
            },
            "history": [
                {"step": "execute", "result": "success", "cost_usd": 0.01},
            ],
            "active_step": None,
        },
        "plan_dir_files": {
            "execution.json": "{}",
        },
    },
    # ── R4-addition: status_lookup_failed ───────────────────────────────
    #
    # _status() raises RuntimeError (per gate issue_hints-6).
    # Hits the except (RuntimeError, json.JSONDecodeError) block at L1475.
    # _record_failure(kind="status_lookup_failed") → _outcome("failed").
    # immediate_terminal because _run_planning_phase is never invoked.
    {
        "name": "status_lookup_failed",
        "branch_ref": "status_lookup_failed",
        "mode": "immediate_terminal",
        "status_raises": True,
        "status_sequence": [],
        "run_exit_kind": None,
    },
    # ── R4-addition: no_next_step_no_override ───────────────────────────
    #
    # _status returns a non-terminal state with no next_step and
    # valid_next without "override force-proceed" → _has_valid_next
    # returns False → escalate block skipped → _record_failure
    # (kind="no_next_step") → _outcome("failed") at L1947.
    {
        "name": "no_next_step_no_override",
        "branch_ref": "no_next_step_no_override",
        "mode": "immediate_terminal",
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "processing",
                "iteration": 1,
                "summary": "Plan is in state 'processing' with no next step and no override.",
                "next_step": None,
                "valid_next": [],
            },
        ],
        "run_exit_kind": None,
    },
    # ── R4-addition: phase_callback_failed ──────────────────────────────
    #
    # on_phase_complete callback raises after a successful execute.
    # Hits L2275-2306 guard: code==0, on_phase_complete is set,
    # next_step="execute" → callback invoked → raises Exception →
    # _record_failure(kind="phase_callback_failed") → _outcome("failed").
    # stateful_run: one _run_planning_phase call writes success, then callback
    # failure terminates the loop.
    {
        "name": "phase_callback_failed",
        "branch_ref": "phase_callback_failed",
        "mode": "stateful_run",
        "drive_kwargs": {
            "stall_threshold": 10,
            "max_iterations": 5,
            "on_phase_complete": "raise",
        },
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 1,
                "summary": "Plan is in state 'executing' — callback will raise.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
        ],
        "run_side_effects": [
            {"code": 0, "stdout": "{}", "stderr": "", "write_phase_result": "success"},
        ],
    },
    # ── R4-addition: iteration_cap ──────────────────────────────────────
    #
    # max_iterations=1; loop runs one execute iteration (iteration 0),
    # then iteration becomes 1 which fails the while condition
    # (1 < 1) → exits → hits iteration cap at L2634 →
    # _record_failure(kind="iteration_cap") → _outcome("cap").
    {
        "name": "iteration_cap",
        "branch_ref": "iteration_cap",
        "mode": "stateful_run",
        "drive_kwargs": {
            "stall_threshold": 10,
            "max_iterations": 1,
        },
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "executing",
                "iteration": 1,
                "summary": "Plan is in state 'executing'.",
                "next_step": "execute",
                "valid_next": ["execute"],
            },
        ],
        "run_side_effects": [
            {"code": 0, "stdout": "", "stderr": "", "write_phase_result": "success"},
        ],
    },
    # ── R4-addition: force_proceed_failed ──────────────────────────────
    #
    # on_escalate="force-proceed" with valid_next containing
    # "override force-proceed".  The override force-proceed subprocess
    # exits code=1 with NO strict-note signals in stderr → the
    # strict-signals check (L1851-1855) fails → _record_failure
    # (kind="override_failed") → _outcome("failed") at L1886.
    {
        "name": "force_proceed_failed",
        "branch_ref": "force_proceed_failed",
        "mode": "stateful_run",
        "drive_kwargs": {"on_escalate": "force-proceed"},
        "status_sequence": [
            {
                "success": True,
                "step": "status",
                "state": "gated",
                "iteration": 1,
                "summary": "Plan is gated — no next step, override available.",
                "next_step": None,
                "valid_next": ["override force-proceed"],
            },
        ],
        "run_side_effects": [
            {
                "code": 1,
                "stdout": "",
                "stderr": "override force-proceed failed: generic subprocess error",
                "write_phase_result": None,
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plan_dir(tmp_path: Path, plan: str) -> Path:
    """Create a skeletal plan dir that ``_resolve_plan_dir`` can locate."""
    plan_dir = tmp_path / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": plan, "current_state": "finalized"}),
        encoding="utf-8",
    )
    return plan_dir


# ---------------------------------------------------------------------------
# Parametrized branch test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("recipe", _GOLDEN_RECIPES, ids=[r["name"] for r in _GOLDEN_RECIPES])
def test_auto_drive_branch(
    recipe: dict[str, Any],
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Drive a single branch seam and snapshot the normalized outcome."""
    from tests.conftest import fake_run_with_phase_result

    plan = recipe["name"].replace("_", "-")
    plan_dir = _make_plan_dir(tmp_path, plan)

    # ── Apply optional state.json patch (e.g. clarification for prep) ──
    state_patch = recipe.get("state_json_patch")
    if state_patch is not None:
        state_path = plan_dir / "state.json"
        current_state = json.loads(state_path.read_text(encoding="utf-8"))
        current_state.update(state_patch)
        state_path.write_text(
            json.dumps(current_state, indent=2), encoding="utf-8"
        )

    # ── Pre-create extra files in plan_dir (e.g. execution.json) ─────
    plan_dir_files: dict[str, str] = recipe.get("plan_dir_files", {})
    for fname, content in plan_dir_files.items():
        (plan_dir / fname).write_text(content, encoding="utf-8")

    # ── Pre-create review.json with pinned mtime (review_rework) ─────
    review_json_initial_mtime = recipe.get("review_json_initial_mtime")
    if review_json_initial_mtime is not None:
        rj = plan_dir / "review.json"
        rj.write_text(
            json.dumps({"rework_count": 0, "needs_rework": True}),
            encoding="utf-8",
        )
        os.utime(rj, (review_json_initial_mtime, review_json_initial_mtime))

    # ── Install determinism ────────────────────────────────────────────
    sidecar = _install_determinism(monkeypatch)

    # ── Mock _status ───────────────────────────────────────────────────
    status_raises = recipe.get("status_raises", False)
    if status_raises:
        def _fake_status_raises(_plan: str, cwd=None, timeout=60, progress_env=None):
            raise RuntimeError("test forced status lookup failure")
        monkeypatch.setattr(auto, "_status", _fake_status_raises)
    else:
        status_iter = iter(recipe["status_sequence"])

        def _fake_status(_plan: str, cwd=None, timeout=60, progress_env=None):
            try:
                return next(status_iter)
            except StopIteration:
                # If the loop asks for more statuses than we provided, return
                # the last one repeatedly (the terminal guard should prevent this).
                return recipe["status_sequence"][-1]

        monkeypatch.setattr(auto, "_status", _fake_status)

    # ── Mock _run_planning_phase ─────────────────────────────────────────────
    mode = recipe["mode"]
    if mode == "execute_then_terminal":
        runner = fake_run_with_phase_result(
            plan_dir,
            exit_kind=recipe["run_exit_kind"],
            code=0,
            stdout="{}",
            stderr="",
        )
    elif mode == "stateful_run":
        from tests.conftest import make_fake_phase_result
        from arnold_pipelines.megaplan.orchestration.phase_result import BlockedTask as _BlockedTask
        from arnold_pipelines.megaplan.orchestration.phase_result import Deviation as _Deviation
        from arnold_pipelines.megaplan.orchestration.phase_result import ExternalError as _ExternalError

        run_effects = recipe.get("run_side_effects", [])
        _call_idx: dict[str, int] = {"n": 0}

        def _stateful_runner(
            cmd: list[str],
            *,
            cwd=None,
            timeout=None,
            idle_timeout=None,
            progress_env=None,
            liveness_plan_dir=None,
        ) -> tuple[int, str, str]:
            idx = _call_idx["n"]
            _call_idx["n"] += 1
            if idx >= len(run_effects):
                return 0, "", ""
            effect = run_effects[idx]
            if effect.get("write_phase_result"):
                ext_err = None
                ext_kw = effect.get("external_error_kwargs")
                if ext_kw:
                    ext_err = _ExternalError(**ext_kw)
                bt_kw = effect.get("blocked_tasks_kwargs", [])
                dv_kw = effect.get("deviations_kwargs", [])
                make_fake_phase_result(
                    plan_dir,
                    phase=effect.get("phase", "execute"),
                    exit_kind=effect["write_phase_result"],
                    external_error=ext_err,
                    blocked_tasks=tuple(_BlockedTask(**kw) for kw in bt_kw),
                    deviations=tuple(_Deviation(**kw) for kw in dv_kw),
                )
                # Advance mtime by 1s per call so _phase_result_signature
                # always detects a genuine change (guards against sub-second
                # filesystem resolution on rapid consecutive writes).
                pr = plan_dir / "phase_result.json"
                _st = pr.stat()
                os.utime(pr, (_st.st_atime + 1, _st.st_mtime + 1))
            # ── Advance review.json mtime (review_rework golden) ─────
            review_mtime = effect.get("review_mtime")
            if review_mtime is not None:
                rj = plan_dir / "review.json"
                if rj.exists():
                    os.utime(rj, (review_mtime, review_mtime))
            return effect["code"], effect["stdout"], effect["stderr"]

        runner = _stateful_runner
    else:
        # immediate_terminal: _run_planning_phase should never be called.
        def _no_run(*args, **kwargs):
            pytest.fail(
                f"_run_planning_phase unexpectedly called in "
                f"'{recipe['name']}' (mode={mode})"
            )

        runner = _no_run

    monkeypatch.setattr(auto, "_run_planning_phase", runner)

    def _override_force_proceed_runner(*, root, plan, reason, user_approved=False):
        return runner(
            [
                "override",
                "force-proceed",
                "--plan",
                plan,
                "--reason",
                reason,
            ],
            cwd=root,
        )

    def _override_abort_runner(*, root, plan, reason):
        return runner(
            ["override", "abort", "--plan", plan, "--reason", reason],
            cwd=root,
        )

    monkeypatch.setattr(
        auto,
        "_override_force_proceed_in_process",
        _override_force_proceed_runner,
    )
    monkeypatch.setattr(auto, "_override_abort_in_process", _override_abort_runner)

    # ── Drive ──────────────────────────────────────────────────────────
    drive_kwargs = recipe.get("drive_kwargs", {})
    on_phase_complete_cb = drive_kwargs.get("on_phase_complete")
    if on_phase_complete_cb == "raise":
        def _raise_callback(_phase: str, _code: int, _out: str, _err: str) -> None:
            raise RuntimeError("phase-complete callback failed: test error")
        on_phase_complete_cb = _raise_callback
    outcome = auto.drive(
        plan,
        cwd=tmp_path,
        stall_threshold=drive_kwargs.get("stall_threshold", 10),
        max_iterations=drive_kwargs.get("max_iterations", 5),
        max_review_rework_cycles=drive_kwargs.get("max_review_rework_cycles", 10),
        max_cost_usd=drive_kwargs.get("max_cost_usd"),
        max_context_retries=drive_kwargs.get("max_context_retries", auto.DEFAULT_MAX_CONTEXT_RETRIES),
        max_external_retries=drive_kwargs.get("max_external_retries", auto.DEFAULT_MAX_EXTERNAL_RETRIES),
        max_blocked_retries=drive_kwargs.get("max_blocked_retries", auto.DEFAULT_MAX_BLOCKED_RETRIES),
        max_add_note_attempts=drive_kwargs.get("max_add_note_attempts", auto.DEFAULT_MAX_ADD_NOTE_ATTEMPTS),
        escalate_after_fails=drive_kwargs.get("escalate_after_fails", auto.DEFAULT_ESCALATE_AFTER_FAILS),
        on_escalate=drive_kwargs.get("on_escalate", "force-proceed"),
        on_phase_complete=on_phase_complete_cb,
        poll_sleep=0,
        push=False,
        writer=lambda _m: None,
    )

    # ── Build exit code via run_auto mapping ───────────────────────────
    branch = next(b for b in _BRANCHES if b["name"] == recipe["branch_ref"])
    exit_code = branch["expected_exit_code"]

    # ── Snapshot & assert ──────────────────────────────────────────────
    events: list[dict[str, Any]] = outcome.events
    snapshot = _normalize_outcome(outcome, events, exit_code, sidecar, tmp_path)
    _assert_or_write(recipe["name"], snapshot, request)


# ---------------------------------------------------------------------------
# Mapping from _record_failure kind= literals to _BRANCHES entry names.
#
# Some ``_record_failure(kind="...")`` values do not appear directly as an
# ``exit_kind_or_status`` in ``_BRANCHES`` (they are non-terminal internal
# events).  This table maps each such kind literal to the **_BRANCHES
# ``name``** of the entry whose golden recipe exercises that code path, so
# the coverage test (``test_auto_drive_corpus_covers_every_outcome_branch``)
# can verify that every literal extracted from the source is covered.
# ---------------------------------------------------------------------------

_KIND_TO_BRANCH: dict[str, str] = {
    "status_lookup_failed": "status_lookup_failed",
    "tasks_blocked": "blocked_all_tasks",
    "override_failed": "force_proceed_failed",
    "gate_escalated": "escalated",
    "no_next_step": "no_next_step_no_override",
    "phase_timeout": "stalled",
    "external_error": "blocked_terminal",
    "phase_failed": "failed_terminal",
    "phase_callback_failed": "phase_callback_failed",
    "execution_blocked": "worker_blocked_quality",
    "iteration_cap": "iteration_cap",
    # The following kind= values are also _outcome status= values, so they
    # match exit_kind_or_status directly without needing this mapping:
    #   cost_cap_exceeded, stalled, human_required, context_retry_exhausted
}


# ---------------------------------------------------------------------------
# auto_drive_corpus() fixture — returns parsed manifest + corpus path for M3
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def auto_drive_corpus() -> dict[str, Any]:
    """Return the parsed MANIFEST and the corpus directory path.

    M3 (substrate-swap) tests can import or request this fixture to
    discover every committed golden, its ``auto_py_branch_line``,
    ``oracle_role``, and the corresponding ``.json`` file on disk.
    """
    manifest_path = CORPUS_DIR / "MANIFEST.json"
    if not manifest_path.exists():
        pytest.fail(f"MANIFEST.json not found at {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Resolve corpus filenames to absolute paths so consumers don't
    # need to know the directory layout.
    for entry in manifest.get("goldens", []):
        fn = entry.get("corpus_filename")
        if fn:
            entry["_corpus_path"] = str(CORPUS_DIR / fn)
    return {"manifest": manifest, "corpus_dir": str(CORPUS_DIR)}


# ---------------------------------------------------------------------------
# Oracle gate test — coverage proof
# ---------------------------------------------------------------------------


def test_auto_drive_corpus_covers_every_outcome_branch() -> None:
    """Assert every ``_outcome(status=…)`` and ``_record_failure(kind=…)``
    literal in ``megaplan/auto.py`` is exercised by ≥1 entry in ``_BRANCHES``.

    Greps the **source** file (not ``_BRANCHES`` itself), builds the union
    set of status / kind literals, maps each one to a ``_BRANCHES`` entry
    name (via ``exit_kind_or_status`` or ``_KIND_TO_BRANCH``), and fails
    with the missing literal name if any branch is uncovered.
    """
    auto_py_path = Path(__file__).resolve().parents[2] / "arnold_pipelines" / "megaplan" / "auto.py"
    source = auto_py_path.read_text(encoding="utf-8")

    # ── Extract every _outcome("X"  status literal ─────────────────────
    # Matches the first positional string arg:  _outcome("X"
    status_literals: set[str] = set(
        re.findall(r'_outcome\(\s*"([^"]+)"', source)
    )

    # ── Also capture the terminal_status dict values at L1599-1605 ─────
    # Pattern:  STATE_XXX: "value"  inside the terminal_status = {...} block
    terminal_dict_values: set[str] = set(
        re.findall(
            r'terminal_status\s*=\s*\{[^}]*?\}',
            source,
            re.DOTALL,
        )
    )
    for block in terminal_dict_values:
        status_literals.update(re.findall(r':\s*"([^"]+)"', block))

    # ── Extract every kind="X" literal from _record_failure calls ─────
    # We find all kind="X" patterns.  In auto.py these only appear inside
    # _record_failure(…) calls, but we filter false positives by requiring
    # the line to also mention _record (the internal wrapper) or
    # _record_lifecycle_failure.
    kind_literals: set[str] = set()
    for lineno, line in enumerate(source.splitlines(), start=1):
        # Skip the function definition itself (line ~1356)
        if "_record_failure" not in line and "_record_lifecycle_failure" not in line:
            continue
        m = re.search(r'kind\s*=\s*"([^"]+)"', line)
        if m:
            kind_literals.add(m.group(1))

    # ── Union ──────────────────────────────────────────────────────────
    all_literals = status_literals | kind_literals

    # ── Build the set of covered values ─────────────────────────────────
    # Every _BRANCHES entry has either ``exit_kind_or_status`` or ``name``
    # that corresponds to a literal.
    branch_names: set[str] = {b["name"] for b in _BRANCHES}
    branch_exit_kinds: set[str] = {
        b["exit_kind_or_status"] for b in _BRANCHES
    }

    # ── Check coverage ─────────────────────────────────────────────────
    uncovered: list[str] = []
    for literal in sorted(all_literals):
        # Direct match on exit_kind_or_status (handles _outcome status values
        # and kind values that mirror status names)
        if literal in branch_exit_kinds:
            continue
        # Indirect match via _KIND_TO_BRANCH mapping
        mapped_branch = _KIND_TO_BRANCH.get(literal)
        if mapped_branch is not None and mapped_branch in branch_names:
            continue
        uncovered.append(literal)

    if uncovered:
        pytest.fail(
            "Coverage gap — the following status / kind literals from "
            f"megaplan/auto.py have no corresponding _BRANCHES entry:\n\n"
            + "\n".join(f"  • {v!r}" for v in uncovered)
            + "\n\nAdd the missing recipe(s) to _GOLDEN_RECIPES and "
            "update MANIFEST.json."
        )


# ---------------------------------------------------------------------------
# Oracle gate test — M3 replay hook (simulated R1 boundary)
# ---------------------------------------------------------------------------


def test_blocked_retry_then_resume_replays_across_simulated_r1_boundary() -> None:
    """Load the canonical M3 oracle trace (``blocked_retry_quality_to_cap``)
    and replay its captured ``events`` through a thin in-process re-driver
    that reads **only** ``state.json`` (the simulated 'R1 authoritative'
    read path).

    Asserts equality of ``resume_cursor`` and ``current_state`` across the
    two read paths (NOT full fold-equivalence — that's M3's job per
    assumption 7 in plan metadata).
    """
    golden_path = CORPUS_DIR / "blocked_retry_quality_to_cap.json"
    if not golden_path.exists():
        pytest.skip(
            "blocked_retry_quality_to_cap.json not found — "
            "regenerate with: pytest tests/characterization/test_auto_drive.py --write-fixture"
        )

    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    events: list[dict[str, Any]] = golden.get("events", [])
    outcome: dict[str, Any] = golden.get("outcome", {})

    # ── Path 1 — values from the committed golden (the "actual" path) ──
    golden_resume_cursor = outcome.get("resume_cursor")
    golden_current_state = outcome.get("current_state")

    # ── Path 2 — thin in-process re-driver that reads ONLY state.json ──
    #
    # The simulated "R1 authoritative" read reconstructs what M3 would see
    # by scanning state-derived information from the event log.  We extract:
    # * current_state  → the last state value seen in a status event
    # * resume_cursor  → built from the last phase that was in progress
    #
    # This simulates reading state.json without depending on any
    # DriverOutcome attributes (per SD3).

    last_state: str | None = None
    last_phase: str | None = None
    terminal_state: str | None = None  # inferred from terminal-condition events

    for ev in events:
        s = ev.get("state")
        if s is not None:
            last_state = s
        p = ev.get("phase")
        if p is not None:
            last_phase = p
        # Detect terminal conditions that update current_state beyond the
        # last status event.  A "bailing" message or retry-cap-reached
        # event means _record_lifecycle_failure wrote STATE_BLOCKED.
        msg = ev.get("msg", "")
        if "retry cap reached" in msg or "bailing" in msg:
            terminal_state = "blocked"
        elif "stalled" in msg:
            terminal_state = "blocked" if "poisoned" in msg else None

    # The authoritative current_state is the terminal-state override
    # (derived from lifecycle-failure events), falling back to the last
    # status-event state.
    replayed_current_state = terminal_state if terminal_state is not None else last_state

    # Build a simulated resume_cursor from event-derived data.
    # The golden's resume_cursor has {phase, batch_index, retry_strategy}.
    # We can derive phase from the last dispatch event; batch_index is
    # None (default); retry_strategy is always "fresh_session" for
    # blocked-by-quality cap paths.
    replayed_resume_cursor: dict[str, Any] | None = None
    if last_phase is not None:
        replayed_resume_cursor = {
            "phase": last_phase,
            "batch_index": None,
            "retry_strategy": "fresh_session",
        }

    # ── Assertions ─────────────────────────────────────────────────────
    assert (
        replayed_resume_cursor == golden_resume_cursor
    ), (
        f"resume_cursor mismatch across R1 boundary:\n"
        f"  replayed (from events): {replayed_resume_cursor}\n"
        f"  golden  (from outcome): {golden_resume_cursor}"
    )

    assert (
        replayed_current_state == golden_current_state
    ), (
        f"current_state mismatch across R1 boundary:\n"
        f"  replayed (from events): {replayed_current_state!r}\n"
        f"  golden  (from outcome): {golden_current_state!r}"
    )
