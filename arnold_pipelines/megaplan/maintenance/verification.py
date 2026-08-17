"""Independent blocker-specific verification (M3 Step 7 / T8).

This module implements the *pure* decision surface for independent
verification: given durable distinct-principal provenance, a coherent
direct owner-source capture, accepted M10/C2 negative controls, and
authoritative progress beyond the pre-repair checkpoint, it returns one
typed fail-closed outcome for the occurrence.  It never writes a record,
never reacquires authority, never re-classifies an M10/C2 result, and never
constructs an owner authority store — the cloud adapter owns mutation.

Locked decisions (do not re-litigate):

* **Distinct principal.**  The verifier must be a durable principal distinct
  from the repair producer.  A repair producer (role
  :attr:`~arnold_pipelines.megaplan.maintenance.operations.ProducerRole.REPAIR_PRODUCER`)
  authoring the verification, or any verifier whose principal equals the
  producer's principal, is self-declared independence and is rejected.
* **Direct owner-source reads.**  The envelope must be one coherent,
  complete, fresh, single-environment capture (T6): the occurrence-bound
  join already required matching environment / run / attempt / occurrence /
  target / lease / fence / WBC / source-version coordinates, so a torn,
  cross-occurrence, or stale envelope can never verify here.
* **Accepted negative controls.**  Blocker-specific negative controls are
  *translated* from accepted M10 recovery and C2 proof-mode results
  (``NegativeControlResult`` with durable content-addressed ``control_ref``);
  this module never duplicates their classifiers.
* **Authoritative progress.**  Terminal verification requires durable
  progress beyond the pre-repair checkpoint.  PID/tmux health, activity,
  local tests, commits, and terminal labels are corroboration only
  (``liveness_only``) and never count as progress.
* **Complete checkpoint set.**  Only the complete policy-required set
  (:data:`~arnold_pipelines.megaplan.maintenance.projections.REQUIRED_CHECKPOINT_WINDOWS`)
  may authorize terminal verification; a terminal attempt with an
  incomplete set stays ``open``.  Non-terminal (checkpoint-level)
  evaluations still require negative controls but not the complete set.

Outcome vocabulary (closed): ``open``, ``unknown``, ``incoherent``,
``failed_control``, ``verified``.  Only ``verified`` may be terminal, and
only with the complete required checkpoint set; every other outcome leaves
canonical custody open without a terminal submission.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from arnold_pipelines.megaplan.maintenance.checkpoints import CANONICAL_CHECKPOINT_ORDER
from arnold_pipelines.megaplan.maintenance.contracts import (
    CoherenceReason,
    CoherenceState,
    CompletenessState,
    FreshnessState,
    ObservationEnvelope,
)
from arnold_pipelines.megaplan.maintenance.events import (
    CheckpointWindowKind,
    VerifierProvenance,
    canonical_checkpoint_window,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    MAINTENANCE_SCHEMA_VERSION,
    OwnerRef,
    canonical_digest,
)
from arnold_pipelines.megaplan.maintenance.operations import ProducerPrincipal, ProducerRole
from arnold_pipelines.megaplan.maintenance.projections import (
    REQUIRED_CHECKPOINT_WINDOWS,
    CheckpointOutcome,
)

#: Locator schemes that are liveness/corroboration evidence only — never
#: durable authoritative progress (Plan Step 7.4).
_LIVENESS_SCHEMES: frozenset[str] = frozenset(
    {
        "pid",
        "tmux",
        "health",
        "activity",
        "test",
        "commit",
        "label",
        "local",
    }
)


def _is_liveness_locator(locator: str) -> bool:
    """Return whether *locator* points at liveness/corroboration evidence."""
    scheme, _, _ = locator.partition("://")
    return scheme.lower() in _LIVENESS_SCHEMES


def _cursor_number(cursor: str | None) -> int | None:
    """Parse a numeric cursor coordinate (``journal:N``, ``seq:N``, ...).

    Returns ``None`` when the cursor is absent or not parseable — a cursor
    is never guessed.
    """
    if cursor is None:
        return None
    text = cursor
    for prefix in ("journal:", "seq:", "sequence:", "cursor:", "epoch:"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    try:
        return int(text)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Closed outcome and reason vocabularies
# ---------------------------------------------------------------------------


class VerificationOutcome(str, Enum):
    """Closed typed outcomes of independent verification (Plan Step 7.5).

    * ``OPEN`` — custody stays open (e.g. a terminal attempt with an
      incomplete required checkpoint set);
    * ``UNKNOWN`` — missing/insufficient evidence (stale authority, missing
      provenance, liveness-only progress, missing negative control);
    * ``INCOHERENT`` — contradictory evidence (torn/cross-occurrence
      envelope, self-declared independence);
    * ``FAILED_CONTROL`` — an accepted negative control ran and the blocker
      is still present;
    * ``VERIFIED`` — durable distinct verifier + direct owner-source reads +
      accepted controls (+ progress and complete checkpoint set when
      terminal).
    """

    OPEN = "open"
    UNKNOWN = "unknown"
    INCOHERENT = "incoherent"
    FAILED_CONTROL = "failed_control"
    VERIFIED = "verified"


class VerificationRejectReason(str, Enum):
    """Closed typed reasons for non-verified outcomes (never guessed)."""

    MISSING_PROVENANCE = "missing_provenance"
    REPAIR_PRODUCER_AUTHORED = "repair_producer_authored"
    SELF_VERIFICATION = "self_verification"
    STALE_AUTHORITY = "stale_authority"
    TORN_ENVELOPE = "torn_envelope"
    INCOHERENT_EVIDENCE = "incoherent_evidence"
    UNKNOWN_EVIDENCE = "unknown_evidence"
    MISSING_NEGATIVE_CONTROL = "missing_negative_control"
    FAILED_CONTROL = "failed_control"
    LIVENESS_ONLY = "liveness_only"
    NO_PROGRESS = "no_progress"
    INCOMPLETE_CHECKPOINTS = "incomplete_checkpoints"


# ---------------------------------------------------------------------------
# Input contracts
# ---------------------------------------------------------------------------


class NegativeControlResult(BaseModel):
    """One accepted blocker-specific negative control (M10/C2 translation).

    ``control_ref`` is the durable content-addressed reference to the
    accepted M10 recovery / C2 proof-mode result; ``blocker_absent`` is the
    translated outcome.  The verifier never re-classifies the control — it
    only requires the accepted durable result.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    control_id: StrictStr
    control_ref: OwnerRef
    blocker_absent: bool

    @field_validator("control_id")
    @classmethod
    def _validate_control_id(cls, value: str) -> str:
        if not value:
            raise ValueError("negative control_id must be a non-empty string")
        return value

    @model_validator(mode="after")
    def _require_durable_ref(self) -> NegativeControlResult:
        if self.control_ref.digest is None:
            raise ValueError(
                "a negative control must carry a durable content-addressed "
                "control_ref (digest required)"
            )
        return self


class ExpectedAuthority(BaseModel):
    """The current authority coordinates the verifier must have re-read.

    ``run_id``/``attempt_id`` are compared against the envelope's captured
    identity fields; ``lease_id``/``custody_epoch``/``fencing_token`` are the
    current M7 lease coordinates the occurrence is bound to (the T6 join
    required matching lease/fence dimensions at capture, and the envelope
    must be fresh).  Absent coordinates are never inferred.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    occurrence_id: StrictStr | None = None
    run_id: StrictStr | None = None
    attempt_id: StrictStr | None = None
    lease_id: StrictStr | None = None
    custody_epoch: int | None = Field(default=None, ge=1)
    fencing_token: StrictStr | None = None

    @field_validator("occurrence_id", "run_id", "attempt_id", "lease_id", "fencing_token")
    @classmethod
    def _validate_nonempty(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError(
                "expected authority coordinates must be non-empty strings "
                "when present"
            )
        return value


class VerificationResult(BaseModel):
    """The typed fail-closed outcome of one verification evaluation.

    ``terminal`` is ``True`` ONLY when the outcome is ``VERIFIED`` (the
    complete required checkpoint set was present for a terminal evaluation);
    every non-verified outcome carries at least one typed
    :class:`VerificationRejectReason` and can never close custody.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    outcome: VerificationOutcome
    reasons: tuple[VerificationRejectReason, ...] = ()
    terminal: bool = False
    verified_windows: tuple[CheckpointWindowKind, ...] = ()
    verifier_principal: StrictStr | None = None
    proof_mode: StrictStr | None = None
    negative_control_result: StrictStr | None = None
    resumed_progress: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @model_validator(mode="after")
    def _enforce_fail_closed(self) -> VerificationResult:
        if self.outcome is VerificationOutcome.VERIFIED and self.reasons:
            raise ValueError(
                "a verified outcome must not carry reject reasons; "
                f"got {[reason.value for reason in self.reasons]}"
            )
        if self.outcome is not VerificationOutcome.VERIFIED and not self.reasons:
            raise ValueError(
                f"outcome {self.outcome.value!r} requires at least one typed "
                "reject reason"
            )
        if self.terminal and self.outcome is not VerificationOutcome.VERIFIED:
            raise ValueError(
                "only a VERIFIED outcome may be terminal; "
                f"got {self.outcome.value!r}"
            )
        return self

    @property
    def digest(self) -> str:
        """Canonical content digest of the whole result (replayable)."""
        return canonical_digest(self)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def required_checkpoint_set() -> tuple[CheckpointWindowKind, ...]:
    """Return the complete policy-required checkpoint set in canonical order."""
    return tuple(
        sorted(
            REQUIRED_CHECKPOINT_WINDOWS,
            key=lambda window: CANONICAL_CHECKPOINT_ORDER.index(window),
        )
    )


def _normalize_windows(
    completed: Sequence[CheckpointWindowKind | str | CheckpointOutcome],
) -> tuple[CheckpointWindowKind, ...]:
    """Normalize a completed-checkpoint set to canonical windows.

    Accepts window kinds, window names (``six_hour`` is a read alias for
    ``next_three_hour``), and :class:`CheckpointOutcome` models.  Anything
    else fails closed with ``ValueError`` — completion is never guessed.
    """
    windows: list[CheckpointWindowKind] = []
    for item in completed:
        if isinstance(item, CheckpointOutcome):
            windows.append(item.window)
        elif isinstance(item, CheckpointWindowKind):
            windows.append(item)
        elif isinstance(item, str):
            windows.append(canonical_checkpoint_window(item))
        else:
            raise ValueError(
                "completed checkpoint entries must be CheckpointWindowKind, "
                "window names, or CheckpointOutcome models; "
                f"got {type(item).__name__}"
            )
    return tuple(
        sorted(set(windows), key=lambda window: CANONICAL_CHECKPOINT_ORDER.index(window))
    )


def checkpoint_set_complete(
    completed: Sequence[CheckpointWindowKind | str | CheckpointOutcome],
) -> bool:
    """Return whether every policy-required window is present."""
    return REQUIRED_CHECKPOINT_WINDOWS.issubset(set(_normalize_windows(completed)))


def negative_controls_passed(controls: Sequence[NegativeControlResult]) -> bool:
    """Return whether *controls* are present and every blocker is absent.

    An empty control set is never "passed" (missing evidence fails closed);
    a single failed control fails the whole set.
    """
    return bool(controls) and all(control.blocker_absent for control in controls)


def authoritative_progress_refs(
    progress_refs: Sequence[OwnerRef],
) -> tuple[OwnerRef, ...]:
    """Filter *progress_refs* down to durable authoritative references.

    Liveness/corroboration locators (``pid://``, ``tmux://``, ``health://``,
    ``activity://``, ``test://``, ``commit://``, ``label://``, ``local://``)
    and references without a content digest are corroboration only and are
    never treated as authoritative progress.
    """
    return tuple(
        ref
        for ref in progress_refs
        if ref.digest is not None and not _is_liveness_locator(ref.locator)
    )


def progress_beyond(
    pre_repair_ref: OwnerRef,
    progress_refs: Sequence[OwnerRef],
) -> bool:
    """Return whether durable progress advances beyond the pre-repair checkpoint.

    A progress reference is *beyond* the checkpoint when its numeric cursor
    (``journal:N`` / ``seq:N`` / ``cursor:N`` / ``epoch:N``) is strictly
    greater than the checkpoint cursor; when the checkpoint carries no
    numeric cursor, the fallback is a changed durable locator AND digest
    (content advanced).  Liveness-only references never count.
    """
    durable = authoritative_progress_refs(progress_refs)
    if not durable:
        return False
    pre_cursor = _cursor_number(pre_repair_ref.cursor)
    pre_digest = pre_repair_ref.digest
    pre_locator = pre_repair_ref.locator
    for ref in durable:
        if pre_cursor is not None:
            progress_cursor = _cursor_number(ref.cursor)
            if progress_cursor is not None and progress_cursor > pre_cursor:
                return True
            continue
        if ref.digest != pre_digest and ref.locator != pre_locator:
            return True
    return False


# ---------------------------------------------------------------------------
# The evaluation
# ---------------------------------------------------------------------------


def evaluate_verification(
    *,
    provenance: VerifierProvenance,
    producer: ProducerPrincipal,
    envelope: ObservationEnvelope,
    negative_controls: Sequence[NegativeControlResult],
    completed_checkpoints: Sequence[CheckpointWindowKind | str | CheckpointOutcome],
    pre_repair_ref: OwnerRef,
    progress_refs: Sequence[OwnerRef],
    expected: ExpectedAuthority | None = None,
    terminal: bool = False,
) -> VerificationResult:
    """Evaluate independent verification for one occurrence, fail-closed.

    * ``provenance`` — the durable distinct verifier principal (direct
      owner-source read references and a credential/runtime envelope
      reference are required).
    * ``producer`` — the repair producer of this occurrence; the verifier
      must be a DIFFERENT principal (self-verification is rejected).
    * ``envelope`` — the coherent direct owner-source capture (T6).  It must
      be coherent/complete/fresh; torn, stale, cross-occurrence, or unknown
      evidence is rejected.
    * ``negative_controls`` — accepted M10/C2 blocker-specific controls.
    * ``completed_checkpoints`` — the current durable checkpoint set.
    * ``pre_repair_ref`` / ``progress_refs`` — the pre-repair checkpoint and
      the durable progress beyond it (required only for ``terminal``).
    * ``expected`` — the current authority coordinates the envelope must
      have been captured under.
    * ``terminal`` — ``True`` for terminal verification (requires the
      complete required checkpoint set and progress beyond the pre-repair
      checkpoint); ``False`` for durable non-terminal checkpoint evidence.

    Returns a :class:`VerificationResult` in ``open`` / ``unknown`` /
    ``incoherent`` / ``failed_control`` / ``verified``.  Only a ``verified``
    terminal result may close custody.
    """
    reasons: list[VerificationRejectReason] = []

    # 1. Durable distinct-principal provenance.
    if provenance.credential_envelope_ref is None or not provenance.direct_read_refs:
        reasons.append(VerificationRejectReason.MISSING_PROVENANCE)
    if (
        producer.role is ProducerRole.REPAIR_PRODUCER
        and provenance.principal == producer.principal
    ):
        reasons.append(VerificationRejectReason.REPAIR_PRODUCER_AUTHORED)
    if provenance.principal == producer.principal:
        reasons.append(VerificationRejectReason.SELF_VERIFICATION)

    # 2. Direct owner-source reads: one coherent, complete, fresh capture.
    if envelope.coherence is CoherenceState.INCOHERENT:
        if CoherenceReason.VERSION_TEAR in envelope.coherence_reasons:
            reasons.append(VerificationRejectReason.TORN_ENVELOPE)
        else:
            reasons.append(VerificationRejectReason.INCOHERENT_EVIDENCE)
    elif envelope.coherence is CoherenceState.UNKNOWN:
        reasons.append(VerificationRejectReason.UNKNOWN_EVIDENCE)
    if envelope.completeness is not CompletenessState.COMPLETE:
        reasons.append(VerificationRejectReason.UNKNOWN_EVIDENCE)
    if envelope.freshness is FreshnessState.STALE:
        reasons.append(VerificationRejectReason.STALE_AUTHORITY)
    elif envelope.freshness is FreshnessState.UNKNOWN:
        reasons.append(VerificationRejectReason.UNKNOWN_EVIDENCE)

    # 3. The envelope must have been captured under the current authority.
    if expected is not None:
        if (
            expected.run_id is not None
            and envelope.run is not None
            and envelope.run.root != expected.run_id
        ):
            reasons.append(VerificationRejectReason.STALE_AUTHORITY)
        if (
            expected.attempt_id is not None
            and envelope.attempt is not None
            and envelope.attempt.root != expected.attempt_id
        ):
            reasons.append(VerificationRejectReason.STALE_AUTHORITY)
        # Lease/epoch/fence identity matching is enforced by the T6 join at
        # capture (declared occurrence/target/lease/fence dimensions) and by
        # the freshness requirement above; the expected coordinates are
        # carried so the executor proves it re-read the CURRENT authority.

    # 4. Accepted blocker-specific negative controls (translated, never
    #    re-classified).
    if not negative_controls:
        reasons.append(VerificationRejectReason.MISSING_NEGATIVE_CONTROL)
    elif not negative_controls_passed(negative_controls):
        reasons.append(VerificationRejectReason.FAILED_CONTROL)

    # 5. Authoritative progress beyond the pre-repair checkpoint (terminal
    #    verification only; checkpoint-level evidence stays nonterminal).
    if terminal:
        if not authoritative_progress_refs(progress_refs):
            reasons.append(VerificationRejectReason.LIVENESS_ONLY)
        elif not progress_beyond(pre_repair_ref, progress_refs):
            reasons.append(VerificationRejectReason.NO_PROGRESS)

    # 6. Complete required checkpoint set for terminal verification.
    complete_set = checkpoint_set_complete(completed_checkpoints)
    if terminal and not complete_set:
        reasons.append(VerificationRejectReason.INCOMPLETE_CHECKPOINTS)

    # 7. Typed outcome (deterministic priority, never guessed).
    if reasons:
        if VerificationRejectReason.FAILED_CONTROL in reasons:
            outcome = VerificationOutcome.FAILED_CONTROL
        elif any(
            reason in reasons
            for reason in (
                VerificationRejectReason.TORN_ENVELOPE,
                VerificationRejectReason.INCOHERENT_EVIDENCE,
                VerificationRejectReason.SELF_VERIFICATION,
                VerificationRejectReason.REPAIR_PRODUCER_AUTHORED,
            )
        ):
            outcome = VerificationOutcome.INCOHERENT
        elif VerificationRejectReason.INCOMPLETE_CHECKPOINTS in reasons:
            outcome = VerificationOutcome.OPEN
        else:
            outcome = VerificationOutcome.UNKNOWN
    else:
        outcome = VerificationOutcome.VERIFIED

    controls_passed = negative_controls_passed(negative_controls)
    return VerificationResult(
        schema_version=MAINTENANCE_SCHEMA_VERSION,
        outcome=outcome,
        reasons=tuple(reasons),
        terminal=terminal and outcome is VerificationOutcome.VERIFIED,
        verified_windows=_normalize_windows(completed_checkpoints),
        verifier_principal=provenance.principal,
        proof_mode=(
            "negative_control"
            if controls_passed
            else ("unknown" if not negative_controls else "failed")
        ),
        negative_control_result=(
            "passed"
            if controls_passed
            else ("unknown" if not negative_controls else "failed")
        ),
        resumed_progress=bool(authoritative_progress_refs(progress_refs)),
    )


__all__ = [
    "ExpectedAuthority",
    "NegativeControlResult",
    "VerificationOutcome",
    "VerificationRejectReason",
    "VerificationResult",
    "authoritative_progress_refs",
    "checkpoint_set_complete",
    "evaluate_verification",
    "negative_controls_passed",
    "progress_beyond",
    "required_checkpoint_set",
]
