"""Steps 11B, 12B, 12C: double-fenced authority gate at action time.

This module implements the main action-time authority gate that
**rereads** the current Run Authority, Custody, and WBC state at the
moment an action is attempted — it never trusts projections, synthetic
defaults, or outbox-only evidence.

The gate is *double-fenced*:

1. **First fence — per-source reread**: each authority source (Run
   Authority grant/fence, Custody lease, WBC attempt) is reread from
   its durable store.  No projection or cached view is trusted.

2. **Second fence — conjunctive gate**: all three sources must return
   SATISFIED.  Any non-SATISFIED outcome blocks the action.  Shadow
   results never authorize.

Step 12B: WBC evidence must come from the WBC store (global reservation
state), NOT from Custody outbox projections or synthetic ``wbc-ref-*``
strings.  Projection-only evidence is rejected.

Step 12C: enforcement is staged by action family.  Each action family
(git, cloud, custody, native) has an independent enablement flag.
Until a family's flag is set, the gate runs in SHADOW mode (records
the decision but does not block).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from arnold_pipelines.run_authority.current_source import (
    DENIED,
    CurrentSourceRequest,
    CurrentSourceResult,
    evaluate_current_source,
)

__all__ = [
    "ActionFamily",
    "ActionGateVerdict",
    "ActionGateResult",
    "ActionGateDecision",
    "WbcEvidenceKind",
    "WbcEvidence",
    "ActionGateConfig",
    "ActionGate",
    "evaluate_action_gate",
]


# ── Action families (Step 12C) ──────────────────────────────────────────────


class ActionFamily(str, Enum):
    """Mutation families staged for enforcement."""

    GIT = "git"
    CLOUD = "cloud"
    CUSTODY = "custody"
    NATIVE = "native"
    EFFECT = "effect"


# Families that have full coverage and are safe to enforce.
_DEFAULT_ENFORCED: frozenset[ActionFamily] = frozenset()


# ── WBC evidence classification (Step 12B) ──────────────────────────────────


class WbcEvidenceKind(str, Enum):
    """How WBC evidence was obtained — only STORE is authoritative."""

    STORE = "store"
    """Evidence read directly from the WBC attempt ledger store."""

    OUTBOX = "outbox"
    """Evidence from the Custody outbox projection (NOT authoritative)."""

    SYNTHETIC = "synthetic"
    """Synthetic ``wbc-ref-*`` string (NEVER authoritative)."""

    PROJECTION = "projection"
    """Derived or computed projection (NEVER authoritative)."""

    MISSING = "missing"
    """No WBC evidence available."""


@dataclass(frozen=True)
class WbcEvidence:
    """WBC evidence observed at action time."""

    kind: WbcEvidenceKind
    attempt_reference: str = ""
    global_logical_effect_key: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def is_authoritative(self) -> bool:
        """Only STORE evidence is authoritative."""
        return self.kind == WbcEvidenceKind.STORE


# ── Gate verdicts ───────────────────────────────────────────────────────────


class ActionGateVerdict(str, Enum):
    """Overall gate verdict."""

    AUTHORIZED = "AUTHORIZED"
    SHADOW_AUTHORIZED = "SHADOW_AUTHORIZED"
    SHADOW_BLOCKED = "SHADOW_BLOCKED"
    BLOCKED_RA_UNSATISFIED = "BLOCKED_RA_UNSATISFIED"
    BLOCKED_CUSTODY = "BLOCKED_CUSTODY"
    BLOCKED_WBC_PROJECTION = "BLOCKED_WBC_PROJECTION"
    BLOCKED_WBC_MISSING = "BLOCKED_WBC_MISSING"
    BLOCKED_WBC_SYNTHETIC = "BLOCKED_WBC_SYNTHETIC"
    BLOCKED_WBC_CONFLICT = "BLOCKED_WBC_CONFLICT"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ActionGateResult:
    """Per-source reread results + overall verdict."""

    verdict: ActionGateVerdict
    ra_result: Optional[CurrentSourceResult]
    custody_active: Optional[bool]
    custody_detail: dict[str, Any]
    wbc_evidence: WbcEvidence
    diagnostics: dict[str, Any]
    enforcement_enabled: bool

    @property
    def is_authorized(self) -> bool:
        return self.verdict == ActionGateVerdict.AUTHORIZED


@dataclass(frozen=True)
class ActionGateDecision:
    """Final decision record for audit/diagnostics."""

    action_family: ActionFamily
    action_target: str
    result: ActionGateResult
    timestamp: str

    @property
    def authorized(self) -> bool:
        return self.result.is_authorized


# ── Gate configuration ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ActionGateConfig:
    """Configuration for the action gate.

    The ``enforced_families`` set controls Step 12C staging: only
    families in this set enforce.  All others run in shadow mode.

    M11 Step 10 (``wbc_evidence_only``):
        When ``True``, the gate requires current Run Authority grant/fence
        **and** current Custody lease/epoch as authority sources.  Absent
        RA or Custody checks BLOCK (stale-half fix) — they do not fall
        through to AUTHORIZED.  WBC is treated as evidence-only: it is
        recorded in the decision diagnostics but never gates the verdict.

        When ``False`` (default, pre-M11 behaviour), WBC remains a blocking
        authority source alongside RA and Custody.
    """

    enforced_families: frozenset[ActionFamily] = _DEFAULT_ENFORCED
    require_wbc_store_evidence: bool = True
    wbc_evidence_only: bool = False

    def is_enforced(self, family: ActionFamily) -> bool:
        return family in self.enforced_families


# ── Gate ────────────────────────────────────────────────────────────────────


class ActionGate:
    """Double-fenced authority gate evaluated at action time.

    Usage::

        gate = ActionGate(
            config=ActionGateConfig(
                enforced_families=frozenset({ActionFamily.GIT}),
            ),
            ra_view_provider=lambda: reducer.build_view(...),
            custody_lease_provider=lambda attempt_id: lease_store.get(...),
            wbc_store_provider=lambda ref: store.get_reservation(...),
        )
        decision = gate.evaluate(
            action_family=ActionFamily.GIT,
            action_target="pr_merge",
            ra_request=CurrentSourceRequest(...),
            wbc_attempt_reference="att-123",
        )
        if not decision.authorized:
            raise ActionBlockedError(decision.result.verdict)
    """

    def __init__(
        self,
        *,
        config: Optional[ActionGateConfig] = None,
        ra_view_provider: Optional[Callable[[], Any]] = None,
        custody_lease_provider: Optional[Callable[[str], Any]] = None,
        wbc_store_provider: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self._config = config or ActionGateConfig()
        self._ra_view_provider = ra_view_provider
        self._custody_lease_provider = custody_lease_provider
        self._wbc_store_provider = wbc_store_provider

    def evaluate(
        self,
        *,
        action_family: ActionFamily,
        action_target: str,
        ra_request: Optional[CurrentSourceRequest] = None,
        wbc_attempt_reference: str = "",
        custody_attempt_id: str = "",
    ) -> ActionGateDecision:
        """Evaluate the double-fenced gate for a single action."""
        import datetime

        enforcement = self._config.is_enforced(action_family)

        # ── First fence: per-source reread ──────────────────────────

        # Run Authority
        ra_result: Optional[CurrentSourceResult] = None
        if self._ra_view_provider is not None and ra_request is not None:
            try:
                view = self._ra_view_provider()
                ra_result = evaluate_current_source(view, ra_request)
            except Exception as exc:
                ra_result = CurrentSourceResult(
                    DENIED,
                    f"RA reread error: {type(exc).__name__}: {exc}",
                    {},
                )

        # Custody lease
        custody_active: Optional[bool] = None
        custody_detail: dict[str, Any] = {}
        if self._custody_lease_provider is not None and custody_attempt_id:
            try:
                lease = self._custody_lease_provider(custody_attempt_id)
                if lease is None:
                    custody_active = False
                    custody_detail = {"reason": "no active lease"}
                else:
                    custody_active = True
                    custody_detail = {
                        "lease_id": getattr(lease, "lease_id", ""),
                        "custody_epoch": getattr(lease, "custody_epoch", 0),
                    }
            except Exception as exc:
                custody_active = False
                custody_detail = {
                    "reason": f"custody reread error: {type(exc).__name__}: {exc}",
                }

        # WBC evidence (Step 12B: only STORE evidence is authoritative)
        wbc_evidence = self._reread_wbc_evidence(wbc_attempt_reference)

        # ── Second fence: conjunctive gate ─────────────────────────

        verdict = self._compute_verdict(
            enforcement=enforcement,
            ra_result=ra_result,
            custody_active=custody_active,
            wbc_evidence=wbc_evidence,
            wbc_evidence_only=self._config.wbc_evidence_only,
        )

        result = ActionGateResult(
            verdict=verdict,
            ra_result=ra_result,
            custody_active=custody_active,
            custody_detail=custody_detail,
            wbc_evidence=wbc_evidence,
            diagnostics={
                "action_family": action_family.value,
                "action_target": action_target,
                "enforcement_enabled": enforcement,
                "gate_schema_version": "m10-action-gate-v1",
                "wbc_evidence_only": self._config.wbc_evidence_only,
            },
            enforcement_enabled=enforcement,
        )

        return ActionGateDecision(
            action_family=action_family,
            action_target=action_target,
            result=result,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    def _reread_wbc_evidence(self, wbc_attempt_reference: str) -> WbcEvidence:
        """Step 12B: read WBC evidence from the store, reject projections."""
        if not wbc_attempt_reference:
            return WbcEvidence(kind=WbcEvidenceKind.MISSING)

        # Reject synthetic references
        if wbc_attempt_reference.startswith("wbc-ref-"):
            return WbcEvidence(
                kind=WbcEvidenceKind.SYNTHETIC,
                attempt_reference=wbc_attempt_reference,
            )

        if self._wbc_store_provider is None:
            return WbcEvidence(
                kind=WbcEvidenceKind.MISSING,
                attempt_reference=wbc_attempt_reference,
            )

        try:
            reservation = self._wbc_store_provider(wbc_attempt_reference)
            if reservation is None:
                return WbcEvidence(
                    kind=WbcEvidenceKind.MISSING,
                    attempt_reference=wbc_attempt_reference,
                )
            return WbcEvidence(
                kind=WbcEvidenceKind.STORE,
                attempt_reference=wbc_attempt_reference,
                global_logical_effect_key=getattr(
                    reservation, "global_logical_effect_key", ""
                ),
                detail={
                    "attempt_id": getattr(reservation, "attempt_id", ""),
                    "effect_family": getattr(
                        getattr(reservation, "effect_identity", None),
                        "effect_family",
                        "",
                    ),
                },
            )
        except Exception:
            return WbcEvidence(
                kind=WbcEvidenceKind.MISSING,
                attempt_reference=wbc_attempt_reference,
            )

    def _compute_verdict(
        self,
        *,
        enforcement: bool,
        ra_result: Optional[CurrentSourceResult],
        custody_active: Optional[bool],
        wbc_evidence: WbcEvidence,
        wbc_evidence_only: bool = False,
    ) -> ActionGateVerdict:
        """Compute the overall verdict (second fence).

        When *wbc_evidence_only* is ``True`` (M11 Step 10), authority is
        created **only** from current Run Authority grant/fence and current
        Custody lease/epoch.  Absent authority checks BLOCK (stale-half fix).
        WBC is recorded as evidence but never gates the verdict.
        """
        if not enforcement:
            # Shadow mode: check but don't block
            if ra_result is not None and not ra_result.status.is_satisfied:
                return ActionGateVerdict.SHADOW_BLOCKED
            return ActionGateVerdict.SHADOW_AUTHORIZED

        # ── M11 Step 10: RA + Custody required, WBC evidence-only ──────
        if wbc_evidence_only:
            # Run Authority: required authority source.
            # Stale-half fix: absent RA BLOCKS — it must not fall through.
            if ra_result is None:
                return ActionGateVerdict.BLOCKED_RA_UNSATISFIED
            if not ra_result.status.is_satisfied:
                return ActionGateVerdict.BLOCKED_RA_UNSATISFIED

            # Custody lease: required authority source.
            # Stale-half fix: absent custody BLOCKS.
            if custody_active is None or not custody_active:
                return ActionGateVerdict.BLOCKED_CUSTODY

            # WBC: evidence-only — recorded in diagnostics, never gates.
            return ActionGateVerdict.AUTHORIZED

        # ── Legacy behaviour (pre-M11): WBC is a blocking authority source

        # Run Authority
        if ra_result is not None and not ra_result.status.is_satisfied:
            return ActionGateVerdict.BLOCKED_RA_UNSATISFIED

        # Custody
        if custody_active is not None and not custody_active:
            return ActionGateVerdict.BLOCKED_CUSTODY

        # WBC (Step 12B: reject projections, synthetic, missing)
        if self._config.require_wbc_store_evidence:
            if wbc_evidence.kind == WbcEvidenceKind.SYNTHETIC:
                return ActionGateVerdict.BLOCKED_WBC_SYNTHETIC
            if wbc_evidence.kind == WbcEvidenceKind.PROJECTION:
                return ActionGateVerdict.BLOCKED_WBC_PROJECTION
            if wbc_evidence.kind == WbcEvidenceKind.OUTBOX:
                return ActionGateVerdict.BLOCKED_WBC_PROJECTION
            if wbc_evidence.kind == WbcEvidenceKind.MISSING:
                return ActionGateVerdict.BLOCKED_WBC_MISSING

        return ActionGateVerdict.AUTHORIZED


def evaluate_action_gate(
    *,
    config: Optional[ActionGateConfig] = None,
    ra_view_provider: Optional[Callable[[], Any]] = None,
    custody_lease_provider: Optional[Callable[[str], Any]] = None,
    wbc_store_provider: Optional[Callable[[str], Any]] = None,
    action_family: ActionFamily = ActionFamily.EFFECT,
    action_target: str = "",
    ra_request: Optional[CurrentSourceRequest] = None,
    wbc_attempt_reference: str = "",
    custody_attempt_id: str = "",
) -> ActionGateDecision:
    """Functional convenience for one-shot gate evaluation."""
    gate = ActionGate(
        config=config,
        ra_view_provider=ra_view_provider,
        custody_lease_provider=custody_lease_provider,
        wbc_store_provider=wbc_store_provider,
    )
    return gate.evaluate(
        action_family=action_family,
        action_target=action_target,
        ra_request=ra_request,
        wbc_attempt_reference=wbc_attempt_reference,
        custody_attempt_id=custody_attempt_id,
    )
