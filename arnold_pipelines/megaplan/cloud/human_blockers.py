"""Conservative human-blocker classifier for cloud repair observe mode.

Distinguishes true human blockers from stale/current-target mismatches,
mechanical/liveness gates, and ambiguous evidence using needs-human sidecar
data plus resolver output.  Uses a disabled-by-default append-only escalation
ledger writer skeleton so that M1 does not make escalation authoritative.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from arnold_pipelines.megaplan.cloud.current_target import resolve_current_target
from arnold_pipelines.megaplan.cloud.redact import redact_payload
from arnold_pipelines.megaplan.cloud.repair_contract import atomic_write_json
from arnold_pipelines.megaplan.observability.events import (
    event_signature_summary,
    format_signature_line,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class BlockerVerdict(Enum):
    TRUE_BLOCKER = auto()        # Needs-human sidecar references the *current* plan AND has current-target proof
    STALE_MISMATCH = auto()      # Needs-human sidecar references a *previous* plan
    AMBIGUOUS_BLOCKER = auto()   # Resolver evidence is missing/incomplete — treat conservatively as blocker
    MECHANICAL_BLOCKER = auto()  # Mechanical/liveness gate, not a genuine human blocker — distinct non-success


@dataclass(frozen=True)
class HumanBlockerClassification:
    """Result of conservative human-blocker classification.

    When ``human_gate_view`` is populated it carries the read-only
    :class:`~arnold_pipelines.megaplan.authority.views.HumanGateView`
    serialized to a dict so that stale/superseded diagnostics are
    source-addressable without granting the view enforcement authority.
    """

    verdict: BlockerVerdict
    session: str
    current_plan: str
    needs_human_path: str = ""
    rationale: Sequence[str] = field(default_factory=tuple)
    resolver_record: dict[str, Any] | None = None
    needs_human_payload: dict[str, Any] | None = None
    human_gate_view: dict[str, Any] | None = None

    @property
    def is_true_blocker(self) -> bool:
        """True when the needs-human sidecar is definitely a real blocker."""
        return self.verdict == BlockerVerdict.TRUE_BLOCKER

    @property
    def is_stale_mismatch(self) -> bool:
        """True when the needs-human sidecar is a stale artifact from a previous target."""
        return self.verdict == BlockerVerdict.STALE_MISMATCH

    @property
    def is_ambiguous(self) -> bool:
        """True when resolver evidence is insufficient — conservatively treat as blocker."""
        return self.verdict == BlockerVerdict.AMBIGUOUS_BLOCKER

    @property
    def is_mechanical(self) -> bool:
        """True when the blocker is a mechanical/liveness gate, not a genuine human blocker."""
        return self.verdict == BlockerVerdict.MECHANICAL_BLOCKER

    @property
    def should_block(self) -> bool:
        """Return True if escalation should be held (true blocker, ambiguous, or mechanical).

        Only a confirmed stale mismatch returns False.
        """
        return self.verdict in (
            BlockerVerdict.TRUE_BLOCKER,
            BlockerVerdict.AMBIGUOUS_BLOCKER,
            BlockerVerdict.MECHANICAL_BLOCKER,
        )


HumanBlockerDispatchGate = Literal["human_required", "broken_superfixer", "clear"]


def dispatch_gate_for_human_blocker(
    classification: HumanBlockerClassification | None,
) -> HumanBlockerDispatchGate:
    """Map human-blocker evidence into the shared repair-dispatch gate."""

    if classification is None:
        return "clear"
    if classification.is_true_blocker or classification.is_ambiguous:
        return "human_required"
    if classification.is_mechanical:
        return "broken_superfixer"
    return "clear"


def _derive_human_gate_view_dict(
    payload: dict[str, Any] | None,
    *,
    current_plan: str,
    needs_human_path: str,
    resolver_record: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Derive a read-only HumanGateView dict from needs-human payload.

    Returns ``None`` when the payload carries insufficient signal to build
    a meaningful view.  The dict is always the serialized form of
    :class:`~arnold_pipelines.megaplan.authority.views.HumanGateView` — it
    never grants enforcement authority.
    """
    if payload is None:
        return None
    try:
        from arnold_pipelines.megaplan.authority.views import derive_human_gate_view

        plan_ref = (
            _safe_marker_text(payload.get("plan_name"))
            or _safe_marker_text(payload.get("current_plan_name"))
            or current_plan
        )
        signal: dict[str, Any] = {
            "gate_type": "needs_human",
            "gate_reason": _safe_marker_text(payload.get("summary")) or "unspecified",
            "source": needs_human_path or "observation://unknown",
            "plan_ref": plan_ref,
        }
        # If resolver evidence indicates staleness, mark the signal accordingly
        if resolver_record:
            stale_evidence = resolver_record.get("stale_evidence", [])
            if isinstance(stale_evidence, list):
                stale_kinds = {e.get("kind") for e in stale_evidence if isinstance(e, dict)}
                if "stale_needs_human_plan_ref" in stale_kinds:
                    signal["stale_token"] = True
                elif any("superseded" in str(e.get("kind", "")) for e in stale_evidence if isinstance(e, dict)):
                    signal["superseded"] = True
            resolver_plan_refs = resolver_record.get("needs_human", {}).get("plan_refs", [])
            if isinstance(resolver_plan_refs, list) and resolver_plan_refs:
                if current_plan not in resolver_plan_refs:
                    signal["stale_token"] = True

        view = derive_human_gate_view([signal], current_plan_revision=plan_ref)
        return view.to_dict()
    except Exception:
        return None


def classify_needs_human_blocker(
    session: str,
    *,
    current_plan: str,
    marker_dir: str | Path,
    repair_data_dir: str | Path | None = None,
    needs_human_path: str | Path | None = None,
    needs_human_payload: Mapping[str, Any] | None = None,
    resolver_record: Mapping[str, Any] | None = None,
    session_is_live: Any = None,
    pid_is_live: Any = None,
) -> HumanBlockerClassification:
    """Conservatively classify a needs-human sidecar as a true blocker or a stale mismatch.

    The classifier prefers false positives (treating ambiguous evidence as a
    blocker) over false negatives (dismissing a genuine blocker as stale).

    Only verified current-target human gates classify as TRUE_BLOCKER.
    Stale markers, mechanical/liveness gates, and ambiguous evidence remain
    distinct non-success classifications.

    Stale and superseded diagnostics are additionally routed through a
    read-only :class:`~arnold_pipelines.megaplan.authority.views.HumanGateView`
    attached as ``human_gate_view`` on the returned classification.  The view
    is a serialized dict — diagnostics only, never enforcement authority.

    Args:
        session: Repair session identifier.
        current_plan: The plan name currently considered authoritative.
        marker_dir: Directory containing session marker files.
        repair_data_dir: Optional repair-data directory.
        needs_human_path: Explicit path to the needs-human sidecar (derived
            from *repair_data_dir* if omitted).
        needs_human_payload: Pre-loaded needs-human payload; loaded from
            *needs_human_path* if omitted.
        resolver_record: Pre-computed resolver evidence record; computed
            via :func:`resolve_current_target` if omitted.
        session_is_live: Optional session-liveness probe.
        pid_is_live: Optional PID-liveness probe.

    Returns:
        A :class:`HumanBlockerClassification` with the conservative verdict
        and an optional read-only ``human_gate_view`` dict.
    """
    rationale: list[str] = []

    # --- resolve the needs-human path and payload -----------------------------------
    resolved_path = _resolve_needs_human_path(session, repair_data_dir, needs_human_path)
    payload = _resolve_needs_human_payload(resolved_path, needs_human_payload)
    needs_human_path_str = str(resolved_path) if resolved_path else ""

    if payload is None:
        return HumanBlockerClassification(
            verdict=BlockerVerdict.AMBIGUOUS_BLOCKER,
            session=session,
            current_plan=current_plan,
            needs_human_path=needs_human_path_str,
            rationale=("needs-human sidecar missing or unreadable — conservatively treating as blocker",),
            needs_human_payload=None,
            human_gate_view=None,
        )

    # --- resolve the evidence record -----------------------------------------------
    # Derive repair_data_dir from the explicit needs-human path when not provided
    # so the resolver can find the sidecar at its non-standard location.
    effective_repair_data_dir = repair_data_dir
    if effective_repair_data_dir is None and resolved_path is not None:
        effective_repair_data_dir = str(resolved_path.parent)

    if resolver_record is not None:
        record = dict(resolver_record)
    else:
        record = resolve_current_target(
            session,
            marker_dir=marker_dir,
            repair_data_dir=effective_repair_data_dir,
            session_is_live=session_is_live,
            pid_is_live=pid_is_live,
        )

    # --- derivation of the read-only HumanGateView ---------------------------------
    human_gate_view = _derive_human_gate_view_dict(
        payload,
        current_plan=current_plan,
        needs_human_path=needs_human_path_str,
        resolver_record=record,
    )

    # --- check for explicit stale_needs_human_plan_ref in stale_evidence ------------
    stale_kinds = {e.get("kind") for e in record.get("stale_evidence", []) if isinstance(e, dict)}
    has_stale_needs_human = "stale_needs_human_plan_ref" in stale_kinds

    resolver_plan_refs = record.get("needs_human", {}).get("plan_refs", [])
    resolver_current_plan = record.get("current_refs", {}).get("current_plan_name", "")

    # --- classification logic ------------------------------------------------------
    if has_stale_needs_human:
        # Resolver explicitly found a stale plan ref mismatch
        rationale.append(
            f"resolver found stale needs-human plan reference "
            f"(needs-human plans={resolver_plan_refs}, current={resolver_current_plan})"
        )
        return HumanBlockerClassification(
            verdict=BlockerVerdict.STALE_MISMATCH,
            session=session,
            current_plan=current_plan,
            needs_human_path=needs_human_path_str,
            rationale=tuple(rationale),
            resolver_record=record,
            needs_human_payload=payload,
            human_gate_view=human_gate_view,
        )

    # Check if the current plan appears in the needs-human plan refs
    current_in_refs = current_plan in resolver_plan_refs if resolver_plan_refs else None

    if resolver_plan_refs and current_in_refs is False:
        rationale.append(
            f"needs-human sidecar references plans {resolver_plan_refs} "
            f"but current plan is {current_plan!r}"
        )
        return HumanBlockerClassification(
            verdict=BlockerVerdict.STALE_MISMATCH,
            session=session,
            current_plan=current_plan,
            needs_human_path=needs_human_path_str,
            rationale=tuple(rationale),
            resolver_record=record,
            needs_human_payload=payload,
            human_gate_view=human_gate_view,
        )

    if not resolver_plan_refs:
        # Resolver plan_refs are empty or None — cannot confirm either way
        rationale.append(
            "resolver did not produce plan_refs from needs-human sidecar "
            f"(resolver_current_plan={resolver_current_plan!r}) — conservatively treating as blocker"
        )
        return HumanBlockerClassification(
            verdict=BlockerVerdict.AMBIGUOUS_BLOCKER,
            session=session,
            current_plan=current_plan,
            needs_human_path=needs_human_path_str,
            rationale=tuple(rationale),
            resolver_record=record,
            needs_human_payload=payload,
            human_gate_view=human_gate_view,
        )

    # --- current plan IS in refs → verify with current-target proof ----------------
    # Require current-target proof: the resolver must have an authoritative source
    # that is not disabled, and at least one piece of live evidence (plan/chain state
    # present, chain log, or active step heartbeat).
    authoritative_source = record.get("authoritative_source", "")
    has_authoritative_source = bool(
        authoritative_source
        and authoritative_source != "resolver_observe_disabled"
    )

    plan_state_present = record.get("plan_state", {}).get("present", False)
    chain_state_present = record.get("chain_state", {}).get("present", False)
    chain_log_present = record.get("chain_log", {}).get("present", False)
    active_step_active = record.get("active_step_heartbeat", {}).get("active", False)

    has_current_target_proof = has_authoritative_source and (
        plan_state_present or chain_state_present or chain_log_present or active_step_active
    )

    if not has_current_target_proof:
        rationale.append(
            f"needs-human references current plan {current_plan!r} but resolver lacks "
            f"current-target proof (authoritative_source={authoritative_source!r}, "
            f"plan_state_present={plan_state_present}, chain_state_present={chain_state_present})"
        )
        return HumanBlockerClassification(
            verdict=BlockerVerdict.AMBIGUOUS_BLOCKER,
            session=session,
            current_plan=current_plan,
            needs_human_path=needs_human_path_str,
            rationale=tuple(rationale),
            resolver_record=record,
            needs_human_payload=payload,
            human_gate_view=human_gate_view,
        )

    # --- current-target proof established → check for mechanical/liveness gate ------
    if _is_mechanical_blocker(payload, record):
        rationale.append(
            f"needs-human references current plan {current_plan!r} but evidence indicates "
            f"a mechanical/liveness gate rather than a genuine human blocker"
        )
        return HumanBlockerClassification(
            verdict=BlockerVerdict.MECHANICAL_BLOCKER,
            session=session,
            current_plan=current_plan,
            needs_human_path=needs_human_path_str,
            rationale=tuple(rationale),
            resolver_record=record,
            needs_human_payload=payload,
            human_gate_view=human_gate_view,
        )

    # --- genuine TRUE_BLOCKER: current-target proof + current plan match ------------
    rationale.append(
        f"needs-human sidecar references current plan {current_plan!r} "
        f"with current-target proof (source={authoritative_source})"
    )
    return HumanBlockerClassification(
        verdict=BlockerVerdict.TRUE_BLOCKER,
        session=session,
        current_plan=current_plan,
        needs_human_path=needs_human_path_str,
        rationale=tuple(rationale),
        resolver_record=record,
        needs_human_payload=payload,
        human_gate_view=human_gate_view,
    )


def build_needs_human_marker(
    repair_payload: Mapping[str, Any],
    *,
    repair_data_path: str | Path,
    discord_status: str,
    recorded_at: str | None = None,
    escalation_label: str | None = None,
) -> dict[str, Any]:
    """Build a compatibility needs-human payload with additive current-pointer fields."""

    iterations = repair_payload.get("iterations")
    if not isinstance(iterations, list):
        iterations = []

    plan_name = _safe_marker_text(repair_payload.get("plan_name"))
    chain_current_plan_name = ""
    events_path = ""
    for item in reversed(iterations):
        if not isinstance(item, Mapping):
            continue
        if not events_path:
            candidate = item.get("plan_events_path")
            if isinstance(candidate, str) and candidate:
                events_path = candidate
        chain_state = item.get("chain_state_summary")
        if isinstance(chain_state, Mapping):
            value = _safe_marker_text(chain_state.get("current_plan_name"))
            if value:
                chain_current_plan_name = value
                break

    summary_parts: list[str] = []
    for item in iterations:
        if not isinstance(item, Mapping):
            continue
        summary_parts.append(
            f"i{item.get('i')} dev={item.get('dev_model', '')} sha={item.get('dev_fix_sha', '') or 'none'} "
            f"mechanical={item.get('mechanical_launch', '') or 'n/a'} "
            f"kimi={item.get('kimi_launch', '') or 'n/a'} why={item.get('why', '') or item.get('kimi_diagnosis', '') or 'n/a'}"
        )

    # Inline the real error signatures from the plan's events.ndjson so the
    # repair operator and humans see the primary evidence (e.g.
    # "authority_divergence/head_mismatch x293") instead of only prose narratives.
    if not events_path:
        failure_context = repair_payload.get("current_failure_context")
        if isinstance(failure_context, Mapping):
            candidate = failure_context.get("plan_events_path")
            if isinstance(candidate, str) and candidate:
                events_path = candidate
    signatures = event_signature_summary(events_path=events_path) if events_path else []
    signature_line = format_signature_line(signatures)

    summary = " | ".join(summary_parts)
    prefixes: list[str] = []
    if escalation_label:
        prefixes.append(f"[{escalation_label}]")
    if signature_line:
        prefixes.append(signature_line)
    if prefixes:
        summary = " ".join(prefixes) + " | " + summary

    current_pointer = _build_current_pointer(
        repair_payload,
        repair_data_path=repair_data_path,
        plan_name=plan_name,
        chain_current_plan_name=chain_current_plan_name,
    )
    marker = {
        "session": repair_payload.get("session"),
        "workspace": repair_payload.get("workspace"),
        "spec": repair_payload.get("spec"),
        "plan_name": plan_name,
        "chain_current_plan_name": chain_current_plan_name,
        "summary": summary,
        "event_signatures": list(signatures),
        "event_signatures_path": events_path,
        "escalation_label": escalation_label or "",
        "repair_data_path": str(repair_data_path),
        "discord_status": discord_status,
        "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),
        "current_plan_name": current_pointer.get("current_plan_name", ""),
        "target_id": current_pointer.get("target_id", ""),
        "authoritative_source": current_pointer.get("authoritative_source", ""),
        "current": current_pointer,
    }
    return redact_payload(marker)


def write_needs_human_marker_payload(
    path: str | Path,
    repair_payload: Mapping[str, Any],
    *,
    repair_data_path: str | Path,
    discord_status: str,
    recorded_at: str | None = None,
    escalation_label: str | None = None,
) -> dict[str, Any]:
    """Persist a compatibility needs-human payload atomically."""

    marker = build_needs_human_marker(
        repair_payload,
        repair_data_path=repair_data_path,
        discord_status=discord_status,
        recorded_at=recorded_at,
        escalation_label=escalation_label,
    )
    atomic_write_json(path, marker)
    return marker


def supersede_needs_human_marker(
    path: str | Path,
    repair_payload: Mapping[str, Any],
    *,
    repair_data_path: str | Path,
    discord_status: str,
    previous_escalation_id: str,
    superseded_by: str,
    ledger_writer: EscalationLedgerWriter | None = None,
    reason: str = "",
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Rewrite the mutable needs-human pointer and record the superseded escalation."""

    marker_path = Path(path)
    previous_marker = _resolve_needs_human_payload(marker_path, None) or {}
    marker = write_needs_human_marker_payload(
        marker_path,
        repair_payload,
        repair_data_path=repair_data_path,
        discord_status=discord_status,
        recorded_at=recorded_at,
    )
    session = _safe_marker_text(marker.get("session")) or _safe_marker_text(repair_payload.get("session"))
    if ledger_writer is not None and previous_escalation_id:
        previous_target_id = _safe_marker_text(previous_marker.get("target_id"))
        new_target_id = _safe_marker_text(marker.get("target_id"))
        ledger_writer.write_superseded(
            session,
            escalation_id=previous_escalation_id,
            superseded_by=superseded_by,
            reason=reason,
            extra={
                "previous_target_id": previous_target_id,
                "new_target_id": new_target_id,
            },
        )
    return marker


def clear_needs_human_marker(path: str | Path) -> bool:
    """Clear the mutable needs-human pointer without touching ledger history."""

    target = Path(path)
    try:
        target.unlink()
    except FileNotFoundError:
        return False
    return True


def compute_escalation_id(
    session: str,
    *,
    target_id: str = "",
    current_plan: str = "",
    current_plan_name: str = "",
    needs_human_path: str = "",
) -> str:
    """Return a deterministic escalation id for the current target pointer."""

    payload = {
        "session": _safe_marker_text(session),
        "target_id": _safe_marker_text(target_id),
        "current_plan": _safe_marker_text(current_plan),
        "current_plan_name": _safe_marker_text(current_plan_name),
        "needs_human_path": _safe_marker_text(needs_human_path),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return f"esc-{digest}"


# ---------------------------------------------------------------------------
# Escalation ledger writer skeleton (disabled by default)
# ---------------------------------------------------------------------------


@dataclass
class EscalationLedgerWriter:
    """Append-only escalation ledger writer — **disabled by default**.

    In M1 this ledger is strictly observe-only.  Writes are no-ops until
    :meth:`enable` is called explicitly (e.g. from tests or an opt-in flag).
    When enabled, records are written as append-only JSONL sidecar files using
    the atomic helpers from :mod:`repair_contract`.

    The ledger captures classification decisions so that later layers can
    audit discrepancy patterns before making escalation authoritative.

    The default ``_enabled`` state respects the centralized
    ``ARNOLD_ESCALATION_LEDGER`` feature flag, so callers that set the env
    var to ``"1"`` will get active ledger writers without an explicit
    :meth:`enable` call.
    """

    sidecar_dir: str | Path | None = None
    _enabled: bool | None = None  # None → resolve from feature flag

    def __post_init__(self) -> None:
        if self._enabled is None:
            from arnold_pipelines.megaplan.cloud.feature_flags import (
                escalation_ledger_enabled,
            )

            self._enabled = escalation_ledger_enabled()

    @property
    def enabled(self) -> bool:
        """Return True when the ledger writer is actively writing records."""
        return self._enabled

    def enable(self, sidecar_dir: str | Path) -> None:
        """Enable the ledger writer and set the sidecar output directory.

        Args:
            sidecar_dir: Root directory for sidecar files (passed through
                to :func:`append_jsonl_record`).
        """
        self.sidecar_dir = str(sidecar_dir)
        self._enabled = True

    def disable(self) -> None:
        """Disable the ledger writer — all subsequent writes become no-ops."""
        self._enabled = False

    def write_classification(self, classification: HumanBlockerClassification) -> Path | None:
        """Append a classification record to the escalation ledger.

        Args:
            classification: The classification result to record.

        Returns:
            The path to the updated JSONL file when enabled, or *None* when
            disabled.
        """
        if not self._enabled or self.sidecar_dir is None:
            logger.debug(
                "escalation ledger write suppressed (disabled or no sidecar_dir): %s",
                classification.verdict.name,
            )
            return None

        from arnold_pipelines.megaplan.cloud.repair_contract import append_incident_record

        record = _classification_to_record(classification)
        return append_incident_record(self.sidecar_dir, record)

    def write_opened(
        self,
        session: str,
        *,
        escalation_id: str,
        current_plan: str = "",
        target_id: str = "",
        extra: Mapping[str, Any] | None = None,
    ) -> Path | None:
        return self._write_lifecycle(
            session,
            event="opened",
            escalation_id=escalation_id,
            extra={
                "current_plan": current_plan,
                "target_id": target_id,
                **(dict(extra) if extra else {}),
            },
        )

    def write_delivered(
        self,
        session: str,
        *,
        escalation_id: str,
        channel_id: str = "",
        message_ids: Sequence[str] | None = None,
        message_count: int | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> Path | None:
        payload: dict[str, Any] = {
            "channel_id": channel_id,
            "message_ids": list(message_ids or ()),
        }
        if message_count is None:
            payload["message_count"] = len(payload["message_ids"])
        else:
            payload["message_count"] = message_count
        if extra:
            payload.update(extra)
        return self._write_lifecycle(
            session,
            event="delivered",
            escalation_id=escalation_id,
            extra=payload,
        )

    def write_unavailable(
        self,
        session: str,
        *,
        escalation_id: str,
        reason: str,
        extra: Mapping[str, Any] | None = None,
    ) -> Path | None:
        return self._write_lifecycle(
            session,
            event="unavailable",
            escalation_id=escalation_id,
            extra={"reason": reason, **(dict(extra) if extra else {})},
        )

    def write_answered(
        self,
        session: str,
        *,
        escalation_id: str,
        responder_user_id: str = "",
        channel_id: str = "",
        message_id: str = "",
        extra: Mapping[str, Any] | None = None,
    ) -> Path | None:
        return self._write_lifecycle(
            session,
            event="answered",
            escalation_id=escalation_id,
            extra={
                "responder_user_id": responder_user_id,
                "channel_id": channel_id,
                "message_id": message_id,
                **(dict(extra) if extra else {}),
            },
        )

    def write_superseded(
        self,
        session: str,
        *,
        escalation_id: str,
        superseded_by: str,
        reason: str = "",
        extra: Mapping[str, Any] | None = None,
    ) -> Path | None:
        return self._write_lifecycle(
            session,
            event="superseded",
            escalation_id=escalation_id,
            extra={
                "superseded_by": superseded_by,
                "reason": reason,
                **(dict(extra) if extra else {}),
            },
        )

    def write_timed_out(
        self,
        session: str,
        *,
        escalation_id: str,
        deadline_at: str = "",
        extra: Mapping[str, Any] | None = None,
    ) -> Path | None:
        return self._write_lifecycle(
            session,
            event="timed_out",
            escalation_id=escalation_id,
            extra={"deadline_at": deadline_at, **(dict(extra) if extra else {})},
        )

    def write_resume_attempted(
        self,
        session: str,
        *,
        escalation_id: str,
        action: str = "",
        resume_status: str = "",
        extra: Mapping[str, Any] | None = None,
    ) -> Path | None:
        return self._write_lifecycle(
            session,
            event="resume_attempted",
            escalation_id=escalation_id,
            extra={
                "action": action,
                "resume_status": resume_status,
                **(dict(extra) if extra else {}),
            },
        )

    def write_incident(
        self,
        session: str,
        *,
        kind: str,
        summary: str,
        extra: Mapping[str, Any] | None = None,
    ) -> Path | None:
        """Append a free-form incident record.

        Args:
            session: The repair session.
            kind: Short incident kind (e.g. ``"blocker_classified"``).
            summary: Human-readable summary.
            extra: Optional additional fields to include in the record.

        Returns:
            Path to the JSONL file, or *None* when disabled.
        """
        if not self._enabled or self.sidecar_dir is None:
            return None

        from arnold_pipelines.megaplan.cloud.repair_contract import append_incident_record

        record: dict[str, Any] = {
            "session": session,
            "kind": kind,
            "summary": summary,
        }
        if extra:
            record.update(extra)
        return append_incident_record(self.sidecar_dir, record)

    def _write_lifecycle(
        self,
        session: str,
        *,
        event: str,
        escalation_id: str,
        extra: Mapping[str, Any] | None = None,
    ) -> Path | None:
        if not self._enabled or self.sidecar_dir is None:
            return None

        from arnold_pipelines.megaplan.cloud.repair_contract import append_escalation_record

        record: dict[str, Any] = {
            "session": session,
            "event": event,
            "escalation_id": escalation_id,
        }
        if extra:
            record.update(extra)
        return append_escalation_record(self.sidecar_dir, _redact_small_record(record))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_needs_human_path(
    session: str,
    repair_data_dir: str | Path | None,
    explicit_path: str | Path | None,
) -> Path | None:
    if explicit_path is not None:
        return Path(explicit_path)
    if repair_data_dir is not None:
        return Path(repair_data_dir) / f"{session}.needs-human.json"
    return None


def _resolve_needs_human_payload(
    path: Path | None,
    preloaded: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if preloaded is not None:
        return dict(preloaded)
    if path is None:
        return None
    if not path.exists():
        return None
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _classification_to_record(classification: HumanBlockerClassification) -> dict[str, Any]:
    """Build a durable ledger record from a classification, including Discord metadata."""
    needs_human = classification.needs_human_payload or {}
    discord_status = _safe_marker_text(needs_human.get("discord_status"))

    # Extract resolver evidence summary for audit trail
    resolver = classification.resolver_record or {}
    authoritative_source = _safe_marker_text(resolver.get("authoritative_source", ""))
    plan_state_mtime = resolver.get("plan_state", {}).get("mtime", 0.0)
    chain_state_mtime = resolver.get("chain_state", {}).get("mtime", 0.0)

    # Extract HumanGateView diagnostics for audit trail
    human_gate_diagnostics: list[dict[str, str]] = []
    if classification.human_gate_view:
        hgv = classification.human_gate_view
        if isinstance(hgv, dict):
            diags = hgv.get("diagnostics", [])
            if isinstance(diags, list):
                human_gate_diagnostics = [
                    {"code": d.get("code", ""), "reason": d.get("reason", ""), "source": d.get("source", "")}
                    for d in diags
                    if isinstance(d, dict)
                ]

    return {
        "session": classification.session,
        "kind": "blocker_classified",
        "verdict": classification.verdict.name,
        "current_plan": classification.current_plan,
        "needs_human_path": classification.needs_human_path,
        "rationale": list(classification.rationale),
        "resolver_stale_evidence": [
            e for e in resolver.get("stale_evidence", [])
            if isinstance(e, dict) and "needs_human" in str(e.get("kind", ""))
        ],
        "discord_status": discord_status,
        "authoritative_source": authoritative_source,
        "plan_state_mtime": plan_state_mtime,
        "chain_state_mtime": chain_state_mtime,
        "human_gate_diagnostics": human_gate_diagnostics,
    }


def _redact_small_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Redact secrets while keeping lifecycle payloads compact and predictable."""

    redacted = redact_payload(record)
    if not isinstance(redacted, dict):
        return dict(record)
    return {
        key: value
        for key, value in redacted.items()
        if value not in ("", None, [], {})
    }


def _is_mechanical_blocker(
    needs_human_payload: dict[str, Any],
    resolver_record: dict[str, Any],
) -> bool:
    """Detect whether a needs-human sidecar represents a mechanical/liveness gate.

    A mechanical blocker is one where the evidence indicates the escalation was
    triggered by a mechanical failure (e.g. repair tool crash, liveness timeout,
    rate-limit) rather than a genuine human gate (e.g. awaiting review, blocked
    by follow-up, needs approval).

    Heuristics (any single signal is sufficient):
    - Summary text contains mechanical/liveness keywords without genuine human-gate keywords.
    - The needs-human payload lacks iteration-level `why`/`kimi_diagnosis` human-gate indicators.
    - The resolver shows active_step_heartbeat with a running phase (liveness gate).
    """
    summary = _safe_marker_text(needs_human_payload.get("summary", "")).lower()

    # Genuine human-gate keywords — if present, it's NOT a mechanical blocker
    human_gate_keywords = (
        "awaiting human", "needs review", "blocked by follow-up",
        "needs approval", "human intervention", "manual review",
        "true blocker", "escalation",
    )
    has_human_gate_indicator = any(kw in summary for kw in human_gate_keywords)

    if has_human_gate_indicator:
        return False

    # Mechanical/liveness keywords
    mechanical_keywords = (
        "mechanical", "liveness", "timeout", "rate-limit",
        "rate limit", "crash", "tool failure", "launch failure",
        "mechanical_launch", "kimi_launch",
    )
    has_mechanical_indicator = any(kw in summary for kw in mechanical_keywords)

    if has_mechanical_indicator:
        return True

    # Check if the needs-human payload was created from a purely mechanical iteration
    # (no human-gate diagnosis in the `why` or `kimi_diagnosis` fields)
    iterations = needs_human_payload.get("iterations")
    if isinstance(iterations, list) and iterations:
        all_mechanical = True
        for item in iterations:
            if not isinstance(item, dict):
                continue
            why = _safe_marker_text(item.get("why", "")).lower()
            kimi_diag = _safe_marker_text(item.get("kimi_diagnosis", "")).lower()
            combined = f"{why} {kimi_diag}"
            if any(kw in combined for kw in human_gate_keywords):
                all_mechanical = False
                break
        if all_mechanical:
            return True

    # Check resolver active_step_heartbeat for liveness-only pattern
    heartbeat = resolver_record.get("active_step_heartbeat", {})
    if heartbeat.get("active") and heartbeat.get("phase"):
        # An active step with a running phase but no human-gate needs-human summary
        # suggests a liveness gate rather than a genuine human blocker
        if not has_human_gate_indicator:
            return True

    return False


def _build_current_pointer(
    repair_payload: Mapping[str, Any],
    *,
    repair_data_path: str | Path,
    plan_name: str,
    chain_current_plan_name: str,
) -> dict[str, Any]:
    resolver_output = repair_payload.get("target")
    if not isinstance(resolver_output, Mapping):
        resolver_output = {}
    current_failure_context = repair_payload.get("current_failure_context")
    if isinstance(current_failure_context, Mapping):
        context_resolver = current_failure_context.get("resolver_output")
        if isinstance(context_resolver, Mapping):
            resolver_output = context_resolver

    current_refs = resolver_output.get("current_refs")
    if not isinstance(current_refs, Mapping):
        current_refs = {}

    current_plan_name = _safe_marker_text(current_refs.get("current_plan_name")) or plan_name
    current_chain_plan = (
        _safe_marker_text(current_refs.get("chain_current_plan_name")) or chain_current_plan_name
    )

    return {
        "session": repair_payload.get("session"),
        "workspace": repair_payload.get("workspace"),
        "spec": repair_payload.get("spec"),
        "repair_data_path": str(repair_data_path),
        "target_id": _safe_marker_text(resolver_output.get("target_id")),
        "authoritative_source": _safe_marker_text(resolver_output.get("authoritative_source")),
        "current_plan_name": current_plan_name,
        "chain_current_plan_name": current_chain_plan,
        "plan_name": plan_name,
        "run_kind": repair_payload.get("run_kind"),
    }


def _safe_marker_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


__all__ = [
    "BlockerVerdict",
    "EscalationLedgerWriter",
    "HumanBlockerDispatchGate",
    "HumanBlockerClassification",
    "build_needs_human_marker",
    "classify_needs_human_blocker",
    "clear_needs_human_marker",
    "compute_escalation_id",
    "dispatch_gate_for_human_blocker",
    "supersede_needs_human_marker",
    "write_needs_human_marker_payload",
]
