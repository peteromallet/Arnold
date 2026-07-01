"""Conservative human-blocker classifier for cloud repair observe mode.

Distinguishes true human blockers from stale/current-target mismatches using
needs-human sidecar data plus resolver output.  Uses a disabled-by-default
append-only escalation ledger writer skeleton so that M1 does not make
escalation authoritative.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan.cloud.current_target import resolve_current_target
from arnold_pipelines.megaplan.cloud.redact import redact_payload
from arnold_pipelines.megaplan.cloud.repair_contract import atomic_write_json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class BlockerVerdict(Enum):
    TRUE_BLOCKER = auto()        # Needs-human sidecar references the *current* plan
    STALE_MISMATCH = auto()      # Needs-human sidecar references a *previous* plan
    AMBIGUOUS_BLOCKER = auto()   # Resolver evidence is missing/incomplete — treat conservatively as blocker


@dataclass(frozen=True)
class HumanBlockerClassification:
    """Result of conservative human-blocker classification."""

    verdict: BlockerVerdict
    session: str
    current_plan: str
    needs_human_path: str = ""
    rationale: Sequence[str] = field(default_factory=tuple)
    resolver_record: dict[str, Any] | None = None
    needs_human_payload: dict[str, Any] | None = None

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
    def should_block(self) -> bool:
        """Return True if escalation should be held (true blocker or ambiguous).

        Only a confirmed stale mismatch returns False.
        """
        return self.verdict in (BlockerVerdict.TRUE_BLOCKER, BlockerVerdict.AMBIGUOUS_BLOCKER)


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
        A :class:`HumanBlockerClassification` with the conservative verdict.
    """
    rationale: list[str] = []

    # --- resolve the needs-human path and payload -----------------------------------
    resolved_path = _resolve_needs_human_path(session, repair_data_dir, needs_human_path)
    payload = _resolve_needs_human_payload(resolved_path, needs_human_payload)

    if payload is None:
        return HumanBlockerClassification(
            verdict=BlockerVerdict.AMBIGUOUS_BLOCKER,
            session=session,
            current_plan=current_plan,
            needs_human_path=str(resolved_path) if resolved_path else "",
            rationale=("needs-human sidecar missing or unreadable — conservatively treating as blocker",),
            needs_human_payload=None,
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
            needs_human_path=str(resolved_path),
            rationale=tuple(rationale),
            resolver_record=record,
            needs_human_payload=payload,
        )

    # Check if the current plan appears in the needs-human plan refs
    current_in_refs = current_plan in resolver_plan_refs if resolver_plan_refs else None

    if resolver_plan_refs and current_in_refs is True:
        rationale.append(
            f"needs-human sidecar references current plan {current_plan!r}"
        )
        return HumanBlockerClassification(
            verdict=BlockerVerdict.TRUE_BLOCKER,
            session=session,
            current_plan=current_plan,
            needs_human_path=str(resolved_path),
            rationale=tuple(rationale),
            resolver_record=record,
            needs_human_payload=payload,
        )

    if resolver_plan_refs and current_in_refs is False:
        rationale.append(
            f"needs-human sidecar references plans {resolver_plan_refs} "
            f"but current plan is {current_plan!r}"
        )
        return HumanBlockerClassification(
            verdict=BlockerVerdict.STALE_MISMATCH,
            session=session,
            current_plan=current_plan,
            needs_human_path=str(resolved_path),
            rationale=tuple(rationale),
            resolver_record=record,
            needs_human_payload=payload,
        )

    # Resolver plan_refs are empty or None — cannot confirm either way
    rationale.append(
        "resolver did not produce plan_refs from needs-human sidecar "
        f"(resolver_current_plan={resolver_current_plan!r}) — conservatively treating as blocker"
    )
    return HumanBlockerClassification(
        verdict=BlockerVerdict.AMBIGUOUS_BLOCKER,
        session=session,
        current_plan=current_plan,
        needs_human_path=str(resolved_path),
        rationale=tuple(rationale),
        resolver_record=record,
        needs_human_payload=payload,
    )


def build_needs_human_marker(
    repair_payload: Mapping[str, Any],
    *,
    repair_data_path: str | Path,
    discord_status: str,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Build a compatibility needs-human payload with additive current-pointer fields."""

    iterations = repair_payload.get("iterations")
    if not isinstance(iterations, list):
        iterations = []

    plan_name = _safe_marker_text(repair_payload.get("plan_name"))
    chain_current_plan_name = ""
    for item in reversed(iterations):
        if not isinstance(item, Mapping):
            continue
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
        "summary": " | ".join(summary_parts),
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
) -> dict[str, Any]:
    """Persist a compatibility needs-human payload atomically."""

    marker = build_needs_human_marker(
        repair_payload,
        repair_data_path=repair_data_path,
        discord_status=discord_status,
        recorded_at=recorded_at,
    )
    atomic_write_json(path, marker)
    return marker


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
    return {
        "session": classification.session,
        "kind": "blocker_classified",
        "verdict": classification.verdict.name,
        "current_plan": classification.current_plan,
        "needs_human_path": classification.needs_human_path,
        "rationale": list(classification.rationale),
        "resolver_stale_evidence": [
            e for e in (classification.resolver_record or {}).get("stale_evidence", [])
            if isinstance(e, dict) and "needs_human" in str(e.get("kind", ""))
        ],
    }


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
    "HumanBlockerClassification",
    "build_needs_human_marker",
    "classify_needs_human_blocker",
    "write_needs_human_marker_payload",
]
