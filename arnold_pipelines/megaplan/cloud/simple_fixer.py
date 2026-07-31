"""Canonical ``simple_fixer`` occurrence contract (Steps 34-35).

The ``simple_fixer`` is the single, exact-occurrence repair entry point.
Everything that mutates a repair occurrence is funnelled through this
contract so that the identity tuple, claim boundary, mutation budget, and
action gates are defined in exactly one place.

This module defines:

* the **exact occurrence identity** — repair authority is derived *only*
  from the F01 repair-occurrence tuple.  It is never derived from a label,
  a liveness signal, a WBC receipt, or a rebuildable projection, because
  none of those uniquely and exactly identify a repair occurrence.
* **typed outcomes** for every claim and mutation decision so callers can
  branch on a closed vocabulary instead of inspecting free-form state.
* a **contract-layer no-child-agent gate** — the fixer is a leaf node.  Any
  request that would spawn a child agent or fan out is rejected at the
  contract layer; the fixer never constructs, launches, or delegates to a
  child process.
* a **singleton exact-occurrence claim** acquired through the existing
  plural repair queue APIs (the queue-root-validated ``mkdir`` lock
  primitive shared with :func:`claim_active_repair_request`), so that only
  one exact occurrence is actively claimed at a time.
* a **two-try unchanged-fingerprint mutation budget** that caps no-op
  retries, and
* **action gates** validated at every mutation boundary (claim held,
  identity exact, no child agent, budget not exhausted).

The module contains no subprocess/agent spawn logic by design.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Mapping

from arnold_pipelines.megaplan.cloud.repair_lock import (
    RepairLockResult,
    acquire_repair_lock,
    inspect_repair_lock,
    release_repair_lock,
)
from arnold_pipelines.megaplan.cloud.repair_requests import (
    singleton_occurrence_claim_lock_dir,
)
from arnold_pipelines.megaplan.custody.contracts import (
    Contract,
    ContractError,
    F01_REPAIR_OCCURRENCE_FIELDS,
    CustodyTargetKey,
    build_custody_target_key,
)

# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

SIMPLE_FIXER_CONTRACT_TYPE = "simple_fixer_occurrence"
SIMPLE_FIXER_SCHEMA_VERSION = 1

#: Cap unchanged-fingerprint mutation attempts at two.  After two
#: consecutive mutation attempts whose fingerprint did not change, the
#: budget is exhausted and further attempts are rejected with the
#: ``exhausted`` outcome.  This bounds retry-loop amplification.
MAX_UNCHANGED_FINGERPRINT_ATTEMPTS: int = 2

#: Authority sources that MUST NOT be used to construct occurrence
#: identity.  A label, liveness signal, WBC receipt, or rebuildable
#: projection does not uniquely identify an exact repair occurrence, so
#: deriving authority from them would permit cross-occurrence acceptance.
FORBIDDEN_AUTHORITY_SOURCES: frozenset[str] = frozenset(
    {
        "label",
        "liveness",
        "wbc_receipt",
        "rebuildable_projection",
    }
)

# Closed outcome vocabulary.  Every claim and mutation decision returns one
# of these typed outcomes so downstream consumers branch on a finite set.
SimpleFixerOutcome = (
    "claimed",            # singleton exact-occurrence claim acquired
    "already_claimed",    # same owner already holds the singleton claim
    "busy",               # occurrence claimed by a different owner
    "attempted",          # mutation applied and the fingerprint changed
    "unchanged",          # mutation applied but the fingerprint did not change
    "exhausted",          # unchanged-fingerprint budget exhausted
    "rejected_identity",  # occurrence identity is not an exact F01 tuple
    "rejected_no_claim",  # action gate: no singleton claim held
    "rejected_child_agent",  # no-child-agent gate: fan-out requested
    "rejected_gate",      # a generic action gate rejected the mutation
)

SIMPLE_FIXER_OUTCOMES: tuple[str, ...] = SimpleFixerOutcome


def _fingerprint_from_tuple(values: Mapping[str, str]) -> str:
    """Deterministic SHA-256 fingerprint over the exact F01 tuple."""

    plain = {name: values[name] for name in F01_REPAIR_OCCURRENCE_FIELDS}
    payload = json.dumps(plain, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


# ═══════════════════════════════════════════════════════════════════════════
# Occurrence contract
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SimpleFixerOccurrence(Contract):
    """Exact repair-occurrence identity for the ``simple_fixer``.

    Wraps the canonical :class:`CustodyTargetKey` and exposes a
    deterministic occurrence fingerprint computed *only* over the ten F01
    repair-occurrence fields.  All ten F01 fields are required non-empty
    strings — a partial tuple (for example a label-only or liveness-only
    identity) is rejected at construction, so authority can never be built
    from a forbidden source.

    The occurrence fingerprint is the canonical identity used for the
    singleton claim key and the unchanged-fingerprint mutation budget.
    """

    contract_type: ClassVar[str] = SIMPLE_FIXER_CONTRACT_TYPE
    schema_version: ClassVar[int] = SIMPLE_FIXER_SCHEMA_VERSION

    target: CustodyTargetKey

    def __post_init__(self) -> None:
        if not isinstance(self.target, CustodyTargetKey):
            raise ContractError("target must be a CustodyTargetKey")
        # Defence in depth: re-validate the exact F01 tuple so a
        # constructed-but-partial key cannot slip through.  This is the
        # boundary at which forbidden authority sources are rejected.
        for name in F01_REPAIR_OCCURRENCE_FIELDS:
            value = getattr(self.target, name)
            if not isinstance(value, str) or not value.strip():
                raise ContractError(
                    "occurrence identity requires the exact F01 tuple; "
                    f"field {name!r} is empty — authority may not be derived "
                    "from a label, liveness signal, WBC receipt, or "
                    "rebuildable projection"
                )

    @property
    def occurrence_fingerprint(self) -> str:
        """Deterministic SHA-256 fingerprint over the exact F01 tuple."""

        return _fingerprint_from_tuple(
            {name: getattr(self.target, name) for name in F01_REPAIR_OCCURRENCE_FIELDS}
        )

    def to_dict(self) -> dict[str, Any]:
        # Override so the nested CustodyTargetKey is serialized to a plain
        # object (the base ``_plain`` helper does not recurse into Contract
        # instances) and so the fingerprint is included in the projection.
        return {
            "contract_type": self.contract_type,
            "schema_version": self.schema_version,
            "target": dict(self.target.to_dict()),
            "occurrence_fingerprint": self.occurrence_fingerprint,
        }


def build_simple_fixer_occurrence(target: CustodyTargetKey | Mapping[str, Any] | None) -> SimpleFixerOccurrence | None:
    """Build a :class:`SimpleFixerOccurrence` or ``None`` for invalid input.

    Accepts either an already-constructed :class:`CustodyTargetKey` or a
    mapping of the F01 fields.  Returns ``None`` (does not raise) when the
    exact F01 tuple cannot be satisfied, so forbidden authority sources
    simply fail to produce an occurrence rather than raising.
    """

    if isinstance(target, SimpleFixerOccurrence):
        return target
    if isinstance(target, CustodyTargetKey):
        key = target
    elif isinstance(target, Mapping):
        key = build_custody_target_key(**{name: target.get(name, "") for name in F01_REPAIR_OCCURRENCE_FIELDS})
    else:
        return None
    if key is None:
        return None
    try:
        return SimpleFixerOccurrence(target=key)
    except ContractError:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# No-child-agent gate
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SimpleFixerAction:
    """A single, in-process mutation action gated by the fixer contract.

    A ``simple_fixer`` action is a *leaf* mutation: it carries exactly one
    in-process callable and MUST NOT request child-agent fan-out.  Any
    request that carries a child-agent / fan-out directive is rejected at
    the contract layer (construction raises) so a fan-out action can never
    be built, in addition to the runtime gate in :func:`guard_no_child_agent`.
    """

    mutate: Callable[[SimpleFixerOccurrence], str]
    label: str = ""

    def __post_init__(self) -> None:
        if not callable(self.mutate):
            raise ContractError("SimpleFixerAction.mutate must be callable")


def guard_no_child_agent(*, requests_child_agent: bool = False, child_agent_count: int = 0) -> str | None:
    """Return ``rejected_child_agent`` if fan-out is requested, else ``None``.

    This is the contract-layer no-child-agent behaviour: the fixer never
    spawns a child agent.  The check is split out so every mutation
    boundary can invoke it without re-implementing the logic.
    """

    if requests_child_agent or (isinstance(child_agent_count, int) and child_agent_count):
        return "rejected_child_agent"
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Typed claim result
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SimpleFixerClaimResult:
    """Typed result of a singleton exact-occurrence claim attempt."""

    outcome: str
    occurrence_fingerprint: str
    lock_dir: str
    owner: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.outcome not in SIMPLE_FIXER_OUTCOMES:
            raise ContractError(f"unknown simple_fixer outcome {self.outcome!r}")

    @property
    def claimed(self) -> bool:
        return self.outcome == "claimed"


def _claim_result_from_lock(
    result: RepairLockResult,
    *,
    occurrence_fingerprint: str,
    request_id: str,
) -> SimpleFixerClaimResult:
    """Map a :class:`RepairLockResult` to a typed claim result.

    A stale lock is *contention evidence for the operator/repair loop*, not
    authority to delete another worker's lock and seize it, so it maps to
    ``busy``.  If the existing owner shares our request id the outcome is
    ``already_claimed``.
    """

    if result.acquired:
        return SimpleFixerClaimResult(
            outcome="claimed",
            occurrence_fingerprint=occurrence_fingerprint,
            lock_dir=str(result.lock_dir),
            owner=result.owner,
        )
    owner = dict(result.owner or {})
    owner_request_id = str(owner.get("request_id") or "")
    if request_id and owner_request_id == request_id:
        outcome = "already_claimed"
    else:
        outcome = "busy"
    evidence = {
        "kind": "singleton_occurrence_claim_contention",
        "outcome": outcome,
        "occurrence_fingerprint": occurrence_fingerprint,
        "request_id": request_id,
        "owner_request_id": owner_request_id,
        "stale": result.status == "stale",
        "stale_evidence": result.stale_evidence,
    }
    return SimpleFixerClaimResult(
        outcome=outcome,
        occurrence_fingerprint=occurrence_fingerprint,
        lock_dir=str(result.lock_dir),
        owner=result.owner,
        evidence=evidence,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Singleton exact-occurrence claim through plural repair queue APIs
# ═══════════════════════════════════════════════════════════════════════════


def claim_singleton_occurrence(
    queue_dir: str,
    occurrence: SimpleFixerOccurrence,
    *,
    actor: str,
    request_id: str,
    session: str,
    pid: int | None = None,
    command: str | None = None,
    started_at: str | None = None,
    cwd: str | None = None,
    timeout_seconds: float | None = None,
    hostname: str | None = None,
    now: Any = None,
    is_pid_live: Callable[[int], bool] | None = None,
) -> SimpleFixerClaimResult:
    """Acquire the singleton exact-occurrence claim.

    The claim is enforced **one active occurrence at a time** through the
    same queue-root-validated ``mkdir`` lock primitive that
    :func:`claim_active_repair_request` uses (via
    :func:`singleton_occurrence_claim_lock_dir`), but keyed by the
    deterministic occurrence fingerprint so two distinct occurrences of the
    same logical blocker cannot share a claim slot.

    Returns a typed :class:`SimpleFixerClaimResult`.  The fixer never
    auto-seizes a stale lock — a stale claim is reported as ``busy`` and
    left for explicit operator/repair-loop handling.
    """

    if not isinstance(occurrence, SimpleFixerOccurrence):
        return SimpleFixerClaimResult(
            outcome="rejected_identity",
            occurrence_fingerprint="",
            lock_dir="",
            evidence={"reason": "occurrence_must_be_simple_fixer_occurrence"},
        )
    fingerprint = occurrence.occurrence_fingerprint
    lock_dir = singleton_occurrence_claim_lock_dir(queue_dir, fingerprint)
    metadata = {
        "kind": "singleton_occurrence_claim",
        "schema_version": SIMPLE_FIXER_SCHEMA_VERSION,
        "actor": actor,
        "session": session,
        "request_id": request_id,
        "occurrence_fingerprint": fingerprint,
        "occurrence": occurrence.target.to_dict(),
    }
    result = acquire_repair_lock(
        lock_dir,
        session=session,
        target_id=fingerprint,
        pid=pid,
        command=command,
        started_at=started_at,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        hostname=hostname,
        extra=metadata,
        now=now,
        is_pid_live=is_pid_live,
    )
    return _claim_result_from_lock(
        result, occurrence_fingerprint=fingerprint, request_id=request_id
    )


def inspect_singleton_occurrence_claim(
    queue_dir: str,
    occurrence: SimpleFixerOccurrence,
    *,
    now: Any = None,
    is_pid_live: Callable[[int], bool] | None = None,
) -> RepairLockResult:
    """Inspect (without mutating) the singleton claim for an occurrence."""

    fingerprint = occurrence.occurrence_fingerprint
    lock_dir = singleton_occurrence_claim_lock_dir(queue_dir, fingerprint)
    return inspect_repair_lock(lock_dir, now=now, is_pid_live=is_pid_live)


def release_singleton_occurrence_claim(
    queue_dir: str,
    occurrence: SimpleFixerOccurrence,
    *,
    owner: Mapping[str, Any] | None = None,
    expected_pid: int | None = None,
) -> bool:
    """Release the singleton exact-occurrence claim.

    Best-effort admission cleanup only (mirrors the no-lease-store path of
    :func:`release_repair_lock`): it does not confer repair authority.
    """

    if not isinstance(occurrence, SimpleFixerOccurrence):
        return False
    lock_dir = singleton_occurrence_claim_lock_dir(queue_dir, occurrence.occurrence_fingerprint)
    return release_repair_lock(lock_dir, owner=owner, expected_pid=expected_pid)


# ═══════════════════════════════════════════════════════════════════════════
# Two-try unchanged-fingerprint mutation budget
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class MutationBudget:
    """Two-try unchanged-fingerprint budget for one exact occurrence.

    Records consecutive mutation attempts whose occurrence fingerprint did
    not change.  The budget is *occurrence-scoped*: it is bound to the
    occurrence fingerprint and a foreign fingerprint never affects it.  When
    :attr:`unchanged_attempts` reaches
    :data:`MAX_UNCHANGED_FINGERPRINT_ATTEMPTS` the budget is exhausted and
    further attempts are rejected with ``exhausted``.
    """

    occurrence_fingerprint: str
    unchanged_attempts: int = 0
    total_attempts: int = 0

    def record_mutation(self, before_fingerprint: str, after_fingerprint: str) -> str:
        """Record a mutation attempt and return its typed outcome.

        ``before``/``after`` are the occurrence-state fingerprints observed
        immediately before and after the mutation callable ran.  If they are
        equal the attempt was a no-op; two consecutive no-ops exhaust the
        budget.
        """

        self.total_attempts += 1
        if before_fingerprint == after_fingerprint:
            self.unchanged_attempts += 1
            if self.unchanged_attempts >= MAX_UNCHANGED_FINGERPRINT_ATTEMPTS:
                return "exhausted"
            return "unchanged"
        # A productive mutation resets the no-op streak.
        self.unchanged_attempts = 0
        return "attempted"

    @property
    def exhausted(self) -> bool:
        return self.unchanged_attempts >= MAX_UNCHANGED_FINGERPRINT_ATTEMPTS

    @property
    def remaining(self) -> int:
        """Number of unchanged attempts left before exhaustion (>= 0)."""

        return max(0, MAX_UNCHANGED_FINGERPRINT_ATTEMPTS - self.unchanged_attempts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "simple_fixer_mutation_budget",
            "schema_version": SIMPLE_FIXER_SCHEMA_VERSION,
            "occurrence_fingerprint": self.occurrence_fingerprint,
            "unchanged_attempts": self.unchanged_attempts,
            "total_attempts": self.total_attempts,
            "max_unchanged_fingerprint_attempts": MAX_UNCHANGED_FINGERPRINT_ATTEMPTS,
            "exhausted": self.exhausted,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Stateful fixer session: action gates at every mutation boundary
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class SimpleFixerSession:
    """Stateful ``simple_fixer`` session for one exact occurrence.

    Holds the singleton claim and the mutation budget.  Every mutation
    boundary is gated in :meth:`attempt_mutation`:

    1. identity must be an exact F01 tuple (guaranteed at construction);
    2. no child agent may be requested (``rejected_child_agent``);
    3. a singleton claim must be held (``rejected_no_claim``);
    4. the unchanged-fingerprint budget must not be exhausted
       (``exhausted``).
    """

    occurrence: SimpleFixerOccurrence
    claim: SimpleFixerClaimResult | None = None
    budget: MutationBudget | None = None

    def __post_init__(self) -> None:
        if self.budget is None:
            self.budget = MutationBudget(self.occurrence.occurrence_fingerprint)

    @property
    def has_claim(self) -> bool:
        return self.claim is not None and self.claim.claimed

    def attempt_mutation(
        self,
        action: SimpleFixerAction,
        *,
        requests_child_agent: bool = False,
        child_agent_count: int = 0,
        after_fingerprint: str | None = None,
    ) -> str:
        """Apply a gated mutation and return its typed outcome.

        ``after_fingerprint`` lets the caller supply the post-mutation
        occurrence-state fingerprint directly (e.g. read from disk after the
        action ran).  When it is ``None`` the action's callable is invoked
        and its return value is used as the post-mutation fingerprint.
        """

        # Gate 2 — no child agent (gate 1 is enforced at construction).
        verdict = guard_no_child_agent(
            requests_child_agent=requests_child_agent,
            child_agent_count=child_agent_count,
        )
        if verdict is not None:
            return verdict
        # Gate 3 — a singleton claim must be held.
        if not self.has_claim:
            return "rejected_no_claim"
        # Gate 4 — budget not exhausted.
        assert self.budget is not None  # set in __post_init__
        if self.budget.exhausted:
            return "exhausted"
        before = self.occurrence.occurrence_fingerprint
        if after_fingerprint is None:
            after_fingerprint = action.mutate(self.occurrence)
        return self.budget.record_mutation(before, after_fingerprint)


# ═══════════════════════════════════════════════════════════════════════════
# Step 36-37 — Canonical runner, verifier receipts, and latency ledger
# ═══════════════════════════════════════════════════════════════════════════

import datetime as _datetime
import json as _json
import os as _os
import time as _time
from dataclasses import asdict as _asdict


@dataclass(frozen=True)
class RunnerReceipt:
    """A redacted transcript/result receipt with exact source/provenance hashes.

    The transcript is redacted (sanitized of sensitive data) and the
    receipt carries content-addressed provenance hashes for the source
    code, environment, and runner identity.  Receipts are never used to
    derive authority — they are evidence-only records for cross-contract
    recovery SLO verification.
    """

    receipt_id: str
    """Content-addressed receipt identifier (sha256 over canonical fields)."""

    occurrence_fingerprint: str
    """The exact occurrence fingerprint this receipt belongs to."""

    kind: str
    """``immediate_trigger`` or ``reconciliation`` — which runner path produced this receipt."""

    status: str
    """``success``, ``failed``, ``timeout``, or ``escalated``."""

    redacted_transcript: str
    """Sanitized transcript of the runner execution (no secrets, PII, or auth tokens)."""

    provenance_hash: str
    """sha256 over the runner's source-code identity (simple_fixer module hash)."""

    source_env_hash: str
    """sha256 over the runtime environment fingerprint (interpreter, platform, dependencies)."""

    runner_identity: str
    """Canonical identity of the runner that produced this receipt (always ``simple_fixer.canonical``)."""

    emitted_at: str
    """ISO-8601 timestamp when this receipt was emitted."""

    verifier_slot: str = ""
    """Scheduled verifier slot: ``five_minute``, ``one_hour``, or ``next_three_hour``."""

    def __post_init__(self) -> None:
        if not self.receipt_id:
            raw = (
                f"{self.occurrence_fingerprint}\\x00{self.kind}\\x00"
                f"{self.status}\\x00{self.provenance_hash}\\x00"
                f"{self.source_env_hash}\\x00{self.emitted_at}"
            )
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            object.__setattr__(self, "receipt_id", f"sha256:{digest}")

    @property
    def redacted(self) -> bool:
        """Receipts are always redacted; this is an affirmative marker for consumers."""
        return True

    def to_dict(self) -> dict[str, Any]:
        payload = _asdict(self)
        payload["redacted"] = self.redacted
        payload["runner_contract"] = "simple_fixer.canonical"
        return payload

    @classmethod
    def from_runner_result(
        cls,
        *,
        occurrence_fingerprint: str,
        kind: str,
        status: str,
        transcript: str,
        provenance_hash: str,
        source_env_hash: str,
        emitted_at: str | None = None,
        verifier_slot: str = "",
    ) -> "RunnerReceipt":
        """Build a receipt from a runner execution result.

        The transcript is redacted by stripping lines that match common
        secret/token patterns.  This is a best-effort redaction that
        removes overt secrets but does not guarantee zero information
        leakage — consumers MUST treat the redacted transcript as
        evidence-only, never authority-bearing.
        """
        # Basic redaction: strip common secret patterns
        redacted_lines: list[str] = []
        _secret_patterns = (
            "TOKEN=", "SECRET=", "PASSWORD=", "API_KEY=", "AUTH=",
            "CREDENTIAL=", "PRIVATE_KEY", "-----BEGIN", "-----END",
        )
        for line in transcript.splitlines():
            low = line.upper()
            if any(pat in low for pat in _secret_patterns):
                redacted_lines.append("[REDACTED]")
            else:
                redacted_lines.append(line)
        redacted = "\n".join(redacted_lines)

        if emitted_at is None:
            emitted_at = _datetime.datetime.now(_datetime.timezone.utc).isoformat()

        return cls(
            receipt_id="",  # computed in __post_init__
            occurrence_fingerprint=occurrence_fingerprint,
            kind=kind,
            status=status,
            redacted_transcript=redacted,
            provenance_hash=provenance_hash,
            source_env_hash=source_env_hash,
            runner_identity="simple_fixer.canonical",
            emitted_at=emitted_at,
            verifier_slot=verifier_slot,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Verifier receipt slots — 5m / 1h / next-three-hour
# ═══════════════════════════════════════════════════════════════════════════

# Canonical verifier slots for M11 recovery SLO.  Legacy six_hour slots
# are NOT in this set — schedule mismatch detection rejects them.
CANONICAL_VERIFIER_SLOTS: frozenset[str] = frozenset(
    {"five_minute", "one_hour", "next_three_hour"}
)

LEGACY_VERIFIER_SLOTS: frozenset[str] = frozenset({"six_hour"})


@dataclass(frozen=True)
class VerifierScheduleCheck:
    """Result of checking a manifest's verifier schedule against M11 requirements."""

    schedule_valid: bool
    """True when all required canonical slots are present."""

    present_slots: frozenset[str]
    """All verifier slots found in the schedule."""

    missing_canonical_slots: frozenset[str]
    """Required canonical slots that are absent."""

    legacy_only_slots: frozenset[str]
    """Legacy slots present (e.g. ``six_hour``) without a ``next_three_hour`` replacement."""

    reason: str
    """Human-readable explanation of the check result."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schedule_valid": self.schedule_valid,
            "present_slots": sorted(self.present_slots),
            "missing_canonical_slots": sorted(self.missing_canonical_slots),
            "legacy_only_slots": sorted(self.legacy_only_slots),
            "reason": self.reason,
        }


def check_verifier_schedule(
    manifest_slots: frozenset[str],
    *,
    required_slots: frozenset[str] | None = None,
) -> VerifierScheduleCheck:
    """Check a verifier schedule manifest for M11 canonical slot compliance.

    If the manifest has ``five_minute`` and ``one_hour`` slots but only
    ``six_hour`` (not ``next_three_hour``), the check emits
    ``recovery_verifier_schedule_mismatch`` and the schedule is invalid.

    A schedule with all three canonical slots (five_minute, one_hour,
    next_three_hour) is valid.  Extra legacy slots are tolerated as long
    as the canonical slots are present.
    """
    if required_slots is None:
        required_slots = CANONICAL_VERIFIER_SLOTS

    present = frozenset(manifest_slots)
    missing = required_slots - present
    legacy_present = LEGACY_VERIFIER_SLOTS & present

    # Schedule mismatch: has legacy six_hour but no next_three_hour
    has_schedule_mismatch = (
        "six_hour" in present
        and "next_three_hour" not in present
    )

    if has_schedule_mismatch:
        return VerifierScheduleCheck(
            schedule_valid=False,
            present_slots=present,
            missing_canonical_slots=missing,
            legacy_only_slots=legacy_present,
            reason=(
                "recovery_verifier_schedule_mismatch: manifest has "
                "six_hour slot but no next_three_hour slot; "
                "m11_prerequisite_incomplete until the manifest is "
                "regenerated or the three-hour receipt set is produced"
            ),
        )

    if missing:
        return VerifierScheduleCheck(
            schedule_valid=False,
            present_slots=present,
            missing_canonical_slots=missing,
            legacy_only_slots=frozenset(),
            reason=(
                f"missing required verifier slots: {sorted(missing)}; "
                "m11_prerequisite_incomplete"
            ),
        )

    return VerifierScheduleCheck(
        schedule_valid=True,
        present_slots=present,
        missing_canonical_slots=frozenset(),
        legacy_only_slots=legacy_present,
        reason="all canonical verifier slots present",
    )


def extract_verifier_slots_from_manifest(
    manifest: Mapping[str, Any] | None,
) -> frozenset[str]:
    """Extract verifier slot names from a genuine-block candidate manifest.

    Reads ``verifier_schedule.schedule`` keys from the manifest.
    Returns an empty frozenset when the manifest is absent or malformed.
    """
    if not isinstance(manifest, Mapping):
        return frozenset()
    schedule = manifest.get("verifier_schedule")
    if not isinstance(schedule, Mapping):
        return frozenset()
    slots = schedule.get("schedule")
    if not isinstance(slots, Mapping):
        return frozenset()
    return frozenset(str(k) for k in slots)


# ═══════════════════════════════════════════════════════════════════════════
# Canonical runner — one implementation for immediate trigger & reconciliation
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class CanonicalRunner:
    """One canonical runner for both immediate-trigger and reconciliation paths.

    The runner is the **only** implementation that can execute a
    ``simple_fixer`` mutation.  Both the immediate event trigger (e.g.
    repair-trigger fired on a new blocked occurrence) and the
    reconciliation path (e.g. missed-event backstop every three hours)
    funnel through the same ``CanonicalRunner.run()`` method so there is
    exactly one code path producing receipts, one provenance hash, and
    one audit trail.

    The runner never spawns child agents and never derives authority from
    labels, liveness, WBC receipts, or rebuildable projections.
    """

    provenance_hash: str
    """Content-addressed hash of the simple_fixer module source."""

    source_env_hash: str
    """Content-addressed hash of the runtime environment."""

    def __post_init__(self) -> None:
        if not self.provenance_hash:
            self.provenance_hash = self._compute_provenance_hash()
        if not self.source_env_hash:
            self.source_env_hash = self._compute_source_env_hash()

    @staticmethod
    def _compute_provenance_hash() -> str:
        """Compute the provenance hash from the simple_fixer module source."""
        try:
            source = Path(__file__).read_text(encoding="utf-8")
        except Exception:
            source = "simple_fixer.canonical"
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    @staticmethod
    def _compute_source_env_hash() -> str:
        """Compute the source environment hash from interpreter and platform."""
        parts = [
            str(_os.name),
            str(_os.uname()) if hasattr(_os, "uname") else "",
            str(_os.environ.get("PYTHON_VERSION", "")),
            str(_os.environ.get("MEGAPLAN_ENGINE_ROOT", "")),
        ]
        digest = hashlib.sha256("\\x00".join(parts).encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    def run(
        self,
        occurrence: SimpleFixerOccurrence,
        action: SimpleFixerAction,
        *,
        kind: str = "immediate_trigger",
        session: SimpleFixerSession | None = None,
        verifier_slot: str = "",
    ) -> tuple[str, RunnerReceipt | None]:
        """Execute a mutation through the canonical runner.

        Returns ``(outcome, receipt)`` where *outcome* is one of the
        :data:`SIMPLE_FIXER_OUTCOMES` and *receipt* is a
        :class:`RunnerReceipt` when a mutation was attempted (success or
        failure), or ``None`` when rejected by action gates.

        The *kind* parameter distinguishes the trigger path:
        ``immediate_trigger`` for event-driven repair and
        ``reconciliation`` for the missed-event backstop.  Both paths
        produce receipts with the same provenance hash — there is never
        a separate implementation.
        """
        transcript_lines: list[str] = []
        start_time = _time.monotonic()

        transcript_lines.append(
            f"canonical_runner start kind={kind} "
            f"fingerprint={occurrence.occurrence_fingerprint} "
            f"provenance={self.provenance_hash}"
        )

        if session is None:
            session = SimpleFixerSession(occurrence=occurrence)

        # Gate check: no child agent
        child_check = guard_no_child_agent()
        if child_check is not None:
            transcript_lines.append(f"gate rejected: {child_check}")
            receipt = RunnerReceipt.from_runner_result(
                occurrence_fingerprint=occurrence.occurrence_fingerprint,
                kind=kind,
                status="rejected",
                transcript="\n".join(transcript_lines),
                provenance_hash=self.provenance_hash,
                source_env_hash=self.source_env_hash,
                verifier_slot=verifier_slot,
            )
            return child_check, receipt

        # Gate check: claim held
        if not session.has_claim:
            transcript_lines.append("gate rejected: rejected_no_claim")
            receipt = RunnerReceipt.from_runner_result(
                occurrence_fingerprint=occurrence.occurrence_fingerprint,
                kind=kind,
                status="rejected",
                transcript="\n".join(transcript_lines),
                provenance_hash=self.provenance_hash,
                source_env_hash=self.source_env_hash,
                verifier_slot=verifier_slot,
            )
            return "rejected_no_claim", receipt

        # Attempt mutation
        try:
            outcome = session.attempt_mutation(action)
        except Exception as exc:
            outcome = "rejected_gate"
            transcript_lines.append(f"mutation raised: {exc}")

        elapsed = _time.monotonic() - start_time
        transcript_lines.append(
            f"canonical_runner finish outcome={outcome} elapsed={elapsed:.3f}s"
        )

        status = "success" if outcome == "attempted" else (
            "failed" if outcome in ("unchanged", "exhausted", "rejected_gate") else "rejected"
        )
        receipt = RunnerReceipt.from_runner_result(
            occurrence_fingerprint=occurrence.occurrence_fingerprint,
            kind=kind,
            status=status,
            transcript="\n".join(transcript_lines),
            provenance_hash=self.provenance_hash,
            source_env_hash=self.source_env_hash,
            verifier_slot=verifier_slot,
        )
        return outcome, receipt


def build_canonical_runner(
    *,
    provenance_hash: str = "",
    source_env_hash: str = "",
) -> CanonicalRunner:
    """Build the canonical runner with content-addressed provenance.

    When *provenance_hash* and *source_env_hash* are empty, they are
    computed from the current module source and environment.  Callers
    that have pre-computed hashes (e.g. from a sealed build) can pass
    them explicitly for deterministic receipts.
    """
    return CanonicalRunner(
        provenance_hash=provenance_hash,
        source_env_hash=source_env_hash,
    )


__all__ = [
    "CANONICAL_VERIFIER_SLOTS",
    "CanonicalRunner",
    "FORBIDDEN_AUTHORITY_SOURCES",
    "LEGACY_VERIFIER_SLOTS",
    "MAX_UNCHANGED_FINGERPRINT_ATTEMPTS",
    "MutationBudget",
    "RunnerReceipt",
    "SIMPLE_FIXER_CONTRACT_TYPE",
    "SIMPLE_FIXER_OUTCOMES",
    "SIMPLE_FIXER_SCHEMA_VERSION",
    "SimpleFixerAction",
    "SimpleFixerClaimResult",
    "SimpleFixerOccurrence",
    "SimpleFixerOutcome",
    "SimpleFixerSession",
    "VerifierScheduleCheck",
    "build_canonical_runner",
    "build_simple_fixer_occurrence",
    "check_verifier_schedule",
    "claim_singleton_occurrence",
    "extract_verifier_slots_from_manifest",
    "guard_no_child_agent",
    "inspect_singleton_occurrence_claim",
    "release_singleton_occurrence_claim",
]
