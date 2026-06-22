"""Step execution contracts: StepContext and StepResult.

Rehomed from ``arnold_pipelines.megaplan._pipeline.types`` during the M3
burn-down (T11).  These are Megaplan-specific runtime contracts that are
INCOMPATIBLE with Arnold's StepContext/StepResult per the T8 shape audit,
so they live in a Megaplan-owned responsibility-named module rather than
being repointed to ``arnold.pipeline.types``.

Dependencies:
* ``RunEnvelope`` / ``EMPTY_ENVELOPE`` — from ``arnold.runtime.envelope``
* ``PipelineVerdict`` / ``ContractResult`` — from ``arnold.pipeline.types``
  (FULLY COMPATIBLE per T8)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.types import ContractResult, PipelineVerdict
from arnold.runtime.envelope import EMPTY_ENVELOPE, RunEnvelope

NextEdge = str


@dataclass
class StepContext:
    """Context handed to ``Step.run`` at dispatch time.

    ``state`` is typed ``Any`` in Sprint 1: the live megaplan ``PlanState``
    is a ``TypedDict`` at ``megaplan/types.py:146``, and tightening the
    annotation belongs to Sprint 2 once the port is in flight.
    """

    plan_dir: Path
    state: Any
    profile: Any
    mode: str
    inputs: Mapping[str, Path] = field(default_factory=dict)
    budget: Any = None
    envelope: RunEnvelope = field(default_factory=lambda: EMPTY_ENVELOPE)


@dataclass(frozen=True)
class StepResult:
    """What a ``Step.run`` invocation returns.

    ``outputs`` maps a label to a filesystem path. The executor verifies
    existence only; layout under ``ctx.plan_dir`` is unconstrained beyond
    that. ``next`` is matched against the enclosing stage's edges (with
    ``'halt'`` reserved). ``state_patch`` is applied to working state via
    a defensive ``dict(...)`` copy.

    ``contract_result`` carries typed seam payloads when a step emits an
    evidence-first contract. Its ``schema_version`` is the structural
    ``ContractResult`` envelope version, while any logical payload schema
    version belongs inside ``contract_result.payload``.
    """

    outputs: Mapping[str, Path] = field(default_factory=dict)
    verdict: PipelineVerdict | None = None
    next: NextEdge = "halt"
    state_patch: Mapping[str, Any] = field(default_factory=dict)
    contract_result: ContractResult | None = None
    envelope: RunEnvelope = field(default_factory=lambda: EMPTY_ENVELOPE)
