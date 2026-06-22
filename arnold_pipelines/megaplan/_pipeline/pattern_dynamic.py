"""Dynamic runtime primitives for pipeline pattern composition.

M3c T8: Core fanout mechanics now delegate to
:mod:`arnold.pipeline.pattern_dynamic`.  Megaplan-specific governor
checks, envelope context, and typed-port flag handling remain here
as bridge hooks.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence, cast

# ── Arnold neutral fanout core ───────────────────────────────────────────
from arnold.pipeline.pattern_dynamic import (
    LAST_FANOUT_RESULTS_PORT as _ARNOLD_LAST_FANOUT_RESULTS_PORT,
    _extract_specs_from_result as _arnold_extract_specs,
    _read_specs_from_path as _arnold_read_specs,
    _specialize_step as _arnold_specialize_step,
    run_fanout as _arnold_run_fanout,
)
from arnold.pipeline.types import ContractResult, ContractStatus
from arnold.pipeline import reduce_contract_results

# ── Megaplan bridge hooks ────────────────────────────────────────────────
from arnold_pipelines.megaplan._pipeline.envelope import (
    EMPTY_ENVELOPE,
    _envelope_ctx,
    _fanout_active_ctx,
)
from arnold_pipelines.megaplan._pipeline.flags import typed_ports_on
from arnold_pipelines.megaplan._pipeline.pattern_types import JoinFn
from arnold_pipelines.megaplan._pipeline.subloop import SubloopStep
from arnold_pipelines.megaplan._pipeline.types import (
    PipelineVerdict,
    Port,
    Stage,
    Step,
    StepContext,
    StepResult,
)


#: Typed value-kind Port emitted by the fan-out join when typed-ports is on.
LAST_FANOUT_RESULTS_PORT: Port = Port(
    name="last_fanout_results",
    content_type="application/x-fanout-results+json",
)


def _passthrough_contract_result(
    results: Sequence[StepResult],
    *,
    child_ids: Sequence[str],
) -> ContractResult | None:
    """Preserve earlier suspended/failed child contracts across pass-through wrappers."""
    seen_contract = False
    saw_non_completed = False
    contracts: list[ContractResult | None] = []
    for result in results:
        contract = result.contract_result
        contracts.append(contract)
        if contract is None:
            continue
        seen_contract = True
        if contract.status is not ContractStatus.COMPLETED:
            saw_non_completed = True
    if not seen_contract:
        return None
    if not saw_non_completed:
        return results[-1].contract_result
    return reduce_contract_results(contracts, child_ids=child_ids)


def _governor_check_fanout(envelope, width: int) -> None:
    """Consult the tree-scoped Governor before spawning ``width`` fan-out specs.

    Raises :class:`megaplan.runtime.governor.BudgetExceeded` when a cap would
    be crossed.  No-op when no Governor is attached.  ``RestorableBoundaryViolation``
    raised by ``restorable_boundary.__enter__`` always precedes this check
    because the boundary fires before any protected body runs.
    """

    from arnold_pipelines.megaplan.runtime.governor import (
        BudgetExceeded,
        current_governor,
    )

    gov = current_governor()
    if gov is None:
        return
    reason = gov.would_exceed(envelope, fanout_width=width)
    if reason is not None:
        raise BudgetExceeded(reason, f"fanout width={width}")
    gov.note_fanout(width)


# ── Bridge helpers (delegate to Arnold, keep megaplan signatures) ────────


def _specialize_step(base: Step, spec: Any) -> Step:
    """Return a per-spec specialised copy of *base* — delegates to Arnold."""
    return cast(Step, _arnold_specialize_step(base, spec))


def _read_specs_from_path(path: Path) -> list[Any]:
    """Read a JSON list of reviewer specs from *path* — delegates to Arnold."""
    return _arnold_read_specs(path)


def _extract_specs_from_result(result: StepResult) -> list[Any]:
    """Pull a list of reviewer specs from a generator's StepResult.

    Flag-ON (``typed_ports_on()``): read the typed Port channel
    ``last_fanout_results`` from ``state_patch`` or ``outputs``;
    flag-OFF: preserve the untyped ``specs`` channel.

    Delegates to Arnold's implementation with the flag read here.
    """
    return _arnold_extract_specs(result, typed_ports=typed_ports_on())


# ── Subclassed steps (bridge wrappers around Arnold core) ────────────────


@dataclass(frozen=True)
class _PanelFromArtifactStep(SubloopStep):
    """SubloopStep subclass implementing :func:`panel_from_artifact`.

    Reads N specs from an upstream JSON artifact and fans out per spec.
    Governor/envelope hooks are megaplan policy; spec reading and step
    specialization delegate to Arnold helpers.
    """

    artifact_ref: str = ""
    base_template: Step | None = None
    join_fn: JoinFn | None = None

    def run(self, ctx: StepContext) -> StepResult:
        if self.base_template is None:
            raise ValueError(
                f"panel_from_artifact {self.name!r}: base_template is None"
            )
        if self.join_fn is None:
            raise ValueError(f"panel_from_artifact {self.name!r}: join is None")

        path: Path | None = None
        if isinstance(ctx.inputs, Mapping):
            raw = ctx.inputs.get(self.artifact_ref)
            if raw is not None:
                path = Path(raw)
        if path is None and isinstance(ctx.state, Mapping):
            raw = ctx.state.get(self.artifact_ref)
            if raw is not None:
                path = Path(raw)
        if path is None:
            raise LookupError(
                f"panel_from_artifact {self.name!r}: artifact "
                f"{self.artifact_ref!r} not found in ctx.inputs or ctx.state"
            )

        specs = _arnold_read_specs(path)
        steps = [_arnold_specialize_step(self.base_template, spec) for spec in specs]

        envelope = getattr(ctx, "envelope", None) or EMPTY_ENVELOPE
        _governor_check_fanout(envelope, len(steps))

        fanout_token = _fanout_active_ctx.set(True)
        env_token = _envelope_ctx.set(envelope)
        try:
            results = [step.run(ctx) for step in steps]
        finally:
            _envelope_ctx.reset(env_token)
            _fanout_active_ctx.reset(fanout_token)

        return self.join_fn(results, ctx)


@dataclass(frozen=True)
class _DynamicFanoutStep(SubloopStep):
    """SubloopStep subclass implementing :func:`dynamic_fanout`.

    Governor/envelope hooks are megaplan policy; the core fanout
    mechanics (generator → specs → specialize → run → join →
    typed port emission) delegate to :func:`arnold.pipeline.pattern_dynamic.run_fanout`.
    """

    generator: Step | None = None
    base_prompt: Step | None = None
    join_fn: JoinFn | None = None
    produces: tuple = field(default_factory=lambda: (LAST_FANOUT_RESULTS_PORT,))

    def run(self, ctx: StepContext) -> StepResult:
        if self.generator is None:
            raise ValueError(f"dynamic_fanout {self.name!r}: generator is None")
        if self.base_prompt is None:
            raise ValueError(f"dynamic_fanout {self.name!r}: base_prompt is None")
        if self.join_fn is None:
            raise ValueError(f"dynamic_fanout {self.name!r}: join is None")

        # ── Governor check ──────────────────────────────────────────
        envelope = getattr(ctx, "envelope", None) or EMPTY_ENVELOPE
        # We don't know the width yet — governor check will happen inside
        # run_fanout via the fanout width after spec extraction.
        # The governor is consulted via context; the actual width check
        # is best-effort: we note the fanout width for budget tracking.
        fanout_token = _fanout_active_ctx.set(True)
        env_token = _envelope_ctx.set(envelope)
        try:
            # ── Delegate to Arnold neutral fanout core ───────────────
            joined = _arnold_run_fanout(
                generator=self.generator,
                base_step=self.base_prompt,
                join_fn=self.join_fn,
                ctx=ctx,
                typed_ports=typed_ports_on(),
                before_run_steps=lambda steps: _governor_check_fanout(
                    envelope, len(steps)
                ),
            )
        finally:
            _envelope_ctx.reset(env_token)
            _fanout_active_ctx.reset(fanout_token)

        return cast(StepResult, joined)


# ── Public constructors ──────────────────────────────────────────────────


def panel_from_artifact(
    artifact_ref: str,
    base_template: Step,
    join: JoinFn,
    *,
    name: str,
) -> SubloopStep:
    """Read N reviewer specs from an upstream JSON artifact and run a copy per spec."""
    return _PanelFromArtifactStep(
        name=name,
        artifact_ref=artifact_ref,
        base_template=base_template,
        join_fn=join,
    )


def dynamic_fanout(
    generator: Step,
    base_prompt: Step,
    join: JoinFn,
    *,
    name: str,
) -> SubloopStep:
    """Run *generator* once, consume specs, and fan out *base_prompt* per spec.

    Core fanout mechanics are delegated to
    :func:`arnold.pipeline.pattern_dynamic.run_fanout`.
    """
    return _DynamicFanoutStep(
        name=name,
        generator=generator,
        base_prompt=base_prompt,
        join_fn=join,
    )


# ── Agreement / consensus (no Arnold dependency needed) ──────────────────


def _agreement_ratio(result: StepResult) -> float:
    """Compute the agreement ratio for a panel result."""

    if result.verdict is None:
        return 0.0
    payload = result.verdict.payload
    recommendations: list[Any] = []
    if isinstance(payload, Mapping):
        value = payload.get("per_reviewer_recommendations")
        if isinstance(value, list):
            recommendations = list(value)
    if not recommendations:
        return 1.0
    counts = Counter(recommendations)
    top = counts.most_common(1)[0][1]
    return float(top) / float(len(recommendations))


@dataclass(frozen=True)
class _ConsensusStep(SubloopStep):
    """SubloopStep subclass implementing :func:`iterate_until_consensus`."""

    panel: Any = None  # Step | Stage
    min_agreement: float = 0.8
    max_iters: int = 3
    condition: Optional[Callable[[Any], bool]] = None

    def run(self, ctx: StepContext) -> StepResult:
        if self.panel is None:
            raise ValueError(
                f"iterate_until_consensus {self.name!r}: panel is None"
            )

        panel_step: Step
        if isinstance(self.panel, Stage):
            panel_step = self.panel.step
        else:
            panel_step = cast(Step, self.panel)

        last_result: StepResult | None = None
        last_ratio = 0.0
        iteration_results: list[StepResult] = []
        for iteration in range(max(1, self.max_iters)):
            result = panel_step.run(ctx)
            last_result = result
            iteration_results.append(result)
            last_ratio = _agreement_ratio(result)
            if self.condition is not None:
                loop_state = type("LoopState", (), {
                    "state": ctx.state,
                    "last_fanout_results": dict(result.outputs),
                    "iteration": iteration + 1,
                })()
                if self.condition(loop_state):
                    merged = (
                        dict(result.state_patch)
                        if isinstance(result.state_patch, Mapping)
                        else {}
                    )
                    merged[f"consensus:{self.name}:agreement"] = last_ratio
                    merged[f"consensus:{self.name}:iterations"] = iteration + 1
                    return StepResult(
                        outputs=result.outputs,
                        verdict=result.verdict,
                        next="halt",
                        state_patch=merged,
                        contract_result=_passthrough_contract_result(
                            iteration_results,
                            child_ids=[
                                f"iteration_{index + 1}"
                                for index in range(len(iteration_results))
                            ],
                        ),
                    )
                continue
            if last_ratio >= self.min_agreement:
                merged = (
                    dict(result.state_patch)
                    if isinstance(result.state_patch, Mapping)
                    else {}
                )
                merged[f"consensus:{self.name}:agreement"] = last_ratio
                merged[f"consensus:{self.name}:iterations"] = iteration + 1
                return StepResult(
                    outputs=result.outputs,
                    verdict=result.verdict,
                    next="halt",
                    state_patch=merged,
                    contract_result=_passthrough_contract_result(
                        iteration_results,
                        child_ids=[
                            f"iteration_{index + 1}"
                            for index in range(len(iteration_results))
                        ],
                    ),
                )

        assert last_result is not None
        merged = (
            dict(last_result.state_patch)
            if isinstance(last_result.state_patch, Mapping)
            else {}
        )
        merged[f"consensus:{self.name}:agreement"] = last_ratio
        merged[f"consensus:{self.name}:iterations"] = max(1, self.max_iters)
        return StepResult(
            outputs=last_result.outputs,
            verdict=last_result.verdict,
            next="halt",
            state_patch=merged,
            contract_result=_passthrough_contract_result(
                iteration_results,
                child_ids=[
                    f"iteration_{index + 1}" for index in range(len(iteration_results))
                ],
            ),
        )


def iterate_until_consensus(
    panel: Step | Stage,
    min_agreement: float = 0.8,
    max_iters: int = 3,
    *,
    name: str,
) -> SubloopStep:
    """Repeatedly invoke *panel* until the agreement ratio threshold is met."""
    return _ConsensusStep(
        name=name,
        panel=panel,
        min_agreement=float(min_agreement),
        max_iters=int(max_iters),
    )


# ── Paired round (no Arnold dependency needed) ───────────────────────────


@dataclass(frozen=True)
class _PairedRoundStep:
    """Custom Step backing :func:`paired_round`."""

    name: str = "paired_round"
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    advocates: tuple[Step, ...] = ()
    sees_other: bool = True

    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        if not self.advocates:
            return StepResult(next="halt")

        prior_outputs: Mapping[str, Path] = {}
        outputs_accum: dict[str, Path] = {}
        last_result: StepResult | None = None
        advocate_results: list[StepResult] = []

        for advocate in self.advocates:
            base_inputs: dict[str, Path] = (
                dict(ctx.inputs) if isinstance(ctx.inputs, Mapping) else {}
            )
            if self.sees_other and prior_outputs:
                for label, path in prior_outputs.items():
                    base_inputs[f"prior.{label}"] = path
            advocate_ctx = dataclasses.replace(ctx, inputs=base_inputs)
            result = advocate.run(advocate_ctx)
            last_result = result
            advocate_results.append(result)
            prior_outputs = (
                dict(result.outputs) if isinstance(result.outputs, Mapping) else {}
            )
            for label, path in prior_outputs.items():
                outputs_accum[f"{advocate.name}.{label}"] = path

        assert last_result is not None
        return StepResult(
            outputs=outputs_accum,
            verdict=last_result.verdict,
            next=last_result.next,
            state_patch=last_result.state_patch,
            contract_result=_passthrough_contract_result(
                advocate_results,
                child_ids=[advocate.name for advocate in self.advocates],
            ),
        )


def paired_round(
    advocates: Sequence[Step],
    *,
    sees_other: bool = True,
    name: str,
) -> Stage:
    """Debate-style round where each advocate sees the other's argument."""
    if not advocates:
        raise ValueError("paired_round: advocates must be non-empty")

    return Stage(
        name=name,
        step=_PairedRoundStep(
            name=name,
            advocates=tuple(advocates),
            sees_other=sees_other,
        ),
        edges=(),
    )
