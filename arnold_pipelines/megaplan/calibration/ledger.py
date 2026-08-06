"""M5-cal calibration ledger — pure dataclasses and value objects.

The calibration ledger records :class:`CapabilityClaim` events alongside the
existing ``events.ndjson`` journal.  Claims reference adjudicated outcomes via
:class:`EvaluandRef`, which joins against :func:`read_evaluand_events` using the
deterministic 4-tuple attribution key ``(piece_version, judge_version,
rubric_version, input_set_hash)``.

Bare numeric outcomes are **rejected at construction time** — the schema
invariant is enforced by :meth:`CapabilityClaim.__post_init__`.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Optional, Sequence


# ---------------------------------------------------------------------------
# Canonical JSON helper
# ---------------------------------------------------------------------------


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# ModelIdentity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelIdentity:
    """Stable, content-addressed identity for a model.

    The identity is a SHA-256 digest of ``f"{model_name}\\x00{reported_version}"``,
    matching :func:`megaplan.observability.events.compute_model_identity`.  This
    is deterministic across processes and runs — required for calibration
    ledger joins.
    """

    model_name: str
    reported_version: Optional[str] = None

    @property
    def identity(self) -> str:
        """Return the deterministic SHA-256 identity digest."""
        name = self.model_name or ""
        version = self.reported_version or ""
        return hashlib.sha256(
            f"{name}\x00{version}".encode("utf-8")
        ).hexdigest()

    def to_json(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "reported_version": self.reported_version,
            "identity": self.identity,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "ModelIdentity":
        return cls(
            model_name=str(value["model_name"]),
            reported_version=(
                str(value["reported_version"])
                if value.get("reported_version") is not None
                else None
            ),
        )

    def __str__(self) -> str:
        return self.identity


# ---------------------------------------------------------------------------
# EvaluandRef — content-addressed reference to an EvaluandRecord
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluandRef:
    """Stable reference to a versioned EvaluandRecord.

    Carries the exact 4-tuple attribution key ``(piece_version, judge_version,
    rubric_version, input_set_hash)`` used to join against
    :func:`~megaplan.observability.evaluand.read_evaluand_events`.

    Modeled after :class:`~megaplan.observability.evaluand.ModelIORef`.
    """

    piece_version: str
    judge_version: str
    rubric_version: str
    input_set_hash: str

    @property
    def key(self) -> tuple[str, str, str, str]:
        """Return the deterministic 4-tuple attribution join key."""
        return (
            self.piece_version,
            self.judge_version,
            self.rubric_version,
            self.input_set_hash,
        )

    @property
    def content_hash(self) -> str:
        """Stable content hash of the ref itself (for idempotency)."""
        return hashlib.sha256(
            _canonical_json(self.to_json()).encode("utf-8")
        ).hexdigest()

    def to_json(self) -> dict[str, Any]:
        return {
            "piece_version": self.piece_version,
            "judge_version": self.judge_version,
            "rubric_version": self.rubric_version,
            "input_set_hash": self.input_set_hash,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "EvaluandRef":
        return cls(
            piece_version=str(value["piece_version"]),
            judge_version=str(value["judge_version"]),
            rubric_version=str(value["rubric_version"]),
            input_set_hash=str(value["input_set_hash"]),
        )


# ---------------------------------------------------------------------------
# CapabilityClaim
# ---------------------------------------------------------------------------


def _coerce_model_identity(
    value: ModelIdentity | Mapping[str, Any] | str,
    *,
    field_name: str,
) -> ModelIdentity:
    if isinstance(value, ModelIdentity):
        return value
    if isinstance(value, Mapping):
        return ModelIdentity.from_json(value)
    if isinstance(value, str):
        return ModelIdentity(model_name=value)
    raise TypeError(
        f"{field_name} must be a ModelIdentity, mapping, or string, "
        f"got {type(value).__name__}"
    )


def _json_value_with_legacy_aliases(
    value: Mapping[str, Any],
    canonical_key: str,
    *legacy_keys: str,
) -> Any:
    if canonical_key in value:
        return value[canonical_key]
    for legacy_key in legacy_keys:
        if legacy_key in value:
            return value[legacy_key]
    return None


@dataclass(frozen=True, init=False)
class CapabilityClaim:
    """One capability claim recorded in the calibration ledger.

    The ``outcome`` field is **always** an :class:`EvaluandRef` — bare numeric
    outcomes are rejected at construction time by :meth:`__post_init__`.

    Claims are recorded into the shared ``events.ndjson`` journal with
    ``EventKind.CAPABILITY_CLAIM`` after adjudicated dispatch (when an
    EvaluandRef is available).  The ``content_hash`` property provides a
    stable idempotency key.

    The ``content_hash`` is computed from the canonical JSON of the claim
    payload **excluding the ``content_hash`` field itself** — the ``to_json``
    payload does not carry ``content_hash``, so the hash is stable for
    semantically identical claims.
    """

    outcome: EvaluandRef
    task_signature: str
    routed_model: ModelIdentity
    recorded_at: float
    verifier_tier: Optional[str] = None
    verifier_identity: Optional[str] = None
    counterfactual_tag: Optional[str] = None
    low_confidence_signal: bool = False
    taint_class: Optional[str] = None
    predicted_tier: Optional[int] = None
    route_phase: Optional[str] = None
    routed_tier_spec: Optional[str] = None
    cost_usd: Optional[float] = None

    def __init__(
        self,
        outcome: EvaluandRef,
        task_signature: str,
        routed_model: ModelIdentity | Mapping[str, Any] | str | None = None,
        recorded_at: float | None = None,
        verifier_tier: Optional[str] = None,
        verifier_identity: Optional[str] = None,
        counterfactual_tag: Optional[str] = None,
        low_confidence_signal: bool = False,
        taint_class: Optional[str] = None,
        predicted_tier: Optional[int] = None,
        route_phase: Optional[str] = None,
        routed_tier_spec: Optional[str] = None,
        cost_usd: Optional[float] = None,
        *,
        model_identity: Optional[str] = None,
        timestamp: float | None = None,
        exploration_tag: Optional[str] = None,
        routed_model_identity: Optional[str] = None,
    ) -> None:
        if routed_model is None:
            legacy_routed_model = routed_model_identity or model_identity
            if legacy_routed_model is None:
                raise TypeError(
                    "CapabilityClaim requires routed_model= or a legacy "
                    "model_identity=/routed_model_identity= alias"
                )
            routed_model_value = ModelIdentity(model_name=legacy_routed_model)
        else:
            routed_model_value = _coerce_model_identity(
                routed_model,
                field_name="CapabilityClaim.routed_model",
            )
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "task_signature", task_signature)
        object.__setattr__(self, "routed_model", routed_model_value)
        object.__setattr__(
            self,
            "recorded_at",
            float(recorded_at if recorded_at is not None else (timestamp if timestamp is not None else time.time())),
        )
        object.__setattr__(self, "verifier_tier", verifier_tier)
        object.__setattr__(self, "verifier_identity", verifier_identity)
        object.__setattr__(
            self,
            "counterfactual_tag",
            counterfactual_tag if counterfactual_tag is not None else exploration_tag,
        )
        object.__setattr__(
            self, "low_confidence_signal", bool(low_confidence_signal)
        )
        object.__setattr__(self, "taint_class", taint_class)
        object.__setattr__(self, "predicted_tier", predicted_tier)
        object.__setattr__(self, "route_phase", route_phase)
        object.__setattr__(self, "routed_tier_spec", routed_tier_spec)
        object.__setattr__(self, "cost_usd", cost_usd)
        validate_capability_claim(self)

    @property
    def model_identity(self) -> str:
        return self.routed_model.model_name

    @property
    def timestamp(self) -> float:
        return self.recorded_at

    @property
    def exploration_tag(self) -> Optional[str]:
        return self.counterfactual_tag

    @property
    def routed_model_identity(self) -> str:
        return self.routed_model.model_name

    def __post_init__(self) -> None:
        validate_capability_claim(self)

    @property
    def content_hash(self) -> str:
        """Stable SHA-256 of the canonical claim payload (excludes ``content_hash``).

        The hash is computed over the sorted-key compact JSON of ``to_json()``
        which explicitly does **not** include a ``content_hash`` key — two
        semantically identical claims always produce the same digest.
        """
        return hashlib.sha256(
            _canonical_json(self.to_json()).encode("utf-8")
        ).hexdigest()

    def to_json(self) -> dict[str, Any]:
        """Return the claim as a JSON-serialisable dict (no ``content_hash`` key)."""
        return {
            "outcome": self.outcome.to_json(),
            "task_signature": self.task_signature,
            "routed_model": self.routed_model.to_json(),
            "recorded_at": self.recorded_at,
            "verifier_tier": self.verifier_tier,
            "verifier_identity": self.verifier_identity,
            "counterfactual_tag": self.counterfactual_tag,
            "low_confidence_signal": self.low_confidence_signal,
            "taint_class": self.taint_class,
            "predicted_tier": self.predicted_tier,
            "route_phase": self.route_phase,
            "routed_tier_spec": self.routed_tier_spec,
            "cost_usd": self.cost_usd,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "CapabilityClaim":
        outcome_raw = value["outcome"]
        if isinstance(outcome_raw, Mapping):
            outcome = EvaluandRef.from_json(outcome_raw)
        else:
            raise TypeError(
                "CapabilityClaim.outcome in json must be a dict, "
                f"got {type(outcome_raw).__name__}"
            )
        routed_model_raw = _json_value_with_legacy_aliases(
            value,
            "routed_model",
            "routed_model_identity",
            "model_identity",
        )
        if routed_model_raw is None:
            raise KeyError("routed_model")
        return cls(
            outcome=outcome,
            task_signature=str(value["task_signature"]),
            routed_model=_coerce_model_identity(
                routed_model_raw,
                field_name="CapabilityClaim.routed_model",
            ),
            recorded_at=float(
                _json_value_with_legacy_aliases(
                    value,
                    "recorded_at",
                    "timestamp",
                )
                if (
                    "recorded_at" in value
                    or "timestamp" in value
                )
                else time.time()
            ),
            verifier_tier=(
                str(value["verifier_tier"])
                if value.get("verifier_tier") is not None
                else None
            ),
            verifier_identity=(
                str(value["verifier_identity"])
                if value.get("verifier_identity") is not None
                else None
            ),
            counterfactual_tag=(
                str(
                    _json_value_with_legacy_aliases(
                        value,
                        "counterfactual_tag",
                        "exploration_tag",
                    )
                )
                if (
                    _json_value_with_legacy_aliases(
                        value,
                        "counterfactual_tag",
                        "exploration_tag",
                    )
                    is not None
                )
                else None
            ),
            low_confidence_signal=bool(value.get("low_confidence_signal", False)),
            taint_class=(
                str(value["taint_class"])
                if value.get("taint_class") is not None
                else None
            ),
            predicted_tier=(
                int(value["predicted_tier"])
                if value.get("predicted_tier") is not None
                else None
            ),
            route_phase=(
                str(value["route_phase"])
                if value.get("route_phase") is not None
                else None
            ),
            routed_tier_spec=(
                str(value["routed_tier_spec"])
                if value.get("routed_tier_spec") is not None
                else None
            ),
            cost_usd=(
                float(value["cost_usd"])
                if value.get("cost_usd") is not None
                else None
            ),
        )


def validate_capability_claim(claim: CapabilityClaim) -> None:
    """Validate the non-negotiable CapabilityClaim schema invariants."""
    outcome = claim.outcome
    if isinstance(outcome, (int, float)):
        raise TypeError(
            "CapabilityClaim.outcome must be an EvaluandRef, "
            f"not a bare {type(outcome).__name__}"
        )
    if not isinstance(outcome, EvaluandRef):
        raise TypeError(
            f"CapabilityClaim.outcome must be an EvaluandRef, "
            f"got {type(outcome).__name__}"
        )


# ---------------------------------------------------------------------------
# Query policy value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QueryPolicy:
    """Configuration for a calibration routing query.

    Controls decay behaviour, exploration budget, and taint filtering for the
    ``route()`` pure function.
    """

    half_life_days: float = 30.0
    exploration_budget: float = 0.0
    default_tier: int = 4
    exclude_tainted: bool = True
    verifier_tier_min: Optional[int] = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "QueryPolicy":
        return cls(
            half_life_days=float(value.get("half_life_days", 30.0)),
            exploration_budget=float(value.get("exploration_budget", 0.0)),
            default_tier=int(value.get("default_tier", 4)),
            exclude_tainted=bool(value.get("exclude_tainted", True)),
            verifier_tier_min=(
                int(value["verifier_tier_min"])
                if value.get("verifier_tier_min") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class RouteSuggestion:
    """Result of a calibration routing query.

    A ``None`` tier_spec means no suggestion — the caller should fall back to
    the current TOML-derived tier routing.
    """

    tier_spec: Optional[str] = None
    model_identity: Optional[str] = None
    confidence: float = 0.0
    source: str = "calibration_ledger"
    exploration: bool = False
    counterfactual_tag: Optional[str] = None
    reason: Optional[str] = None
    projected_tier: Optional[int] = None

    @property
    def has_suggestion(self) -> bool:
        return self.tier_spec is not None

    @property
    def low_confidence(self) -> bool:
        """True when confidence is below the actionable threshold."""
        return self.confidence < 0.5

    def to_json(self) -> dict[str, Any]:
        return {
            "tier_spec": self.tier_spec,
            "model_identity": self.model_identity,
            "confidence": self.confidence,
            "source": self.source,
            "exploration": self.exploration,
            "counterfactual_tag": self.counterfactual_tag,
            "reason": self.reason,
            "projected_tier": self.projected_tier,
        }


# ---------------------------------------------------------------------------
# Write path — record a CapabilityClaim through the canonical event ledger
# ---------------------------------------------------------------------------


def write_capability_claim(
    claim: CapabilityClaim,
    *,
    plan_dir: Path | str | None = None,
    event_sink: Any | None = None,
    phase: Optional[str] = None,
    scope: Optional[str] = None,
) -> dict:
    """Record a capability claim into the shared ``events.ndjson`` journal.

    Follows the same ``plan_dir`` / ``event_sink`` dual-target pattern as
    :func:`~megaplan.observability.evaluand.write_evaluand_event`.

    Args:
        claim: The :class:`CapabilityClaim` to record.
        plan_dir: Plan directory; an ``NdjsonBackend`` is created when set.
        event_sink: An :class:`EventSink` — superseeds ``plan_dir``.
        phase: Optional phase label forwarded to the event sink.
        scope: Optional scope label forwarded to the event sink.

    Returns:
        The full event dict returned by the backend's ``emit()``.

    Raises:
        ValueError: if neither ``plan_dir`` nor ``event_sink`` is provided.
    """
    # Idempotency key derived from the claim's stable content hash.
    idempotency_key: str = claim.content_hash

    # Build the payload — to_json() deliberately excludes content_hash
    # so the canonical serialisation is stable across identical claims.
    payload = claim.to_json()

    if event_sink is None and plan_dir is None:
        raise ValueError(
            "write_capability_claim requires either plan_dir= or event_sink="
        )

    if event_sink is None:
        from arnold_pipelines.megaplan.observability.event_sink import NdjsonBackend

        event_sink = NdjsonBackend(Path(plan_dir))  # type: ignore[arg-type]

    # Lazy import to stay cycle-free with megaplan.observability.events.
    from arnold_pipelines.megaplan.observability.events import EventKind

    return event_sink.emit(
        EventKind.CAPABILITY_CLAIM,
        payload=payload,
        scope=scope,
        phase=phase,
        idempotency_key=idempotency_key,
    )


# ---------------------------------------------------------------------------
# Read path — read claims from events.ndjson
# ---------------------------------------------------------------------------


def iter_capability_claim_payloads(
    plan_dir: Path | str,
    *,
    since_seq: Optional[int] = None,
) -> Iterator[dict]:
    """Yield raw capability-claim payload dicts from ``plan_dir/events.ndjson``.

    Uses :func:`~megaplan.observability.events.read_events` filtered to
    ``EventKind.CAPABILITY_CLAIM``.  Each yielded dict is the ``payload``
    sub-object from the event envelope — the caller is responsible for
    reconstructing :class:`CapabilityClaim` via ``from_json()`` if needed.

    Args:
        plan_dir: Path to the plan directory.
        since_seq: If set, only yield events with ``seq > since_seq``.

    Yields:
        Payload dicts in file order (monotonic seq).
    """
    from arnold_pipelines.megaplan.observability.events import EventKind, read_events

    for event in read_events(
        Path(plan_dir),
        kinds=[EventKind.CAPABILITY_CLAIM],
        since_seq=since_seq,
    ):
        payload = event.get("payload")
        if isinstance(payload, dict):
            yield payload


def read_capability_claims(
    plan_dir: Path | str,
    *,
    since_seq: Optional[int] = None,
    since_timestamp: Optional[float] = None,
    routed_model: ModelIdentity | Mapping[str, Any] | None = None,
    model_identity: Optional[str] = None,
    taint_class: Optional[str] = None,
    task_signature: Optional[str] = None,
) -> tuple[CapabilityClaim, ...]:
    """Read and filter :class:`CapabilityClaim` instances from the journal.

    All filters are Python-side and applied after deserialization.  Filters
    that are ``None`` are skipped.

    Args:
        plan_dir: Path to the plan directory.
        since_seq: Only consider events with ``seq > since_seq``.
        since_timestamp: Only return claims recorded at or after this epoch
            time.
        routed_model: Only return claims whose canonical ``routed_model``
            matches. Canonical filter takes precedence over the legacy
            ``model_identity`` alias.
        model_identity: Legacy alias that filters by routed model name.
        taint_class: Only return claims whose ``taint_class`` matches.
        task_signature: Only return claims whose ``task_signature`` matches.

    Returns:
        A tuple of :class:`CapabilityClaim` instances matching all filters,
        in journal order (earliest first).
    """
    claims: list[CapabilityClaim] = []
    routed_model_filter = (
        _coerce_model_identity(
            routed_model,
            field_name="read_capability_claims.routed_model",
        )
        if routed_model is not None
        else None
    )

    for payload in iter_capability_claim_payloads(
        plan_dir, since_seq=since_seq
    ):
        try:
            claim = CapabilityClaim.from_json(payload)
        except (TypeError, KeyError, ValueError):
            # Corrupt or legacy payload — skip gracefully.
            continue

        if since_timestamp is not None and claim.recorded_at < since_timestamp:
            continue
        if (
            routed_model_filter is not None
            and claim.routed_model != routed_model_filter
        ):
            continue
        if (
            routed_model_filter is None
            and model_identity is not None
            and claim.routed_model.model_name != model_identity
        ):
            continue
        if taint_class is not None and claim.taint_class != taint_class:
            continue
        if task_signature is not None and claim.task_signature != task_signature:
            continue

        claims.append(claim)

    return tuple(claims)


# ---------------------------------------------------------------------------
# Evaluand resolution
# ---------------------------------------------------------------------------


class EvaluandStatus(Enum):
    """Outcome of resolving an :class:`EvaluandRef` against the journal."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


@dataclass(frozen=True)
class EvaluandResolution:
    """Result of resolving an :class:`EvaluandRef` against the journal.

    When ``status`` is ``AVAILABLE``, ``record`` holds the folded
    :class:`~megaplan.observability.evaluand.EvaluandRecord`.  Otherwise
    ``reason`` explains why resolution failed (missing piece_version, no
    matching record, corrupt payload, etc.).
    """

    status: EvaluandStatus
    record: Any = None  # EvaluandRecord | None
    reason: Optional[str] = None

    @property
    def is_available(self) -> bool:
        return self.status is EvaluandStatus.AVAILABLE


def resolve_evaluand(
    plan_dir: Path | str,
    evaluand_ref: EvaluandRef,
    *,
    strict: bool = False,
) -> EvaluandResolution:
    """Resolve an :class:`EvaluandRef` against the evaluand journal.

    Joins the ref's 4-tuple attribution key ``(piece_version, judge_version,
    rubric_version, input_set_hash)`` against the folded dict returned by
    :func:`~megaplan.observability.evaluand.read_evaluand_events`.

    Missing Evaluands are represented explicitly via
    :class:`EvaluandStatus.UNAVAILABLE` — never as a bare score fallback.

    Args:
        plan_dir: Path to the plan directory.
        evaluand_ref: The content-addressed reference to resolve.
        strict: If ``True``, raise on journal decode errors (passed through to
            ``read_evaluand_events(strict=...)``).

    Returns:
        An :class:`EvaluandResolution` with status and optional record/reason.
    """
    from arnold_pipelines.megaplan.observability.evaluand import read_evaluand_events

    key = evaluand_ref.key

    try:
        folded = read_evaluand_events(Path(plan_dir), strict=strict)
    except Exception as exc:
        return EvaluandResolution(
            status=EvaluandStatus.INVALID,
            reason=f"Failed to read evaluand events: {exc}",
        )

    record = folded.get(key)
    if record is not None:
        return EvaluandResolution(
            status=EvaluandStatus.AVAILABLE,
            record=record,
        )

    # The ref key wasn't found.  Give a diagnostic reason.
    return EvaluandResolution(
        status=EvaluandStatus.UNAVAILABLE,
        reason=(
            f"No EvaluandRecord found for attribution key "
            f"{key} in {plan_dir}"
        ),
    )


def _iter_claim_event_envelopes(
    plan_dir: Path | str,
    *,
    since_seq: Optional[int] = None,
) -> Iterator[dict]:
    """Yield full event envelopes (not just payloads) for CAPABILITY_CLAIM events.

    Internal helper used by advanced readers that need envelope metadata
    (scope, phase, seq, ts_utc, run_id) alongside the claim payload.
    """
    from arnold_pipelines.megaplan.observability.events import EventKind, read_events

    for event in read_events(
        Path(plan_dir),
        kinds=[EventKind.CAPABILITY_CLAIM],
        since_seq=since_seq,
    ):
        yield event

# ---------------------------------------------------------------------------
# Calibration math — half-life decay weight
# ---------------------------------------------------------------------------


def half_life_weight(
    recorded_at: float,
    now: float,
    half_life_seconds: float,
) -> float:
    """Compute exponential decay weight for a claim recorded at ``recorded_at``.

    The weight decays by a factor of 2 every ``half_life_seconds``::

        weight = 2 ** (-elapsed / half_life_seconds)

    Args:
        recorded_at: Epoch timestamp when the claim was recorded.
        now: Reference epoch timestamp (typically ``time.time()``).
        half_life_seconds: Half-life in seconds -- positive, non-zero.

    Returns:
        A float in (0.0, 1.0] -- 1.0 when ``elapsed == 0``, approaching
        but never reaching 0.0 for very stale claims.

    Raises:
        ValueError: if ``half_life_seconds`` is not strictly positive or
            ``recorded_at > now``.
    """
    if half_life_seconds <= 0:
        raise ValueError(
            f"half_life_seconds must be > 0, got {half_life_seconds!r}"
        )
    elapsed = now - recorded_at
    if elapsed < 0:
        raise ValueError(
            f"recorded_at ({recorded_at}) must not be in the future "
            f"relative to now ({now})"
        )
    return math.pow(2.0, -elapsed / half_life_seconds)


# ---------------------------------------------------------------------------
# Aggregation policy
# ---------------------------------------------------------------------------


class AggregationPolicy(Enum):
    """Where a capability claim may be aggregated.

    ``SHARED``
        The claim feeds the cross-tenant shared calibration ledger -- all
        tenants benefit from this observation.

    ``TENANT_LOCAL``
        The claim is only visible within the originating tenant/plan scope.
        Tainted, private, or cost-pressured verifier claims fall here.
    """

    SHARED = "shared"
    TENANT_LOCAL = "tenant_local"


# ---------------------------------------------------------------------------
# Taint -> policy derivation
# ---------------------------------------------------------------------------

# Taint labels that force a claim into TENANT_LOCAL aggregation.
_PRIVATE_TAINT_MARKERS: frozenset[str] = frozenset(
    {"private", "confidential", "internal", "sensitive", "pii", "phi"}
)


def derive_aggregation_policy(
    taint_class: Optional[str],
    *,
    default: AggregationPolicy = AggregationPolicy.SHARED,
    in_tree: Optional[bool] = None,
    project_dir: Optional[Path | str] = None,
    repo_root: Optional[Path | str] = None,
) -> AggregationPolicy:
    """Derive the aggregation policy from a claim's taint class.

    When ``taint_class`` is ``None`` or empty, the policy is driven by
    the ``in_tree`` signal (or path-derived defaults):

    * ``in_tree=True``  → ``SHARED`` (clean in-tree claims are shared).
    * ``in_tree=False`` → ``TENANT_LOCAL`` (clean out-of-tree claims stay
      tenant-local).
    * ``in_tree=None``  → ``default`` (no signal — preserve existing
      behaviour).

    If ``in_tree`` is ``None`` but both ``project_dir`` and ``repo_root``
    are supplied, the function computes ``in_tree`` from path containment
    (``project_dir`` is a subdirectory of ``repo_root``).

    When ``taint_class`` matches a known private marker (case-insensitive),
    the policy is **always** forced to ``TENANT_LOCAL`` regardless of the
    ``in_tree`` signal.

    Args:
        taint_class: The claim's taint class label (derived from evaluand
            taint).
        default: Fallback policy when no taint or path signal is present.
        in_tree: Explicit in-tree signal (``True`` / ``False`` / ``None``).
        project_dir: Project directory for path containment check.
        repo_root: Repository root for path containment check.

    Returns:
        The :class:`AggregationPolicy` for the claim.
    """
    if not taint_class:
        resolved_in_tree = _resolve_in_tree(in_tree, project_dir, repo_root)
        if resolved_in_tree is True:
            return AggregationPolicy.SHARED
        if resolved_in_tree is False:
            return AggregationPolicy.TENANT_LOCAL
        return default
    normalized = taint_class.lower().strip()
    if any(marker in normalized for marker in _PRIVATE_TAINT_MARKERS):
        return AggregationPolicy.TENANT_LOCAL
    # Clean with explicit taint_class but no private markers:
    # still respect the in_tree signal.
    resolved_in_tree = _resolve_in_tree(in_tree, project_dir, repo_root)
    if resolved_in_tree is True:
        return AggregationPolicy.SHARED
    if resolved_in_tree is False:
        return AggregationPolicy.TENANT_LOCAL
    return default


def _resolve_in_tree(
    in_tree: Optional[bool],
    project_dir: Optional[Path | str],
    repo_root: Optional[Path | str],
) -> Optional[bool]:
    """Resolve the ``in_tree`` signal, optionally from path containment."""
    if in_tree is not None:
        return in_tree
    if project_dir is not None and repo_root is not None:
        pd = Path(project_dir).resolve()
        rr = Path(repo_root).resolve()
        try:
            pd.relative_to(rr)
        except ValueError:
            return False
        return True
    return None


def _taint_class_from_evaluand_taint(
    taint: tuple[str, ...],
) -> Optional[str]:
    """Derive a single taint_class label from evaluand taint labels.

    The first private-adjacent taint label (case-insensitive substring match against
    ``_PRIVATE_TAINT_MARKERS``) wins.  If nothing matches, returns ``None``
    -- the claim is clean and eligible for ``SHARED`` aggregation.
    """
    if not taint:
        return None
    for label in taint:
        normalized = label.lower().strip()
        if any(marker in normalized for marker in _PRIVATE_TAINT_MARKERS):
            return normalized
    return None


def classify_claim_taint(
    taint: tuple[str, ...],
    *,
    in_tree: Optional[bool] = None,
    project_dir: Optional[Path | str] = None,
    repo_root: Optional[Path | str] = None,
) -> tuple[Optional[str], AggregationPolicy]:
    """Classify evaluand taint labels into a ``(taint_class, policy)`` pair.

    Convenience helper that runs :func:`_taint_class_from_evaluand_taint`
    and :func:`derive_aggregation_policy` in one call -- useful when
    constructing a :class:`CapabilityClaim` from an
    :class:`~megaplan.observability.evaluand.EvaluandRecord`.

    Args:
        taint: Taint labels from the evaluand record.
        in_tree: Explicit in-tree signal forwarded to
            :func:`derive_aggregation_policy`.
        project_dir: Project directory for path containment check.
        repo_root: Repository root for path containment check.

    Returns:
        A ``(taint_class, aggregation_policy)`` tuple.
    """
    tc = _taint_class_from_evaluand_taint(taint)
    policy = derive_aggregation_policy(
        tc,
        in_tree=in_tree,
        project_dir=project_dir,
        repo_root=repo_root,
    )
    return tc, policy


# ---------------------------------------------------------------------------
# Capability-class prior -- default tier for unseen classes
# ---------------------------------------------------------------------------

_UnseenTier = 4  # default tier for capability classes with no prior data


def _task_signature_class_prior(
    task_signature: str,
    *,
    tier_map: Optional[Mapping[str, int]] = None,
    default_tier: int = _UnseenTier,
) -> int:
    """Return a prior tier from a task-signature lookup.

    Legacy helper: looks up ``task_signature`` in ``tier_map`` and falls back
    to ``default_tier``.  Prefer :func:`capability_class_prior` for new
    callers that can supply a :class:`ModelIdentity`.
    """
    if tier_map is not None and task_signature in tier_map:
        return int(tier_map[task_signature])
    return default_tier


def capability_class_prior(
    model_identity: ModelIdentity | str,
    *,
    model_class_table: Optional[Mapping[str, str]] = None,
    class_tier_priors: Optional[Mapping[str, int]] = None,
    default_tier: int = _UnseenTier,
) -> int:
    """Return the prior tier for a model's capability class.

    Uses a two-level lookup: first resolve the model to a *class label*
    via ``model_class_table`` (keyed by :attr:`ModelIdentity.identity`,
    then by :attr:`ModelIdentity.model_name`), then look up the class
    label in ``class_tier_priors`` to get a tier.

    The lookup chain is:

    1. ``model_identity.identity`` → ``model_class_table`` → class label →
       ``class_tier_priors`` → tier.
    2. ``model_identity.model_name`` → ``model_class_table`` → class label →
       ``class_tier_priors`` → tier.
    3. Raw ``model_identity.model_name`` (or ``identity``) directly in
       ``class_tier_priors``.

    When none of the lookups produces a tier, ``default_tier`` (tier 4) is
    returned — a conservative fallback for unseen models and classes.

    Args:
        model_identity: The model whose class tier is being queried.
        model_class_table: Mapping from model identity/name to class label.
        class_tier_priors: Mapping from class label to tier int (1-10).
        default_tier: Fallback tier for unknown models/classes (default: 5).

    Returns:
        An integer tier (1-10).
    """
    if isinstance(model_identity, str):
        identity = model_identity
        model_name = model_identity
    else:
        identity = model_identity.identity
        model_name = model_identity.model_name

    # Step 1: Try identity in model_class_table → class_tier_priors
    if model_class_table is not None:
        for attr in (identity, model_name):
            class_label = model_class_table.get(attr)
            if class_label is not None and class_tier_priors is not None:
                tier = class_tier_priors.get(class_label)
                if tier is not None:
                    return int(tier)
    # Step 3: Try raw model_name (or identity) directly in class_tier_priors
    if class_tier_priors is not None:
        for raw_key in (model_name, identity):
            tier = class_tier_priors.get(raw_key)
            if tier is not None:
                return int(tier)
    return default_tier


# ---------------------------------------------------------------------------
# Claim filtering helpers for aggregation
# ---------------------------------------------------------------------------


def is_shared_claim(
    claim: CapabilityClaim,
    *,
    taint_class: Optional[str] = None,
    in_tree: Optional[bool] = None,
    project_dir: Optional[Path | str] = None,
    repo_root: Optional[Path | str] = None,
) -> bool:
    """Return ``True`` if a claim is eligible for ``SHARED`` aggregation.

    Claims are excluded from shared aggregation when:

    * ``low_confidence_signal`` is ``True`` (cost-pressured verifier, see
      :func:`check_reviewer_invariant`).
    * ``taint_class`` (on the claim or passed explicitly) maps to
      ``TENANT_LOCAL`` via :func:`derive_aggregation_policy`.
    * ``in_tree`` (or path-derived) is ``False`` for a clean claim —
      out-of-tree claims stay tenant-local.

    Args:
        claim: The capability claim to test.
        taint_class: Override taint class (defaults to
            ``claim.taint_class``).
        in_tree: Explicit in-tree signal forwarded to
            :func:`derive_aggregation_policy`.
        project_dir: Project directory for path containment check.
        repo_root: Repository root for path containment check.

    Returns:
        ``True`` if the claim should be included in the shared ledger.
    """
    if claim.low_confidence_signal:
        return False
    tc = taint_class if taint_class is not None else claim.taint_class
    policy = derive_aggregation_policy(
        tc,
        in_tree=in_tree,
        project_dir=project_dir,
        repo_root=repo_root,
    )
    return policy is AggregationPolicy.SHARED


def filter_shared_claims(
    claims: Sequence[CapabilityClaim],
) -> tuple[CapabilityClaim, ...]:
    """Return only claims eligible for shared aggregation.

    Convenience wrapper around :func:`is_shared_claim` for batch filtering.
    """
    return tuple(c for c in claims if is_shared_claim(c))


# ---------------------------------------------------------------------------
# Reviewer invariant -- cost-pressured verifier detection
# ---------------------------------------------------------------------------


def check_reviewer_invariant(
    *,
    verifier_tier: Optional[str],
    routed_model_tier: Optional[int],
) -> tuple[bool, Optional[str]]:
    """Check the cost-pressured verifier invariant.

    When a cheaper (higher-numbered) verifier tier evaluates a more
    expensive (lower-numbered) model's output, the claim is flagged as
    low-confidence and excluded from shared closing-loop aggregation::

        verifier_tier < routed_model_tier -> low_confidence_signal=True

    The intuition: a tier-4 reviewer cannot reliably assess tier-2 output,
    so that claim must not feed the shared calibration ledger.

    Args:
        verifier_tier: String tier label of the verifier model
            (e.g. ``"3"``).
        routed_model_tier: Integer tier of the routed model (e.g. ``2``).

    Returns:
        A ``(low_confidence_signal, reason)`` tuple.  ``reason`` is
        ``None`` when the invariant passes (no issue) and a diagnostic
        string when it fails.
    """
    if verifier_tier is None or routed_model_tier is None:
        return True, "missing verifier or model tier"
    try:
        vt = int(verifier_tier)
    except (TypeError, ValueError):
        return True, f"unparseable verifier_tier: {verifier_tier!r}"
    if vt < routed_model_tier:
        return True, (
            f"cost-pressured verifier: verifier_tier={verifier_tier} "
            f"< routed_model_tier={routed_model_tier}"
        )
    return False, None


# ---------------------------------------------------------------------------
# Weighted aggregation helpers
# ---------------------------------------------------------------------------


def aggregate_weighted_tier(
    claims: Sequence[CapabilityClaim],
    *,
    now: Optional[float] = None,
    half_life_seconds: float = 30.0 * 86400,  # 30 days
    default_tier: int = 4,
) -> float:
    """Compute a decay-weighted average predicted tier from a set of claims.

    Each claim's ``predicted_tier`` (or ``default_tier`` when ``None``) is
    weighted by :func:`half_life_weight`.  Returns ``float(default_tier)``
    when ``claims`` is empty.

    Args:
        claims: Calibration claims to aggregate.
        now: Reference time (default: ``time.time()``).
        half_life_seconds: Half-life for decay weighting.
        default_tier: Tier to use for claims missing ``predicted_tier``.

    Returns:
        Weighted average tier as a float.
    """
    if now is None:
        now = time.time()
    if not claims:
        return float(default_tier)
    total_weight = 0.0
    weighted_sum = 0.0
    for claim in claims:
        w = half_life_weight(claim.recorded_at, now, half_life_seconds)
        tier = (
            float(claim.predicted_tier)
            if claim.predicted_tier is not None
            else float(default_tier)
        )
        weighted_sum += tier * w
        total_weight += w
    if total_weight == 0.0:
        return float(default_tier)
    return weighted_sum / total_weight


def normalize_projected_complexity(
    complexity: Any,
    *,
    default: int = 5,
) -> int:
    """Normalize a projected task complexity to the 1..10 contract.

    Mirrors finalize's current normalization behaviour: malformed, boolean,
    missing, or out-of-range values fall back to a mid/high tier (5).
    """
    if (
        not isinstance(complexity, int)
        or isinstance(complexity, bool)
        or complexity < 1
        or complexity > 10
    ):
        return default
    return complexity


def project_claimed_complexity(
    claims: Sequence[CapabilityClaim],
    *,
    now: Optional[float] = None,
    half_life_seconds: float = 30.0 * 86400,
    default: int = 5,
) -> int:
    """Project a task complexity from claims while preserving 1..10 semantics."""
    if not claims:
        return default
    projected = aggregate_weighted_tier(
        claims,
        now=now,
        half_life_seconds=half_life_seconds,
        default_tier=default,
    )
    if not math.isfinite(projected):
        return default
    return normalize_projected_complexity(int(round(projected)), default=default)


def project_batch_complexity(
    finalize_data: Mapping[str, Any],
    batch_task_ids: Sequence[str],
) -> int:
    """Preserve the existing batch fail-safe semantics for projected routing."""
    from arnold_pipelines.megaplan._core.io import compute_batch_complexity

    return compute_batch_complexity(dict(finalize_data), list(batch_task_ids))


def project_tier_models(
    claims: Sequence[CapabilityClaim],
    fallback_tier_models: Mapping[str, Mapping[int | str, Any]] | None = None,
    *,
    now: Optional[float] = None,
    half_life_seconds: float = 30.0 * 86400,
) -> dict[str, dict[str, str]]:
    """Project ``tier_models`` from eligible ledger claims.

    Eligible claims are clean/shared claims with a valid ``route_phase`` (or a
    task-signature prefix that names a known phase), ``predicted_tier`` in
    1..10, and a non-empty ``routed_tier_spec``. For every phase/tier slot the
    selected spec is the candidate with the highest freshness-decayed total
    weight, then the most recent claim, then the lexicographically smallest
    spec. Missing phase/tier slots are filled from the fallback TOML-derived
    map before the existing profile validators canonicalize the result.
    """
    from arnold_pipelines.megaplan.profiles import (
        VALID_PHASE_KEYS,
        _canonicalize_tier_models_for_json,
        _validate_projected_tier_models,
    )

    reference_now = time.time() if now is None else now
    projected: dict[str, dict[int, str]] = {}
    candidates: dict[tuple[str, int], dict[str, tuple[float, float]]] = {}

    for claim in claims:
        if not is_shared_claim(claim):
            continue
        phase = _claim_route_phase(claim, valid_phases=VALID_PHASE_KEYS)
        if phase is None:
            continue
        tier = normalize_projected_complexity(claim.predicted_tier, default=0)
        if tier == 0:
            continue
        spec = claim.routed_tier_spec.strip() if claim.routed_tier_spec else ""
        if not spec:
            continue
        weight = half_life_weight(
            claim.recorded_at,
            reference_now,
            half_life_seconds,
        )
        slot = candidates.setdefault((phase, tier), {})
        total_weight, most_recent = slot.get(spec, (0.0, float("-inf")))
        slot[spec] = (
            total_weight + weight,
            max(most_recent, claim.recorded_at),
        )

    for (phase, tier), weighted_specs in candidates.items():
        best_spec, _metrics = min(
            weighted_specs.items(),
            key=lambda item: (-item[1][0], -item[1][1], item[0]),
        )
        projected.setdefault(phase, {})[tier] = best_spec

    fallback_validated = _validate_projected_tier_models(fallback_tier_models or {})
    for phase, tiers in fallback_validated.items():
        phase_slots = projected.setdefault(phase, {})
        for tier, spec in tiers.items():
            phase_slots.setdefault(tier, spec)

    validated = _validate_projected_tier_models(projected)
    return _canonicalize_tier_models_for_json(validated)


def _claim_route_phase(
    claim: CapabilityClaim,
    *,
    valid_phases: frozenset[str],
) -> Optional[str]:
    if claim.route_phase is not None:
        phase = claim.route_phase.strip()
        return phase if phase in valid_phases else None
    prefix, sep, _rest = claim.task_signature.partition(":")
    if sep and prefix in valid_phases:
        return prefix
    return None


# ---------------------------------------------------------------------------
# Route selection — pure read/query route(TaskIdentifiers) -> RouteSuggestion
# ---------------------------------------------------------------------------


def route(
    task_signature: str,
    *,
    plan_dir: Path | str | None = None,
    claims: Sequence[CapabilityClaim] | None = None,
    taint_class: Optional[str] = None,
    exploration_budget: float = 0.0,
    seed: Optional[int] = None,
    half_life_seconds: float = 30.0 * 86400,  # 30 days
    default_tier: int = 4,
    tier_models: Mapping[str, Mapping[str, str]] | None = None,
    exclude_tainted: bool = True,
    now: Optional[float] = None,
) -> RouteSuggestion:
    """Pure route selection — read claims, project a tier, optionally explore.

    This is a **read/query-only** path.  It never writes to the journal, never
    mutates TOML, and never emits events.  The caller is responsible for
    deciding whether to follow the suggestion or fall back to TOML-derived
    routing.

    When ``exploration_budget`` is ``0.0`` (the default), the route is greedy:
    it returns the decay-weighted consensus tier with no exploration flag.

    When ``exploration_budget > 0.0`` and a ``seed`` is provided, the function
    performs **deterministic pseudorandom exploration**: for a fraction of
    calls equal to ``exploration_budget`` (clamped to [0, 1]) a non-greedy
    tier is selected.  The exploration is tagged with a
    ``counterfactual_tag`` in the returned :class:`RouteSuggestion`.

    Args:
        task_signature: Opaque task-class identifier used to filter claims.
        plan_dir: Plan directory — claims are read from here when ``claims``
            is not supplied.
        claims: Pre-loaded claims (avoids journal I/O).  Supersedes
            ``plan_dir`` when both are provided.
        taint_class: Taint filter — only claims whose ``taint_class`` matches
            (or is ``None``/equal) are considered.
        exploration_budget: Probability of selecting a non-greedy tier
            (capped to [0, 1]).  ``0.0`` means no exploration.
        seed: Integer seed for deterministic exploration.  When ``None``,
            exploration is skipped even if ``budget > 0`` (the caller must
            inject a seed for determinism).
        half_life_seconds: Half-life for decay weighting of claim recency.
        default_tier: Tier returned when no claims are available (1–5).
        tier_models: Optional tier_models mapping for resolving tier → spec
            lookups.  When provided and exploration selects a tier, the
            returned ``tier_spec`` is looked up from this mapping.
        exclude_tainted: If ``True``, claims with a ``taint_class`` that maps
            to ``TENANT_LOCAL`` aggregation are excluded.
        now: Reference epoch time for half-life weighting (default:
            ``time.time()``).

    Returns:
        A :class:`RouteSuggestion`.  When ``tier_spec`` is ``None`` the
        caller should fall back to TOML-derived routing.
    """
    import random as _random

    # ------------------------------------------------------------------
    # 1. Collect claims
    # ------------------------------------------------------------------
    if claims is None and plan_dir is not None:
        claims = read_capability_claims(
            plan_dir,
            task_signature=task_signature,
            taint_class=taint_class,
        )
    elif claims is None:
        claims = ()

    # ------------------------------------------------------------------
    # 2. Filter claims for shared aggregation
    # ------------------------------------------------------------------
    shared: tuple[CapabilityClaim, ...]
    if exclude_tainted:
        shared = filter_shared_claims(claims)
    else:
        shared = tuple(claims)

    # ------------------------------------------------------------------
    # 3. Greedy projection — the decay-weighted consensus tier
    # ------------------------------------------------------------------
    greedy_tier: int = project_claimed_complexity(
        shared,
        now=now,
        half_life_seconds=half_life_seconds,
        default=default_tier,
    )

    # Compute a confidence score from both freshness and agreement.
    confidence: float
    if not shared:
        confidence = 0.0
    else:
        _now = now if now is not None else time.time()
        total_weight = 0.0
        greedy_weight = 0.0
        for claim in shared:
            weight = half_life_weight(
                claim.recorded_at, _now, half_life_seconds
            )
            total_weight += weight
            claim_tier = normalize_projected_complexity(
                claim.predicted_tier,
                default=default_tier,
            )
            if claim_tier == greedy_tier:
                greedy_weight += weight
        # Fresh evidence should raise confidence, but conflicting evidence
        # should cap it. Multiply freshness by consensus on the greedy tier.
        freshness_confidence = 1.0 - math.exp(-total_weight / 3.0)
        agreement_confidence = (
            greedy_weight / total_weight if total_weight > 0.0 else 0.0
        )
        confidence = freshness_confidence * agreement_confidence
        confidence = max(0.0, min(1.0, confidence))

    # ------------------------------------------------------------------
    # 4. Exploration — deterministic pseudorandom off-policy selection
    # ------------------------------------------------------------------
    budget = max(0.0, min(1.0, float(exploration_budget)))

    if budget == 0.0 or seed is None:
        # No exploration → return greedy suggestion.
        tier_spec = _lookup_tier_spec(greedy_tier, tier_models)
        return RouteSuggestion(
            tier_spec=tier_spec,
            model_identity=None,
            confidence=confidence,
            exploration=False,
            projected_tier=greedy_tier,
            reason=(
                "greedy (no claims)"
                if not shared
                else f"greedy tier {greedy_tier} from {len(shared)} claims"
            ),
        )

    # Deterministic exploration: seed the RNG with the caller-provided seed
    # hashed together with the task_signature so different tasks get
    # different exploration outcomes even with the same global seed.
    task_hash = int.from_bytes(
        hashlib.sha256(task_signature.encode("utf-8")).digest()[:8],
        "big",
    )
    rng = _random.Random(seed ^ task_hash)
    roll = rng.random()

    if roll >= budget:
        # Do not explore on this call — return greedy.
        tier_spec = _lookup_tier_spec(greedy_tier, tier_models)
        return RouteSuggestion(
            tier_spec=tier_spec,
            model_identity=None,
            confidence=confidence,
            exploration=False,
            projected_tier=greedy_tier,
            reason=(
                f"greedy tier {greedy_tier} "
                f"(exploration roll {roll:.3f} >= budget {budget:.3f})"
            ),
        )

    # Explore: select a non-greedy tier from the available set.
    available_tiers = _available_tiers(tier_models, default_tier)
    off_policy_candidates = [t for t in available_tiers if t != greedy_tier]
    if not off_policy_candidates:
        # Only one tier available — cannot explore.
        tier_spec = _lookup_tier_spec(greedy_tier, tier_models)
        return RouteSuggestion(
            tier_spec=tier_spec,
            model_identity=None,
            confidence=confidence,
            exploration=False,
            projected_tier=greedy_tier,
            reason=(
                f"greedy tier {greedy_tier} "
                f"(no off-policy candidates for exploration)"
            ),
        )

    explored_tier = rng.choice(off_policy_candidates)
    tier_spec = _lookup_tier_spec(explored_tier, tier_models)

    # Build the counterfactual tag: encodes seed, budget, and the chosen tier
    # so the selection is traceable and reproducible.
    counterfactual_tag = (
        f"cf:explore:seed={seed}:budget={budget:.4f}:roll={roll:.6f}"
        f":greedy={greedy_tier}:selected={explored_tier}"
    )

    return RouteSuggestion(
        tier_spec=tier_spec,
        model_identity=None,
        confidence=confidence,
        exploration=True,
        counterfactual_tag=counterfactual_tag,
        projected_tier=explored_tier,
        reason=(
            f"explore tier {explored_tier} "
            f"(greedy was {greedy_tier}, "
            f"seed={seed}, roll={roll:.6f} < budget={budget:.4f})"
        ),
    )


def query_route_if_enabled(
    task_signature: str,
    *,
    plan_dir: Path | str | None = None,
    claims: Sequence[CapabilityClaim] | None = None,
    taint_class: Optional[str] = None,
    exploration_budget: float = 0.0,
    seed: Optional[int] = None,
    half_life_seconds: float = 30.0 * 86400,
    default_tier: int = 4,
    tier_models: Mapping[str, Mapping[str, str]] | None = None,
    exclude_tainted: bool = True,
    now: Optional[float] = None,
) -> RouteSuggestion | None:
    """Return a route suggestion only when calibration query routing is enabled."""
    from arnold_pipelines.megaplan.feature_flags import calibration_query_route_on

    if not calibration_query_route_on():
        return None
    suggestion = route(
        task_signature,
        plan_dir=plan_dir,
        claims=claims,
        taint_class=taint_class,
        exploration_budget=exploration_budget,
        seed=seed,
        half_life_seconds=half_life_seconds,
        default_tier=default_tier,
        tier_models=tier_models,
        exclude_tainted=exclude_tainted,
        now=now,
    )
    if not suggestion.has_suggestion:
        return None
    return suggestion


def project_tier_models_if_enabled(
    claims: Sequence[CapabilityClaim],
    fallback_tier_models: Mapping[str, Mapping[int | str, Any]] | None = None,
) -> dict[str, dict[str, str]] | None:
    """Return projected tier models only when the calibration route flag is on."""
    from arnold_pipelines.megaplan.feature_flags import calibration_query_route_on

    if not calibration_query_route_on():
        return None
    projected = project_tier_models(claims, fallback_tier_models)
    if not projected:
        return None
    return projected


def _lookup_tier_spec(
    tier: int,
    tier_models: Mapping[str, Mapping[str, str]] | None,
) -> Optional[str]:
    """Resolve a tier number to a tier spec string from tier_models.

    Returns ``None`` when ``tier_models`` is ``None`` (caller should fall
    back to TOML).
    """
    if tier_models is None:
        return None
    # Search across phases for the matching tier key (as string).
    tier_str = str(tier)
    for phase_specs in tier_models.values():
        if isinstance(phase_specs, Mapping) and tier_str in phase_specs:
            return str(phase_specs[tier_str])
    return None


def _available_tiers(
    tier_models: Mapping[str, Mapping[str, str]] | None,
    default_tier: int,
) -> list[int]:
    """Return the set of tiers available for exploration.

    When ``tier_models`` is provided, the available tiers are those with at
    least one spec across any phase.  Otherwise the full 1..10 range is used,
    with ``default_tier`` always reachable as a fallback.
    """
    if tier_models is None:
        return [1, 2, 3, 4, 5]

    tiers: set[int] = {default_tier}
    for phase_specs in tier_models.values():
        if isinstance(phase_specs, Mapping):
            for key in phase_specs:
                try:
                    tiers.add(int(key))
                except (TypeError, ValueError):
                    pass
    if not tiers:
        return [default_tier]
    return sorted(tiers)


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

__all__ = [
    "AggregationPolicy",
    "CapabilityClaim",
    "EvaluandRef",
    "EvaluandResolution",
    "EvaluandStatus",
    "ModelIdentity",
    "QueryPolicy",
    "RouteSuggestion",
    "aggregate_weighted_tier",
    "capability_class_prior",
    "check_reviewer_invariant",
    "classify_claim_taint",
    "derive_aggregation_policy",
    "filter_shared_claims",
    "half_life_weight",
    "is_shared_claim",
    "iter_capability_claim_payloads",
    "normalize_projected_complexity",
    "project_batch_complexity",
    "project_claimed_complexity",
    "project_tier_models",
    "project_tier_models_if_enabled",
    "read_capability_claims",
    "resolve_evaluand",
    "route",
    "query_route_if_enabled",
    "validate_capability_claim",
    "write_capability_claim",
]
