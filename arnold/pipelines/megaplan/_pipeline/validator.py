"""W7 — Static graph validator for :class:`Pipeline` definitions.

Pure graph-shape validation, NO dispatch and NO Port resolution:

* every :class:`Edge`.``target`` names a real stage in ``Pipeline.stages`` or
  the reserved terminal ``\"halt\"``;
* ``\"halt\"`` is never used as an :class:`Edge`.``label`` (it is reserved as a
  target only);
* every stage that emits at least one ``kind == \"decision\"`` edge must cover
  the declared ``decision_vocabulary`` when non-empty;
* every stage that emits at least one ``kind == \"override\"`` edge must cover
  the declared ``override_vocabulary`` when non-empty;
* no stage is unreachable from :attr:`Pipeline.entry`.

M3c T3/T4: validation logic now lives in :mod:`arnold.pipeline.validator`.
This module provides a compatibility shim that delegates to Arnold with
the megaplan fallback vocabulary.
"""

from __future__ import annotations

from typing import Any

# ── Megaplan fallback vocabularies ────────────────────────────────────────

#: Standard planning-pipeline decision vocabulary when a stage declares no
#: ``decision_vocabulary`` but has decision/gate edges.  Injected by the
#: Megaplan shim before delegating to Arnold so that legacy ``kind='gate'``
#: edges on stages without explicit vocabularies are still validated.
_FALLBACK_DECISION_VOCABULARY: frozenset[str] = frozenset(
    {"proceed", "iterate", "tiebreaker", "escalate"}
)

# ── Re-export the Arnold types for backward compatibility ──────────────
from arnold.pipeline.validator import (  # noqa: F401  # re-export
    CONTRACT_ERROR_CODE_MAP,
    DECLARATION_DRIFT_CODE,
    Diagnostics,
    MISSING_BINDING_CODE,
    UNKNOWN_ADAPTER_CODE,
    UNSATISFIED_CAPABILITY_CODE,
    ValidationIssue,
    ValidationOptions,
    contract_diagnostic_code,
    validate_control_flow as _arnold_validate_control_flow,
    validate as _arnold_validate,
)


def validate(
    pipeline: Any,
    options: ValidationOptions | None = None,
    *,
    adapter_registry: Any = None,
) -> Diagnostics:
    """Run the full graph-shape validation over *pipeline*.

    A thin wrapper around :func:`arnold.pipeline.validator.validate` that
    injects the Megaplan ``_FALLBACK_DECISION_VOCABULARY`` when no explicit
    options are supplied.  This ensures legacy ``kind='gate'`` edges on
    vocabulary-less stages still participate in coverage checks.

    Returns a :class:`Diagnostics` whose ``defects`` list is empty iff
    every check passes.
    """
    if options is None:
        from arnold.pipeline.validator import ValidationOptions as VO

        options = VO(
            decision_vocabulary_fallback=_FALLBACK_DECISION_VOCABULARY,
        )
    return _arnold_validate(pipeline, options, adapter_registry=adapter_registry)


def validate_control_flow(
    pipeline: Any,
    options: ValidationOptions | None = None,
) -> Diagnostics:
    """Run control-flow validation over *pipeline*.

    Delegates to :func:`arnold.pipeline.validator.validate_control_flow`
    with the Megaplan fallback vocabulary injected when no explicit
    *options* are supplied.
    """
    if options is None:
        from arnold.pipeline.validator import ValidationOptions as VO

        options = VO(
            decision_vocabulary_fallback=_FALLBACK_DECISION_VOCABULARY,
        )
    return _arnold_validate_control_flow(pipeline, options)


__all__ = [
    "CONTRACT_ERROR_CODE_MAP",
    "DECLARATION_DRIFT_CODE",
    "Diagnostics",
    "MISSING_BINDING_CODE",
    "UNKNOWN_ADAPTER_CODE",
    "UNSATISFIED_CAPABILITY_CODE",
    "ValidationIssue",
    "ValidationOptions",
    "contract_diagnostic_code",
    "validate",
    "validate_control_flow",
]
