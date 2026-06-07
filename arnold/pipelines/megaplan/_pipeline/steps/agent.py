"""Single-model markdown step: read inputs, render prompt, call worker, write output.

Writes ``<plan_dir>/<stage_id>/v<n>.md`` with the model's response.

Canonical Python-composition Step impl — not a YAML wrapper. Shared
input/prompt/version helpers live in
:mod:`megaplan._pipeline.step_helpers`.

M3a compatibility bridge; delete in M7.
Neutral equivalent: :class:`arnold.pipeline.steps.agent.AgentStep`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold.pipeline.runtime_contract_diagnostics import diagnostic_from_agent_capture
from arnold.pipeline.step_invocation import StepInvocation
from arnold.pipelines.megaplan.model_seam import (
    ModelStructuralAuditError,
    capture_step_output,
    render_step_message,
)
from arnold.pipelines.megaplan._pipeline.flags import typed_ports_on
from arnold.pipelines.megaplan._pipeline.step_helpers import (
    interpolate_inputs,
    next_version,
    resolve_inputs,
    resolve_prompt_text,
)
from arnold.pipelines.megaplan._pipeline.types import StepContext, StepResult


# Worker function type
WorkerFn = Callable[..., Any]


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
    _invocation: StepInvocation | None = None
    _invocation_explicit: bool | None = None

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
        contract_result = None

        if self._worker is not None:
            worker_inputs = {k: str(v) for k, v in inputs.items()}
            invocation_explicit = (
                self._invocation_explicit if self._invocation_explicit is not None else self._invocation is not None
            )
            if invocation_explicit and self._invocation is not None and self._invocation.kind == "model":
                worker_invocation = self._worker_facing_invocation(rendered)
                rendered_message = render_step_message(worker_invocation)
                worker_output = self._worker(
                    prompt=rendered_message.prompt,
                    step_name=self.name,
                    pipeline_name=self._pipeline_name,
                    inputs=worker_inputs,
                    mode=self._mode or ctx.mode,
                )
                try:
                    capture_outcome = capture_step_output(worker_invocation, worker_output)
                except ModelStructuralAuditError as exc:
                    diagnostic = diagnostic_from_agent_capture(
                        stage_name=self.name,
                        logical_type=self._primary_logical_type(),
                        failure_code="worker_structural_audit_failed",
                        detail=exc.details,
                    )
                    raise ValueError(diagnostic.message) from exc
                result_text = self._legacy_markdown_text(worker_output)
                contract_result = capture_outcome.contract_result
            else:
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
            contract_result=contract_result,
        )

    def _worker_facing_invocation(self, rendered_prompt: str) -> StepInvocation:
        invocation = self._invocation
        if invocation is None:
            raise ValueError("worker-facing invocation requested without a declared invocation")
        metadata = dict(invocation.metadata)
        adapter_config = metadata.get("adapter_config")
        worker_metadata = dict(adapter_config) if isinstance(adapter_config, Mapping) else {}
        worker_metadata.update(metadata)
        worker_metadata["prompt"] = rendered_prompt
        worker_metadata["message"] = rendered_prompt
        worker_metadata["prompt_components"] = rendered_prompt
        return StepInvocation(kind=invocation.kind, metadata=worker_metadata)

    @staticmethod
    def _legacy_markdown_text(worker_output: Any) -> str:
        if isinstance(worker_output, str):
            return worker_output
        if isinstance(worker_output, Mapping):
            return json.dumps(worker_output, indent=2, sort_keys=True, default=str)
        return str(worker_output)

    def _primary_logical_type(self) -> str:
        port = next((port for port in self.produces if getattr(port, "logical_type", None)), None)
        if port is None:
            return "unknown"
        return str(getattr(port, "logical_type", None) or "unknown")
