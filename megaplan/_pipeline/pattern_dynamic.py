"""Dynamic runtime primitives for pipeline pattern composition."""

from __future__ import annotations

import dataclasses
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence, cast

from megaplan._pipeline.pattern_types import JoinFn
from megaplan._pipeline.subloop import SubloopStep
from megaplan._pipeline.flags import typed_ports_on
from megaplan._pipeline.types import (
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


def _specialize_step(base: Step, spec: Any) -> Step:
    """Return a per-spec specialised copy of *base*."""

    if not isinstance(spec, Mapping):
        return base
    base_any: Any = base
    if dataclasses.is_dataclass(base_any) and not isinstance(base_any, type):
        valid = {field.name for field in dataclasses.fields(base_any)}
        kwargs = {key: value for key, value in spec.items() if key in valid}
        if kwargs:
            try:
                return cast(Step, dataclasses.replace(base_any, **kwargs))
            except TypeError:
                return base
    return base


def _read_specs_from_path(path: Path) -> list[Any]:
    """Read a JSON list of reviewer specs from *path*."""

    loaded = json.loads(Path(path).read_text())
    if not isinstance(loaded, list):
        raise ValueError(
            f"reviewer-spec artifact {str(path)!r} must be a JSON list, "
            f"got {type(loaded).__name__}"
        )
    return loaded


def _extract_specs_from_result(result: StepResult) -> list[Any]:
    """Pull a list of reviewer specs from a generator's StepResult.

    Flag-ON (``typed_ports_on()``): read the typed Port channel
    ``last_fanout_results`` from ``state_patch`` or ``outputs``;
    flag-OFF: preserve the untyped ``specs`` channel.
    """

    state_patch = result.state_patch
    outputs = result.outputs
    if typed_ports_on():
        port_name = LAST_FANOUT_RESULTS_PORT.name
        if isinstance(state_patch, Mapping):
            value = state_patch.get(port_name)
            if isinstance(value, list):
                return list(value)
        if isinstance(outputs, Mapping):
            out_path = outputs.get(port_name)
            if out_path is not None:
                return _read_specs_from_path(Path(out_path))
        raise LookupError(
            f"dynamic_fanout: generator emitted no typed Port "
            f"{port_name!r} (neither in state_patch nor outputs)"
        )
    if isinstance(state_patch, Mapping):
        value = state_patch.get("specs")
        if isinstance(value, list):
            return list(value)
    if isinstance(outputs, Mapping):
        out_path = outputs.get("specs")
        if out_path is not None:
            return _read_specs_from_path(Path(out_path))
    raise LookupError(
        "dynamic_fanout: generator emitted no 'specs' (neither in "
        "state_patch nor outputs)"
    )


@dataclass(frozen=True)
class _PanelFromArtifactStep(SubloopStep):
    """SubloopStep subclass implementing :func:`panel_from_artifact`."""

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

        specs = _read_specs_from_path(path)
        steps = [_specialize_step(self.base_template, spec) for spec in specs]
        results = [step.run(ctx) for step in steps]
        return self.join_fn(results, ctx)


@dataclass(frozen=True)
class _DynamicFanoutStep(SubloopStep):
    """SubloopStep subclass implementing :func:`dynamic_fanout`."""

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

        gen_result = self.generator.run(ctx)
        specs = _extract_specs_from_result(gen_result)
        steps = [_specialize_step(self.base_prompt, spec) for spec in specs]
        results = [step.run(ctx) for step in steps]
        joined = self.join_fn(results, ctx)
        if typed_ports_on():
            # Emit the typed Port last_fanout_results carrying the per-spec
            # StepResults; do NOT touch the untyped state_patch['specs'] channel.
            patch = dict(joined.state_patch) if isinstance(joined.state_patch, Mapping) else {}
            patch[LAST_FANOUT_RESULTS_PORT.name] = list(results)
            patch.pop("specs", None)
            joined = dataclasses.replace(joined, state_patch=patch)
        return joined


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
    """Run *generator* once, consume specs, and fan out *base_prompt* per spec."""

    return _DynamicFanoutStep(
        name=name,
        generator=generator,
        base_prompt=base_prompt,
        join_fn=join,
    )


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
        for iteration in range(max(1, self.max_iters)):
            result = panel_step.run(ctx)
            last_result = result
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
