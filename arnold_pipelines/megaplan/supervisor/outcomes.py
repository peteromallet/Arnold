"""Re-export adapter: delegates to arnold.supervisor.outcomes for outcome normalization."""

from arnold.supervisor.outcomes import (
    NORMALIZED_FROM_DRIVER_SOURCE,
    NormalizedOutcome,
    _DOCUMENTED_STATUSES,
    _DRIVER_STATUS_TO_RUN_OUTCOME,
    normalize_driver_outcome,
    normalize_driver_outcome_from_dict,
)

__all__ = [
    "NORMALIZED_FROM_DRIVER_SOURCE",
    "NormalizedOutcome",
    "normalize_driver_outcome",
    "normalize_driver_outcome_from_dict",
    "_DRIVER_STATUS_TO_RUN_OUTCOME",
]
