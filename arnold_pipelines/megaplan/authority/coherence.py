"""Read-only authority coherence facade over the Maintenance join (M2, T10).

This module is the *replacement* for the previous authority coherence
implementation, which maintained a second, filesystem-based coherence
algorithm and imported the nonexistent ``CoherentObservationEnvelope`` from
``arnold_pipelines.run_authority.contracts`` (the module could not even be
imported).  It is now a thin, read-only compatibility facade:

* **Coherent capture** delegates to
  :func:`~arnold_pipelines.megaplan.maintenance.observation.capture_observation`,
  the canonical bounded two-phase join (before -> read -> after, retry only
  within the configured two-attempt default).
* **Envelope construction** delegates to
  :class:`~arnold_pipelines.megaplan.maintenance.contracts.ObservationEnvelope`,
  whose ``build`` derives ``terminal`` / ``green`` / ``dispatchable``
  fail-closed from the observed completeness/freshness/coherence states.
  This module performs no local derivation and can never infer green,
  terminal, or dispatchable state.
* There is exactly **one coherence algorithm** in the system — the
  Maintenance join.  This module carries no reduction, no classification,
  no filesystem capture, no ``fold_events`` import, and no fallback path.
* Supported read-only callers keep a stable entry point:
  :func:`capture_authority_coherence` is preserved as the authority-facing
  name and forwards verbatim to the Maintenance join (same signature and
  semantics: ``capture_observation(sources, *, observed_at, ...)``).

The full join API and the closed envelope contract are re-exported here so
authority-side consumers can build sources, capture observations, and read
envelopes without importing the Maintenance package directly.
"""

from __future__ import annotations

from typing import Any

from arnold_pipelines.megaplan.maintenance.contracts import (
    CoherenceReason,
    CoherenceState,
    CompletenessState,
    FreshnessState,
    ObservationEnvelope,
    SourceVersionVector,
    eligibility_supported,
    precedence_rank,
)
from arnold_pipelines.megaplan.maintenance.observation import (
    DEFAULT_MAX_ATTEMPTS,
    JoinSource,
    capture_observation,
    conformance_source,
    custody_source,
    native_manifest_source,
    run_authority_source,
    wbc_source,
)


def capture_authority_coherence(*args: Any, **kwargs: Any) -> ObservationEnvelope:
    """Capture one coherent authority observation via the Maintenance join.

    Compatibility entry point preserved for supported read-only callers of
    this module.  It forwards verbatim to the canonical join
    :func:`~arnold_pipelines.megaplan.maintenance.observation.capture_observation`
    — ``capture_observation(sources, *, observed_at, environment, tenant,
    run, chain, plan, stage, model, profile, attempt, max_attempts,
    expected_incarnation, expected_restore_generation)`` — and returns the
    Maintenance :class:`ObservationEnvelope`.  There is no local fallback:
    every call path runs exactly the one coherence algorithm (the join), and
    terminal/green/dispatchable eligibility is derived only by
    ``ObservationEnvelope.build``, fail-closed.
    """
    return capture_observation(*args, **kwargs)


__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "JoinSource",
    "capture_authority_coherence",
    "capture_observation",
    "conformance_source",
    "custody_source",
    "native_manifest_source",
    "run_authority_source",
    "wbc_source",
    "CoherenceReason",
    "CoherenceState",
    "CompletenessState",
    "FreshnessState",
    "ObservationEnvelope",
    "SourceVersionVector",
    "eligibility_supported",
    "precedence_rank",
]
