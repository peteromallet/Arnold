"""Report-only installed-runtime Maintenance canary driver (M3 Step 13 / T14).

This cloud adapter exercises the complete default-off M3 lifecycle through
the EXISTING M11 installed-runtime seams — it never recreates M11
infrastructure.  It reuses:

* **M11 installed-runtime identity** — the strict
  ``arnold.megaplan.m11_bound_runtime_identity.v1`` runtime receipt binding
  (``m11_workflow_canary._strict_runtime_binding``) plus the live-canary
  evidence helpers (content digests, append-only atomic JSON, private-root
  containment, UTC instants, :class:`CanarySafetyError`).
* **M11 isolated-relaunch and verifier evidence** — the distinct verifier
  provenance contract (``VerifierProvenance`` with runtime/source digests and
  direct owner-source read refs) that M11 produces; the canary *fences* the
  verifier against the admitted installed runtime (a source/runtime digest
  mismatch fails closed before anything runs).

The canary drives ONE occurrence-bound repair request, ONE allowlisted
effect, and ALL canonical checkpoints through the same cloud adapter seams
as production (``maintenance_recovery.submit_occurrence_bound_repair_request``
and ``route_allowlisted_effect``), then evaluates independent terminal
verification.  Every stage appends its durable result BEFORE any closure
decision, and every receipt is truthful and non-authorizing: reference-only
``OwnerRef`` receipts never authorize the next edge by themselves, and the
run stays report-only (custody open, no terminal submission) unless an
approved operator sign-off is injected (``authorizing=True``).

The settled journal contract derives the ``checkpoint_verification`` action
key from the strict coordinates (schema/occurrence/action/policy/target)
PLUS the checkpoint window, so every due window has a distinct durable
identity and an exact retry of the SAME window reproduces the SAME key
(dedup by window identity, never rewrite).  The canary drives EVERY due
window's fresh capture and independent evaluation and appends each verified
window's event before any closure decision — all four durable rows coexist.

Covered failure modes (closed typed outcomes, never guessed):

* forced install/retrigger failure → the effect route rejects with typed
  reasons and nothing is appended;
* kill-switch rollback → a truthful non-authorizing rollback receipt while
  observation, ledger, and replay stay available;
* stale verifier fencing → a stale/torn verifier capture is fenced
  (``STALE_AUTHORITY``) and no checkpoint window is completed;
* source/runtime digest mismatch → admission and/or verifier binding fail
  closed with typed ``MaintenanceCanaryError`` / ``VERIFIER_DIGEST_MISMATCH``.

SD1 is preserved: only this cloud adapter calls the canonical owner seams,
and this module never reimplements a lease store, effect ledger, repair
queue, verifier suite, or lifecycle writer.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)

from arnold_pipelines.megaplan.cloud.m11_live_canary import (
    CANARY_BASE,
    CanarySafetyError,
    _atomic_json,
    _canonical_bytes,
    _digest,
    _inside,
    _load_json,
    _sha256_file,
    _utc_now,
)
from arnold_pipelines.megaplan.cloud.m11_workflow_canary import (
    _strict_runtime_binding,
)
from arnold_pipelines.megaplan.cloud.maintenance_recovery import (
    EffectOutcome,
    EffectRoutingResult,
    RequestOutcome,
    RequestSubmissionResult,
    route_allowlisted_effect,
    submit_occurrence_bound_repair_request,
    submit_terminal_verification,
    TerminalOutcome,
)
from arnold_pipelines.megaplan.maintenance.checkpoints import (
    CANONICAL_CHECKPOINT_ORDER,
    CheckpointDueItem,
    due_checkpoints,
)
from arnold_pipelines.megaplan.maintenance.contracts import ObservationEnvelope
from arnold_pipelines.megaplan.maintenance.events import (
    CheckpointVerificationPayload,
    CheckpointWindowKind,
    OperationalEvent,
    TerminalVerificationPayload,
    VerifierProvenance,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    MAINTENANCE_SCHEMA_VERSION,
    OwnerRef,
    UtcTime,
    canonical_digest,
)
from arnold_pipelines.megaplan.maintenance.ledger import (
    MaintenanceEventConflict,
    MaintenanceLedger,
)
from arnold_pipelines.megaplan.maintenance.observation import capture_observation
from arnold_pipelines.megaplan.maintenance.operations import (
    OwnerReceipts,
    ProducerPrincipal,
    ProducerRole,
)
from arnold_pipelines.megaplan.maintenance.verification import (
    ExpectedAuthority,
    NegativeControlResult,
    VerificationOutcome,
    VerificationRejectReason,
    VerificationResult,
    evaluate_verification,
)

#: Canary artifact schema (M3 Step 13; distinct from the M11 schemas).
MAINTENANCE_CANARY_SCHEMA = "arnold.megaplan.maintenance_canary.v1"

#: One named child of the canary base owns one maintenance canary.
MAINTENANCE_CANARY_PREFIX = "maintenance-canary-"

_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

#: Global runtime roots the canary must never touch (mirrors M11).
_FORBIDDEN_ROOTS = frozenset(
    {
        Path("/workspace").resolve(),
        Path("/workspace/.megaplan").resolve(),
        Path("/workspace/.megaplan/cloud-sessions").resolve(),
        Path("/workspace/.megaplan/repair-queue").resolve(),
    }
)


class MaintenanceCanaryError(CanarySafetyError):
    """A typed fail-closed canary error over the M11 safety base.

    ``reason`` is a closed machine-readable code so callers can distinguish
    a source/runtime digest mismatch from an admission conflict without
    parsing the message.
    """

    def __init__(self, message: str, *, reason: str = "canary_error") -> None:
        super().__init__(message)
        self.reason = reason


class CanaryOutcome(str, Enum):
    """Closed outcome of one canary run.

    * ``COMPLETED`` — the full lifecycle was driven; the terminal receipt is
      truthful (submitted once when ``authorizing``, otherwise pending
      human sign-off with custody open);
    * ``REJECTED`` — a stage failed closed with typed reasons; nothing
      further ran and no terminal event was submitted;
    * ``ROLLED_BACK`` — a stage failure was followed by the kill-switch
      rollback receipt.
    """

    COMPLETED = "completed"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


class CanaryRejectReason(str, Enum):
    """Closed typed reasons for a rejected/rolled-back canary run."""

    VERIFIER_DIGEST_MISMATCH = "verifier_digest_mismatch"
    REQUEST_REJECTED = "request_rejected"
    EFFECT_REJECTED = "effect_rejected"
    CHECKPOINT_NOT_VERIFIED = "checkpoint_not_verified"
    STALE_VERIFIER = "stale_verifier"
    TERMINAL_NOT_VERIFIED = "terminal_not_verified"
    TERMINAL_BOUNDARY_BLOCKED = "terminal_boundary_blocked"


# ---------------------------------------------------------------------------
# Admission: bind the canary to the M11 installed-runtime identity
# ---------------------------------------------------------------------------


class MaintenanceCanaryAdmission(BaseModel):
    """The append-only admission binding one canary to the M11 runtime.

    ``runtime_digest`` / ``source_digest`` are bare sha256 hex so the canary
    can fence a distinct verifier's ``VerifierProvenance`` digests exactly.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # ``schema`` is the M11 artifact-key convention; the python name avoids
    # shadowing BaseModel.schema (pydantic emits a UserWarning otherwise).
    artifact_schema: Literal["arnold.megaplan.maintenance_canary.v1"] = Field(
        default=MAINTENANCE_CANARY_SCHEMA, alias="schema"
    )
    kind: Literal["maintenance_canary_admission"] = "maintenance_canary_admission"
    job_id: StrictStr
    deployment: dict[str, str]
    runtime_receipt: dict[str, Any]
    runtime_digest: StrictStr
    source_digest: StrictStr
    required_checkpoints: tuple[str, ...] = tuple(
        window.value for window in CANONICAL_CHECKPOINT_ORDER
    )
    admitted_at: StrictStr
    status: Literal["admitted"] = "admitted"
    content_sha256: StrictStr | None = None

    @field_validator("runtime_digest", "source_digest")
    @classmethod
    def _validate_digests(cls, value: str) -> str:
        if not _SHA256_HEX_RE.fullmatch(value):
            raise ValueError(
                "canary runtime/source digests must be 64-character lowercase "
                "sha256 hex digests"
            )
        return value

    @field_validator("job_id")
    @classmethod
    def _validate_job(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("canary job_id must be a non-empty string")
        return value


def validate_maintenance_canary_root(
    root: str | Path, *, base_root: str | Path = CANARY_BASE
) -> Path:
    """Require one named ``maintenance-canary-*`` child of the canary base.

    Mirrors the M11 root validators (one direct child, a reserved prefix,
    never a global runtime root) so the canary owns exactly one private
    directory and can never point at a live runtime root.
    """
    base = Path(base_root).resolve(strict=False)
    candidate = Path(root).resolve(strict=False)
    if candidate.parent != base or not candidate.name.startswith(
        MAINTENANCE_CANARY_PREFIX
    ):
        raise MaintenanceCanaryError(
            f"maintenance canary root must be one direct "
            f"{MAINTENANCE_CANARY_PREFIX!r} child of {base}",
            reason="invalid_canary_root",
        )
    if candidate in _FORBIDDEN_ROOTS:
        raise MaintenanceCanaryError(
            "global runtime roots are forbidden for a maintenance canary",
            reason="invalid_canary_root",
        )
    return candidate


def _source_lineage_digest(source_lineage: Mapping[str, Any]) -> str:
    """Deterministic source identity digest of the M11 runtime receipt.

    Prefers an explicit ``source_digest`` recorded on the source lineage;
    otherwise derives a content digest over the lineage coordinates
    (revision + expected_revision).  A malformed explicit digest fails
    closed — the source identity is never guessed.
    """
    explicit = source_lineage.get("source_digest")
    if explicit is not None:
        text = str(explicit)
        if text.startswith("sha256:"):
            text = text[len("sha256:") :]
        if _SHA256_HEX_RE.fullmatch(text):
            return text
        raise MaintenanceCanaryError(
            "runtime source_lineage carries a malformed source_digest",
            reason="invalid_runtime_binding",
        )
    revision = str(source_lineage.get("revision") or "")
    expected = str(source_lineage.get("expected_revision") or "")
    material = _canonical_bytes({"revision": revision, "expected_revision": expected})
    return hashlib.sha256(material).hexdigest()


def admit_maintenance_canary(
    *,
    root: str | Path,
    job_id: str,
    deployment_target: str,
    deployment_id: str,
    expected_revision: str,
    runtime_receipt_path: str | Path,
    expected_runtime_digest: str | None = None,
    expected_source_digest: str | None = None,
    base_root: str | Path = CANARY_BASE,
) -> MaintenanceCanaryAdmission:
    """Pin one canary to the exact M11 installed-runtime identity.

    Order (fail-closed at every step; nothing is written before the previous
    step is satisfied):

    1. the canary root must be one private ``maintenance-canary-*`` child of
       ``base_root``;
    2. the runtime receipt must be inside that root and must satisfy the
       FULL strict M11 runtime tuple (schema, valid, strict, expected
       revision, content digest, all bound components, source lineage, and
       deployment target/id marker) — reused from ``m11_workflow_canary``;
    3. the receipt's ``content_sha256`` must equal ``expected_runtime_digest``
       when pinned (runtime digest mismatch fails closed);
    4. the source identity digest must equal ``expected_source_digest`` when
       pinned (source/runtime digest mismatch fails closed);
    5. the admission artifact is written append-only (exclusive) and
       content-addressed.
    """
    private_root = validate_maintenance_canary_root(root, base_root=base_root)
    private_root.mkdir(parents=True, exist_ok=True)
    if not all(value.strip() for value in (job_id, deployment_target, deployment_id)):
        raise MaintenanceCanaryError(
            "canary job and deployment identities are required",
            reason="invalid_input",
        )
    if not _REVISION_RE.fullmatch(expected_revision):
        raise MaintenanceCanaryError(
            "expected revision must be a full lowercase git SHA",
            reason="invalid_input",
        )
    runtime_path = _inside(private_root, runtime_receipt_path, name="runtime receipt")
    try:
        runtime = _strict_runtime_binding(
            runtime_path,
            expected_revision=expected_revision,
            deployment_target=deployment_target,
            deployment_id=deployment_id,
        )
    except CanarySafetyError as exc:
        raise MaintenanceCanaryError(
            f"installed-runtime identity binding failed: {exc}",
            reason="invalid_runtime_binding",
        ) from exc

    runtime_digest = str(runtime["content_sha256"])
    if (
        expected_runtime_digest is not None
        and expected_runtime_digest != runtime_digest
    ):
        raise MaintenanceCanaryError(
            "maintenance canary runtime digest mismatch: "
            f"expected {expected_runtime_digest}, observed {runtime_digest}",
            reason="runtime_digest_mismatch",
        )
    components = runtime["components"]
    source_digest = _source_lineage_digest(components["source_lineage"])
    if expected_source_digest is not None and expected_source_digest != source_digest:
        raise MaintenanceCanaryError(
            "maintenance canary source/runtime digest mismatch: "
            f"expected source digest {expected_source_digest}, "
            f"observed {source_digest}",
            reason="source_runtime_digest_mismatch",
        )

    admission = MaintenanceCanaryAdmission(
        job_id=job_id,
        deployment={
            "target": deployment_target,
            "id": deployment_id,
            "expected_revision": expected_revision,
        },
        runtime_receipt={
            "path": str(runtime_path),
            "sha256": _sha256_file(runtime_path),
            "runtime_identity": f"sha256:{runtime_digest}",
        },
        runtime_digest=runtime_digest,
        source_digest=source_digest,
        admitted_at=_utc_now(),
    )
    payload = admission.model_dump(mode="json", by_alias=True)
    # The admission model serializes content_sha256 as null; hash the payload
    # WITHOUT that field so the artifact digest matches on load.
    payload.pop("content_sha256", None)
    payload["content_sha256"] = _digest(payload)
    try:
        _atomic_json(
            private_root / "maintenance-canary" / "admission.json",
            payload,
            exclusive=True,
        )
    except CanarySafetyError as exc:
        raise MaintenanceCanaryError(
            f"canary admission conflict: {exc}",
            reason="admission_conflict",
        ) from exc
    return MaintenanceCanaryAdmission.model_validate(payload)


def load_maintenance_canary_admission(
    root: str | Path, *, base_root: str | Path = CANARY_BASE
) -> MaintenanceCanaryAdmission:
    """Load and content-verify the append-only admission artifact."""
    private_root = validate_maintenance_canary_root(root, base_root=base_root)
    path = private_root / "maintenance-canary" / "admission.json"
    payload = _load_json(path)
    observed = str(payload.get("content_sha256") or "")
    unhashed = dict(payload)
    unhashed.pop("content_sha256", None)
    if not observed or observed != _digest(unhashed):
        raise MaintenanceCanaryError(
            f"canary admission content hash mismatch: {path}",
            reason="admission_conflict",
        )
    return MaintenanceCanaryAdmission.model_validate(payload)


def canary_verifier_binding_matches(
    admission: MaintenanceCanaryAdmission | Mapping[str, Any],
    verifier: VerifierProvenance,
) -> bool:
    """Whether the verifier evidence is bound to the admitted runtime.

    The distinct verifier must have run under the SAME installed runtime and
    SAME source digest the canary was admitted against; anything else is a
    source/runtime digest mismatch and is fenced before any lifecycle edge.
    """
    if isinstance(admission, MaintenanceCanaryAdmission):
        runtime_digest = admission.runtime_digest
        source_digest = admission.source_digest
    else:
        runtime_digest = str(admission.get("runtime_digest") or "")
        source_digest = str(admission.get("source_digest") or "")
    return (
        verifier.runtime_digest == runtime_digest
        and verifier.source_digest == source_digest
    )


# ---------------------------------------------------------------------------
# Stage outcomes
# ---------------------------------------------------------------------------


class CheckpointCanaryOutcome(BaseModel):
    """One due checkpoint window's evaluation and its durable append.

    ``appended`` is ``True`` only when the window's ``checkpoint_verification``
    event was accepted by the Maintenance ledger.  Each window has a
    distinct stable lifecycle key (base action key folded with the
    checkpoint window), so the four policy-required windows coexist as four
    durable rows; an exact retry of the SAME window reproduces the SAME key
    and is deduplicated, never rewritten.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    window: CheckpointWindowKind
    due: CheckpointDueItem
    verification: VerificationResult
    appended: bool
    append_reason: StrictStr | None = None
    event_id: StrictStr | None = None
    event_digest: StrictStr | None = None
    envelope_digest: StrictStr | None = None


class TerminalCanaryOutcome(BaseModel):
    """The terminal verification evaluation and its truthful receipt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    verification: VerificationResult
    submitted: bool
    pending_signoff: bool
    event_id: StrictStr | None = None
    event_digest: StrictStr | None = None
    envelope_digest: StrictStr | None = None


class RollbackCanaryReceipt(BaseModel):
    """Truthful non-authorizing kill-switch rollback receipt.

    Records that effects are disabled, that the Maintenance ledger and its
    replay machinery remain available (nothing was deleted), and that
    canonical custody stays OPEN — a rollback never closes custody and
    never waives a gate.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: StrictStr
    reason: StrictStr
    effects_disabled: bool
    ledger_event_count: int
    replay_replayed: int
    replay_pending: int
    custody_open: bool
    authorizing: bool = False
    receipt_ref: OwnerRef | None = None
    receipt_digest: StrictStr | None = None
    recorded_at: StrictStr


class CanaryRunResult(BaseModel):
    """The typed fail-closed outcome of one canary run.

    ``outcome`` is ``completed`` only when the full lifecycle was driven.
    ``custody_open`` is ``True`` whenever the terminal event was NOT
    submitted (every rejection, every rollback, and every report-only
    completion); only an authorizing run with a verified terminal result
    submits the terminal event exactly once and closes custody.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    run_id: StrictStr
    outcome: CanaryOutcome
    reasons: tuple[CanaryRejectReason, ...] = ()
    admission_digest: StrictStr | None = None
    request: RequestSubmissionResult | None = None
    effect: EffectRoutingResult | None = None
    checkpoints: tuple[CheckpointCanaryOutcome, ...] = ()
    terminal: TerminalCanaryOutcome | None = None
    rollback: RollbackCanaryReceipt | None = None
    custody_open: bool = True
    terminal_submitted: bool = False
    authorizing: bool = False
    artifact_path: StrictStr | None = None

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("run_id")
    @classmethod
    def _validate_run_id(cls, value: str) -> str:
        if not value:
            raise ValueError("canary run_id must be a non-empty string")
        return value

    @model_validator(mode="after")
    def _enforce_fail_closed(self) -> CanaryRunResult:
        if self.outcome is CanaryOutcome.REJECTED and not self.reasons:
            raise ValueError(
                "a rejected canary run requires at least one typed reject reason"
            )
        if self.terminal_submitted and self.custody_open:
            raise ValueError(
                "a submitted terminal event closes custody; custody_open "
                "must be False"
            )
        if not self.terminal_submitted and not self.custody_open:
            raise ValueError(
                "custody stays open unless the terminal event was submitted"
            )
        return self


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _evidence_refs(
    envelope: ObservationEnvelope,
    controls: Sequence[NegativeControlResult],
) -> tuple[OwnerRef, ...]:
    """Deduplicated, precedence-ordered durable evidence references."""
    refs: list[OwnerRef] = list(envelope.references)
    for control in controls:
        if control.control_ref not in refs:
            refs.append(control.control_ref)
    return tuple(
        sorted(
            refs,
            key=lambda ref: (
                ref.owner,
                ref.locator,
                ref.digest or "",
                ref.cursor or "",
            ),
        )
    )


def _verifier_producer(principal: str) -> ProducerPrincipal:
    """The distinct verifier principal that authors verification events."""
    return ProducerPrincipal(principal=principal, role=ProducerRole.VERIFIER)


def _persist_json(
    private_root: Path,
    relative: Path,
    payload: Mapping[str, Any],
    *,
    exclusive: bool,
) -> Path:
    """Write one content-addressed canary artifact under the private root."""
    path = _inside(
        private_root, private_root / relative, name="canary artifact"
    )
    data = dict(payload)
    data["content_sha256"] = _digest(data)
    _atomic_json(path, data, exclusive=exclusive)
    return path


def _append_operational_event(
    ledger: MaintenanceLedger,
    event: OperationalEvent,
    *,
    event_id: str,
    envelope_digest: str,
) -> tuple[str, str]:
    """Append one operational event at most once; fail closed on conflict.

    Returns ``(event_id, event_digest)``.  A divergent reuse of the
    occurrence action key raises ``MaintenanceEventConflict`` (nothing is
    appended) — the canary never rewrites history.
    """
    try:
        ledger.append(event)
    except MaintenanceEventConflict as exc:
        raise MaintenanceCanaryError(
            f"canary lifecycle append diverged for {event_id}: {exc}",
            reason="divergent_reuse",
        ) from exc
    return event_id, canonical_digest(event)


# ---------------------------------------------------------------------------
# The lifecycle driver
# ---------------------------------------------------------------------------


def run_maintenance_canary(
    *,
    root: str | Path,
    run_id: str,
    admission: MaintenanceCanaryAdmission | Mapping[str, Any],
    verifier: VerifierProvenance,
    negative_controls: Sequence[NegativeControlResult],
    pre_repair_ref: OwnerRef,
    progress_refs: Sequence[OwnerRef],
    request_kwargs: Mapping[str, Any],
    effect_kwargs: Mapping[str, Any],
    anchor_at: UtcTime | datetime,
    now: UtcTime | datetime,
    checkpoint_policy: Sequence[CheckpointWindowKind | str] | None = None,
    expected_authority: ExpectedAuthority | None = None,
    terminal_expected_authority: ExpectedAuthority | None = None,
    terminal_reason: str = "independent verification of the controlled canary",
    final_boundary_fn: Callable[[], Any] | None = None,
    authorizing: bool = False,
    rollback_on_failure: bool = False,
    base_root: str | Path = CANARY_BASE,
    persist: bool = True,
) -> CanaryRunResult:
    """Drive ONE request, ONE effect, and ALL due checkpoints (report-only).

    Stage order (fail-closed; every result is appended before any closure
    decision):

    0. **Verifier fencing.**  The distinct verifier evidence must be bound
       to the admitted M11 installed runtime (runtime AND source digests
       match); a source/runtime digest mismatch rejects the whole run with
       ``VERIFIER_DIGEST_MISMATCH`` before any lifecycle edge.
    1. **One request.**  ``submit_occurrence_bound_repair_request`` (the
       canonical enqueue-or-join seam) — rejected requests stop the run.
    2. **One effect.**  ``route_allowlisted_effect`` (claim/source/install/
       retrigger) — a forced install or retrigger failure stops the run
       (and records the kill-switch rollback when ``rollback_on_failure``).
    3. **All due checkpoints.**  For each due window in event-time order the
       canary takes a FRESH coherent owner-source capture and evaluates
       independent (non-terminal) verification; a verified window appends
       its ``checkpoint_verification`` event BEFORE any closure decision.  A
       stale/torn verifier capture is fenced (``STALE_AUTHORITY``) and the
       window is never completed.
    4. **Terminal.**  With the complete policy-required checkpoint set, the
       canary re-reads a fresh envelope (plus the optional final
       action-validator reread) and evaluates terminal verification.  A
       verified terminal result is submitted EXACTLY ONCE only when
       ``authorizing`` (operator sign-off); the default report-only run
       records a truthful non-authorizing ``pending_signoff`` receipt and
       canonical custody stays OPEN.
    """
    private_root = validate_maintenance_canary_root(root, base_root=base_root)
    private_root.mkdir(parents=True, exist_ok=True)
    if isinstance(admission, MaintenanceCanaryAdmission):
        admission_model = admission
    else:
        admission_model = MaintenanceCanaryAdmission.model_validate(admission)
    admission_digest = admission_model.content_sha256

    def _rejected(
        *reasons: CanaryRejectReason,
        request: RequestSubmissionResult | None = None,
        effect: EffectRoutingResult | None = None,
        checkpoints: Sequence[CheckpointCanaryOutcome] = (),
        terminal: TerminalCanaryOutcome | None = None,
        rollback: RollbackCanaryReceipt | None = None,
        outcome: CanaryOutcome = CanaryOutcome.REJECTED,
    ) -> CanaryRunResult:
        return CanaryRunResult(
            run_id=run_id,
            outcome=outcome,
            reasons=tuple(dict.fromkeys(reasons)),
            admission_digest=admission_digest,
            request=request,
            effect=effect,
            checkpoints=tuple(checkpoints),
            terminal=terminal,
            rollback=rollback,
            custody_open=True,
            terminal_submitted=False,
            authorizing=authorizing,
        )

    # 0. Verifier fencing against the admitted installed runtime.
    if not canary_verifier_binding_matches(admission_model, verifier):
        return _rejected(CanaryRejectReason.VERIFIER_DIGEST_MISMATCH)

    ledger = request_kwargs.get("ledger") or MaintenanceLedger(private_root)
    request_kwargs = dict(request_kwargs)
    request_kwargs["ledger"] = ledger
    request_kwargs["terminal_receipt_expectations"] = [
        window.value for window in CANONICAL_CHECKPOINT_ORDER
    ]

    # 1. One occurrence-bound repair request.
    request = submit_occurrence_bound_repair_request(**request_kwargs)
    if request.outcome is RequestOutcome.REJECTED:
        return _rejected(CanaryRejectReason.REQUEST_REJECTED, request=request)

    # 2. One allowlisted effect (claim/source/install/retrigger).
    effect_kwargs = dict(effect_kwargs)
    effect_kwargs["ledger"] = ledger
    effect = route_allowlisted_effect(**effect_kwargs)
    if effect.outcome is EffectOutcome.REJECTED:
        if rollback_on_failure:
            rollback = rollback_maintenance_canary(
                root=private_root,
                run_id=run_id,
                ledger=ledger,
                reason="forced install/retrigger failure triggered the kill switch",
                base_root=base_root,
            )
            return _rejected(
                CanaryRejectReason.EFFECT_REJECTED,
                request=request,
                effect=effect,
                rollback=rollback,
                outcome=CanaryOutcome.ROLLED_BACK,
            )
        return _rejected(CanaryRejectReason.EFFECT_REJECTED, request=request, effect=effect)

    # Coordinates inherited from the request decision (never guessed).
    occurrence = request_kwargs["occurrence"]
    lease = request_kwargs["lease"]
    run_authority = request_kwargs["run_authority"]
    policy = request_kwargs["policy"]
    target = request_kwargs["target"]
    producer = request_kwargs["producer"]
    wbc_attempt = request_kwargs.get("wbc_attempt")
    sources = request_kwargs["sources"]
    environment = request_kwargs.get("environment")
    run = request_kwargs.get("run")
    attempt = request_kwargs.get("attempt")
    expected = request_kwargs.get("expected")
    fence = expected.fencing_token if expected is not None else None

    # 3. All due checkpoints (event-time order, anchored to the durable
    #    effect receipt).
    checkpoint_outcomes: list[CheckpointCanaryOutcome] = []
    completed_windows: list[CheckpointWindowKind] = []
    due = due_checkpoints(
        anchor_at=anchor_at,
        now=now,
        policy=checkpoint_policy,
        occurrence_id=occurrence.occurrence_id,
        lease_id=lease.lease_id,
        custody_epoch=lease.custody_epoch,
        fencing_token=fence,
        anchor_ref=effect.effect_ref,
    )
    for item in due:
        envelope = capture_observation(
            sources,
            observed_at=now,
            environment=environment,
            run=run,
            attempt=attempt,
            occurrence_id=occurrence.occurrence_id,
            target=target.target,
            lease_id=lease.lease_id,
            fence=fence,
        )
        result = evaluate_verification(
            provenance=verifier,
            producer=producer,
            envelope=envelope,
            negative_controls=negative_controls,
            completed_checkpoints=tuple(completed_windows),
            pre_repair_ref=pre_repair_ref,
            progress_refs=progress_refs,
            expected=expected_authority,
            terminal=False,
        )
        envelope_digest = canonical_digest(envelope)
        if result.outcome is not VerificationOutcome.VERIFIED:
            checkpoint_outcomes.append(
                CheckpointCanaryOutcome(
                    window=item.window,
                    due=item,
                    verification=result,
                    appended=False,
                    envelope_digest=envelope_digest,
                )
            )
            reason = (
                CanaryRejectReason.STALE_VERIFIER
                if VerificationRejectReason.STALE_AUTHORITY in result.reasons
                else CanaryRejectReason.CHECKPOINT_NOT_VERIFIED
            )
            return _rejected(
                reason,
                request=request,
                effect=effect,
                checkpoints=checkpoint_outcomes,
            )

        checkpoint_ref = OwnerRef(
            owner="repair_custody",
            record_type="checkpoint",
            identity=item.window.value,
            locator=f"checkpoint://{occurrence.occurrence_id}/{item.window.value}",
            digest=result.digest,
        )
        event = OperationalEvent.build(
            event_id=f"checkpoint_verification:{occurrence.occurrence_id}:{item.window.value}",
            occurrence=occurrence,
            lease=lease,
            run_authority=run_authority,
            policy=policy,
            target=target,
            producer=_verifier_producer(verifier.principal),
            payload=CheckpointVerificationPayload(
                checkpoint=item.window,
                checkpoint_ref=checkpoint_ref,
                evidence_refs=_evidence_refs(envelope, negative_controls),
            ),
            observed_at=now,
            wbc_attempt=wbc_attempt,
            owner_receipts=OwnerReceipts(receipt_refs=(checkpoint_ref,)),
        )
        event_id, event_digest = _append_operational_event(
            ledger, event, event_id=event.event_id, envelope_digest=envelope_digest
        )
        completed_windows.append(item.window)
        checkpoint_outcomes.append(
            CheckpointCanaryOutcome(
                window=item.window,
                due=item,
                verification=result,
                appended=True,
                event_id=event_id,
                event_digest=event_digest,
                envelope_digest=envelope_digest,
            )
        )

    # 4. Terminal evaluation (only with the complete durable set).
    terminal: TerminalCanaryOutcome | None = None
    if (
        tuple(completed_windows) != tuple(CANONICAL_CHECKPOINT_ORDER)
        or len(checkpoint_outcomes) != len(CANONICAL_CHECKPOINT_ORDER)
        or not all(item.appended for item in checkpoint_outcomes)
    ):
        return _rejected(
            CanaryRejectReason.CHECKPOINT_NOT_VERIFIED,
            request=request,
            effect=effect,
            checkpoints=checkpoint_outcomes,
        )
    if final_boundary_fn is None and authorizing:
        return _rejected(
            CanaryRejectReason.TERMINAL_BOUNDARY_BLOCKED,
            request=request,
            effect=effect,
            checkpoints=checkpoint_outcomes,
        )
    terminal_envelope = capture_observation(
        sources,
        observed_at=now,
        environment=environment,
        run=run,
        attempt=attempt,
        occurrence_id=occurrence.occurrence_id,
        target=target.target,
        lease_id=lease.lease_id,
        fence=fence,
    )
    terminal_envelope_digest = canonical_digest(terminal_envelope)
    terminal_result = evaluate_verification(
        provenance=verifier,
        producer=producer,
        envelope=terminal_envelope,
        negative_controls=negative_controls,
        completed_checkpoints=tuple(completed_windows),
        pre_repair_ref=pre_repair_ref,
        progress_refs=progress_refs,
        expected=terminal_expected_authority or expected_authority,
        terminal=True,
    )
    if terminal_result.outcome is VerificationOutcome.VERIFIED and authorizing:
        verification_ref = OwnerRef(
            owner="repair_custody",
            record_type="verification",
            identity=occurrence.occurrence_id,
            locator=f"verification://{occurrence.occurrence_id}",
            digest=terminal_result.digest,
        )
        submission = submit_terminal_verification(
            occurrence=occurrence,
            lease=lease,
            run_authority=request_kwargs["run_authority"],
            policy=policy,
            target=target,
            producer=producer,
            observed_at=now,
            verifier=verifier,
            terminal_reason=terminal_reason,
            negative_control_refs=tuple(
                control.control_ref for control in negative_controls
            ),
            verification_ref=verification_ref,
            sources=sources,
            environment=environment,
            run=run,
            attempt=attempt,
            expected=expected,
            boundary_fn=final_boundary_fn,
            ledger=ledger,
            wbc_attempt=wbc_attempt,
            request_kwargs=request_kwargs,
        )
        if submission.outcome is TerminalOutcome.REJECTED:
            return _rejected(
                CanaryRejectReason.TERMINAL_BOUNDARY_BLOCKED,
                request=request,
                effect=effect,
                checkpoints=checkpoint_outcomes,
                terminal=TerminalCanaryOutcome(
                    verification=terminal_result,
                    submitted=False,
                    pending_signoff=False,
                    envelope_digest=terminal_envelope_digest,
                ),
            )
        terminal = TerminalCanaryOutcome(
            verification=terminal_result,
            submitted=True,
            pending_signoff=False,
            event_id=submission.event_id,
            event_digest=submission.event_digest,
            envelope_digest=terminal_envelope_digest,
        )
    elif terminal_result.outcome is VerificationOutcome.VERIFIED:
        terminal = TerminalCanaryOutcome(
            verification=terminal_result,
            submitted=False,
            pending_signoff=True,
            envelope_digest=terminal_envelope_digest,
        )
    else:
        reason = (
            CanaryRejectReason.STALE_VERIFIER
            if VerificationRejectReason.STALE_AUTHORITY
            in terminal_result.reasons
            else CanaryRejectReason.TERMINAL_NOT_VERIFIED
        )
        return _rejected(
            reason,
            request=request,
            effect=effect,
            checkpoints=checkpoint_outcomes,
            terminal=TerminalCanaryOutcome(
                verification=terminal_result,
                submitted=False,
                pending_signoff=False,
                envelope_digest=terminal_envelope_digest,
            ),
        )

    result = CanaryRunResult(
        run_id=run_id,
        outcome=CanaryOutcome.COMPLETED,
        admission_digest=admission_digest,
        request=request,
        effect=effect,
        checkpoints=tuple(checkpoint_outcomes),
        terminal=terminal,
        custody_open=not (terminal is not None and terminal.submitted),
        terminal_submitted=terminal is not None and terminal.submitted,
        authorizing=authorizing,
    )
    if persist:
        try:
            artifact = _persist_json(
                private_root,
                Path("maintenance-canary") / "run" / f"{run_id}.json",
                result.model_dump(mode="json"),
                exclusive=True,
            )
        except CanarySafetyError:
            artifact = None
        result = CanaryRunResult.model_validate(
            {**result.model_dump(mode="json"), "artifact_path": str(artifact) if artifact else None}
        )
    return result


# ---------------------------------------------------------------------------
# Kill-switch rollback
# ---------------------------------------------------------------------------


def rollback_maintenance_canary(
    *,
    root: str | Path,
    run_id: str,
    ledger: MaintenanceLedger | None = None,
    reason: str,
    mutation_gate_fn: Callable[[str], bool] | None = None,
    base_root: str | Path = CANARY_BASE,
) -> RollbackCanaryReceipt:
    """Record a truthful non-authorizing kill-switch rollback.

    The kill switch requires effects to be DISABLED: when a mutation-gate
    predicate is supplied and authorizes the L1 path, the rollback is
    REFUSED (``MaintenanceCanaryError`` ``rollback_refused``) — a rollback
    while effects are still authorized would be a lie.

    The rollback preserves observation, ledger, and replay: the Maintenance
    ledger is re-read (its event count is recorded), the dead-letter replay
    machinery is exercised (idempotent, append-only), and canonical custody
    is recorded as OPEN.  The receipt is non-authorizing: it never closes
    custody and never waives a gate.
    """
    private_root = validate_maintenance_canary_root(root, base_root=base_root)
    private_root.mkdir(parents=True, exist_ok=True)
    if not str(reason).strip():
        raise MaintenanceCanaryError(
            "kill-switch rollback requires a non-empty reason",
            reason="invalid_input",
        )
    if mutation_gate_fn is not None and mutation_gate_fn("l1") is True:
        raise MaintenanceCanaryError(
            "kill-switch rollback refused: mutation effects are still "
            "authorized on the L1 path",
            reason="rollback_refused",
        )
    ledger = ledger if ledger is not None else MaintenanceLedger(private_root)
    event_count = 0
    if ledger.events_path.exists():
        with ledger.events_path.open("r", encoding="utf-8") as handle:
            event_count = sum(1 for line in handle if line.strip())
    report = ledger.replay_dead_letters()

    receipt = RollbackCanaryReceipt(
        run_id=run_id,
        reason=str(reason).strip(),
        effects_disabled=True,
        ledger_event_count=event_count,
        replay_replayed=report.replayed_count,
        replay_pending=report.pending_or_failed_count,
        custody_open=True,
        authorizing=False,
        recorded_at=_utc_now(),
    )
    payload = receipt.model_dump(mode="json")
    payload["content_sha256"] = _digest(payload)
    path = _inside(
        private_root,
        private_root / "maintenance-canary" / "rollback" / f"{run_id}.json",
        name="rollback receipt",
    )
    _atomic_json(path, payload, exclusive=True)
    return RollbackCanaryReceipt.model_validate(
        {
            **{key: value for key, value in payload.items() if key != "content_sha256"},
            "receipt_ref": OwnerRef(
                owner="repair_custody",
                record_type="rollback_receipt",
                identity=run_id,
                locator=f"rollback://{run_id}",
                digest=str(payload["content_sha256"]).removeprefix("sha256:"),
            ).model_dump(mode="json"),
            "receipt_digest": str(payload["content_sha256"]).removeprefix("sha256:"),
        }
    )


__all__ = [
    "CANONICAL_CHECKPOINT_ORDER",
    "CanaryOutcome",
    "CanaryRejectReason",
    "CanaryRunResult",
    "CheckpointCanaryOutcome",
    "MAINTENANCE_CANARY_PREFIX",
    "MAINTENANCE_CANARY_SCHEMA",
    "MaintenanceCanaryAdmission",
    "MaintenanceCanaryError",
    "RollbackCanaryReceipt",
    "TerminalCanaryOutcome",
    "admit_maintenance_canary",
    "canary_verifier_binding_matches",
    "load_maintenance_canary_admission",
    "rollback_maintenance_canary",
    "run_maintenance_canary",
    "validate_maintenance_canary_root",
]
