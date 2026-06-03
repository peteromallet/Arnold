"""Single-model markdown step: read inputs, render prompt, call worker, write output.

Writes ``<plan_dir>/<stage_id>/v<n>.md`` with the model's response.

Canonical Python-composition Step impl — not a YAML wrapper. Shared
input/prompt/version helpers live in
:mod:`megaplan._pipeline.step_helpers`.

M3a compatibility bridge; delete in M7.
Neutral equivalent: :class:`arnold.pipeline.steps.agent.AgentStep`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from megaplan._pipeline.flags import typed_ports_on
from megaplan._pipeline.step_helpers import (
    interpolate_inputs,
    next_version,
    resolve_inputs,
    resolve_prompt_text,
)
from megaplan._pipeline.types import StepContext, StepResult


# Worker function type
WorkerFn = Callable[..., str]


@dataclass
class AgentStep:
    """A single-model step: read inputs, render prompt, call worker, write output.

    Writes ``<plan_dir>/<stage_id>/v<n>.md``.
    """

    name: str
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None

    # Compiler-injected config
    _prompt_ref: str = ""
    _pipeline_dir: Path = field(default_factory=Path)
    _pipeline_name: str = ""
    _input_refs: list[str] = field(default_factory=list)
    _produces: str = "markdown"
    _worker: WorkerFn | None = None
    _prompt_registry: Callable[[str], str] | None = None
    _panel_reviewer_order: dict[str, list[str]] = field(default_factory=dict)
    _mode: str = ""

    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        # Flag-ON (M2 / T11b): read consumes' PortRefs by name instead of
        # the legacy `_input_refs` list. Flag-OFF preserves byte-identical
        # behaviour.
        if typed_ports_on():
            refs = [c.port_name for c in self.consumes]
        else:
            refs = self._input_refs
        inputs = resolve_inputs(
            refs,
            ctx,
            panel_reviewer_order=self._panel_reviewer_order,
        )
        prompt_text = resolve_prompt_text(
            self._prompt_ref,
            self._pipeline_dir,
            prompt_registry=self._prompt_registry,
        )
        # Interpolate input contents into prompt
        rendered = interpolate_inputs(prompt_text, inputs)

        output_dir = ctx.plan_dir / self.name
        output_dir.mkdir(parents=True, exist_ok=True)
        version = next_version(output_dir)
        output_path = output_dir / f"v{version}.md"

        if self._worker is not None:
            worker_inputs = {k: str(v) for k, v in inputs.items()}
            result_text = self._worker(
                prompt=rendered,
                step_name=self.name,
                pipeline_name=self._pipeline_name,
                inputs=worker_inputs,
                mode=self._mode or ctx.mode,
            )
        else:
            result_text = f"[AgentStep {self.name}] prompt: {self._prompt_ref}"

        output_path.write_text(result_text, encoding="utf-8")
        return StepResult(
            outputs={self.name: output_path},
            next="done",
        )
