"""Calibration experiment findings.

This module holds deterministic, write-only experiment records for the M5
calibration ledger. These findings are observational only:

* they always set ``governs_live_policy`` to ``False``
* they write through the existing ``EventSink`` / ``events.ndjson`` path
* they do not query routing, rewrite TOML, or introduce a new backend
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


CALIBRATION_EXPERIMENT_EVENT_KIND = "calibration_experiment"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(nested) for key, nested in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_jsonable(nested) for nested in value]
    return value


@dataclass(frozen=True)
class CalibrationExperimentFinding:
    """Shared value object for recorded calibration experiment findings."""

    experiment_name: str
    inputs_summary: Mapping[str, Any]
    findings: tuple[str, ...]
    recorded_at: float = field(default_factory=time.time)
    governs_live_policy: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs_summary", dict(self.inputs_summary))
        object.__setattr__(self, "findings", tuple(str(item) for item in self.findings))

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.to_json()).encode("utf-8")
        ).hexdigest()

    def to_json(self) -> dict[str, Any]:
        return {
            "experiment_name": self.experiment_name,
            "inputs_summary": _jsonable(self.inputs_summary),
            "findings": list(self.findings),
            "governs_live_policy": False,
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True, init=False)
class CheapestRoutingExperiment(CalibrationExperimentFinding):
    """Cheapest-routing vs prompt-caching tension finding."""

    phase: str
    cheap_route_pressure: float
    prefix_cache_hit_rate: float
    tension_threshold: float

    def __init__(
        self,
        *,
        phase: str,
        cheap_route_pressure: float,
        prefix_cache_hit_rate: float,
        tension_threshold: float,
        findings: Sequence[str],
        recorded_at: float | None = None,
    ) -> None:
        summary = {
            "phase": phase,
            "cheap_route_pressure": float(cheap_route_pressure),
            "prefix_cache_hit_rate": float(prefix_cache_hit_rate),
            "tension_threshold": float(tension_threshold),
        }
        super().__init__(
            experiment_name="cheapest_routing",
            inputs_summary=summary,
            findings=tuple(findings),
            recorded_at=time.time() if recorded_at is None else float(recorded_at),
        )
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "cheap_route_pressure", float(cheap_route_pressure))
        object.__setattr__(self, "prefix_cache_hit_rate", float(prefix_cache_hit_rate))
        object.__setattr__(self, "tension_threshold", float(tension_threshold))


@dataclass(frozen=True, init=False)
class MonocultureExperiment(CalibrationExperimentFinding):
    """Monoculture / co-degradation attractor finding."""

    phase: str
    monoculture_index: float
    low_confidence_claim_count: int
    filtered_claim_count: int
    attractor_threshold: float

    def __init__(
        self,
        *,
        phase: str,
        monoculture_index: float,
        low_confidence_claim_count: int,
        filtered_claim_count: int,
        attractor_threshold: float,
        findings: Sequence[str],
        recorded_at: float | None = None,
    ) -> None:
        summary = {
            "phase": phase,
            "monoculture_index": float(monoculture_index),
            "low_confidence_claim_count": int(low_confidence_claim_count),
            "filtered_claim_count": int(filtered_claim_count),
            "attractor_threshold": float(attractor_threshold),
        }
        super().__init__(
            experiment_name="monoculture",
            inputs_summary=summary,
            findings=tuple(findings),
            recorded_at=time.time() if recorded_at is None else float(recorded_at),
        )
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "monoculture_index", float(monoculture_index))
        object.__setattr__(
            self,
            "low_confidence_claim_count",
            int(low_confidence_claim_count),
        )
        object.__setattr__(self, "filtered_claim_count", int(filtered_claim_count))
        object.__setattr__(self, "attractor_threshold", float(attractor_threshold))


def write_experiment_finding(
    finding: CalibrationExperimentFinding,
    *,
    plan_dir: Path | str | None = None,
    event_sink: Any | None = None,
    phase: Optional[str] = None,
    scope: Optional[str] = None,
) -> dict[str, Any]:
    """Record an experiment finding through the existing EventSink path."""

    if event_sink is None and plan_dir is None:
        raise ValueError(
            "write_experiment_finding requires either plan_dir= or event_sink="
        )

    if event_sink is None:
        from arnold_pipelines.megaplan.observability.event_sink import NdjsonBackend

        event_sink = NdjsonBackend(Path(plan_dir))  # type: ignore[arg-type]

    emitted_phase = phase
    if emitted_phase is None and hasattr(finding, "phase"):
        emitted_phase = getattr(finding, "phase")

    return event_sink.emit(
        CALIBRATION_EXPERIMENT_EVENT_KIND,
        payload=finding.to_json(),
        scope=scope,
        phase=emitted_phase,
        idempotency_key=finding.content_hash,
    )


# ---------------------------------------------------------------------------
# Experiment feeders — consume cost aggregates + projected claims
# ---------------------------------------------------------------------------


def _compute_cheap_route_pressure(
    claims: Sequence[Any],
    *,
    cheap_tier_max: int = 2,
) -> float:
    """Derive cheap-route pressure from claims.

    Returns the proportion of eligible claims whose ``predicted_tier`` is at
    or below ``cheap_tier_max``.  An empty claim set yields 0.0.
    """
    if not claims:
        return 0.0
    cheap = 0
    for claim in claims:
        tier = getattr(claim, "predicted_tier", None)
        if tier is not None and isinstance(tier, int) and tier <= cheap_tier_max:
            cheap += 1
    return cheap / len(claims)


def run_cheapest_routing_experiment(
    *,
    cost_aggregate: Mapping[str, Any],
    claims: Sequence[Any],
    phase: str = "execute",
    tension_threshold: float = 0.75,
    cache_hit_low_threshold: float = 0.3,
    recorded_at: Optional[float] = None,
) -> Optional[CheapestRoutingExperiment]:
    """Feed the cheapest-routing-vs-prompt-caching tension experiment.

    Consumes ``phase_prefix_cache_hit_rate`` from *cost_aggregate* and the
    cheap-route pressure derived from ``predicted_tier`` on *claims*.

    A tension finding is emitted when the cheap-route pressure exceeds
    *tension_threshold* **and** the prefix-cache hit rate for *phase* is
    below *cache_hit_low_threshold*.

    Returns ``None`` when no tension is detected so callers can skip writing.
    """
    cache_hit_rates: Mapping[str, Any] = cost_aggregate.get(
        "phase_prefix_cache_hit_rate", {}
    )
    cache_hit_rate = float(cache_hit_rates.get(phase, 0.0))
    cheap_route_pressure = _compute_cheap_route_pressure(claims)

    if (
        cheap_route_pressure > tension_threshold
        and cache_hit_rate < cache_hit_low_threshold
    ):
        return CheapestRoutingExperiment(
            phase=phase,
            cheap_route_pressure=cheap_route_pressure,
            prefix_cache_hit_rate=cache_hit_rate,
            tension_threshold=tension_threshold,
            findings=(
                (
                    f"cheapest_routing tension: pressure={cheap_route_pressure:.3f}"
                    f" > {tension_threshold}, cache_hit={cache_hit_rate:.3f}"
                    f" < {cache_hit_low_threshold} (phase={phase})"
                ),
            ),
            recorded_at=recorded_at,
        )
    return None


def run_monoculture_experiment(
    *,
    cost_aggregate: Mapping[str, Any],
    claims: Sequence[Any],
    phase: str = "execute",
    attractor_threshold: float = 0.7,
    recorded_at: Optional[float] = None,
) -> Optional[MonocultureExperiment]:
    """Feed the monoculture / co-degradation attractor experiment.

    Consumes ``monoculture_index`` from *cost_aggregate* and counts
    low-confidence / filtered claims from *claims*.

    An attractor finding is emitted when the monoculture index exceeds
    *attractor_threshold* (closer to 1.0 = fewer distinct models, more
    concentration).  Low-confidence claims are those where
    ``low_confidence_signal`` is ``True``; filtered claims are non-shared
    claims determined by :func:`~megaplan.calibration.ledger.is_shared_claim`.

    Returns ``None`` when no attractor is detected so callers can skip writing.
    """
    monoculture_index = float(cost_aggregate.get("monoculture_index", 0.0))

    from arnold_pipelines.megaplan.calibration.ledger import is_shared_claim as _is_shared

    low_confidence_claim_count = sum(
        1 for c in claims if getattr(c, "low_confidence_signal", False)
    )
    filtered_claim_count = sum(
        1 for c in claims if not _is_shared(c)
    )

    if monoculture_index > attractor_threshold:
        return MonocultureExperiment(
            phase=phase,
            monoculture_index=monoculture_index,
            low_confidence_claim_count=low_confidence_claim_count,
            filtered_claim_count=filtered_claim_count,
            attractor_threshold=attractor_threshold,
            findings=(
                (
                    f"monoculture attractor: index={monoculture_index:.3f}"
                    f" > {attractor_threshold}, low_conf={low_confidence_claim_count}"
                    f", filtered={filtered_claim_count} (phase={phase})"
                ),
            ),
            recorded_at=recorded_at,
        )
    return None


__all__ = [
    "CALIBRATION_EXPERIMENT_EVENT_KIND",
    "CalibrationExperimentFinding",
    "CheapestRoutingExperiment",
    "MonocultureExperiment",
    "run_cheapest_routing_experiment",
    "run_monoculture_experiment",
    "write_experiment_finding",
]
